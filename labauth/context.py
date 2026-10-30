import os

from django.apps import apps
from django.conf import settings
from django.urls import NoReverseMatch, reverse

from . import access

# Where the family lives; settings or the environment override them (dev.sh points them at localhost).
DEFAULT_URLS = {
    "home_url": ("HOME_URL", "https://home.nephty.top/"),
    "admin_url": ("ADMIN_URL", "https://admin.nephty.top/"),
    "shopping_url": ("SHOPPING_URL", "https://shopping.nephty.top/"),
    "nyochi_url": ("NYOCHI_URL", "https://nyochi.nephty.top/"),
}


def _url(name, default):
    return getattr(settings, name, None) or os.environ.get(name) or default


def _reverse(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def lab(request):
    """{{ lab.community }}, {{ lab.communities }}, {{ lab.perms }}, {{ lab.platform }}, {{ lab.manages }}, the app
    we're in ({{ lab.app }}) and the family's URLs, for the rails' community switcher, app links and foot
    (labauth/rail_apps.html, labauth/rail_foot.html)."""
    urls = {key: _url(name, default) for key, (name, default) in DEFAULT_URLS.items()} | {
        "app": getattr(settings, "LABAUTH_APP", ""),
        # the Nephty Lab hub, above Home (Shopping's and Nyochi's settings.HUB_URL mean Home, so the environment only)
        "hub_url": os.environ.get("HUB_URL") or "https://nephty.top/",
        "logout_url": _reverse("logout"),
        "django_admin": _reverse("admin:index") if apps.is_installed("django.contrib.admin") else None,
    }
    if not request.user.is_authenticated or not hasattr(request, "lab_community"):
        return {"lab": urls}
    community = request.lab_community()
    member = request.lab_membership()
    return {"lab": urls | {
        "community": community,
        "communities": list(access.communities_of(request.user)),
        "perms": request.lab_perms(),
        "platform": request.lab_platform(),
        "role": member.role if member else ("superuser" if request.user.is_superuser else None),
        "manages": request.user.is_superuser or bool(member and member.manages),
    }}
