# FKS Trading Platform - AI Coding Agent Instructions

## Quick Reference
**Architecture:** 8-Service Microservices | **Main Stack:** Python 3.13 + FastAPI + Django  
**Database:** PostgreSQL + TimescaleDB + pgvector | **AI/ML:** PyTorch + Ollama (local LLM)  
**Test:** `docker-compose exec fks_api pytest tests/` | **Lint:** `make lint` | **Format:** `make format`  
**Run:** `make up` (standard 8 services) or `make gpu-up` (with Ollama LLM + GPU ML)  
**Current Status:** ✅ Architecture documented, AI strategy planned (Oct 24, 2025)

## Project Overview
**FKS Main** is the **orchestrator and monitoring hub** for an **8-service microservices architecture**. It provides centralized authentication, service registry, health monitoring, and Celery Beat scheduling for the entire trading ecosystem.

### Architecture: Multi-Repo Microservices (October 2025)
FKS uses **Git submodules** under `repo/` for each microservice, with FKS Main as the orchestration layer.

**8 Core Services**:
1. **fks_main** (This Repo, Port 8000) - Orchestrator, service registry, health monitoring, Celery Beat
2. **fks_api** (Port 8001) - Thin API gateway with routing, auth, rate limiting
3. **fks_app** (Port 8002) - ALL business logic: strategies, signals, portfolio optimization
4. **fks_data** (Port 8003) - Always-on data collection with CCXT, TimescaleDB storage
5. **fks_execution** (Port 8004) - Rust execution engine, ONLY service that talks to exchanges
6. **fks_ninja** (Port 8005) - C# .NET bridge to NinjaTrader 8 for prop firm futures
7. **fks_ai** (Port 8006) - GPU-accelerated ML/RAG: local LLM (Ollama), regime detection, forecasting
8. **fks_web** (Port 3001) - Django/Vite web UI with Bootstrap 5 templates

### Current Phase: Architecture Planning & Documentation
- **Status**: Phase 1 Complete ✅ - Architecture documented, AI strategy planned
- **Priority**: Submodule setup, Dockerfiles, CI/CD workflows, integration testing
- **Next**: Create microservice repositories, implement core functionality
- **Not Yet**: Live trading, production deployment (focus on paper trading first)

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

2. **fks_api** (Gateway - `repo/api/`):
   - Route requests to fks_app, fks_data, fks_execution
   - JWT auth and API key validation
   - Rate limiting and throttling
   - **Pure gateway pattern - NO domain logic**

3. **fks_app** (Business Logic - `repo/app/`):
   - Strategy development and backtesting
   - Signal generation (RSI, MACD, Bollinger Bands)
   - Portfolio optimization with Optuna
   - Queries fks_ai for ML predictions and RAG insights
   - **ALL trading intelligence lives here**

4. **fks_ai** (ML/RAG - `repo/ai/`):
   - Local LLM inference with Ollama/llama.cpp (CUDA)
   - RAG system with pgvector semantic search
   - Embeddings (sentence-transformers + OpenAI fallback)
   - Document processing and chunking
   - **Regime detection**, **LLM strategy generation**, **forecasting**
   - Zero-cost AI inference (no API fees)

5. **fks_data** (Data Collection - `repo/data/`):
   - Continuous market data collection (CCXT + Binance)
   - TimescaleDB hypertables for time-series storage
   - Redis caching for fast queries
   - **Other services query fks_data, NEVER exchanges directly**

6. **fks_execution** (Execution Engine - `repo/execution/`):
   - Rust-based high-performance order execution
   - **ONLY service that talks to exchanges/brokers**
   - Order lifecycle management with FSM
   - Position tracking and updates

7. **fks_ninja** (NinjaTrader Bridge - `repo/ninja/`):
   - C# .NET bridge to NinjaTrader 8
   - Forward signals from fks_app to NT8
   - Support prop firm accounts (FXIFY, Topstep)

8. **fks_web** (Web UI - `repo/web/`):
   - Dashboard, strategies, signals, portfolio views
   - Bootstrap 5 templates with Mermaid diagrams
   - **All data fetched via fks_api** (no direct DB queries)
   - Real-time updates with WebSocket

### FKS Main Repository Structure (Orchestrator Only)

```
fks/  (THIS REPOSITORY)
├── docker-compose.yml         # 8-service orchestration
├── docker-compose.gpu.yml     # GPU overrides for fks_ai (Ollama)
├── requirements.txt           # Python dependencies (orchestrator)
├── Makefile                   # Development commands
│
├── repo/                      # Git submodules (microservices)
│   ├── api/                  # fks_api service
│   ├── app/                  # fks_app service
│   ├── ai/                   # fks_ai service (GPU ML/RAG)
│   ├── data/                 # fks_data service
│   ├── execution/            # fks_execution service (Rust)
│   ├── ninja/                # fks_ninja service (.NET)
│   └── web/                  # fks_web service (Django UI)
│
├── src/                       # FKS Main Django app (orchestrator)
│   ├── monitor/              # Service registry & health checks
│   ├── authentication/       # Centralized auth
│   └── web/django/           # Django settings, Celery config
│
├── docs/                      # Documentation
│   ├── AI_STRATEGY_INTEGRATION.md      # 5-phase AI implementation plan (12 weeks)
│   ├── CRYPTO_REGIME_BACKTESTING.md    # Regime detection research (13 weeks)
│   ├── TRANSFORMER_TIME_SERIES.md      # Transformer forecasting guide
│   ├── ARCHITECTURE.md                  # Detailed architecture
│   └── SERVICE_CLEANUP_PLAN.md          # Migration plan
│
├── monitoring/                # Prometheus/Grafana config
├── sql/                       # TimescaleDB init scripts
└── tests/                     # Orchestrator tests only
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
4. **Submodule updates** - Run `git submodule update --init --recursive` after pulling
5. **Service dependencies** - Check docker-compose.yml `depends_on` before starting services
6. **Cross-service imports** - Each service is independent, communicate via HTTP APIs only
7. **GPU requirements** - Need CUDA 12.2+, nvidia-docker2, 8GB VRAM for fks_ai/Ollama
8. **Regime detection expectations** - Expect 50-70% degradation from backtest to forward test

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
- `docs/ARCHITECTURE.md` - Detailed architecture (668 lines)
- `docs/AI_STRATEGY_INTEGRATION.md` - Comprehensive 5-phase AI plan (1000+ lines)
- `docs/CRYPTO_REGIME_BACKTESTING.md` - Research analysis with empirical results (1000+ lines)
- `docs/TRANSFORMER_TIME_SERIES.md` - Transformer forecasting guide
- `docs/CLEANUP_PLAN.md` - Doc consolidation roadmap (111 docs → 15-20)
- `scripts/README.md` - Script system documentation

## Key Files to Reference

- **Orchestrator Config**: `src/web/django/settings.py` (Django for FKS Main)
- **Docker Orchestration**: `docker-compose.yml` (8 services), `docker-compose.gpu.yml` (GPU overrides)
- **AI Strategy Plans**: `docs/AI_STRATEGY_INTEGRATION.md`, `docs/CRYPTO_REGIME_BACKTESTING.md`
- **Celery**: `src/web/django/celery.py` (Beat scheduler), `src/trading/tasks.py` (task definitions)
- **Models**: `src/core/database/models.py` (shared models)
- **Makefile**: Development commands (`make up`, `make gpu-up`, `make logs`)
- **Testing**: `pytest.ini`, `tests/unit/test_trading/` (69 passing tests)

## When Making Changes

### Pre-Development Checklist
1. **Identify target service** - Determine which microservice needs changes (fks_main, fks_api, fks_app, fks_ai, fks_data, fks_execution, fks_ninja, fks_web)
2. **Review service boundaries** - Ensure changes respect service responsibilities (no business logic in fks_api, no DB queries in fks_web)
3. **Check existing tests** - Understand test patterns before adding new code
4. **Verify submodules** - Run `git submodule update --init --recursive` if working with repo/

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
1. **Complete submodule setup** - Create GitHub repositories for all 8 microservices
2. **Create Dockerfiles** - Implement Dockerfiles for each service (api, app, ai, data, execution, ninja, web)
3. **Test GPU stack** - Validate Ollama + fks_ai service with `make gpu-up`

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

- ✅ **69 passing** - Security, signals, strategies, optimizer (Phase 3.1 complete)
- ⏳ **Some blocked** - Python 3.13 type hint issues (non-critical)
- 🎯 **Goal**: Expand test coverage to all microservices (80%+ each)

**Current Test Results**: 69 passing tests (FKS Main orchestrator)  
**Target**: 80%+ coverage across all 8 microservices

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
*Generated: October 2025 | Based on 8-Service Microservices Architecture | Status: Architecture Documented (AI Strategy Planned)*  
*Last Updated: 2025-10-24 | Copilot Instructions v3.0*
