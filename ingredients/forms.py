from django import forms
from django.forms import inlineformset_factory
from recipes.models import Ingredient, SeasonalAvailability, Shop, ShopLink
from recipes.utils import accessible_qs

_INPUT_CLASS = (
    'w-full border border-gray-300 rounded px-2 py-1 text-sm '
    'focus:outline-none focus:ring-2 focus:ring-emerald-400 transition-colors'
)


class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['name', 'category']
        widgets = {
            'category': forms.Select(attrs={'class': _INPUT_CLASS}),
        }


class SeasonalAvailabilityForm(forms.ModelForm):
    class Meta:
        model = SeasonalAvailability
        fields = ['month', 'status']
        widgets = {
            'month': forms.HiddenInput(),
            'status': forms.Select(attrs={'class': _INPUT_CLASS}),
        }


SeasonalAvailabilityFormSet = inlineformset_factory(
    Ingredient,
    SeasonalAvailability,
    form=SeasonalAvailabilityForm,
    extra=0,
    can_delete=False,
)

# extra=12 so all 12 month forms are rendered on create
SeasonalAvailabilityCreateFormSet = inlineformset_factory(
    Ingredient,
    SeasonalAvailability,
    form=SeasonalAvailabilityForm,
    extra=12,
    can_delete=False,
)


class ShopLinkForm(forms.ModelForm):
    class Meta:
        model = ShopLink
        fields = ['shop', 'name', 'url']
        widgets = {
            'shop': forms.Select(attrs={'class': _INPUT_CLASS}),
            'name': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Label (optional)'}),
            'url': forms.URLInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'https://…'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['shop'].queryset = accessible_qs(Shop, user)


ShopLinkFormSet = inlineformset_factory(
    Ingredient,
    ShopLink,
    form=ShopLinkForm,
    extra=1,
    can_delete=True,
)
