from django.urls import path
from . import views

urlpatterns = [
    path('ingredients/', views.IngredientListView.as_view(), name='ingredient-list'),
    path('ingredients/new/', views.IngredientCreateView.as_view(), name='ingredient-create'),
    path('ingredients/<int:pk>/', views.IngredientDetailView.as_view(), name='ingredient-detail'),
    path('ingredients/<int:pk>/edit/', views.IngredientUpdateView.as_view(), name='ingredient-update'),
    path('ingredients/<int:pk>/delete/', views.IngredientDeleteView.as_view(), name='ingredient-delete'),
]
