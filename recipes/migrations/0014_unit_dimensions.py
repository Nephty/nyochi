from decimal import Decimal

from django.db import migrations

# abbreviation (lower-cased) -> (dimension, factor to the base unit: g, ml, piece)
KNOWN = {
    'g': ('mass', '1'), 'gr': ('mass', '1'), 'gram': ('mass', '1'), 'grams': ('mass', '1'),
    'mg': ('mass', '0.001'),
    'kg': ('mass', '1000'), 'kilogram': ('mass', '1000'), 'kilograms': ('mass', '1000'),
    'ml': ('volume', '1'), 'milliliter': ('volume', '1'), 'millilitre': ('volume', '1'),
    'millilitres': ('volume', '1'), 'milliliters': ('volume', '1'),
    'cl': ('volume', '10'), 'dl': ('volume', '100'),
    'l': ('volume', '1000'), 'liter': ('volume', '1000'), 'litre': ('volume', '1000'),
    'liters': ('volume', '1000'), 'litres': ('volume', '1000'),
    'tsp': ('volume', '5'), 'teaspoon': ('volume', '5'),
    'tbsp': ('volume', '15'), 'tablespoon': ('volume', '15'),
    'cup': ('volume', '240'),
    'pc': ('count', '1'), 'pcs': ('count', '1'), 'piece': ('count', '1'), 'pieces': ('count', '1'),
}


def set_dimensions(apps, schema_editor):
    Unit = apps.get_model('recipes', 'Unit')
    for unit in Unit.objects.all():
        match = KNOWN.get(unit.abbreviation.strip().lower()) or KNOWN.get(unit.name.strip().lower())
        if match:
            unit.dimension, unit.factor = match[0], Decimal(match[1])
            unit.save(update_fields=['dimension', 'factor'])


def ensure_metric_units(apps, schema_editor):
    """The grocery list shows 1500 g as 1.5 kg: g, kg, ml and l have to exist."""
    Unit = apps.get_model('recipes', 'Unit')
    for name, abbr, dim, factor in [
        ('gram', 'g', 'mass', '1'), ('kilogram', 'kg', 'mass', '1000'),
        ('milliliter', 'ml', 'volume', '1'), ('liter', 'l', 'volume', '1000'),
    ]:
        exists = Unit.objects.filter(dimension=dim, factor=Decimal(factor)).exists()
        if not exists:
            Unit.objects.get_or_create(
                name=name, defaults={'abbreviation': abbr, 'dimension': dim, 'factor': Decimal(factor)},
            )


def forwards(apps, schema_editor):
    set_dimensions(apps, schema_editor)
    ensure_metric_units(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [('recipes', '0013_shopping_links_units_layout')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
