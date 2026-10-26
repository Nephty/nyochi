ACCOUNT_LABELS = {"auth", "sessions", "contenttypes", "admin"}


class AccountsRouter:
    """Users, sessions, content types and the admin log live in the accounts database that Nyochi shares with
    Shopping (one login for both, not the hub); everything else is this app's own database.

    Shopping owns the schema of that database (it runs `migrate --database accounts`); Nyochi never does."""

    def db_for_read(self, model, **hints):
        return "accounts" if model._meta.app_label in ACCOUNT_LABELS else "default"

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, **hints):
        if app_label in ACCOUNT_LABELS:
            return db == "accounts"
        return db == "default"
