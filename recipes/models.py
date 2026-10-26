from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower


# auth_user lives in the hub's SQLite file, so no foreign key to it can be enforced by this
# database: every owner / shared_with link is declared with db_constraint=False.
def owner_field():
    return models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', db_constraint=False,
    )


def shared_field(related_name):
    return models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name=related_name, db_constraint=False,
    )


class Tag(models.Model):
    name = models.CharField(max_length=50)
    owner = owner_field()

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(Lower('name'), 'owner', name='tag_name_per_owner'),
        ]

    def __str__(self):
        return self.name


class IngredientCategory(models.TextChoices):
    """The categories every account starts with (see categories.py); each account can then add, rename, reorder, delete."""
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


class Category(models.Model):
    """An ingredient category of one account. `key` is stable (ingredients and shop layouts store it) and `name` is
    what is shown; renaming never touches ingredients. Accounts get the defaults on first use."""
    owner = owner_field()
    key = models.SlugField(max_length=40)
    name = models.CharField(max_length=60)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']
        verbose_name_plural = 'categories'
        constraints = [
            models.UniqueConstraint('owner', 'key', name='category_key_per_owner'),
            models.UniqueConstraint(Lower('name'), 'owner', name='category_name_per_owner'),
        ]

    def __str__(self):
        return self.name


class Unit(models.Model):
    """A measure. mass (base g), volume (base ml) and count ("piece") units can be added together;
    every other unit (clove, bunch, pinch...) is only summed with itself."""

    class Dimension(models.TextChoices):
        MASS = 'mass', 'Mass'
        VOLUME = 'volume', 'Volume'
        COUNT = 'count', 'Pieces'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=50, unique=True)
    abbreviation = models.CharField(max_length=10)
    dimension = models.CharField(max_length=10, choices=Dimension.choices, default=Dimension.OTHER)
    factor = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text='How many base units (g, ml, pieces) one of this unit is.',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.abbreviation})'

    @property
    def mergeable(self):
        return self.dimension != self.Dimension.OTHER and bool(self.factor)


class Ingredient(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=40, default=IngredientCategory.OTHER)   # a Category.key
    owner = owner_field()
    shared_with = shared_field('shared_ingredients')

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(Lower('name'), 'owner', name='ingredient_name_per_owner'),
        ]

    def __str__(self):
        return self.name

    def season_map(self) -> dict:
        """{month: status}. Uses the prefetch cache when seasonal_availability was prefetched."""
        return {sa.month: sa.status for sa in self.seasonal_availability.all()}

    def season_status_for_month(self, month: int) -> str:
        return self.season_map().get(month, 'unknown')

    def current_season_status(self) -> str:
        from .seasons import current_month
        return self.season_status_for_month(current_month())


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
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OUT)

    class Meta:
        unique_together = ('ingredient', 'month')
        ordering = ['month']

    def __str__(self):
        return f'{self.ingredient} — month {self.month}: {self.get_status_display()}'


class Shop(models.Model):
    name = models.CharField(max_length=100)
    # The Shopping store this shop is (delhaize, colruyt, kruidvat...): grocery lists for it
    # prefer an ingredient's product from that store.
    shopping_store = models.CharField(max_length=30, blank=True)
    owner = owner_field()
    shared_with = shared_field('shared_shops')

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(Lower('name'), 'owner', name='shop_name_per_owner'),
        ]

    def __str__(self):
        return self.name


class ShopLocation(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=100)
    owner = owner_field()
    shared_with = shared_field('shared_shop_locations')

    class Meta:
        ordering = ['shop', 'name']
        unique_together = ('shop', 'name')

    def __str__(self):
        return f'{self.shop.name} — {self.name}'


class Aisle(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='aisles')
    name = models.CharField(max_length=100)
    owner = owner_field()
    shared_with = shared_field('shared_aisles')

    class Meta:
        ordering = ['shop', 'name']
        unique_together = ('shop', 'name')

    def __str__(self):
        return self.name


class AisleOrder(models.Model):
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name='location_orders')
    location = models.ForeignKey(ShopLocation, on_delete=models.CASCADE, related_name='aisle_orders')
    order = models.PositiveIntegerField()
    owner = owner_field()
    shared_with = shared_field('shared_aisle_orders')

    class Meta:
        ordering = ['location', 'order']
        unique_together = ('aisle', 'location')

    def clean(self):
        if self.aisle_id and self.location_id:
            if self.aisle.shop_id != self.location.shop_id:
                raise ValidationError('Aisle must belong to the same shop as the location.')

    def __str__(self):
        return f'{self.location} — {self.aisle} (#{self.order})'


class CategoryAisleMapping(models.Model):
    location = models.ForeignKey(ShopLocation, on_delete=models.CASCADE, related_name='category_mappings')
    category = models.CharField(max_length=40)   # a Category.key
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name='category_mappings')
    owner = owner_field()
    shared_with = shared_field('shared_category_mappings')

    class Meta:
        unique_together = ('location', 'category')

    def clean(self):
        if self.aisle_id and self.location_id:
            if self.aisle.shop_id != self.location.shop_id:
                raise ValidationError('Aisle must belong to the same shop as the location.')

    def __str__(self):
        return f'{self.location} — {self.category} → {self.aisle}'


class IngredientAisle(models.Model):
    """An exception to the category -> aisle mapping: this ingredient sits in that aisle at that location."""
    location = models.ForeignKey(ShopLocation, on_delete=models.CASCADE, related_name='ingredient_aisles')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='aisle_overrides')
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name='ingredient_overrides')

    class Meta:
        unique_together = ('location', 'ingredient')

    def __str__(self):
        return f'{self.location} — {self.ingredient} → {self.aisle}'


class ShopLink(models.Model):
    """Legacy: a free-text web link of an ingredient in one of the user's shops. Replaced by
    ShoppingLink (a product of the Shopping app); kept so the old data isn't lost, not shown any more."""
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='shop_links',
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, blank=True)
    url = models.URLField()
    owner = owner_field()
    shared_with = shared_field('shared_shop_links')

    class Meta:
        ordering = ['shop__name']
        unique_together = ('ingredient', 'shop')

    def __str__(self):
        return f'{self.shop.name} — {self.ingredient}'


class ShoppingLink(models.Model):
    """An ingredient's product in the Shopping app, with the last price / promotion we read from it."""
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='shopping_links')
    key = models.CharField(max_length=80)          # "store|code", Shopping's product identity
    store = models.CharField(max_length=30)
    store_label = models.CharField(max_length=40, blank=True)
    code = models.CharField(max_length=60)
    is_preferred = models.BooleanField(default=False)

    # snapshot of Shopping's data, refreshed in batches (recipes/shopping.py)
    name = models.CharField(max_length=300, blank=True)
    brand = models.CharField(max_length=120, blank=True)
    package_size = models.CharField(max_length=80, blank=True)
    pack_amount = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    pack_dimension = models.CharField(max_length=10, blank=True)   # mass | volume | count | ''
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    prev_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_day = models.DateField(null=True, blank=True)
    on_promotion = models.BooleanField(default=False)
    promo_titles = models.CharField(max_length=600, blank=True)
    promo_until = models.DateField(null=True, blank=True)
    deal_qty = models.PositiveIntegerField(null=True, blank=True)
    deal_saving = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    deal_percent = models.FloatField(null=True, blank=True)
    usual_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    real_percent = models.FloatField(null=True, blank=True)
    url = models.URLField(max_length=2000, blank=True)
    missing = models.BooleanField(default=False)   # Shopping no longer knows this product
    refreshed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_preferred', 'store', 'name']
        unique_together = ('ingredient', 'key')

    def __str__(self):
        return f'{self.ingredient} → {self.key}'


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
        DESERT     = 'desert',     'Dessert'

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
    owner = owner_field()
    shared_with = shared_field('shared_recipes')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_time(self) -> int:
        return self.prep_time + self.cook_time


class SavedGroceryList(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    recipes = models.ManyToManyField('Recipe', blank=True)
    archived = models.BooleanField(default=False)
    location = models.ForeignKey(
        ShopLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    owner = owner_field()
    shared_with = shared_field('shared_grocery_lists')

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
    # null ingredient + custom_name = an item typed in by hand ("bin bags")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True)
    custom_name = models.CharField(max_length=120, blank=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('1'))
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True)
    in_cart = models.BooleanField(default=False)
    owner = owner_field()
    shared_with = shared_field('shared_grocery_items')

    class Meta:
        ordering = ['ingredient__category', 'ingredient__name', 'custom_name']

    def __str__(self):
        return f'{self.ingredient or self.custom_name} ({self.grocery_list})'

    @property
    def display_name(self):
        return self.ingredient.name if self.ingredient_id else self.custom_name


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))],
    )
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    is_main = models.BooleanField(default=False)
    owner = owner_field()
    shared_with = shared_field('shared_recipe_ingredients')

    class Meta:
        unique_together = ('recipe', 'ingredient')

    def __str__(self):
        return f'{self.quantity} {self.unit.abbreviation} {self.ingredient} → {self.recipe}'
