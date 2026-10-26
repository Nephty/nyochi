"""Who can see / change / delete what.

Four kinds of rows:
  * top-level objects (Recipe, Ingredient, Shop, SavedGroceryList, Tag) have an owner and a shared_with list;
  * their children (RecipeIngredient, ShopLocation, Aisle, mappings, orders, list items, links...) have no access of
    their own: they follow their parent, so sharing a shop shares its locations and layout, with no copying;
  * an ingredient or tag is also readable (not editable) when a recipe / list you can read uses it;
  * rows without an owner are everyone's to read, a superuser's to change.

auth_user lives in the hub's database, so nothing here joins to it: shared_with is read through the
M2M table's user_id column only.
"""
from django.db.models import Q

from .models import (
    Aisle, Ingredient, Recipe, RecipeIngredient, SavedGroceryItem, SavedGroceryList, Shop, ShopLocation, Tag,
)


def _shared_ids(model, user):
    through = model.shared_with.through
    return through.objects.filter(user_id=user.pk).values(f'{model._meta.model_name}_id')


def readable(model, user):
    """Rows of a top-level model that `user` may see."""
    q = Q(owner_id=user.pk) | Q(owner__isnull=True)
    if hasattr(model, 'shared_with'):
        q |= Q(pk__in=_shared_ids(model, user))
    if model is Ingredient:
        recipes = readable(Recipe, user).values('pk')
        lists = readable(SavedGroceryList, user).values('pk')
        q |= Q(pk__in=RecipeIngredient.objects.filter(recipe__in=recipes).values('ingredient'))
        q |= Q(pk__in=SavedGroceryItem.objects.filter(grocery_list__in=lists).values('ingredient'))
    elif model is Tag:
        q |= Q(pk__in=Recipe.tags.through.objects.filter(
            recipe__in=readable(Recipe, user).values('pk')).values('tag'))
    return model.objects.filter(q)


def writable(model, user):
    """Rows `user` may edit: their own, shared with them, and (superusers) the ownerless ones."""
    q = Q(owner_id=user.pk)
    if hasattr(model, 'shared_with'):
        q |= Q(pk__in=_shared_ids(model, user))
    if user.is_superuser:
        q |= Q(owner__isnull=True)
    return model.objects.filter(q)


def deletable(model, user):
    """Rows `user` may delete or share: only the owner (a superuser for ownerless rows)."""
    q = Q(owner_id=user.pk)
    if user.is_superuser:
        q |= Q(owner__isnull=True)
    return model.objects.filter(q)


def is_owner(obj, user):
    return obj.owner_id == user.pk or (obj.owner_id is None and user.is_superuser)


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
