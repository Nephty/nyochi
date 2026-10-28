"""Does this app's copy of labauth match the database? Home migrates the lab-auth database; the other apps carry a
synced copy of this package. A copy that is behind (or ahead) would read tables it doesn't know, so the first request
of each process checks the migration names recorded in the database against the copy's own."""

from pathlib import Path

from django.db import DatabaseError, connections, router


def _known():
    folder = Path(__file__).resolve().parent / "migrations"
    return {p.stem for p in folder.glob("[0-9][0-9][0-9][0-9]_*.py")}


def schema_problem():
    """None when fine, else a sentence for the logs and the 503 page."""
    from .models import Community

    alias = router.db_for_read(Community)
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT name FROM django_migrations WHERE app = 'labauth'")
            applied = {row[0] for row in cursor.fetchall()}
    except DatabaseError:
        return "the accounts database is not ready (Home has not migrated it yet)."
    known = _known()
    if known - applied:
        return f"the accounts database misses migrations {sorted(known - applied)}: Home must be deployed first."
    if applied - known:
        return f"this app's labauth copy is older than the database ({sorted(applied - known)}): run scripts/sync_labauth.sh."
    return None
