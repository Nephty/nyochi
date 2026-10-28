"""Throttle failed logins and signups (counted in the database, so every worker agrees).

- login: 5 failures for one username, or 10 failures from one IP, within 15 minutes.
- signup (invite links): 10 attempts from one IP within an hour.
- api: 20 wrong or missing tokens from one IP within 15 minutes (Shopping's external API).
"""

import ipaddress
from datetime import timedelta

from django.utils import timezone

from .models import AuthAttempt

LIMITS = {
    "login": {"window": timedelta(minutes=15), "per_user": 5, "per_ip": 10, "failures_only": True},
    "signup": {"window": timedelta(hours=1), "per_user": None, "per_ip": 10, "failures_only": False},
    "api": {"window": timedelta(minutes=15), "per_user": None, "per_ip": 20, "failures_only": True},
}


def client_ip(request):
    """The visitor's IP. Behind Caddy REMOTE_ADDR is loopback and Caddy appends the client to X-Forwarded-For (the
    last entry: earlier ones are whatever the client sent, so they can't be trusted)."""
    remote = request.META.get("REMOTE_ADDR", "")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = remote
    try:
        if forwarded and ipaddress.ip_address(remote).is_loopback:
            ip = forwarded.split(",")[-1].strip()
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


def retry_after(kind, ip, username=""):
    """Seconds to wait, or 0 when the attempt may go ahead."""
    rule = LIMITS[kind]
    since = timezone.now() - rule["window"]
    recent = AuthAttempt.objects.filter(kind=kind, at__gte=since)
    if rule["failures_only"]:
        recent = recent.filter(ok=False)
    checks = []
    if ip and rule["per_ip"]:
        checks.append((recent.filter(ip=ip), rule["per_ip"]))
    if username and rule["per_user"]:
        checks.append((recent.filter(username__iexact=username), rule["per_user"]))
    wait = 0
    for qs, limit in checks:
        times = list(qs.order_by("-at").values_list("at", flat=True)[:limit])
        if len(times) >= limit:
            wait = max(wait, int((times[-1] + rule["window"] - timezone.now()).total_seconds()) + 1)
    return max(wait, 0)


def record(kind, ip, username, ok):
    AuthAttempt.objects.create(kind=kind, ip=ip, username=(username or "")[:150], ok=ok)


def wait_message(seconds):
    minutes = max(1, round(seconds / 60))
    return f"Too many attempts. Try again in {minutes} minute{'s' if minutes > 1 else ''}."
