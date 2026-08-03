HUB_LABELS = {"auth", "sessions", "contenttypes", "admin"}


class HubRouter:
    """Route auth/sessions/contenttypes to the hub DB; everything else to default."""

    def db_for_read(self, model, **hints):
        if model._meta.app_label in HUB_LABELS:
            return "hub"
        return "default"

    def db_for_write(self, model, **hints):
        if model._meta.app_label in HUB_LABELS:
            return "hub"
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, **hints):
        if app_label in HUB_LABELS:
            return db == "hub"
        return db == "default"
