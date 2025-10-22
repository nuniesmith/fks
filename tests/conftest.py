"""Test configuration for FKS Trading Platform.

This module provides pytest fixtures and configuration for the entire test suite.
"""
import os
import sys
import pytest
from pathlib import Path

# Add src to path for imports
ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

# Django setup - only for integration tests
# Unit tests should not require Django
if os.environ.get("REQUIRE_DJANGO", "false").lower() == "true":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.django.settings")
    import django
    django.setup()


@pytest.fixture
def sample_trading_data():
    """Provide sample trading data for tests."""
    return {
        'symbol': 'BTCUSDT',
        'entry_price': 42000,
        'current_price': 43000,
        'quantity': 1.0,
        'side': 'LONG'
    }


@pytest.fixture
def mock_api_response():
    """Provide mock API response data."""
    return {
        'status': 'success',
        'data': {
            'price': 43000,
            'volume': 1250.5,
            'timestamp': 1634567890
        }
    }


@pytest.fixture(scope='session')
def django_db_setup():
    """Setup Django database for testing."""
    from django.conf import settings
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
