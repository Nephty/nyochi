"""The community a request acts in (labauth), for the models and access rules.

Every row with an owner also has a `community_id`: the labauth Community it was made in (an id in the lab-auth
database; no FK, it is another SQLite file). Everything in Nyochi belongs to its community: every member who may open
Nyochi reads it, and the matching `nyochi.*.edit` permission changes and deletes it (recipes/access.py).

CommunityMiddleware (after labauth's) puts the active community on `request.user` (`lab_community_id`, `lab_perms`), so
the access rules keep taking just a user, and into a context variable, so a row saved during the request gets its
community without every view passing it on. Outside a request (tests, commands) a new row takes its owner's first
community.
"""

from contextvars import ContextVar

from django.db.models.signals import pre_save

current = ContextVar("nyochi_community", default=None)

# The permission that changes (and deletes) each kind of row.
EDIT_PERM = {
    "recipe": "nyochi.recipes.edit", "tag": "nyochi.recipes.edit",
    "ingredient": "nyochi.ingredients.edit", "category": "nyochi.ingredients.edit",
    "shop": "nyochi.shops.edit",
    "savedgrocerylist": "nyochi.lists.edit",
}


def community_of(user):
    """The active community id of a user (set by the middleware), else their first membership's (tests, commands)."""
    cid = getattr(user, "lab_community_id", None)
    if cid is None and getattr(user, "pk", None):
        from labauth.models import Membership

        cid = Membership.objects.filter(user_id=user.pk).order_by("joined_at", "pk").values_list("community_id", flat=True).first()
        user.lab_community_id = cid
    return cid


def perms_of(user):
    perms = getattr(user, "lab_perms", None)
    if perms is None:
        from labauth import access
        from labauth.models import Community

        cid = community_of(user)
        perms = access.community_perms(user, Community.objects.filter(pk=cid).first()) if cid else set()
        user.lab_perms = perms
    return perms


def can_edit(user, model):
    return EDIT_PERM.get(model._meta.model_name) in perms_of(user)


class CommunityMiddleware:
    """After labauth's CommunityMiddleware / AppAccessMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = None
        if request.user.is_authenticated and hasattr(request, "lab_community"):
            community = request.lab_community()
            request.user.lab_community_id = community.pk if community else None
            request.user.lab_perms = request.lab_perms()
            token = current.set(request.user.lab_community_id)
        try:
            return self.get_response(request)
        finally:
            if token is not None:
                current.reset(token)


def fill_community(sender, instance, **kwargs):
    """A new row with an owner gets the request's community (else its owner's first one); a child row gets its
    parent's when it has one."""
    if getattr(instance, "community_id", "missing") is not None or not hasattr(instance, "owner_id"):
        return
    for parent in ("recipe", "shop", "grocery_list", "location", "aisle", "ingredient"):
        field = next((f for f in instance._meta.fields if f.name == parent), None)
        if field is not None and getattr(instance, f"{parent}_id", None):
            cid = getattr(getattr(instance, parent), "community_id", None)
            if cid:
                instance.community_id = cid
                return
    cid = current.get()
    if cid is None and instance.owner_id:
        from labauth.models import Membership

        cid = Membership.objects.filter(user_id=instance.owner_id).order_by("joined_at", "pk").values_list("community_id", flat=True).first()
    instance.community_id = cid


def connect():
    pre_save.connect(fill_community, dispatch_uid="nyochi-fill-community")
