from django.urls import path
from . import views

urlpatterns = [
    path('selector/', views.RecipeSelectorView.as_view(), name='recipe-selector'),
    path('selector/search/<str:meal_type>/', views.SelectorSectionView.as_view(), name='selector-section'),
    path('selector/grocery/', views.SelectorGroceryView.as_view(), name='selector-grocery'),
]
