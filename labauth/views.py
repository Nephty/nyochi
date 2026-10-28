from django.http import Http404
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import access
from .middleware import set_active


@require_POST
def switch_community(request):
    """POST community=<id>[&next=<path>]: make it the active community (in every app: the session is shared)."""
    community = access.communities_of(request.user).filter(pk=request.POST.get("community") or 0).first()
    if community is None:
        raise Http404("No such community")
    set_active(request, community)
    target = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        target = "/"
    return redirect(target)
