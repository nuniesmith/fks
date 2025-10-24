"""Core app configuration."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Core application configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "FKS Core Framework"

    def ready(self):
        """Import signals and perform app initialization."""
        pass  # Import signals here when needed
