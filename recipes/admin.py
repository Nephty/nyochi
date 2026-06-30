from django.contrib import admin
from .models import (
    Ingredient, Recipe, RecipeIngredient,
    SeasonalAvailability, ShopLink, Tag, Unit,
)


class SeasonalAvailabilityInline(admin.TabularInline):
    model = SeasonalAvailability
    extra = 0


class ShopLinkInline(admin.TabularInline):
    model = ShopLink
    extra = 1


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


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation']
