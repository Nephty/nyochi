from django.urls import path
from . import views

urlpatterns = [
    path('', views.RecipeListView.as_view(), name='recipe-list'),
    path('recipes/new/', views.RecipeCreateView.as_view(), name='recipe-create'),
    path('recipes/<int:pk>/', views.RecipeDetailView.as_view(), name='recipe-detail'),
    path('recipes/<int:pk>/edit/', views.RecipeUpdateView.as_view(), name='recipe-update'),
    path('recipes/<int:pk>/delete/', views.RecipeDeleteView.as_view(), name='recipe-delete'),
    path('recipes/ingredient-row/', views.IngredientRowView.as_view(), name='recipe-ingredient-row'),
    path('share/<str:model_type>/<int:pk>/', views.ShareView.as_view(), name='share-object'),
]
