# FKS Project Architecture Review & Recommendations

## Current Structure Analysis

### ❌ Critical Issues

#### 1. **File/Module Name Conflicts**
You have BOTH files AND directories with the same names in `src/`:

```
src/
├── config.py          ❌ CONFLICT
├── config/            ❌ CONFLICT
│   ├── __init__.py
│   └── ...
├── data.py            ❌ CONFLICT  
├── data/              ❌ CONFLICT
│   ├── __init__.py
│   └── ...
```

**Problem**: Python will be confused about whether to import the file or the package. This causes unpredictable behavior.

#### 2. **Non-Django Files in Django Root**
Your `src/` directory mixes legacy standalone scripts with Django apps:

```
src/
├── app.py              ❌ Streamlit app (not Django)
├── backtest.py         ❌ Standalone module
├── cache.py            ❌ Standalone module
├── config.py           ❌ Standalone module
├── data.py             ❌ Standalone module
├── database.py         ❌ Standalone module
├── db_utils.py         ❌ Standalone module
├── signals.py          ❌ Standalone module
├── utils.py            ❌ Standalone module
├── optimizer.py        ❌ Standalone module
├── websocket_service.py ❌ Standalone service
├── data_sync_service.py ❌ Standalone service
│
└── fks_project/        ✅ Django project
    ├── settings.py
    └── ...
```

#### 3. **Wildcard Imports in `__init__.py`**
```python
from config import *
from database import *
from cache import *
```
This is an anti-pattern that pollutes the namespace and makes debugging difficult.

#### 4. **Duplicated Functionality**
- `data.py` and `data/` both handle data operations
- `config.py` and `config/` both handle configuration
- `cache.py` and `core/cache/` both handle caching
- Multiple database modules: `database.py`, `db_utils.py`, `infrastructure/database/`

---

## 🎯 Recommended Structure

### Option A: Full Django Migration (Recommended)

Organize everything as Django apps:

```
fks/
├── manage.py
├── docker-compose.yml
├── requirements.txt
│
├── src/
│   ├── fks_project/          # Django project settings
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   ├── asgi.py
│   │   └── celery.py
│   │
│   ├── core/                 # Core models & utilities (existing)
│   │   ├── models.py         # Base models: Account, User, etc.
│   │   ├── cache/
│   │   ├── exceptions/
│   │   ├── utils/
│   │   └── registry.py
│   │
│   ├── trading/              # Trading app (existing)
│   │   ├── models.py         # Position, Trade, Strategy
│   │   ├── services/         # NEW: Business logic
│   │   │   ├── __init__.py
│   │   │   ├── backtest_service.py     # Move backtest.py here
│   │   │   ├── signal_service.py       # Move signals.py here
│   │   │   ├── optimizer_service.py    # Move optimizer.py here
│   │   │   └── execution_service.py
│   │   ├── tasks.py          # Celery tasks
│   │   ├── admin.py
│   │   ├── urls.py           # NEW: Create URLs
│   │   ├── views.py          # NEW: Create views
│   │   ├── backtest/         # Keep existing
│   │   ├── engine/           # Keep existing
│   │   ├── execution/        # Keep existing
│   │   ├── indicators/       # Keep existing
│   │   ├── signals/          # Keep existing
│   │   └── strategies/       # Keep existing
│   │
│   ├── market_data/          # NEW: Dedicated data app
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py         # OHLCVData, SyncStatus
│   │   ├── admin.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── data_service.py        # Move data.py logic
│   │   │   ├── sync_service.py        # Move data_sync_service.py
│   │   │   └── websocket_service.py   # Move websocket_service.py
│   │   ├── tasks.py          # Data sync Celery tasks
│   │   ├── adapters/         # Move from data/adapters/
│   │   │   ├── binance.py
│   │   │   ├── oanda.py
│   │   │   └── polygon.py
│   │   └── utils/
│   │       └── db_operations.py       # Move db_utils.py
│   │
│   ├── api/                  # REST API (existing)
│   │   ├── routes/
│   │   ├── serializers/      # NEW: Create DRF serializers
│   │   ├── middleware/
│   │   └── urls.py
│   │
│   ├── web/                  # Web UI (existing)
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/
│   │   └── static/
│   │
│   ├── rag/                  # RAG system (existing)
│   │   ├── models.py         # Document, DocumentChunk
│   │   ├── services/
│   │   │   ├── intelligence_service.py
│   │   │   ├── ingestion_service.py
│   │   │   └── retrieval_service.py
│   │   └── urls.py
│   │
│   ├── infrastructure/       # Keep as-is (existing)
│   │   ├── database/
│   │   ├── external/
│   │   └── messaging/
│   │
│   └── framework/            # Keep as-is (existing)
│       ├── cache/
│       ├── config/
│       ├── middleware/
│       └── services/
│
├── scripts/                  # Standalone scripts (existing)
│   ├── data_sync_runner.py   # NEW: Runner for data_sync_service
│   ├── websocket_runner.py   # NEW: Runner for websocket_service
│   └── ...
│
├── legacy/                   # NEW: Move legacy files here
│   ├── streamlit_app.py      # Move app.py
│   ├── standalone_backtest.py
│   └── README.md             # Document migration status
│
└── docs/
    └── architecture/
        ├── apps_overview.md
        ├── data_flow.md
        └── service_architecture.md
```

---

## 📋 Migration Plan

### Phase 1: Resolve Conflicts (Critical - Do First)

1. **Rename conflicting files:**
   ```bash
   mv src/config.py src/legacy_config.py
   mv src/data.py src/legacy_data.py
   mv src/database.py src/legacy_database.py
   mv src/cache.py src/legacy_cache.py
   ```

2. **Create `legacy/` directory:**
   ```bash
   mkdir -p legacy
   mv src/app.py legacy/streamlit_app.py
   mv src/backtest.py legacy/standalone_backtest.py
   mv src/signals.py legacy/standalone_signals.py
   mv src/optimizer.py legacy/standalone_optimizer.py
   ```

3. **Update `src/__init__.py`:**
   ```python
   # src/__init__.py
   """
   FKS Trading Platform
   Django-based monolith with modular apps
   """
   
   __version__ = "2.0.0"
   
   # Don't use wildcard imports - let Django's app registry handle imports
   ```

### Phase 2: Create Django Apps

1. **Create `market_data` app:**
   ```bash
   cd src
   django-admin startapp market_data
   ```

2. **Move functionality:**
   - `legacy_data.py` → `market_data/services/data_service.py`
   - `data_sync_service.py` → `market_data/services/sync_service.py`
   - `websocket_service.py` → `market_data/services/websocket_service.py`
   - `db_utils.py` → `market_data/utils/db_operations.py`

3. **Create services in `trading/`:**
   ```bash
   mkdir -p src/trading/services
   # Move logic from standalone files to services
   ```

### Phase 3: Update Django Settings

Update `fks_project/settings.py`:

```python
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'rest_framework',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    
    # FKS apps
    'core.apps.CoreConfig',
    'trading.apps.TradingAppConfig',
    'market_data.apps.MarketDataConfig',  # NEW
    'api.apps.ApiAppConfig',
    'web.apps.WebAppConfig',
    'rag.apps.RagConfig',
    'forecasting.apps.ForecastingConfig',
    'chatbot.apps.ChatbotConfig',
]
```

### Phase 4: Create Service Layer

Each Django app should have a `services/` directory for business logic:

```python
# src/trading/services/__init__.py
from .backtest_service import BacktestService
from .signal_service import SignalService
from .optimizer_service import OptimizerService

__all__ = ['BacktestService', 'SignalService', 'OptimizerService']

# src/trading/services/backtest_service.py
class BacktestService:
    """Handles backtesting logic (moved from backtest.py)"""
    
    def __init__(self):
        pass
    
    def run_backtest(self, df_prices, M, atr_period=14, ...):
        """Run backtest with given parameters"""
        # Move logic from backtest.py here
        pass
```

### Phase 5: Update Celery Tasks

Update `trading/tasks.py` to use services:

```python
# src/trading/tasks.py
from celery import shared_task
from .services import BacktestService, SignalService

@shared_task
def run_scheduled_backtest(strategy_id):
    """Run backtest for strategy"""
    service = BacktestService()
    return service.run_backtest(...)

@shared_task
def update_signals():
    """Update trading signals"""
    service = SignalService()
    return service.generate_signals()
```

---

## 🎨 Design Principles Applied

### 1. **Single Responsibility**
Each Django app has ONE clear purpose:
- `core` - Shared models and utilities
- `trading` - Trading strategies and execution
- `market_data` - Data fetching and storage
- `api` - REST API endpoints
- `web` - Web interface
- `rag` - AI intelligence

### 2. **Dependency Inversion**
```
High-level modules (views, tasks)
         ↓
    Services (business logic)
         ↓
Low-level modules (models, utils)
```

### 3. **Don't Repeat Yourself (DRY)**
Consolidate duplicated functionality:
- One data service (not data.py + data/)
- One config system (not config.py + config/)
- One cache system (use framework/cache/)

### 4. **Separation of Concerns**
```
Presentation Layer:   views.py, templates/
Business Logic Layer: services/
Data Access Layer:    models.py, utils/
Infrastructure:       infrastructure/, framework/
```

---

## 🔧 Quick Fixes to Apply Now

### 1. Fix the `__init__.py` wildcard imports:

```python
# src/__init__.py (current - BAD)
from config import *  # ❌
from database import *  # ❌

# src/__init__.py (improved)
"""FKS Trading Platform"""
__version__ = "2.0.0"
```

### 2. Rename conflicting files immediately:

```bash
# Run these commands NOW to prevent import confusion
cd /mnt/c/Users/jordan/nextcloud/code/repos/fks/src
mv config.py _legacy_config.py
mv data.py _legacy_data.py  
mv database.py _legacy_database.py
mv cache.py _legacy_cache.py
```

### 3. Create a services directory in trading:

```bash
mkdir -p src/trading/services
touch src/trading/services/__init__.py
```

---

## 📊 Benefits of This Restructure

### Before (Current)
- ❌ File/module conflicts causing import errors
- ❌ Mixing standalone scripts with Django apps
- ❌ Duplicated functionality across modules
- ❌ Unclear separation of concerns
- ❌ Difficult to test and maintain

### After (Proposed)
- ✅ Clean Django app structure
- ✅ Clear separation of concerns
- ✅ Service layer for reusable business logic
- ✅ Easy to test (mock services)
- ✅ Follows Django best practices
- ✅ Scalable and maintainable
- ✅ Clear dependency flow

---

## 🎯 Priority Order

1. **IMMEDIATE** (Today):
   - Fix `__init__.py` wildcard imports
   - Rename conflicting files
   - Create `market_data` Django app

2. **SHORT TERM** (This Week):
   - Move data sync logic to `market_data` app
   - Create service layer in `trading` app
   - Update Celery tasks to use services

3. **MEDIUM TERM** (Next 2 Weeks):
   - Migrate all standalone scripts
   - Create comprehensive tests
   - Update documentation

4. **LONG TERM** (Next Month):
   - Remove all legacy files
   - Complete API documentation
   - Performance optimization

---

## 📝 Next Immediate Steps

1. Read this document
2. Decide on migration approach
3. Start with Phase 1 (resolve conflicts)
4. Create a git branch: `git checkout -b refactor/django-apps`
5. Make changes incrementally
6. Test after each change
7. Commit frequently

---

## 🤔 Questions to Consider

1. **Do you still need the Streamlit app (`app.py`)?**
   - If yes → Move to `legacy/` and keep as standalone
   - If no → Remove it

2. **Are the standalone services still needed?**
   - `data_sync_service.py` - Should be a Django management command
   - `websocket_service.py` - Should be a Django management command

3. **What's the timeline for migration?**
   - Can do it gradually (recommended)
   - Or all at once (risky)

---

## 📚 References

- [Django App Structure Best Practices](https://docs.djangoproject.com/en/5.2/intro/reusable-apps/)
- [Service Layer Pattern](https://martinfowler.com/eaaCatalog/serviceLayer.html)
- [Django Project Structure](https://github.com/cookiecutter/cookiecutter-django)

---

**Status**: Draft for Review
**Date**: October 17, 2025
**Version**: 1.0
