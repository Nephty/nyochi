from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    # Signing in is Home's job (one login for the house apps).
    path('login/', RedirectView.as_view(url=settings.LOGIN_URL, query_string=True), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('accounts/logout/', LogoutView.as_view()),
]
