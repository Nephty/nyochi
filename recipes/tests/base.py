import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from labauth.catalogue import COMMUNITY_PERMS
from labauth.models import Community, CommunityGrant, MemberGrant, Membership

from recipes.models import Ingredient, Recipe, RecipeIngredient, SeasonalAvailability, Unit

User = get_user_model()


def community(name, perms=COMMUNITY_PERMS):
    c = Community.objects.create(name=name, slug=name.lower())
    CommunityGrant.objects.bulk_create(CommunityGrant(community=c, perm=p) for p in perms)
    return c


def join(user, c, deny=(), role=Membership.MEMBER):
    """Put `user` in community `c`, without the permissions in `deny`."""
    m, _ = Membership.objects.get_or_create(user=user, community=c, defaults={'role': role})
    for perm in deny:
        MemberGrant.objects.update_or_create(membership=m, perm=perm, defaults={'allow': False})
    return user


class HubTestCase(TestCase):
    """Users, sessions and labauth live in the 'accounts' database (Home's); everything else in 'default'.
    alice, bob and carol (superusers: every permission) each have their own community, A, B and C, so by default they
    don't see each other's rows; join() puts someone in another community."""
    databases = {'default', 'accounts'}

    @classmethod
    def setUpTestData(cls):
        # ids well above anything the app's own database ever had: an account need not exist locally
        cls.alice = User.objects.create_user('alice', password='x', is_superuser=True, pk=41)
        cls.bob = User.objects.create_user('bob', password='x', is_superuser=True, pk=42)
        cls.carol = User.objects.create_user('carol', password='x', is_superuser=True, pk=43)
        cls.a, cls.b, cls.c = community('A'), community('B'), community('C')
        join(cls.alice, cls.a)
        join(cls.bob, cls.b)
        join(cls.carol, cls.c)
        cls.gram = Unit.objects.get(abbreviation='g')
        cls.kilo = Unit.objects.get(abbreviation='kg')
        cls.tsp = Unit.objects.get(abbreviation='tsp')
        cls.piece = Unit.objects.get(abbreviation='pc')
        cls.clove = Unit.objects.get(abbreviation='clove')

    def login(self, user):
        self.client.force_login(user)

    def post_json(self, url, data, **kw):
        return self.client.post(url, json.dumps(data), content_type='application/json',
                                headers={'Accept': 'application/json'}, **kw)

    def get_json(self, url, **kw):
        return self.client.get(url, headers={'Accept': 'application/json'}, **kw)

    def make_ingredient(self, name, owner=None, category='other', seasons=None):
        ing = Ingredient.objects.create(name=name, category=category, owner=owner or self.alice)
        for m in range(1, 13):
            SeasonalAvailability.objects.create(ingredient=ing, month=m, status=(seasons or {}).get(m, 'out'))
        return ing

    def make_recipe(self, name, rows, owner=None, **kw):
        """rows: [(ingredient, quantity, unit, is_main)]"""
        r = Recipe.objects.create(name=name, prep_time=kw.pop('prep', 10), cook_time=kw.pop('cook', 20),
                                  owner=owner or self.alice, **kw)
        for ing, qty, unit, *main in rows:
            RecipeIngredient.objects.create(recipe=r, ingredient=ing, quantity=Decimal(str(qty)), unit=unit,
                                            is_main=bool(main and main[0]), owner=r.owner)
        return r
