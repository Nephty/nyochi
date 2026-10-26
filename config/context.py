from django.contrib.messages import get_messages


def flash(request):
    """Server-side messages (messages.success(...)) become toasts: the page embeds them as JSON."""
    items = [{'level': m.level_tag or 'info', 'text': str(m)} for m in get_messages(request)]
    return {'flash': items, 'has_flash': bool(items)}
