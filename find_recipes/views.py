"""The shopping list planner: recipes (or the meal calendar's days) and extra items become a list to save."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from recipes import grocery
from recipes.access import readable, readable_locations
from recipes.community import can_edit
from recipes.costing import recipe_costing
from recipes.http import ApiError, api, body, positive_int
from recipes.models import Ingredient, Recipe, RecipeIngredient, SavedGroceryItem, SavedGroceryList
from recipes.seasons import current_month

MAX_RECIPES = 40
MAX_EXTRAS = 60
MULT_MIN, MULT_MAX = Decimal('0.25'), Decimal('20')


def _plan_recipes(user):
    month = current_month()
    qs = readable(Recipe, user).prefetch_related(
        'tags',
        Prefetch('recipeingredient_set', queryset=RecipeIngredient.objects.select_related('ingredient', 'unit')
                 .prefetch_related('ingredient__seasonal_availability', 'ingredient__shopping_links')),
    )
    out = []
    for r in qs:
        ris = list(r.recipeingredient_set.all())
        mains = [{'id': ri.ingredient_id, 'name': ri.ingredient.name,
                  'season': ri.ingredient.season_map().get(month, 'unknown')} for ri in ris if ri.is_main]
        costing = recipe_costing(ris)
        out.append({
            'id': r.pk, 'name': r.name, 'meal': r.meal_type, 'prep': r.prep_time, 'cook': r.cook_time,
            'difficulty': r.difficulty, 'tags': [t.pk for t in r.tags.all()],
            'ing': [ri.ingredient_id for ri in ris], 'main': mains,
            'inSeason': bool(mains) and all(m['season'] in ('in', 'early', 'late') for m in mains),
            'cost': float(costing['cost']) if costing['cost'] is not None else None,
            'priced': costing['priced'], 'count': costing['total'], 'promos': costing['promos'],
        })
    return out


class PlanView(LoginRequiredMixin, View):
    def get(self, request):
        recipes = _plan_recipes(request.user)
        locations = readable_locations(request.user).select_related('shop').order_by('shop__name', 'name')
        # ?recipe=<id> or <id>x<portions> (the meal calendar's "Shopping list for these days" also sends from / to)
        preselect = {}
        for raw in request.GET.getlist('recipe'):
            rid, _, mult = raw.partition('x')
            try:
                rid, mult = int(rid), Decimal(mult or '1')
            except (ValueError, InvalidOperation):
                continue
            if MULT_MIN <= mult <= MULT_MAX:
                preselect[rid] = float(mult)
        covers = _covers(request.GET)
        return render(request, 'plan/plan.html', {
            'page': 'plan',
            'weeks': _calendar_weeks(request.user, covers),
            'plan': {
                'recipes': recipes,
                'ingredients': list(readable(Ingredient, request.user).order_by('name').values_list('name', flat=True)),
                'locations': [{'id': l.pk, 'name': str(l), 'store': l.shop.shopping_store} for l in locations],
                'preselect': [{'id': k, 'mult': v} for k, v in preselect.items()],
                'covers': covers and {'from': covers[0].isoformat(), 'to': covers[1].isoformat(),
                                      'label': _covers_label(*covers)},
                'urls': {'receipt': reverse('plan-receipt'), 'save': reverse('plan-save')},
            },
        })


def _calendar_weeks(user, covers):
    """The rest of this week and next week, when the meal calendar has recipes to cook in them."""
    from meals.planning import meals_between, monday

    today = timezone.localdate()
    end = monday(today) + timedelta(days=6)
    out = []
    for label, start, stop in [('This week', today, end), ('Next week', end + timedelta(days=1), end + timedelta(days=7))]:
        n = sum(1 for m in meals_between(user, start, stop) if m.kind == 'recipe')
        if n:
            out.append({'label': label, 'meals': n, 'start': start.isoformat(), 'end': stop.isoformat(),
                        'on': covers == (start, stop)})
    return out


def _covers(data):
    """(from, to) days of the meal calendar a list is made for, when given."""
    try:
        start, end = date.fromisoformat(str(data.get('from'))), date.fromisoformat(str(data.get('to')))
    except (TypeError, ValueError):
        return None
    return (start, end) if start <= end else None


def _covers_label(start, end):
    if start == end:
        return start.strftime('%a %-d %b')
    return f"{start.strftime('%a %-d %b')} – {end.strftime('%a %-d %b')}"


def _selection(request):
    """(data, [(Recipe, multiplier)], extra Lines, location) from a planner request."""
    data = body(request)
    picks = data.get('recipes') or []
    extras = data.get('extras') or []
    if not isinstance(picks, list) or not isinstance(extras, list):
        raise ApiError('Invalid selection.')
    if not picks and not extras:
        raise ApiError('Pick a recipe or add an item.')
    if len(picks) > MAX_RECIPES:
        raise ApiError(f'At most {MAX_RECIPES} recipes at once.')
    if len(extras) > MAX_EXTRAS:
        raise ApiError(f'At most {MAX_EXTRAS} extra items.')
    mults = {}
    for p in picks:
        if not isinstance(p, dict):
            raise ApiError('Invalid selection.')
        rid = positive_int(p.get('id'), 'recipe')
        try:
            mult = Decimal(str(p.get('mult', 1)))
        except InvalidOperation:
            raise ApiError('Invalid portion multiplier.')
        if not MULT_MIN <= mult <= MULT_MAX:
            raise ApiError('Portions can be scaled from ×0.25 to ×20.')
        mults[rid] = mult
    recipes = list(readable(Recipe, request.user).filter(pk__in=mults)) if mults else []
    if mults and not recipes:
        raise ApiError('None of these recipes exist (any more).', 404)
    location = None
    if data.get('location'):
        location = readable_locations(request.user).select_related('shop').filter(
            pk=positive_int(data['location'], 'location')).first()
        if location is None:
            raise ApiError('Unknown shop location.', 404)
    return data, [(r, mults[r.pk]) for r in recipes], _extra_lines(request.user, extras), location


def _extra_lines(user, names):
    """Items added by hand: a known ingredient's name becomes that ingredient (its aisle, its price), else free text."""
    clean = []
    for raw in names:
        name = ' '.join(str(raw).split())[:120]
        if name and name.lower() not in {n.lower() for n in clean}:
            clean.append(name)
    wanted = {n.lower() for n in clean}
    known = {i.name.lower(): i for i in readable(Ingredient, user).prefetch_related('seasonal_availability')
             if i.name.lower() in wanted} if clean else {}
    return [grocery.Line(ingredient=known.get(n.lower()), custom_name='' if n.lower() in known else n,
                         amount=Decimal(1)) for n in clean]


def _lines(picks, extras):
    lines = grocery.merge_recipes(picks) if picks else []
    have = {l.ingredient.pk for l in lines}
    return lines + [l for l in extras if not l.ingredient or l.ingredient.pk not in have]


@api
def receipt(request):
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    _, picks, extras, location = _selection(request)
    return JsonResponse(grocery.receipt(_lines(picks, extras), location, request.user))


@api
def save(request):
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    if not can_edit(request.user, SavedGroceryList):
        raise ApiError('Your community does not let you save lists.', 403)
    data, picks, extras, location = _selection(request)
    lines = _lines(picks, extras)
    if not lines:
        raise ApiError('These recipes have no ingredients.')
    covers = _covers(data.get('covers') or {})
    name = ' '.join(str(data.get('name') or '').split())[:200] or (
        f'Meals {_covers_label(*covers)}' if covers else f'Shopping list — {timezone.localdate().strftime("%-d %B")}')
    with transaction.atomic():
        saved = SavedGroceryList.objects.create(name=name, owner=request.user, location=location,
                                                covers_from=covers and covers[0], covers_to=covers and covers[1])
        saved.recipes.set([r for r, _ in picks])
        SavedGroceryItem.objects.bulk_create([
            SavedGroceryItem(grocery_list=saved, ingredient=l.ingredient, custom_name=l.custom_name,
                             quantity=max(l.amount, Decimal('0.01')), unit=l.unit, owner=request.user)
            for l in lines
        ])
    return JsonResponse({'id': saved.pk, 'url': reverse('saved-grocery-detail', args=[saved.pk])}, status=201)
