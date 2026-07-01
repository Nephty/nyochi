from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('recipes', '0003_add_absolute_unit')]

    operations = [
        migrations.CreateModel(
            name='Shop',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='ShopLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='locations', to='recipes.shop')),
            ],
            options={'ordering': ['shop', 'name'], 'unique_together': {('shop', 'name')}},
        ),
        migrations.CreateModel(
            name='Aisle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aisles', to='recipes.shop')),
            ],
            options={'ordering': ['shop', 'name'], 'unique_together': {('shop', 'name')}},
        ),
        migrations.CreateModel(
            name='AisleOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField()),
                ('aisle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='location_orders', to='recipes.aisle')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aisle_orders', to='recipes.shoplocation')),
            ],
            options={'ordering': ['location', 'order'], 'unique_together': {('aisle', 'location')}},
        ),
        migrations.CreateModel(
            name='CategoryAisleMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=20, choices=[
                    ('vegetable', 'Vegetable'), ('fruit', 'Fruit'), ('starch', 'Starch'),
                    ('meat', 'Meat'), ('dairy', 'Dairy'), ('legume', 'Legume'),
                    ('fish', 'Fish & Seafood'), ('spice', 'Spice & Herb'),
                    ('oil', 'Oil & Fat'), ('other', 'Other'),
                ])),
                ('aisle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='category_mappings', to='recipes.aisle')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='category_mappings', to='recipes.shoplocation')),
            ],
            options={'unique_together': {('location', 'category')}},
        ),
        # Add nullable shop FK to ShopLink (populated in next migration)
        migrations.AddField(
            model_name='shoplink',
            name='shop',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='recipes.shop'),
        ),
    ]
