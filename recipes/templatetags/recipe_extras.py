from django import template

register = template.Library()

SEASON_CLASSES = {
    'in': 'bg-green-100 text-green-800',
    'early': 'bg-yellow-100 text-yellow-800',
    'late': 'bg-orange-100 text-orange-800',
    'out': 'bg-gray-100 text-gray-500',
    'unknown': 'bg-gray-100 text-gray-400',
}

SEASON_LABELS = {
    'in': 'In season',
    'early': 'Early season',
    'late': 'Late season',
    'out': 'Out of season',
    'unknown': '—',
}


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.simple_tag
def season_badge_class(status):
    return SEASON_CLASSES.get(status, 'bg-gray-100 text-gray-400')


@register.simple_tag
def season_label(status):
    return SEASON_LABELS.get(status, status)
