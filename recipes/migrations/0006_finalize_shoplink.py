from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('recipes', '0005_migrate_shop_names')]

    operations = [
        migrations.AlterField(
            model_name='shoplink',
            name='shop',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='recipes.shop'),
        ),
        migrations.RemoveField(model_name='shoplink', name='shop_name'),
        migrations.AlterModelOptions(
            name='shoplink',
            options={'ordering': ['shop__name']},
        ),
        migrations.AlterUniqueTogether(
            name='shoplink',
            unique_together={('ingredient', 'shop')},
        ),
    ]
