from django.conf import settings
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
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_ingredients',
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


class Shop(models.Model):
    name = models.CharField(max_length=100, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_shops',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ShopLocation(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_shop_locations',
    )

    class Meta:
        ordering = ['shop', 'name']
        unique_together = ('shop', 'name')

    def __str__(self):
        return f'{self.shop.name} — {self.name}'


class Aisle(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='aisles')
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_aisles',
    )

    class Meta:
        ordering = ['shop', 'name']
        unique_together = ('shop', 'name')

    def __str__(self):
        return self.name


class AisleOrder(models.Model):
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name='location_orders')
    location = models.ForeignKey(ShopLocation, on_delete=models.CASCADE, related_name='aisle_orders')
    order = models.PositiveIntegerField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_aisle_orders',
    )

    class Meta:
        ordering = ['location', 'order']
        unique_together = ('aisle', 'location')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.aisle_id and self.location_id:
            if self.aisle.shop_id != self.location.shop_id:
                raise ValidationError('Aisle must belong to the same shop as the location.')

    def __str__(self):
        return f'{self.location} — {self.aisle} (#{self.order})'


class CategoryAisleMapping(models.Model):
    location = models.ForeignKey(ShopLocation, on_delete=models.CASCADE, related_name='category_mappings')
    category = models.CharField(max_length=20, choices=IngredientCategory.choices)
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name='category_mappings')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_category_mappings',
    )

    class Meta:
        unique_together = ('location', 'category')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.aisle_id and self.location_id:
            if self.aisle.shop_id != self.location.shop_id:
                raise ValidationError('Aisle must belong to the same shop as the location.')

    def __str__(self):
        return f'{self.location} — {self.get_category_display()} → {self.aisle}'


class ShopLink(models.Model):
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='shop_links',
    )
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT)
    name = models.CharField(max_length=200, blank=True)
    url = models.URLField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_shop_links',
    )

    class Meta:
        ordering = ['shop__name']
        unique_together = ('ingredient', 'shop')

    def __str__(self):
        return f'{self.shop.name} — {self.ingredient}'


class Recipe(models.Model):
    class Difficulty(models.TextChoices):
        EASY         = 'easy',         'Easy'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        DIFFICULT    = 'difficult',    'Difficult'
        PRO          = 'pro',          'Pro'

    class MealType(models.TextChoices):
        BREAKFAST  = 'breakfast',  'Breakfast'
        FULL_MEAL  = 'full_meal',  'Full meal'
        SNACK      = 'snack',      'Snack'
        DESERT     = 'desert',     'Desert'

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    prep_time = models.PositiveIntegerField(help_text='Minutes')
    cook_time = models.PositiveIntegerField(help_text='Minutes')
    difficulty = models.CharField(
        max_length=15,
        choices=Difficulty.choices,
        default=Difficulty.EASY,
    )
    meal_type = models.CharField(
        max_length=15,
        choices=MealType.choices,
        default=MealType.FULL_MEAL,
    )
    tags = models.ManyToManyField(Tag, blank=True)
    ingredients = models.ManyToManyField(Ingredient, through='RecipeIngredient', blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_recipes',
    )

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


class SavedGroceryList(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    recipes = models.ManyToManyField('Recipe', blank=True)
    archived = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_grocery_lists',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class SavedGroceryItem(models.Model):
    grocery_list = models.ForeignKey(
        SavedGroceryList,
        on_delete=models.CASCADE,
        related_name='items',
    )
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    in_cart = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_grocery_items',
    )

    class Meta:
        ordering = ['ingredient__category', 'ingredient__name']

    def __str__(self):
        return f'{self.ingredient} ({self.grocery_list})'


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    is_main = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='shared_recipe_ingredients',
    )

    class Meta:
        unique_together = ('recipe', 'ingredient')

    def __str__(self):
        return f'{self.quantity} {self.unit.abbreviation} {self.ingredient} → {self.recipe}'
