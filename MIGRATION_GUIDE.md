# FKS Platform Migration Guide

**Migration Date**: October 2025  
**Architecture Change**: Microservices → Django Monolith + Celery  
**Status**: Refactor Complete (Phase 9/10)

---

## 📋 Executive Summary

This guide documents the major architectural transformation of the FKS Trading Platform from a microservices architecture to a unified Django monolith with Celery background processing.

### What Changed
- ✅ Removed React frontend (~55,000 lines)
- ✅ Removed 3 microservices: worker/, transformer/, training/ (~160K, 98 files)
- ✅ Consolidated to Django monolith architecture
- ✅ Migrated to Celery 5.5.3 for background tasks
- ✅ Removed legacy code and dead imports (~112K, 50 files)
- ✅ Removed old trading/ module (~380K, 31 files)
- ✅ Kept `src/framework/` as-is (stable, working, provides valuable abstractions)

### What Stayed
- ✅ Django 5.2.7 as core framework
- ✅ PostgreSQL + TimescaleDB for data storage
- ✅ Redis for caching and Celery broker
- ✅ All trading functionality (signals, backtesting, optimization)
- ✅ RAG system with local LLM support
- ✅ Framework utilities (circuit breaker, rate limiter, etc.)

---

## 🗂️ New Project Structure

### Before (Microservices)
```
fks/
├── frontend/           # React app (~55K lines)
├── worker/            # Microservice 1
├── transformer/       # Microservice 2
├── training/          # Microservice 3
├── domain/            # Dead code
├── src/
│   ├── trading/       # Old trading module
│   └── ...
```

### After (Django Monolith)
```
fks/
├── src/
│   ├── core/                    # Core models and utilities
│   ├── config_app/              # Configuration management
│   ├── trading_app/             # Trading logic (NEW)
│   │   ├── models/
│   │   ├── services/
│   │   ├── tasks.py            # 16 Celery tasks
│   │   └── views/
│   ├── api_app/                 # REST API endpoints
│   │   ├── middleware/         # Circuit breaker, rate limiter
│   │   ├── routes/
│   │   └── serializers/
│   ├── web_app/                 # Web interface
│   ├── framework/               # Core abstractions (kept as-is)
│   │   ├── middleware/
│   │   │   ├── circuit_breaker/ # Fault tolerance
│   │   │   ├── rate_limiter/   # API protection
│   │   │   └── metrics/        # Prometheus metrics
│   │   ├── exceptions/         # Custom exception hierarchy
│   │   ├── services/           # Service templates
│   │   ├── config/             # Configuration management
│   │   ├── cache/              # Caching abstraction
│   │   └── lifecycle/          # App lifecycle hooks
│   ├── data/                    # Data management
│   ├── rag/                     # RAG system
│   ├── forecasting/             # Forecasting models
│   ├── chatbot/                 # Chatbot interface
│   ├── engine/                  # Core engine
│   └── infrastructure/          # Infrastructure services
├── manage.py                    # Django CLI
├── docker-compose.yml           # Service orchestration
└── requirements.txt             # Python dependencies
```

---

## 🔄 Breaking Changes

### 1. Import Path Changes

#### Trading Module Imports
**OLD:**
```python
from trading.services import TradingService
from trading.models import Trade
from trading.signals import SignalGenerator
```

**NEW:**
```python
from trading_app.services import TradingService
from trading_app.models import Trade
from trading_app.signals import SignalGenerator
```

#### Celery Task Names
**OLD:**
```python
from trading.tasks import execute_trade
execute_trade.delay(trade_id)
```

**NEW:**
```python
from trading_app.tasks import execute_trade
# Task name in Celery: 'trading_app.tasks.execute_trade'
execute_trade.delay(trade_id)
```

### 2. Django Settings Changes

#### INSTALLED_APPS
**OLD:**
```python
INSTALLED_APPS = [
    'trading',           # Old module
    'worker',           # Microservice
    'transformer',      # Microservice
    'training',         # Microservice
    # ...
]
```

**NEW:**
```python
INSTALLED_APPS = [
    'trading_app',      # New consolidated module
    'api_app',
    'web_app',
    'config_app',
    'core',
    'data',
    'rag',
    'forecasting',
    'chatbot',
    'engine',
    # ...
]
```

### 3. Celery Task Registry

All 16 critical Celery tasks have been migrated to `trading_app.tasks`:

| Old Task Name | New Task Name | Purpose |
|--------------|---------------|---------|
| `trading.tasks.execute_trade` | `trading_app.tasks.execute_trade` | Execute a trade |
| `trading.tasks.update_market_data` | `trading_app.tasks.update_market_data` | Fetch market data |
| `trading.tasks.generate_signals` | `trading_app.tasks.generate_signals` | Generate trading signals |
| `trading.tasks.run_backtest` | `trading_app.tasks.run_backtest` | Run strategy backtest |
| `trading.tasks.optimize_strategy` | `trading_app.tasks.optimize_strategy` | Optimize parameters |
| `trading.tasks.calculate_portfolio_metrics` | `trading_app.tasks.calculate_portfolio_metrics` | Portfolio analytics |
| `trading.tasks.send_discord_notification` | `trading_app.tasks.send_discord_notification` | Discord alerts |
| `trading.tasks.cleanup_old_data` | `trading_app.tasks.cleanup_old_data` | Data maintenance |
| `trading.tasks.sync_exchange_balances` | `trading_app.tasks.sync_exchange_balances` | Balance sync |
| `trading.tasks.update_position_status` | `trading_app.tasks.update_position_status` | Position tracking |
| `trading.tasks.calculate_risk_metrics` | `trading_app.tasks.calculate_risk_metrics` | Risk analytics |
| `trading.tasks.process_webhook` | `trading_app.tasks.process_webhook` | Webhook processing |
| `trading.tasks.archive_old_logs` | `trading_app.tasks.archive_old_logs` | Log management |
| `trading.tasks.health_check` | `trading_app.tasks.health_check` | System health |
| `trading.tasks.refresh_cache` | `trading_app.tasks.refresh_cache` | Cache warming |
| `trading.tasks.generate_daily_report` | `trading_app.tasks.generate_daily_report` | Daily reports |

### 4. API Endpoints

API structure remains the same, but internal routing updated:

**Endpoints (unchanged):**
- `GET /api/v1/trades/` - List trades
- `POST /api/v1/trades/` - Create trade
- `GET /api/v1/signals/` - List signals
- `POST /api/v1/backtest/` - Run backtest

**Internal routing now uses:**
- `api_app.routes.*` for endpoint definitions
- `trading_app.services.*` for business logic
- `trading_app.tasks.*` for async operations

### 5. Framework Components

**Decision: Kept As-Is** (Phase 9D Analysis)

The `src/framework/` directory (64 files, 928K) was kept because:
- Provides stable, valuable abstractions
- 26 external imports across critical paths
- No blocking issues for deployment
- Migration would be 2-3 hours with MEDIUM-HIGH risk for LOW benefit

**Available Framework Components:**
```python
# Circuit breaker for fault tolerance
from framework.middleware.circuit_breaker import CircuitBreaker

# Rate limiting for API protection
from framework.middleware.rate_limiter import RateLimiter

# Custom exceptions
from framework.exceptions import ValidationError, ServiceError

# Service templates
from framework.services import BaseService, ServiceRegistry

# Configuration management
from framework.config import ConfigManager

# Caching
from framework.cache import CacheBackend

# Metrics
from framework.middleware.metrics import PrometheusMetrics
```

---

## 🚀 Migration Steps for Developers

### 1. Update Local Environment

```bash
# Pull latest refactor branch
git fetch origin
git checkout refactor
git pull origin refactor

# Rebuild Docker containers
docker compose down
docker compose build --no-cache
docker compose up -d

# Run migrations
docker compose exec web python manage.py migrate

# Verify Celery tasks
docker compose exec web python manage.py shell
>>> from trading_app import tasks
>>> dir(tasks)  # Should show all 16 tasks
```

### 2. Update Code References

**Search and Replace:**
```bash
# Find old trading imports
grep -r "from trading\." src/

# Find old trading task calls
grep -r "trading\.tasks\." src/

# Replace with new paths
# trading.* → trading_app.*
```

### 3. Update Tests

```python
# OLD
from trading.services import TradingService
from trading.tasks import execute_trade

# NEW
from trading_app.services import TradingService
from trading_app.tasks import execute_trade
```

### 4. Verify Celery Configuration

```python
# Check settings.py or celery.py
CELERY_IMPORTS = [
    'trading_app.tasks',
    'api_app.tasks',
    # ... other task modules
]

# Task routing (if needed)
CELERY_TASK_ROUTES = {
    'trading_app.tasks.*': {'queue': 'trading'},
    'api_app.tasks.*': {'queue': 'api'},
}
```

---

## 🧪 Testing Guide

### Running Tests Locally

**Note:** Full testing deferred to deployment environment due to:
- 130+ dependencies (uwsgi, pandas, numpy, scikit-learn)
- Windows incompatibility (uwsgi)
- Large ML libraries (~5-10GB)

### Recommended Testing Approach

1. **Deploy to Docker/Linux staging environment**
2. **Run full test suite:**
   ```bash
   # Inside Docker container
   pytest tests/ -v --cov
   ```

3. **Verify Celery tasks:**
   ```bash
   # Check task registration
   celery -A fks_project inspect registered
   
   # Should see:
   # trading_app.tasks.execute_trade
   # trading_app.tasks.update_market_data
   # ... (all 16 tasks)
   ```

4. **Test API endpoints:**
   ```bash
   # Health check
   curl http://localhost:8000/api/health/
   
   # List trades
   curl http://localhost:8000/api/v1/trades/
   ```

5. **Monitor for errors:**
   ```bash
   # Check logs
   docker compose logs web
   docker compose logs celery_worker
   
   # Check Flower UI
   open http://localhost:5555
   ```

---

## 📊 Migration Statistics

### Code Removed
| Phase | Description | Files | Size | Lines (est) |
|-------|-------------|-------|------|-------------|
| 1 | React Frontend | 35+ | 55K | ~55,000 |
| 9A | Microservices (worker, transformer, training) | 98 | 160K | ~3,553 |
| 9B | Dead Code (domain, pipelines) | 50 | 112K | ~3,055 |
| 9C | Old trading/ module | 31 | 380K | ~15,000 |
| **Total** | **All Removed** | **214** | **707K** | **~76,608** |

### Code Kept
- **Django Apps**: 10 apps (core, config_app, trading_app, api_app, web_app, data, rag, forecasting, chatbot, engine)
- **Framework**: 64 files, 928K (circuit breaker, rate limiter, exceptions, services, config, cache, lifecycle, metrics)
- **Tests**: 69+ test cases
- **Infrastructure**: Docker, Celery, Redis, PostgreSQL

### Architecture Metrics
- **Before**: Microservices + React + Django (214 files to be removed)
- **After**: Django Monolith + Celery (streamlined)
- **Commits**: 34+ on refactor branch
- **Phases Complete**: 9/10 (90%)

---

## 🔧 Common Issues & Solutions

### Issue 1: Import Errors

**Symptom:**
```
ImportError: No module named 'trading'
```

**Solution:**
Update imports to use `trading_app`:
```python
from trading_app.models import Trade
from trading_app.services import TradingService
```

### Issue 2: Celery Tasks Not Found

**Symptom:**
```
celery.exceptions.NotRegistered: 'trading.tasks.execute_trade'
```

**Solution:**
Update task calls to use new names:
```python
from trading_app.tasks import execute_trade
execute_trade.delay(trade_id)
```

### Issue 3: INSTALLED_APPS Configuration

**Symptom:**
```
django.core.exceptions.ImproperlyConfigured: App 'trading' not found
```

**Solution:**
Update `settings.py`:
```python
INSTALLED_APPS = [
    # Remove: 'trading', 'worker', 'transformer', 'training'
    # Add:
    'trading_app',
    'api_app',
    'web_app',
    'config_app',
    # ...
]
```

### Issue 4: Database Migrations

**Symptom:**
```
django.db.migrations.exceptions.InconsistentMigrationHistory
```

**Solution:**
```bash
# Reset migrations if needed (development only!)
docker compose exec web python manage.py migrate --fake trading_app zero
docker compose exec web python manage.py migrate trading_app
```

---

## 📚 Additional Resources

- **Phase 9 Complete**: `docs/PHASE9_FINAL_SUMMARY.md`
- **Framework Analysis**: `docs/PHASE9D_FRAMEWORK_ANALYSIS.md`
- **Testing Summary**: `docs/PHASE9C_TESTING_SUMMARY.md`
- **Quick Start**: `docs/QUICKSTART.md`
- **Architecture Overview**: `docs/SYSTEM_OVERVIEW.txt`
- **RAG Setup**: `docs/RAG_SETUP_GUIDE.md`

---

## 🎯 Next Steps

1. **Deploy to Staging**: Test in Docker/Linux environment
2. **Run Full Test Suite**: Verify all 16 Celery tasks
3. **Monitor Performance**: Check logs and metrics
4. **Update Documentation**: Keep guides current
5. **Train Team**: Ensure everyone understands new structure

---

## 📞 Support

For questions or issues:
1. Check `docs/` directory for detailed documentation
2. Review commit history on `refactor` branch
3. Check Celery logs: `docker compose logs celery_worker`
4. Check Django logs: `docker compose logs web`

---

**Migration Complete** ✅  
**Status**: Ready for deployment testing  
**Branch**: `refactor` (34+ commits)
