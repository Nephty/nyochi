"""Metric only: amounts in cups become millilitres and the cup unit goes (teaspoon and tablespoon stay: 5 and 15 ml)."""
from decimal import Decimal

from django.db import migrations

CUP_ML = Decimal(240)


def to_metric(apps, schema_editor):
    Unit = apps.get_model('recipes', 'Unit')
    RecipeIngredient = apps.get_model('recipes', 'RecipeIngredient')
    SavedGroceryItem = apps.get_model('recipes', 'SavedGroceryItem')
    cups = [u for u in Unit.objects.all() if 'cup' in (u.abbreviation.strip().lower(), u.name.strip().lower())]
    if not cups:
        return
    ml = Unit.objects.filter(dimension='volume', factor=Decimal(1)).order_by('pk').first()
    if ml is None:
        ml = Unit.objects.create(name='milliliter', abbreviation='ml', dimension='volume', factor=Decimal(1))
    for cup in cups:
        for Model in (RecipeIngredient, SavedGroceryItem):
            for row in Model.objects.filter(unit=cup):
                row.quantity = (row.quantity * CUP_ML).quantize(Decimal('0.01'))
                row.unit = ml
                row.save(update_fields=['quantity', 'unit'])
        cup.delete()


class Migration(migrations.Migration):
    dependencies = [('recipes', '0019_list_covers')]
    operations = [migrations.RunPython(to_metric, migrations.RunPython.noop)]
