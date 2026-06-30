from django.urls import path
from . import views

urlpatterns = [
    # Recipes
    path('', views.RecipeListView.as_view(), name='recipe-list'),
    path('recipes/new/', views.RecipeCreateView.as_view(), name='recipe-create'),
    path('recipes/<int:pk>/', views.RecipeDetailView.as_view(), name='recipe-detail'),
    path('recipes/<int:pk>/edit/', views.RecipeUpdateView.as_view(), name='recipe-update'),
    path('recipes/<int:pk>/delete/', views.RecipeDeleteView.as_view(), name='recipe-delete'),

    # Ingredients
    path('ingredients/', views.IngredientListView.as_view(), name='ingredient-list'),
    path('ingredients/new/', views.IngredientCreateView.as_view(), name='ingredient-create'),
    path('ingredients/<int:pk>/', views.IngredientDetailView.as_view(), name='ingredient-detail'),
    path('ingredients/<int:pk>/edit/', views.IngredientUpdateView.as_view(), name='ingredient-update'),
    path('ingredients/<int:pk>/delete/', views.IngredientDeleteView.as_view(), name='ingredient-delete'),

    # Tags
    path('tags/', views.TagListView.as_view(), name='tag-list'),
    path('tags/<int:pk>/delete/', views.TagDeleteView.as_view(), name='tag-delete'),

    # Grocery & selector
    path('grocery/', views.GroceryListView.as_view(), name='grocery-list'),
    path('selector/', views.RecipeSelectorView.as_view(), name='recipe-selector'),
]
