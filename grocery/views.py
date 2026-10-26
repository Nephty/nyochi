from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from recipes import grocery
from recipes.access import (
    deletable, is_owner, readable, readable_locations, readable_items, writable, writable_items,
)
from recipes.http import ApiError, api, body, positive_int
from recipes.models import Ingredient, SavedGroceryItem, SavedGroceryList, Unit


class SavedListsView(LoginRequiredMixin, View):
    def get(self, request):
        archived = request.GET.get('tab') == 'archived'
        lists = (
            readable(SavedGroceryList, request.user).filter(archived=archived)
            .annotate(total=Count('items', distinct=True),
                      done=Count('items', filter=Q(items__in_cart=True), distinct=True))
            .prefetch_related('recipes').select_related('location__shop')
        )
        for l in lists:
            l.mine = is_owner(l, request.user)
        return render(request, 'lists/list.html', {
            'lists': lists, 'archived': archived, 'page': 'lists',
            'archived_count': readable(SavedGroceryList, request.user).filter(archived=True).count(),
        })


def _list_for_read(request, pk):
    return get_object_or_404(readable(SavedGroceryList, request.user).prefetch_related('recipes'), pk=pk)


def _list_for_write(request, pk):
    return get_object_or_404(writable(SavedGroceryList, request.user), pk=pk)


def _location(request, raw):
    if not raw:
        return None
    return readable_locations(request.user).select_related('shop').filter(pk=positive_int(raw, 'location')).first()


def _receipt(saved, location, user):
    items = saved.items.select_related('ingredient', 'unit').prefetch_related('ingredient__seasonal_availability')
    data = grocery.receipt(grocery.lines_from_items(items), location, user)
    done = sum(1 for s in data['sections'] for l in s['lines'] if l['checked'])
    data['progress'] = {'done': done, 'total': data['totals']['lines']}
    return data


class SavedListDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        saved = _list_for_read(request, pk)
        location = _location(request, request.GET.get('location')) or saved.location
        if location is not None and not readable_locations(request.user).filter(pk=location.pk).exists():
            location = None
        ingredients = readable(Ingredient, request.user).order_by('name')
        return render(request, 'lists/detail.html', {
            'saved': saved, 'page': 'lists',
            'can_edit': writable(SavedGroceryList, request.user).filter(pk=saved.pk).exists(),
            'mine': is_owner(saved, request.user),
            'data': {
                'id': saved.pk,
                'receipt': _receipt(saved, location, request.user),
                'location': location.pk if location else None,
                'locations': [{'id': l.pk, 'name': str(l)}
                              for l in readable_locations(request.user).select_related('shop')
                              .order_by('shop__name', 'name')],
                'ingredients': [{'id': i.pk, 'name': i.name} for i in ingredients],
                'units': [{'id': u.pk, 'abbr': u.abbreviation, 'name': u.name} for u in Unit.objects.all()],
                'canEdit': writable(SavedGroceryList, request.user).filter(pk=saved.pk).exists(),
            },
            'recipes': saved.recipes.all(),
        })


@api
def receipt_json(request, pk):
    saved = _list_for_read(request, pk)
    location = _location(request, request.GET.get('location'))
    return JsonResponse(_receipt(saved, location, request.user))


class SavedListActionView(LoginRequiredMixin, View):
    """Plain form posts from the lists page and the list screen: rename, archive, unarchive, delete."""

    def post(self, request, pk, action):
        if action == 'delete':
            saved = get_object_or_404(deletable(SavedGroceryList, request.user), pk=pk)
            saved.delete()
            messages.success(request, 'List deleted.')
            return redirect('saved-grocery-list')
        saved = _list_for_write(request, pk)
        if action == 'rename':
            name = ' '.join(request.POST.get('name', '').split())[:200]
            if not name:
                messages.error(request, 'A list needs a name.')
            else:
                saved.name = name
                saved.save(update_fields=['name'])
                messages.success(request, 'List renamed.')
            return redirect('saved-grocery-detail', pk=saved.pk)
        if action in ('archive', 'unarchive'):
            saved.archived = action == 'archive'
            saved.save(update_fields=['archived'])
            messages.success(request, 'List archived.' if saved.archived else 'List restored.')
            return redirect('saved-grocery-list')
        raise ApiError('Unknown action.', 404)


@api
def set_location(request, pk):
    saved = _list_for_write(request, pk)
    location = _location(request, body(request).get('location'))
    saved.location = location
    saved.save(update_fields=['location'])
    return JsonResponse(_receipt(saved, location, request.user))


@api
def check_item(request, pk):
    item = get_object_or_404(writable_items(request.user), pk=pk)
    checked = body(request).get('checked')
    if not isinstance(checked, bool):
        raise ApiError('Say whether the item is in the cart (checked: true/false).')
    item.in_cart = checked
    item.save(update_fields=['in_cart'])
    qs = item.grocery_list.items
    return JsonResponse({'done': qs.filter(in_cart=True).count(), 'total': qs.count()})


@api
def uncheck_all(request, pk):
    saved = _list_for_write(request, pk)
    saved.items.update(in_cart=False)
    return JsonResponse({'done': 0, 'total': saved.items.count()})


@api
def add_item(request, pk):
    saved = _list_for_write(request, pk)
    data = body(request)
    if data.get('ingredient_id'):
        ingredient = readable(Ingredient, request.user).filter(
            pk=positive_int(data['ingredient_id'], 'ingredient')).first()
        if ingredient is None:
            raise ApiError('Unknown ingredient.', 404)
        unit = Unit.objects.filter(pk=positive_int(data.get('unit_id'), 'unit')).first()
        if unit is None:
            raise ApiError('Pick a unit.')
        try:
            quantity = Decimal(str(data.get('quantity', 1)))
        except InvalidOperation:
            raise ApiError('Invalid quantity.')
        if not Decimal('0.01') <= quantity <= Decimal('99999'):
            raise ApiError('Quantity must be positive.')
        item = saved.items.filter(ingredient=ingredient, unit=unit).first()
        if item:
            item.quantity += quantity
            item.in_cart = False
            item.save(update_fields=['quantity', 'in_cart'])
        else:
            SavedGroceryItem.objects.create(grocery_list=saved, ingredient=ingredient, unit=unit,
                                            quantity=quantity, owner=request.user)
    else:
        name = ' '.join(str(data.get('name', '')).split())[:120]
        if not name:
            raise ApiError('Type what to buy.')
        SavedGroceryItem.objects.create(grocery_list=saved, custom_name=name, owner=request.user)
    return JsonResponse(_receipt(saved, saved.location, request.user), status=201)


@api
def delete_item(request, pk):
    item = get_object_or_404(writable_items(request.user), pk=pk)
    saved = item.grocery_list
    item.delete()
    return JsonResponse(_receipt(saved, saved.location, request.user))
