from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from . import shopping
from .access import deletable, is_owner, readable, writable
from .costing import recipe_costing
from .forms import RecipeForm, RecipeIngredientFormSet
from .http import ApiError, api, body
from .models import (
    Ingredient, Recipe, RecipeIngredient, SavedGroceryList, Shop, ShoppingLink, Tag, Unit,
)
from .seasons import current_month


def _recipes_with_everything(user):
    return readable(Recipe, user).prefetch_related(
        'tags',
        Prefetch('recipeingredient_set', queryset=RecipeIngredient.objects.select_related('ingredient', 'unit')
                 .prefetch_related('ingredient__seasonal_availability', 'ingredient__shopping_links')),
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
        })


class RecipeDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        recipe = get_object_or_404(readable(Recipe, request.user).prefetch_related('tags'), pk=pk)
        ris = list(
            recipe.recipeingredient_set.select_related('ingredient', 'unit')
            .prefetch_related('ingredient__seasonal_availability', 'ingredient__shopping_links')
            .order_by('-is_main', 'ingredient__name')
        )
        all_links = [l for ri in ris for l in ri.ingredient.shopping_links.all()]
        reachable = shopping.refresh(all_links) if all_links else True
        month = current_month()
        rows = []
        for ri in ris:
            link = shopping.pick_link(list(ri.ingredient.shopping_links.all()))
            rows.append({
                'ri': ri, 'status': ri.ingredient.season_map().get(month, 'unknown'),
                'link': link, 'promo': bool(link and shopping.promo_active(link)),
                'verdict': shopping.verdict(link) if link else '',
                'deal': shopping.deal_text(link) if link else '',
                'cost': shopping.cost_for_amount(ri.quantity, ri.unit, link) if link else None,
            })
        return render(request, 'recipes/detail.html', {
            'recipe': recipe, 'rows': rows, 'costing': recipe_costing(ris),
            'reachable': reachable, 'shopping_on': shopping.configured(),
            'mine': is_owner(recipe, request.user),
            'can_edit': writable(Recipe, request.user).filter(pk=recipe.pk).exists(),
            'page': 'recipes',
        })


class RecipeFormView(LoginRequiredMixin, View):
    template_name = 'recipes/form.html'

    def _recipe(self, request, pk):
        return get_object_or_404(writable(Recipe, request.user), pk=pk) if pk else None

    def _render(self, request, recipe, form, formset):
        return render(request, self.template_name, {
            'form': form, 'formset': formset, 'recipe': recipe, 'page': 'recipes',
            'title': f'Edit {recipe.name}' if recipe else 'New recipe',
            'units': Unit.objects.all(),
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


# ------------------------------------------------------------------ sharing (a dialog on every page)

SHAREABLE = {'recipe': Recipe, 'ingredient': Ingredient, 'shop': Shop, 'grocerylist': SavedGroceryList}


def _shared_users(obj):
    """Two queries instead of a join: the M2M table is in this database, auth_user is in the accounts database shared with Shopping."""
    through = obj.shared_with.through
    ids = list(through.objects.filter(**{f'{obj._meta.model_name}_id': obj.pk}).values_list('user_id', flat=True))
    if not ids:
        return []
    users = get_user_model().objects.using('accounts').filter(pk__in=ids).order_by('username')
    return [{'id': u.pk, 'username': u.username} for u in users]


@api
def share(request, model_type, pk):
    model = SHAREABLE.get(model_type)
    if model is None:
        raise ApiError('Unknown kind of object.', 404)
    obj = deletable(model, request.user).filter(pk=pk).first()
    if obj is None:
        raise ApiError('Only the owner can share this.', 404)
    if request.method == 'POST':
        data = body(request)
        User = get_user_model()
        if data.get('add_username'):
            username = str(data['add_username']).strip()
            user = User.objects.using('accounts').filter(username__iexact=username).first()
            if user is None:
                raise ApiError(f'There is no user "{username}".', 404)
            if user.pk == request.user.pk:
                raise ApiError("That's you: you already have access.")
            obj.shared_with.add(user)
        elif data.get('remove_user_id') is not None:
            try:
                obj.shared_with.remove(int(data['remove_user_id']))
            except (TypeError, ValueError):
                raise ApiError('Invalid user.')
    return JsonResponse({'name': str(obj), 'users': _shared_users(obj)})
