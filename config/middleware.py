from django.db import connections
from django.http import HttpResponseForbidden

APP_SLUG = "recipe-book"


class AppAccessMiddleware:
    """
    For authenticated non-superusers, require an AppAccess row in hub DB.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            with connections["hub"].cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM access_appaccess WHERE user_id = %s AND app = %s LIMIT 1",
                    [request.user.pk, APP_SLUG],
                )
                if cursor.fetchone() is None:
                    return HttpResponseForbidden(
                        "You don't have access to this app. "
                        "Contact the administrator at nephty.top."
                    )
        return self.get_response(request)
