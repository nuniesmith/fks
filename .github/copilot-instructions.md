# FKS Trading Platform - AI Coding Agent Instructions

## Quick Reference
**Language:** Python 3.13.9 | **Framework:** Django 5.2.7 | **Database:** PostgreSQL + TimescaleDB  
**Test:** `docker-compose exec web pytest tests/unit/` | **Lint:** `make lint` | **Format:** `make format`  
**Run:** `make up` (standard) or `make gpu-up` (with AI/RAG)  
**Test Status:** ✅ 69 passing tests (Phase 3.1 complete - Oct 23, 2025)

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
# Run tests in Docker container (REQUIRED - tests not on host)
docker-compose exec web pytest tests/unit/ -v
docker-compose exec web pytest tests/unit/test_security.py -v      # Specific file
docker-compose exec web pytest tests/unit/ -m "not slow" -v        # Skip slow tests
docker-compose exec web pytest tests/unit/ -m unit -v              # Unit tests only
docker-compose exec web pytest tests/integration/ -m integration -v # Integration tests

# Copy tests into container if needed (run once after rebuild)
docker cp tests fks_app:/app/tests

# Run passing tests (Phase 3.1 baseline)
docker-compose exec web pytest tests/unit/test_security.py \
  tests/unit/test_trading/test_signals.py \
  tests/unit/test_trading/test_strategies.py -v
```

**Test config**: `pytest.ini` (marks: unit, integration, slow, data, backtest, trading, api, web)

**GitHub Actions CI**: `.github/workflows/ci-cd.yml` runs tests on push/PR
- Always run tests locally before committing
- CI catches issues early for solo development
- Coverage reports help identify untested code

**Current Test Status (Oct 23, 2025)**:
- ✅ **69 tests passing** (security, signals, strategies, optimizer)
- ❌ Core/RAG tests blocked (Python 3.13 type hint issues)
- ❌ Some tests timing out (container resource limits)
- 📊 See `docs/PHASE_3_BASELINE_TESTS.md` for full report

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

### File Organization & Naming
- **Django apps**: Use directory-based apps under `src/` (e.g., `src/authentication/`, `src/trading/`)
- **Models**: Place in `models.py` or `models/` subdirectory for complex apps
- **Views**: Use `views.py` or `views/` for multiple view files
- **Tests**: Mirror source structure in `tests/unit/` and `tests/integration/`
- **Templates**: Place in `src/web/templates/` with app-specific subdirectories
- **Static files**: Place in `src/web/static/` (CSS, JS, images)
- **Naming convention**: Use `snake_case` for files, functions, and variables; `PascalCase` for classes

### Import Patterns
- **Framework imports**: `from framework.middleware.circuit_breaker import CircuitBreaker`
- **Core models**: `from core.database.models import Trade, Position`
- **Django apps**: `from authentication.models import User`
- **Avoid**: Importing from `infrastructure/` or `services/` - legacy modules being phased out
- **Absolute imports**: Always use absolute imports from `src/` root

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

## Known Test Failures & Fixes (Phase 3.1 Progress)

### ✅ FIXED - Import Errors from Legacy Architecture (Oct 23, 2025)
**Status**: Major issues resolved, 69 tests now passing!

#### ✅ Issue 1: `config` Module Import Errors - FIXED
```python
# OLD (broken):
from config import SYMBOLS, MAINS, ALTS, FEE_RATE, DATABASE_URL

# NEW (working):
from framework.config.constants import SYMBOLS, MAINS, ALTS, FEE_RATE
from django.conf import settings
```

**Fixed Files**:
- ✅ `src/trading/signals/generator.py` - Now imports from framework.config.constants
- ✅ `src/framework/config/constants.py` - Created with all trading symbols
- ✅ `src/core/database/models.py` - Metadata columns renamed (doc_metadata, chunk_metadata, insight_metadata)
- ✅ `src/core/database/utils.py` - Fixed database import path

**Resolution**: Created `framework/config/constants.py` with all required constants

#### ✅ Issue 2: FastAPI & Auth Dependencies - FIXED
```python
# Added to requirements.txt:
fastapi>=0.115.0  # Legacy API routes (being migrated to Django)
uvicorn>=0.32.0   # ASGI server for FastAPI
passlib>=1.7.4    # Password hashing
python-jose>=3.5.0  # JWT tokens
```

**Fixed Files**:
- ✅ `src/framework/middleware/__init__.py` - Made FastAPI optional
- ✅ `src/framework/exceptions/api.py` - Fixed import path (framework.exceptions.base)
- ✅ `src/framework/exceptions/app.py` - Fixed import path
- ✅ `src/framework/exceptions/data.py` - Fixed import path
- ✅ `requirements.txt` - Added FastAPI dependencies

**Resolution**: Added missing dependencies and fixed import paths

#### ✅ Issue 3: Database & Container Configuration - FIXED
- ✅ Redis version downgraded to 5.2.0 (Celery 5.5.3 compatibility)
- ✅ PostgreSQL SSL disabled for local testing
- ✅ trading_db database created with fks_user
- ✅ Django migrations applied successfully

### Test Files Status (69 Passing!)
- ✅ `tests/unit/test_security.py` (25/26) - **PASSING** ✅
- ✅ `tests/unit/test_trading/test_signals.py` (20/20) - **PASSING** ✅
- ✅ `tests/unit/test_trading/test_strategies.py` (19/19) - **PASSING** ✅
- ✅ `tests/unit/test_trading/test_binance_rate_limiting.py` (1/1) - **PASSING** ✅
- ✅ `tests/unit/test_trading/test_optuna_optimizer.py` (3/3) - **PASSING** ✅
- ⏳ `tests/unit/test_core/*` - Python 3.13 type hint issues (TypeError)
- ⏳ `tests/unit/test_rag/*` - Python 3.13 type hint issues (TypeError)
- ⏳ `tests/unit/test_trading/test_tasks.py` - Works but times out
- ⏳ `tests/unit/test_trading/test_assets.py` - Times out (needs investigation)
- ⏳ `tests/integration/*` - Not yet tested

### How Tests Were Fixed (Phase 3.1)

#### Docker Environment Setup
```bash
# 1. Copy tests into container
docker cp tests fks_app:/app/tests

# 2. Fixed dependencies
# - Added FastAPI, passlib, python-jose to requirements.txt
# - Fixed redis version to 5.2.0

# 3. Database setup
docker-compose exec db psql -U fks_user -d postgres -c "CREATE DATABASE trading_db;"
docker-compose exec web python manage.py migrate

# 4. Run working tests
docker-compose exec web pytest tests/unit/test_security.py -v
docker-compose exec web pytest tests/unit/test_trading/test_signals.py -v
docker-compose exec web pytest tests/unit/test_trading/test_strategies.py -v
```

#### Common Issues & Solutions

**Issue**: `ModuleNotFoundError: No module named 'config'`
- **Fix**: Import from `framework.config.constants` instead
- **File**: `src/framework/config/constants.py` (exists with all symbols)

**Issue**: `ModuleNotFoundError: No module named 'fastapi'`
- **Fix**: Already added to requirements.txt, install in container if needed:
  ```bash
  docker-compose exec web pip install fastapi uvicorn passlib python-jose
  ```

**Issue**: Tests timing out or hanging
- **Fix**: Container may be resource-constrained, restart services:
  ```bash
  docker-compose down && docker-compose up -d
  ```

**Issue**: Coverage collection hangs
- **Fix**: Run tests without coverage, or use targeted coverage:
  ```bash
  docker-compose exec web pytest tests/unit/test_signals.py --cov=trading/signals
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

### Pre-Development Checklist
1. **Check Django app registration** - Verify app in `INSTALLED_APPS` before importing
2. **Review existing tests** - Understand test patterns before adding new code
3. **Check imports** - Ensure no circular dependencies with framework layer

### Development Workflow
1. **Write tests first** - TDD approach, create test cases before implementation
2. **Implement changes** - Follow existing code patterns and conventions
3. **Run tests frequently** - `pytest tests/` after each logical change
4. **Validate syntax** - `make lint` to check for style issues
5. **Format code** - `make format` to apply consistent formatting

### Post-Development Checklist
1. **Run migrations** - `make migrate` after model changes
2. **Test locally** - Use `make up` + `make logs` to verify services
3. **Full test suite** - Run complete test suite: `pytest tests/ -v --cov=src`
4. **Check coverage** - Ensure new code has adequate test coverage (>80%)
5. **Update docs** - If changing architecture or adding major features
6. **Verify no regressions** - Ensure existing functionality still works

### Code Style & Quality
- **Formatting**: Use Black (line length 100) and isort for imports
- **Type hints**: Add type annotations for function parameters and returns
- **Docstrings**: Use Google-style docstrings for classes and functions
- **Comments**: Add comments only when code intent is not obvious
- **DRY principle**: Extract repeated code into reusable functions/classes

## Pull Request Guidelines

### PR Requirements
- **Tests**: All new code must have corresponding test cases (unit and/or integration)
- **Linting**: Code must pass `make lint` without errors
- **Coverage**: Maintain or improve overall test coverage (currently 41%, target 80%+)
- **Documentation**: Update relevant docs if changing architecture or major features
- **Commits**: Use descriptive commit messages following conventional commits format

### PR Description Template
```markdown
## Changes
- Brief description of what changed

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated  
- [ ] Manual testing completed
- [ ] All tests passing locally

## Checklist
- [ ] Code follows project conventions
- [ ] Linting passes (`make lint`)
- [ ] Tests pass (`make test`)
- [ ] Documentation updated (if needed)
- [ ] No sensitive data or secrets committed
```

### Code Review Expectations
- **Small PRs**: Keep changes focused and manageable (< 500 lines preferred)
- **Self-review**: Review your own code before requesting review
- **Test evidence**: Include test output or screenshots demonstrating changes
- **Breaking changes**: Clearly document any breaking changes in PR description

## Development Philosophy & Approach

### Core Principles
1. **Start Manual, Then Automate** - Verify functionality manually in development before automating
2. **Dynamic Growth** - System adapts to user capital ($100 conservative → $1M aggressive strategies)
3. **Emotional Safeguards** - Provide "hand-holding" through rule-based guidance and visualizations
4. **Test-Driven Development** - Write tests before implementation
5. **Incremental Progress** - Small, focused changes over large rewrites

### Intelligence Evolution Strategy
The FKS Intelligence system is designed to:
- **Watch Over Everything** - Monitor trades, positions, balances, and market conditions
- **Learn Daily** - Optimize strategies based on historical performance and current portfolio state
- **Grow With User** - Scale complexity and sophistication based on available capital
- **Mitigate Emotions** - Use probabilistic models (Markov chains, RL) for objective decision-making

### Multi-Account Architecture
Support multiple account types with isolated states:
- **Personal Accounts** - Daily spending via crypto cards (Shakepay, Netcoins, Crypto.com)
- **Prop Firm Accounts** - Leveraged API trading for income scaling (FXIFY, Topstep)
- **Long-Term Accounts** - Stable banking for wealth preservation (Canadian banks via open banking APIs)
- **Profit Split Logic** - 50% to long-term accounts, 50% to crypto for trading/expenses (default $1000/month)

## Enhanced Development Priorities

### Phase 1: Immediate Fixes (Weeks 1-4; High Urgency)
**Goal**: Stabilize core, unblock development

1. **Security Hardening** (3 hrs total)
   - Generate secure passwords for all services
   - Configure django-axes and django-ratelimit
   - Enable DB SSL, run pip-audit
   - **Priority**: Run before any deployment

2. **Fix Import/Test Failures** (11 hrs total)
   - Create `framework.config.constants` with trading symbols
   - Migrate all legacy imports to Django patterns
   - Fix 20 failing tests to reach 34/34 passing
   - Add GitHub Action for automated testing
   - **Priority**: Blocks all other development

3. **Code Cleanup** (5 hrs total)
   - Review/flesh out/delete 25+ empty files
   - Merge legacy duplicates (engine.py variants)
   - Run black/isort/flake8 for style consistency
   - **Priority**: After import fixes

### Phase 2: Core Development (Weeks 5-10; High Impact)
**Goal**: Complete migration, implement features

1. **Celery Task Implementation** (25-30 hrs; phased)
   - Market data sync from Binance (4 hrs)
   - Signal generation with technical indicators (6 hrs)
   - Backtesting execution (8 hrs)
   - Portfolio optimization with RAG (10 hrs)
   - Configure Beat schedule for automation
   - **Priority**: Foundation for trading functionality

2. **RAG System Completion** (14 hrs)
   - Document processor for chunking (3 hrs)
   - Embeddings with GPU fallback (2 hrs)
   - Semantic search via pgvector (3 hrs)
   - Intelligence orchestrator with Ollama (4 hrs)
   - Auto-ingestion pipeline via Celery (2 hrs)
   - **Priority**: Enables AI-powered recommendations

3. **Markov Chain Integration** (8 hrs)
   - Basic Markov model for trading states (3 hrs)
   - Decision logic with risk management (2 hrs)
   - Layer AI models for daily optimization (3 hrs)
   - **Priority**: Probabilistic foundation for decisions

4. **Web UI/API Migration** (9 hrs)
   - Complete Bootstrap templates (3 hrs)
   - Migrate FastAPI routes to Django (4 hrs)
   - Implement health dashboard (2 hrs)
   - **Priority**: User-facing features

### Phase 3: Testing & QA (Weeks 7-12; Parallel with Phase 2)
**Goal**: Achieve 80%+ coverage

1. **Expand Tests** (9 hrs)
   - RAG unit tests with mocked components (3 hrs)
   - Celery integration tests (4 hrs)
   - Performance benchmarks (2 hrs)
   - **Priority**: Run after each feature implementation

2. **CI/CD Setup** (3 hrs)
   - GitHub Action for Docker build/tests/lint (2 hrs)
   - Integrate analyze script for auto-reporting (1 hr)
   - **Priority**: Automates quality checks

### Phase 4: Account Integration (Weeks 9-11; Medium Priority)
**Goal**: Support multiple account types

1. **Personal Accounts** (4 hrs)
   - API wrappers for Shakepay, Netcoins, Crypto.com
   - Balance checks and transfers
   - Manual funding prompts in dev

2. **Prop Firm Integration** (5 hrs)
   - Support for FXIFY, Topstep APIs
   - Automated trade execution
   - Profit stacking logic

3. **Long-Term Banking** (4 hrs)
   - Open banking APIs (RBC, Scotiabank via Flinks)
   - 50/50 profit split automation
   - Secure encrypted transfers

### Phase 5: Visualization & Monitoring (Weeks 10-12)
**Goal**: Dynamic diagrams and metrics

1. **Mermaid.js Integration** (5 hrs)
   - Install and configure in Django templates
   - Generate dynamic workflow diagrams
   - Visualize Markov states, profit splits, account flows
   - **Priority**: Emotional hand-holding through visuals

2. **Rust Monitoring Wrapper** (8 hrs; optional)
   - Spawn Django processes from Rust binary
   - Collect system/app metrics
   - Prometheus exporter for unified monitoring
   - **Priority**: Advanced monitoring for production

### Phase 6: Advanced Features (Weeks 13+; Future)
**Goal**: Production readiness and scaling

1. **Multi-Container Architecture** (12 hrs)
   - Split into fks_app, fks_gpu, fks_api, fks_web, fks_data
   - Docker Compose orchestration
   - GPU passthrough for AI tasks

2. **Deployment Readiness** (9 hrs)
   - Tailscale VPN configuration
   - Prometheus alerts
   - VPS deployment with security hardening

## Next Steps for AI Agent

When working on this codebase, prioritize in this order:

### Immediate Actions (This Week)
1. **Fix test imports** - Update legacy `config` and `shared_python` imports to Django patterns
2. **Security hardening** - Generate secure passwords, configure rate limiting, run pip-audit
3. **Code cleanup** - Remove empty files, merge duplicates

### Near-Term Focus (Next 2-4 Weeks)
4. **Celery tasks** - Implement market data sync, signal generation, backtesting
5. **RAG integration** - Complete document processing, embeddings, intelligence orchestrator
6. **Markov chains** - Add probabilistic trading logic with AI optimization
7. **Test coverage** - Write comprehensive tests for all new functionality (aim for 80%+)

### Medium-Term Goals (1-3 Months)
8. **Web UI development** - Create templates, forms, and views for user interface
9. **Account integration** - Support personal, prop firm, and long-term accounts
10. **Visualization** - Add Mermaid diagrams for workflow mapping
11. **Multi-user states** - Isolate user data with PostgreSQL, encrypted backups

### Avoid
- Production deployment (not ready yet - focus on local dev)
- NinjaTrader integration (future feature)
- Modifying `framework/` without explicit analysis (26 external imports - high risk)
- Implementing features without tests (violates TDD approach)
- Large, unfocused PRs (keep changes small and surgical)
- Hardcoding secrets or sensitive data

## Test Status Summary

- ✅ **14 passing** - `tests/unit/test_api/*` (API routes working)
- ❌ **20 failing** - Import errors from microservices migration
- 🎯 **Goal**: Fix imports, get to 34/34 passing tests

**Current Test Results**: 14 passing / 34 total (41% pass rate)  
**Target**: 34 passing / 34 total (100% pass rate)

## Troubleshooting for Copilot Agent

### Common Issues & Solutions

**Import Errors (config, shared_python)**
- **Problem**: Legacy microservices imports failing
- **Solution**: Use `from framework.config` or `from django.conf import settings`
- **See**: "Known Test Failures" section above for detailed fix strategy

**Django App Not Found**
- **Problem**: `ModuleNotFoundError` or `AppNotFound`
- **Solution**: Verify app is in `INSTALLED_APPS` in `src/web/django/settings.py`
- **Check**: Some apps are intentionally disabled (see "Common Pitfalls" #6)

**Circular Import Errors**
- **Problem**: `ImportError: cannot import name 'X' from partially initialized module`
- **Solution**: Avoid importing from `framework/` during module initialization
- **Pattern**: Use lazy imports or import inside functions when needed

**Test Discovery Issues**
- **Problem**: Pytest can't find tests
- **Solution**: Ensure test files are named `test_*.py` and in `tests/` directory
- **Config**: Check `pytest.ini` for test discovery settings

**Docker/Container Issues**
- **Problem**: Services won't start or connection errors
- **Solution**: 
  1. Check `.env` file exists (copy from `.env.example`)
  2. Run `make down && make up` to restart services
  3. View logs with `make logs` to identify specific errors
  4. Verify ports aren't in use: `docker-compose ps`

**Database Migration Errors**
- **Problem**: Migration conflicts or missing migrations
- **Solution**: 
  1. Check for unapplied migrations: `make migrate`
  2. If conflicts, resolve manually in `src/*/migrations/`
  3. Create new migration: `docker-compose exec web python manage.py makemigrations`

### Getting Help
- **Logs**: Always check `make logs` first for error details
- **Health Dashboard**: Visit http://localhost:8000/health/dashboard/ for system status
- **Documentation**: Refer to `docs/ARCHITECTURE.md` for detailed architecture info
- **Tests**: Run specific test files to isolate issues: `pytest tests/unit/test_X.py -v`

---
*Generated: October 2025 | Based on Django 5.2.7 monolith migration | Status: Phase 9 Complete (90%)*  
*Last Updated: 2025-10-18 | Copilot Instructions v2.0*
