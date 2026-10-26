from django.db import models


class AuthAttempt(models.Model):
    """Every login attempt on this app, used for throttling and for the admin to review."""

    KIND_CHOICES = [("login", "Login")]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    ip = models.GenericIPAddressField(null=True, blank=True)
    username = models.CharField(max_length=150, blank=True)
    ok = models.BooleanField()
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-at"]
        indexes = [
            models.Index(fields=["kind", "ip", "at"]),
            models.Index(fields=["kind", "username", "at"]),
        ]

    def __str__(self):
        return f"{self.kind} {self.username or '?'} from {self.ip} ({'ok' if self.ok else 'failed'})"
