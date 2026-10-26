from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect
from django.urls import path

urlpatterns = [
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    # Accounts live in the hub: its login page is the only one.
    path('accounts/login/', lambda request: redirect(settings.LOGIN_URL), name='login'),
]
