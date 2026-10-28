"""What data an app shows in the active community.

Every community or personal row has a `community_id` (the community it was made in) and an `owner_id` (who made it).
  * community data (recipes, shopping lists...): every member who may open the app reads it; the matching `*.edit`
    permission changes it;
  * personal data (stars, savings...): only its owner, and only in the community it was made in.
The ids are plain integers: the rows live in the app's own database, the communities in the lab-auth one.
"""

from functools import wraps

from .middleware import deny


def community_id(request):
    community = request.lab_community()
    return community.pk if community else None


def community_rows(model_or_qs, request):
    qs = model_or_qs._default_manager.all() if hasattr(model_or_qs, "_default_manager") else model_or_qs
    return qs.filter(community_id=community_id(request))


def personal_rows(model_or_qs, request):
    return community_rows(model_or_qs, request).filter(owner_id=request.user.pk)


def stamp(request):
    """Fields for a new row: `Model.objects.create(**stamp(request), ...)`."""
    return {"community_id": community_id(request), "owner_id": request.user.pk}


def has(request, perm):
    return perm in request.lab_perms() or perm in request.lab_platform()


def requires(*perms, message=None):
    """Let the view run when the user holds ANY of `perms` (community or platform); 403 otherwise."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if any(has(request, p) for p in perms):
                return view(request, *args, **kwargs)
            return deny(request, message or "You don't have the permission for this here. Ask your community's admins.")

        return wrapper

    return decorator
