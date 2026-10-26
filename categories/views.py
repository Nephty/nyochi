from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from recipes import categories as cats
from recipes.models import Category, CategoryAisleMapping, Ingredient


def _mine(request):
    cats.user_categories(request.user)          # seeds the defaults on first use
    return Category.objects.filter(owner_id=request.user.pk)


def _clean(raw):
    return ' '.join((raw or '').split())[:60]


class CategoryListView(LoginRequiredMixin, View):
    def get(self, request):
        rows = list(_mine(request))
        counts = dict(
            Ingredient.objects.filter(owner_id=request.user.pk).values_list('category')
            .annotate(n=Count('pk')).values_list('category', 'n')
        )
        for c in rows:
            c.uses = counts.get(c.key, 0)
        known = {c.key for c in rows}
        # keys on your own ingredients that have no category any more (only after something went wrong): show them
        orphans = {k: n for k, n in counts.items() if k not in known}
        return render(request, 'categories/list.html', {
            'categories': rows, 'orphans': [(k, cats.pretty(k), n) for k, n in orphans.items()], 'page': 'categories',
        })

    def post(self, request):
        name = _clean(request.POST.get('name'))
        if not name:
            messages.error(request, 'Give the category a name.')
            return redirect('category-list')
        mine = _mine(request)
        if mine.filter(name__iexact=name).exists():
            messages.error(request, f'You already have a category called “{name}”.')
            return redirect('category-list')
        Category.objects.create(owner_id=request.user.pk, name=name, key=cats.new_key(request.user, name),
                                position=mine.count())
        messages.success(request, f'Added the category “{name}”.')
        return redirect('category-list')


class CategoryRenameView(LoginRequiredMixin, View):
    def post(self, request, pk):
        category = get_object_or_404(_mine(request), pk=pk)
        name = _clean(request.POST.get('name'))
        if not name:
            messages.error(request, 'A category needs a name.')
        elif _mine(request).filter(name__iexact=name).exclude(pk=category.pk).exists():
            messages.error(request, f'You already have a category called “{name}”.')
        else:
            category.name = name
            category.save(update_fields=['name'])
            messages.success(request, 'Category renamed.')
        return redirect('category-list')


class CategoryMoveView(LoginRequiredMixin, View):
    def post(self, request, pk, direction):
        if direction not in ('up', 'down'):
            raise Http404
        category = get_object_or_404(_mine(request), pk=pk)
        with transaction.atomic():
            cats.renumber(request.user)
            rows = list(_mine(request))
            i = next(n for n, c in enumerate(rows) if c.pk == category.pk)
            j = i - 1 if direction == 'up' else i + 1
            if 0 <= j < len(rows):
                rows[i].position, rows[j].position = rows[j].position, rows[i].position
                rows[i].save(update_fields=['position'])
                rows[j].save(update_fields=['position'])
        return redirect('category-list')


class CategoryDeleteView(LoginRequiredMixin, View):
    """Deleting a category moves its ingredients to another one (they'd otherwise lose their place on the list)
    and forgets where the category sat in your shops."""

    def post(self, request, pk):
        category = get_object_or_404(_mine(request), pk=pk)
        others = _mine(request).exclude(pk=category.pk)
        if not others.exists():
            messages.error(request, 'You need at least one category.')
            return redirect('category-list')
        ingredients = Ingredient.objects.filter(owner_id=request.user.pk, category=category.key)
        target_key = request.POST.get('move_to') or ''
        target = others.filter(key=target_key).first()
        if ingredients.exists() and target is None:
            messages.error(request, 'Choose the category its ingredients should move to.')
            return redirect('category-list')
        with transaction.atomic():
            moved = ingredients.update(category=target.key) if target else 0
            CategoryAisleMapping.objects.filter(
                category=category.key, location__shop__owner_id=request.user.pk).delete()
            name = category.name
            category.delete()
            cats.renumber(request.user)
        messages.success(request, f'Deleted “{name}”' + (f' and moved {moved} ingredient{"s" if moved != 1 else ""} to “{target.name}”.' if moved else '.'))
        return redirect('category-list')
