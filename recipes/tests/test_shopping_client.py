import io
import json
import tempfile
import urllib.error
from decimal import Decimal
from unittest import mock

from django.test import override_settings

from recipes import shopping
from recipes.models import ShoppingLink

from .base import HubTestCase


def fake_response(payload):
    return io.BytesIO(json.dumps(payload).encode())


class ClientTests(HubTestCase):
    def setUp(self):
        shopping._down_until = 0.0
        f = tempfile.NamedTemporaryFile('w', suffix='.token', delete=False)
        f.write('s3cret\n')
        f.close()
        self.token_file = f.name
        self.settings_ctx = override_settings(SHOPPING_API_TOKEN_FILE=self.token_file, SHOPPING_API_URL='https://shop.example')
        self.settings_ctx.enable()
        self.addCleanup(self.settings_ctx.disable)
        self.addCleanup(lambda: setattr(shopping, '_down_until', 0.0))

    def test_sends_the_bearer_token_and_parses_rows(self):
        with mock.patch('urllib.request.urlopen', return_value=fake_response({'rows': [{'key': 'a|1'}]})) as op:
            rows = shopping.search('penne', 'colruyt')
        request = op.call_args.args[0]
        self.assertEqual(request.headers['Authorization'], 'Bearer s3cret')
        self.assertIn('https://shop.example/api/ext/search/?q=penne&store=colruyt', request.full_url)
        self.assertEqual(rows, [{'key': 'a|1'}])

    def test_lookup_drops_invalid_keys_and_dedups(self):
        with mock.patch('urllib.request.urlopen', return_value=fake_response({'products': {}})) as op:
            shopping.lookup(['delhaize|A1', 'delhaize|A1', 'bad key', '|x'])
        self.assertIn('keys=delhaize%7CA1', op.call_args.args[0].full_url)
        self.assertNotIn('bad', op.call_args.args[0].full_url)

    def test_failure_returns_none_and_backs_off(self):
        with mock.patch('urllib.request.urlopen', side_effect=urllib.error.URLError('down')) as op:
            self.assertIsNone(shopping.search('penne'))
            self.assertIsNone(shopping.search('penne'))
        self.assertEqual(op.call_count, 1)    # the second call didn't even try

    def test_no_token_means_off(self):
        with override_settings(SHOPPING_API_TOKEN_FILE=''):
            self.assertFalse(shopping.configured())
            self.assertIsNone(shopping.search('penne'))

    def test_refresh_updates_snapshots_and_flags_missing_products(self):
        ing = self.make_ingredient('Penne')
        a = ShoppingLink.objects.create(ingredient=ing, key='delhaize|A', store='delhaize', code='A')
        b = ShoppingLink.objects.create(ingredient=ing, key='delhaize|B', store='delhaize', code='B')
        product = {'key': 'delhaize|A', 'store_label': 'Delhaize', 'name': 'Penne 6 x 33 cl', 'package_size': '6 x 33 cl',
                   'price': 3.5, 'on_promotion': True, 'promo_titles': '2+1', 'promo_until': '2099-01-01',
                   'deal_percent': 33.3, 'deal_saving': 1.2, 'deal_qty': 3, 'real_percent': 12.0, 'usual_price': 3.9,
                   'url': 'https://x'}
        with mock.patch.object(shopping, 'lookup', return_value={'delhaize|A': product, 'delhaize|B': None}):
            self.assertTrue(shopping.refresh([a, b]))
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.price, a.pack_amount, a.pack_dimension, a.on_promotion, a.deal_qty),
                         (Decimal('3.50'), Decimal('1980'), 'volume', True, 3))
        self.assertTrue(b.missing)
        self.assertEqual((shopping.verdict(a), shopping.deal_text(a)), ('real', '−33 % when you buy 3'))

    def test_fresh_links_are_not_refetched_and_offline_is_reported(self):
        ing = self.make_ingredient('Penne')
        link = ShoppingLink.objects.create(ingredient=ing, key='delhaize|A', store='delhaize', code='A')
        with mock.patch.object(shopping, 'lookup', return_value={'delhaize|A': None}) as lk:
            shopping.refresh([link]); shopping.refresh([link])
        self.assertEqual(lk.call_count, 1)
        link.refreshed_at = None
        with mock.patch.object(shopping, 'lookup', return_value=None):
            self.assertFalse(shopping.refresh([link]))
