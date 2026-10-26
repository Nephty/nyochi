"""Turning recipes into a shopping list: merge amounts, walk the shop's layout, price with Shopping."""
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from . import categories, shopping
from .models import AisleOrder, CategoryAisleMapping, IngredientAisle, RecipeIngredient, ShoppingLink, Unit
from .seasons import current_month

TWO = Decimal('0.01')


@dataclass
class Line:
    ingredient: object = None            # Ingredient, or None for a hand-typed item
    custom_name: str = ''
    amount: Decimal = Decimal(0)
    unit: object = None                  # Unit
    sources: list = field(default_factory=list)
    item_id: int | None = None
    checked: bool = False
    category_label: str = ''             # set by group_lines from the viewer's categories

    @property
    def name(self):
        return self.ingredient.name if self.ingredient else self.custom_name


# ------------------------------------------------------------------ merging

def _metric_units():
    """{(dimension, factor): Unit} for g, kg, ml, l and the piece, used to show 1500 g as 1.5 kg."""
    return {
        (u.dimension, u.factor): u
        for u in Unit.objects.filter(dimension__in=['mass', 'volume', 'count'], factor__in=[1, 1000])
    }


def _tidy(base: Decimal, units, used_units):
    """(amount, unit) for `base` (in g / ml / pieces), in the friendliest unit that exists."""
    first = used_units[0]
    dim = first.dimension
    if dim in ('mass', 'volume') and (len(used_units) > 1 or first.factor in (1, 1000)):
        big, small = units.get((dim, Decimal(1000))), units.get((dim, Decimal(1)))
        if big and small:
            return (base / 1000, big) if base >= 1000 else (base, small)
    if len(used_units) == 1:
        return base / first.factor, first
    if dim == 'count' and (dim, Decimal(1)) in units:
        return base, units[(dim, Decimal(1))]
    return base / first.factor, first


def _q(value) -> Decimal:
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def merge_recipes(recipe_mults) -> list[Line]:
    """recipe_mults: [(Recipe, Decimal multiplier)] -> one Line per ingredient (and per non-comparable unit)."""
    mult = {r.pk: Decimal(m) for r, m in recipe_mults}
    rows = (
        RecipeIngredient.objects.filter(recipe_id__in=mult)
        .select_related('ingredient', 'unit', 'recipe')
        .prefetch_related('ingredient__seasonal_availability')
    )
    groups = defaultdict(lambda: {'base': Decimal(0), 'units': [], 'ingredient': None, 'sources': []})
    for ri in rows:
        unit = ri.unit
        amount = ri.quantity * mult[ri.recipe_id]
        key = (ri.ingredient_id, unit.dimension if unit.mergeable else f'u{unit.pk}')
        g = groups[key]
        g['ingredient'] = ri.ingredient
        g['base'] += amount * unit.factor if unit.mergeable else amount
        if unit not in g['units']:
            g['units'].append(unit)
        if ri.recipe.name not in g['sources']:
            g['sources'].append(ri.recipe.name)
    metric = _metric_units()
    lines = []
    for g in groups.values():
        if g['units'][0].mergeable:
            amount, unit = _tidy(g['base'], metric, g['units'])
        else:
            amount, unit = g['base'], g['units'][0]
        lines.append(Line(ingredient=g['ingredient'], amount=_q(amount), unit=unit, sources=g['sources']))
    return lines


def lines_from_items(items) -> list[Line]:
    """A saved list's items as Lines (the amounts were merged when the list was saved)."""
    return [
        Line(ingredient=i.ingredient, custom_name=i.custom_name, amount=i.quantity, unit=i.unit,
             item_id=i.pk, checked=i.in_cart)
        for i in items
    ]


# ------------------------------------------------------------------ the shop's layout

class Layout:
    """Where things are at one ShopLocation: aisle walking order, category -> aisle, per-ingredient exceptions."""

    def __init__(self, location):
        self.location = location
        orders = AisleOrder.objects.filter(location=location).select_related('aisle')
        self.order = {o.aisle_id: o.order for o in orders}
        self.names = {o.aisle_id: o.aisle.name for o in orders}
        self.by_category = {}
        for m in CategoryAisleMapping.objects.filter(location=location).select_related('aisle'):
            self.by_category[m.category] = m.aisle_id
            self.names[m.aisle_id] = m.aisle.name
        self.overrides = {}
        for o in IngredientAisle.objects.filter(location=location).select_related('aisle'):
            self.overrides[o.ingredient_id] = o.aisle_id
            self.names[o.aisle_id] = o.aisle.name

    def aisle_of(self, line):
        if not line.ingredient:
            return None
        return self.overrides.get(line.ingredient.pk) or self.by_category.get(line.ingredient.category)

    def sort_key(self, aisle_id):
        # walking order first, then aisles nobody gave a position, by name
        if aisle_id in self.order:
            return (0, self.order[aisle_id], '')
        return (1, 0, self.names.get(aisle_id, '').lower())


def group_lines(lines, layout: Layout | None, labels=None):
    """[{key, title, kind, stop, lines}]: by aisle in walking order when there's a layout, else by category.
    Stops (1, 2, 3...) number the sections in the order you'll reach them.
    `labels` = the viewer's {category key: name}, in their order (default: the built-in categories)."""
    labels = categories.DEFAULT_LABELS if labels is None else labels
    position = {k: i for i, k in enumerate(labels)}
    for line in lines:
        line.category_label = categories.label_of(line.ingredient.category, labels) if line.ingredient else 'Extras'
    buckets = defaultdict(list)
    for line in lines:
        if not line.ingredient:
            buckets[('extras', None)].append(line)
        elif layout:
            aisle = layout.aisle_of(line)
            buckets[('aisle', aisle) if aisle else ('elsewhere', None)].append(line)
        else:
            buckets[('category', line.ingredient.category)].append(line)

    def rank(bucket_key):
        kind, ref = bucket_key
        if kind == 'aisle':
            return (0, layout.sort_key(ref))
        if kind == 'category':
            return (0, (0, position.get(ref, 999), categories.label_of(ref, labels)))
        return ({'elsewhere': 1, 'extras': 2}[kind], (0, 0, ''))

    sections = []
    for bucket_key in sorted(buckets, key=rank):
        kind, ref = bucket_key
        title = {
            'aisle': lambda: layout.names[ref], 'category': lambda: categories.label_of(ref, labels),
            'elsewhere': lambda: 'Elsewhere', 'extras': lambda: 'Extras',
        }[kind]()
        sections.append({
            'key': f'{kind}:{ref}' if ref else kind, 'title': title, 'kind': kind,
            'lines': sorted(buckets[bucket_key], key=lambda l: (l.category_label.lower(), l.name.lower())),
        })
    stop = 0
    for s in sections:
        if layout and s['kind'] in ('aisle', 'elsewhere'):
            stop += 1
            s['stop'] = stop
        else:
            s['stop'] = None
    return sections


# ------------------------------------------------------------------ pricing and JSON

def _amount(value: Decimal):
    value = Decimal(value)
    return int(value) if value == value.to_integral_value() else float(value)


def receipt(lines, location=None, user=None):
    """Everything the list/plan screens draw: sections, lines with the product to buy, totals."""
    layout = Layout(location) if location else None
    sections = group_lines(lines, layout, categories.labels_for(user, location.shop.owner_id) if user and location
                           else categories.user_labels(user) if user else None)
    ingredient_ids = {l.ingredient.pk for l in lines if l.ingredient}
    links = defaultdict(list)
    all_links = list(ShoppingLink.objects.filter(ingredient_id__in=ingredient_ids))
    reachable = shopping.refresh(all_links) if all_links else True
    for link in all_links:
        links[link.ingredient_id].append(link)
    store = location.shop.shopping_store if location else ''
    month = current_month()

    total, saving, priced, per_store = Decimal(0), Decimal(0), 0, {}
    out = []
    for section in sections:
        rows = []
        for line in section['lines']:
            row = {
                'id': line.item_id, 'name': line.name, 'category': line.category_label,
                'ingredient_id': line.ingredient.pk if line.ingredient else None,
                'amount': _amount(line.amount) if line.unit else None,
                'unit': line.unit.abbreviation if line.unit else '',
                'unit_name': line.unit.name if line.unit else '',
                'checked': line.checked, 'sources': line.sources,
                'season': line.ingredient.season_status_for_month(month) if line.ingredient else None,
                'buy': None,
            }
            options = links.get(line.ingredient.pk, []) if line.ingredient else []
            pick = shopping.pick_link(options, store)
            if pick and line.unit:
                p = shopping.price_line(line.amount, line.unit, pick)
                row['buy'] = {**shopping.link_json(pick), 'packs': p['packs'], 'cost': float(p['cost']),
                              'saving': float(p['saving']), 'exact': p['exact'],
                              'others': len(options) - 1}
                total += p['cost']
                saving += p['saving']
                priced += 1
            if line.unit and options:
                by_store = defaultdict(list)
                for link in options:
                    by_store[link.store].append(link)
                for st, group in by_store.items():
                    best = shopping.pick_link(group)
                    if not best:
                        continue
                    s = per_store.setdefault(st, {'store': st, 'label': best.store_label or st,
                                                  'lines': 0, 'cost': Decimal(0)})
                    s['lines'] += 1
                    s['cost'] += shopping.price_line(line.amount, line.unit, best)['cost']
            rows.append(row)
        out.append({'key': section['key'], 'title': section['title'], 'kind': section['kind'],
                    'stop': section['stop'], 'lines': rows})
    n = sum(len(s['lines']) for s in out)
    return {
        'sections': out,
        'totals': {
            'lines': n, 'priced': priced, 'unpriced': n - priced,
            'cost': float(total), 'saving': float(saving), 'after_deals': float(total - saving),
        },
        'stores': sorted(
            ({'store': s['store'], 'label': s['label'], 'lines': s['lines'], 'cost': float(s['cost'])}
             for s in per_store.values()),
            key=lambda s: (-s['lines'], s['cost'])),
        'shopping': {'configured': shopping.configured(), 'reachable': reachable},
        'location': {'id': location.pk, 'name': str(location), 'routed': True} if location else None,
    }
