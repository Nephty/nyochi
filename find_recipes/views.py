"""Plan: choose recipes (filtering happens in the browser over the data below), see the shopping list build up."""
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
from recipes.costing import recipe_costing
from recipes.http import ApiError, api, body, positive_int
from recipes.models import Recipe, RecipeIngredient, SavedGroceryItem, SavedGroceryList, Tag
from recipes.seasons import current_month

MAX_RECIPES = 40
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
        used = {i for r in recipes for i in r['ing']}
        ingredient_names = {}
        for ri in RecipeIngredient.objects.filter(ingredient_id__in=used).select_related('ingredient').distinct():
            ingredient_names[ri.ingredient_id] = ri.ingredient.name
        locations = readable_locations(request.user).select_related('shop').order_by('shop__name', 'name')
        preselect = []
        for raw in request.GET.getlist('recipe'):
            try:
                preselect.append(int(raw))
            except ValueError:
                pass
        return render(request, 'plan/plan.html', {
            'page': 'plan',
            'plan': {
                'recipes': recipes,
                'tags': [{'id': t.pk, 'name': t.name} for t in readable(Tag, request.user)],
                'ingredients': sorted(({'id': k, 'name': v} for k, v in ingredient_names.items()),
                                      key=lambda i: i['name'].lower()),
                'locations': [{'id': l.pk, 'name': str(l), 'store': l.shop.shopping_store} for l in locations],
                'meals': [{'value': v, 'label': l} for v, l in Recipe.MealType.choices],
                'preselect': preselect,
                'urls': {'receipt': reverse('plan-receipt'), 'save': reverse('plan-save')},
            },
        })


def _selection(request):
    data = body(request)
    picks = data.get('recipes')
    if not isinstance(picks, list) or not picks:
        raise ApiError('Pick at least one recipe.')
    if len(picks) > MAX_RECIPES:
        raise ApiError(f'At most {MAX_RECIPES} recipes at once.')
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
    recipes = list(readable(Recipe, request.user).filter(pk__in=mults))
    if not recipes:
        raise ApiError('None of these recipes exist (any more).', 404)
    location = None
    if data.get('location'):
        location = readable_locations(request.user).select_related('shop').filter(
            pk=positive_int(data['location'], 'location')).first()
        if location is None:
            raise ApiError('Unknown shop location.', 404)
    return data, [(r, mults[r.pk]) for r in recipes], location


@api
def receipt(request):
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    _, picks, location = _selection(request)
    return JsonResponse(grocery.receipt(grocery.merge_recipes(picks), location, request.user))


@api
def save(request):
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    data, picks, location = _selection(request)
    lines = grocery.merge_recipes(picks)
    if not lines:
        raise ApiError('These recipes have no ingredients.')
    name = ' '.join(str(data.get('name') or '').split())[:200] or \
        f'Shopping list — {timezone.localdate().strftime("%B %-d")}'
    with transaction.atomic():
        saved = SavedGroceryList.objects.create(name=name, owner=request.user, location=location)
        saved.recipes.set([r for r, _ in picks])
        SavedGroceryItem.objects.bulk_create([
            SavedGroceryItem(grocery_list=saved, ingredient=l.ingredient, quantity=max(l.amount, Decimal('0.01')),
                             unit=l.unit, owner=request.user)
            for l in lines
        ])
    return JsonResponse({'id': saved.pk, 'url': reverse('saved-grocery-detail', args=[saved.pk])}, status=201)
