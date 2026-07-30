from django.db import connections
from django.shortcuts import render

APP_SLUG = "recipe-book"


class AppAccessMiddleware:
    """
    Block access to all unauthenticated visitors and to authenticated
    non-superusers who lack an AppAccess row in hub DB.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return render(request, "403.html", status=403)
        if not request.user.is_superuser:
            with connections["hub"].cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM access_appaccess WHERE user_id = %s AND app = %s LIMIT 1",
                    [request.user.pk, APP_SLUG],
                )
                if cursor.fetchone() is None:
                    return render(request, "403.html", status=403)
        return self.get_response(request)
