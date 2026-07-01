from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('recipes', '0006_finalize_shoplink')]

    operations = [
        migrations.AddField(
            model_name='recipe',
            name='difficulty',
            field=models.CharField(
                max_length=15,
                choices=[('easy', 'Easy'), ('intermediate', 'Intermediate'),
                         ('difficult', 'Difficult'), ('pro', 'Pro')],
                default='easy',
            ),
        ),
    ]
