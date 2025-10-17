"""
FKS Trading Platform Test Suite
================================

Unified test directory structure for all project tests.

## Directory Structure

- `unit/` - Unit tests for individual components
  - `test_core/` - Tests for core utilities and base classes
  - `test_config/` - Tests for configuration management
  - `test_trading/` - Tests for trading strategies and indicators
  - `test_api/` - Tests for API middleware and routes
  - `test_web/` - Tests for web views and templates

- `integration/` - Integration tests for component interactions
  - `test_data/` - Tests for data adapters and repositories
  - `test_backtest/` - Tests for backtesting engine
  - `test_execution/` - Tests for trade execution workflows
  - `test_api_integration/` - Tests for API endpoint integration

- `fixtures/` - Shared test fixtures and mock data
  - Sample trading data
  - Mock API responses
  - Test database fixtures

## Running Tests

### Run all tests:
```bash
pytest tests/
```

### Run specific test category:
```bash
pytest tests/unit/
pytest tests/integration/
```

### Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

### Run specific test file:
```bash
pytest tests/unit/test_core/test_exceptions.py
```

## Test Organization

Tests are organized by application and test type:
- Unit tests focus on isolated component functionality
- Integration tests verify component interactions
- All tests use pytest fixtures from conftest.py

## Import Patterns

Tests should import from the new app structure:
```python
from core.exceptions import FKSException
from trading_app.strategies import BaseStrategy
from config_app.manager import ConfigManager
from api_app.middleware.auth import AuthMiddleware
```

## Migration Notes

Tests have been consolidated from:
- `src/tests/` - General tests
- `src/data/tests/` - Data adapter tests
- `src/engine/tests/` - Engine tests
- `scripts/` - Smoke tests and QA scripts

All import paths have been updated to use the new app structure.
