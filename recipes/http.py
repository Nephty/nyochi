"""Small helpers for the JSON endpoints the screens' JavaScript talks to."""
import json
from functools import wraps

from django.http import JsonResponse


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def body(request) -> dict:
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        raise ApiError('The request body is not valid JSON.')
    if not isinstance(data, dict):
        raise ApiError('The request body must be a JSON object.')
    return data


def api(view):
    """Turn ApiError into {"error": ...} with its status; a missing row is a clean 404 JSON."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except ApiError as exc:
            return JsonResponse({'error': exc.message}, status=exc.status)
    return wrapped


def positive_int(value, what='id'):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ApiError(f'Invalid {what}.')
    if n < 0:
        raise ApiError(f'Invalid {what}.')
    return n
