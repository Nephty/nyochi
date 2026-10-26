from decimal import Decimal

from recipes import grocery, shopping
from recipes.models import (
    Aisle, AisleOrder, CategoryAisleMapping, IngredientAisle, Shop, ShopLocation, ShoppingLink,
)

from .base import HubTestCase


class MergeTests(HubTestCase):
    def test_mass_units_merge_and_read_nicely(self):
        flour = self.make_ingredient('Flour', category='starch')
        a = self.make_recipe('A', [(flour, 500, self.gram)])
        b = self.make_recipe('B', [(flour, 1, self.kilo)])
        (line,) = grocery.merge_recipes([(a, 1), (b, 1)])
        self.assertEqual((line.amount, line.unit.abbreviation), (Decimal('1.50'), 'kg'))
        self.assertEqual(sorted(line.sources), ['A', 'B'])

    def test_small_totals_stay_in_grams(self):
        flour = self.make_ingredient('Flour')
        a = self.make_recipe('A', [(flour, 300, self.gram)])
        b = self.make_recipe('B', [(flour, 0.2, self.kilo)])
        (line,) = grocery.merge_recipes([(a, 1), (b, 1)])
        self.assertEqual((line.amount, line.unit.abbreviation), (Decimal('500.00'), 'g'))

    def test_single_spoon_unit_is_kept(self):
        salt = self.make_ingredient('Salt')
        a = self.make_recipe('A', [(salt, 1, self.tsp)])
        b = self.make_recipe('B', [(salt, 2, self.tsp)])
        (line,) = grocery.merge_recipes([(a, 1), (b, 1)])
        self.assertEqual((line.amount, line.unit.abbreviation), (Decimal('3.00'), 'tsp'))

    def test_incomparable_units_are_not_added(self):
        garlic = self.make_ingredient('Garlic')
        a = self.make_recipe('A', [(garlic, 2, self.clove)])
        b = self.make_recipe('B', [(garlic, 1, self.piece)])
        lines = grocery.merge_recipes([(a, 1), (b, 1)])
        self.assertEqual(sorted((l.unit.abbreviation, l.amount) for l in lines),
                         [('clove', Decimal('2.00')), ('pc', Decimal('1.00'))])

    def test_multiplier_scales(self):
        rice = self.make_ingredient('Rice')
        a = self.make_recipe('A', [(rice, 150, self.gram)])
        (line,) = grocery.merge_recipes([(a, Decimal('3'))])
        self.assertEqual((line.amount, line.unit.abbreviation), (Decimal('450.00'), 'g'))


class LayoutTests(HubTestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name='Mart', owner=self.alice)
        self.loc = ShopLocation.objects.create(shop=self.shop, name='Main', owner=self.alice)
        self.veg = Aisle.objects.create(shop=self.shop, name='Produce', owner=self.alice)
        self.dairy = Aisle.objects.create(shop=self.shop, name='Chill', owner=self.alice)
        self.bake = Aisle.objects.create(shop=self.shop, name='Baking', owner=self.alice)
        # the walking order is NOT alphabetical: Chill, Produce, Baking
        AisleOrder.objects.create(location=self.loc, aisle=self.dairy, order=1)
        AisleOrder.objects.create(location=self.loc, aisle=self.veg, order=2)
        AisleOrder.objects.create(location=self.loc, aisle=self.bake, order=3)
        CategoryAisleMapping.objects.create(location=self.loc, category='vegetable', aisle=self.veg)
        CategoryAisleMapping.objects.create(location=self.loc, category='dairy', aisle=self.dairy)
        self.tomato = self.make_ingredient('Tomato', category='vegetable')
        self.milk = self.make_ingredient('Milk', category='dairy')
        self.salt = self.make_ingredient('Salt', category='spice')
        self.rice = self.make_ingredient('Rice', category='starch')

    def _sections(self):
        r = self.make_recipe('R', [(self.tomato, 2, self.piece), (self.milk, 200, self.gram),
                                   (self.salt, 1, self.tsp), (self.rice, 100, self.gram)])
        return grocery.group_lines(grocery.merge_recipes([(r, 1)]), grocery.Layout(self.loc))

    def test_sections_follow_walking_order_then_elsewhere(self):
        sections = self._sections()
        self.assertEqual([s['title'] for s in sections], ['Chill', 'Produce', 'Elsewhere'])
        self.assertEqual([s['stop'] for s in sections], [1, 2, 3])
        self.assertEqual(sorted(l.name for l in sections[2]['lines']), ['Rice', 'Salt'])

    def test_two_categories_in_one_aisle_share_a_section(self):
        CategoryAisleMapping.objects.create(location=self.loc, category='spice', aisle=self.bake)
        CategoryAisleMapping.objects.create(location=self.loc, category='starch', aisle=self.bake)
        sections = self._sections()
        self.assertEqual([s['title'] for s in sections], ['Chill', 'Produce', 'Baking'])
        self.assertEqual(sorted(l.name for l in sections[2]['lines']), ['Rice', 'Salt'])

    def test_ingredient_exception_beats_category(self):
        IngredientAisle.objects.create(location=self.loc, ingredient=self.milk, aisle=self.bake)
        sections = self._sections()
        self.assertEqual([s['title'] for s in sections], ['Produce', 'Baking', 'Elsewhere'])

    def test_without_a_layout_it_groups_by_category(self):
        r = self.make_recipe('R', [(self.tomato, 2, self.piece), (self.milk, 200, self.gram)])
        sections = grocery.group_lines(grocery.merge_recipes([(r, 1)]), None)
        self.assertEqual([s['title'] for s in sections], ['Vegetable', 'Dairy'])   # the account's category order
        self.assertTrue(all(s['stop'] is None for s in sections))


class PricingTests(HubTestCase):
    def test_parse_pack(self):
        self.assertEqual(shopping.parse_pack('500 g'), (Decimal(500), 'mass'))
        self.assertEqual(shopping.parse_pack('1,5 l'), (Decimal(1500), 'volume'))
        self.assertEqual(shopping.parse_pack('6 x 33 cl'), (Decimal(1980), 'volume'))
        self.assertEqual(shopping.parse_pack('12 st'), (Decimal(12), 'count'))
        self.assertEqual(shopping.parse_pack('per piece'), (None, ''))

    def _link(self, ing, **kw):
        defaults = dict(ingredient=ing, key='colruyt|1', store='colruyt', code='1', store_label='Colruyt',
                        name='Pasta 500 g', package_size='500 g', pack_amount=Decimal(500), pack_dimension='mass',
                        price=Decimal('2.00'), refreshed_at=__import__('django').utils.timezone.now())
        defaults.update(kw)
        return ShoppingLink.objects.create(**defaults)

    def test_whole_packs_and_promotion_saving(self):
        pasta = self.make_ingredient('Pasta')
        link = self._link(pasta, on_promotion=True, deal_qty=2, deal_saving=Decimal('1.00'), deal_percent=25.0)
        r = self.make_recipe('R', [(pasta, 1.2, self.kilo)])      # 1200 g -> 3 packs of 500 g
        (line,) = grocery.merge_recipes([(r, 1)])
        p = shopping.price_line(line.amount, line.unit, link)
        self.assertEqual((p['packs'], p['cost'], p['saving'], p['exact']),
                         (3, Decimal('6.00'), Decimal('1.00'), True))   # one "2 for" deal fits in 3 packs

    def test_recipe_estimate_is_proportional(self):
        pasta = self.make_ingredient('Pasta')
        link = self._link(pasta)
        self.assertEqual(shopping.cost_for_amount(Decimal(250), self.gram, link), Decimal('1.00'))
        self.assertIsNone(shopping.cost_for_amount(Decimal(2), self.piece, link))   # pieces vs grams

    def test_receipt_prices_the_picked_product_and_totals(self):
        from unittest import mock
        pasta = self.make_ingredient('Pasta', category='starch')
        self._link(pasta)
        self._link(pasta, key='delhaize|9', store='delhaize', code='9', store_label='Delhaize',
                   price=Decimal('1.50'), package_size='500 g')
        r = self.make_recipe('R', [(pasta, 400, self.gram)])
        with mock.patch.object(shopping, 'refresh', return_value=True):
            data = grocery.receipt(grocery.merge_recipes([(r, 1)]))
        (line,) = data['sections'][0]['lines']
        self.assertEqual(line['buy']['store'], 'delhaize')          # the cheapest of two
        self.assertEqual(line['buy']['cost'], 1.5)
        self.assertEqual(data['totals']['cost'], 1.5)
        self.assertEqual({s['store'] for s in data['stores']}, {'colruyt', 'delhaize'})

    def test_shop_store_wins_over_cheapest(self):
        pasta = self.make_ingredient('Pasta')
        a = self._link(pasta)
        self._link(pasta, key='delhaize|9', store='delhaize', code='9', price=Decimal('1.50'))
        self.assertEqual(shopping.pick_link(list(pasta.shopping_links.all()), 'colruyt'), a)


class PackSizeTests(HubTestCase):
    def test_bare_pack_sizes_from_shopping(self):
        # real examples: Shopping often gives "360" with the unit only in the name, or nowhere
        self.assertEqual(shopping.pack_from_product('360', 'HAK haricots blancs 360g'), (Decimal(360), 'mass'))
        self.assertEqual(shopping.pack_from_product('1000', 'BOGRAIN haricots blancs 1kg'), (Decimal(1000), 'mass'))
        self.assertEqual(shopping.pack_from_product('200', 'Delhaize Houmous'), (Decimal(200), shopping.BARE))
        self.assertEqual(shopping.pack_from_product('6x55g', 'ALMO 6x55g'), (Decimal(330), 'mass'))
        self.assertEqual(shopping.pack_from_product('1 pc', 'Salade'), (Decimal(1), 'count'))
        self.assertEqual(shopping.pack_from_product('', 'Laitue iceberg 1pc'), (Decimal(1), 'count'))
        self.assertEqual(shopping.pack_from_product('', 'Pâtes'), (None, ''))

    def test_a_bare_pack_is_grams_or_millilitres_never_pieces(self):
        pasta = self.make_ingredient('Houmous')
        link = ShoppingLink.objects.create(ingredient=pasta, key='delhaize|H', store='delhaize', code='H', price=Decimal('2.20'),
                                           pack_amount=Decimal(200), pack_dimension=shopping.BARE)
        self.assertEqual(shopping.cost_for_amount(Decimal(100), self.gram, link), Decimal('1.10'))   # half the pack
        self.assertEqual(shopping.cost_for_amount(Decimal('0.1'), self.kilo, link), Decimal('1.10'))
        self.assertIsNone(shopping.cost_for_amount(Decimal(2), self.piece, link))

    def test_season_distribution_sums_to_100(self):
        from recipes.seasons import distribution
        d = distribution(['in', 'in', 'in', 'early', 'late', 'out', 'out'])
        self.assertEqual(sum(x['pct'] for x in d), 100)
        self.assertEqual([(x['status'], x['count']) for x in d], [('in', 3), ('early', 1), ('late', 1), ('out', 2)])
        self.assertEqual(distribution([]), [])
        self.assertEqual([x['pct'] for x in distribution(['in'] * 3)], [100])
        self.assertEqual(sum(x['pct'] for x in distribution(['in', 'early', 'out'])), 100)
