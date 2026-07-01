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

    # Shops
    path('shops/', views.ShopListView.as_view(), name='shop-list'),
    path('shops/<int:pk>/', views.ShopDetailView.as_view(), name='shop-detail'),
    path('shops/<int:pk>/delete/', views.ShopDeleteView.as_view(), name='shop-delete'),
    path('shops/locations/<int:pk>/delete/', views.ShopLocationDeleteView.as_view(), name='shoplocation-delete'),
    path('shops/aisles/<int:pk>/delete/', views.AisleDeleteView.as_view(), name='aisle-delete'),

    # Tags
    path('tags/', views.TagListView.as_view(), name='tag-list'),
    path('tags/<int:pk>/delete/', views.TagDeleteView.as_view(), name='tag-delete'),

    # Grocery & selector
    path('grocery/', views.GroceryListView.as_view(), name='grocery-list'),
    path('grocery/results/', views.GroceryResultsView.as_view(), name='grocery-results'),
    path('selector/', views.RecipeSelectorView.as_view(), name='recipe-selector'),
    path('selector/search/<str:meal_type>/', views.SelectorSectionView.as_view(), name='selector-section'),
    path('selector/grocery/', views.SelectorGroceryView.as_view(), name='selector-grocery'),

    # HTMX partials
    path('recipes/ingredient-row/', views.IngredientRowView.as_view(), name='recipe-ingredient-row'),
]
