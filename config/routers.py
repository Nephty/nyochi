ACCOUNT_LABELS = {"auth", "sessions", "contenttypes", "admin", "labauth"}


class AccountsRouter:
    """Users, sessions, content types, the admin log and labauth (communities, permissions) live in the lab-auth
    database every house app shares; everything else is this app's own database.

    Home owns the schema of that database (its home-accounts unit migrates it); Nyochi never runs
    `migrate --database accounts` in production (the tests do, on their own copy)."""

    def db_for_read(self, model, **hints):
        return "accounts" if model._meta.app_label in ACCOUNT_LABELS else "default"

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, **hints):
        if app_label in ACCOUNT_LABELS:
            return db == "accounts"
        return db == "default"
