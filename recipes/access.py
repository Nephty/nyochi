"""Who can see / change / delete what: the community decides (labauth, recipes/community.py).

Three kinds of rows:
  * top-level objects (Recipe, Ingredient, Shop, SavedGroceryList, Tag, Category) belong to a community: every member
    who may open Nyochi reads them, the matching `nyochi.*.edit` permission changes and deletes them;
  * their children (RecipeIngredient, ShopLocation, Aisle, mappings, orders, list items, links...) have no access of
    their own: they follow their parent;
  * rows without a community (seeded ones) are everyone's to read, a superuser's to change.

`user` is request.user, which carries the active community (`lab_community_id`) and its permissions (`lab_perms`).
The owner of a row is only who made it; it gives no rights.
"""
from django.db.models import Q

from .community import can_edit, community_of
from .models import Aisle, SavedGroceryItem, SavedGroceryList, Shop, ShopLocation


def readable(model, user):
    """Rows of a top-level model that `user` may see: their community's, and the global ones."""
    return model.objects.filter(Q(community_id=community_of(user)) | Q(community_id__isnull=True))


def writable(model, user):
    """Rows `user` may edit (and delete): their community's, with the permission for that kind; superusers also the
    global ones."""
    q = Q(community_id=community_of(user)) if can_edit(user, model) else Q(pk__in=[])
    if user.is_superuser:
        q |= Q(community_id__isnull=True)
    return model.objects.filter(q)


deletable = writable


def is_owner(obj, user):
    """May `user` change this row? (The templates call it `mine`: they show the edit / delete buttons.)"""
    if obj.community_id is None:
        return user.is_superuser
    return obj.community_id == community_of(user) and can_edit(user, type(obj))


# children, through their parent -------------------------------------------------------------

def readable_locations(user):
    return ShopLocation.objects.filter(shop__in=readable(Shop, user).values('pk'))


def readable_aisles(user):
    return Aisle.objects.filter(shop__in=readable(Shop, user).values('pk'))


def writable_locations(user):
    return ShopLocation.objects.filter(shop__in=writable(Shop, user).values('pk'))


def readable_items(user):
    return SavedGroceryItem.objects.filter(grocery_list__in=readable(SavedGroceryList, user).values('pk'))


def writable_items(user):
    return SavedGroceryItem.objects.filter(grocery_list__in=writable(SavedGroceryList, user).values('pk'))
