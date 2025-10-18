"""Trading app configuration."""

from django.apps import AppConfig


class TradingAppConfig(AppConfig):
    """Trading strategies, backtesting, and execution."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "trading"  # Fixed: was 'trading_app' but directory is 'trading'
    verbose_name = "FKS Trading System"

    def ready(self):
        """Initialize trading system on app ready."""
        pass  # Register strategies/indicators here when needed
