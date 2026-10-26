from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from recipes.access import deletable, is_owner, readable
from recipes.models import Tag

from .forms import TagForm


class TagListView(LoginRequiredMixin, View):
    def get(self, request, form=None):
        tags = readable(Tag, request.user).annotate(uses=Count('recipe')).order_by('name')
        for t in tags:
            t.mine = is_owner(t, request.user)
        return render(request, 'tags/tags.html', {'tags': tags, 'form': form or TagForm(owner=request.user),
                                                  'page': 'tags'})

    def post(self, request):
        form = TagForm(request.POST, owner=request.user)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.owner = request.user
            tag.save()
            messages.success(request, f'Added the tag “{tag.name}”.')
            return redirect('tag-list')
        return self.get(request, form)


class TagDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        tag = get_object_or_404(deletable(Tag, request.user), pk=pk)
        name = tag.name
        tag.delete()
        messages.success(request, f'Deleted the tag “{name}”.')
        return redirect('tag-list')
