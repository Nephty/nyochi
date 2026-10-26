from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from recipes.access import deletable, is_owner, readable, writable
from recipes.http import ApiError, api, body, positive_int
from recipes.models import (
    Aisle, AisleOrder, CategoryAisleMapping, Ingredient, IngredientAisle, IngredientCategory, Shop, ShopLocation,
)

from .forms import ShopForm


def _clean_name(raw, what):
    name = ' '.join(str(raw or '').split())[:100]
    if not name:
        raise ValueError(f'Give the {what} a name.')
    return name


class ShopListView(LoginRequiredMixin, View):
    def get(self, request, form=None):
        shops = readable(Shop, request.user).prefetch_related('aisles', 'locations').order_by('name')
        for s in shops:
            s.mine = is_owner(s, request.user)
        return render(request, 'shops/list.html', {
            'shops': shops, 'form': form or ShopForm(owner=request.user), 'page': 'shops',
        })

    def post(self, request):
        form = ShopForm(request.POST, owner=request.user)
        if form.is_valid():
            shop = form.save(commit=False)
            shop.owner = request.user
            shop.save()
            messages.success(request, f'Added {shop.name}. Now give it locations and aisles.')
            return redirect('shop-detail', pk=shop.pk)
        return self.get(request, form)


def layout_data(shop, locations):
    """Everything the layout editor needs, per location."""
    aisles = list(shop.aisles.all())
    out = {}
    for loc in locations:
        orders = {o.aisle_id: o.order for o in loc.aisle_orders.all()}
        route = sorted((a for a in aisles if a.pk in orders), key=lambda a: orders[a.pk])
        out[loc.pk] = {
            'configured': bool(orders),
            'route': [a.pk for a in route] if orders else [a.pk for a in aisles],
            'mappings': {m.category: m.aisle_id for m in loc.category_mappings.all()},
            'overrides': [
                {'ingredient_id': o.ingredient_id, 'name': o.ingredient.name, 'aisle_id': o.aisle_id}
                for o in loc.ingredient_aisles.all()
            ],
        }
    return out


class ShopDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        shop = get_object_or_404(readable(Shop, request.user), pk=pk)
        locations = list(
            shop.locations.prefetch_related('aisle_orders', 'category_mappings', 'ingredient_aisles__ingredient')
        )
        can_edit = writable(Shop, request.user).filter(pk=shop.pk).exists()
        aisles = list(shop.aisles.all())
        return render(request, 'shops/detail.html', {
            'shop': shop, 'locations': locations, 'aisles': aisles, 'can_edit': can_edit,
            'mine': is_owner(shop, request.user),
            'form': ShopForm(instance=shop, owner=request.user),
            'editor': {
                'canEdit': can_edit,
                'aisles': [{'id': a.pk, 'name': a.name} for a in aisles],
                'categories': [{'value': v, 'label': l} for v, l in IngredientCategory.choices],
                'locations': [{'id': l.pk, 'name': l.name} for l in locations],
                'layouts': layout_data(shop, locations),
                'ingredients': [
                    {'id': i.pk, 'name': i.name, 'category': i.category}
                    for i in readable(Ingredient, request.user).order_by('name')
                ],
                'urls': {
                    'layout': '/shops/locations/0/layout/',
                    'copy': '/shops/locations/0/copy/',
                },
            },
            'page': 'shops',
        })


def _shop(request, pk):
    return get_object_or_404(writable(Shop, request.user), pk=pk)


class ShopUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        shop = _shop(request, pk)
        form = ShopForm(request.POST, instance=shop, owner=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shop updated.')
        else:
            messages.error(request, ' '.join(e for errs in form.errors.values() for e in errs))
        return redirect('shop-detail', pk=shop.pk)


class ShopDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        shop = get_object_or_404(deletable(Shop, request.user), pk=pk)
        name = shop.name
        shop.delete()
        messages.success(request, f'Deleted {name} with its locations and aisles.')
        return redirect('shop-list')


class LocationAddView(LoginRequiredMixin, View):
    def post(self, request, pk):
        shop = _shop(request, pk)
        try:
            name = _clean_name(request.POST.get('name'), 'location')
            ShopLocation.objects.create(shop=shop, name=name, owner_id=shop.owner_id)
            messages.success(request, f'Added location “{name}”.')
        except ValueError as exc:
            messages.error(request, str(exc))
        except IntegrityError:
            messages.error(request, 'This shop already has a location with that name.')
        return redirect('shop-detail', pk=shop.pk)


class LocationDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        location = get_object_or_404(ShopLocation, pk=pk, shop__in=writable(Shop, request.user).values('pk'))
        shop_pk = location.shop_id
        location.delete()
        messages.success(request, 'Location deleted.')
        return redirect('shop-detail', pk=shop_pk)


class AisleAddView(LoginRequiredMixin, View):
    def post(self, request, pk):
        shop = _shop(request, pk)
        names = [n for n in (' '.join(p.split())[:100] for p in request.POST.get('names', '').replace(',', '\n').splitlines()) if n]
        if not names:
            messages.error(request, 'Type at least one aisle name (several can be separated by commas).')
            return redirect('shop-detail', pk=shop.pk)
        added = 0
        for name in names:
            _, created = Aisle.objects.get_or_create(shop=shop, name=name, defaults={'owner_id': shop.owner_id})
            added += created
        messages.success(request, f'Added {added} aisle{"s" if added != 1 else ""}.' if added else 'Those aisles already exist.')
        return redirect('shop-detail', pk=shop.pk)


class AisleUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        aisle = get_object_or_404(Aisle, pk=pk, shop__in=writable(Shop, request.user).values('pk'))
        try:
            name = _clean_name(request.POST.get('name'), 'aisle')
            aisle.name = name
            aisle.save(update_fields=['name'])
            messages.success(request, 'Aisle renamed.')
        except ValueError as exc:
            messages.error(request, str(exc))
        except IntegrityError:
            messages.error(request, 'This shop already has an aisle with that name.')
        return redirect('shop-detail', pk=aisle.shop_id)


class AisleDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        aisle = get_object_or_404(Aisle, pk=pk, shop__in=writable(Shop, request.user).values('pk'))
        shop_pk = aisle.shop_id
        aisle.delete()
        messages.success(request, 'Aisle deleted (and removed from every location’s route).')
        return redirect('shop-detail', pk=shop_pk)


# ------------------------------------------------------------------ the layout editor's JSON

def _location_for_edit(request, pk):
    location = ShopLocation.objects.filter(pk=pk, shop__in=writable(Shop, request.user).values('pk')).first()
    if location is None:
        raise ApiError('Location not found.', 404)
    return location


@api
def save_layout(request, pk):
    """POST {route: [aisle ids in walking order], mappings: {category: aisle id | null},
    overrides: [{ingredient_id, aisle_id}]} -> replaces the location's whole layout."""
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    location = _location_for_edit(request, pk)
    data = body(request)
    shop_aisles = set(location.shop.aisles.values_list('pk', flat=True))
    route = []
    for raw in data.get('route', []):
        aid = positive_int(raw, 'aisle')
        if aid not in shop_aisles:
            raise ApiError('An aisle of the route is not in this shop.')
        if aid not in route:
            route.append(aid)
    mappings = {}
    for cat, raw in (data.get('mappings') or {}).items():
        if cat not in IngredientCategory.values:
            raise ApiError(f'Unknown category “{cat}”.')
        if raw in (None, ''):
            continue
        aid = positive_int(raw, 'aisle')
        if aid in route:       # an aisle that isn't on the route can't hold anything
            mappings[cat] = aid
    overrides = {}
    readable_ids = set(readable(Ingredient, request.user).values_list('pk', flat=True))
    for item in data.get('overrides') or []:
        iid, aid = positive_int(item.get('ingredient_id'), 'ingredient'), positive_int(item.get('aisle_id'), 'aisle')
        if iid in readable_ids and aid in route:
            overrides[iid] = aid
    owner_id = location.shop.owner_id
    with transaction.atomic():
        location.aisle_orders.exclude(aisle_id__in=route).delete()
        for position, aid in enumerate(route, start=1):
            AisleOrder.objects.update_or_create(
                location=location, aisle_id=aid, defaults={'order': position, 'owner_id': owner_id})
        location.category_mappings.all().delete()
        CategoryAisleMapping.objects.bulk_create([
            CategoryAisleMapping(location=location, category=c, aisle_id=a, owner_id=owner_id)
            for c, a in mappings.items()
        ])
        location.ingredient_aisles.all().delete()
        IngredientAisle.objects.bulk_create([
            IngredientAisle(location=location, ingredient_id=i, aisle_id=a) for i, a in overrides.items()
        ])
    return JsonResponse({'saved': True, 'route': route, 'mappings': mappings})


@api
def copy_layout(request, pk):
    """POST {from: location id} -> this location gets the other one's route, mappings and exceptions."""
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    target = _location_for_edit(request, pk)
    source = ShopLocation.objects.filter(
        pk=positive_int(body(request).get('from'), 'location'), shop_id=target.shop_id).first()
    if source is None or source.pk == target.pk:
        raise ApiError('Pick another location of this shop.')
    owner_id = target.shop.owner_id
    with transaction.atomic():
        for model in (AisleOrder, CategoryAisleMapping, IngredientAisle):
            model.objects.filter(location=target).delete()
        AisleOrder.objects.bulk_create([
            AisleOrder(location=target, aisle_id=o.aisle_id, order=o.order, owner_id=owner_id)
            for o in source.aisle_orders.all()])
        CategoryAisleMapping.objects.bulk_create([
            CategoryAisleMapping(location=target, category=m.category, aisle_id=m.aisle_id, owner_id=owner_id)
            for m in source.category_mappings.all()])
        IngredientAisle.objects.bulk_create([
            IngredientAisle(location=target, ingredient_id=o.ingredient_id, aisle_id=o.aisle_id)
            for o in source.ingredient_aisles.all()])
    return JsonResponse({'copied': True})
