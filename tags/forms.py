from django import forms

from recipes.forms import UniqueNameMixin
from recipes.models import Tag


class TagForm(UniqueNameMixin, forms.ModelForm):
    owner_label = 'a tag'

    class Meta:
        model = Tag
        fields = ['name']
