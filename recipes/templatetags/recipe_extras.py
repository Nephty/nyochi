from django import template
from django.utils.html import mark_safe

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


_DIFFICULTY_COUNTS = {'easy': 1, 'intermediate': 2, 'difficult': 3, 'pro': 4}


@register.simple_tag
def difficulty_stars(difficulty):
    count = _DIFFICULTY_COUNTS.get(difficulty, 0)
    filled = f'<span class="text-amber-400">{"★" * count}</span>'
    empty = f'<span class="text-gray-300">{"☆" * (4 - count)}</span>' if count < 4 else ''
    return mark_safe(filled + empty)
