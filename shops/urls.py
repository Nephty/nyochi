from django.urls import path
from . import views

urlpatterns = [
    path('shops/', views.ShopListView.as_view(), name='shop-list'),
    path('shops/<int:pk>/', views.ShopDetailView.as_view(), name='shop-detail'),
    path('shops/<int:pk>/delete/', views.ShopDeleteView.as_view(), name='shop-delete'),
    path('shops/locations/<int:pk>/delete/', views.ShopLocationDeleteView.as_view(), name='shoplocation-delete'),
    path('shops/aisles/<int:pk>/delete/', views.AisleDeleteView.as_view(), name='aisle-delete'),
]
