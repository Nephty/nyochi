"""Nyochi's meal calendar got its own permission (nyochi.meals.edit). Whoever could edit Nyochi's lists gets it too:
the community defaults and the members' own overrides (allow or deny) are copied from nyochi.lists.edit."""

from django.db import migrations

OLD, NEW = "nyochi.lists.edit", "nyochi.meals.edit"


def copy_grants(apps, schema_editor):
    CommunityGrant = apps.get_model("labauth", "CommunityGrant")
    MemberGrant = apps.get_model("labauth", "MemberGrant")
    for g in CommunityGrant.objects.filter(perm=OLD):
        CommunityGrant.objects.get_or_create(community_id=g.community_id, perm=NEW)
    for g in MemberGrant.objects.filter(perm=OLD):
        MemberGrant.objects.get_or_create(membership_id=g.membership_id, perm=NEW, defaults={"allow": g.allow})


def drop_grants(apps, schema_editor):
    apps.get_model("labauth", "CommunityGrant").objects.filter(perm=NEW).delete()
    apps.get_model("labauth", "MemberGrant").objects.filter(perm=NEW).delete()


class Migration(migrations.Migration):
    dependencies = [("labauth", "0001_initial")]
    operations = [migrations.RunPython(copy_grants, drop_grants)]
