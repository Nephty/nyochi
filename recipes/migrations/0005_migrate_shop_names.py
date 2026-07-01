from django.db import migrations


def migrate_shop_names(apps, schema_editor):
    ShopLink = apps.get_model('recipes', 'ShopLink')
    Shop = apps.get_model('recipes', 'Shop')
    for link in ShopLink.objects.filter(shop__isnull=True):
        shop, _ = Shop.objects.get_or_create(name=link.shop_name)
        link.shop = shop
        link.save(update_fields=['shop'])


class Migration(migrations.Migration):
    dependencies = [('recipes', '0004_shops_aisles')]
    operations = [migrations.RunPython(migrate_shop_names, migrations.RunPython.noop)]
