from django import forms
from recipes.models import Recipe, ShopLocation


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
