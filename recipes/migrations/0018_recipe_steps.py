from django.db import migrations, models


def method_to_steps(apps, schema_editor):
    """Each old Method text becomes preparation steps, one per line, so nothing written is lost."""
    from recipes.kitchen import split_method
    Recipe = apps.get_model('recipes', 'Recipe')
    for recipe in Recipe.objects.exclude(description=''):
        recipe.steps = split_method(recipe.description)
        recipe.save(update_fields=['steps'])


def steps_to_method(apps, schema_editor):
    Recipe = apps.get_model('recipes', 'Recipe')
    for recipe in Recipe.objects.all():
        recipe.description = '\n'.join(s['text'] for s in recipe.steps or [])
        recipe.save(update_fields=['description'])


class Migration(migrations.Migration):
    dependencies = [('recipes', '0017_communities')]

    operations = [
        migrations.AddField('recipe', 'steps', models.JSONField(blank=True, default=list)),
        migrations.AddField('recipe', 'tools', models.JSONField(blank=True, default=list)),
        migrations.AddField('recipe', 'kitchenware', models.JSONField(blank=True, default=list)),
        migrations.RunPython(method_to_steps, steps_to_method),
        migrations.RemoveField('recipe', 'description'),
    ]
