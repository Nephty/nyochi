from recipes.access import deletable, readable, writable
from recipes.models import Aisle, Ingredient, Recipe, SavedGroceryList, Shop, ShopLocation, Tag

from .base import HubTestCase


class AccessTests(HubTestCase):
    def setUp(self):
        self.tomato = self.make_ingredient('Tomato')
        self.recipe = self.make_recipe('Soup', [(self.tomato, 3, self.piece)])

    def test_private_by_default(self):
        self.assertFalse(readable(Recipe, self.bob).filter(pk=self.recipe.pk).exists())
        self.assertFalse(readable(Ingredient, self.bob).filter(pk=self.tomato.pk).exists())

    def test_account_with_a_high_id_can_own_and_share(self):
        # regression: these used to be real foreign keys to a table that isn't in this database
        self.recipe.shared_with.add(self.carol)
        self.assertTrue(readable(Recipe, self.carol).filter(pk=self.recipe.pk).exists())

    def test_sharing_a_recipe_lets_you_read_its_ingredients_but_not_edit_them(self):
        self.recipe.shared_with.add(self.bob)
        self.assertTrue(readable(Ingredient, self.bob).filter(pk=self.tomato.pk).exists())
        self.assertFalse(writable(Ingredient, self.bob).filter(pk=self.tomato.pk).exists())
        self.assertTrue(writable(Recipe, self.bob).filter(pk=self.recipe.pk).exists())

    def test_shared_user_cannot_delete_or_reshare(self):
        self.recipe.shared_with.add(self.bob)
        self.assertFalse(deletable(Recipe, self.bob).filter(pk=self.recipe.pk).exists())
        self.assertTrue(deletable(Recipe, self.alice).filter(pk=self.recipe.pk).exists())

    def test_ownerless_rows_are_read_by_all_changed_by_superusers_only(self):
        from django.contrib.auth import get_user_model
        plain = get_user_model().objects.create_user('plain', password='x', pk=60)
        tag = Tag.objects.create(name='seed')
        self.assertTrue(readable(Tag, plain).filter(pk=tag.pk).exists())
        self.assertFalse(writable(Tag, plain).filter(pk=tag.pk).exists())
        self.assertTrue(writable(Tag, self.alice).filter(pk=tag.pk).exists())

    def test_same_name_for_two_owners(self):
        Ingredient.objects.create(name='Tomato', owner=self.bob)   # no clash with alice's

    def test_children_follow_the_shop(self):
        shop = Shop.objects.create(name='Mart', owner=self.alice)
        loc = ShopLocation.objects.create(shop=shop, name='Main', owner=self.alice)
        from recipes.access import readable_locations
        self.assertFalse(readable_locations(self.bob).filter(pk=loc.pk).exists())
        shop.shared_with.add(self.bob)
        self.assertTrue(readable_locations(self.bob).filter(pk=loc.pk).exists())
