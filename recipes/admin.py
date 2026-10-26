from django.contrib import admin

from .models import (
    Aisle, AisleOrder, CategoryAisleMapping, Ingredient, IngredientAisle, Recipe, RecipeIngredient,
    SavedGroceryItem, SavedGroceryList, SeasonalAvailability, Shop, ShoppingLink, ShopLocation, Tag, Unit,
)


class HideShared:
    """shared_with is a many-to-many to the shared accounts: Django would join the two databases to show it. Sharing is done
    from the app (Share buttons), not here."""

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or [])
        if any(f.name == 'shared_with' for f in self.model._meta.get_fields()):
            exclude.append('shared_with')
        return exclude


class SeasonalAvailabilityInline(HideShared, admin.TabularInline):
    model = SeasonalAvailability
    extra = 0


class ShoppingLinkInline(HideShared, admin.TabularInline):
    model = ShoppingLink
    extra = 0
    fields = ['key', 'is_preferred', 'name', 'price', 'on_promotion', 'refreshed_at']
    readonly_fields = ['name', 'price', 'on_promotion', 'refreshed_at']


@admin.register(Ingredient)
class IngredientAdmin(HideShared, admin.ModelAdmin):
    list_display = ['name', 'category', 'owner']
    list_filter = ['category']
    search_fields = ['name']
    inlines = [SeasonalAvailabilityInline, ShoppingLinkInline]


class RecipeIngredientInline(HideShared, admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    autocomplete_fields = ['ingredient']


@admin.register(Recipe)
class RecipeAdmin(HideShared, admin.ModelAdmin):
    list_display = ['name', 'prep_time', 'cook_time', 'total_time', 'owner']
    list_filter = ['tags']
    search_fields = ['name']
    filter_horizontal = ['tags']
    inlines = [RecipeIngredientInline]

    @admin.display(description='Total time')
    def total_time(self, obj):
        return f'{obj.total_time} min'


class AisleInline(HideShared, admin.TabularInline):
    model = Aisle
    extra = 1


class ShopLocationInline(HideShared, admin.TabularInline):
    model = ShopLocation
    extra = 1


@admin.register(Shop)
class ShopAdmin(HideShared, admin.ModelAdmin):
    list_display = ['name', 'shopping_store', 'owner']
    search_fields = ['name']
    inlines = [AisleInline, ShopLocationInline]


class AisleOrderInline(HideShared, admin.TabularInline):
    model = AisleOrder
    extra = 0


class CategoryAisleMappingInline(HideShared, admin.TabularInline):
    model = CategoryAisleMapping
    extra = 0


class IngredientAisleInline(HideShared, admin.TabularInline):
    model = IngredientAisle
    extra = 0
    autocomplete_fields = ['ingredient']


@admin.register(ShopLocation)
class ShopLocationAdmin(HideShared, admin.ModelAdmin):
    list_display = ['name', 'shop']
    list_filter = ['shop']
    inlines = [AisleOrderInline, CategoryAisleMappingInline, IngredientAisleInline]


@admin.register(Aisle)
class AisleAdmin(HideShared, admin.ModelAdmin):
    list_display = ['name', 'shop']
    list_filter = ['shop']


@admin.register(Tag)
class TagAdmin(HideShared, admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Unit)
class UnitAdmin(HideShared, admin.ModelAdmin):
    list_display = ['name', 'abbreviation', 'dimension', 'factor']
    list_filter = ['dimension']
    search_fields = ['name', 'abbreviation']


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(HideShared, admin.ModelAdmin):
    list_display = ['recipe', 'ingredient', 'quantity', 'unit', 'is_main']
    list_filter = ['is_main']
    search_fields = ['recipe__name', 'ingredient__name']
    autocomplete_fields = ['recipe', 'ingredient']


class SavedGroceryItemInline(HideShared, admin.TabularInline):
    model = SavedGroceryItem
    extra = 0
    autocomplete_fields = ['ingredient', 'unit']


@admin.register(SavedGroceryList)
class SavedGroceryListAdmin(HideShared, admin.ModelAdmin):
    list_display = ['name', 'created_at', 'archived', 'owner']
    list_filter = ['archived']
    search_fields = ['name']
    inlines = [SavedGroceryItemInline]


@admin.register(ShoppingLink)
class ShoppingLinkAdmin(HideShared, admin.ModelAdmin):
    list_display = ['ingredient', 'key', 'name', 'price', 'on_promotion', 'refreshed_at']
    search_fields = ['ingredient__name', 'key', 'name']
