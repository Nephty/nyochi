from decimal import Decimal
from unittest import mock

from django.urls import reverse

from recipes import shopping
from recipes.models import Ingredient, SeasonalAvailability, ShoppingLink

from .base import HubTestCase

PRODUCT = {'key': 'delhaize|P1', 'store': 'delhaize', 'store_label': 'Delhaize', 'name': 'Penne 500 g',
           'package_size': '500 g', 'price': 1.39, 'on_promotion': False, 'url': 'https://x/p1'}


def season_post(**overrides):
    data = {f'season_{m}': 'out' for m in range(1, 13)}
    data.update(overrides)
    return data


class IngredientFormTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        patcher = mock.patch.object(shopping, 'lookup', side_effect=lambda keys: {k: dict(PRODUCT, key=k) for k in keys})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_adding_a_link_while_editing_seasons_saves_both(self):
        """The reported bug: adding a store link used to add a phantom 13th month and block the save."""
        ing = self.make_ingredient('Penne', category='starch')
        data = {'name': 'Penne', 'category': 'starch', 'link': ['delhaize|P1'], 'preferred': 'delhaize|P1',
                **season_post(season_1='in', season_2='early')}
        r = self.client.post(reverse('ingredient-update', args=[ing.pk]), data)
        self.assertRedirects(r, reverse('ingredient-detail', args=[ing.pk]))
        self.assertEqual(SeasonalAvailability.objects.filter(ingredient=ing).count(), 12)
        self.assertEqual(ing.season_map()[1], 'in')
        link = ing.shopping_links.get()
        self.assertEqual((link.key, link.is_preferred, link.name, link.price), ('delhaize|P1', True, 'Penne 500 g', Decimal('1.39')))

    def test_create_with_seasons_and_links(self):
        r = self.client.post(reverse('ingredient-create'), {
            'name': 'Basil', 'category': 'spice', 'link': ['delhaize|P1'], **season_post(season_6='in')})
        ing = Ingredient.objects.get(name='Basil')
        self.assertRedirects(r, reverse('ingredient-detail', args=[ing.pk]))
        self.assertEqual(ing.owner_id, self.alice.pk)
        self.assertEqual(ing.season_map()[6], 'in')
        self.assertEqual(ing.shopping_links.count(), 1)

    def test_removing_a_link(self):
        ing = self.make_ingredient('Penne')
        ShoppingLink.objects.create(ingredient=ing, key='delhaize|P1', store='delhaize', code='P1')
        self.client.post(reverse('ingredient-update', args=[ing.pk]), {'name': 'Penne', 'category': 'other', **season_post()})
        self.assertEqual(ing.shopping_links.count(), 0)

    def test_offline_shopping_still_saves_the_link(self):
        ing = self.make_ingredient('Penne')
        with mock.patch.object(shopping, 'lookup', return_value=None):
            self.client.post(reverse('ingredient-update', args=[ing.pk]), {
                'name': 'Penne', 'category': 'other', 'link': ['delhaize|P1'], **season_post()})
        link = ing.shopping_links.get()
        self.assertIsNone(link.refreshed_at)       # filled in by the next page view

    def test_a_bad_key_is_ignored(self):
        ing = self.make_ingredient('Penne')
        self.client.post(reverse('ingredient-update', args=[ing.pk]), {
            'name': 'Penne', 'category': 'other', 'link': ['nonsense'], **season_post()})
        self.assertEqual(ing.shopping_links.count(), 0)

    def test_duplicate_name_is_refused_case_insensitively(self):
        self.make_ingredient('Tomato')
        r = self.client.post(reverse('ingredient-create'), {'name': 'tomato', 'category': 'other', **season_post()})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Your community already has an ingredient called')
        self.assertEqual(Ingredient.objects.filter(name__iexact='tomato').count(), 1)

    def test_pages_render(self):
        ing = self.make_ingredient('Tomato')
        for name, args in [('ingredient-list', []), ('ingredient-detail', [ing.pk]),
                           ('ingredient-update', [ing.pk]), ('ingredient-create', [])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
