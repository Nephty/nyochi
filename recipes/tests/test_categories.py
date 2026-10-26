from django.urls import reverse

from recipes import categories, grocery
from recipes.models import (
    Aisle, AisleOrder, Category, CategoryAisleMapping, Ingredient, Shop, ShopLocation,
)

from .base import HubTestCase


class CategoryPageTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)

    def mine(self):
        return Category.objects.filter(owner_id=self.alice.pk)

    def test_defaults_are_created_on_first_visit_and_are_per_account(self):
        self.assertEqual(self.mine().count(), 0)
        r = self.client.get(reverse('category-list'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(self.mine().values_list('key', flat=True))[:3], ['vegetable', 'fruit', 'starch'])
        self.assertEqual(Category.objects.filter(owner_id=self.bob.pk).count(), 0)

    def test_add_rename_and_duplicates(self):
        self.client.get(reverse('category-list'))
        self.client.post(reverse('category-list'), {'name': 'Frozen food'})
        frozen = self.mine().get(name='Frozen food')
        self.assertEqual((frozen.key, frozen.position), ('frozen-food', 10))
        self.client.post(reverse('category-list'), {'name': 'frozen FOOD'})       # same name, other case
        self.assertEqual(self.mine().filter(name__iexact='frozen food').count(), 1)
        self.client.post(reverse('category-rename', args=[frozen.pk]), {'name': 'Freezer'})
        frozen.refresh_from_db()
        self.assertEqual((frozen.name, frozen.key), ('Freezer', 'frozen-food'))     # the key never changes
        self.client.post(reverse('category-rename', args=[frozen.pk]), {'name': 'Dairy'})
        frozen.refresh_from_db()
        self.assertEqual(frozen.name, 'Freezer')

    def test_reorder(self):
        self.client.get(reverse('category-list'))
        second = self.mine().get(key='fruit')
        self.client.post(reverse('category-move', args=[second.pk, 'up']))
        self.assertEqual(list(self.mine().values_list('key', flat=True))[:2], ['fruit', 'vegetable'])
        self.client.post(reverse('category-move', args=[second.pk, 'up']))          # already first: no-op
        self.assertEqual(self.client.post(reverse('category-move', args=[second.pk, 'sideways'])).status_code, 404)

    def test_delete_moves_ingredients_and_forgets_layout_mappings(self):
        self.client.get(reverse('category-list'))
        fruit = self.mine().get(key='fruit')
        apple = self.make_ingredient('Apple', category='fruit')
        shop = Shop.objects.create(name='Mart', owner=self.alice)
        loc = ShopLocation.objects.create(shop=shop, name='Main', owner=self.alice)
        aisle = Aisle.objects.create(shop=shop, name='Veg', owner=self.alice)
        CategoryAisleMapping.objects.create(location=loc, category='fruit', aisle=aisle)
        # asking to delete without saying where the ingredients go is refused
        self.client.post(reverse('category-delete', args=[fruit.pk]), {})
        self.assertTrue(self.mine().filter(key='fruit').exists())
        self.client.post(reverse('category-delete', args=[fruit.pk]), {'move_to': 'vegetable'})
        apple.refresh_from_db()
        self.assertEqual(apple.category, 'vegetable')
        self.assertFalse(self.mine().filter(key='fruit').exists())
        self.assertEqual(CategoryAisleMapping.objects.count(), 0)
        self.assertEqual(list(self.mine().values_list('position', flat=True)), list(range(9)))

    def test_cannot_delete_the_last_category_or_someone_elses(self):
        self.client.get(reverse('category-list'))
        self.mine().exclude(key='other').delete()
        only = self.mine().get()
        self.client.post(reverse('category-delete', args=[only.pk]), {})
        self.assertEqual(self.mine().count(), 1)
        theirs = Category.objects.create(owner_id=self.bob.pk, key='x', name='X')
        self.assertEqual(self.client.post(reverse('category-delete', args=[theirs.pk]), {}).status_code, 404)
        self.assertEqual(self.client.post(reverse('category-rename', args=[theirs.pk]), {'name': 'Y'}).status_code, 404)


class CategoryUseTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        self.client.get(reverse('category-list'))
        Category.objects.create(owner_id=self.alice.pk, key='frozen', name='Frozen', position=0)
        Category.objects.filter(owner_id=self.alice.pk).exclude(key='frozen').update(position=5)

    def test_ingredient_form_offers_and_accepts_custom_categories(self):
        r = self.client.get(reverse('ingredient-create'))
        self.assertContains(r, '<option value="frozen">Frozen</option>', html=True)
        r = self.client.post(reverse('ingredient-create'), {
            'name': 'Peas', 'category': 'frozen', **{f'season_{m}': 'out' for m in range(1, 13)}})
        self.assertEqual(Ingredient.objects.get(name='Peas').category, 'frozen')
        r = self.client.post(reverse('ingredient-create'), {
            'name': 'Corn', 'category': 'made-up', **{f'season_{m}': 'out' for m in range(1, 13)}})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Ingredient.objects.filter(name='Corn').exists())

    def test_ingredient_list_groups_by_your_order_and_names(self):
        self.make_ingredient('Peas', category='frozen')
        self.make_ingredient('Apple', category='fruit')
        r = self.client.get(reverse('ingredient-list'))
        body = r.content.decode()
        self.assertLess(body.index('Frozen</h2>'), body.index('Fruit</h2>'))

    def test_receipt_uses_your_names_and_order(self):
        peas = self.make_ingredient('Peas', category='frozen')
        milk = self.make_ingredient('Milk', category='dairy')
        r = self.make_recipe('R', [(peas, 100, self.gram), (milk, 100, self.gram)])
        data = grocery.receipt(grocery.merge_recipes([(r, 1)]), None, self.alice)
        self.assertEqual([s['title'] for s in data['sections']], ['Frozen', 'Dairy'])

    def test_layout_editor_lists_and_accepts_custom_categories(self):
        shop = Shop.objects.create(name='Mart', owner=self.alice)
        loc = ShopLocation.objects.create(shop=shop, name='Main', owner=self.alice)
        aisle = Aisle.objects.create(shop=shop, name='Cold', owner=self.alice)
        r = self.client.get(reverse('shop-detail', args=[shop.pk]))
        self.assertContains(r, '"label": "Frozen"')
        r = self.post_json(reverse('location-layout', args=[loc.pk]),
                           {'route': [aisle.pk], 'mappings': {'frozen': aisle.pk}, 'overrides': []})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(CategoryAisleMapping.objects.filter(location=loc, category='frozen').exists())

    def test_unknown_keys_are_prettified_not_hidden(self):
        self.assertEqual(categories.label_of('some-key', {}), 'Some key')
        self.assertEqual(categories.label_of('dairy', {}), 'Dairy')
