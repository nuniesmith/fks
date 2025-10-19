"""API models.

Note: This app is part of the legacy FastAPI implementation being migrated to Django.
Django ORM models for core functionality are now located in the respective Django apps:
- authentication/models.py - User, APIKey, Session models
- trading/models.py - Strategy, Signal, Backtest models
- core/models.py - Account, Trade, Position models (SQLAlchemy-based)

This file is retained for backward compatibility during the migration phase.
"""

from django.db import models  # noqa: F401

# Legacy API models will be removed after migration is complete
