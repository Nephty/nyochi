"""A recipe's method and what it needs: steps in two phases, manual tools and kitchenware.

They are stored as JSON on the Recipe (`steps`, `tools`, `kitchenware`), always written through `clean_*` below:

  steps        [{"phase": "setup" | "prep", "text": str, "appliance": KITCHENWARE key or "", "minutes": int | None}]
  tools        [str]                                   manual tools: knife, whisk, grater...
  kitchenware  [{"key": KITCHENWARE key, "setting": str}]   oven 180 °C, stove medium heat, fridge...

A step that names an appliance is a flag in the cooking guide ("in the oven now"); the setting comes from the recipe's
kitchenware entry for that appliance.
"""

PHASES = [
    ('setup', 'Ingredient set-up', 'Getting the ingredients ready: washing, peeling, cutting, weighing.'),
    ('prep', 'Preparation', 'What you actually do with them.'),
]
PHASE_KEYS = [p[0] for p in PHASES]
PHASE_LABELS = {k: label for k, label, _ in PHASES}

# key -> label, icon, the setting's placeholder, the verb the cooking guide uses for its flag
KITCHENWARE = {
    'oven':      {'label': 'Oven',          'icon': 'oven_gen',      'hint': '180 °C, fan',    'flag': 'Oven'},
    'stove':     {'label': 'Stove',         'icon': 'cooking',       'hint': 'medium heat',    'flag': 'Stove'},
    'fridge':    {'label': 'Fridge',        'icon': 'kitchen',       'hint': 'to chill',       'flag': 'Fridge'},
    'freezer':   {'label': 'Freezer',       'icon': 'ac_unit',       'hint': '',               'flag': 'Freezer'},
    'microwave': {'label': 'Microwave',     'icon': 'microwave_gen', 'hint': '800 W',          'flag': 'Microwave'},
    'grill':     {'label': 'Grill',         'icon': 'outdoor_grill', 'hint': 'high',           'flag': 'Grill'},
    'blender':   {'label': 'Blender',       'icon': 'blender',       'hint': 'or food processor', 'flag': 'Blender'},
    'kettle':    {'label': 'Kettle',        'icon': 'kettle',        'hint': '',               'flag': 'Kettle'},
}

TOOL_SUGGESTIONS = [
    'Chef’s knife', 'Chopping board', 'Peeler', 'Grater', 'Whisk', 'Wooden spoon', 'Spatula', 'Ladle', 'Tongs',
    'Colander', 'Sieve', 'Mixing bowl', 'Measuring jug', 'Kitchen scale', 'Rolling pin', 'Frying pan', 'Saucepan',
    'Large pot', 'Baking tray', 'Baking dish', 'Cake tin', 'Garlic press', 'Can opener', 'Mortar and pestle',
]

MAX_STEPS = 80
MAX_TOOLS = 40
MAX_TEXT = 2000


def _text(value, limit):
    return ' '.join(str(value or '').split())[:limit] if limit < 200 else str(value or '').strip()[:limit]


def _minutes(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 0 < n <= 24 * 60 else None


def clean_steps(raw):
    steps = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        text = _text(item.get('text'), MAX_TEXT)
        if not text:
            continue
        phase = item.get('phase') if item.get('phase') in PHASE_KEYS else 'prep'
        appliance = item.get('appliance') if item.get('appliance') in KITCHENWARE else ''
        steps.append({'phase': phase, 'text': text, 'appliance': appliance, 'minutes': _minutes(item.get('minutes'))})
    # set-up first, then preparation, each in the order given
    steps.sort(key=lambda s: PHASE_KEYS.index(s['phase']))
    return steps[:MAX_STEPS]


def clean_tools(raw):
    tools, seen = [], set()
    for item in raw if isinstance(raw, list) else []:
        name = _text(item, 80)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            tools.append(name)
    return tools[:MAX_TOOLS]


def clean_kitchenware(raw):
    items, seen = [], set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or item.get('key') not in KITCHENWARE or item['key'] in seen:
            continue
        seen.add(item['key'])
        items.append({'key': item['key'], 'setting': _text(item.get('setting'), 80)})
    return items


def needed_kitchenware(recipe):
    """The recipe's kitchenware with labels and icons, plus any appliance a step uses that wasn't listed."""
    listed = {k['key']: k for k in recipe.kitchenware or []}
    keys = list(listed) + [s['appliance'] for s in recipe.steps or [] if s.get('appliance') and s['appliance'] not in listed]
    out = []
    for key in dict.fromkeys(keys):
        meta = KITCHENWARE[key]
        out.append({'key': key, 'label': meta['label'], 'icon': meta['icon'],
                    'setting': listed.get(key, {}).get('setting', '')})
    return out


def grouped_steps(recipe):
    """[(key, label, [steps with their overall number])] for the phases that have steps."""
    groups, n = [], 0
    for key, label, _ in PHASES:
        rows = []
        for s in recipe.steps or []:
            if s['phase'] == key:
                n += 1
                meta = KITCHENWARE.get(s.get('appliance') or '')
                rows.append(s | {'n': n, 'appliance_label': meta['label'] if meta else '',
                                 'appliance_icon': meta['icon'] if meta else ''})
        if rows:
            groups.append((key, label, rows))
    return groups


def split_method(text):
    """Old free-text Method -> preparation steps, one per non-empty line (leading "1." / "-" / "•" dropped)."""
    import re
    steps = []
    for line in (text or '').splitlines():
        line = re.sub(r'^\s*(?:\d+\s*[.)\-:]|[-–•*])\s*', '', line).strip()
        if line:
            steps.append({'phase': 'prep', 'text': line[:MAX_TEXT], 'appliance': '', 'minutes': None})
    return steps[:MAX_STEPS]
