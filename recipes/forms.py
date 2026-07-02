from django import forms
from django.forms import inlineformset_factory

from .models import Ingredient, Recipe, RecipeIngredient, Unit

_INPUT_CLASS = 'w-full border border-gray-300 rounded px-2 py-1 text-sm'


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'abbreviation']


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
