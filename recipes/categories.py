"""Ingredient categories: a list per community (add, rename, reorder, delete in the UI).

Ingredients and shop layouts store the category's stable `key`; the name is only for display. Every community starts with
the ten defaults, created the first time its list is needed. A key we don't know (a row made before a category was
deleted) is shown prettified rather than hidden. `user` is request.user, which carries the active community."""
from collections import OrderedDict

from django.db import transaction
from django.utils.text import slugify

from .community import community_of
from .models import Category, IngredientCategory

DEFAULT_LABELS = OrderedDict(IngredientCategory.choices)


def pretty(key: str) -> str:
    return (key or 'other').replace('-', ' ').replace('_', ' ').strip().capitalize() or 'Other'


def user_categories(user):
    """The community's categories in order, seeding the defaults the first time."""
    cid = community_of(user)
    rows = list(Category.objects.filter(community_id=cid))
    if not rows and cid is not None:
        Category.objects.bulk_create(
            [Category(owner_id=user.pk, community_id=cid, key=k, name=n, position=i) for i, (k, n) in enumerate(DEFAULT_LABELS.items())],
            ignore_conflicts=True,
        )
        rows = list(Category.objects.filter(community_id=cid))
    return rows


def user_labels(user) -> OrderedDict:
    """{key: name} in the community's order."""
    return OrderedDict((c.key, c.name) for c in user_categories(user))


def labels_for(user, owner_id=None) -> OrderedDict:
    """The community's categories (`owner_id` is left from when shops could be shared across accounts)."""
    return user_labels(user)


def label_of(key, labels) -> str:
    return labels.get(key) or DEFAULT_LABELS.get(key) or pretty(key)


def default_key(labels) -> str:
    return 'other' if 'other' in labels else next(iter(labels), 'other')


def new_key(user, name: str) -> str:
    base = slugify(name)[:34] or 'category'
    taken = set(Category.objects.filter(community_id=community_of(user)).values_list('key', flat=True))
    key, n = base, 2
    while key in taken:
        key = f'{base}-{n}'
        n += 1
    return key


@transaction.atomic
def renumber(user):
    for i, c in enumerate(Category.objects.filter(community_id=community_of(user))):
        if c.position != i:
            c.position = i
            c.save(update_fields=['position'])
