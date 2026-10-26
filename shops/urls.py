from django.urls import path

from . import views

urlpatterns = [
    path('shops/', views.ShopListView.as_view(), name='shop-list'),
    path('shops/<int:pk>/', views.ShopDetailView.as_view(), name='shop-detail'),
    path('shops/<int:pk>/update/', views.ShopUpdateView.as_view(), name='shop-update'),
    path('shops/<int:pk>/delete/', views.ShopDeleteView.as_view(), name='shop-delete'),
    path('shops/<int:pk>/locations/add/', views.LocationAddView.as_view(), name='location-add'),
    path('shops/<int:pk>/aisles/add/', views.AisleAddView.as_view(), name='aisle-add'),
    path('shops/locations/<int:pk>/delete/', views.LocationDeleteView.as_view(), name='shoplocation-delete'),
    path('shops/locations/<int:pk>/layout/', views.save_layout, name='location-layout'),
    path('shops/locations/<int:pk>/copy/', views.copy_layout, name='location-copy'),
    path('shops/aisles/<int:pk>/update/', views.AisleUpdateView.as_view(), name='aisle-update'),
    path('shops/aisles/<int:pk>/delete/', views.AisleDeleteView.as_view(), name='aisle-delete'),
]
