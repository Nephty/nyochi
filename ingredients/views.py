from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from recipes import shopping
from recipes.access import deletable, is_owner, readable, writable
from recipes.community import can_edit
from recipes.http import ApiError, api, body
from recipes import categories
from recipes.models import Ingredient, Recipe, ShoppingLink
from recipes.seasons import current_month

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
            'in_season_count': sum(1 for i in ingredients if i.status_now in ('in', 'early', 'late')),
        })


class IngredientDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        ingredient = get_object_or_404(readable(Ingredient, request.user), pk=pk)
        links = list(ingredient.shopping_links.all())
        reachable = shopping.refresh(links) if links else True
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
        return self._render(request, ingredient, IngredientForm(instance=ingredient, owner=request.user))

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
    labels = categories.user_labels(request.user)
    category = data.get('category') or categories.default_key(labels)
    if category not in labels:
        raise ApiError('Unknown category.')
    existing = readable(Ingredient, request.user).filter(name__iexact=name).first()
    if existing:
        return JsonResponse({'id': existing.pk, 'name': existing.name, 'existing': True})
    ingredient = Ingredient.objects.create(name=name, category=category, owner=request.user)
    from recipes.models import SeasonalAvailability
    SeasonalAvailability.objects.bulk_create(
        [SeasonalAvailability(ingredient=ingredient, month=m, status='out') for m in range(1, 13)])
    return JsonResponse({'id': ingredient.pk, 'name': ingredient.name, 'existing': False}, status=201)


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
