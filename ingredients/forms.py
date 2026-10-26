from django import forms

from recipes.forms import UniqueNameMixin
from recipes.models import Ingredient, SeasonalAvailability
from recipes.seasons import MONTHS, STATUS_LABELS, STATUSES


class IngredientForm(UniqueNameMixin, forms.ModelForm):
    """Name, category and the twelve months of the season ribbon (season_1 .. season_12)."""
    owner_label = 'an ingredient'

    class Meta:
        model = Ingredient
        fields = ['name', 'category']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.season_map() if self.instance.pk else {}
        for number, label in MONTHS:
            self.fields[f'season_{number}'] = forms.ChoiceField(
                choices=[(s, STATUS_LABELS[s]) for s in STATUSES], required=False, label=label,
                initial=current.get(number, 'out'),
            )

    def season_values(self):
        return {n: (self.cleaned_data.get(f'season_{n}') or 'out') for n, _ in MONTHS}

    def season_cells(self):
        """[(month number, label, bound field)] for the ribbon editor."""
        return [(n, label, self[f'season_{n}']) for n, label in MONTHS]

    def save_seasons(self, ingredient):
        existing = {sa.month: sa for sa in ingredient.seasonal_availability.all()}
        for month, status in self.season_values().items():
            row = existing.get(month)
            if row is None:
                SeasonalAvailability.objects.create(ingredient=ingredient, month=month, status=status)
            elif row.status != status:
                row.status = status
                row.save(update_fields=['status'])
