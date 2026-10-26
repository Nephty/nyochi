from django.contrib.auth import get_user_model
from django.urls import reverse

from recipes.models import (
    Aisle, AisleOrder, CategoryAisleMapping, IngredientAisle, Recipe, SavedGroceryItem, SavedGroceryList, Shop,
    ShopLocation,
)

from .base import HubTestCase

User = get_user_model()


def formset(rows, prefix='ing', initial=0):
    data = {f'{prefix}-TOTAL_FORMS': len(rows), f'{prefix}-INITIAL_FORMS': initial,
            f'{prefix}-MIN_NUM_FORMS': 1, f'{prefix}-MAX_NUM_FORMS': 1000}
    for i, (ing, qty, unit, *main) in enumerate(rows):
        data[f'{prefix}-{i}-ingredient'] = ing.pk
        data[f'{prefix}-{i}-quantity'] = qty
        data[f'{prefix}-{i}-unit'] = unit.pk
        if main and main[0]:
            data[f'{prefix}-{i}-is_main'] = 'on'
    return data


class RecipeViewTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        self.tomato = self.make_ingredient('Tomato')
        self.basil = self.make_ingredient('Basil')

    def recipe_post(self, rows, **extra):
        return {'name': 'Soup', 'meal_type': 'full_meal', 'difficulty': 'easy', 'prep_time': 5, 'cook_time': 10,
                'description': '', 'new_tags': 'Quick, Winter', **formset(rows), **extra}

    def test_create_with_ingredients_and_new_tags(self):
        r = self.client.post(reverse('recipe-create'), self.recipe_post([(self.tomato, '3', self.piece, True)]))
        recipe = Recipe.objects.get(name='Soup')
        self.assertRedirects(r, reverse('recipe-detail', args=[recipe.pk]))
        self.assertEqual(recipe.owner_id, self.alice.pk)
        self.assertEqual(sorted(t.name for t in recipe.tags.all()), ['Quick', 'Winter'])
        (ri,) = recipe.recipeingredient_set.all()
        self.assertTrue(ri.is_main)

    def test_duplicate_ingredient_shows_an_error_and_saves_nothing(self):
        r = self.client.post(reverse('recipe-create'),
                             self.recipe_post([(self.tomato, '1', self.piece), (self.tomato, '2', self.piece)]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Recipe.objects.filter(name='Soup').exists())
        self.assertContains(r, 'Please correct the duplicate data')

    def test_at_least_one_ingredient(self):
        r = self.client.post(reverse('recipe-create'), self.recipe_post([]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Recipe.objects.filter(name='Soup').exists())

    def test_zero_quantity_refused(self):
        r = self.client.post(reverse('recipe-create'), self.recipe_post([(self.tomato, '0', self.piece)]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Recipe.objects.filter(name='Soup').exists())

    def test_editing_replaces_rows(self):
        recipe = self.make_recipe('Soup', [(self.tomato, 3, self.piece)])
        ri = recipe.recipeingredient_set.get()
        data = {'name': 'Soup', 'meal_type': 'full_meal', 'difficulty': 'easy', 'prep_time': 5, 'cook_time': 10,
                'description': '', **formset([(self.tomato, '4', self.piece), (self.basil, '1', self.piece)], initial=1)}
        data['ing-0-id'] = ri.pk
        data['ing-0-recipe'] = recipe.pk
        r = self.client.post(reverse('recipe-update', args=[recipe.pk]), data)
        self.assertRedirects(r, reverse('recipe-detail', args=[recipe.pk]))
        self.assertEqual(recipe.recipeingredient_set.count(), 2)

    def test_pages_render(self):
        recipe = self.make_recipe('Soup', [(self.tomato, 3, self.piece, True)])
        for name, args in [('recipe-list', []), ('recipe-detail', [recipe.pk]), ('recipe-update', [recipe.pk]),
                           ('recipe-create', []), ('plan', []), ('shop-list', []), ('tag-list', []),
                           ('saved-grocery-list', [])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_shared_user_edits_but_cannot_delete(self):
        recipe = self.make_recipe('Soup', [(self.tomato, 3, self.piece)])
        recipe.shared_with.add(self.bob)
        self.login(self.bob)
        self.assertEqual(self.client.get(reverse('recipe-update', args=[recipe.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('recipe-delete', args=[recipe.pk])).status_code, 404)
        self.assertTrue(Recipe.objects.filter(pk=recipe.pk).exists())
        self.login(self.alice)
        self.client.post(reverse('recipe-delete', args=[recipe.pk]))
        self.assertFalse(Recipe.objects.filter(pk=recipe.pk).exists())

    def test_stranger_gets_404(self):
        recipe = self.make_recipe('Soup', [(self.tomato, 3, self.piece)])
        self.login(self.bob)
        self.assertEqual(self.client.get(reverse('recipe-detail', args=[recipe.pk])).status_code, 404)

    def test_old_urls_redirect(self):
        self.assertEqual(self.client.get('/selector/').status_code, 301)
        self.assertEqual(self.client.get('/grocery/').status_code, 301)


class ShareApiTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        self.recipe = self.make_recipe('Soup', [(self.make_ingredient('Tomato'), 3, self.piece)])
        self.url = reverse('share-object', args=['recipe', self.recipe.pk])

    def test_add_list_and_remove(self):
        r = self.post_json(self.url, {'add_username': 'Bob'})
        self.assertEqual([u['username'] for u in r.json()['users']], ['bob'])
        self.assertEqual(self.get_json(self.url).json()['users'][0]['id'], self.bob.pk)
        r = self.post_json(self.url, {'remove_user_id': self.bob.pk})
        self.assertEqual(r.json()['users'], [])

    def test_errors(self):
        self.assertEqual(self.post_json(self.url, {'add_username': 'nobody'}).status_code, 404)
        self.assertEqual(self.post_json(self.url, {'add_username': 'alice'}).status_code, 400)
        self.assertEqual(self.post_json(self.url, {'remove_user_id': 'x'}).status_code, 400)
        self.assertEqual(self.client.post(self.url, 'not json', content_type='application/json').status_code, 400)

    def test_only_the_owner_can_share(self):
        self.recipe.shared_with.add(self.bob)
        self.login(self.bob)
        self.assertEqual(self.post_json(self.url, {'add_username': 'carol'}).status_code, 404)


class LoginTests(HubTestCase):
    def test_signed_out_json_gets_a_login_link(self):
        r = self.get_json(reverse('plan-receipt'))
        self.assertEqual(r.status_code, 403)
        self.assertIn('/login/', r.json()['login'])

    def test_signed_out_page_redirects_to_the_login_with_next(self):
        r = self.client.get('/plan/?recipe=1')
        self.assertRedirects(r, '/login/?next=/plan/%3Frecipe%3D1', fetch_redirect_response=False)

    def test_login_page_is_open_and_signs_in_then_out(self):
        self.assertEqual(self.client.get('/login/').status_code, 200)
        r = self.client.post('/login/', {'username': 'alice', 'password': 'x', 'next': '/plan/'})
        self.assertRedirects(r, '/plan/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.client.post('/logout/')
        self.assertEqual(self.client.get('/').status_code, 302)

    def test_wrong_password_and_throttle(self):
        for _ in range(5):
            r = self.client.post('/login/', {'username': 'alice', 'password': 'nope'})
            self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Wrong username or password')
        r = self.client.post('/login/', {'username': 'alice', 'password': 'x'})
        self.assertEqual(r.status_code, 429)

    def test_any_account_may_use_the_app(self):
        user = User.objects.create_user('plain', password='x', pk=70)   # not staff, not superuser
        self.login(user)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_session_cookie_is_the_shared_one(self):
        from django.conf import settings
        self.client.post('/login/', {'username': 'alice', 'password': 'x'})
        self.assertIn(settings.SESSION_COOKIE_NAME, self.client.cookies)
        self.assertEqual(settings.SESSION_COOKIE_NAME, 'nyoshop_session')


class PlanAndListTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        self.flour = self.make_ingredient('Flour', category='starch')
        self.milk = self.make_ingredient('Milk', category='dairy')
        self.pancakes = self.make_recipe('Pancakes', [(self.flour, 250, self.gram), (self.milk, 400, self.gram)])
        self.bread = self.make_recipe('Bread', [(self.flour, 0.5, self.kilo)])

    def plan(self, **extra):
        return self.post_json(reverse('plan-receipt'), {'recipes': [
            {'id': self.pancakes.pk, 'mult': 1}, {'id': self.bread.pk, 'mult': 2}], **extra})

    def test_receipt_merges_and_scales(self):
        data = self.plan().json()
        lines = {l['name']: l for s in data['sections'] for l in s['lines']}
        self.assertEqual((lines['Flour']['amount'], lines['Flour']['unit']), (1.25, 'kg'))
        self.assertEqual(sorted(lines['Flour']['sources']), ['Bread', 'Pancakes'])
        self.assertEqual(data['totals']['lines'], 2)

    def test_receipt_validation(self):
        self.assertEqual(self.post_json(reverse('plan-receipt'), {'recipes': []}).status_code, 400)
        self.assertEqual(self.post_json(reverse('plan-receipt'),
                                        {'recipes': [{'id': self.bread.pk, 'mult': 500}]}).status_code, 400)
        self.assertEqual(self.post_json(reverse('plan-receipt'), {'recipes': [{'id': 99999, 'mult': 1}]}).status_code, 404)
        self.assertEqual(self.plan(location=99999).status_code, 404)

    def test_someone_elses_recipe_is_not_planned(self):
        theirs = self.make_recipe('Secret', [(self.make_ingredient('X', owner=self.bob), 1, self.gram)], owner=self.bob)
        r = self.post_json(reverse('plan-receipt'), {'recipes': [{'id': theirs.pk, 'mult': 1}]})
        self.assertEqual(r.status_code, 404)

    def test_save_then_use_the_list(self):
        made = self.post_json(reverse('plan-save'), {'recipes': [{'id': self.pancakes.pk, 'mult': 1}], 'name': 'Sunday'}).json()
        saved = SavedGroceryList.objects.get(pk=made['id'])
        self.assertEqual((saved.name, saved.owner_id, saved.items.count()), ('Sunday', self.alice.pk, 2))
        item = saved.items.first()
        r = self.post_json(reverse('list-check-item', args=[item.pk]), {'checked': True})
        self.assertEqual(r.json(), {'done': 1, 'total': 2})
        self.assertEqual(self.post_json(reverse('list-check-item', args=[item.pk]), {'checked': 'yes'}).status_code, 400)
        self.post_json(reverse('list-uncheck', args=[saved.pk]), {})
        self.assertEqual(saved.items.filter(in_cart=True).count(), 0)
        r = self.post_json(reverse('list-add-item', args=[saved.pk]), {'name': 'bin bags'})
        self.assertEqual(r.status_code, 201)
        extras = [s for s in r.json()['sections'] if s['kind'] == 'extras'][0]
        self.assertEqual(extras['lines'][0]['name'], 'bin bags')
        custom = saved.items.get(custom_name='bin bags')
        r = self.post_json(reverse('list-delete-item', args=[custom.pk]), {})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(saved.items.count(), 2)
        self.assertEqual(self.post_json(reverse('list-add-item', args=[saved.pk]), {'name': ' '}).status_code, 400)

    def test_adding_an_ingredient_merges_with_the_existing_line(self):
        saved = SavedGroceryList.objects.create(name='L', owner=self.alice)
        item = SavedGroceryItem.objects.create(grocery_list=saved, ingredient=self.flour, quantity=100, unit=self.gram)
        self.post_json(reverse('list-add-item', args=[saved.pk]),
                       {'ingredient_id': self.flour.pk, 'unit_id': self.gram.pk, 'quantity': 50})
        item.refresh_from_db()
        self.assertEqual(float(item.quantity), 150.0)

    def test_list_pages_and_actions(self):
        saved = SavedGroceryList.objects.create(name='L', owner=self.alice)
        SavedGroceryItem.objects.create(grocery_list=saved, ingredient=self.flour, quantity=100, unit=self.gram)
        self.assertEqual(self.client.get(reverse('saved-grocery-detail', args=[saved.pk])).status_code, 200)
        self.client.post(reverse('list-action', args=[saved.pk, 'rename']), {'name': 'Renamed'})
        self.client.post(reverse('list-action', args=[saved.pk, 'archive']))
        saved.refresh_from_db()
        self.assertEqual((saved.name, saved.archived), ('Renamed', True))
        self.assertNotContains(self.client.get(reverse('saved-grocery-list')), 'Renamed')
        self.assertContains(self.client.get(reverse('saved-grocery-list') + '?tab=archived'), 'Renamed')
        self.client.post(reverse('list-action', args=[saved.pk, 'unarchive']))
        saved.refresh_from_db()
        self.assertFalse(saved.archived)

    def test_shared_user_can_tick_but_not_delete(self):
        saved = SavedGroceryList.objects.create(name='L', owner=self.alice)
        item = SavedGroceryItem.objects.create(grocery_list=saved, ingredient=self.flour, quantity=100, unit=self.gram)
        self.login(self.bob)
        self.assertEqual(self.post_json(reverse('list-check-item', args=[item.pk]), {'checked': True}).status_code, 404)
        saved.shared_with.add(self.bob)
        self.assertEqual(self.post_json(reverse('list-check-item', args=[item.pk]), {'checked': True}).status_code, 200)
        self.assertEqual(self.client.post(reverse('list-action', args=[saved.pk, 'delete'])).status_code, 404)

    def test_list_follows_a_chosen_location(self):
        shop = Shop.objects.create(name='Mart', owner=self.alice)
        loc = ShopLocation.objects.create(shop=shop, name='Main', owner=self.alice)
        aisle = Aisle.objects.create(shop=shop, name='Baking', owner=self.alice)
        AisleOrder.objects.create(location=loc, aisle=aisle, order=1)
        CategoryAisleMapping.objects.create(location=loc, category='starch', aisle=aisle)
        saved = SavedGroceryList.objects.create(name='L', owner=self.alice)
        SavedGroceryItem.objects.create(grocery_list=saved, ingredient=self.flour, quantity=100, unit=self.gram)
        r = self.post_json(reverse('list-location', args=[saved.pk]), {'location': loc.pk})
        self.assertEqual([s['title'] for s in r.json()['sections']], ['Baking'])
        saved.refresh_from_db()
        self.assertEqual(saved.location_id, loc.pk)


class ShopLayoutTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        self.shop = Shop.objects.create(name='Mart', owner=self.alice)
        self.loc = ShopLocation.objects.create(shop=self.shop, name='Main', owner=self.alice)
        self.other = ShopLocation.objects.create(shop=self.shop, name='Second', owner=self.alice)
        self.a1, self.a2, self.a3 = (Aisle.objects.create(shop=self.shop, name=n, owner=self.alice)
                                     for n in ('Veg', 'Dairy', 'Bakery'))
        self.url = reverse('location-layout', args=[self.loc.pk])
        self.olive = self.make_ingredient('Olives', category='vegetable')

    def test_save_replaces_the_layout(self):
        r = self.post_json(self.url, {
            'route': [self.a2.pk, self.a1.pk], 'mappings': {'dairy': self.a2.pk, 'vegetable': self.a1.pk, 'meat': self.a3.pk},
            'overrides': [{'ingredient_id': self.olive.pk, 'aisle_id': self.a2.pk}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(AisleOrder.objects.filter(location=self.loc).order_by('order').values_list('aisle_id', flat=True)),
                         [self.a2.pk, self.a1.pk])
        # "meat" pointed at an aisle that is not on the route: dropped
        self.assertEqual(set(CategoryAisleMapping.objects.filter(location=self.loc).values_list('category', flat=True)),
                         {'dairy', 'vegetable'})
        self.assertEqual(IngredientAisle.objects.get(location=self.loc).aisle_id, self.a2.pk)
        # saving again with fewer aisles removes the rest
        self.post_json(self.url, {'route': [self.a1.pk], 'mappings': {}, 'overrides': []})
        self.assertEqual(AisleOrder.objects.filter(location=self.loc).count(), 1)
        self.assertEqual(IngredientAisle.objects.count(), 0)

    def test_rejects_foreign_aisles_and_bad_categories(self):
        other_shop = Shop.objects.create(name='Other', owner=self.alice)
        foreign = Aisle.objects.create(shop=other_shop, name='Foreign', owner=self.alice)
        self.assertEqual(self.post_json(self.url, {'route': [foreign.pk]}).status_code, 400)
        self.assertEqual(self.post_json(self.url, {'route': [self.a1.pk], 'mappings': {'nonsense': self.a1.pk}}).status_code, 400)
        self.assertEqual(self.post_json(self.url, {'route': ['abc']}).status_code, 400)

    def test_stranger_cannot_change_it(self):
        self.login(self.bob)
        self.assertEqual(self.post_json(self.url, {'route': []}).status_code, 404)

    def test_copy_layout(self):
        self.post_json(self.url, {'route': [self.a3.pk, self.a1.pk], 'mappings': {'fruit': self.a1.pk}, 'overrides': []})
        r = self.post_json(reverse('location-copy', args=[self.other.pk]), {'from': self.loc.pk})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(AisleOrder.objects.filter(location=self.other).order_by('order').values_list('aisle_id', flat=True)),
                         [self.a3.pk, self.a1.pk])
        self.assertEqual(self.post_json(reverse('location-copy', args=[self.other.pk]), {'from': self.other.pk}).status_code, 400)

    def test_shop_pages_and_crud(self):
        self.assertEqual(self.client.get(reverse('shop-detail', args=[self.shop.pk])).status_code, 200)
        self.client.post(reverse('aisle-add', args=[self.shop.pk]), {'names': 'Frozen, Drinks\nSnacks'})
        self.assertEqual(self.shop.aisles.count(), 6)
        self.client.post(reverse('location-add', args=[self.shop.pk]), {'name': 'Third'})
        self.assertEqual(self.shop.locations.count(), 3)
        self.client.post(reverse('shop-update', args=[self.shop.pk]), {'name': 'Mart!', 'shopping_store': 'colruyt'})
        self.shop.refresh_from_db()
        self.assertEqual((self.shop.name, self.shop.shopping_store), ('Mart!', 'colruyt'))

    def test_duplicate_shop_name_is_refused(self):
        r = self.client.post(reverse('shop-list'), {'name': 'mart', 'shopping_store': ''})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Shop.objects.filter(name__iexact='mart').count(), 1)

    def test_deleting_a_shop_with_legacy_links_works(self):
        from recipes.models import ShopLink
        ShopLink.objects.create(ingredient=self.olive, shop=self.shop, url='https://x.example/')
        self.client.post(reverse('shop-delete', args=[self.shop.pk]))
        self.assertFalse(Shop.objects.filter(pk=self.shop.pk).exists())

    def test_shared_shop_is_editable_but_not_deletable(self):
        self.shop.shared_with.add(self.bob)
        self.login(self.bob)
        self.assertEqual(self.post_json(self.url, {'route': [self.a1.pk]}).status_code, 200)
        self.assertEqual(self.client.post(reverse('shop-delete', args=[self.shop.pk])).status_code, 404)


class QuickCreateTests(HubTestCase):
    def test_create_and_reuse(self):
        self.login(self.alice)
        r = self.post_json(reverse('ingredient-quick'), {'name': '  Saffron  ', 'category': 'spice'})
        self.assertEqual((r.status_code, r.json()['existing']), (201, False))
        again = self.post_json(reverse('ingredient-quick'), {'name': 'saffron'})
        self.assertEqual((again.status_code, again.json()['existing']), (200, True))
        self.assertEqual(self.post_json(reverse('ingredient-quick'), {'name': ''}).status_code, 400)
        self.assertEqual(self.post_json(reverse('ingredient-quick'), {'name': 'x', 'category': 'zzz'}).status_code, 400)

    def test_shopping_search_proxy_is_off_without_a_token(self):
        self.login(self.alice)
        self.assertEqual(self.get_json(reverse('shopping-search') + '?q=penne').status_code, 503)


class AdminSmokeTests(HubTestCase):
    """The admin must not join auth_user (accounts database) with this database's tables."""

    def test_change_pages_open(self):
        from django.contrib import admin as dj_admin
        self.alice.is_staff = True
        self.alice.save()
        self.login(self.alice)
        ing = self.make_ingredient('Tomato')
        recipe = self.make_recipe('Soup', [(ing, 3, self.piece)])
        recipe.shared_with.add(self.bob)
        ing.shared_with.add(self.bob)
        shop = Shop.objects.create(name='Mart', owner=self.alice)
        shop.shared_with.add(self.bob)
        loc = ShopLocation.objects.create(shop=shop, name='Main', owner=self.alice)
        for url in [f'/admin/recipes/ingredient/{ing.pk}/change/', f'/admin/recipes/recipe/{recipe.pk}/change/',
                    f'/admin/recipes/shop/{shop.pk}/change/', f'/admin/recipes/shoplocation/{loc.pk}/change/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        for model in dj_admin.site._registry:
            if model._meta.app_label == 'recipes':
                url = f'/admin/recipes/{model._meta.model_name}/'
                self.assertEqual(self.client.get(url).status_code, 200, url)


class RemapOwnersTests(HubTestCase):
    def test_remaps_owners_and_shares_in_one_pass_even_when_ids_swap(self):
        from io import StringIO
        from django.core.management import call_command
        from recipes.models import Ingredient
        a = Ingredient.objects.create(name='A', owner_id=1)
        b = Ingredient.objects.create(name='B', owner_id=2)
        c = Ingredient.objects.create(name='C', owner_id=3)       # not in the map: untouched
        a.shared_with.add(self.bob)
        out = StringIO()
        # old 1 -> alice (41), old 2 -> bob (42), old 41 is not mapped
        call_command('remap_owners', '--map', '1=alice', '--map', '2=bob', stdout=out)
        for ing, owner in ((a, self.alice.pk), (b, self.bob.pk), (c, 3)):
            ing.refresh_from_db()
            self.assertEqual(ing.owner_id, owner, ing.name)
        self.assertIn('Not in the map', out.getvalue())
        # bob (id 42) was a shared_with user id; it maps from old id 42, which is not in the map: left as it was
        self.assertTrue(a.shared_with.through.objects.filter(user_id=self.bob.pk).exists())

    def test_dry_run_changes_nothing_and_unknown_user_fails(self):
        from django.core.management import CommandError, call_command
        from io import StringIO
        from recipes.models import Ingredient
        a = Ingredient.objects.create(name='A', owner_id=1)
        call_command('remap_owners', '--map', '1=alice', '--dry-run', stdout=StringIO())
        a.refresh_from_db()
        self.assertEqual(a.owner_id, 1)
        with self.assertRaises(CommandError):
            call_command('remap_owners', '--map', '1=ghost', stdout=StringIO())
