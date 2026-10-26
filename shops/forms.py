from django import forms

from recipes.forms import UniqueNameMixin
from recipes.models import Shop

STORE_CHOICES = [
    ('', 'Not linked to a Shopping store'),
    ('delhaize', 'Delhaize'),
    ('colruyt', 'Colruyt'),
    ('kruidvat', 'Kruidvat'),
]


class ShopForm(UniqueNameMixin, forms.ModelForm):
    owner_label = 'a shop'
    shopping_store = forms.ChoiceField(choices=STORE_CHOICES, required=False, label='Shopping store')

    class Meta:
        model = Shop
        fields = ['name', 'shopping_store']
