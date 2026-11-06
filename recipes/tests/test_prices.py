from decimal import Decimal

from django.urls import reverse

from recipes.costing import recipe_costing
from recipes.grocery import receipt
from recipes.models import Ingredient, RecipeIngredient, ShoppingLink, Unit, UnitPrice

from .base import HubTestCase, join


class PricesByHandTests(HubTestCase):
    """A price typed in for one unit of an ingredient fills in what Shopping's products can't price."""

    def setUp(self):
        self.login(self.alice)
        self.tbsp = Unit.objects.get_or_create(abbreviation='tbsp', defaults={'name': 'tablespoon', 'dimension': 'volume', 'factor': 15})[0]
        self.litre = Unit.objects.get_or_create(abbreviation='l', defaults={'name': 'litre', 'dimension': 'volume', 'factor': 1000})[0]
        self.oil = self.make_ingredient('Olive oil')
        self.avocado = self.make_ingredient('Avocado')
        self.salad = self.make_recipe('Salad', [(self.oil, 2, self.tbsp), (self.avocado, 1, self.clove)])

    def price(self, ingredient, unit, paid, amount, **extra):
        return self.post_json(reverse('unit-price-save'),
                              {'ingredient': ingredient.pk, 'unit': unit.pk, 'paid': paid, 'for': amount, **extra})

    def costing(self):
        ris = RecipeIngredient.objects.filter(recipe=self.salad).select_related('ingredient', 'unit') \
            .prefetch_related('ingredient__shopping_links', 'ingredient__unit_prices__unit')
        return recipe_costing(ris)

    def test_a_price_per_unit_is_saved_and_used_for_any_amount(self):
        self.assertEqual(self.costing()['cost'], None)
        r = self.price(self.oil, self.tbsp, '10', '100')             # a 10 € bottle is about 100 tablespoons
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['price']['price'], 0.1)
        costing = self.costing()
        self.assertEqual((costing['cost'], costing['priced'], costing['manual']), (Decimal('0.20'), 1, 1))
        # another recipe with 3 tbsp: the same price, times 3; a teaspoon is a third of a tablespoon
        dressing = self.make_recipe('Dressing', [(self.oil, 3, self.tbsp)])
        page = self.client.get(reverse('recipe-detail', args=[dressing.pk]))
        self.assertContains(page, 'manual price')
        self.assertEqual(page.context['rows'][0]['cost'], Decimal('0.30'))
        self.make_recipe('Vinaigrette', [(self.oil, 3, self.tsp)])
        ri = RecipeIngredient.objects.get(recipe__name='Vinaigrette')
        from recipes.costing import ingredient_cost
        self.assertEqual(ingredient_cost(ri)['cost'], Decimal('0.10'))

    def test_shopping_wins_when_its_product_prices_the_amount(self):
        ShoppingLink.objects.create(ingredient=self.oil, key='delhaize|O', store='delhaize', code='O', price=Decimal('6'),
                                    pack_amount=Decimal('750'), pack_dimension='volume')
        self.price(self.oil, self.tbsp, '10', '100')
        row = self.client.get(reverse('recipe-detail', args=[self.salad.pk])).context['rows']
        oil = next(r for r in row if r['ri'].ingredient_id == self.oil.pk)
        self.assertEqual((oil['source'], oil['cost']), ('shopping', Decimal('0.24')))   # 30 ml of 750 ml for 6 €

    def test_a_pack_of_pieces_is_offered_as_a_starting_point(self):
        ShoppingLink.objects.create(ingredient=self.avocado, key='delhaize|A', store='delhaize', code='A', name='Avocados',
                                    price=Decimal('5'), pack_amount=Decimal('5'), pack_dimension='count', package_size='5 st')
        boot = self.client.get(reverse('recipe-detail', args=[self.salad.pk])).context['recipe_boot']
        avocado = next(p for p in boot['prices'] if p['ingredient'] == self.avocado.pk)
        self.assertEqual(avocado['hint'], {'paid': 5.0, 'for': 5.0, 'name': 'Avocados', 'size': '5 st'})
        self.price(self.avocado, self.clove, '5', '5')
        self.assertEqual(self.costing()['cost'], Decimal('1.00'))

    def test_the_estimate_shows_each_ingredients_share_costliest_first(self):
        ShoppingLink.objects.create(ingredient=self.avocado, key='delhaize|A', store='delhaize', code='A', price=Decimal('5'),
                                    pack_amount=Decimal('5'), pack_dimension='count', package_size='5 st')
        self.price(self.avocado, self.clove, '6', '5')     # 1,20 € each
        self.price(self.oil, self.tbsp, '10', '100')      # 0,20 € for 2 tbsp
        page = self.client.get(reverse('recipe-detail', args=[self.salad.pk]))
        shares = page.context['shares']
        self.assertEqual([(s['name'], s['cost'], round(s['pct'])) for s in shares],
                         [('Avocado', Decimal('1.20'), 86), ('Olive oil', Decimal('0.20'), 14)])
        self.assertContains(page, 'class="shares"')
        # past seven, the cheapest fold into one line
        from recipes.views import cost_shares
        rows = [{'ri': RecipeIngredient(ingredient=Ingredient(pk=i, name=f'I{i}'), ingredient_id=i), 'cost': Decimal(i),
                 'source': 'shopping'} for i in range(1, 11)]
        names = [s['name'] for s in cost_shares(rows)]
        self.assertEqual(names, ['I10', 'I9', 'I8', 'I7', 'I6', 'I5', 'I4', '3 others'])
        self.assertAlmostEqual(sum(s['pct'] for s in cost_shares(rows)), 100)

    def test_change_unit_remove_and_validation(self):
        self.price(self.oil, self.tbsp, '10', '100')
        # priced per litre instead: replaces the price per tablespoon; 2 tbsp of a 8 €/l oil
        self.price(self.oil, self.litre, '8', '1', replaces=self.tbsp.pk)
        self.assertEqual(list(UnitPrice.objects.values_list('unit__abbreviation', flat=True)), ['l'])
        self.assertEqual(self.costing()['cost'], Decimal('0.24'))
        self.assertEqual(self.price(self.oil, self.litre, '0', '1').status_code, 400)
        self.assertEqual(self.price(self.oil, self.litre, 'x', '1').status_code, 400)
        self.assertEqual(self.price(self.oil, self.litre, '3', '-1').status_code, 400)
        self.post_json(reverse('unit-price-save'), {'ingredient': self.oil.pk, 'unit': self.litre.pk, 'remove': True})
        self.assertFalse(UnitPrice.objects.exists())

    def test_only_who_may_change_the_ingredient(self):
        self.login(self.bob)   # another community
        self.assertEqual(self.price(self.oil, self.tbsp, '10', '100').status_code, 403)
        from django.contrib.auth import get_user_model
        dan = join(get_user_model().objects.create_user('dan', password='x', pk=44), self.a, deny=['nyochi.ingredients.edit'])
        self.login(dan)
        self.assertEqual(self.price(self.oil, self.tbsp, '10', '100').status_code, 403)
        self.assertEqual(self.client.get(reverse('recipe-detail', args=[self.salad.pk])).context['recipe_boot']['prices'], [])

    def test_the_ingredient_page_lists_them(self):
        self.price(self.oil, self.tbsp, '10', '100')
        page = self.client.get(reverse('ingredient-detail', args=[self.oil.pk]))
        self.assertContains(page, '0,10 € per tbsp')
        self.assertEqual(page.context['price_boot']['unit'], self.tbsp.pk)   # the unit its recipes use

    def test_a_shopping_list_line_without_a_product_uses_it(self):
        self.price(self.oil, self.tbsp, '10', '100')
        from recipes.grocery import merge_recipes
        data = receipt(merge_recipes([(self.salad, Decimal(3))]), user=self.alice)
        line = next(l for s in data['sections'] for l in s['lines'] if l['name'] == 'Olive oil')
        self.assertEqual(line['manual']['cost'], 0.6)
        self.assertEqual(data['totals']['priced'], 1)


class PortionsAndSeveralTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        self.rice = self.make_ingredient('Rice')
        self.recipe = self.make_recipe('Rice bowl', [(self.rice, 100, self.gram)], steps=[{'phase': 'prep', 'text': 'Boil'}])

    def test_cooking_takes_the_portions(self):
        cook = reverse('recipe-cook', args=[self.recipe.pk])
        self.assertEqual(self.client.get(cook).context['boot']['portions'], 1)
        self.assertEqual(self.client.get(cook, {'portions': 4}).context['boot']['portions'], 4)
        self.assertEqual(self.client.get(cook, {'portions': 'lots'}).context['boot']['portions'], 1)
        self.assertEqual(self.client.get(cook, {'portions': 500}).context['boot']['portions'], 1)
        self.assertContains(self.client.get(reverse('recipe-detail', args=[self.recipe.pk])), 'data-portions')

    def test_add_several_ingredients_at_once(self):
        r = self.post_json(reverse('ingredient-bulk'), {'names': ['Leek', ' chickpeas ', 'leek', 'rice', ''], 'category': 'other'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json(), {'made': ['Leek', 'chickpeas'], 'existing': ['Rice']})
        self.assertEqual(Ingredient.objects.get(name='Leek').seasonal_availability.count(), 12)
        self.assertEqual(self.post_json(reverse('ingredient-bulk'), {'names': []}).status_code, 400)
        self.assertEqual(self.post_json(reverse('ingredient-bulk'), {'names': ['x'], 'category': 'zzz'}).status_code, 400)

    def test_save_and_add_another(self):
        from .test_ingredient_form import season_post
        r = self.client.post(reverse('ingredient-create'), {'name': 'Fennel', 'category': 'vegetable', 'then': 'new', **season_post()})
        self.assertRedirects(r, reverse('ingredient-create') + '?category=vegetable', fetch_redirect_response=False)
        self.assertEqual(self.client.get(r.url).context['form']['category'].value(), 'vegetable')
        r = self.client.post(reverse('ingredient-create'), {'name': 'Dill', 'category': 'vegetable', **season_post()})
        self.assertRedirects(r, reverse('ingredient-detail', args=[Ingredient.objects.get(name='Dill').pk]),
                             fetch_redirect_response=False)
