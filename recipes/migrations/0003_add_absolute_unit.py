from django.db import migrations


def add_absolute_unit(apps, schema_editor):
    Unit = apps.get_model('recipes', 'Unit')
    Unit.objects.get_or_create(name='absolute', defaults={'abbreviation': 'abs'})


class Migration(migrations.Migration):
    dependencies = [('recipes', '0002_seed_units')]
    operations = [migrations.RunPython(add_absolute_unit, migrations.RunPython.noop)]
