from django.contrib import admin
from .models import (
    Aisle, AisleOrder, CategoryAisleMapping,
    Ingredient, Recipe, RecipeIngredient,
    SavedGroceryItem, SavedGroceryList,
    SeasonalAvailability, Shop, ShopLink, ShopLocation, Tag, Unit,
)


class SeasonalAvailabilityInline(admin.TabularInline):
    model = SeasonalAvailability
    extra = 0


class ShopLinkInline(admin.TabularInline):
    model = ShopLink
    extra = 1
    fields = ['shop', 'url']


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ['name', 'category']
    list_filter = ['category']
    search_fields = ['name']
    inlines = [SeasonalAvailabilityInline, ShopLinkInline]


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    autocomplete_fields = ['ingredient']


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['name', 'prep_time', 'cook_time', 'total_time']
    list_filter = ['tags']
    search_fields = ['name']
    filter_horizontal = ['tags']
    inlines = [RecipeIngredientInline]

    @admin.display(description='Total time')
    def total_time(self, obj):
        return f'{obj.total_time} min'


class AisleInline(admin.TabularInline):
    model = Aisle
    extra = 1


class ShopLocationInline(admin.TabularInline):
    model = ShopLocation
    extra = 1


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    inlines = [AisleInline, ShopLocationInline]


class AisleOrderInline(admin.TabularInline):
    model = AisleOrder
    extra = 0


class CategoryAisleMappingInline(admin.TabularInline):
    model = CategoryAisleMapping
    extra = 0


@admin.register(ShopLocation)
class ShopLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'shop']
    list_filter = ['shop']
    inlines = [AisleOrderInline, CategoryAisleMappingInline]


@admin.register(Aisle)
class AisleAdmin(admin.ModelAdmin):
    list_display = ['name', 'shop']
    list_filter = ['shop']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation']


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'ingredient', 'quantity', 'unit', 'is_main']
    list_filter = ['is_main']
    search_fields = ['recipe__name', 'ingredient__name']
    autocomplete_fields = ['recipe', 'ingredient']


class SavedGroceryItemInline(admin.TabularInline):
    model = SavedGroceryItem
    extra = 0
    autocomplete_fields = ['ingredient', 'unit']


@admin.register(SavedGroceryList)
class SavedGroceryListAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'archived']
    list_filter = ['archived']
    search_fields = ['name']
    inlines = [SavedGroceryItemInline]
