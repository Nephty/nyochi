from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views import View

from recipes.models import SavedGroceryItem, SavedGroceryList, ShopLocation
from recipes.utils import (
    _compute_grocery_list, _LOCATION_QS, _save_grocery_list,
    _sorted_grocery_items, is_htmx,
)
from .forms import GrocerySelectForm

_SAVE_SUCCESS_HTML = (
    '<span class="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 py-1">'
    '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 12 12" fill="none"'
    ' stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M2 6l3 3 5-5"/></svg>List saved</span>'
)


class GroceryListView(View):
    template_name = 'grocery/grocery_list.html'

    def _saved_lists(self):
        return SavedGroceryList.objects.filter(archived=False).prefetch_related('recipes', 'items')

    def get(self, request):
        return render(request, self.template_name, {
            'form': GrocerySelectForm(),
            'saved_lists': self._saved_lists(),
        })

    def post(self, request):
        form = GrocerySelectForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'saved_lists': self._saved_lists(),
            })

        selected_recipes = form.cleaned_data['recipes']
        location = form.cleaned_data.get('shop_location')
        grouped, aisle_label = _compute_grocery_list(selected_recipes, location)

        return render(request, self.template_name, {
            'form': form,
            'grouped': grouped,
            'aisle_label': aisle_label,
            'selected_recipes': selected_recipes,
            'location': location,
            'saved_lists': self._saved_lists(),
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


class SaveGroceryListView(View):
    def post(self, request):
        pks = request.POST.getlist('recipe_pks') or request.POST.getlist('selected_recipe_pks')
        saved = _save_grocery_list(pks)
        if is_htmx(request):
            if not saved:
                return HttpResponse('<span class="text-xs text-red-500">No recipes selected.</span>')
            saved_lists = SavedGroceryList.objects.filter(archived=False).prefetch_related('recipes', 'items')
            oob = render_to_string(
                'partials/saved_lists_section.html',
                {'saved_lists': saved_lists},
                request=request,
            )
            return HttpResponse(
                _SAVE_SUCCESS_HTML +
                f'<div id="saved-lists-section" hx-swap-oob="true">{oob}</div>'
            )
        return redirect('saved-grocery-detail', pk=saved.pk) if saved else redirect('grocery-list')


class SavedGroceryListsView(View):
    template_name = 'saved_lists/list.html'

    def get(self, request):
        saved_lists = SavedGroceryList.objects.filter(archived=False).prefetch_related('recipes', 'items')
        return render(request, self.template_name, {'saved_lists': saved_lists})


class SavedGroceryDetailView(View):
    template_name = 'saved_lists/detail.html'

    def get(self, request, pk):
        saved = get_object_or_404(SavedGroceryList, pk=pk)
        location_id = request.GET.get('location', '')
        location = ShopLocation.objects.filter(pk=location_id).first() if location_id else None
        grouped, aisle_label = _sorted_grocery_items(saved, location)
        total   = saved.items.count()
        in_cart = saved.items.filter(in_cart=True).count()
        all_done = total > 0 and in_cart == total
        return render(request, self.template_name, {
            'saved': saved,
            'grouped': grouped,
            'aisle_label': aisle_label,
            'location_choices': _LOCATION_QS(),
            'location': location,
            'location_id': location_id,
            'total': total,
            'in_cart': in_cart,
            'all_done': all_done,
        })


class SavedGroceryDeleteView(View):
    def post(self, request, pk):
        SavedGroceryList.objects.filter(pk=pk).delete()
        next_url = request.POST.get('next', '')
        return redirect(next_url if next_url else 'saved-grocery-list')


class ArchiveGroceryListView(View):
    def post(self, request, pk):
        saved = get_object_or_404(SavedGroceryList, pk=pk)
        saved.archived = True
        saved.save(update_fields=['archived'])
        return redirect('grocery-list')


class ToggleCartItemView(View):
    def post(self, request, pk):
        item = get_object_or_404(SavedGroceryItem, pk=pk)
        item.in_cart = not item.in_cart
        item.save(update_fields=['in_cart'])
        saved = item.grocery_list
        total    = saved.items.count()
        in_cart  = saved.items.filter(in_cart=True).count()
        pct      = f'calc({in_cart} / {total} * 100%)' if total else '0%'
        all_done = total > 0 and in_cart == total
        item_html = render_to_string('partials/cart_item.html', {'item': item}, request=request)
        archive_html = render_to_string(
            'partials/archive_btn.html',
            {'saved': saved, 'all_done': all_done},
            request=request,
        )
        oob = (
            f'<span id="progress-text" hx-swap-oob="true">{in_cart} / {total}</span>'
            f'<div id="progress-bar" hx-swap-oob="true"'
            f' class="h-full bg-emerald-500 rounded-full transition-all duration-300"'
            f' style="width:{pct}"></div>'
            f'<div id="archive-btn-area" hx-swap-oob="true">{archive_html}</div>'
        )
        return HttpResponse(item_html + oob)
