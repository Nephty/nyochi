"""request.community / request.membership / request.perms / request.platform_perms, set lazily on every request.

The active community is kept in the session under SESSION_KEY. The session cookie is shared by every app of the family,
so switching community in one app switches it in all of them.

Each app also names itself in `settings.LABAUTH_APP` ("shopping", "nyochi"); AppAccessMiddleware then lets a signed-in
user in only when the active community gives them `<app>.view` (else a page that says so, or a JSON 403 for /api/).
"""

import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

from . import access
from .checks import schema_problem
from .models import Community, Membership

SESSION_KEY = "lab_community"
log = logging.getLogger("labauth")


def active_community(request):
    """The community the request acts in: the session's choice if the user may still enter it, else their first."""
    user = request.user
    if not user.is_authenticated:
        return None
    allowed = access.communities_of(user)
    wanted = request.session.get(SESSION_KEY)
    community = allowed.filter(pk=wanted).first() if wanted else None
    if community is None:
        if user.is_superuser:
            # a superuser's own memberships first, then any community
            community = Community.objects.filter(memberships__user=user).order_by("memberships__joined_at").first()
        else:
            community = allowed.order_by("memberships__joined_at").first()
        community = community or allowed.order_by("pk").first()
        if community is not None:
            request.session[SESSION_KEY] = community.pk
    return community


def set_active(request, community):
    request.session[SESSION_KEY] = community.pk
    for attr in ("_lab_community", "_lab_membership", "_lab_perms"):
        request.__dict__.pop(attr, None)


class CommunityMiddleware:
    """Must come after AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.checked = False

    def __call__(self, request):
        if not self.checked:
            problem = schema_problem()
            if problem:
                log.error("labauth: %s", problem)
                return render(request, "labauth/message.html", {"title": "Being updated", "message": problem}, status=503)
            self.checked = True

        def community():
            if "_lab_community" not in request.__dict__:
                request.__dict__["_lab_community"] = active_community(request)
            return request.__dict__["_lab_community"]

        def membership():
            if "_lab_membership" not in request.__dict__:
                request.__dict__["_lab_membership"] = access.membership(request.user, community())
            return request.__dict__["_lab_membership"]

        def perms():
            if "_lab_perms" not in request.__dict__:
                request.__dict__["_lab_perms"] = access.community_perms(request.user, community(), membership())
            return request.__dict__["_lab_perms"]

        def platform():
            if "_lab_platform" not in request.__dict__:
                request.__dict__["_lab_platform"] = access.platform_perms(request.user)
            return request.__dict__["_lab_platform"]

        # callables (computed once, on first use): the community may be None
        request.lab_community = community
        request.lab_membership = membership
        request.lab_perms = perms
        request.lab_platform = platform
        return self.get_response(request)


def wants_json(request):
    return request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", "")


def deny(request, message, status=403):
    if wants_json(request):
        return JsonResponse({"error": message}, status=status)
    return render(request, "labauth/message.html", {
        "title": "Not open to you here", "message": message, "home_url": settings.HOME_URL,
    }, status=status)


class AppAccessMiddleware:
    """The app's door: a signed-in user needs `<LABAUTH_APP>.view` in the active community. Paths in
    LABAUTH_OPEN_PATHS (login, logout, the external token API...) are left to the app, and switching community is
    always open (it is how someone stuck in a community without this app gets out)."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.app = settings.LABAUTH_APP
        self.open = tuple(getattr(settings, "LABAUTH_OPEN_PATHS", ())) + ("/community/switch/",)

    def __call__(self, request):
        if not request.user.is_authenticated or request.path.startswith(self.open):
            return self.get_response(request)
        community = request.lab_community()
        if community is None:
            return deny(request, "You are not in any community yet. Ask someone who manages one for an invite link.")
        if f"{self.app}.view" not in request.lab_perms():
            return deny(request, f"Your community “{community.name}” does not open this app to you. "
                                 "Switch community on Home, or ask its admins.")
        return self.get_response(request)


__all__ = ["CommunityMiddleware", "AppAccessMiddleware", "Membership", "set_active", "SESSION_KEY"]
