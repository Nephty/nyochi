"""Ingredient categories: a list per account (add, rename, reorder, delete in the UI).

Ingredients and shop layouts store the category's stable `key`; the name is only for display. Every account starts with the
ten defaults, created the first time its list is needed. A key we don't know (an ingredient shared by someone who has a
category you don't) is shown prettified rather than hidden."""
from collections import OrderedDict

from django.db import transaction
from django.utils.text import slugify

from .models import Category, IngredientCategory

DEFAULT_LABELS = OrderedDict(IngredientCategory.choices)


def pretty(key: str) -> str:
    return (key or 'other').replace('-', ' ').replace('_', ' ').strip().capitalize() or 'Other'


def user_categories(user):
    """The account's categories in order, seeding the defaults the first time."""
    rows = list(Category.objects.filter(owner_id=user.pk))
    if not rows:
        Category.objects.bulk_create(
            [Category(owner_id=user.pk, key=k, name=n, position=i) for i, (k, n) in enumerate(DEFAULT_LABELS.items())],
            ignore_conflicts=True,
        )
        rows = list(Category.objects.filter(owner_id=user.pk))
    return rows


def user_labels(user) -> OrderedDict:
    """{key: name} in the account's order."""
    return OrderedDict((c.key, c.name) for c in user_categories(user))


def labels_for(user, owner_id=None) -> OrderedDict:
    """The viewer's categories, plus those of another account (the owner of a shared shop) that the viewer lacks."""
    labels = user_labels(user)
    if owner_id and owner_id != user.pk:
        for c in Category.objects.filter(owner_id=owner_id):
            labels.setdefault(c.key, c.name)
    return labels


def label_of(key, labels) -> str:
    return labels.get(key) or DEFAULT_LABELS.get(key) or pretty(key)


def default_key(labels) -> str:
    return 'other' if 'other' in labels else next(iter(labels), 'other')


def new_key(user, name: str) -> str:
    base = slugify(name)[:34] or 'category'
    taken = set(Category.objects.filter(owner_id=user.pk).values_list('key', flat=True))
    key, n = base, 2
    while key in taken:
        key = f'{base}-{n}'
        n += 1
    return key


@transaction.atomic
def renumber(user):
    for i, c in enumerate(Category.objects.filter(owner_id=user.pk)):
        if c.position != i:
            c.position = i
            c.save(update_fields=['position'])
