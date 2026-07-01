from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)
from django.urls import reverse_lazy

from .forms import (
    AisleForm, GrocerySelectForm, IngredientForm, RecipeForm,
    RecipeIngredientForm, RecipeIngredientFormSet, RecipeSelectorForm,
    SeasonalAvailabilityCreateFormSet, SeasonalAvailabilityFormSet,
    ShopForm, ShopLinkFormSet, ShopLocationForm, TagForm,
)
from .models import (
    Aisle, AisleOrder, CategoryAisleMapping,
    Ingredient, IngredientCategory, Recipe, RecipeIngredient,
    SeasonalAvailability, Shop, ShopLocation, Tag, Unit,
)

MONTHS = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]


def is_htmx(request):
    return request.headers.get('HX-Request') == 'true'


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
            'season_formset': SeasonalAvailabilityCreateFormSet(
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


# ── Shops ────────────────────────────────────────────────────────────────────

class ShopListView(View):
    template_name = 'shops/list.html'

    def get(self, request):
        return render(request, self.template_name, {
            'shops': Shop.objects.prefetch_related('aisles', 'locations'),
            'form': ShopForm(),
        })

    def post(self, request):
        form = ShopForm(request.POST)
        if form.is_valid():
            shop = form.save()
            if is_htmx(request):
                return render(request, 'partials/shop_card.html', {'shop': shop})
            return redirect('shop-list')
        return render(request, self.template_name, {
            'shops': Shop.objects.prefetch_related('aisles', 'locations'),
            'form': form,
        })


class ShopDeleteView(View):
    def post(self, request, pk):
        Shop.objects.filter(pk=pk).delete()
        if is_htmx(request):
            return HttpResponse('')
        return redirect('shop-list')


class ShopDetailView(View):
    template_name = 'shops/detail.html'

    def _build_loc_data(self, shop, aisles):
        loc_data = []
        for loc in shop.locations.prefetch_related('aisle_orders', 'category_mappings'):
            existing_orders = {ao.aisle_id: ao.order for ao in loc.aisle_orders.all()}
            existing_mappings = {m.category: m.aisle_id for m in loc.category_mappings.all()}
            loc_data.append({
                'location': loc,
                'aisle_rows': [
                    {'aisle': a, 'order': existing_orders.get(a.pk, '')}
                    for a in aisles
                ],
                'category_rows': [
                    {'value': v, 'label': l, 'aisle_id': existing_mappings.get(v)}
                    for v, l in IngredientCategory.choices
                ],
            })
        return loc_data

    def _ctx(self, shop, aisle_form=None, location_form=None):
        aisles = list(shop.aisles.all())
        return {
            'shop': shop,
            'aisles': aisles,
            'loc_data': self._build_loc_data(shop, aisles),
            'location_count': shop.locations.count(),
            'aisle_form': aisle_form or AisleForm(initial={'shop': shop.pk}),
            'location_form': location_form or ShopLocationForm(initial={'shop': shop.pk}),
        }

    def get(self, request, pk):
        shop = get_object_or_404(Shop, pk=pk)
        return render(request, self.template_name, self._ctx(shop))

    def post(self, request, pk):
        shop = get_object_or_404(Shop, pk=pk)
        action = request.POST.get('action')

        if action == 'add_aisle':
            data = request.POST.copy()
            data['shop'] = shop.pk
            form = AisleForm(data)
            if form.is_valid():
                aisle = form.save()
                if is_htmx(request):
                    return render(request, 'partials/aisle_item.html', {'aisle': aisle, 'shop': shop})
                return redirect('shop-detail', pk=shop.pk)
            return render(request, self.template_name, self._ctx(shop, aisle_form=form))

        elif action == 'add_location':
            data = request.POST.copy()
            data['shop'] = shop.pk
            form = ShopLocationForm(data)
            if form.is_valid():
                loc = form.save()
                if is_htmx(request):
                    aisles = list(shop.aisles.all())
                    item = {
                        'location': loc,
                        'aisle_rows': [{'aisle': a, 'order': ''} for a in aisles],
                        'category_rows': [
                            {'value': v, 'label': l, 'aisle_id': None}
                            for v, l in IngredientCategory.choices
                        ],
                    }
                    return render(request, 'partials/location_card.html', {
                        'item': item,
                        'aisles': aisles,
                        'location_count': shop.locations.count(),
                        'shop': shop,
                    })
                return redirect('shop-detail', pk=shop.pk)
            return render(request, self.template_name, self._ctx(shop, location_form=form))

        elif action in ('save_orders', 'save_mappings', 'copy_mappings'):
            location_pk = request.POST.get('location_pk')
            location = get_object_or_404(ShopLocation, pk=location_pk, shop=shop)

            if action == 'save_orders':
                for aisle in shop.aisles.all():
                    val = request.POST.get(f'order_{aisle.pk}', '').strip()
                    if val:
                        try:
                            AisleOrder.objects.update_or_create(
                                aisle=aisle, location=location,
                                defaults={'order': int(val)},
                            )
                        except (ValueError, TypeError):
                            pass
                    else:
                        AisleOrder.objects.filter(aisle=aisle, location=location).delete()
                if is_htmx(request):
                    return HttpResponse('Saved ✓')

            elif action == 'save_mappings':
                for cat_value, _ in IngredientCategory.choices:
                    aisle_pk_val = request.POST.get(f'aisle_{cat_value}', '').strip()
                    if aisle_pk_val:
                        try:
                            aisle = Aisle.objects.get(pk=aisle_pk_val, shop=shop)
                            CategoryAisleMapping.objects.update_or_create(
                                location=location, category=cat_value,
                                defaults={'aisle': aisle},
                            )
                        except (Aisle.DoesNotExist, ValueError):
                            pass
                    else:
                        CategoryAisleMapping.objects.filter(
                            location=location, category=cat_value
                        ).delete()
                if is_htmx(request):
                    return HttpResponse('Saved ✓')

            elif action == 'copy_mappings':
                mappings = list(location.category_mappings.all())
                for other in shop.locations.exclude(pk=location.pk):
                    for m in mappings:
                        CategoryAisleMapping.objects.update_or_create(
                            location=other, category=m.category,
                            defaults={'aisle': m.aisle},
                        )
                if is_htmx(request):
                    return HttpResponse('Copied ✓')

        return redirect('shop-detail', pk=shop.pk)


class AisleDeleteView(View):
    def post(self, request, pk):
        aisle = get_object_or_404(Aisle, pk=pk)
        shop_pk = aisle.shop_id
        aisle.delete()
        if is_htmx(request):
            return HttpResponse('')
        return redirect('shop-detail', pk=shop_pk)


class ShopLocationDeleteView(View):
    def post(self, request, pk):
        location = get_object_or_404(ShopLocation, pk=pk)
        shop_pk = location.shop_id
        location.delete()
        if is_htmx(request):
            return HttpResponse('')
        return redirect('shop-detail', pk=shop_pk)


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
            tag = form.save()
            if is_htmx(request):
                return render(request, 'partials/tag_row.html', {'tag': tag})
            return redirect('tag-list')
        return render(request, self.template_name, {
            'tags': Tag.objects.all(),
            'form': form,
        })


class TagDeleteView(View):
    def post(self, request, pk):
        Tag.objects.filter(pk=pk).delete()
        if is_htmx(request):
            return HttpResponse('')
        return redirect('tag-list')


# ── Grocery list ──────────────────────────────────────────────────────────────

def _compute_grocery_list(recipes, location):
    """Aggregate ingredients from recipes, optionally sorted by aisle order.

    Returns (grouped, aisle_label) where grouped maps category display name →
    list of {ingredient, total, unit} dicts, and aisle_label maps category
    display name → aisle name string.
    """
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


class GroceryListView(View):
    template_name = 'recipes/grocery_list.html'

    def get(self, request):
        return render(request, self.template_name, {'form': GrocerySelectForm()})

    def post(self, request):
        form = GrocerySelectForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        selected_recipes = form.cleaned_data['recipes']
        location = form.cleaned_data.get('shop_location')
        grouped, aisle_label = _compute_grocery_list(selected_recipes, location)

        return render(request, self.template_name, {
            'form': form,
            'grouped': grouped,
            'aisle_label': aisle_label,
            'selected_recipes': selected_recipes,
            'location': location,
        })


# ── Recipe selector ───────────────────────────────────────────────────────────

_MEAL_EMOJI = {
    'breakfast': '🌅',
    'full_meal': '🍽️',
    'snack': '🍎',
    'desert': '🍰',
}

_LOCATION_QS = lambda: ShopLocation.objects.select_related('shop').order_by('shop__name', 'name')


class RecipeSelectorView(View):
    template_name = 'recipes/selector.html'

    def get(self, request):
        sections = [
            {'value': v, 'label': l, 'emoji': _MEAL_EMOJI[v],
             'form': RecipeSelectorForm(prefix=v), 'results': None}
            for v, l in Recipe.MealType.choices
        ]
        return render(request, self.template_name, {
            'sections': sections,
            'location_choices': _LOCATION_QS(),
            'shop_location_id': '',
            'selected_pks': set(),
        })

    def post(self, request):
        sections = []
        for v, l in Recipe.MealType.choices:
            form = RecipeSelectorForm(request.POST, prefix=v)
            results = self._filter(form.cleaned_data, v) if form.is_valid() else []
            sections.append({'value': v, 'label': l, 'emoji': _MEAL_EMOJI[v],
                             'form': form, 'results': results})

        selected_pks = set(request.POST.getlist('selected_recipe_pks'))
        shop_location_id = request.POST.get('shop_location', '')
        location = ShopLocation.objects.filter(pk=shop_location_id).first() if shop_location_id else None

        grocery_grouped, aisle_label, selected_recipes = None, {}, []
        if selected_pks and location:
            selected_recipes = list(Recipe.objects.filter(pk__in=selected_pks))
            grocery_grouped, aisle_label = _compute_grocery_list(selected_recipes, location)

        return render(request, self.template_name, {
            'sections': sections,
            'location_choices': _LOCATION_QS(),
            'shop_location_id': shop_location_id,
            'selected_pks': selected_pks,
            'selected_recipes': selected_recipes,
            'grocery_grouped': grocery_grouped,
            'aisle_label': aisle_label,
            'location': location,
        })

    def _filter(self, cd, meal_type):
        qs = Recipe.objects.filter(meal_type=meal_type).prefetch_related('tags', 'ingredients')
        if cd.get('exclude_ingredients'):
            qs = qs.exclude(ingredients__in=cd['exclude_ingredients'])
        if cd.get('max_prep_time') is not None:
            qs = qs.filter(prep_time__lte=cd['max_prep_time'])
        if cd.get('max_cook_time') is not None:
            qs = qs.filter(cook_time__lte=cd['max_cook_time'])
        scored = []
        for recipe in qs:
            score = 0
            ri_ids = set(recipe.ingredients.values_list('pk', flat=True))
            tag_ids = set(recipe.tags.values_list('pk', flat=True))
            if cd.get('include_ingredients'):
                score += len(set(cd['include_ingredients'].values_list('pk', flat=True)) & ri_ids)
            if cd.get('tags'):
                score += len(set(cd['tags'].values_list('pk', flat=True)) & tag_ids)
            scored.append((score, recipe))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        return [{'recipe': r, 'score': s} for s, r in scored]


class SelectorSectionView(View):
    def post(self, request, meal_type):
        form = RecipeSelectorForm(request.POST, prefix=meal_type)
        results = RecipeSelectorView()._filter(form.cleaned_data, meal_type) if form.is_valid() else []
        selected_pks = set(request.POST.getlist('selected_recipe_pks'))
        return render(request, 'partials/selector_results.html', {
            'results': results,
            'selected_pks': selected_pks,
        })


class SelectorGroceryView(View):
    def post(self, request):
        selected_pks = request.POST.getlist('selected_recipe_pks')
        shop_location_id = request.POST.get('shop_location', '')
        location = ShopLocation.objects.filter(pk=shop_location_id).first() if shop_location_id else None
        grocery_grouped, aisle_label, selected_recipes = None, {}, []
        if selected_pks and location:
            selected_recipes = list(Recipe.objects.filter(pk__in=selected_pks))
            grocery_grouped, aisle_label = _compute_grocery_list(selected_recipes, location)
        return render(request, 'partials/selector_grocery.html', {
            'grocery_grouped': grocery_grouped,
            'aisle_label': aisle_label,
            'location': location,
            'selected_pks': set(selected_pks),
            'selected_recipes': selected_recipes,
        })


class GroceryResultsView(View):
    def post(self, request):
        form = GrocerySelectForm(request.POST)
        if not form.is_valid():
            return HttpResponse('')
        selected_recipes = form.cleaned_data['recipes']
        location = form.cleaned_data.get('shop_location')
        grouped, aisle_label = _compute_grocery_list(selected_recipes, location)
        return render(request, 'partials/grocery_results.html', {
            'grouped': grouped,
            'aisle_label': aisle_label,
            'selected_recipes': selected_recipes,
            'location': location,
        })


class IngredientRowView(View):
    def get(self, request):
        total = request.GET.get('form-TOTAL_FORMS') or request.GET.get('idx', '0')
        idx = int(total)
        form = RecipeIngredientForm(prefix=f'form-{idx}')
        return render(request, 'partials/ingredient_row.html', {'ing_form': form, 'idx': idx})
