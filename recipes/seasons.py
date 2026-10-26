from django.utils import timezone

MONTHS = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]
MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
STATUSES = ['out', 'early', 'in', 'late']
STATUS_LABELS = {
    'in': 'In season', 'early': 'Early season', 'late': 'Late season',
    'out': 'Out of season', 'unknown': 'Unknown',
}


def current_month() -> int:
    """The month it is in the user's time zone (settings.TIME_ZONE), not UTC."""
    return timezone.localtime().month


SEASON_ORDER = ['in', 'early', 'late', 'out', 'unknown']
SEASON_SHORT = {'in': 'in season', 'early': 'early', 'late': 'late', 'out': 'out', 'unknown': 'unknown'}


def distribution(statuses):
    """[{status, label, short, count, pct}] for a recipe's ingredients, percentages summing to exactly 100
    (largest remainder), zero shares left out, in the order in / early / late / out / unknown."""
    statuses = list(statuses)
    total = len(statuses)
    if not total:
        return []
    counts = {s: statuses.count(s) for s in SEASON_ORDER}
    raw = {s: counts[s] * 100 / total for s in SEASON_ORDER}
    pct = {s: int(raw[s]) for s in SEASON_ORDER}
    for s in sorted(SEASON_ORDER, key=lambda s: raw[s] - pct[s], reverse=True)[:100 - sum(pct.values())]:
        pct[s] += 1
    return [{'status': s, 'label': STATUS_LABELS[s], 'short': SEASON_SHORT[s], 'count': counts[s], 'pct': pct[s]}
            for s in SEASON_ORDER if counts[s]]
