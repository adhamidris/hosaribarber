from django.apps import AppConfig


class AuditlogConfig(AppConfig):
    name = "auditlog"

    def ready(self):
        import auditlog.signals  # noqa: F401
