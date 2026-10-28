"""Who may change what in Admin. Views call these before every write; the UI uses them to hide what can't be done.

  * the creator (and the superuser) manage everything in their community, and are the only ones who make or unmake
    admins;
  * admins edit the community defaults and the permissions of plain members, add and remove plain members, and make
    invites; they cannot touch the creator, other admins or themselves;
  * nobody removes the creator; admins and the creator hold every permission of their community anyway, so only plain
    members have per-member permissions.
"""

from .models import Membership


def _actor(user, community):
    """'superuser' / 'creator' / 'admin' / None for what `user` is in `community`, management-wise."""
    if not (user and user.is_authenticated):
        return None
    if user.is_superuser:
        return "superuser"
    m = Membership.objects.filter(user=user, community=community).only("role").first()
    if m and m.role in (Membership.CREATOR, Membership.ADMIN):
        return m.role
    return None


def can_manage(user, community):
    """Open the community in Admin, edit its defaults, add members, make invites."""
    return _actor(user, community) is not None


def can_set_roles(user, community):
    return _actor(user, community) in ("superuser", "creator")


def can_set_role(user, target):
    """Make `target` (a Membership) an admin or a plain member again."""
    return target.role != Membership.CREATOR and can_set_roles(user, target.community)


def can_edit_member(user, target):
    """Change `target`'s own permissions (only plain members have any of their own)."""
    return target.role == Membership.MEMBER and target.user_id != user.pk and can_manage(user, target.community)


def can_remove(user, target):
    if target.role == Membership.CREATOR or target.user_id == user.pk:
        return False
    if target.role == Membership.ADMIN:
        return can_set_roles(user, target.community)
    return can_manage(user, target.community)


def can_superuse(user):
    """Create / rename / delete communities and give platform permissions."""
    return bool(user and user.is_authenticated and user.is_superuser)
