"""Template helpers: icons (Material Symbols Rounded as inline SVG, like Shopping), money, seasons."""
import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from django import template
from django.utils.html import escape, format_html, json_script
from django.utils.safestring import mark_safe

from ..seasons import MONTH_SHORT, STATUS_LABELS, current_month

register = template.Library()


@lru_cache(maxsize=1)
def icons():
    return json.loads((Path(__file__).resolve().parent.parent / 'icons.json').read_text())


@register.simple_tag
def icon(name, cls=''):
    d = icons()[name]
    return mark_safe(
        f'<svg class="ic {escape(cls)}" viewBox="0 -960 960 960" aria-hidden="true"><path d="{d}"/></svg>'
    )


@register.simple_tag
def icons_json():
    return json_script(icons(), 'nyo-icons')


@register.filter
def euro(value):
    if value in (None, ''):
        return '–'
    return f'{Decimal(str(value)):.2f}'.replace('.', ',') + ' €'


@register.filter
def amount(value):
    """1.50 -> 1.5, 2.00 -> 2"""
    if value is None:
        return ''
    text = f'{Decimal(value):f}'
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text


@register.filter
def season_label(status):
    return STATUS_LABELS.get(status, status)


@register.filter
def initial(name):
    name = (name or '?').strip()
    return name[:1].upper() if name else '?'


@register.simple_tag
def ribbon(season_map, cls=''):
    """The 12 months of an ingredient as one ribbon; the current month is ringed."""
    now = current_month()
    cells = []
    for m in range(1, 13):
        status = season_map.get(m, 'unknown')
        cells.append(format_html(
            '<i class="m m-{}{}" title="{}: {}"><b>{}</b></i>',
            status, ' now' if m == now else '', MONTH_SHORT[m - 1], STATUS_LABELS.get(status, status),
            MONTH_SHORT[m - 1][0],
        ))
    return format_html('<span class="ribbon {}" role="img" aria-label="Seasonality by month">{}</span>',
                       cls, mark_safe(''.join(cells)))


@register.simple_tag
def flames(difficulty):
    count = {'easy': 1, 'intermediate': 2, 'difficult': 3, 'pro': 4}.get(difficulty, 0)
    on = ''.join(str(icon('local_fire_department', 'on')) for _ in range(count))
    off = ''.join(str(icon('local_fire_department', 'off')) for _ in range(4 - count))
    return format_html('<span class="flames" title="{}">{}{}</span>', difficulty.title(), mark_safe(on), mark_safe(off))


@register.filter
def get_item(d, key):
    return d.get(key)
