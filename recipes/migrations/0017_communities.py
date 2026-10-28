"""Communities (labauth, owned by Home): every row with an owner gets the community it belongs to, and names become
unique per community instead of per owner. Per-row sharing (shared_with) goes: a community is what is shared now.

Existing rows with an owner go to the first community, the one Home's bootstrap_labauth made from the existing accounts
(Home migrates the lab-auth database first: home-accounts runs before Nyochi). Rows without an owner stay global.
Names that would clash once several owners share one community get a " (2)" suffix; a category key that clashes keeps
the oldest row (ingredients refer to the key, so they keep working)."""

from collections import defaultdict


import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


MODELS = ["tag", "category", "ingredient", "shop", "shoplocation", "aisle", "aisleorder", "categoryaislemapping",
          "shoplink", "recipe", "savedgrocerylist", "savedgroceryitem", "recipeingredient"]


def first_community_id():
    from django.db import connections

    for alias in ("accounts", "default"):
        if alias not in connections:
            continue
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT id FROM labauth_community ORDER BY id LIMIT 1")
                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception:  # no lab-auth tables (a fresh database, the tests)
            continue
    return None


def fill(apps, schema_editor):
    cid = first_community_id()
    if cid is None:
        return
    db = schema_editor.connection.alias
    for name in MODELS:
        apps.get_model("recipes", name).objects.using(db).exclude(owner_id=None).update(community_id=cid)
    # names unique per community now: rename the later ones of a clash
    for name in ("tag", "ingredient", "shop", "category"):
        model = apps.get_model("recipes", name)
        seen = defaultdict(int)
        for row in model.objects.using(db).exclude(community_id=None).order_by("pk"):
            k = (row.community_id, row.name.lower())
            seen[k] += 1
            if seen[k] > 1:
                row.name = f"{row.name} ({seen[k]})"
                row.save(update_fields=["name"])
    Category = apps.get_model("recipes", "category")
    keys = set()
    for row in Category.objects.using(db).exclude(community_id=None).order_by("pk"):
        if (row.community_id, row.key) in keys:
            row.delete()
        else:
            keys.add((row.community_id, row.key))


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0016_recompute_pack_sizes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='category',
            name='category_key_per_owner',
        ),
        migrations.RemoveConstraint(
            model_name='category',
            name='category_name_per_owner',
        ),
        migrations.RemoveConstraint(
            model_name='ingredient',
            name='ingredient_name_per_owner',
        ),
        migrations.RemoveConstraint(
            model_name='shop',
            name='shop_name_per_owner',
        ),
        migrations.RemoveConstraint(
            model_name='tag',
            name='tag_name_per_owner',
        ),
        migrations.RemoveField(
            model_name='aisle',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='aisleorder',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='categoryaislemapping',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='recipe',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='recipeingredient',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='savedgroceryitem',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='savedgrocerylist',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='shoplink',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='shoplocation',
            name='shared_with',
        ),
        migrations.AddField(
            model_name='aisle',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='aisleorder',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='category',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='categoryaislemapping',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='ingredient',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='recipe',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='recipeingredient',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='savedgroceryitem',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='savedgrocerylist',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='shop',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='shoplink',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='shoplocation',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='tag',
            name='community_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(models.F('community_id'), models.F('key'), name='category_key_per_community'),
        ),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('name'), models.F('community_id'), name='category_name_per_community'),
        ),
        migrations.AddConstraint(
            model_name='ingredient',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('name'), models.F('community_id'), name='ingredient_name_per_community'),
        ),
        migrations.AddConstraint(
            model_name='shop',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('name'), models.F('community_id'), name='shop_name_per_community'),
        ),
        migrations.AddConstraint(
            model_name='tag',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('name'), models.F('community_id'), name='tag_name_per_community'),
        ),
        migrations.RemoveField(
            model_name='ingredient',
            name='shared_with',
        ),
        migrations.RemoveField(
            model_name='shop',
            name='shared_with',
        ),
    ]
