from urllib.parse import quote

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect

OPEN_PATHS = ("/login/",)


def wants_json(request):
    return (
        'application/json' in request.headers.get('Accept', '')
        or request.content_type == 'application/json'
    )


class LoginRequiredMiddleware:
    """Every page needs a signed-in account (accounts are shared with Shopping, created in the Django admin).
    Pages redirect to the login; `fetch` calls get a JSON 403 carrying the login address, which the JS follows."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or request.path in OPEN_PATHS:
            return self.get_response(request)
        login = f'{settings.LOGIN_URL}?next={quote(request.get_full_path())}'
        if wants_json(request):
            return JsonResponse({'error': 'Your session has ended: sign in again.', 'login': login}, status=403)
        return redirect(login)
