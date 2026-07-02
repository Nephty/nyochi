from django import forms
from recipes.models import Tag


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']
