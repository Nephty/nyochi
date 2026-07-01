from django import forms
from django.forms import inlineformset_factory

from .models import (
    Aisle, CategoryAisleMapping, Ingredient, IngredientCategory,
    Recipe, RecipeIngredient, SeasonalAvailability, Shop, ShopLink,
    ShopLocation, Tag, Unit,
)

MONTHS = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]

_INPUT_CLASS = 'w-full border border-gray-300 rounded px-2 py-1 text-sm'


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

# Used only on the create view: extra=12 so the 12 initial month forms are rendered
SeasonalAvailabilityCreateFormSet = inlineformset_factory(
    Ingredient,
    SeasonalAvailability,
    form=SeasonalAvailabilityForm,
    extra=12,
    can_delete=False,
)


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name']


class ShopLocationForm(forms.ModelForm):
    class Meta:
        model = ShopLocation
        fields = ['shop', 'name']
        widgets = {'shop': forms.HiddenInput()}


class AisleForm(forms.ModelForm):
    class Meta:
        model = Aisle
        fields = ['shop', 'name']
        widgets = {'shop': forms.HiddenInput()}


class ShopLinkForm(forms.ModelForm):
    class Meta:
        model = ShopLink
        fields = ['shop', 'name', 'url']
        widgets = {
            'shop': forms.Select(attrs={'class': _INPUT_CLASS}),
            'name': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Label (optional)'}),
            'url': forms.URLInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'https://…'}),
        }


ShopLinkFormSet = inlineformset_factory(
    Ingredient,
    ShopLink,
    form=ShopLinkForm,
    extra=1,
    can_delete=True,
)


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['name', 'difficulty', 'meal_type', 'description', 'prep_time', 'cook_time', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.CheckboxSelectMultiple(),
        }


class RecipeIngredientForm(forms.ModelForm):
    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'quantity', 'unit', 'is_main']
        widgets = {
            'ingredient': forms.Select(attrs={'class': _INPUT_CLASS}),
            'quantity': forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': '0.01', 'min': '0'}),
            'unit': forms.Select(attrs={'class': _INPUT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ingredient'].empty_label = ''
        self.fields['unit'].empty_label = ''


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
    shop_location = forms.ModelChoiceField(
        queryset=ShopLocation.objects.select_related('shop').order_by('shop__name', 'name'),
        required=False,
        empty_label='',
        label='Sort by shop location',
    )


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
