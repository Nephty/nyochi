"""The Shopping app, seen from Nyochi: a read-only JSON API with a bearer token (shopping/core/ext_api.py).

Only Nyochi's server talks to Shopping (the browser's CSP forbids it). Every link keeps a snapshot of what
Shopping answered last (price, promotion, real-deal figures), refreshed in batches when it is older than
STALE, so pages still work when Shopping is down.
"""
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from math import ceil

from django.conf import settings
from django.utils import timezone

from .models import ShoppingLink

log = logging.getLogger(__name__)

STALE = timedelta(hours=6)
TIMEOUT = 5
BACKOFF = 60          # seconds without trying again after a failure
KEY_RE = re.compile(r'^[a-z0-9_-]{2,30}\|[\w.-]{1,40}$')
_down_until = 0.0


# ------------------------------------------------------------------ the API

def _token() -> str:
    path = getattr(settings, 'SHOPPING_API_TOKEN_FILE', '')
    if not path:
        return ''
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return ''


def configured() -> bool:
    return bool(_token())


def _get(path: str, params: dict):
    """GET path -> parsed JSON, or None when Shopping can't be reached / refuses."""
    global _down_until
    token = _token()
    if not token or time.monotonic() < _down_until:
        return None
    url = f'{settings.SHOPPING_API_URL.rstrip("/")}{path}?{urllib.parse.urlencode(params)}'
    request = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning('Shopping API %s failed: %s', path, exc)
        _down_until = time.monotonic() + BACKOFF
        return None


def search(query: str, store: str = ''):
    """Products matching the words, or None when Shopping is unreachable."""
    params = {'q': query}
    if store:
        params['store'] = store
    data = _get('/api/ext/search/', params)
    return None if data is None else data.get('rows', [])


def lookup(keys):
    """{key: product dict or None} for "store|code" keys, or None when Shopping is unreachable."""
    keys = list(dict.fromkeys(k for k in keys if KEY_RE.match(k)))
    result = {}
    for i in range(0, len(keys), 100):
        data = _get('/api/ext/products/', {'keys': ','.join(keys[i:i + 100])})
        if data is None:
            return None
        result.update(data.get('products', {}))
    return result


# ------------------------------------------------------------------ pack sizes

_UNITS = {
    'mg': ('mass', Decimal('0.001')), 'g': ('mass', Decimal(1)), 'gr': ('mass', Decimal(1)),
    'kg': ('mass', Decimal(1000)),
    'ml': ('volume', Decimal(1)), 'cl': ('volume', Decimal(10)), 'dl': ('volume', Decimal(100)),
    'l': ('volume', Decimal(1000)),
    'st': ('count', Decimal(1)), 'stuk': ('count', Decimal(1)), 'stuks': ('count', Decimal(1)),
    'pc': ('count', Decimal(1)), 'pcs': ('count', Decimal(1)), 'piece': ('count', Decimal(1)),
    'pieces': ('count', Decimal(1)),
}
_PACK = re.compile(
    r'(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(mg|kg|gr|g|ml|cl|dl|l|stuks|stuk|st|pcs|pc|pieces|piece)\b'
)


BARE = 'bare'    # a pack size with no unit ("360"): Shopping's stores mostly give grams or millilitres that way
_BARE = re.compile(r'^\s*(\d+(?:[.,]\d+)?)\s*$')


def pack_from_product(package_size: str, name: str):
    """(amount, dimension) of a Shopping product's pack. An explicit unit wins; a bare number ("360") takes its unit from
    the product name when the name says the same amount ("... 360g"), otherwise it stays BARE and is read as grams or
    millilitres depending on the recipe's own unit (a recipe in pieces never compares with it)."""
    amount, dimension = parse_pack(package_size)
    if amount:
        return amount, dimension
    bare = _BARE.match(package_size or '')
    if bare:
        value = Decimal(bare.group(1).replace(',', '.'))
        if value <= 0:
            return None, ''
        named_amount, named_dimension = parse_pack(name)
        if named_amount == value:
            return named_amount, named_dimension
        return value, BARE
    return parse_pack(name)


def parse_pack(text: str):
    """"6 x 33 cl" -> (Decimal(1980), "volume") in base units (g, ml, pieces); (None, "") if unreadable."""
    match = _PACK.search((text or '').lower())
    if not match:
        return None, ''
    count = Decimal(match.group(1) or 1)
    try:
        amount = Decimal(match.group(2).replace(',', '.'))
    except InvalidOperation:
        return None, ''
    dimension, factor = _UNITS[match.group(3)]
    total = count * amount * factor
    return (total if total > 0 else None), dimension


# ------------------------------------------------------------------ snapshots

def _money(value):
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except InvalidOperation:
        return None


def _day(value):
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


SNAPSHOT_FIELDS = [
    'store_label', 'name', 'brand', 'package_size', 'pack_amount', 'pack_dimension', 'price', 'prev_price',
    'price_day', 'on_promotion', 'promo_titles', 'promo_until', 'deal_qty', 'deal_saving', 'deal_percent',
    'usual_price', 'real_percent', 'url', 'missing', 'refreshed_at',
]


def apply_snapshot(link: ShoppingLink, product: dict | None):
    link.refreshed_at = timezone.now()
    if product is None:
        link.missing = True
        return
    link.missing = False
    link.store_label = (product.get('store_label') or link.store_label or link.store)[:40]
    link.name = (product.get('name') or '')[:300]
    link.brand = (product.get('brand') or '')[:120]
    link.package_size = (product.get('package_size') or '')[:80]
    link.pack_amount, link.pack_dimension = pack_from_product(link.package_size, link.name)
    link.price = _money(product.get('price'))
    link.prev_price = _money(product.get('prev_price'))
    link.price_day = _day(product.get('price_day'))
    link.on_promotion = bool(product.get('on_promotion'))
    link.promo_titles = (product.get('promo_titles') or '')[:600]
    link.promo_until = _day(product.get('promo_until'))
    link.deal_qty = product.get('deal_qty')
    link.deal_saving = _money(product.get('deal_saving'))
    link.deal_percent = product.get('deal_percent')
    link.usual_price = _money(product.get('usual_price'))
    link.real_percent = product.get('real_percent')
    link.url = (product.get('url') or '')[:2000]


def refresh(links, force=False) -> bool:
    """Bring stale snapshots up to date with one batch call. False when Shopping couldn't be asked."""
    now = timezone.now()
    stale = [l for l in links if force or l.refreshed_at is None or now - l.refreshed_at > STALE]
    if not stale:
        return True
    products = lookup([l.key for l in stale])
    if products is None:
        return False
    for link in stale:
        apply_snapshot(link, products.get(link.key))
    ShoppingLink.objects.bulk_update(stale, SNAPSHOT_FIELDS)
    return True


def promo_active(link: ShoppingLink, today: date | None = None) -> bool:
    if not link.on_promotion:
        return False
    return link.promo_until is None or link.promo_until >= (today or timezone.localdate())


def verdict(link: ShoppingLink) -> str:
    """Shopping's "is this a real deal?": real >= 10 % under the usual price, usual < 3 %."""
    if link.real_percent is None:
        return ''
    return 'real' if link.real_percent >= 10 else 'usual' if link.real_percent < 3 else 'some'


def deal_text(link: ShoppingLink) -> str:
    if link.deal_saving is None or link.deal_percent is None:
        return ''
    text = f'−{round(link.deal_percent)} %'
    if link.deal_qty and link.deal_qty > 1:
        text += f' when you buy {link.deal_qty}'
    return text


def link_json(link: ShoppingLink) -> dict:
    promo = promo_active(link)
    return {
        'id': link.pk, 'key': link.key, 'store': link.store, 'store_label': link.store_label or link.store,
        'name': link.name or link.key, 'brand': link.brand, 'package_size': link.package_size,
        'price': float(link.price) if link.price is not None else None,
        'prev_price': float(link.prev_price) if link.prev_price is not None else None,
        'url': link.url, 'preferred': link.is_preferred, 'missing': link.missing,
        'promo': {
            'titles': link.promo_titles,
            'until': link.promo_until.isoformat() if link.promo_until else None,
            'deal': deal_text(link),
            'saving': float(link.deal_saving) if link.deal_saving is not None else None,
            'qty': link.deal_qty or 1,
            'verdict': verdict(link),
            'real_percent': link.real_percent,
            'usual_price': float(link.usual_price) if link.usual_price is not None else None,
        } if promo else None,
    }


# ------------------------------------------------------------------ choosing and costing

def pick_link(links, store: str = ''):
    """The product to buy: from the shop's own store when the ingredient has one there, else the preferred
    one, else the cheapest. Missing products and priceless ones come last."""
    usable = [l for l in links if not l.missing and l.price is not None]
    if not usable:
        return None
    if store:
        own = [l for l in usable if l.store == store]
        if own:
            preferred = [l for l in own if l.is_preferred]
            return min(preferred or own, key=lambda l: l.price)
    preferred = [l for l in usable if l.is_preferred]
    return preferred[0] if preferred else min(usable, key=lambda l: l.price)


def need_in_pack_units(amount: Decimal, unit, link: ShoppingLink):
    """How much of the pack's dimension a recipe amount is, or None when units don't compare."""
    if unit is None or not link.pack_amount or not unit.mergeable:
        return None
    if link.pack_dimension == BARE:
        if unit.dimension not in ('mass', 'volume'):
            return None
    elif unit.dimension != link.pack_dimension:
        return None
    return Decimal(amount) * unit.factor


def cost_for_amount(amount: Decimal, unit, link: ShoppingLink) -> Decimal | None:
    """Proportional cost of just this amount (for a recipe's estimate); None if the pack can't be compared."""
    need = need_in_pack_units(amount, unit, link)
    if need is None or link.price is None:
        return None
    return (need / link.pack_amount * link.price).quantize(Decimal('0.01'))


def price_line(amount: Decimal, unit, link: ShoppingLink) -> dict:
    """What buying `amount` costs: whole packs, the saving the current promotion gives on them."""
    need = need_in_pack_units(amount, unit, link)
    exact = need is not None
    packs = max(1, ceil(need / link.pack_amount)) if exact else 1
    cost = (link.price * packs).quantize(Decimal('0.01'))
    saving = Decimal('0')
    if promo_active(link) and link.deal_saving:
        qty = link.deal_qty or 1
        saving = (link.deal_saving * (packs // qty)).quantize(Decimal('0.01'))
    return {'packs': packs, 'cost': cost, 'saving': saving, 'exact': exact}
