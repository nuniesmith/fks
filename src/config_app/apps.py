"""Configuration app configuration."""
from django.apps import AppConfig


class ConfigAppConfig(AppConfig):
    """Configuration management application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'config_app'
    verbose_name = 'FKS Configuration Management'

    def ready(self):
        """Initialize configuration on app ready."""
        pass  # Load config here when needed
