from django import forms
from recipes.models import Aisle, Shop, ShopLocation


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
