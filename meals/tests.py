import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from recipes.models import Recipe, SavedGroceryList
from recipes.tests.base import HubTestCase, join

from .models import Meal

User = get_user_model()


class MealCalendarTests(HubTestCase):
    def setUp(self):
        self.login(self.alice)
        self.today = timezone.localdate()
        self.tomato = self.make_ingredient('Tomato')
        self.pasta = self.make_recipe('Pasta', [(self.tomato, 200, self.gram, True)])
        self.soup = self.make_recipe('Soup', [(self.tomato, 500, self.gram, True)], steps=[{'phase': 'prep', 'text': 'Boil'}])

    def save(self, **data):
        return self.post_json(reverse('meal-save'), data)

    def act(self, meal_id, action, **data):
        return self.post_json(reverse('meal-action', args=[meal_id, action]), data)

    def test_recipe_meal_with_leftovers(self):
        day = self.today.isoformat()
        r = self.save(day=day, slot='dinner', recipe=self.pasta.pk, mult=2,
                      leftovers={'day': (self.today + timedelta(days=1)).isoformat(), 'slot': 'lunch'})
        self.assertEqual(r.status_code, 200, r.content)
        meals = r.json()['meals']
        self.assertEqual([(m['kind'], m['slot']) for m in meals], [('recipe', 'dinner'), ('leftovers', 'lunch')])
        self.assertEqual(meals[1]['name'], 'Leftovers: Pasta')
        self.assertEqual(meals[0]['leftovers'], [meals[1]['id']])
        # no more leftovers: the server says which meal went
        r = self.save(id=meals[0]['id'], day=day, slot='dinner', recipe=self.pasta.pk, mult=1, leftovers=None)
        self.assertEqual(r.json()['deleted'], [meals[1]['id']])
        self.assertEqual(Meal.objects.count(), 1)

    def test_free_text_and_validation(self):
        day = self.today.isoformat()
        self.assertEqual(self.save(day=day, slot='lunch', text='  Restaurant ').json()['meals'][0]['name'], 'Restaurant')
        self.assertEqual(self.save(day=day, slot='lunch').status_code, 400)                       # nothing to eat
        self.assertEqual(self.save(day=day, slot='brunch', text='x').status_code, 400)            # unknown slot
        self.assertEqual(self.save(day='soon', slot='lunch', text='x').status_code, 400)          # bad day
        self.assertEqual(self.save(day=day, slot='lunch', recipe=self.pasta.pk, mult=50).status_code, 400)

    def test_move_cooked_delete(self):
        meal = Meal.objects.create(day=self.today, slot='dinner', recipe=self.pasta, title='Pasta', owner=self.alice)
        left = Meal.objects.create(day=self.today, slot='lunch', leftover_of=meal, title='Pasta', owner=self.alice)
        r = self.act(meal.pk, 'move', day=(self.today + timedelta(days=2)).isoformat(), slot='lunch')
        self.assertEqual(r.json()['meals'][0]['day'], (self.today + timedelta(days=2)).isoformat())
        self.assertTrue(self.act(meal.pk, 'cooked', cooked=True).json()['meals'][0]['cooked'])
        self.assertEqual(sorted(self.act(meal.pk, 'delete').json()['deleted']), sorted([meal.pk, left.pk]))
        self.assertFalse(Meal.objects.exists())

    def test_pages(self):
        Meal.objects.create(day=self.today, slot='dinner', recipe=self.pasta, title='Pasta', owner=self.alice)
        week = self.client.get(reverse('meals'))
        self.assertEqual(week.status_code, 200)
        self.assertEqual([m['name'] for m in week.context['boot']['meals']], ['Pasta'])
        self.assertContains(self.client.get(reverse('meals-month')), 'Pasta')
        assistant = self.client.get(reverse('meals-assistant'), {'start': self.today.isoformat(), 'days': 3})
        self.assertEqual(assistant.context['boot']['n'], 3)
        self.assertEqual(len(assistant.context['boot']['meals']), 1)

    def test_month_link_follows_the_week(self):
        # the week of today opens today's month, even when it started in the month before
        self.assertEqual(self.client.get(reverse('meals')).context['month'], self.today.strftime('%Y-%m'))
        # another week opens the month most of it is in: Mon 30 Nov 2026 - Sun 6 Dec 2026 is December's
        self.assertEqual(self.client.get(reverse('meals'), {'week': '2026-11-30'}).context['month'], '2026-12')
        self.assertEqual(self.client.get(reverse('meals'), {'week': '2026-11-23'}).context['month'], '2026-11')

    def test_phone_sliders_load_weeks_and_months(self):
        # the day slider loads a neighbouring week as JSON (from any day of it), the month slider just the calendar
        self.save(day='2026-12-09', slot='dinner', recipe=self.pasta.pk)
        week = self.client.get(reverse('meal-week'), {'start': '2026-12-10'}).json()
        self.assertEqual((week['start'], len(week['days']), [m['day'] for m in week['meals']]),
                         ('2026-12-07', 7, ['2026-12-09']))
        self.assertEqual(self.client.get(reverse('meal-week'), {'start': 'soon'}).status_code, 400)
        part = self.client.get(reverse('meals-month'), {'m': '2026-12', 'part': 1})
        self.assertTemplateUsed(part, 'meals/_month_body.html')
        self.assertTemplateNotUsed(part, 'base.html')
        self.assertContains(part, 'data-m="2026-12"')

    def test_bulk(self):
        day = self.today.isoformat()
        r = self.post_json(reverse('meal-bulk'), {'meals': [
            {'day': day, 'slot': 'lunch', 'recipe': self.pasta.pk, 'mult': 1.5},
            {'day': day, 'slot': 'dinner', 'recipe': self.soup.pk}]})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Meal.objects.get(slot='lunch').mult, Decimal('1.5'))

    def test_shopping_list_for_days(self):
        d0 = self.today
        meal = Meal.objects.create(day=d0, slot='dinner', recipe=self.pasta, title='Pasta', owner=self.alice)
        Meal.objects.create(day=d0 + timedelta(days=1), slot='dinner', recipe=self.pasta, title='Pasta', mult=2, owner=self.alice)
        Meal.objects.create(day=d0 + timedelta(days=1), slot='lunch', leftover_of=meal, title='Pasta', owner=self.alice)
        Meal.objects.create(day=d0 + timedelta(days=2), slot='lunch', title='Restaurant', owner=self.alice)
        Meal.objects.create(day=d0 + timedelta(days=9), slot='lunch', recipe=self.soup, title='Soup', owner=self.alice)
        end = d0 + timedelta(days=6)
        r = self.client.get(reverse('meal-shop'), {'start': d0.isoformat(), 'end': end.isoformat()})
        self.assertEqual(r.status_code, 302)
        self.assertIn(f'recipe={self.pasta.pk}x3', r.url)
        self.assertNotIn(f'recipe={self.soup.pk}', r.url)
        plan = self.client.get(r.url)
        self.assertEqual(plan.context['plan']['preselect'], [{'id': self.pasta.pk, 'mult': 3.0}])
        self.assertEqual(plan.context['plan']['covers']['from'], d0.isoformat())
        saved = self.post_json(reverse('plan-save'), {'recipes': [{'id': self.pasta.pk, 'mult': 3}],
                                                      'covers': {'from': d0.isoformat(), 'to': end.isoformat()}})
        self.assertEqual(saved.status_code, 201)
        lst = SavedGroceryList.objects.get()
        self.assertEqual((lst.covers_from, lst.covers_to), (d0, end))
        self.assertTrue(lst.name.startswith('Meals '))
        week = self.client.get(reverse('meals'), {'week': d0.isoformat()})
        self.assertEqual([l['id'] for l in week.context['boot']['lists']], [lst.pk])

    def test_cooking_guide_marks_todays_meal(self):
        meal = Meal.objects.create(day=self.today, slot='dinner', recipe=self.soup, title='Soup', owner=self.alice)
        boot = self.client.get(reverse('recipe-cook', args=[self.soup.pk])).context['boot']
        self.assertEqual(boot['meal']['id'], meal.pk)
        self.assertEqual(boot['meal']['url'], reverse('meal-action', args=[meal.pk, 'cooked']))
        self.assertIsNone(self.client.get(reverse('recipe-cook', args=[self.pasta.pk])).context['boot']['meal'])
        self.act(meal.pk, 'cooked', cooked=True)
        page = self.client.get(reverse('recipe-detail', args=[self.soup.pk]))
        self.assertContains(page, 'Last cooked today')
        self.assertContains(page, 'Add to the calendar')
        listing = self.client.get(reverse('recipe-list'))
        self.assertContains(listing, 'today-meals')
        self.assertContains(listing, 'cooked')

    def test_communities_and_permission(self):
        meal = Meal.objects.create(day=self.today, slot='dinner', recipe=self.pasta, title='Pasta', owner=self.alice)
        self.login(self.bob)  # another community: doesn't see it
        self.assertEqual(self.client.get(reverse('meals')).context['boot']['meals'], [])
        self.assertEqual(self.act(meal.pk, 'delete').status_code, 404)
        dan = join(User.objects.create_user('dan', password='x', pk=44), self.a, deny=['nyochi.meals.edit'])
        self.login(dan)  # same community, may look but not change
        week = self.client.get(reverse('meals'))
        self.assertEqual(len(week.context['boot']['meals']), 1)
        self.assertFalse(week.context['boot']['canEdit'])
        self.assertEqual(self.act(meal.pk, 'delete').status_code, 403)
        self.assertEqual(self.save(day=self.today.isoformat(), slot='lunch', text='x').status_code, 403)
        self.assertTrue(Meal.objects.filter(pk=meal.pk).exists())
