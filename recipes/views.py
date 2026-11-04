from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from meals import planning as meal_planning
from meals import views as meal_views

from . import kitchen, shopping
from .access import deletable, is_owner, readable, writable
from .community import can_edit
from .costing import ingredient_cost, recipe_costing
from .forms import RecipeForm, RecipeIngredientFormSet
from .http import ApiError, api, body
from .models import (
    Ingredient, Recipe, RecipeIngredient, SavedGroceryList, Shop, ShoppingLink, Tag, Unit,
)
from .seasons import current_month, distribution


def _recipes_with_everything(user):
    return readable(Recipe, user).prefetch_related(
        'tags',
        Prefetch('recipeingredient_set', queryset=RecipeIngredient.objects.select_related('ingredient', 'unit')
                 .prefetch_related('ingredient__seasonal_availability', 'ingredient__shopping_links',
                                  'ingredient__unit_prices__unit')),
    )


class RecipeListView(LoginRequiredMixin, View):
    def get(self, request):
        month = current_month()
        recipes = []
        for r in _recipes_with_everything(request.user):
            ris = list(r.recipeingredient_set.all())
            mains = [ri for ri in ris if ri.is_main]
            seasons = [{'ingredient': ri.ingredient, 'status': ri.ingredient.season_map().get(month, 'unknown')}
                       for ri in mains]
            costing = recipe_costing(ris)
            r.card = {
                'seasons': seasons,
                'in_season': bool(seasons) and all(s['status'] in ('in', 'early', 'late') for s in seasons),
                'dist': distribution(ri.ingredient.season_map().get(month, 'unknown') for ri in ris),
                'ingredient_count': len(ris),
                'costing': costing,
                'mine': is_owner(r, request.user),
            }
            recipes.append(r)

        # promotions on products linked to ingredients of the recipes you can see
        recipe_by_ing = {}
        for r in recipes:
            for ri in r.recipeingredient_set.all():
                recipe_by_ing.setdefault(ri.ingredient_id, (ri.ingredient, []))[1].append(r)
        deals = []
        for ing_id, (ing, rs) in recipe_by_ing.items():
            link = shopping.pick_link(list(ing.shopping_links.all()))
            if link and shopping.promo_active(link):
                deals.append({'ingredient': ing, 'link': link, 'verdict': shopping.verdict(link),
                              'deal': shopping.deal_text(link), 'recipes': rs[:3]})
        deals.sort(key=lambda d: -(d['link'].real_percent or d['link'].deal_percent or 0))
        return render(request, 'recipes/list.html', {
            'recipes': recipes, 'deals': deals[:8], 'tags': readable(Tag, request.user),
            'meal_types': Recipe.MealType.choices, 'page': 'recipes',
            'today_meals': meal_planning.today_meals(request.user), 'slot_icons': meal_planning.SLOT_ICONS,
        })


class RecipeDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        recipe = get_object_or_404(readable(Recipe, request.user).prefetch_related('tags'), pk=pk)
        ris = list(
            recipe.recipeingredient_set.select_related('ingredient', 'unit')
            .prefetch_related('ingredient__seasonal_availability', 'ingredient__shopping_links',
                                  'ingredient__unit_prices__unit')
            .order_by('-is_main', 'ingredient__name')
        )
        all_links = [l for ri in ris for l in ri.ingredient.shopping_links.all()]
        reachable = shopping.refresh(all_links) if all_links else True
        month = current_month()
        priceable = set(writable(Ingredient, request.user).filter(pk__in=[ri.ingredient_id for ri in ris])
                        .values_list('pk', flat=True))
        rows, prices = [], []
        for ri in ris:
            link = shopping.pick_link(list(ri.ingredient.shopping_links.all()))
            cost = ingredient_cost(ri, link)
            rows.append({
                'ri': ri, 'status': ri.ingredient.season_map().get(month, 'unknown'),
                'link': link, 'promo': bool(link and shopping.promo_active(link)),
                'verdict': shopping.verdict(link) if link else '',
                'deal': shopping.deal_text(link) if link else '',
                'cost': cost['cost'], 'source': cost['source'], 'manual': cost['manual'],
            })
            # what the price dialog needs for the rows Shopping can't price (and the ones priced by hand)
            if cost['source'] != 'shopping' and ri.ingredient_id in priceable:
                prices.append(price_dialog_row(ri, link, cost['manual']))
        costing = recipe_costing(ris)
        return render(request, 'recipes/detail.html', {
            'recipe': recipe, 'rows': rows, 'costing': costing,
            'phases': kitchen.grouped_steps(recipe), 'kitchenware': kitchen.needed_kitchenware(recipe),
            'reachable': reachable, 'shopping_on': shopping.configured(),
            'mine': is_owner(recipe, request.user),
            'can_edit': writable(Recipe, request.user).filter(pk=recipe.pk).exists(),
            'page': 'recipes',
            'recipe_boot': {'id': recipe.pk, 'prices': prices, 'priceUrl': reverse('unit-price-save'), 'cookUrl': reverse('recipe-cook', args=[recipe.pk]),
                            'units': units_json()},
            'calendar': meal_planning.recipe_calendar(request.user, recipe),
            'meal_boot': {
                'recipes': [{'id': recipe.pk, 'name': recipe.name, 'meal': recipe.meal_type, 'prep': recipe.prep_time,
                             'cook': recipe.cook_time, 'inSeason': False, 'promos': 0, 'tags': [], 'main': [], 'ing': [],
                             'cost': float(costing['cost']) if costing['cost'] is not None else None}],
                'slots': meal_views._slots(), 'urls': meal_views._urls(), 'today': timezone.localdate().isoformat(),
                'slot': meal_planning.slot_for(recipe), 'meals': [], 'canEdit': True,
            },
        })


def units_json():
    return [{'id': u.pk, 'name': u.name, 'abbr': u.abbreviation, 'dimension': u.dimension,
             'factor': float(u.factor) if u.factor else None} for u in Unit.objects.all()]


def price_dialog_row(ri, link, manual):
    """One recipe ingredient for the "price by hand" dialog: its amount, the price already entered, and a starting
    point from its linked product (€5 for a pack of 5 pieces)."""
    hint = None
    if link and link.price is not None:
        count = link.pack_amount if link.pack_dimension == 'count' and link.pack_amount else None
        hint = {'paid': float(link.price), 'for': float(count) if count else None, 'name': link.name,
                'size': link.package_size}
    return {
        'ingredient': ri.ingredient_id, 'name': ri.ingredient.name, 'amount': float(ri.quantity),
        'unit': ri.unit_id, 'abbr': ri.unit.abbreviation,
        'manual': unit_price_json(manual) if manual else None, 'hint': hint,
    }


def unit_price_json(p):
    return {'id': p.pk, 'unit': p.unit_id, 'abbr': p.unit.abbreviation, 'price': float(p.price),
            'paid': float(p.paid), 'for': float(p.for_amount), 'updated': timezone.localtime(p.updated_at).date().isoformat()}


class RecipeCookView(LoginRequiredMixin, View):
    """The cooking guide: the recipe's steps one at a time (static/nyochi/cook.js)."""

    def get(self, request, pk):
        recipe = get_object_or_404(readable(Recipe, request.user), pk=pk)
        ris = recipe.recipeingredient_set.select_related('ingredient', 'unit').order_by('-is_main', 'ingredient__name')
        ware = {k['key']: k for k in kitchen.needed_kitchenware(recipe)}
        steps = [{
            'phase': s['phase'], 'phase_label': kitchen.PHASE_LABELS[s['phase']], 'text': s['text'],
            'minutes': s.get('minutes'), 'appliance': ware.get(s.get('appliance') or ''),
        } for s in recipe.steps or []]
        meal = _cooking_meal(request, recipe)
        return render(request, 'recipes/cook.html', {
            'recipe': recipe, 'page': 'recipes', 'boot': {
                'id': recipe.pk, 'name': recipe.name, 'steps': steps, 'url': reverse('recipe-detail', args=[recipe.pk]),
                'ingredients': [{'name': ri.ingredient.name, 'amount': float(ri.quantity) if ri.quantity else None,
                                 'unit': ri.unit.abbreviation if ri.unit else '', 'main': ri.is_main} for ri in ris],
                'tools': recipe.tools or [], 'kitchenware': list(ware.values()),
                'meal': meal, 'portions': _portions(request, meal),
            },
        })


def _portions(request, meal):
    """How many portions are cooked (a recipe is for one): ?portions= (from the recipe page), else the calendar meal's."""
    try:
        n = float(request.GET.get('portions', ''))
        if 0 < n <= 20:
            return n
    except ValueError:
        pass
    return meal['mult'] if meal else 1


def _cooking_meal(request, recipe):
    """The calendar meal this cooking session is for: ?meal=<id>, else today's uncooked meal with this recipe."""
    from meals.models import Meal

    if not can_edit(request.user, Meal):
        return None
    qs = writable(Meal, request.user).filter(recipe=recipe, leftover_of__isnull=True)
    meal = qs.filter(pk=request.GET['meal']).first() if request.GET.get('meal', '').isdigit() else None
    if meal is None:
        meal = qs.filter(day=timezone.localdate(), cooked_at__isnull=True).order_by('position').first()
    if meal is None:
        return None
    return {'id': meal.pk, 'cooked': meal.cooked_at is not None, 'mult': float(meal.mult), 'url': reverse('meal-action', args=[meal.pk, 'cooked']),
            'label': f"{meal.day.strftime('%a %-d %b')}, {meal.get_slot_display().lower()}"}


class RecipeFormView(LoginRequiredMixin, View):
    template_name = 'recipes/form.html'

    def _recipe(self, request, pk):
        if not pk and not can_edit(request.user, Recipe):
            raise Http404('Your community does not let you add recipes.')
        return get_object_or_404(writable(Recipe, request.user), pk=pk) if pk else None

    def _render(self, request, recipe, form, formset):
        return render(request, self.template_name, {
            'form': form, 'formset': formset, 'recipe': recipe, 'page': 'recipes',
            'title': f'Edit {recipe.name}' if recipe else 'New recipe',
            'units': Unit.objects.all(),
            'kitchen': {
                'phases': [{'key': k, 'label': label, 'help': help} for k, label, help in kitchen.PHASES],
                'kitchenware': [{'key': k} | v for k, v in kitchen.KITCHENWARE.items()],
                'tools': kitchen.TOOL_SUGGESTIONS,
            },
        })

    def get(self, request, pk=None):
        recipe = self._recipe(request, pk)
        return self._render(
            request, recipe, RecipeForm(instance=recipe, user=request.user),
            RecipeIngredientFormSet(instance=recipe, prefix='ing', form_kwargs={'user': request.user}),
        )

    def post(self, request, pk=None):
        recipe = self._recipe(request, pk)
        form = RecipeForm(request.POST, instance=recipe, user=request.user)
        formset = RecipeIngredientFormSet(
            request.POST, instance=recipe, prefix='ing', form_kwargs={'user': request.user})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                saved = form.save(commit=False)
                if recipe is None:
                    saved.owner = request.user
                saved.save()
                form.save_tags(saved)
                formset.instance = saved
                for obj in formset.save(commit=False):
                    obj.owner_id = saved.owner_id
                    obj.save()
                for obj in formset.deleted_objects:
                    obj.delete()
            messages.success(request, f'Saved “{saved.name}”.')
            if recipe is None and request.POST.get('then') == 'new':
                return redirect('recipe-create')
            return redirect('recipe-detail', pk=saved.pk)
        messages.error(request, 'The recipe was not saved: fix the highlighted fields.')
        return self._render(request, recipe, form, formset)


class RecipeDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        recipe = get_object_or_404(deletable(Recipe, request.user), pk=pk)
        name = recipe.name
        recipe.delete()
        messages.success(request, f'Deleted “{name}”.')
        return redirect('recipe-list')


