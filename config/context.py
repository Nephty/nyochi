from django.conf import settings
from django.contrib.messages import get_messages


def flash(request):
    """Server-side messages (messages.success(...)) become toasts: the page embeds them as JSON."""
    items = [{'level': m.level_tag or 'info', 'text': str(m)} for m in get_messages(request)]
    return {'flash': items, 'has_flash': bool(items)}


def links(request):
    """Where the sister app lives (the same base the Shopping API calls use) and the hub, for the rail."""
    return {'shopping_url': settings.SHOPPING_API_URL, 'hub_url': settings.HUB_URL}
