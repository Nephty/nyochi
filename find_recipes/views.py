from django.shortcuts import render
from django.views import View

from recipes.models import Recipe, ShopLocation
from recipes.utils import _compute_grocery_list, _LOCATION_QS
from .forms import RecipeSelectorForm

_MEAL_EMOJI = {
    'breakfast': '🌅',
    'full_meal': '🍽️',
    'snack': '🍎',
    'desert': '🍰',
}


class RecipeSelectorView(View):
    template_name = 'find_recipes/selector.html'

    def get(self, request):
        empty_cd = {'include_ingredients': None, 'exclude_ingredients': None,
                    'tags': None, 'max_prep_time': None, 'max_cook_time': None}
        sections = [
            {'value': v, 'label': l, 'emoji': _MEAL_EMOJI[v],
             'form': RecipeSelectorForm(prefix=v), 'results': self._filter(empty_cd, v)}
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
        if selected_pks:
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
        if selected_pks:
            selected_recipes = list(Recipe.objects.filter(pk__in=selected_pks))
            grocery_grouped, aisle_label = _compute_grocery_list(selected_recipes, location)
        return render(request, 'partials/selector_grocery.html', {
            'grocery_grouped': grocery_grouped,
            'aisle_label': aisle_label,
            'location': location,
            'selected_pks': set(selected_pks),
            'selected_recipes': selected_recipes,
        })
