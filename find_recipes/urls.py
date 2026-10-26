from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('plan/', views.PlanView.as_view(), name='plan'),
    path('plan/receipt/', views.receipt, name='plan-receipt'),
    path('plan/save/', views.save, name='plan-save'),
    path('selector/', RedirectView.as_view(pattern_name='plan', permanent=True), name='recipe-selector'),
]
