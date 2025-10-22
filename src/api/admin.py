"""API admin interfaces.

Note: This app is part of the legacy FastAPI implementation being migrated to Django.
Admin interfaces for core functionality are now located in the respective Django apps:
- authentication/admin.py - User and API key management
- trading/admin.py - Trading strategies and signals
- core/admin.py - Core trading entities

This file is retained for backward compatibility during the migration phase.
"""

from django.contrib import admin  # noqa: F401

# Legacy API admin registration will be removed after migration is complete
