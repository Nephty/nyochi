from django.urls import path
from . import views

urlpatterns = [
    path('grocery/', views.GroceryListView.as_view(), name='grocery-list'),
    path('grocery/results/', views.GroceryResultsView.as_view(), name='grocery-results'),
    path('grocery/save/', views.SaveGroceryListView.as_view(), name='save-grocery-list'),
    path('grocery/saved/', views.SavedGroceryListsView.as_view(), name='saved-grocery-list'),
    path('grocery/saved/<int:pk>/', views.SavedGroceryDetailView.as_view(), name='saved-grocery-detail'),
    path('grocery/saved/<int:pk>/delete/', views.SavedGroceryDeleteView.as_view(), name='saved-grocery-delete'),
    path('grocery/saved/item/<int:pk>/toggle/', views.ToggleCartItemView.as_view(), name='toggle-cart-item'),
    path('grocery/saved/<int:pk>/archive/', views.ArchiveGroceryListView.as_view(), name='archive-grocery-list'),
]
