# The meal calendar (meals/models.py).

import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('recipes', '0019_list_covers'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Meal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField(db_index=True)),
                ('slot', models.CharField(choices=[('breakfast', 'Breakfast'), ('lunch', 'Lunch'), ('snack', 'Snack'), ('dinner', 'Dinner')], default='dinner', max_length=10)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('title', models.CharField(blank=True, max_length=200)),
                ('mult', models.DecimalField(decimal_places=2, default=Decimal('1'), max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0.25')), django.core.validators.MaxValueValidator(Decimal('20'))])),
                ('note', models.CharField(blank=True, max_length=200)),
                ('cooked_at', models.DateTimeField(blank=True, null=True)),
                ('community_id', models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('leftover_of', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='leftovers', to='meals.meal')),
                ('owner', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('recipe', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='meals', to='recipes.recipe')),
            ],
            options={
                'ordering': ['day', 'slot', 'position', 'pk'],
                'indexes': [models.Index(fields=['community_id', 'day'], name='meals_meal_communi_6171c0_idx')],
            },
        ),
    ]
