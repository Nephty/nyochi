from django.db.models import Sum
from django.utils import timezone

from .models import (
    AisleOrder, CategoryAisleMapping, Ingredient, IngredientCategory,
    Recipe, RecipeIngredient, SavedGroceryItem, SavedGroceryList,
    ShopLocation, Unit,
)

MONTHS = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]


def is_htmx(request):
    return request.headers.get('HX-Request') == 'true'


_LOCATION_QS = lambda: ShopLocation.objects.select_related('shop').order_by('shop__name', 'name')


def _compute_grocery_list(recipes, location):
    """Aggregate ingredients from recipes, optionally sorted by aisle order."""
    rows = (
        RecipeIngredient.objects
        .filter(recipe__in=recipes)
        .values('ingredient', 'unit')
        .annotate(total=Sum('quantity'))
        .order_by('ingredient__category', 'ingredient__name')
    )

    ingredient_ids = [r['ingredient'] for r in rows]
    unit_ids = [r['unit'] for r in rows]
    ingredients_map = {i.pk: i for i in Ingredient.objects.filter(pk__in=ingredient_ids)}
    units_map = {u.pk: u for u in Unit.objects.filter(pk__in=unit_ids)}

    grouped: dict[str, list] = {}
    for row in rows:
        ingredient = ingredients_map[row['ingredient']]
        unit = units_map[row['unit']]
        cat = ingredient.get_category_display()
        grouped.setdefault(cat, []).append({
            'ingredient': ingredient,
            'total': row['total'],
            'unit': unit,
        })

    aisle_label: dict[str, str] = {}
    if location:
        aisle_orders = {
            ao.aisle_id: ao.order
            for ao in AisleOrder.objects.filter(location=location).select_related('aisle')
        }
        cat_display = dict(IngredientCategory.choices)
        cat_order: dict[str, int] = {}
        for m in CategoryAisleMapping.objects.filter(location=location).select_related('aisle'):
            display = cat_display.get(m.category, m.category)
            cat_order[display] = aisle_orders.get(m.aisle_id, 9999)
            aisle_label[display] = m.aisle.name
        grouped = dict(
            sorted(grouped.items(), key=lambda kv: (cat_order.get(kv[0], 9999), kv[0]))
        )

    return grouped, aisle_label


def _save_grocery_list(recipe_pks):
    """Create a SavedGroceryList from a list of recipe PKs and return it."""
    recipes = list(Recipe.objects.filter(pk__in=recipe_pks))
    if not recipes:
        return None

    rows = (
        RecipeIngredient.objects
        .filter(recipe__in=recipes)
        .values('ingredient', 'unit')
        .annotate(total=Sum('quantity'))
    )

    name = f'Shopping list — {timezone.localdate().strftime("%B %-d, %Y")}'
    saved = SavedGroceryList.objects.create(name=name)
    saved.recipes.set(recipes)

    ingredient_ids = [r['ingredient'] for r in rows]
    unit_ids       = [r['unit']       for r in rows]
    ingredients_map = {i.pk: i for i in Ingredient.objects.filter(pk__in=ingredient_ids)}
    units_map       = {u.pk: u for u in Unit.objects.filter(pk__in=unit_ids)}

    SavedGroceryItem.objects.bulk_create([
        SavedGroceryItem(
            grocery_list=saved,
            ingredient=ingredients_map[r['ingredient']],
            quantity=r['total'],
            unit=units_map[r['unit']],
        )
        for r in rows
    ])
    return saved


def _sorted_grocery_items(saved, location):
    """Return (grouped_dict, aisle_label_dict) for a SavedGroceryList."""
    items = list(saved.items.select_related('ingredient', 'unit'))
    aisle_label: dict[str, str] = {}

    if location:
        aisle_orders = {
            ao.aisle_id: ao.order
            for ao in AisleOrder.objects.filter(location=location)
        }
        cat_display = dict(IngredientCategory.choices)
        cat_order: dict[str, int] = {}
        for m in CategoryAisleMapping.objects.filter(location=location).select_related('aisle'):
            display = cat_display.get(m.category, m.category)
            cat_order[display] = aisle_orders.get(m.aisle_id, 9999)
            aisle_label[display] = m.aisle.name
        items.sort(key=lambda i: (
            cat_order.get(i.ingredient.get_category_display(), 9999),
            i.ingredient.get_category_display(),
            i.ingredient.name,
        ))
    else:
        items.sort(key=lambda i: (i.ingredient.get_category_display(), i.ingredient.name))

    grouped: dict[str, list] = {}
    for item in items:
        grouped.setdefault(item.ingredient.get_category_display(), []).append(item)
    return grouped, aisle_label
