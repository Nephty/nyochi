"""Who has which permission where. The single place that decides; every app and Admin's grid ask it.

In a community:
  * superuser: everything;
  * not a member: nothing;
  * creator or admin: every community permission;
  * member: the community defaults (CommunityGrant), with their own allow / deny (MemberGrant) on top, and an app's
    feature codes only count with that app's `view` code.
Platform permissions (catalogue.PLATFORM) are per account, not per community.
"""

from .catalogue import COMMUNITY_PERMS, PLATFORM_PERMS, app_of, view_code
from .models import Community, CommunityGrant, MemberGrant, Membership, PlatformGrant


def resolve(defaults, overrides):
    """defaults: set of codes; overrides: {code: bool}. -> the member's set of codes."""
    held = (set(defaults) | {c for c, allow in overrides.items() if allow}) - {c for c, allow in overrides.items() if not allow}
    held &= set(COMMUNITY_PERMS)
    return {c for c in held if c == view_code(app_of(c)) or view_code(app_of(c)) in held}


def defaults_of(community):
    return set(CommunityGrant.objects.filter(community=community).values_list("perm", flat=True))


def overrides_of(membership):
    return dict(MemberGrant.objects.filter(membership=membership).values_list("perm", "allow"))


def membership(user, community):
    if not (user and user.is_authenticated and community):
        return None
    return Membership.objects.filter(user=user, community=community).first()


def community_perms(user, community, member=None):
    """The set of community codes `user` holds in `community`."""
    if not (user and user.is_authenticated and community):
        return set()
    if user.is_superuser:
        return set(COMMUNITY_PERMS)
    member = member or membership(user, community)
    if member is None:
        return set()
    if member.manages:
        return set(COMMUNITY_PERMS)
    return resolve(defaults_of(community), overrides_of(member))


def platform_perms(user):
    if not (user and user.is_authenticated):
        return set()
    if user.is_superuser:
        return set(PLATFORM_PERMS)
    return set(PlatformGrant.objects.filter(user=user, perm__in=PLATFORM_PERMS).values_list("perm", flat=True))


def communities_of(user):
    """The communities a user can enter: their memberships (all of them for a superuser)."""
    if not (user and user.is_authenticated):
        return Community.objects.none()
    if user.is_superuser:
        return Community.objects.all()
    return Community.objects.filter(memberships__user=user).distinct()


def managed_by(user):
    """Communities whose members `user` may manage in Admin."""
    if not (user and user.is_authenticated):
        return Community.objects.none()
    if user.is_superuser:
        return Community.objects.all()
    return Community.objects.filter(
        memberships__user=user, memberships__role__in=[Membership.CREATOR, Membership.ADMIN]
    ).distinct()
