from django import forms
from django.forms import inlineformset_factory

from .models import (
    Ingredient, IngredientCategory, Recipe, RecipeIngredient,
    SeasonalAvailability, ShopLink, Tag, Unit,
)

MONTHS = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'abbreviation']


class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['name', 'category']
        widgets = {
            'category': forms.Select(attrs={'class': 'w-full'}),
        }


class SeasonalAvailabilityForm(forms.ModelForm):
    class Meta:
        model = SeasonalAvailability
        fields = ['month', 'status']
        widgets = {
            'month': forms.HiddenInput(),
            'status': forms.Select(),
        }


SeasonalAvailabilityFormSet = inlineformset_factory(
    Ingredient,
    SeasonalAvailability,
    form=SeasonalAvailabilityForm,
    extra=0,
    can_delete=False,
)

ShopLinkFormSet = inlineformset_factory(
    Ingredient,
    ShopLink,
    fields=['shop_name', 'url'],
    extra=1,
    can_delete=True,
)


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['name', 'description', 'prep_time', 'cook_time', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.CheckboxSelectMultiple(),
        }


_INPUT_CLASS = 'w-full border border-gray-300 rounded px-2 py-1 text-sm'


class RecipeIngredientForm(forms.ModelForm):
    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'quantity', 'unit', 'is_main']
        widgets = {
            'ingredient': forms.Select(attrs={'class': _INPUT_CLASS}),
            'quantity': forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': '0.01', 'min': '0'}),
            'unit': forms.Select(attrs={'class': _INPUT_CLASS}),
        }


RecipeIngredientFormSet = inlineformset_factory(
    Recipe,
    RecipeIngredient,
    form=RecipeIngredientForm,
    extra=1,
    can_delete=True,
)


class GrocerySelectForm(forms.Form):
    recipes = forms.ModelMultipleChoiceField(
        queryset=Recipe.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        label='',
    )


class RecipeSelectorForm(forms.Form):
    include_ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 6}),
        label='Must include ingredients',
    )
    exclude_ingredients = forms.ModelMultipleChoiceField(
        queryset=Ingredient.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 6}),
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
    categories = forms.MultipleChoiceField(
        choices=IngredientCategory.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Ingredient categories',
    )
