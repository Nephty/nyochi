"""What a recipe costs, from the prices Shopping last gave for its ingredients' linked products, and where those can't
price an amount (a tablespoon of a bottle, a piece of a pack sold by weight...) from prices entered by hand
(UnitPrice), which are marked as such: Shopping never updates them."""
from decimal import Decimal

from . import shopping

CENT = Decimal('0.01')


def manual_cost(amount, unit, prices):
    """(cost, UnitPrice) from the ingredient's prices entered by hand: one for this very unit, else one for a unit of
    the same kind (2 tsp from a price per tbsp, 300 ml from a price per litre); (None, None) without one.
    prices: the ingredient's UnitPrice rows (unit_prices__unit prefetched)."""
    if unit is None:
        return None, None
    for p in prices:
        if p.unit_id == unit.pk:
            return (Decimal(amount) * p.price).quantize(CENT), p
    if unit.mergeable:
        for p in prices:
            if p.unit.mergeable and p.unit.dimension == unit.dimension:
                return (Decimal(amount) * unit.factor / p.unit.factor * p.price).quantize(CENT), p
    return None, None


def ingredient_cost(ri, link=None):
    """What one recipe ingredient costs: {'cost', 'source': 'shopping' | 'manual' | None, 'manual': UnitPrice}.
    A linked product that can price the amount wins; a price entered by hand fills the gap."""
    if link is not None:
        cost = shopping.cost_for_amount(ri.quantity, ri.unit, link)
        if cost is not None:
            return {'cost': cost, 'source': 'shopping', 'manual': None}
    cost, price = manual_cost(ri.quantity, ri.unit, list(ri.ingredient.unit_prices.all()))
    if cost is not None:
        return {'cost': cost, 'source': 'manual', 'manual': price}
    return {'cost': None, 'source': None, 'manual': None}


def recipe_costing(recipe_ingredients, store=''):
    """recipe_ingredients: RecipeIngredient rows with ingredient__shopping_links and ingredient__unit_prices__unit
    prefetched. Cost is proportional to what the recipe uses (a quarter of a 1 kg pack costs a quarter of its price);
    ingredients priced neither way just aren't counted. A recipe is for one portion."""
    total, saving, priced, manual, promos, count = Decimal(0), Decimal(0), 0, 0, 0, 0
    for ri in recipe_ingredients:
        count += 1
        link = shopping.pick_link(list(ri.ingredient.shopping_links.all()), store)
        if link and shopping.promo_active(link):
            promos += 1
        row = ingredient_cost(ri, link)
        if row['cost'] is None:
            continue
        priced += 1
        total += row['cost']
        if row['source'] == 'manual':
            manual += 1
        elif shopping.promo_active(link) and link.deal_saving and link.pack_amount:
            # the promotion's saving, scaled like the cost (a deal on a pack, used partly)
            saving += (link.deal_saving / (link.deal_qty or 1) * (row['cost'] / link.price)).quantize(CENT)
    return {
        'cost': total if priced else None, 'priced': priced, 'manual': manual, 'total': count, 'promos': promos,
        'saving': saving if saving else None,
    }
