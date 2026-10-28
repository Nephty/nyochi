from urllib.parse import quote

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect

OPEN_PATHS = ("/login/",)  # a redirect to Home's login


def wants_json(request):
    return (
        'application/json' in request.headers.get('Accept', '')
        or request.content_type == 'application/json'
    )


class LoginRequiredMiddleware:
    """Every page needs a signed-in account (one login for the house apps, on Home). Pages redirect to Home's login
    with the full address to come back to; `fetch` calls get a JSON 403 carrying the login address, which the JS follows."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or request.path in OPEN_PATHS:
            return self.get_response(request)
        login = f'{settings.LOGIN_URL}?next={quote(request.build_absolute_uri())}'
        if wants_json(request):
            return JsonResponse({'error': 'Your session has ended: sign in again.', 'login': login}, status=403)
        return redirect(login)
