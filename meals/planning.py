"""What the calendar pages need: weeks, meals as JSON, the recipes to choose from, the link to Plan, shared ingredients."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from recipes.access import readable
from recipes.models import Recipe, RecipeIngredient, SavedGroceryList

from .models import Meal

SLOTS = [value for value, _ in Meal.Slot.choices]
SLOT_LABELS = dict(Meal.Slot.choices)
SLOT_ICONS = {'breakfast': 'breakfast_dining', 'lunch': 'lunch_dining', 'snack': 'cookie', 'dinner': 'dinner_dining'}
# which recipes suit a slot first (Recipe.meal_type); any recipe can still be put anywhere
SLOT_MEALS = {'breakfast': ['breakfast'], 'lunch': ['full_meal'], 'snack': ['snack', 'desert'], 'dinner': ['full_meal']}
MAX_RANGE = 62  # days a shopping list or the assistant may cover


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def parse_day(raw, default=None):
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return default


def slot_order(meal):
    return (meal.day, SLOTS.index(meal.slot) if meal.slot in SLOTS else 9, meal.position, meal.pk)


def meals_between(user, start, end):
    """The community's meals from start to end (both included), in calendar order."""
    qs = readable(Meal, user).filter(day__gte=start, day__lte=end).select_related('recipe', 'leftover_of').prefetch_related('leftovers')
    return sorted(qs, key=slot_order)


def meal_json(m):
    return {
        'id': m.pk, 'day': m.day.isoformat(), 'slot': m.slot, 'kind': m.kind, 'name': m.name,
        'recipe': m.recipe_id, 'title': m.title, 'mult': float(m.mult), 'note': m.note,
        'cooked': m.cooked_at is not None, 'leftover_of': m.leftover_of_id,
        'leftovers': [l.pk for l in m.leftovers.all()] if m.kind == 'recipe' else [],
    }


def recipes_json(user):
    """The Plan screen's recipe data (season, cost, promotions...) plus when each was last cooked."""
    from find_recipes.views import _plan_recipes

    rows = _plan_recipes(user)
    cooked = dict(readable(Meal, user).filter(recipe__isnull=False, cooked_at__isnull=False)
                  .values('recipe').annotate(at=Max('cooked_at')).values_list('recipe', 'at'))
    for r in rows:
        at = cooked.get(r['id'])
        r['lastCooked'] = timezone.localtime(at).date().isoformat() if at else None
    return rows


def history(user, start, end):
    """Planned meals around a range (three weeks before it to its end), for "not recently" and "variety"."""
    qs = readable(Meal, user).filter(day__gte=start - timedelta(days=21), day__lte=end, recipe__isnull=False,
                                     leftover_of__isnull=True)
    return [{'day': d.isoformat(), 'recipe': r} for d, r in qs.values_list('day', 'recipe')]


def to_buy(meals):
    """{recipe: multiplier} for the meals that are cooked from a recipe (leftovers and free text buy nothing)."""
    out = defaultdict(Decimal)
    for m in meals:
        if m.kind == 'recipe':
            out[m.recipe_id] += m.mult
    return out


def plan_url(user, start, end):
    """Plan, preset with the recipes of these days (portions summed) and the days, so a saved list remembers them."""
    picks = to_buy(meals_between(user, start, end))
    query = [f'recipe={rid}x{_num(mult)}' for rid, mult in picks.items()]
    query += [f'from={start.isoformat()}', f'to={end.isoformat()}']
    return f"{reverse('plan')}?{'&'.join(query)}"


def _num(d: Decimal):
    return format(d.normalize(), 'f')


def ingredient_names(recipes):
    """{ingredient id: name} for the ingredients of these recipe rows (recipes_json), for the week's "used twice"."""
    ids = {i for r in recipes for i in r['ing']}
    return {str(k): v for k, v in RecipeIngredient.objects.filter(ingredient_id__in=ids)
            .values_list('ingredient_id', 'ingredient__name').distinct()}


def lists_covering(user, start, end):
    """Saved lists (not archived) made from the calendar for days in this range."""
    qs = readable(SavedGroceryList, user).filter(archived=False, covers_from__isnull=False,
                                                 covers_from__lte=end, covers_to__gte=start)
    return [{'id': l.pk, 'name': l.name, 'from': l.covers_from.isoformat(), 'to': l.covers_to.isoformat(),
             'url': reverse('saved-grocery-detail', args=[l.pk])} for l in qs]


def slot_for(recipe):
    """The slot a recipe goes to by default: its meal type's."""
    return {'breakfast': 'breakfast', 'snack': 'snack', 'desert': 'snack'}.get(recipe.meal_type, 'dinner')


def today_meals(user):
    return meals_between(user, timezone.localdate(), timezone.localdate())


def recipe_calendar(user, recipe):
    """For a recipe page: when it was last cooked and when it is planned next."""
    today = timezone.localdate()
    qs = readable(Meal, user).filter(recipe=recipe, leftover_of__isnull=True)
    last = qs.filter(cooked_at__isnull=False).aggregate(at=Max('cooked_at'))['at']
    nxt = qs.filter(day__gte=today).filter(Q(cooked_at__isnull=True)).order_by('day').first()
    return {
        'last_cooked': timezone.localtime(last).date() if last else None,
        'last_days': (today - timezone.localtime(last).date()).days if last else None,
        'next': nxt,
    }
