from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)
from django.urls import reverse_lazy

from .forms import (
    GrocerySelectForm, IngredientForm, RecipeForm,
    RecipeIngredientFormSet, RecipeSelectorForm,
    SeasonalAvailabilityFormSet, ShopLinkFormSet, TagForm,
)
from .models import (
    Ingredient, IngredientCategory, Recipe, RecipeIngredient,
    SeasonalAvailability, Tag, Unit,
)

MONTHS = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]


# ── Recipes ──────────────────────────────────────────────────────────────────

class RecipeListView(ListView):
    model = Recipe
    template_name = 'recipes/list.html'
    context_object_name = 'recipes'

    def get_queryset(self):
        return Recipe.objects.prefetch_related('tags', 'recipeingredient_set__ingredient')


class RecipeDetailView(DetailView):
    model = Recipe
    template_name = 'recipes/detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['recipe_ingredients'] = (
            self.object.recipeingredient_set
            .select_related('ingredient', 'unit')
            .order_by('-is_main', 'ingredient__name')
        )
        return ctx


class RecipeCreateView(View):
    template_name = 'recipes/form.html'

    def get(self, request):
        return render(request, self.template_name, {
            'form': RecipeForm(),
            'ingredient_formset': RecipeIngredientFormSet(),
            'title': 'New recipe',
        })

    def post(self, request):
        form = RecipeForm(request.POST)
        formset = RecipeIngredientFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            recipe = form.save()
            formset.instance = recipe
            formset.save()
            return redirect('recipe-detail', pk=recipe.pk)
        return render(request, self.template_name, {
            'form': form,
            'ingredient_formset': formset,
            'title': 'New recipe',
        })


class RecipeUpdateView(View):
    template_name = 'recipes/form.html'

    def _get_recipe(self, pk):
        return get_object_or_404(Recipe, pk=pk)

    def get(self, request, pk):
        recipe = self._get_recipe(pk)
        return render(request, self.template_name, {
            'form': RecipeForm(instance=recipe),
            'ingredient_formset': RecipeIngredientFormSet(instance=recipe),
            'title': f'Edit — {recipe.name}',
            'recipe': recipe,
        })

    def post(self, request, pk):
        recipe = self._get_recipe(pk)
        form = RecipeForm(request.POST, instance=recipe)
        formset = RecipeIngredientFormSet(request.POST, instance=recipe)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('recipe-detail', pk=recipe.pk)
        return render(request, self.template_name, {
            'form': form,
            'ingredient_formset': formset,
            'title': f'Edit — {recipe.name}',
            'recipe': recipe,
        })


class RecipeDeleteView(DeleteView):
    model = Recipe
    template_name = 'recipes/confirm_delete.html'
    success_url = reverse_lazy('recipe-list')


# ── Ingredients ───────────────────────────────────────────────────────────────

class IngredientListView(ListView):
    model = Ingredient
    template_name = 'ingredients/list.html'
    context_object_name = 'ingredients'

    def get_queryset(self):
        return Ingredient.objects.order_by('category', 'name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = IngredientCategory.choices
        return ctx


class IngredientDetailView(DetailView):
    model = Ingredient
    template_name = 'ingredients/detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['seasons'] = {
            sa.month: sa
            for sa in self.object.seasonal_availability.all()
        }
        ctx['months'] = MONTHS
        ctx['shop_links'] = self.object.shop_links.all()
        return ctx


class IngredientCreateView(View):
    template_name = 'ingredients/form.html'

    def _make_season_initial(self):
        return [{'month': m, 'status': 'out'} for m, _ in MONTHS]

    def get(self, request):
        ingredient = Ingredient()
        return render(request, self.template_name, {
            'form': IngredientForm(),
            'season_formset': SeasonalAvailabilityFormSet(
                instance=ingredient,
                initial=self._make_season_initial(),
            ),
            'shop_formset': ShopLinkFormSet(instance=ingredient),
            'months': MONTHS,
            'title': 'New ingredient',
        })

    def post(self, request):
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save()
            season_formset = SeasonalAvailabilityFormSet(request.POST, instance=ingredient)
            shop_formset = ShopLinkFormSet(request.POST, instance=ingredient)
            if season_formset.is_valid() and shop_formset.is_valid():
                season_formset.save()
                shop_formset.save()
                return redirect('ingredient-detail', pk=ingredient.pk)
            ingredient.delete()
        else:
            season_formset = SeasonalAvailabilityFormSet(
                request.POST,
                initial=self._make_season_initial(),
            )
            shop_formset = ShopLinkFormSet(request.POST)
        return render(request, self.template_name, {
            'form': form,
            'season_formset': season_formset,
            'shop_formset': shop_formset,
            'months': MONTHS,
            'title': 'New ingredient',
        })


class IngredientUpdateView(View):
    template_name = 'ingredients/form.html'

    def _get_ingredient(self, pk):
        return get_object_or_404(Ingredient, pk=pk)

    def _ensure_all_months(self, ingredient):
        existing = set(ingredient.seasonal_availability.values_list('month', flat=True))
        to_create = [
            SeasonalAvailability(ingredient=ingredient, month=m, status='out')
            for m, _ in MONTHS if m not in existing
        ]
        if to_create:
            SeasonalAvailability.objects.bulk_create(to_create)

    def get(self, request, pk):
        ingredient = self._get_ingredient(pk)
        self._ensure_all_months(ingredient)
        return render(request, self.template_name, {
            'form': IngredientForm(instance=ingredient),
            'season_formset': SeasonalAvailabilityFormSet(instance=ingredient),
            'shop_formset': ShopLinkFormSet(instance=ingredient),
            'months': MONTHS,
            'title': f'Edit — {ingredient.name}',
            'ingredient': ingredient,
        })

    def post(self, request, pk):
        ingredient = self._get_ingredient(pk)
        self._ensure_all_months(ingredient)
        form = IngredientForm(request.POST, instance=ingredient)
        season_formset = SeasonalAvailabilityFormSet(request.POST, instance=ingredient)
        shop_formset = ShopLinkFormSet(request.POST, instance=ingredient)
        if form.is_valid() and season_formset.is_valid() and shop_formset.is_valid():
            form.save()
            season_formset.save()
            shop_formset.save()
            return redirect('ingredient-detail', pk=ingredient.pk)
        return render(request, self.template_name, {
            'form': form,
            'season_formset': season_formset,
            'shop_formset': shop_formset,
            'months': MONTHS,
            'title': f'Edit — {ingredient.name}',
            'ingredient': ingredient,
        })


class IngredientDeleteView(DeleteView):
    model = Ingredient
    template_name = 'ingredients/confirm_delete.html'
    success_url = reverse_lazy('ingredient-list')


# ── Tags ─────────────────────────────────────────────────────────────────────

class TagListView(View):
    template_name = 'recipes/tags.html'

    def get(self, request):
        return render(request, self.template_name, {
            'tags': Tag.objects.all(),
            'form': TagForm(),
        })

    def post(self, request):
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tag-list')
        return render(request, self.template_name, {
            'tags': Tag.objects.all(),
            'form': form,
        })


class TagDeleteView(View):
    def post(self, request, pk):
        Tag.objects.filter(pk=pk).delete()
        return redirect('tag-list')


# ── Grocery list ──────────────────────────────────────────────────────────────

class GroceryListView(View):
    template_name = 'recipes/grocery_list.html'

    def get(self, request):
        return render(request, self.template_name, {'form': GrocerySelectForm()})

    def post(self, request):
        form = GrocerySelectForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        selected_recipes = form.cleaned_data['recipes']

        rows = (
            RecipeIngredient.objects
            .filter(recipe__in=selected_recipes)
            .values('ingredient', 'unit')
            .annotate(total=Sum('quantity'))
            .order_by('ingredient__category', 'ingredient__name')
        )

        # Enrich with full objects grouped by category
        from .models import Unit as UnitModel
        ingredient_ids = [r['ingredient'] for r in rows]
        unit_ids = [r['unit'] for r in rows]
        ingredients_map = {i.pk: i for i in Ingredient.objects.filter(pk__in=ingredient_ids)}
        units_map = {u.pk: u for u in UnitModel.objects.filter(pk__in=unit_ids)}

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

        return render(request, self.template_name, {
            'form': form,
            'grouped': grouped,
            'selected_recipes': selected_recipes,
        })


# ── Recipe selector ───────────────────────────────────────────────────────────

class RecipeSelectorView(View):
    template_name = 'recipes/selector.html'

    def get(self, request):
        return render(request, self.template_name, {'form': RecipeSelectorForm()})

    def post(self, request):
        form = RecipeSelectorForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        cd = form.cleaned_data
        qs = Recipe.objects.prefetch_related('tags', 'ingredients')

        # Hard filters
        if cd.get('exclude_ingredients'):
            qs = qs.exclude(ingredients__in=cd['exclude_ingredients'])
        if cd.get('max_prep_time') is not None:
            qs = qs.filter(prep_time__lte=cd['max_prep_time'])
        if cd.get('max_cook_time') is not None:
            qs = qs.filter(cook_time__lte=cd['max_cook_time'])

        # Score each recipe by how many soft criteria it matches
        scored = []
        for recipe in qs:
            score = 0
            recipe_ingredient_ids = set(recipe.ingredients.values_list('pk', flat=True))
            recipe_tag_ids = set(recipe.tags.values_list('pk', flat=True))

            if cd.get('include_ingredients'):
                wanted = set(cd['include_ingredients'].values_list('pk', flat=True))
                score += len(wanted & recipe_ingredient_ids)

            if cd.get('tags'):
                wanted_tags = set(cd['tags'].values_list('pk', flat=True))
                score += len(wanted_tags & recipe_tag_ids)

            scored.append((score, recipe))

        scored.sort(key=lambda x: (-x[0], x[1].name))
        results = [{'recipe': r, 'score': s} for s, r in scored]

        return render(request, self.template_name, {
            'form': form,
            'results': results,
        })
