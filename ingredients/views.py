from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from recipes import shopping
from recipes.access import deletable, is_owner, readable, writable
from recipes.community import can_edit
from recipes.http import ApiError, api, body, positive_int
from recipes import categories
from recipes.models import Ingredient, Recipe, ShoppingLink, Unit, UnitPrice
from recipes.seasons import current_month
from recipes.views import unit_price_json, units_json

from .forms import IngredientForm


class IngredientListView(LoginRequiredMixin, View):
    def get(self, request):
        month = current_month()
        labels = categories.user_labels(request.user)
        position = {k: i for i, k in enumerate(labels)}
        ingredients = sorted(
            readable(Ingredient, request.user).prefetch_related('seasonal_availability', 'shopping_links'),
            key=lambda i: (position.get(i.category, 999), categories.label_of(i.category, labels).lower(), i.name.lower()),
        )
        for ing in ingredients:
            ing.category_label = categories.label_of(ing.category, labels)
            ing.seasons = ing.season_map()
            ing.status_now = ing.seasons.get(month, 'unknown')
            link = shopping.pick_link(list(ing.shopping_links.all()))
            ing.link = link
            ing.promo = bool(link and shopping.promo_active(link))
            ing.mine = is_owner(ing, request.user)
        return render(request, 'ingredients/list.html', {
            'ingredients': ingredients, 'categories': list(labels.items()), 'page': 'ingredients',
            'several': {'url': reverse('ingredient-bulk'), 'default': categories.default_key(labels),
                        'categories': [{'key': k, 'label': v} for k, v in labels.items()]},
            'in_season_count': sum(1 for i in ingredients if i.status_now in ('in', 'early', 'late')),
        })


class IngredientDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        ingredient = get_object_or_404(readable(Ingredient, request.user), pk=pk)
        links = list(ingredient.shopping_links.all())
        reachable = shopping.refresh(links) if links else True
        unit_prices = list(ingredient.unit_prices.select_related('unit'))
        month = current_month()
        recipes = (
            readable(Recipe, request.user)
            .filter(recipeingredient__ingredient=ingredient)
            .select_related().distinct()
        )
        return render(request, 'ingredients/detail.html', {
            'ingredient': ingredient,
            'category_label': categories.label_of(ingredient.category, categories.user_labels(request.user)), 'seasons': ingredient.season_map(), 'month': month,
            'links': [
                {'link': l, 'promo': shopping.promo_active(l), 'verdict': shopping.verdict(l),
                 'deal': shopping.deal_text(l)} for l in links
            ],
            'recipes': recipes, 'reachable': reachable, 'shopping_on': shopping.configured(),
            'mine': is_owner(ingredient, request.user),
            'can_edit': writable(Ingredient, request.user).filter(pk=ingredient.pk).exists(),
            'page': 'ingredients',
            'unit_prices': unit_prices,
            'price_boot': {'ingredient': ingredient.pk, 'name': ingredient.name, 'priceUrl': reverse('unit-price-save'),
                           'units': units_json(), 'prices': [unit_price_json(p) for p in unit_prices],
                           # "Add a price" starts with the unit the recipes use most for it
                           'unit': ingredient.recipeingredient_set.values('unit').annotate(n=Count('pk'))
                           .order_by('-n').values_list('unit', flat=True).first()},
        })


def _sync_links(ingredient, request):
    """Make the ingredient's Shopping links match the form: the posted keys, one of them preferred."""
    posted = []
    for key in request.POST.getlist('link'):
        key = key.strip()
        if shopping.KEY_RE.match(key) and key not in posted:
            posted.append(key)
    preferred = request.POST.get('preferred', '')
    existing = {l.key: l for l in ingredient.shopping_links.all()}
    for key, link in existing.items():
        if key not in posted:
            link.delete()
    created = []
    for key in posted:
        store, code = key.split('|', 1)
        link = existing.get(key)
        if link is None:
            link = ShoppingLink.objects.create(ingredient=ingredient, key=key, store=store, code=code,
                                               store_label=store.title())
            created.append(link)
            existing[key] = link
        want = key == preferred
        if link.is_preferred != want:
            link.is_preferred = want
            link.save(update_fields=['is_preferred'])
    if created:
        shopping.refresh(created, force=True)   # one batch call; offline, the next page view fills them in
    return len(posted)


class IngredientFormView(LoginRequiredMixin, View):
    template_name = 'ingredients/form.html'

    def _ingredient(self, request, pk):
        if not pk and not can_edit(request.user, Ingredient):
            raise Http404('Your community does not let you add ingredients.')
        return get_object_or_404(writable(Ingredient, request.user), pk=pk) if pk else None

    def _render(self, request, ingredient, form):
        links = list(ingredient.shopping_links.all()) if ingredient else []
        if request.method == 'POST':   # keep what was picked when the form comes back with errors
            keys = [k for k in request.POST.getlist('link') if shopping.KEY_RE.match(k)]
            by_key = {l.key: l for l in links}
            links = [by_key.get(k) or ShoppingLink(key=k, store=k.split('|')[0], code=k.split('|')[1],
                                                   name=k) for k in dict.fromkeys(keys)]
            for l in links:
                l.is_preferred = l.key == request.POST.get('preferred')
        return render(request, self.template_name, {
            'form': form, 'ingredient': ingredient, 'links': links, 'page': 'ingredients',
            'title': f'Edit {ingredient.name}' if ingredient else 'New ingredient',
            'shopping_on': shopping.configured(),
            'links_json': [shopping.link_json(l) for l in links],
        })

    def get(self, request, pk=None):
        ingredient = self._ingredient(request, pk)
        form = IngredientForm(instance=ingredient, owner=request.user)
        # "Save and add another" keeps the category of the one just saved
        if ingredient is None and request.GET.get('category') in dict(form.fields['category'].choices):
            form.initial['category'] = request.GET['category']
        return self._render(request, ingredient, form)

    def post(self, request, pk=None):
        ingredient = self._ingredient(request, pk)
        form = IngredientForm(request.POST, instance=ingredient, owner=request.user)
        if form.is_valid():
            with transaction.atomic():
                saved = form.save(commit=False)
                if ingredient is None:
                    saved.owner = request.user
                saved.save()
                form.save_seasons(saved)
                n = _sync_links(saved, request)
            messages.success(request, f'Saved “{saved.name}”' + (f' with {n} linked product{"s" if n != 1 else ""}.' if n else '.'))
            if ingredient is None and request.POST.get('then') == 'new':
                return redirect(f"{reverse('ingredient-create')}?{urlencode({'category': saved.category})}")
            return redirect('ingredient-detail', pk=saved.pk)
        messages.error(request, 'The ingredient was not saved: fix the highlighted fields.')
        return self._render(request, ingredient, form)


class IngredientDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ingredient = get_object_or_404(deletable(Ingredient, request.user), pk=pk)
        name = ingredient.name
        ingredient.delete()
        messages.success(request, f'Deleted “{name}” (and its place in recipes and lists).')
        return redirect('ingredient-list')


@api
def quick_create(request):
    """POST {name, category?} -> the user's ingredient of that name (created if needed)."""
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    if not can_edit(request.user, Ingredient):
        raise ApiError('Your community does not let you add ingredients.', 403)
    data = body(request)
    name = ' '.join(str(data.get('name', '')).split())[:100]
    if not name:
        raise ApiError('Give the ingredient a name.')
    ingredient, made = _make(request.user, name, _category(request.user, data.get('category')))
    return JsonResponse({'id': ingredient.pk, 'name': ingredient.name, 'existing': not made}, status=201 if made else 200)


def _category(user, key):
    labels = categories.user_labels(user)
    key = key or categories.default_key(labels)
    if key not in labels:
        raise ApiError('Unknown category.')
    return key


def _make(user, name, category):
    """(ingredient, created): the community's ingredient of that name, made (no season, no product) if needed."""
    existing = readable(Ingredient, user).filter(name__iexact=name).first()
    if existing:
        return existing, False
    ingredient = Ingredient.objects.create(name=name, category=category, owner=user)
    from recipes.models import SeasonalAvailability
    SeasonalAvailability.objects.bulk_create(
        [SeasonalAvailability(ingredient=ingredient, month=m, status='out') for m in range(1, 13)])
    return ingredient, True


@api
def bulk_create(request):
    """POST {names: [..], category} -> several ingredients at once (seasons and products added later, one by one)."""
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    if not can_edit(request.user, Ingredient):
        raise ApiError('Your community does not let you add ingredients.', 403)
    data = body(request)
    names = []
    for raw in data.get('names') or []:
        name = ' '.join(str(raw).split())[:100]
        if name and name.lower() not in [n.lower() for n in names]:
            names.append(name)
    if not names:
        raise ApiError('Write at least one name.')
    if len(names) > 100:
        raise ApiError('At most 100 at a time.')
    category = _category(request.user, data.get('category'))
    made, existing = [], []
    with transaction.atomic():
        for name in names:
            ingredient, created = _make(request.user, name, category)
            (made if created else existing).append(ingredient.name)
    text = f'Added {len(made)} ingredient{"s" if len(made) != 1 else ""}.' if made else 'Nothing added.'
    if existing:
        text += f' Already there: {", ".join(existing)}.'
    messages.success(request, text)
    return JsonResponse({'made': made, 'existing': existing}, status=201 if made else 200)


def _amount(value, what, most):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ApiError(f'Give {what} as a number.')
    if not n.is_finite() or n <= 0 or n > most:
        raise ApiError(f'{what[0].upper()}{what[1:]} must be more than 0 and at most {most}.')
    return n


@api
def unit_price_save(request):
    """POST {ingredient, unit, paid, for} -> the price of one unit of an ingredient, entered by hand (€10 for 100 tbsp).
    {ingredient, unit, remove: true} deletes it. Answers {price} (null once removed)."""
    if request.method != 'POST':
        raise ApiError('POST only.', 405)
    data = body(request)
    ingredient = writable(Ingredient, request.user).filter(pk=positive_int(data.get('ingredient'), 'ingredient')).first()
    if ingredient is None:
        raise ApiError('You can’t change this ingredient.', 403)
    unit = Unit.objects.filter(pk=positive_int(data.get('unit'), 'unit')).first()
    if unit is None:
        raise ApiError('Unknown unit.')
    if data.get('remove'):
        UnitPrice.objects.filter(ingredient=ingredient, unit=unit).delete()
        return JsonResponse({'price': None})
    paid = _amount(data.get('paid'), 'the price', 10000).quantize(Decimal('0.01'))
    amount = _amount(data.get('for'), 'the amount', 100000).quantize(Decimal('0.001'))
    if paid <= 0 or amount <= 0:
        raise ApiError('The price and the amount must be more than 0.')
    with transaction.atomic():
        price, _ = UnitPrice.objects.update_or_create(
            ingredient=ingredient, unit=unit,
            defaults={'paid': paid, 'for_amount': amount, 'price': (paid / amount).quantize(Decimal('0.000001'))})
        if data.get('replaces') and str(data['replaces']) != str(unit.pk):   # the price moved to another unit
            UnitPrice.objects.filter(ingredient=ingredient, unit_id=positive_int(data['replaces'], 'unit')).delete()
    return JsonResponse({'price': unit_price_json(price)})


@api
def shopping_search(request):
    """GET ?q=&store= -> Shopping products (proxied: the browser may not call Shopping itself)."""
    if not shopping.configured():
        raise ApiError('The Shopping link is not set up on this server.', 503)
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'rows': []})
    rows = shopping.search(q, request.GET.get('store', ''))
    if rows is None:
        raise ApiError('Shopping is unreachable right now.', 503)
    return JsonResponse({'rows': rows})
