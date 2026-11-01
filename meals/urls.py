from django.urls import path

from . import views

urlpatterns = [
    path('', views.WeekView.as_view(), name='home'),
    path('meals/', views.WeekView.as_view(), name='meals'),
    path('meals/month/', views.MonthView.as_view(), name='meals-month'),
    path('meals/assistant/', views.AssistantView.as_view(), name='meals-assistant'),
    path('meals/shop/', views.shop, name='meal-shop'),
    path('meals/api/save/', views.save, name='meal-save'),
    path('meals/api/bulk/', views.bulk, name='meal-bulk'),
    path('meals/api/<int:pk>/<str:action>/', views.action, name='meal-action'),
]
