"""What a recipe costs, from the prices Shopping last gave for its ingredients' linked products."""
from decimal import Decimal

from . import shopping


def recipe_costing(recipe_ingredients, store=''):
    """recipe_ingredients: RecipeIngredient rows with ingredient__shopping_links prefetched.
    Cost is proportional to what the recipe uses (a quarter of a 1 kg pack costs a quarter of its price);
    ingredients without a comparable pack just aren't counted."""
    total, saving, priced, promos, count = Decimal(0), Decimal(0), 0, 0, 0
    for ri in recipe_ingredients:
        count += 1
        link = shopping.pick_link(list(ri.ingredient.shopping_links.all()), store)
        if not link:
            continue
        cost = shopping.cost_for_amount(ri.quantity, ri.unit, link)
        if shopping.promo_active(link):
            promos += 1
        if cost is None:
            continue
        priced += 1
        total += cost
        if shopping.promo_active(link) and link.deal_saving and link.pack_amount:
            # the promotion's saving, scaled like the cost (a deal on a pack, used partly)
            saving += (link.deal_saving / (link.deal_qty or 1) * (cost / link.price)).quantize(Decimal('0.01'))
    return {
        'cost': total if priced else None, 'priced': priced, 'total': count, 'promos': promos,
        'saving': saving if saving else None,
    }
