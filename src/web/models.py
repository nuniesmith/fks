"""Web UI models.

Note: The web UI Django app primarily uses models from other apps for data access:
- authentication/models.py - User authentication and authorization
- trading/models.py - Trading strategies, signals, backtests
- core/database/models.py - Core trading entities (SQLAlchemy-based)

This file is reserved for web UI-specific models (e.g., UI preferences, dashboards, 
saved views) that don't belong in the core domain models.
"""

from django.db import models  # noqa: F401

# Web UI-specific models will be added here as needed
