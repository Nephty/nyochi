from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from recipes.models import Ingredient, IngredientCategory, SeasonalAvailability
from recipes.utils import accessible_qs, MONTHS
from .forms import IngredientForm, SeasonalAvailabilityCreateFormSet, SeasonalAvailabilityFormSet, ShopLinkFormSet


class IngredientListView(LoginRequiredMixin, ListView):
    model = Ingredient
    template_name = 'ingredients/list.html'
    context_object_name = 'ingredients'

    def get_queryset(self):
        return accessible_qs(Ingredient, self.request.user).order_by('category', 'name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = IngredientCategory.choices
        return ctx


class IngredientDetailView(LoginRequiredMixin, DetailView):
    model = Ingredient
    template_name = 'ingredients/detail.html'

    def get_queryset(self):
        return accessible_qs(Ingredient, self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['seasons'] = {
            sa.month: sa
            for sa in self.object.seasonal_availability.all()
        }
        ctx['months'] = MONTHS
        ctx['shop_links'] = self.object.shop_links.all()
        return ctx


class IngredientCreateView(LoginRequiredMixin, View):
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
            'shop_formset': ShopLinkFormSet(
                instance=ingredient, form_kwargs={'user': request.user}
            ),
            'months': MONTHS,
            'title': 'New ingredient',
        })

    def post(self, request):
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save(commit=False)
            ingredient.owner = request.user
            ingredient.save()
            season_formset = SeasonalAvailabilityFormSet(request.POST, instance=ingredient)
            shop_formset = ShopLinkFormSet(
                request.POST, instance=ingredient, form_kwargs={'user': request.user}
            )
            if season_formset.is_valid() and shop_formset.is_valid():
                season_formset.save()
                shop_formset.save()
                for obj in shop_formset.new_objects:
                    obj.owner = request.user
                    obj.save(update_fields=['owner'])
                return redirect('ingredient-detail', pk=ingredient.pk)
            ingredient.delete()
        else:
            season_formset = SeasonalAvailabilityFormSet(
                request.POST,
                initial=self._make_season_initial(),
            )
            shop_formset = ShopLinkFormSet(request.POST, form_kwargs={'user': request.user})
        return render(request, self.template_name, {
            'form': form,
            'season_formset': season_formset,
            'shop_formset': shop_formset,
            'months': MONTHS,
            'title': 'New ingredient',
        })


class IngredientUpdateView(LoginRequiredMixin, View):
    template_name = 'ingredients/form.html'

    def _get_ingredient(self, request, pk):
        return get_object_or_404(accessible_qs(Ingredient, request.user), pk=pk)

    def _ensure_all_months(self, ingredient):
        existing = set(ingredient.seasonal_availability.values_list('month', flat=True))
        to_create = [
            SeasonalAvailability(ingredient=ingredient, month=m, status='out')
            for m, _ in MONTHS if m not in existing
        ]
        if to_create:
            SeasonalAvailability.objects.bulk_create(to_create)

    def get(self, request, pk):
        ingredient = self._get_ingredient(request, pk)
        self._ensure_all_months(ingredient)
        return render(request, self.template_name, {
            'form': IngredientForm(instance=ingredient),
            'season_formset': SeasonalAvailabilityFormSet(instance=ingredient),
            'shop_formset': ShopLinkFormSet(
                instance=ingredient, form_kwargs={'user': request.user}
            ),
            'months': MONTHS,
            'title': f'Edit — {ingredient.name}',
            'ingredient': ingredient,
        })

    def post(self, request, pk):
        ingredient = self._get_ingredient(request, pk)
        self._ensure_all_months(ingredient)
        form = IngredientForm(request.POST, instance=ingredient)
        season_formset = SeasonalAvailabilityFormSet(request.POST, instance=ingredient)
        shop_formset = ShopLinkFormSet(
            request.POST, instance=ingredient, form_kwargs={'user': request.user}
        )
        if form.is_valid() and season_formset.is_valid() and shop_formset.is_valid():
            form.save()
            season_formset.save()
            shop_formset.save()
            for obj in shop_formset.new_objects:
                obj.owner = request.user
                obj.save(update_fields=['owner'])
            return redirect('ingredient-detail', pk=ingredient.pk)
        return render(request, self.template_name, {
            'form': form,
            'season_formset': season_formset,
            'shop_formset': shop_formset,
            'months': MONTHS,
            'title': f'Edit — {ingredient.name}',
            'ingredient': ingredient,
        })


class IngredientDeleteView(LoginRequiredMixin, DeleteView):
    model = Ingredient
    template_name = 'ingredients/confirm_delete.html'
    success_url = reverse_lazy('ingredient-list')

    def get_queryset(self):
        return accessible_qs(Ingredient, self.request.user)
