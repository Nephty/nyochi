from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from recipes.models import Aisle, AisleOrder, CategoryAisleMapping, IngredientCategory, Shop, ShopLocation
from recipes.utils import accessible_qs, is_htmx
from .forms import AisleForm, ShopForm, ShopLocationForm


class ShopListView(LoginRequiredMixin, View):
    template_name = 'shops/list.html'

    def get(self, request):
        return render(request, self.template_name, {
            'shops': accessible_qs(Shop, request.user).prefetch_related('aisles', 'locations'),
            'form': ShopForm(),
        })

    def post(self, request):
        form = ShopForm(request.POST)
        if form.is_valid():
            shop = form.save(commit=False)
            shop.owner = request.user
            shop.save()
            if is_htmx(request):
                return render(request, 'partials/shop_card.html', {'shop': shop})
            return redirect('shop-list')
        return render(request, self.template_name, {
            'shops': accessible_qs(Shop, request.user).prefetch_related('aisles', 'locations'),
            'form': form,
        })


class ShopDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        accessible_qs(Shop, request.user).filter(pk=pk).delete()
        if is_htmx(request):
            return HttpResponse('')
        return redirect('shop-list')


class ShopDetailView(LoginRequiredMixin, View):
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
        shop = get_object_or_404(accessible_qs(Shop, request.user), pk=pk)
        return render(request, self.template_name, self._ctx(shop))

    def post(self, request, pk):
        shop = get_object_or_404(accessible_qs(Shop, request.user), pk=pk)
        action = request.POST.get('action')

        if action == 'add_aisle':
            data = request.POST.copy()
            data['shop'] = shop.pk
            form = AisleForm(data)
            if form.is_valid():
                aisle = form.save(commit=False)
                aisle.owner = request.user
                aisle.save()
                if is_htmx(request):
                    return render(request, 'partials/aisle_item.html', {'aisle': aisle, 'shop': shop})
                return redirect('shop-detail', pk=shop.pk)
            return render(request, self.template_name, self._ctx(shop, aisle_form=form))

        elif action == 'add_location':
            data = request.POST.copy()
            data['shop'] = shop.pk
            form = ShopLocationForm(data)
            if form.is_valid():
                loc = form.save(commit=False)
                loc.owner = request.user
                loc.save()
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
                                defaults={'order': int(val), 'owner': request.user},
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
                                defaults={'aisle': aisle, 'owner': request.user},
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
                            defaults={'aisle': m.aisle, 'owner': request.user},
                        )
                if is_htmx(request):
                    return HttpResponse('Copied ✓')

        return redirect('shop-detail', pk=shop.pk)


class AisleDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        aisle = get_object_or_404(accessible_qs(Aisle, request.user), pk=pk)
        shop_pk = aisle.shop_id
        aisle.delete()
        if is_htmx(request):
            return HttpResponse('')
        return redirect('shop-detail', pk=shop_pk)


class ShopLocationDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        location = get_object_or_404(accessible_qs(ShopLocation, request.user), pk=pk)
        shop_pk = location.shop_id
        location.delete()
        if is_htmx(request):
            return HttpResponse('')
        return redirect('shop-detail', pk=shop_pk)
