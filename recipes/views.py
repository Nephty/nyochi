from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from .forms import RecipeForm, RecipeIngredientForm, RecipeIngredientFormSet
from .models import Recipe, RecipeIngredient


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


class IngredientRowView(View):
    def get(self, request):
        total = request.GET.get('form-TOTAL_FORMS') or request.GET.get('idx', '0')
        idx = int(total)
        form = RecipeIngredientForm(prefix=f'form-{idx}')
        return render(request, 'partials/ingredient_row.html', {'ing_form': form, 'idx': idx})
