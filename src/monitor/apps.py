"""Monitor app configuration."""

from django.apps import AppConfig


class MonitorConfig(AppConfig):
    """Configuration for the monitor app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "monitor"
    verbose_name = "FKS Service Monitor"

    def ready(self):
        """Import signals when app is ready."""
        # Import signals or tasks here if needed
        pass
