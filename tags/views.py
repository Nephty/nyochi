from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from recipes.models import Tag
from recipes.utils import is_htmx
from .forms import TagForm


class TagListView(View):
    template_name = 'tags/tags.html'

    def get(self, request):
        return render(request, self.template_name, {
            'tags': Tag.objects.all(),
            'form': TagForm(),
        })

    def post(self, request):
        form = TagForm(request.POST)
        if form.is_valid():
            tag = form.save()
            if is_htmx(request):
                return render(request, 'partials/tag_row.html', {'tag': tag})
            return redirect('tag-list')
        return render(request, self.template_name, {
            'tags': Tag.objects.all(),
            'form': form,
        })


class TagDeleteView(View):
    def post(self, request, pk):
        Tag.objects.filter(pk=pk).delete()
        if is_htmx(request):
            return HttpResponse('')
        return redirect('tag-list')
