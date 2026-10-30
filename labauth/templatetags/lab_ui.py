"""{% lab_icon "name" %} for labauth's own partials (the family links and the rail foot), so they render the same in every
app whatever icon set the app has. Path data lives in labauth/icons.json (Material Symbols Rounded)."""

import json
from functools import lru_cache
from pathlib import Path

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@lru_cache(maxsize=1)
def icons():
    return json.loads((Path(__file__).resolve().parent.parent / "icons.json").read_text())


@register.simple_tag
def lab_icon(name, cls=""):
    return mark_safe(
        f'<svg class="ic {escape(cls)}" viewBox="0 -960 960 960" aria-hidden="true"><path d="{icons()[name]}"/></svg>'
    )
