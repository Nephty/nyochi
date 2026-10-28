from django.conf import settings

from . import access


def lab(request):
    """{{ lab.community }}, {{ lab.communities }}, {{ lab.perms }}, {{ lab.platform }}, {{ lab.manages }} and the
    family's URLs, for the rails' community switcher and links."""
    urls = {
        "home_url": getattr(settings, "HOME_URL", "/"),
        "admin_url": getattr(settings, "ADMIN_URL", ""),
    }
    if not request.user.is_authenticated or not hasattr(request, "lab_community"):
        return {"lab": urls}
    community = request.lab_community()
    member = request.lab_membership()
    return {"lab": urls | {
        "community": community,
        "communities": list(access.communities_of(request.user)),
        "perms": request.lab_perms(),
        "platform": request.lab_platform(),
        "role": member.role if member else ("superuser" if request.user.is_superuser else None),
        "manages": request.user.is_superuser or bool(member and member.manages),
    }}
