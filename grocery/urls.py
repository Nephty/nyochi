from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('lists/', views.SavedListsView.as_view(), name='saved-grocery-list'),
    path('lists/<int:pk>/', views.SavedListDetailView.as_view(), name='saved-grocery-detail'),
    path('lists/<int:pk>/receipt/', views.receipt_json, name='list-receipt'),
    path('lists/<int:pk>/location/', views.set_location, name='list-location'),
    path('lists/<int:pk>/uncheck/', views.uncheck_all, name='list-uncheck'),
    path('lists/<int:pk>/items/', views.add_item, name='list-add-item'),
    path('lists/<int:pk>/<str:action>/', views.SavedListActionView.as_view(), name='list-action'),
    path('lists/item/<int:pk>/check/', views.check_item, name='list-check-item'),
    path('lists/item/<int:pk>/delete/', views.delete_item, name='list-delete-item'),
    # the old addresses
    path('grocery/', RedirectView.as_view(pattern_name='plan', permanent=True), name='grocery-list'),
    path('grocery/saved/', RedirectView.as_view(pattern_name='saved-grocery-list', permanent=True)),
    path('grocery/saved/<int:pk>/', RedirectView.as_view(pattern_name='saved-grocery-detail', permanent=True)),
]
