from django.db import migrations


def stale(apps, schema_editor):
    """Pack sizes without a unit ("360") used to be unreadable, so no link could be priced: make every snapshot stale
    so the next page that shows it asks Shopping again and re-reads the pack."""
    apps.get_model('recipes', 'ShoppingLink').objects.update(refreshed_at=None)


class Migration(migrations.Migration):
    dependencies = [('recipes', '0015_editable_categories')]
    operations = [migrations.RunPython(stale, migrations.RunPython.noop)]
