from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.shortcuts import redirect
from django.urls import path

urlpatterns = [
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    # Legacy path — redirect to hub login rather than showing a local login page.
    path('accounts/login/', lambda request: redirect(settings.LOGIN_URL), name='login'),
]
