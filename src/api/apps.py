"""API app configuration."""

from django.apps import AppConfig


class ApiAppConfig(AppConfig):
    """REST API endpoints and middleware."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"  # Fixed: was 'api_app' but directory is 'api'
    verbose_name = "FKS REST API"

    def ready(self):
        """Initialize API on app ready."""
        pass  # Register API routes here when needed
