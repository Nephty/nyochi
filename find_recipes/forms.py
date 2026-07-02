from django import forms
from recipes.models import Ingredient, Tag


class RecipeSelectorForm(forms.Form):
    include_ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Must include ingredients',
    )
    exclude_ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Exclude ingredients',
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Must have tags',
    )
    max_prep_time = forms.IntegerField(
        required=False,
        min_value=0,
        label='Max prep time (min)',
    )
    max_cook_time = forms.IntegerField(
        required=False,
        min_value=0,
        label='Max cook time (min)',
    )
