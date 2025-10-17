# FKS Trading Platform - AI Coding Agent Instructions

## Project Overview
**Django 5.2.7 monolith** trading platform with PostgreSQL+TimescaleDB, Redis, Celery 5.5.3, and AI-powered RAG system for intelligent trading insights. Recently migrated from microservices to monolith (Oct 2025). **Currently in local development** - focus on building core functionality with comprehensive testing before deployment.

### Current Phase: Local Development & Testing
- **Goal**: Build working FKS Intelligence system with RAG to generate optimal trading signals
- **Priority**: Django migration, web UI development, comprehensive test coverage, GitHub Actions CI
- **Status**: Core models exist, tasks are stubs, web interface needs HTML/CSS work
- **Not Yet**: Production deployment, NinjaTrader integration (post-working app)

## Architecture Essentials

### Django App Structure (`src/`)
The codebase uses **directory-based Django apps** under `src/`:
- `authentication/` - User auth with API keys, session tracking, rate limiting
- `core/` - Base models (Account, Trade, Position) and database utilities
- `trading/` - Trading strategies, signals, backtesting, Celery tasks
- `api/` - REST API routes using FastAPI (legacy, being migrated)
- `web/` - Django templates, views, forms (Bootstrap 5 UI)
- `framework/` - **64 files, 928KB** of reusable abstractions (circuit breaker, rate limiter, exceptions, services, config, caching, lifecycle, metrics). **NEVER modify without explicit analysis** - heavily imported across codebase.

**Django settings path**: `src/web/django/settings.py`  
**URL routing**: `src/web/django/urls.py`  
**Celery config**: `src/web/django/celery.py`  
**Entry point**: `src/manage.py`

### Service Architecture (docker-compose.yml)
```yaml
nginx (80/443) → web (Django+Gunicorn:8000)
                 ├── db (TimescaleDB+pgvector:5432)
                 ├── redis (6379) → celery_worker/celery_beat
                 ├── pgadmin (5050)
                 └── flower (5555)
```

**GPU stack** (`docker-compose.gpu.yml`): Adds `rag_service` (8001) + `ollama` (11434) for local LLM.

### Database Models
- **Core**: `src/core/database/models.py` - SQLAlchemy models with TimescaleDB hypertables
- **Django**: Apps define Django ORM models (e.g., `authentication/models.py`, `trading/models.py`)
- **Dual ORM**: Legacy SQLAlchemy coexists with Django ORM during migration

### Celery Tasks
Located in `src/trading/tasks.py`. Use `@shared_task` decorator. Tasks are **currently stubs** - implementations needed for:
- Market data sync from Binance
- Signal generation (RSI, MACD, Bollinger Bands, etc.)
- Backtesting execution
- Position updates and portfolio rebalancing
- RAG-powered intelligence queries

Beat schedule in `src/web/django/celery.py` is commented out until implementations complete.

## FKS Intelligence System (RAG-Powered)

### Purpose & Goals
The RAG system provides **AI-powered trading intelligence** to:
- Generate optimal daily trading signals based on market conditions
- Track all trading activity with context-aware analysis
- Continuously optimize strategies based on account balance and available cash
- Learn from historical trades to improve recommendations

### RAG Architecture
```
Trading Data → Document Processor → pgvector (embeddings)
                                          ↓
User Query → Retrieval Service → Context + LLM → Trading Insights
```

**Key Components**:
- **Embeddings**: `sentence-transformers` for local inference (GPU-accelerated)
- **Vector Store**: pgvector extension in PostgreSQL for semantic search
- **LLM**: Ollama + llama.cpp with CUDA support for zero-cost inference
- **Auto-Ingestion**: Signals, backtests, trades, positions automatically indexed

### RAG Integration Points
```python
# Example: Query RAG for trading recommendations
from rag.services import IntelligenceOrchestrator

orchestrator = IntelligenceOrchestrator()
recommendation = orchestrator.get_trading_recommendation(
    symbol="BTCUSDT",
    account_balance=10000.00,
    context="current market conditions"
)
```

**When to Use RAG**:
- Generating daily trading signals
- Portfolio optimization decisions
- Strategy parameter tuning
- Risk assessment for new positions

## Developer Workflows

### Starting Services (Local Development)
```bash
make up              # Standard stack (no GPU)
make gpu-up          # With GPU/RAG/LLM support
make logs            # Follow all logs
make down            # Stop everything
make restart         # Restart services
```

**Access Points**:
- Web UI: http://localhost:8000
- **Health Dashboard: http://localhost:8000/health/dashboard/**
- Django Admin: http://localhost:8000/admin
- **Grafana: http://localhost:3000** (admin/admin)
- **Prometheus: http://localhost:9090**
- PgAdmin: http://localhost:5050
- Flower (Celery): http://localhost:5555
- RAG API: http://localhost:8001 (GPU mode only)

### Database Operations
```bash
make migrate         # Run Django migrations
make shell           # Django shell (access ORM)
make db-shell        # Direct psql access
docker-compose exec db psql -U postgres -d trading_db
```

### Testing (Critical for Solo Development)
```bash
pytest src/tests/ -v --cov=src           # All tests with coverage
pytest src/tests/test_assets.py -v      # Specific file
pytest -m "not slow"                     # Skip slow tests
pytest -m unit                           # Unit tests only
pytest -m integration                    # Integration tests only
```

**Test config**: `pytest.ini` (marks: unit, integration, slow, data, backtest, trading, api, web)

**GitHub Actions CI**: `.github/workflows/ci-cd.yml` runs tests on push/PR
- Always run tests locally before committing
- CI catches issues early for solo development
- Coverage reports help identify untested code

### Code Quality
```bash
make lint            # ruff, mypy, black
make format          # black, isort
```
**Config**: `ruff.toml` for linting rules

### Web UI Development
**Templates**: `src/web/templates/` - Django templates with Bootstrap 5
**Static files**: `src/web/static/` - CSS, JavaScript, images
**Forms**: `src/web/forms.py` - Django forms for user input
**Views**: `src/web/views/` - View logic for rendering pages

**Workflow**:
1. Create/modify templates in `src/web/templates/`
2. Add CSS in `src/web/static/css/`
3. Run `make up` to see changes
4. Use Django template tags for dynamic content
5. Leverage Bootstrap 5 classes for responsive design

## Project-Specific Conventions

### Import Patterns
- **Framework imports**: `from framework.middleware.circuit_breaker import CircuitBreaker`
- **Core models**: `from core.database.models import Trade, Position`
- **Django apps**: `from authentication.models import User`
- **Avoid**: Importing from `infrastructure/` or `services/` - legacy modules being phased out

### Exception Hierarchy
All custom exceptions inherit from `FKSException` in `src/core/exceptions/__init__.py`:
- `TradingError`, `DataError`, `ModelError`, `ConfigError`, `CircuitBreakerError`, `RateLimitError`, etc.
- Use specific exceptions, not generic `Exception`

### Configuration
- **Django**: Environment variables via `.env` → `src/web/django/settings.py`
- **Framework**: `src/framework/config/` - Type-safe dataclasses (DatabaseConfig, TradingConfig, MLConfig, etc.)
- **Never hardcode**: API keys, secrets, DB credentials

### Middleware Usage
**Circuit Breaker**: `src/framework/middleware/circuit_breaker/core.py`
```python
from framework.middleware.circuit_breaker import CircuitBreaker
cb = CircuitBreaker(name="binance_api", failure_threshold=5, timeout=60)
```

**Rate Limiter**: `src/framework/middleware/rate_limiter/core.py`
```python
from framework.middleware.rate_limiter import RateLimiter
limiter = RateLimiter(max_requests=100, window=60)
```

### Script System (`scripts/`)
**Modular Bash scripts** for deployment/maintenance. Use `scripts/main.sh` as orchestrator:
- `core/` - Config, logging, validation
- `docker/` - Docker operations
- `deployment/` - Deployment automation (not currently used in local dev)

**Never run**: Monolithic `run.sh` or deprecated scripts in `scripts/archive/`

**Note**: Focus is on local development - deployment scripts exist but aren't priority yet.

## Critical Integration Points

### TimescaleDB + pgvector
- Hypertables for time-series data (trades, market data)
- pgvector for RAG embeddings
- Extensions loaded via: `postgres -c shared_preload_libraries='timescaledb,vector'`

### RAG System (GPU Stack)
- **Embeddings**: `sentence-transformers` (local) + OpenAI fallback
- **Vector store**: pgvector in PostgreSQL
- **LLM**: Ollama/llama.cpp with CUDA acceleration
- **Document ingestion**: Auto-ingests signals, backtests, trades
- **Purpose**: Powers FKS Intelligence for optimal daily trading recommendations

### Discord Integration
- Trade notifications via webhook (`DISCORD_WEBHOOK_URL` env var)
- Located in `src/` (exact location TBD during migration)

### Monitoring Stack
- **Health Dashboard**: `http://localhost:8000/health/dashboard/` - Single-pane view of all services, issues, next steps
- **Prometheus**: `http://localhost:9090` - Metrics collection (system, DB, Redis, Celery)
- **Grafana**: `http://localhost:3000` - Visualization dashboards
- **Exporters**: node-exporter (system), postgres-exporter, redis-exporter
- **Configuration**: `monitoring/prometheus/prometheus.yml`, `monitoring/grafana/`

### Tailscale VPN
- **Purpose**: Secure remote access to local dev environment
- **Setup**: Add `TAILSCALE_AUTH_KEY` to `.env` from https://login.tailscale.com/admin/settings/keys
- **DNS**: Point public DNS records to Tailscale IP for secure external access
- **Access**: Use Tailscale IP or configured DNS to reach services from anywhere

## Current Development Priorities

### 1. FKS Intelligence Implementation
- **Goal**: RAG-powered system to generate optimal trading signals daily
- **Tracks**: All trades, positions, account balance, available cash
- **Optimizes**: Strategy parameters based on current portfolio state
- **Tasks to implement**: Signal generation, backtesting, portfolio analysis

### 2. Django Migration & Web UI
- **Templates**: Build out HTML pages in `src/web/templates/`
- **Styling**: Bootstrap 5 CSS for responsive design
- **Forms**: Create Django forms for user input
- **Views**: Connect templates to business logic
- **URLs**: Register routes in `src/web/urls.py`

### 3. Testing & CI/CD
- **Write tests first**: TDD approach for new features
- **Run locally**: `pytest` before every commit
- **GitHub Actions**: Automatic test runs on push/PR
- **Coverage**: Track with `--cov` flag, aim for >80%
- **Marks**: Use pytest marks (unit, integration, slow) to organize tests

## Common Pitfalls

1. **Don't modify `framework/` without Phase 9D analysis** - 26 external imports across codebase
2. **Check both ORMs** - Django ORM and SQLAlchemy coexist during migration
3. **GPU commands differ** - Use `docker-compose -f docker-compose.yml -f docker-compose.gpu.yml` for RAG/LLM
4. **Session IDs in settings** - Django uses `web.django` namespace, not `fks_project`
5. **Celery tasks are stubs** - Implementations pending, don't expect them to work yet
6. **Apps disabled in settings** - `config`, `forecasting`, `chatbot`, `rag`, `data` commented out due to import issues

## Known Test Failures (To Fix)

### Import Errors from Legacy Architecture
**Status**: 20/34 tests failing due to microservices-era imports

#### Issue 1: `config` Module Import Errors
```python
# Current (broken):
from config import SYMBOLS, MAINS, ALTS, FEE_RATE, DATABASE_URL

# Should be (Django):
from framework.config.models import TradingConfig
from django.conf import settings
```

**Affected Files**:
- `src/trading/backtest/engine.py` - Line 16
- `src/trading/signals/generator.py` - Line 11
- `src/trading/optimizer/engine.py` - Via backtest import
- `src/core/database/models.py` - Line 10

**Fix Strategy**:
1. Create `framework.config.constants` with trading symbols
2. Update all imports to use `framework.config` or Django settings
3. Remove dependency on legacy `config` module

#### Issue 2: `shared_python` Module Missing
```python
# Current (broken):
from shared_python.config import get_settings
from shared_python import get_settings

# Should be:
from django.conf import settings
```

**Affected Files**:
- `src/data/adapters/base.py` - Line 20, 24

**Fix Strategy**:
1. Remove `shared_python` references (microservices artifact)
2. Use Django settings throughout
3. Update all `data` module imports

### Test Files Needing Updates
- ✗ `tests/integration/test_backtest/*` (4 files) - config imports
- ✗ `tests/integration/test_data/*` (11 files) - shared_python imports
- ✗ `tests/unit/test_core/test_data.py` - shared_python imports
- ✗ `tests/unit/test_core/test_database.py` - config imports
- ✗ `tests/unit/test_core/test_rag_system.py` - config imports
- ✗ `tests/unit/test_trading/test_assets.py` - config imports
- ✗ `tests/unit/test_trading/test_optimizer.py` - config imports
- ✗ `tests/unit/test_trading/test_signals.py` - config imports
- ✓ `tests/unit/test_api/*` (14 files) - Passing ✅

### How to Fix Tests

#### Step 1: Fix config module imports
```python
# Create src/framework/config/constants.py
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
MAINS = ['BTC', 'ETH']
ALTS = ['BNB', 'ADA', 'SOL']
FEE_RATE = 0.001
RISK_PER_TRADE = 0.02

# Update src/core/database/models.py
from django.conf import settings
DATABASE_URL = settings.DATABASES['default']
```

#### Step 2: Fix shared_python imports
```python
# In src/data/adapters/base.py
# Remove:
from shared_python.config import get_settings
from shared_python import get_settings

# Add:
from django.conf import settings
```

#### Step 3: Run tests to verify fixes
```bash
pytest tests/unit/test_api/ -v          # Should pass (14 tests)
pytest tests/unit/test_trading/ -v      # Fix and verify
pytest tests/integration/ -v            # Fix and verify
```

## Documentation Structure

- `README.md` - Main project overview
- `QUICKREF.md` - Quick command reference
- `docs/ARCHITECTURE.md` - Detailed architecture (668 lines)
- `docs/CLEANUP_PLAN.md` - Doc consolidation roadmap (111 docs → 15-20)
- `scripts/README.md` - Script system documentation

## Key Files to Reference

- **Django Config**: `src/web/django/settings.py` (311 lines)
- **URL Routes**: `src/web/django/urls.py`
- **Models**: `src/core/database/models.py` (SQLAlchemy), `src/authentication/models.py` (Django)
- **Celery**: `src/web/django/celery.py`, `src/trading/tasks.py`
- **Docker**: `docker-compose.yml` (257 lines), `docker-compose.gpu.yml` (173 lines)
- **Makefile**: Development commands (239 lines)
- **Testing**: `pytest.ini`, `tests/unit/test_trading/test_assets.py`

## When Making Changes

1. **Check Django app registration** - Verify app in `INSTALLED_APPS` before importing
2. **Run migrations** - `make migrate` after model changes
3. **Test locally** - Use `make up` + `make logs` to verify
4. **Write tests first** - TDD approach, run `pytest` before committing
5. **Validate syntax** - `make lint` before committing
6. **Check imports** - Ensure no circular dependencies with framework layer
7. **Update docs** - If changing architecture or adding major features

## Next Steps for AI Agent

When working on this codebase, prioritize:
1. **Fix test imports** - Update legacy `config` and `shared_python` imports to Django patterns
2. **FKS Intelligence tasks** - Implement Celery tasks in `src/trading/tasks.py` for RAG-powered recommendations
3. **Web UI development** - Create templates, forms, and views for user interface
4. **Test coverage** - Write comprehensive tests for all new functionality (aim for 80%+)
5. **Django migration** - Convert remaining FastAPI routes to Django views
6. **RAG integration** - Connect trading logic to RAG system for intelligent insights

Avoid:
- Production deployment concerns (not ready yet)
- NinjaTrader integration (future feature)
- Modifying `framework/` without analysis
- Implementing features without tests

## Test Status Summary

- ✅ **14 passing** - `tests/unit/test_api/*` (API routes working)
- ❌ **20 failing** - Import errors from microservices migration
- 🎯 **Goal**: Fix imports, get to 34/34 passing tests

**Current Test Results**: 14 passing / 34 total (41% pass rate)  
**Target**: 34 passing / 34 total (100% pass rate)

---
*Generated: October 2025 | Based on Django 5.2.7 monolith migration | Status: Phase 9 Complete (90%)*
