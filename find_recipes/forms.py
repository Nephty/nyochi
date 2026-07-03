from django import forms
from recipes.models import Ingredient, Tag
from recipes.utils import accessible_qs


class RecipeSelectorForm(forms.Form):
    include_ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Must include ingredients',
    )
    exclude_ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.none(),
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

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            ing_qs = accessible_qs(Ingredient, user)
        else:
            ing_qs = Ingredient.objects.all()
        self.fields['include_ingredients'].queryset = ing_qs
        self.fields['exclude_ingredients'].queryset = ing_qs
