from django.urls import path

from . import views

urlpatterns = [
    path("community/switch/", views.switch_community, name="lab_switch"),
]
