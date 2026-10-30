import json

from django.urls import reverse

from recipes import kitchen
from recipes.models import Recipe

from .base import HubTestCase
from .test_views import formset


class CleaningTests(HubTestCase):
    def test_steps_are_cleaned_and_setup_comes_first(self):
        steps = kitchen.clean_steps([
            {'phase': 'prep', 'text': 'Cook it', 'appliance': 'oven', 'minutes': '25'},
            {'phase': 'setup', 'text': '  Peel  ', 'appliance': 'rocket', 'minutes': 'soon'},
            {'phase': 'nope', 'text': 'Serve'},
            {'phase': 'prep', 'text': '   '},
            'junk',
        ])
        self.assertEqual(steps, [
            {'phase': 'setup', 'text': 'Peel', 'appliance': '', 'minutes': None},
            {'phase': 'prep', 'text': 'Cook it', 'appliance': 'oven', 'minutes': 25},
            {'phase': 'prep', 'text': 'Serve', 'appliance': '', 'minutes': None},
        ])

    def test_tools_and_kitchenware(self):
        self.assertEqual(kitchen.clean_tools(['Knife', ' knife ', 'Whisk', '', 3]), ['Knife', 'Whisk', '3'])
        self.assertEqual(kitchen.clean_kitchenware([{'key': 'oven', 'setting': ' 180 °C '}, {'key': 'oven'}, {'key': 'x'}]),
                         [{'key': 'oven', 'setting': '180 °C'}])

    def test_old_method_becomes_steps(self):
        self.assertEqual([s['text'] for s in kitchen.split_method('1. Boil water\n\n2) Add pasta\n- Drain\nServe')],
                         ['Boil water', 'Add pasta', 'Drain', 'Serve'])

    def test_kitchenware_includes_appliances_used_by_steps(self):
        r = Recipe(steps=[{'phase': 'prep', 'text': 'Chill', 'appliance': 'fridge', 'minutes': None}],
                   kitchenware=[{'key': 'oven', 'setting': '200 °C'}])
        self.assertEqual([(k['key'], k['setting']) for k in kitchen.needed_kitchenware(r)], [('oven', '200 °C'), ('fridge', '')])


class StepPagesTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        self.tomato = self.make_ingredient('Tomato')

    def test_form_saves_steps_tools_and_kitchenware(self):
        data = {'name': 'Soup', 'meal_type': 'full_meal', 'difficulty': 'easy', 'prep_time': 5, 'cook_time': 10,
                **formset([(self.tomato, '3', self.piece)]),
                'steps_json': json.dumps([{'phase': 'prep', 'text': 'Simmer', 'appliance': 'stove', 'minutes': 20},
                                          {'phase': 'setup', 'text': 'Dice the tomatoes'}]),
                'tools_json': json.dumps(['Knife', 'Pot']),
                'kitchenware_json': json.dumps([{'key': 'stove', 'setting': 'low heat'}])}
        self.client.post(reverse('recipe-create'), data)
        recipe = Recipe.objects.get(name='Soup')
        self.assertEqual([s['text'] for s in recipe.steps], ['Dice the tomatoes', 'Simmer'])
        self.assertEqual(recipe.tools, ['Knife', 'Pot'])
        self.assertEqual(recipe.kitchenware, [{'key': 'stove', 'setting': 'low heat'}])

        page = self.client.get(reverse('recipe-detail', args=[recipe.pk]))
        self.assertContains(page, 'Start cooking')
        self.assertContains(page, 'Ingredient set-up')
        self.assertContains(page, 'low heat')
        self.assertNotContains(page, 'from the linked Shopping products')
        edit = self.client.get(reverse('recipe-update', args=[recipe.pk]))
        self.assertContains(edit, 'Dice the tomatoes')  # in the editor's JSON

        cook = self.client.get(reverse('recipe-cook', args=[recipe.pk]))
        self.assertEqual(cook.status_code, 200)
        self.assertEqual([s['appliance']['setting'] if s['appliance'] else None for s in cook.context['boot']['steps']],
                         [None, 'low heat'])

    def test_bad_json_is_refused(self):
        data = {'name': 'Soup', 'meal_type': 'full_meal', 'difficulty': 'easy', 'prep_time': 5, 'cook_time': 10,
                **formset([(self.tomato, '3', self.piece)]), 'steps_json': '{nope'}
        r = self.client.post(reverse('recipe-create'), data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Recipe.objects.filter(name='Soup').exists())

    def test_cook_page_follows_read_access(self):
        recipe = self.make_recipe('Soup', [(self.tomato, 3, self.piece)])
        self.login(self.bob)
        self.assertEqual(self.client.get(reverse('recipe-cook', args=[recipe.pk])).status_code, 404)
