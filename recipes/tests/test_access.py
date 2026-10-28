from django.contrib.auth import get_user_model

from recipes.access import deletable, readable, readable_locations, writable
from recipes.models import Ingredient, Recipe, Shop, ShopLocation, Tag

from .base import HubTestCase, join

User = get_user_model()


class AccessTests(HubTestCase):
    def setUp(self):
        self.tomato = self.make_ingredient('Tomato')
        self.recipe = self.make_recipe('Soup', [(self.tomato, 3, self.piece)])

    def plain(self, deny=(), pk=60):
        return join(User.objects.create_user(f'plain{pk}', password='x', pk=pk), self.a, deny=deny)

    def test_other_communities_do_not_see_it(self):
        self.assertFalse(readable(Recipe, self.bob).filter(pk=self.recipe.pk).exists())
        self.assertFalse(readable(Ingredient, self.bob).filter(pk=self.tomato.pk).exists())

    def test_rows_take_their_owners_community(self):
        self.assertEqual((self.recipe.community_id, self.tomato.community_id), (self.a.pk, self.a.pk))
        self.assertEqual(self.recipe.recipeingredient_set.get().community_id, self.a.pk)  # a child: its parent's

    def test_members_read_and_edit_with_the_permission(self):
        member = self.plain()
        self.assertTrue(readable(Recipe, member).filter(pk=self.recipe.pk).exists())
        self.assertTrue(writable(Recipe, member).filter(pk=self.recipe.pk).exists())
        self.assertTrue(deletable(Recipe, member).filter(pk=self.recipe.pk).exists())

    def test_each_kind_has_its_permission(self):
        member = self.plain(deny=['nyochi.recipes.edit'])
        self.assertTrue(readable(Recipe, member).filter(pk=self.recipe.pk).exists())
        self.assertFalse(writable(Recipe, member).filter(pk=self.recipe.pk).exists())
        self.assertTrue(writable(Ingredient, member).filter(pk=self.tomato.pk).exists())

    def test_global_rows_are_read_by_all_changed_by_superusers_only(self):
        member = self.plain()
        tag = Tag.objects.create(name='seed')  # no owner: global
        self.assertIsNone(tag.community_id)
        self.assertTrue(readable(Tag, member).filter(pk=tag.pk).exists())
        self.assertFalse(writable(Tag, member).filter(pk=tag.pk).exists())
        self.assertTrue(writable(Tag, self.alice).filter(pk=tag.pk).exists())

    def test_same_name_in_two_communities(self):
        Ingredient.objects.create(name='Tomato', owner=self.bob)   # B: no clash with A's

    def test_children_follow_the_shop(self):
        shop = Shop.objects.create(name='Mart', owner=self.alice)
        loc = ShopLocation.objects.create(shop=shop, name='Main', owner=self.alice)
        self.assertFalse(readable_locations(self.bob).filter(pk=loc.pk).exists())
        self.assertTrue(readable_locations(self.plain()).filter(pk=loc.pk).exists())
