from urllib.parse import quote

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.shortcuts import render

APP_SLUG = "recipe-book"


def wants_json(request):
    return (
        'application/json' in request.headers.get('Accept', '')
        or request.content_type == 'application/json'
    )


class AppAccessMiddleware:
    """
    Block access to all unauthenticated visitors and to authenticated
    non-superusers who lack an AppAccess row in hub DB.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def deny(self, request, signed_in):
        if wants_json(request):
            login = f'{settings.LOGIN_URL}?next={quote(request.build_absolute_uri())}'
            return JsonResponse(
                {'error': 'You have no access to this app.' if signed_in else 'Your session has ended: sign in again.',
                 'login': None if signed_in else login},
                status=403,
            )
        return render(request, "403.html", {'signed_in': signed_in}, status=403)

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.deny(request, False)
        if not request.user.is_superuser:
            with connections["hub"].cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM access_appaccess WHERE user_id = %s AND app = %s LIMIT 1",
                    [request.user.pk, APP_SLUG],
                )
                if cursor.fetchone() is None:
                    return self.deny(request, True)
        return self.get_response(request)
