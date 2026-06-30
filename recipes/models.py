from django.db import models


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class IngredientCategory(models.TextChoices):
    VEGETABLE = 'vegetable', 'Vegetable'
    FRUIT = 'fruit', 'Fruit'
    STARCH = 'starch', 'Starch'
    MEAT = 'meat', 'Meat'
    DAIRY = 'dairy', 'Dairy'
    LEGUME = 'legume', 'Legume'
    FISH = 'fish', 'Fish & Seafood'
    SPICE = 'spice', 'Spice & Herb'
    OIL = 'oil', 'Oil & Fat'
    OTHER = 'other', 'Other'


class Unit(models.Model):
    name = models.CharField(max_length=50, unique=True)
    abbreviation = models.CharField(max_length=10)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.abbreviation})'


class Ingredient(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(
        max_length=20,
        choices=IngredientCategory.choices,
        default=IngredientCategory.OTHER,
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def season_status_for_month(self, month: int) -> str:
        try:
            return self.seasonal_availability.get(month=month).status
        except SeasonalAvailability.DoesNotExist:
            return 'unknown'

    def current_season_status(self) -> str:
        from django.utils import timezone
        return self.season_status_for_month(timezone.now().month)


class SeasonalAvailability(models.Model):
    class Status(models.TextChoices):
        OUT = 'out', 'Out of season'
        EARLY = 'early', 'Early season'
        IN = 'in', 'In season'
        LATE = 'late', 'Late season'

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='seasonal_availability',
    )
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OUT)

    class Meta:
        unique_together = ('ingredient', 'month')
        ordering = ['month']

    def __str__(self):
        return f'{self.ingredient} — month {self.month}: {self.get_status_display()}'


class ShopLink(models.Model):
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='shop_links',
    )
    shop_name = models.CharField(max_length=100)
    url = models.URLField()

    class Meta:
        ordering = ['shop_name']

    def __str__(self):
        return f'{self.shop_name} — {self.ingredient}'


class Recipe(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    prep_time = models.PositiveIntegerField(help_text='Minutes')
    cook_time = models.PositiveIntegerField(help_text='Minutes')
    tags = models.ManyToManyField(Tag, blank=True)
    ingredients = models.ManyToManyField(Ingredient, through='RecipeIngredient', blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_time(self) -> int:
        return self.prep_time + self.cook_time

    def main_ingredient_seasons(self) -> list[dict]:
        from django.utils import timezone
        month = timezone.now().month
        result = []
        for ri in self.recipeingredient_set.filter(is_main=True).select_related('ingredient'):
            result.append({
                'ingredient': ri.ingredient,
                'status': ri.ingredient.season_status_for_month(month),
            })
        return result


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    is_main = models.BooleanField(default=False)

    class Meta:
        unique_together = ('recipe', 'ingredient')

    def __str__(self):
        return f'{self.quantity} {self.unit.abbreviation} {self.ingredient} → {self.recipe}'
