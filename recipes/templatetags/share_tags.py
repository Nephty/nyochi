from django import template
from django.contrib.auth import get_user_model

register = template.Library()


@register.simple_tag
def get_shared_users(obj):
    """
    Return the list of users obj.shared_with contains, using a two-query
    approach to avoid a cross-database JOIN (auth_user lives in the hub DB,
    the M2M through table lives in the recipe-book default DB).
    """
    through = obj.shared_with.through
    source_col = obj._meta.model_name + "_id"
    user_ids = list(
        through.objects.filter(**{source_col: obj.pk}).values_list("user_id", flat=True)
    )
    if not user_ids:
        return []
    User = get_user_model()
    return list(User.objects.using("hub").filter(pk__in=user_ids))
