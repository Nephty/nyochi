from django import forms
from recipes.models import Recipe, ShopLocation
from recipes.utils import accessible_qs


class GrocerySelectForm(forms.Form):
    recipes = forms.ModelMultipleChoiceField(
        queryset=Recipe.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        label='',
    )
    shop_location = forms.ModelChoiceField(
        queryset=ShopLocation.objects.none(),
        required=False,
        empty_label='',
        label='Sort by shop location',
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['recipes'].queryset = accessible_qs(Recipe, user)
            self.fields['shop_location'].queryset = (
                accessible_qs(ShopLocation, user)
                .select_related('shop')
                .order_by('shop__name', 'name')
            )
        else:
            self.fields['recipes'].queryset = Recipe.objects.all()
            self.fields['shop_location'].queryset = (
                ShopLocation.objects.select_related('shop').order_by('shop__name', 'name')
            )
