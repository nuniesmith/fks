# FKS Trading Platform - AI Coding Agent Instructions

## Quick Reference
**Architecture:** 8-Service Microservices | **Main Stack:** Python 3.13 + FastAPI + Django  
**Database:** PostgreSQL + TimescaleDB + pgvector + Fundamentals Schema | **AI/ML:** PyTorch + Ollama (local LLM)  
**Test:** `docker-compose exec fks_app pytest tests/unit/strategies/asmbtr/` | **Lint:** `make lint` | **Format:** `make format`  
**Run:** `make up` (standard 8 services) or `make gpu-up` (with Ollama LLM + GPU ML)  
**Current Status:** ✅ Phase 5.4 Complete - Data Foundation with Redis Caching (Oct 30, 2025)

## Project Overview
**FKS Main** is the **orchestrator and monitoring hub** for an **8-service microservices architecture**. It provides centralized authentication, service registry, health monitoring, and Celery Beat scheduling for the entire trading ecosystem.

### Architecture: Monorepo Multi-Container (October 2025)
FKS uses a **monorepo architecture** with multiple Docker containers under `services/` for each microservice, with FKS Main as the orchestration layer. All code lives in a single Git repository for simplified development while maintaining service isolation via containers.

**8 Core Services**:
1. **fks_main** (This Repo, Port 8000) - Orchestrator, service registry, health monitoring, Celery Beat
2. **fks_api** (Port 8001) - Thin API gateway with routing, auth, rate limiting
3. **fks_app** (Port 8002) - ALL business logic: strategies, signals, portfolio optimization
4. **fks_data** (Port 8003) - Always-on data collection with CCXT, TimescaleDB storage
5. **fks_execution** (Port 8004) - Rust execution engine, ONLY service that talks to exchanges
6. **fks_ninja** (Port 8005) - C# .NET bridge to NinjaTrader 8 for prop firm futures
7. **fks_ai** (Port 8006) - GPU-accelerated ML/RAG: local LLM (Ollama), regime detection, forecasting
8. **fks_web** (Port 3001) - Django/Vite web UI with Bootstrap 5 templates

### Current Phase: Phase 5.4 Complete - Redis Caching Layer Ready
- **Status**: Phase 5.4 Complete ✅ - Redis Caching Infrastructure (Oct 30, 2025)
- **Latest Achievement**: Complete Redis caching layer for features and API responses
  - ✅ Phase 5.1: EODHD API Integration - Full fundamentals data collection capability
  - ✅ Phase 5.2: Feature Engineering Pipeline - 63 technical features with TA-Lib/numpy fallback
  - ✅ Phase 5.3: TimescaleDB Fundamentals Schema - 6 hypertables for comprehensive data storage
  - ✅ Phase 5.4: Redis Caching Layer - Feature cache + EODHD response caching (COMPLETE)
  - 📋 Phase 5.5: Data Quality Validation - Next priority (4-6 hours)
- **Previous Achievement**: Phase 3 Complete - ASMBTR Baseline Fully Tested (108/108 tests passing - Oct 29, 2025)
- **Infrastructure**: Enhanced data foundation with Redis caching
  - Core services healthy: fks_main, fks_api, fks_app, fks_data, redis
  - Database: TimescaleDB with fundamentals schema, Redis caching, Prometheus, Grafana, Nginx
  - New capabilities: EODHD API, 63-feature engineering, Redis caching (80-95% speedup), economic indicators
  - Disabled services: fks_execution (Rust runtime issue), fks_web_ui (architectural review needed)
- **Next Steps**: Complete Phase 5.5 then Advanced AI Enhancement Plan (12 phases, 12-16 weeks)
  - Phase 5.5: Data quality validation pipeline (outlier detection, freshness monitoring, completeness checks)
  - Phase 6: Multi-agent foundation (LangGraph + Ollama setup)
  - Phase 7: Regime detection models (VAE + Transformer)
- **Focus**: Data quality validation, then multi-agent AI system implementation

**Important**: When working with services, note that:
- Code is in `src/services/[service_name]/src/` (e.g., `src/services/api/src/main.py`)
- Each service has its own README.md with detailed architecture
- Services communicate via HTTP within docker-compose network
- Django settings are in `src/services/web/src/django/settings.py`
- Root `manage.py` sets `DJANGO_SETTINGS_MODULE=services.web.src.django.settings`

## Architecture Essentials

### 8-Service Microservices Overview

**Data Flow**:
```
Market Data: Exchanges → fks_data (collect) → TimescaleDB/Redis → fks_app (query)
Signal Execution: fks_app (signal) → fks_execution (order) → Exchange
AI/ML: fks_app (request) → fks_ai (GPU inference/RAG) → fks_app (prediction)
External API: Client → fks_api (auth) → fks_app (logic) → fks_api (response)
NinjaTrader: fks_app (signal) → fks_ninja (bridge) → NinjaTrader 8 → Prop Firm
```

**Service Responsibilities**:

1. **fks_main** (Orchestrator - This Repository):
   - Service registry and health monitoring (every 2 minutes)
   - Centralized authentication (delegates to fks_api)
   - Celery Beat scheduler for periodic tasks
   - **NO business logic, NO exchange communication, NO data storage**

2. **fks_api** (Gateway - `src/services/api/`):
   - Route requests to fks_app, fks_data, fks_execution
   - JWT auth and API key validation
   - Rate limiting and throttling
   - **Pure gateway pattern - NO domain logic**

3. **fks_app** (Business Logic - `src/services/app/`):
   - Strategy development and backtesting
   - Signal generation (RSI, MACD, Bollinger Bands)
   - Portfolio optimization with Optuna
   - Queries fks_ai for ML predictions and RAG insights
   - **ALL trading intelligence lives here**

4. **fks_ai** (ML/RAG - `src/services/ai/`):
   - Local LLM inference with Ollama/llama.cpp (CUDA)
   - RAG system with pgvector semantic search
   - Embeddings (sentence-transformers + OpenAI fallback)
   - Document processing and chunking
   - **Regime detection**, **LLM strategy generation**, **forecasting**
   - Zero-cost AI inference (no API fees)

5. **fks_data** (Data Collection - `src/services/data/`):
   - Continuous market data collection (CCXT + Binance)
   - TimescaleDB hypertables for time-series storage
   - Redis caching for fast queries
   - **Other services query fks_data, NEVER exchanges directly**

6. **fks_execution** (Execution Engine - `src/services/execution/`):
   - Rust-based high-performance order execution
   - **ONLY service that talks to exchanges/brokers**
   - Order lifecycle management with FSM
   - Position tracking and updates

7. **fks_ninja** (NinjaTrader Bridge - `src/services/ninja/`):
   - C# .NET bridge to NinjaTrader 8
   - Forward signals from fks_app to NT8
   - Support prop firm accounts (FXIFY, Topstep)

8. **fks_web** (Web UI - `src/services/web/`):
   - Dashboard, strategies, signals, portfolio views
   - Bootstrap 5 templates with Mermaid diagrams
   - **All data fetched via fks_api** (no direct DB queries)
   - Real-time updates with WebSocket

### FKS Main Repository Structure (Monorepo)

```
fks/  (THIS REPOSITORY)
├── docker-compose.yml         # 8-service orchestration
├── docker-compose.gpu.yml     # GPU overrides for fks_ai (Ollama)
├── requirements.txt           # Python dependencies (orchestrator)
├── Makefile                   # Development commands (make up, make gpu-up, etc.)
├── manage.py                  # Django management (in root for orchestrator)
│
├── src/                       # All source code (monorepo)
│   ├── services/             # Microservices code (each service has own README)
│   │   ├── api/              # fks_api service (FastAPI gateway)
│   │   ├── app/              # fks_app service (business logic)
│   │   ├── ai/               # fks_ai service (GPU ML/RAG)
│   │   ├── data/             # fks_data service (market data collection)
│   │   ├── execution/        # fks_execution service (Rust order execution)
│   │   ├── ninja/            # fks_ninja service (.NET NinjaTrader bridge)
│   │   └── web/              # fks_web service (Django UI templates)
│   │
│   ├── monitor/              # Service registry & health checks (fks_main)
│   ├── authentication/       # Centralized auth (fks_main)
│   ├── core/                 # Core models, exceptions, database (fks_main)
│   ├── framework/            # Middleware, config, patterns, services (fks_main)
│   ├── manage.py             # Django management (symlinked from root)
│   └── tests/                # Unit/integration tests for orchestrator
│
├── repo/                      # Git submodules (alternative to services/, deprecated)
│
├── docs/                      # Comprehensive documentation
│   ├── AI_STRATEGY_INTEGRATION.md      # 5-phase AI implementation plan (12 weeks)
│   ├── CRYPTO_REGIME_BACKTESTING.md    # Regime detection research (13 weeks)
│   ├── TRANSFORMER_TIME_SERIES.md      # Transformer forecasting guide
│   ├── ARCHITECTURE.md                  # Detailed architecture (668 lines)
│   ├── MONOREPO_ARCHITECTURE.md         # Monorepo structure explanation
│   └── PHASE_*.md                       # Development phase plans and status
│
├── monitoring/                # Prometheus/Grafana config
│   ├── prometheus/           # Prometheus config and rules
│   └── grafana/              # Grafana dashboards
│
├── sql/                       # TimescaleDB init scripts
├── nginx/                     # Nginx reverse proxy config
├── scripts/                   # Bash automation scripts
└── tests/                     # Orchestrator tests (symlinked to src/tests/)
```

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
# Standard development stack (8 services without GPU)
make up              # Starts: nginx, web, db, redis, celery, prometheus, grafana
make logs            # Follow all logs
make down            # Stop everything
make restart         # Restart services

# GPU stack (adds Ollama LLM + fks_ai service)
make gpu-up          # Combines docker-compose.yml + docker-compose.gpu.yml

# Multi-repo commands (when submodules are set up)
make multi-up        # Start all microservices (fks_api, fks_data, fks_execution, etc.)
make multi-down      # Stop microservices
make multi-logs      # Follow microservice logs
make multi-status    # Health check all services
```

**Access Points**:
- Web UI: http://localhost:8000
- **Health Dashboard: http://localhost:8000/health/dashboard/**
- **Monitor Dashboard: http://localhost:8000/monitor/**
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
# IMPORTANT: Tests run in Docker containers, not on host
# The orchestrator (fks_main) uses the 'web' container

# Run orchestrator tests
docker-compose exec web pytest tests/unit/ -v
docker-compose exec web pytest tests/unit/test_security.py -v      # Specific file
docker-compose exec web pytest tests/unit/ -m "not slow" -v        # Skip slow tests
docker-compose exec web pytest tests/unit/ -m unit -v              # Unit tests only
docker-compose exec web pytest tests/integration/ -m integration -v # Integration tests

# Copy tests into container if needed (run once after rebuild)
docker cp tests fks_main:/app/tests

# Run passing tests (Phase 3.1 baseline)
docker-compose exec web pytest tests/unit/test_security.py \
  tests/unit/test_trading/test_signals.py \
  tests/unit/test_trading/test_strategies.py -v

# Service-specific tests (when services are running)
docker-compose exec fks_api pytest tests/
docker-compose exec fks_app pytest tests/
docker-compose exec fks_data pytest tests/
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
- **Django**: Environment variables via `.env` → Django settings (managed in `services/web/src/django/settings.py`)
- **Orchestrator**: Root `manage.py` uses `web.django.settings` as DJANGO_SETTINGS_MODULE
- **Framework**: `src/framework/config/` - Type-safe dataclasses (DatabaseConfig, TradingConfig, MLConfig, etc.)
- **Service-specific**: Each microservice in `services/` has own config (e.g., `services/api/config.py`)
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

### Immediate: Architecture & Infrastructure (Weeks 1-4)

**1. Submodule Setup & Repository Creation**
- Create GitHub repositories for all 8 microservices
- Initialize git submodules in `repo/` directory
- Set up basic README.md for each service with:
  - Service purpose and responsibilities
  - Tech stack (FastAPI/Django/Rust/.NET)
  - API endpoints and data flow
  - Dependencies and environment setup

**2. Dockerfile Creation**
- `repo/api/`: Python 3.13 + FastAPI + uvicorn
- `repo/app/`: Python 3.13 + FastAPI + TA-Lib + Optuna
- `repo/ai/`: Python 3.13 + PyTorch + CUDA + Ollama + sentence-transformers
- `repo/data/`: Python 3.13 + FastAPI + CCXT + TimescaleDB client
- `repo/execution/`: Rust + Actix-web/Axum + exchange APIs
- `repo/ninja/`: .NET 8 + NinjaTrader SDK
- `repo/web/`: Python 3.13 + Django + Vite + Bootstrap 5

**3. CI/CD Workflows**
- GitHub Actions for each microservice:
  - Run tests (pytest/cargo test/dotnet test)
  - Linting (ruff/clippy/dotnet format)
  - Coverage reporting
  - Docker image builds
- Integration testing workflow for full stack

**4. Service Health Monitoring**
- Implement health check endpoints in all services
- Configure Prometheus exporters
- Set up Grafana dashboards for service metrics
- Test service-to-service communication

### Near-Term: AI Strategy Implementation (Weeks 5-16)

**Phase 1: Data Foundation** (2 weeks)
- Extend fks_data with EODHD API for fundamentals
- Feature engineering: log returns, 21d vol, 5d momentum
- TimescaleDB fundamentals hypertable
- Redis caching for engineered features

**Phase 2: DL Regime Detection** (3-4 weeks)
- Implement VAE in fks_ai (PyTorch)
- Implement Transformer classifier (16-day sequences)
- Training pipeline with Celery tasks
- API endpoints: `/ai/regime`, `/ai/train-regime-model`
- **Expected Results**: Sharpe 5-11 in calm regimes

**Phase 3: LLM Strategy Generation** (3 weeks)
- Prompt engineering framework for Ollama
- Strategy validation and parsing
- Backtest integration with fks_app
- API endpoint: `/ai/generate-strategy`
- **Expected Results**: 60%+ profitable strategies

**Phase 4: Integration & Orchestration** (2 weeks)
- Regime-aware position sizing in fks_app
- Celery Beat scheduling (regime updates every 15m)
- Grafana monitoring dashboards
- Web UI enhancements for regime visualization

**Phase 5: Validation & Optimization** (2 weeks)
- Historical backtests (2-year BTC data)
- Walk-forward validation
- Hyperparameter tuning with Optuna
- Paper trading deployment

### Medium-Term: Crypto Regime Research (Weeks 5-17)

**Phase 1: Baseline GMM** (2 weeks)
- Gaussian Mixture Model regime classifier
- Backtest on BTC 2013-2022 data
- **Target**: 80-100% PNL, Sharpe 4.5-5.5

**Phase 2: VAE + Transformer** (3 weeks)
- Nonlinear latent space with VAE
- Temporal sequences with Transformer
- **Target**: 90-110% PNL, Sharpe 5.5-6.5

**Phase 3: Ensemble Models** (2 weeks)
- Random Forest and Bagging classifiers
- **Target**: 100-120% PNL, Sharpe 6.5-7.5 (backtest)
- **Expected Forward**: 30-50% PNL, Sharpe 4-8

**Phase 4: Walk-Forward Testing** (2 weeks)
- 12-month rolling window validation
- Monthly retraining automation
- Compare backtest vs. walk-forward vs. forward

**Phase 5: Paper Trading** (4 weeks)
- Deploy on Binance Testnet
- Monitor real-world performance
- **Target**: Real Sharpe >2.5 (vs. buy-hold 1.5)

### Long-Term: Testing & Production (Weeks 13+)

**Testing & QA**
- Comprehensive unit tests for all services
- Integration tests for service communication
- End-to-end tests for trading workflows
- Load testing for high-frequency scenarios
- Coverage target: 80%+ across all services

**Production Readiness**
- Security hardening (secrets management, SSL/TLS)
- Deployment automation with Docker Compose
- Monitoring and alerting setup
- Backup and disaster recovery
- Multi-account support (personal, prop firm, banking)

## Common Pitfalls

1. **Don't bypass fks_execution** - ONLY service that talks to exchanges/brokers directly
2. **Don't query exchanges directly** - Use fks_data service for all market data
3. **GPU commands differ** - Use `make gpu-up` (combines docker-compose.yml + docker-compose.gpu.yml)
4. **Service dependencies** - Check docker-compose.yml `depends_on` before starting services
5. **Cross-service imports** - Each service is independent, communicate via HTTP APIs only
6. **GPU requirements** - Need CUDA 12.2+, nvidia-docker2, 8GB VRAM for fks_ai/Ollama
7. **Regime detection expectations** - Expect 50-70% degradation from backtest to forward test
8. **Django settings location** - Settings are in `services/web/src/django/settings.py`, NOT `src/web/django/settings.py`
9. **DJANGO_SETTINGS_MODULE** - Root `manage.py` sets this to `web.django.settings` to find settings in services/web/

## Test Status & Known Issues (Phase 3.1 - Oct 23, 2025)

### Current Test Results
- ✅ **69 tests passing** across security, signals, strategies, optimizer
- ✅ Core trading logic validated (RSI, MACD, Bollinger Bands, portfolio optimization)
- ✅ Security features working (JWT auth, password hashing, rate limiting)
- ⏳ Some tests blocked by Python 3.13 type hint issues (non-critical)

### Passing Test Suites
- ✅ `tests/unit/test_security.py` (25/26) - Auth, JWT, password validation
- ✅ `tests/unit/test_trading/test_signals.py` (20/20) - Technical indicators
- ✅ `tests/unit/test_trading/test_strategies.py` (19/19) - Strategy generation
- ✅ `tests/unit/test_trading/test_binance_rate_limiting.py` (1/1) - Rate limiting
- ✅ `tests/unit/test_trading/test_optuna_optimizer.py` (3/3) - Portfolio optimization

### Microservices Testing Strategy
Each microservice should have its own test suite in its repository:

**fks_main** (This Repo):
- Unit tests: Service registry, health monitoring, Celery Beat scheduling
- Integration tests: Service discovery, auth delegation

**fks_api** (repo/api/):
- Unit tests: Routing logic, JWT validation, rate limiting
- Integration tests: Proxy requests to fks_app, fks_data

**fks_app** (repo/app/):
- Unit tests: Strategy logic, signal generation, portfolio optimization
- Integration tests: Queries to fks_data, fks_ai
- Backtesting validation: Historical performance tests

**fks_ai** (repo/ai/):
- Unit tests: Embeddings, VAE, Transformer, LLM prompts
- Integration tests: Ollama communication, pgvector queries
- Model tests: Regime detection accuracy, strategy generation quality

**fks_data** (repo/data/):
- Unit tests: CCXT wrappers, TimescaleDB queries, Redis caching
- Integration tests: Data collection pipelines, feature engineering

**fks_execution** (repo/execution/):
- Unit tests: Order FSM, position tracking (Rust)
- Integration tests: Exchange API communication (paper trading)

**fks_ninja** (repo/ninja/):
- Unit tests: NT8 bridge logic (.NET)
- Integration tests: NinjaTrader 8 AT Interface

**fks_web** (repo/web/):
- Unit tests: Django views, forms, template rendering
- Integration tests: API calls to fks_api
- E2E tests: Full user workflows (Selenium/Playwright)

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

- `README.md` - Main project overview (8-service architecture, GPU setup)
- `QUICKREF.md` - Quick command reference
- `docs/MONOREPO_DOCKER_GUIDE.md` - **⭐ Comprehensive monorepo setup guide (NEW)**
- `docs/ARCHITECTURE.md` - Detailed architecture (668 lines)
- `docs/AI_STRATEGY_INTEGRATION.md` - Comprehensive 5-phase AI plan (1000+ lines)
- `docs/CRYPTO_REGIME_BACKTESTING.md` - Research analysis with empirical results (1000+ lines)
- `docs/TRANSFORMER_TIME_SERIES.md` - Transformer forecasting guide
- `docs/MONOREPO_ARCHITECTURE.md` - Monorepo structure explanation
- `scripts/README.md` - Script system documentation

## Key Files to Reference

- **Orchestrator Config**: Django settings in `src/services/web/src/django/settings.py`
- **Root Management**: `manage.py` (sets DJANGO_SETTINGS_MODULE=services.web.src.django.settings)
- **Docker Orchestration**: `docker-compose.yml` (8 services), `docker-compose.gpu.yml` (GPU overrides)
- **AI Strategy Plans**: `docs/AI_STRATEGY_INTEGRATION.md`, `docs/CRYPTO_REGIME_BACKTESTING.md`
- **Celery**: `src/services/web/src/django/celery.py` (Beat scheduler), task definitions in service-specific code
- **Models**: `src/core/database/models.py` (shared orchestrator models)
- **Service Code**: All microservice implementations in `src/services/[service_name]/src/`
- **Makefile**: Development commands (`make up`, `make gpu-up`, `make logs`)
- **Testing**: `pytest.ini`, `tests/unit/` (69 passing tests), service-specific tests in `src/services/*/tests/`

## When Making Changes

### Pre-Development Checklist
1. **Identify target service** - Determine which microservice needs changes (fks_main, fks_api, fks_app, fks_ai, fks_data, fks_execution, fks_ninja, fks_web)
2. **Review service boundaries** - Ensure changes respect service responsibilities (no business logic in fks_api, no DB queries in fks_web)
3. **Check existing tests** - Understand test patterns before adding new code
4. **Review service code** - All service code is in `src/services/[service_name]/`

### Development Workflow
1. **Write tests first** - TDD approach, create test cases before implementation
2. **Implement changes** - Follow existing code patterns and conventions
3. **Run tests frequently** - `docker-compose exec <service> pytest tests/` after each logical change
4. **Validate syntax** - `make lint` to check for style issues
5. **Format code** - `make format` to apply consistent formatting

### Post-Development Checklist
1. **Run migrations** - `make migrate` after model changes
2. **Test locally** - Use `make up` or `make gpu-up` + `make logs` to verify services
3. **Full test suite** - Run complete test suite for affected service
4. **Check coverage** - Ensure new code has adequate test coverage (>80%)
5. **Update docs** - If changing architecture, API contracts, or adding major features
6. **Verify no regressions** - Ensure existing functionality still works across all dependent services

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
1. **Fix import errors** - Create `src/framework/config/constants.py` and update all imports
2. **Implement core Celery tasks** - Market data sync, signal generation in `services/app/`
3. **Test service communication** - Verify fks_app → fks_data → fks_execution flow

### Near-Term Focus (Next 2-4 Weeks)
4. **AI Strategy Phase 1** - Data Foundation (EODHD API, fundamentals table, feature engineering)
5. **Service health monitoring** - Implement health checks and Prometheus metrics for all services
6. **Integration testing** - Test service-to-service communication (fks_app → fks_data → fks_execution)
7. **Test coverage** - Write comprehensive tests for each microservice (aim for 80%+)

### Medium-Term Goals (1-3 Months)
8. **AI Strategy Phase 2** - DL Regime Detection (VAE + Transformer models in fks_ai)
9. **AI Strategy Phase 3** - LLM Strategy Generation (Ollama prompt engineering)
10. **Web UI development** - fks_web Django templates with Bootstrap 5 and Mermaid diagrams
11. **Crypto regime research** - Implement GMM baseline, ensemble models, walk-forward testing

### Avoid
- Production deployment (not ready yet - focus on local dev and paper trading)
- Bypassing fks_execution (ONLY service that talks to exchanges)
- Cross-service imports (services must communicate via HTTP APIs only)
- Implementing features without tests (violates TDD approach)
- Large, unfocused PRs (keep changes small and surgical)
- Hardcoding secrets or sensitive data

## Test Status Summary

- ✅ **108/108 passing** - ASMBTR baseline fully tested (100% pass rate - Phase 3 complete, Oct 29, 2025)
- ✅ **Phase 5 Data Foundation** - Feature processor working with 63 features from 6 inputs (Oct 30, 2025)
- ✅ **All test suites passing**: BTR encoding (28), state encoder (19), prediction table (26), strategy (35)
- ✅ **New Infrastructure**: EODHD API adapter, fundamentals schema, feature engineering pipeline
- 🎯 **Next Goal**: Redis caching layer and data quality validation

**Current Test Results**: 
- **ASMBTR Framework**: 108/108 passing (100%) - Complete test coverage
- **Test Location**: `tests/unit/strategies/asmbtr/` (test_btr.py, test_encoder.py, test_predictor.py, test_strategy.py)
- **Container**: Tests run in `fks_app` Docker container via `docker-compose exec fks_app pytest`

**Target**: 80%+ coverage across all 8 microservices

### ASMBTR Test Suite Details (Phase 3 Complete)

**Test Categories**:
1. **BTR Encoding (28 tests)**: State creation, decimal conversion, encoder initialization, movement tracking, buffer management, edge cases
2. **State Encoder (19 tests)**: Tick processing, multi-symbol support, price change detection, zero-change handling, statistics
3. **Prediction Table (26 tests)**: State observation, probability calculation, decay application, save/load, edge cases
4. **Strategy (35 tests)**: Position management, signal generation, PnL tracking, stop-loss/take-profit, backtesting, performance metrics

**Key Test Learnings** (Oct 29, 2025):
- **Zero price changes are skipped**: `StateEncoder` only adds movements when price actually changes (not treated as DOWN)
- **Buffer is FIFO**: `BTREncoder` keeps last N movements in rolling window, dropping oldest when full
- **Dataclass properties**: `StatePrediction.prediction` and `confidence` are computed `@property`, not `__init__` parameters
- **API naming**: Production uses `save_to_dict()`/`load_from_dict()`, not `save()`/`load()`
- **Attribute names**: `StateEncoder.encoder` (not `btr_encoder`), `PredictionTable.state_counts` (not `table`)
- **Decay rate validation**: Must be 0.9-1.0 (not 0.5), enforced in `PredictionTable.__init__`

**Test Execution**:
```bash
# Run all ASMBTR tests
docker-compose exec fks_app pytest tests/unit/strategies/asmbtr/ -v

# Run specific test file
docker-compose exec fks_app pytest tests/unit/strategies/asmbtr/test_encoder.py -v

# Run with coverage
docker-compose exec fks_app pytest tests/unit/strategies/asmbtr/ --cov=strategies.asmbtr --cov-report=term-missing
```

## Advanced AI Trading System Enhancement Plan (2025-2026)

### Overview: Hybrid Multi-Agent Architecture
**Goal**: Evolve FKS into a deep-thinking, self-improving trading system combining non-AI baselines (ASMBTR, Markov chains), multi-agent LLM architectures, advanced ML evaluation, risk controls, and hedging strategies for multi-asset crypto/FX trading.

**Timeline**: 12-16 weeks (phased rollout) | **Expected Performance**: Calmar >0.4, Sharpe ~0.5, Max Drawdown <-0.5

### Core Components & Technologies

**AI/ML Stack Enhancements**:
- **Multi-Agent System**: LangGraph orchestration with Bull/Bear/Manager agents, adversarial debates
- **Hybrid Models**: CNN-LSTM + LLM vetoes, WFO parameter optimization, MDD protection
- **Baselines**: ASMBTR (Adaptive State Model on BTR), Markov chains for memoryless transitions
- **Evaluation**: Confusion matrices, p-value adjustments (Bonferroni/Benjamini-Hochberg), LLM-judge audits
- **Memory**: ChromaDB for agent memory, Redis for state management
- **Hedging**: CPI-Gold threshold switching, multi-asset diversification

**Integration Points**:
- `fks_ai` (8006): LangGraph agents, regime detection, hybrid model inference
- `fks_app` (8002): ASMBTR strategies, Markov signal processing, portfolio optimization
- `fks_data` (8003): Multi-asset data (crypto/FX), CPI/Gold macro data ingestion
- `fks_execution` (8004): Dual pool execution (long/short), MDD circuit breakers

### 12-Phase Implementation Roadmap

#### Phase 1: Data Preparation & Compatibility (1-2 days)
**Objective**: Establish data foundation for ASMBTR and multi-agent systems

**Tasks**:
- Fetch high-frequency FX data (EUR/USD, GBP/USD) and crypto (BTC/ETH) via CCXT
- Implement micro-price change (Δ) scanner for tick-level analysis
- Verify TimescaleDB hypertable compatibility with BTR encoding
- Create `docs/ASMBTR_COMPATIBILITY.md` documenting data requirements

**Code Location**: `services/data/src/collectors/`, `services/data/src/processors/`

**Acceptance Criteria**:
- [ ] EUR/USD tick data streaming to TimescaleDB
- [ ] Δ scanner detecting price changes <0.01%
- [ ] Data quality report showing >99% completeness

---

#### Phase 2: ASMBTR Baseline Core (3-5 days)
**Objective**: Implement Adaptive State Model on BTR as memoryless baseline

**Tasks**:
- Build BTR (Binary Tree Representation) encoder: `asmbtr/btr.py`
- Implement state encoding: `asmbtr/encoder.py` with configurable depth (default: 8)
- Create prediction table: `asmbtr/predictor.py` mapping states → probabilities
- Develop trading logic: `asmbtr/strategy.py` with event-driven execution
- Add configuration: Support variable depths, decay rates, threshold tuning

**Code Location**: `services/app/src/strategies/asmbtr/`

**Key Algorithm**:
```python
# BTR Encoding Example (depth=8)
def encode_asmbtr(deltas: List[float], depth: int = 8) -> str:
    """Encode price changes into binary tree state"""
    state = ""
    for delta in deltas[-depth:]:
        state += "1" if delta > 0 else "0"
    return state  # e.g., "10110011"

def predict_next(state: str, table: Dict) -> float:
    """Predict next move probability from learned table"""
    return table.get(state, {}).get('up_prob', 0.5)
```

**Acceptance Criteria**:
- [ ] BTR encoder handles variable depths (4-12)
- [ ] Prediction table populated from historical EUR/USD data
- [ ] Strategy achieves Calmar >0.3 on 2024 backtest

---

#### Phase 3: Baseline Testing & Optimization (4-7 days)
**Objective**: Validate ASMBTR and optimize hyperparameters

**Tasks**:
- Unit tests: `tests/unit/strategies/test_asmbtr.py` (>80% coverage)
- Integration tests: `tests/integration/test_asmbtr_backtest.py`
- Hyperparameter search with Optuna: depth, decay rate, entry/exit thresholds
- Compare ASMBTR vs. RSI/MACD baselines on multiple pairs (EUR/USD, BTC/USDT)
- Document results: `docs/ASMBTR_OPTIMIZATION.md`

**Code Location**: `tests/`, `scripts/optimize_asmbtr.py`

**Optuna Example**:
```python
def objective(trial):
    depth = trial.suggest_int('depth', 6, 12)
    decay = trial.suggest_float('decay', 0.95, 0.999)
    threshold = trial.suggest_float('threshold', 0.55, 0.75)
    
    strategy = ASMBTRStrategy(depth=depth, decay=decay, threshold=threshold)
    backtest = run_backtest(strategy, data='EUR_USD_2024')
    return backtest.calmar_ratio
```

**Acceptance Criteria**:
- [ ] Test coverage >80% for ASMBTR module
- [ ] Optimized hyperparameters documented
- [ ] Calmar ratio improvement >10% vs. default params

---

#### Phase 4: Baseline Deployment (2-3 days)
**Objective**: Containerize ASMBTR and integrate with Celery

**Tasks**:
- Update `docker/Dockerfile.app` with ASMBTR dependencies
- Create Celery task: `tasks/asmbtr_prediction.py` for periodic state updates
- Add monitoring: Prometheus metrics for state transitions, prediction accuracy
- Configure Celery Beat schedule: Run ASMBTR predictions every 1 minute

**Code Location**: `services/app/tasks/`, `monitoring/prometheus/`

**Acceptance Criteria**:
- [ ] ASMBTR runs in fks_app container
- [ ] Celery tasks executing every 60 seconds
- [ ] Prometheus dashboards showing live state metrics

---

#### Phase 5: Agentic Foundation (5-7 days)
**Objective**: Establish LangGraph infrastructure for multi-agent system

**Tasks**:
- Setup LangChain/LangGraph with local Ollama (llama3.2:3b for cost efficiency)
- Define AgentState schema: TypedDict with market_data, signals, debates, memory
- Implement ChromaDB memory: Store agent interactions, decisions, reflections
- Extend toolkit: Add CCXT tools, TA-Lib wrappers, backtesting utilities
- Create base agent factory: `agents/base.py` with shared prompt templates

**Code Location**: `services/ai/src/agents/`, `services/ai/src/memory/`

**AgentState Schema**:
```python
from typing import TypedDict, List, Annotated
from langgraph.graph import add_messages

class AgentState(TypedDict):
    messages: Annotated[List, add_messages]
    market_data: Dict[str, Any]  # OHLCV, indicators
    signals: List[Dict]  # Bull/Bear recommendations
    debates: List[str]  # Adversarial arguments
    memory: List[str]  # ChromaDB retrieval context
    final_decision: Optional[str]  # Manager output
```

**Acceptance Criteria**:
- [ ] Ollama serving llama3.2:3b on fks_ai (8006)
- [ ] ChromaDB initialized with trading knowledge base
- [ ] Base agent can query market data and generate simple signals

---

#### Phase 6: Multi-Agent Debate System (7-10 days)
**Objective**: Build adversarial agents with specialized roles

**Tasks**:
1. **Analyst Agents (4 types)**:
   - Technical Analyst: RSI, MACD, Bollinger analysis
   - Sentiment Analyst: News/social media (optional, use OpenAI fallback)
   - Macro Analyst: CPI, interest rates, correlations
   - Risk Analyst: VaR, MDD, position sizing

2. **Debate Agents**:
   - Bull Agent: Optimistic scenarios, long opportunities
   - Bear Agent: Pessimistic scenarios, short signals
   - Manager Agent: Synthesizes debates, final decision

3. **Trader Personas (3 + Judge)**:
   - Conservative: Low leverage, tight stops
   - Moderate: Balanced risk/reward
   - Aggressive: High leverage, wider stops
   - Judge: Selects best persona based on market regime

**Code Location**: `services/ai/src/agents/analysts/`, `services/ai/src/agents/debaters/`

**Debate Loop Example**:
```python
async def debate_node(state: AgentState):
    """Adversarial debate between Bull and Bear"""
    bull_arg = await bull_agent.invoke(state)
    bear_arg = await bear_agent.invoke(state)
    
    # Store debate for reflection
    state['debates'].extend([bull_arg, bear_arg])
    
    # Manager synthesizes
    decision = await manager_agent.invoke({
        **state,
        'bull_argument': bull_arg,
        'bear_argument': bear_arg
    })
    state['final_decision'] = decision
    return state
```

**Acceptance Criteria**:
- [ ] All 4 analyst agents operational
- [ ] Bull/Bear debates generating contrasting views
- [ ] Manager making decisions based on debate quality
- [ ] Judge selecting personas >70% accuracy on test data

---

#### Phase 7: Graph Orchestration & Reflection (7-10 days)
**Objective**: Build end-to-end StateGraph with feedback loops

**Tasks**:
- Construct StateGraph: Analysts → Debaters → Manager → Trader → Execution
- Add conditional edges: Route based on market regime (calm/volatile)
- Implement SignalProcessor: Aggregate multi-agent outputs into unified signals
- Build Reflector: Analyze past decisions, update memory with learnings
- Initial evaluations: Run graph on historical data, measure latency (<5s per decision)

**Code Location**: `services/ai/src/graph/`, `services/ai/src/processors/`

**Graph Structure**:
```python
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)

# Nodes
graph.add_node("analysts", run_analysts)
graph.add_node("debate", debate_node)
graph.add_node("manager", manager_decision)
graph.add_node("trader", select_trader_persona)
graph.add_node("reflect", reflection_node)

# Edges
graph.add_edge("analysts", "debate")
graph.add_edge("debate", "manager")
graph.add_conditional_edges(
    "manager",
    route_to_trader,  # Checks market regime
    {"conservative": "trader", "aggressive": "trader", "skip": END}
)
graph.add_edge("trader", "reflect")
graph.add_edge("reflect", END)

compiled_graph = graph.compile()
```

**Acceptance Criteria**:
- [ ] Graph executes full pipeline in <5 seconds
- [ ] Conditional routing working based on volatility
- [ ] Reflection node updating ChromaDB with insights
- [ ] Signal quality >60% accuracy on validation set

---

#### Phase 8: Advanced Evaluation Framework (3-5 days)
**Objective**: Implement rigorous testing and validation

**Tasks**:
- Confusion Matrix: For ASMBTR and ML models (KNN-like in `fks_ai`)
  - Calculate precision, recall, F1 for buy/sell/hold predictions
  - Apply Bonferroni/Benjamini-Hochberg corrections for p-values
  - Test on BTC/ETH data (2023-2024)

- LLM-Judge Audits: Verify agent reasoning
  - Factual consistency checks (e.g., "Did Bull agent hallucinate data?")
  - Discrepancy detection between analyst claims and actual market data
  - Bias analysis (over-optimistic/pessimistic patterns)

- Ground Truth Backtests: Compare predictions vs. reality
  - ASMBTR states vs. actual next-price moves
  - Agent signals vs. optimal hindsight trades
  - CPI-Gold hedge vs. S&P 500 benchmark

**Code Location**: `tests/unit/test_evaluation.py`, `services/ai/src/evaluators/`

**Confusion Matrix Example**:
```python
from sklearn.metrics import confusion_matrix, classification_report
from scipy.stats import chi2_contingency

# Predictions: buy(1), sell(-1), hold(0)
y_true = [1, 1, -1, 0, 1, -1, 0, 0, 1, -1]
y_pred = [1, 0, -1, 0, 1, -1, 1, 0, 1, 0]

cm = confusion_matrix(y_true, y_pred)
print(classification_report(y_true, y_pred))

# Chi-square test
chi2, p_value, _, _ = chi2_contingency(cm)
adjusted_p = p_value * 3  # Bonferroni for 3 classes
print(f"Adjusted p-value: {adjusted_p}")
```

**Acceptance Criteria**:
- [ ] Confusion matrices showing balanced precision/recall (>0.6)
- [ ] LLM-judge catching >80% of factual errors in test cases
- [ ] Ground truth backtests validating ASMBTR Calmar >0.4

---

#### Phase 9: Hybrid Models & Risk Controls (5-7 days)
**Objective**: Integrate CNN-LSTM with LLM vetoes and hedging

**Tasks**:
1. **LLM Vetoes**:
   - Add veto layer to strategies: LLM reviews signals before execution
   - Prompt: "Given [market_data], [signal], assess risk. Veto if: ..."
   - Integrate with `fks_execution` to block high-risk trades

2. **Walk-Forward Optimization (WFO)**:
   - Implement rolling window parameter updates (monthly retraining)
   - Use Optuna for hyperparameter search on each window
   - Track parameter drift over time

3. **Maximum Drawdown Protection**:
   - Add circuit breaker in `fks_execution`: Halt trading if MDD > threshold (-15%)
   - Email alerts via Discord webhook
   - Auto-reduce position sizes during drawdown recovery

4. **CPI-Gold Hedging**:
   - Build `strategies/hedge.py` with threshold-based asset switching
   - Fetch CPI data from BLS API, Gold prices from yfinance
   - Corrected metrics: Target Sharpe 0.48 (not >1 as claimed), drawdown -0.51
   - Backtest vs. S&P 500 benchmark (2020-2024)

**Code Location**: `services/app/src/strategies/hybrid/`, `services/execution/src/risk/`

**LLM Veto Example**:
```python
async def veto_check(signal: Dict, market_data: Dict) -> bool:
    """LLM reviews signal for risk"""
    prompt = f"""
    Signal: {signal['action']} {signal['symbol']} at {signal['price']}
    Market: RSI={market_data['rsi']}, Vol={market_data['volatility']}
    
    Veto this trade if:
    1. RSI > 80 (overbought) and action = BUY
    2. Volatility > 2x average
    3. News sentiment extremely negative
    
    Answer: VETO or APPROVE
    """
    response = await ollama.generate(prompt)
    return "VETO" in response.upper()
```

**CPI-Gold Hedge** (Corrected):
```python
def cpi_gold_strategy(cpi_yoy: float, threshold: float = 3.0):
    """Switch between Gold and S&P based on CPI"""
    if cpi_yoy > threshold:
        return "GOLD"  # High inflation
    else:
        return "SPY"  # Normal conditions
    
# Historical Performance (2020-2024):
# Sharpe: 0.48, Max DD: -0.51, Correlation (CPI-Gold): 0.85
```

**Acceptance Criteria**:
- [ ] LLM vetoes blocking >30% of risky signals in validation
- [ ] WFO showing <10% parameter drift over 6-month test
- [ ] MDD protection triggering correctly in backtest stress scenarios
- [ ] CPI-Gold hedge outperforming SPY in high-inflation periods (2021-2022)

---

#### Phase 10: Markov Chains & Integration (5-7 days)
**Objective**: Add memoryless state transitions and finalize system

**Tasks**:
1. **Markov Chain Module**:
   - Build `strategies/markov.py` for bull/bear/sideways state transitions
   - Compute steady-state probabilities for long-term predictions
   - Validate memoryless assumption: Test autocorrelation on price data
   - Use with ASMBTR for hybrid state-based signals

2. **Full System Merge**:
   - Integrate Markov states into StateGraph (new node: "markov_regime")
   - Update agents to use Markov context in prompts
   - Combine ASMBTR (micro) + Markov (macro) for multi-timeframe analysis

3. **Final Optimizations**:
   - Latency tuning: Reduce graph execution to <3 seconds
   - Memory pruning: ChromaDB cleanup for old, irrelevant records
   - Model refinement: Retrain ML models with all collected data

**Code Location**: `services/app/src/strategies/markov/`, `services/ai/src/graph/`

**Markov Example**:
```python
import numpy as np

# Transition matrix: Bull, Bear, Sideways
P = np.array([
    [0.7, 0.2, 0.1],  # From Bull
    [0.3, 0.6, 0.1],  # From Bear
    [0.4, 0.3, 0.3]   # From Sideways
])

# Steady-state: Solve π = πP
eigenvalues, eigenvectors = np.linalg.eig(P.T)
steady_state = eigenvectors[:, np.isclose(eigenvalues, 1)]
steady_state = steady_state / steady_state.sum()
print(f"Long-term probabilities: Bull={steady_state[0]:.2f}, Bear={steady_state[1]:.2f}")
```

**Acceptance Criteria**:
- [ ] Markov module computing steady-state for BTC data
- [ ] Autocorrelation tests confirming memoryless on short-term (<1h)
- [ ] Graph latency <3 seconds for full pipeline
- [ ] Hybrid ASMBTR+Markov achieving Calmar >0.45

---

#### Phase 11: Deployment & Monitoring (3-5 days)
**Objective**: Production-ready deployment with observability

**Tasks**:
- Update Docker Compose: Add resource limits for `fks_ai` (8GB RAM, 2 CPUs)
- Prometheus metrics:
  - Agent decision latency, debate quality scores
  - Sharpe/Calmar ratios (live tracking)
  - MDD, position counts, veto rates
- Grafana dashboards:
  - Multi-agent system overview (nodes, edges, execution times)
  - Strategy performance (ASMBTR, Markov, Hybrid)
  - Risk metrics (VaR, MDD, exposure)
- Email alerts: Discord webhook for critical events (MDD breach, system errors)
- Update `docs/MONITORING_README.md` with new dashboards

**Code Location**: `monitoring/grafana/dashboards/`, `monitoring/prometheus/rules/`

**Acceptance Criteria**:
- [ ] All services running with health checks passing
- [ ] Prometheus scraping AI metrics every 30 seconds
- [ ] Grafana dashboards showing live agent activity
- [ ] Discord alerts functional for test events

---

#### Phase 12: Iteration & Continuous Learning (Ongoing)
**Objective**: Establish feedback loop for long-term improvement

**Tasks**:
- Live simulation: Run system in paper trading for 4 weeks
- A/B testing: Compare ASMBTR vs. Hybrid vs. Multi-agent on different pairs
- Incorporate best practices from searches:
  - **Data quality**: LuxAlgo's validation pipelines
  - **AI ethics**: TWIML's fairness checks (avoid market manipulation)
  - **Modular platforms**: Biz4Group's microservice patterns (already in use)
- Plan v2 features:
  - Reinforcement learning (RL) for adaptive strategies
  - Multi-agent collaboration on cross-asset arbitrage
  - Explainability dashboards (SHAP values for ML, LLM reasoning chains)
- Document learnings: Update `docs/PHASE_7_FUTURE_FEATURES.md`

**Code Location**: `docs/`, `scripts/ab_testing.py`

**Acceptance Criteria**:
- [ ] Paper trading logs showing 30-day performance
- [ ] A/B test results documented with statistical significance
- [ ] Ethics audit completed (no wash trading patterns detected)
- [ ] v2 roadmap drafted with prioritized features

---

### Best Practices Integration

**From Industry Research** (LuxAlgo, QuantStart, Biz4Group, etc.):
1. **Data Validation**: Implement pre-trade checks (outlier detection, sanity tests)
2. **Risk-Adjusted Metrics**: Focus on Sharpe, Calmar, Sortino (not just raw returns)
3. **Modular Architecture**: Already implemented via microservices ✅
4. **Walk-Forward Optimization**: Avoid overfitting with rolling windows
5. **Ethical AI**: No market manipulation, transparent decision-making
6. **Ground Truth Validation**: Always backtest with out-of-sample data

**Key Pitfalls to Avoid**:
- **Overfitting**: Use confusion matrices, cross-validation, WFO
- **Black Swan Events**: CPI-Gold correlation breaks in crises (2008, 2020)
- **Memory Assumptions**: Markov memoryless fails for long-term trends
- **LLM Costs**: Prioritize local Ollama; use OpenAI only for critical tasks
- **Data Sparsity**: ASMBTR needs high-frequency data; ensure <1s resolution

### Implementation Delegation Templates

**For AI Agent**:
```
Phase X, Task X.Y: "In [file_path], implement [feature]. 
Requirements: [specific_details]. 
Test with: [test_data]. 
Expected output: [acceptance_criteria]."
```

**Example Prompts**:
- Phase 8, Task 8.1: "In `tests/unit/test_ml_models.py`, add scikit-learn confusion_matrix for ASMBTR predictions. Include Bonferroni p-value adjustments. Test on BTC 2024 data."
- Phase 9, Task 9.2: "Implement CPI-Gold hedge in `strategies/hedge.py`. Use BLS CPI API and yfinance for Gold. Target Sharpe 0.48, MDD -0.51. Backtest vs. S&P 2020-2024."
- Phase 10, Task 10.1: "Build Markov module in `strategies/markov.py`. Compute steady-state for bull/bear/sideways. Validate memoryless assumption with autocorrelation tests on EUR/USD hourly data."

### Key Citations & Resources

**Academic/Technical**:
- ASMBTR Paper: Adaptive State Model on Binary Tree Representation for FX
- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- Scikit-learn Metrics: https://scikit-learn.org/stable/modules/model_evaluation.html
- CPI Data: https://www.bls.gov/cpi/
- Gold Historical: https://www.macrotrends.net/

**Best Practices**:
- LuxAlgo: https://www.luxalgo.com/blog/best-practices-in-algo-trading-strategy-development/
- QuantStart: https://www.quantstart.com/articles/Best-Practices-for-Algorithmic-Trading-System-Development/
- Biz4Group: https://www.biz4group.com/blog/ai-algo-trading-platform-development

**Internal Docs**:
- `docs/PHASE_PLAN_SUMMARY.md` - Existing phase structure
- `docs/AI_STRATEGY_INTEGRATION.md` - Original AI plan
- `docs/OPTIMIZATION_GUIDE.md` - Hyperparameter tuning
- `docs/PROJECT_HEALTH_DASHBOARD.md` - System monitoring

---

## Phase 5 Implementation Details - Data Foundation (COMPLETED Oct 30, 2025)

### Phase 5.1: EODHD API Integration ✅
**Location**: `src/services/data/src/adapters/eodhd.py`, `src/services/data/src/collectors/fundamentals_collector.py`

**Key Components**:
- **EODHD Adapter**: Comprehensive API client with rate limiting (1000 requests/day)
- **Data Types**: Fundamentals, earnings, economic indicators, insider transactions
- **Features**: Async requests, response normalization, error handling, request building
- **Testing**: Full test suite with mocking (`src/services/data/src/tests/test_adapter_eodhd.py`)

**Usage Example**:
```python
from adapters.eodhd import EODHDAdapter
from collectors.fundamentals_collector import FundamentalsCollector

adapter = EODHDAdapter(api_key="your_key")
collector = FundamentalsCollector(adapter)

# Collect fundamentals data
fundamentals = await collector.collect_fundamentals(['AAPL', 'MSFT'])
```

### Phase 5.2: Feature Engineering Pipeline ✅
**Location**: `src/services/app/src/features/feature_processor.py`

**Key Features**:
- **40+ Technical Indicators**: RSI, MACD, Bollinger Bands, Stochastic, Williams %R, CCI, ATR, ADX
- **Statistical Features**: Log returns, volatility (5d/21d/63d), momentum, price changes
- **Volume Features**: OBV, volume ratios, VWAP
- **Time Features**: Hour, day of week, market sessions (US/EU/Asia)
- **Microstructure**: Bid-ask spreads, price impact, volume imbalance
- **TA-Lib Integration**: With numpy fallback for maximum compatibility

**Performance**: Generates 63 features from 6 OHLCV input columns

**Usage Example**:
```python
from features.feature_processor import FeatureProcessor

processor = FeatureProcessor(min_periods=20)
features = processor.process_ohlcv_features(ohlcv_data, symbol='BTCUSDT')
# Returns DataFrame with 63 engineered features
```

### Phase 5.3: TimescaleDB Fundamentals Schema ✅
**Location**: `sql/fundamentals_schema.sql`, `sql/migrations/003_fundamentals_core_working.sql`

**Database Tables (6 Hypertables)**:
1. **company_fundamentals**: Financial statements, ratios (PE, PB, ROE)
2. **earnings_data**: Earnings estimates vs actuals, surprise analysis
3. **economic_indicators**: Macro data (GDP, CPI, Fed rates, unemployment)
4. **insider_transactions**: Corporate insider buy/sell activity
5. **news_sentiment**: News analysis with sentiment scoring
6. **correlation_analysis**: Asset correlation tracking

**Features**: Proper TimescaleDB partitioning, compression policies, indexes for performance

**Sample Data**: US economic indicators (GDP, CPI, Fed funds rate, unemployment) pre-loaded

**Usage Example**:
```sql
-- Query economic indicators
SELECT indicator_code, value, unit FROM economic_indicators 
WHERE country = 'US' ORDER BY time DESC;

-- Query latest fundamentals
SELECT * FROM company_fundamentals 
WHERE symbol = 'AAPL' ORDER BY time DESC LIMIT 1;
```

### Phase 5.4: Redis Caching Layer 🚧 (NEXT PRIORITY)
**Planned Location**: `src/services/app/src/cache/`, `src/services/data/src/cache/`

**Implementation Plan**:
- Cache engineered features with TTL (1-24 hours based on timeframe)
- EODHD API response caching to avoid rate limits
- Cache warming strategies for frequently accessed data
- Invalidation on new data arrival
- Redis cluster support for high availability

### Phase 5.5: Data Quality Validation 📋 (PLANNED)
**Planned Location**: `src/services/data/src/validators/`

**Implementation Plan**:
- Outlier detection for price/volume anomalies
- Data freshness checks (alert if data >15min old)
- Completeness validation (missing OHLCV fields)
- Quality scoring (0-100) with alerts
- Historical data consistency checks

### Phase 5 Key Files Created/Modified:
```
src/services/data/src/adapters/eodhd.py                     (355 lines) - EODHD API adapter
src/services/data/src/collectors/fundamentals_collector.py  (447 lines) - Async fundamentals collector  
src/services/app/src/features/feature_processor.py          (502 lines) - Feature engineering pipeline
src/services/data/src/tests/test_adapter_eodhd.py          (275 lines) - EODHD adapter tests
src/services/app/src/tests/test_feature_processor.py        (TBD lines) - Feature processor tests
sql/fundamentals_schema.sql                                 (450 lines) - Complete schema definition
sql/migrations/003_fundamentals_core_working.sql            (200 lines) - Applied migration
```

### Next Steps (Continue Tomorrow):
1. **Phase 5.4**: Implement Redis caching for features and API responses
2. **Phase 5.5**: Add data quality validation pipeline
3. **Integration Testing**: Test EODHD → Features → Database pipeline end-to-end
4. **Phase 6**: Begin multi-agent AI system (LangGraph + Ollama setup)

---

## Troubleshooting for Copilot Agent

### Common Issues & Solutions

**Import Errors (config, shared_python)**
- **Problem**: Legacy microservices imports failing
- **Solution**: Use `from framework.config.constants` instead
- **See**: "Test Status & Known Issues" section above for detailed patterns

**Service Communication Errors**
- **Problem**: `ConnectionRefusedError` or service not found
- **Solution**: Verify service is running (`docker-compose ps`) and health check passing
- **Check**: Use service name from docker-compose.yml (e.g., `http://fks_api:8001` not `http://localhost:8001`)

**Circular Import Errors**
- **Problem**: `ImportError: cannot import name 'X' from partially initialized module`
- **Solution**: Avoid importing from `framework/` during module initialization
- **Pattern**: Use lazy imports or import inside functions when needed

**Test Discovery Issues**
- **Problem**: Pytest can't find tests
- **Solution**: Ensure test files are named `test_*.py` and in `tests/` directory
- **Config**: Check `pytest.ini` for test discovery settings

**ASMBTR Test Failures (Fixed Oct 29, 2025)**
- **Zero price changes**: StateEncoder skips them entirely (not treated as DOWN movement)
- **Attribute mismatches**: Use `StateEncoder.encoder` (not `btr_encoder`), `PredictionTable.state_counts` (not `table`)
- **Dataclass parameters**: `StatePrediction` has no `prediction` parameter - it's a computed `@property`
- **Save/Load methods**: Use `save_to_dict()`/`load_from_dict()`, not `save()`/`load()`
- **Decay rate range**: Must be 0.9-1.0, not 0.5 (enforced in `PredictionTable.__init__`)
- **Error message patterns**: Match actual production messages (e.g., "must have same length" not "must have the same length")

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

## Tomorrow's Continuation Plan (Phase 5.4 & Beyond)

### Immediate Priorities (Phase 5.4: Redis Caching Layer)
1. **Create Cache Framework**: `src/services/app/src/cache/feature_cache.py`
   - Redis client with connection pooling
   - TTL management based on timeframe (1m=1min, 1h=1hour, 1d=24hours)
   - Cache key namespacing (features:BTCUSDT:1h:rsi_14)
   - Serialization/deserialization for numpy arrays and DataFrames

2. **Integrate with Feature Processor**: Update `feature_processor.py`
   - Check cache before computation
   - Store results with appropriate TTL
   - Cache invalidation on new OHLCV data
   - Cache warming for frequently requested features

3. **EODHD Response Caching**: Update `adapters/eodhd.py`
   - Cache API responses to avoid rate limiting
   - Longer TTL for fundamentals (daily) vs real-time data (minutes)
   - Handle API errors with cached fallbacks

### Phase 5.5: Data Quality Validation
1. **Outlier Detection**: `src/services/data/src/validators/outlier_detector.py`
2. **Freshness Monitoring**: Alert system for stale data
3. **Completeness Checks**: Validate OHLCV completeness
4. **Quality Scoring**: 0-100 score with thresholds

### Phase 6: Multi-Agent Foundation
- LangGraph + Ollama integration for local LLM
- Agent state management with ChromaDB memory
- Bull/Bear/Manager agent framework

### Current Working Files:
- ✅ `src/services/data/src/adapters/eodhd.py` - EODHD API client
- ✅ `src/services/data/src/collectors/fundamentals_collector.py` - Async collector
- ✅ `src/services/app/src/features/feature_processor.py` - 63 features from 6 inputs
- ✅ `sql/fundamentals_schema.sql` - 6 hypertables for fundamentals
- ✅ TimescaleDB schema applied with sample economic data

### Test Commands:
```bash
# Test feature processor
docker-compose exec fks_app python -c "
import sys; sys.path.insert(0, '/app/src')
from features.feature_processor import FeatureProcessor
processor = FeatureProcessor(min_periods=20)
print('Feature processor ready for Redis caching integration')
"

# Test fundamentals schema
docker-compose exec db psql -U fks_user -d trading_db -c "
SELECT COUNT(*) FROM economic_indicators;
SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%fundamental%';
"
```

---
*Generated: October 2025 | Based on 8-Service Microservices Architecture | Status: Phase 5 Complete - Data Foundation Ready*  
*Last Updated: 2025-10-30 | Copilot Instructions v5.0 - Data Foundation Complete (EODHD + Features + Fundamentals Schema)*
