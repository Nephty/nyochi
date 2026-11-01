"""The meal calendar: what the community eats on a given day and slot.

A meal is one of three kinds:
  * a recipe, with a portion multiplier (×1 = the recipe as written), like the Plan screen's;
  * free text ("Restaurant", "Pizza night"): no recipe, nothing to buy;
  * leftovers of another meal (`leftover_of`): shown on its own day, bought with the meal it comes from.
`title` keeps the recipe's name when the meal is planned, so a meal whose recipe is deleted later still reads right.
Several meals may share a slot (a starter and a main); `position` orders them.
"""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from recipes.models import Recipe, community_field, owner_field


class Meal(models.Model):
    class Slot(models.TextChoices):
        BREAKFAST = 'breakfast', 'Breakfast'
        LUNCH = 'lunch', 'Lunch'
        SNACK = 'snack', 'Snack'
        DINNER = 'dinner', 'Dinner'

    day = models.DateField(db_index=True)
    slot = models.CharField(max_length=10, choices=Slot.choices, default=Slot.DINNER)
    position = models.PositiveSmallIntegerField(default=0)
    recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, null=True, blank=True, related_name='meals')
    title = models.CharField(max_length=200, blank=True)
    mult = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1'),
                               validators=[MinValueValidator(Decimal('0.25')), MaxValueValidator(Decimal('20'))])
    leftover_of = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='leftovers')
    note = models.CharField(max_length=200, blank=True)
    cooked_at = models.DateTimeField(null=True, blank=True)
    owner = owner_field()
    community_id = community_field()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day', 'slot', 'position', 'pk']
        indexes = [models.Index(fields=['community_id', 'day'])]

    def __str__(self):
        return f'{self.day} {self.slot}: {self.name}'

    @property
    def kind(self):
        if self.leftover_of_id:
            return 'leftovers'
        return 'recipe' if self.recipe_id else 'text'

    @property
    def name(self):
        if self.leftover_of_id:
            return f'Leftovers: {self.title}' if self.title else 'Leftovers'
        return self.recipe.name if self.recipe_id else self.title
