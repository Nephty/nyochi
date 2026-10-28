"""Django admin (superuser only, on Home): a raw view of the tables. Day-to-day management is the Admin app."""

from django.contrib import admin

from .models import AuditEntry, AuthAttempt, Community, CommunityGrant, Invite, MemberGrant, Membership, PlatformGrant


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    raw_id_fields = ["user"]


class CommunityGrantInline(admin.TabularInline):
    model = CommunityGrant
    extra = 0


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "creator", "created_at"]
    prepopulated_fields = {"slug": ["name"]}
    raw_id_fields = ["creator"]
    inlines = [MembershipInline, CommunityGrantInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "community", "role", "joined_at"]
    list_filter = ["community", "role"]


admin.site.register(MemberGrant)
admin.site.register(PlatformGrant)


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ["hint", "community", "note", "created_by", "expires_at", "used_by", "revoked_at"]
    readonly_fields = ["token_hash"]


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ["at", "community", "actor_name", "action", "target_name"]
    list_filter = ["community", "action"]


@admin.register(AuthAttempt)
class AuthAttemptAdmin(admin.ModelAdmin):
    list_display = ["at", "kind", "username", "ip", "ok"]
    list_filter = ["kind", "ok"]
