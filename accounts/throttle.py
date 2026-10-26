"""Throttle failed logins (counted in the database, so all workers agree).

Rules (failures only, rolling windows):
- login: 5 failures for one username, or 10 failures from one IP, within 15 minutes.
"""

import ipaddress
from datetime import timedelta

from django.utils import timezone

from .models import AuthAttempt

RULES = {
    "login": {"window": timedelta(minutes=15), "per_user": 5, "per_ip": 10},
}


def client_ip(request):
    """The visitor's IP. Behind Caddy REMOTE_ADDR is loopback and Caddy sets X-Forwarded-For."""
    remote = request.META.get("REMOTE_ADDR", "")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = remote
    try:
        if forwarded and ipaddress.ip_address(remote).is_loopback:
            ip = forwarded.split(",")[-1].strip()
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


def _wait(qs, limit, window, now):
    if not limit:
        return 0
    times = list(qs.order_by("-at").values_list("at", flat=True)[:limit])
    if len(times) < limit:
        return 0
    return max(0, int((times[-1] + window - now).total_seconds()))


def retry_after(kind, ip, username=""):
    """Seconds until another attempt is allowed (0 = allowed now)."""
    rule = RULES[kind]
    now = timezone.now()
    failures = AuthAttempt.objects.filter(kind=kind, ok=False, at__gte=now - rule["window"])
    waits = [0]
    if ip:
        waits.append(_wait(failures.filter(ip=ip), rule["per_ip"], rule["window"], now))
    if username and rule["per_user"]:
        waits.append(_wait(failures.filter(username__iexact=username), rule["per_user"], rule["window"], now))
    return max(waits)


def record(kind, ip, username, ok):
    AuthAttempt.objects.create(kind=kind, ip=ip, username=(username or "")[:150], ok=ok)


def wait_message(seconds):
    minutes = max(1, -(-seconds // 60))
    return f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes > 1 else ''}."
