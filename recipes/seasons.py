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
