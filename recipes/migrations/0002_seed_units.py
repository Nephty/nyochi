from django.db import migrations

UNITS = [
    ('grams', 'g'),
    ('kilograms', 'kg'),
    ('millilitres', 'ml'),
    ('litres', 'l'),
    ('teaspoon', 'tsp'),
    ('tablespoon', 'tbsp'),
    ('cup', 'cup'),
    ('piece', 'pc'),
    ('clove', 'clove'),
    ('bunch', 'bunch'),
    ('slice', 'slice'),
    ('pinch', 'pinch'),
]


def seed_units(apps, schema_editor):
    Unit = apps.get_model('recipes', 'Unit')
    for name, abbreviation in UNITS:
        Unit.objects.get_or_create(name=name, defaults={'abbreviation': abbreviation})


class Migration(migrations.Migration):
    dependencies = [('recipes', '0001_initial')]
    operations = [migrations.RunPython(seed_units, migrations.RunPython.noop)]
