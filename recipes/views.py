from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from .forms import RecipeForm, RecipeIngredientForm, RecipeIngredientFormSet
from .models import Ingredient, Recipe, RecipeIngredient, SavedGroceryList, Shop
from .utils import accessible_qs


class RecipeListView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = 'recipes/list.html'
    context_object_name = 'recipes'

    def get_queryset(self):
        return (
            accessible_qs(Recipe, self.request.user)
            .prefetch_related('tags', 'recipeingredient_set__ingredient')
        )


class RecipeDetailView(LoginRequiredMixin, DetailView):
    model = Recipe
    template_name = 'recipes/detail.html'

    def get_queryset(self):
        return accessible_qs(Recipe, self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['recipe_ingredients'] = (
            self.object.recipeingredient_set
            .select_related('ingredient', 'unit')
            .order_by('-is_main', 'ingredient__name')
        )
        return ctx


class RecipeCreateView(LoginRequiredMixin, View):
    template_name = 'recipes/form.html'

    def get(self, request):
        return render(request, self.template_name, {
            'form': RecipeForm(),
            'ingredient_formset': RecipeIngredientFormSet(
                prefix='form', form_kwargs={'user': request.user}
            ),
            'title': 'New recipe',
        })

    def post(self, request):
        form = RecipeForm(request.POST)
        formset = RecipeIngredientFormSet(
            request.POST, prefix='form', form_kwargs={'user': request.user}
        )
        if form.is_valid() and formset.is_valid():
            recipe = form.save(commit=False)
            recipe.owner = request.user
            recipe.save()
            form.save_m2m()
            formset.instance = recipe
            formset.save()
            for obj in formset.new_objects:
                obj.owner = request.user
                obj.save(update_fields=['owner'])
            return redirect('recipe-detail', pk=recipe.pk)
        return render(request, self.template_name, {
            'form': form,
            'ingredient_formset': formset,
            'title': 'New recipe',
        })


class RecipeUpdateView(LoginRequiredMixin, View):
    template_name = 'recipes/form.html'

    def _get_recipe(self, request, pk):
        return get_object_or_404(accessible_qs(Recipe, request.user), pk=pk)

    def get(self, request, pk):
        recipe = self._get_recipe(request, pk)
        return render(request, self.template_name, {
            'form': RecipeForm(instance=recipe),
            'ingredient_formset': RecipeIngredientFormSet(
                instance=recipe, prefix='form', form_kwargs={'user': request.user}
            ),
            'title': f'Edit — {recipe.name}',
            'recipe': recipe,
        })

    def post(self, request, pk):
        recipe = self._get_recipe(request, pk)
        form = RecipeForm(request.POST, instance=recipe)
        formset = RecipeIngredientFormSet(
            request.POST, instance=recipe, prefix='form', form_kwargs={'user': request.user}
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            for obj in formset.new_objects:
                obj.owner = request.user
                obj.save(update_fields=['owner'])
            return redirect('recipe-detail', pk=recipe.pk)
        return render(request, self.template_name, {
            'form': form,
            'ingredient_formset': formset,
            'title': f'Edit — {recipe.name}',
            'recipe': recipe,
        })


class RecipeDeleteView(LoginRequiredMixin, DeleteView):
    model = Recipe
    template_name = 'recipes/confirm_delete.html'
    success_url = reverse_lazy('recipe-list')

    def get_queryset(self):
        return accessible_qs(Recipe, self.request.user)


class ShareView(LoginRequiredMixin, View):
    _model_map = {
        'recipe': Recipe,
        'ingredient': Ingredient,
        'shop': Shop,
        'grocerylist': SavedGroceryList,
    }

    def _get_obj(self, request, model_type, pk):
        model = self._model_map.get(model_type)
        if not model:
            raise Http404
        return get_object_or_404(model, pk=pk, owner=request.user)

    def post(self, request, model_type, pk):
        obj = self._get_obj(request, model_type, pk)
        User = get_user_model()
        error = None

        if 'add_username' in request.POST:
            username = request.POST.get('add_username', '').strip()
            try:
                user = User.objects.get(username=username)
                if user == request.user:
                    error = "You can't share with yourself."
                elif obj.shared_with.filter(pk=user.pk).exists():
                    error = f'"{username}" already has access.'
                else:
                    obj.shared_with.add(user)
            except User.DoesNotExist:
                error = f'User "{username}" not found.'
        elif 'remove_user_pk' in request.POST:
            obj.shared_with.remove(request.POST.get('remove_user_pk'))

        return render(request, 'partials/share_panel.html', {
            'obj': obj,
            'model_type': model_type,
            'error': error,
        })


class IngredientRowView(LoginRequiredMixin, View):
    def get(self, request):
        total = request.GET.get('form-TOTAL_FORMS') or request.GET.get('idx', '0')
        idx = int(total)
        form = RecipeIngredientForm(prefix=f'form-{idx}', user=request.user)
        return render(request, 'partials/ingredient_row.html', {'ing_form': form, 'idx': idx})
