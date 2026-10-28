import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

USER = settings.AUTH_USER_MODEL


class Community(models.Model):
    """A group of accounts (a household, friends...). Only the superuser creates one; its creator manages it in Admin.
    The apps' data rows carry the id of the community they were made in (`community_id`)."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, unique=True)
    creator = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "communities"

    def __str__(self):
        return self.name


class Membership(models.Model):
    CREATOR, ADMIN, MEMBER = "creator", "admin", "member"
    ROLES = [(CREATOR, "Creator"), (ADMIN, "Admin"), (MEMBER, "Member")]

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="lab_memberships")
    role = models.CharField(max_length=10, choices=ROLES, default=MEMBER)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["joined_at", "pk"]
        constraints = [models.UniqueConstraint(fields=["community", "user"], name="uniq_membership")]

    def __str__(self):
        return f"{self.user} in {self.community} ({self.role})"

    @property
    def manages(self):
        return self.role in (self.CREATOR, self.ADMIN)


class CommunityGrant(models.Model):
    """A permission every member of the community has unless their own MemberGrant says otherwise."""

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="grants")
    perm = models.CharField(max_length=60)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["community", "perm"], name="uniq_community_grant")]

    def __str__(self):
        return f"{self.community}: {self.perm}"


class MemberGrant(models.Model):
    """One member's override of one permission: allow or deny. No row = the community default."""

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="grants")
    perm = models.CharField(max_length=60)
    allow = models.BooleanField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["membership", "perm"], name="uniq_member_grant")]

    def __str__(self):
        return f"{self.membership}: {self.perm} {'allow' if self.allow else 'deny'}"


class PlatformGrant(models.Model):
    """A global permission (catalogue.PLATFORM), given by the superuser to one account."""

    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="lab_platform_grants")
    perm = models.CharField(max_length=60)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "perm"], name="uniq_platform_grant")]

    def __str__(self):
        return f"{self.user}: {self.perm}"


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Invite(models.Model):
    """A one-use link to join a community (and create an account when the person has none). Only the hash is kept."""

    LIFETIME = timedelta(days=7)

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="invites")
    token_hash = models.CharField(max_length=64, unique=True)
    hint = models.CharField(max_length=8, blank=True, help_text="The token's first characters, to tell links apart.")
    note = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def make(cls, community, created_by, note=""):
        """Returns (invite, token): the token is only known now, put it in the link."""
        token = secrets.token_urlsafe(24)
        invite = cls.objects.create(
            community=community, token_hash=_hash(token), hint=token[:6], note=note[:80], created_by=created_by,
            expires_at=timezone.now() + cls.LIFETIME,
        )
        return invite, token

    @classmethod
    def find(cls, token):
        return cls.objects.select_related("community").filter(token_hash=_hash(token or "")).first()

    @property
    def state(self):
        if self.revoked_at:
            return "revoked"
        if self.used_at:
            return "used"
        if self.expires_at <= timezone.now():
            return "expired"
        return "open"

    def __str__(self):
        return f"invite {self.hint}… to {self.community} ({self.state})"


class AuditEntry(models.Model):
    """Every change made in Admin. Names are copied so the log still reads after an account is deleted."""

    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.CASCADE, related_name="audit")
    actor = models.ForeignKey(USER, null=True, on_delete=models.SET_NULL, related_name="+")
    actor_name = models.CharField(max_length=150)
    action = models.CharField(max_length=40)
    target = models.ForeignKey(USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    target_name = models.CharField(max_length=150, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-at", "-pk"]
        verbose_name_plural = "audit entries"

    @classmethod
    def log(cls, actor, action, community=None, target=None, **detail):
        return cls.objects.create(
            community=community, actor=actor, actor_name=actor.get_username() if actor else "system", action=action,
            target=target, target_name=target.get_username() if target else "", detail=detail,
        )

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.actor_name} {self.action} {self.target_name}"


class AuthAttempt(models.Model):
    """Every login / signup attempt on Home and every wrong token on Shopping's external API, used for throttling."""

    KIND_CHOICES = [("login", "Login"), ("signup", "Signup"), ("api", "API token")]

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
