# FKS Trading Platform - AI Coding Agent Instructions

## 🎯 Quick Reference

| Category | Command / URL | Description |
|----------|---------------|-------------|
| **Start Services** | `make up` | Standard 8 services |
| | `make gpu-up` | With Ollama LLM + GPU ML |
| **Testing** | `docker-compose exec fks_app pytest tests/unit/strategies/asmbtr/` | ASMBTR suite (108/108) |
| | `docker-compose exec fks_app pytest tests/unit/validators/` | Quality validators (34/34) |
| | `docker-compose exec fks_app pytest tests/unit/cache/` | Redis caching (20/20) |
| **Code Quality** | `make lint` | Run ruff + mypy + black |
| | `make format` | Auto-format with black + isort |
| **Monitoring** | http://localhost:8000/health/dashboard/ | System health overview |
| | http://localhost:3000 | Grafana dashboards |
| | http://localhost:9090 | Prometheus metrics |
| **Database** | `make migrate` | Run Django migrations |
| | `make db-shell` | PostgreSQL psql shell |

**Current Status:** ✅ Phase 5.6 Complete - Quality Monitoring & Observability (Oct 30, 2025)  
**Next Phase:** 🎯 Phase 6 - Multi-Agent Foundation (LangGraph + Ollama + ChromaDB)  
**Architecture:** 8-Service Microservices | **Stack:** Python 3.13, FastAPI, Django, PostgreSQL, TimescaleDB, Redis  
**Test Status:** 188/188 passing (ASMBTR: 108, Redis: 20, Validators: 34, Monitoring: 40)

## 📋 Project Overview

**FKS Main** is the **orchestrator and monitoring hub** for an **8-service microservices architecture** providing algorithmic trading, AI-powered strategy generation, and comprehensive market analysis.

### System Architecture (Monorepo Multi-Container)

FKS uses a **monorepo architecture** with Docker containers under `src/services/` for each microservice. All code lives in a single Git repository for simplified development while maintaining service isolation.

| Service | Port | Responsibilities | Status |
|---------|------|------------------|--------|
| **fks_main** | 8000 | Orchestrator, service registry, health monitoring, Celery Beat | ✅ |
| **fks_api** | 8001 | Gateway with routing, JWT auth, rate limiting | ✅ |
| **fks_app** | 8002 | Business logic: strategies, signals, portfolio optimization | ✅ |
| **fks_data** | 8003 | Market data collection (CCXT), TimescaleDB storage | ✅ |
| **fks_execution** | 8004 | Rust execution engine (ONLY talks to exchanges) | ⏸️ Runtime issue |
| **fks_ninja** | 8005 | C# .NET bridge to NinjaTrader 8 for prop firms | ✅ |
| **fks_ai** | 8006 | GPU ML/RAG: Ollama, regime detection, forecasting | ✅ |
| **fks_web** | 3001 | Django/Vite web UI with Bootstrap 5 | ⏸️ Architecture review |

### Current Status: Phase 5.6 Complete ✅ (Oct 30, 2025)

**Latest Achievement**: Complete quality monitoring & observability system
- ✅ **Phase 5.1**: EODHD API Integration - Fundamentals data collection
- ✅ **Phase 5.2**: Feature Engineering - 63 technical features with TA-Lib
- ✅ **Phase 5.3**: TimescaleDB Schema - 6 fundamentals hypertables
- ✅ **Phase 5.4**: Redis Caching - 80-95% speedup on feature queries
- ✅ **Phase 5.5**: Data Quality Validation - 4 validators (outlier, freshness, completeness, scoring)
- ✅ **Phase 5.6**: Quality Monitoring - Prometheus + Grafana + Alerts + TimescaleDB

**Infrastructure**:
- 15/16 services operational (93.75% health)
- Database: PostgreSQL + TimescaleDB + pgvector + Redis
- Monitoring: Prometheus (10 quality metrics) + Grafana (8-panel dashboard) + Alertmanager
- Capabilities: EODHD API, 63-feature engineering, Redis caching, quality validation

**Next Steps**: Phase 6 - Multi-Agent Foundation (LangGraph + Ollama + ChromaDB)
- Establish LangGraph infrastructure for multi-agent system
- Setup Ollama local LLM (llama3.2:3b)
- Implement ChromaDB memory for agent context
- Create Bull/Bear/Manager agent debate framework

**Important**: When working with services, note that:
- Code is in `src/services/[service_name]/src/` (e.g., `src/services/api/src/main.py`)
- Each service has its own README.md with detailed architecture
- Services communicate via HTTP APIs within docker-compose network
- Django settings: `src/services/web/src/django/settings.py`
- Root `manage.py` sets `DJANGO_SETTINGS_MODULE=services.web.src.django.settings`

## 🏗️ Architecture Essentials

### Data Flow Diagram

```
Market Data: Exchanges → fks_data (collect) → TimescaleDB/Redis → fks_app (query)
Signal Flow: fks_app (signal) → fks_execution (order) → Exchange
AI/ML Flow: fks_app (request) → fks_ai (GPU inference/RAG) → fks_app (prediction)
API Flow:   Client → fks_api (auth) → fks_app (logic) → fks_api (response)
NinjaTrader: fks_app (signal) → fks_ninja (bridge) → NT8 → Prop Firm
```### Service Responsibilities

| Service | Responsibilities | Critical Rules |
|---------|------------------|----------------|
| **fks_main** | Orchestrator, registry, health monitoring | NO business logic, NO exchange communication |
| **fks_api** | Gateway, JWT auth, rate limiting | Pure routing - NO domain logic |
| **fks_app** | Strategies, signals, portfolio optimization | ALL trading intelligence here |
| **fks_ai** | Local LLM (Ollama), regime detection, RAG | Zero-cost AI inference |
| **fks_data** | Market data collection, TimescaleDB storage | Other services query here, NEVER exchanges directly |
| **fks_execution** | Rust order execution | ONLY service that talks to exchanges |
| **fks_ninja** | C# NinjaTrader 8 bridge | Forward signals to prop firm platforms |
| **fks_web** | Django UI with Bootstrap 5 | Fetch ALL data via fks_api |

## 🤖 Agent Usage Guide (Best Practices for AI Development)

### Core Development Philosophy

**Guiding Principles**:
1. **Test-Driven Development (TDD)** - Write tests BEFORE implementation
2. **Incremental Progress** - Small, focused changes over large rewrites
3. **Human Oversight** - Always request review for critical changes
4. **Explicit Over Implicit** - Ask for clarification when uncertain
5. **Edge Case Handling** - Consider failure modes proactively

### Agent Personas & Prompt Templates

**When to Use Each Persona**:

#### 1. Conservative Coder (Default for Core Systems)
**Use for**: Authentication, database migrations, payment logic, data integrity
**Prompt Template**:
```
As Conservative Coder, I need to [implement feature] in [file_path].

Requirements:
1. Write comprehensive tests FIRST (include edge cases: [specific examples])
2. Handle errors explicitly (no silent failures)
3. Add type hints and docstrings
4. Consider: What could go wrong? How do we recover?

Expected output: Tests → Implementation → Validation
```

**Example**:
```
As Conservative Coder, implement Redis caching in `feature_processor.py`.
Edge cases: connection failures, serialization errors, TTL expiry mid-request.
Tests first, then implementation with graceful degradation on cache miss.
```

#### 2. Performance Optimizer (For Speed-Critical Code)
**Use for**: Feature engineering, data processing pipelines, high-frequency operations
**Prompt Template**:
```
As Performance Optimizer, optimize [function/module] in [file_path].

Current performance: [metric] 
Target: [metric]

Constraints:
- Must maintain existing API
- Cannot break tests
- Benchmark before/after with [specific dataset]

Output: Profiling data → Optimization → Benchmark comparison
```

**Example**:
```
As Performance Optimizer, reduce quality check duration from 1s to <300ms.
Current: Z-score outlier detection on 10k rows.
Profile with cProfile, optimize NumPy operations, benchmark on BTCUSDT 1-week data.
```

#### 3. Integration Specialist (For Cross-Service Features)
**Use for**: API integration, service-to-service communication, external APIs
**Prompt Template**:
```
As Integration Specialist, integrate [system A] with [system B].

Data flow: [describe flow]
Failure modes: [list potential failures]
Fallback strategy: [e.g., cached responses, circuit breaker]

Output: Integration tests → Implementation → Error handling → Monitoring
```

**Example**:
```
As Integration Specialist, integrate EODHD API with TimescaleDB storage.
Failure modes: rate limits (1000/day), network errors, malformed responses.
Fallback: Use cached data, alert on staleness >24h.
Tests must mock API calls.
```

### Interaction Workflow (Step-by-Step)

**For Complex Tasks** (e.g., "Implement multi-agent debate system"):

1. **Analysis Phase**
   ```
   Before implementing, I need to:
   - Clarify requirements: [specific questions]
   - Identify dependencies: [list services/modules]
   - Assess risks: [potential issues]
   
   Should I proceed with [proposed approach]?
   ```

2. **Test Planning**
   ```
   I'll write tests for:
   - Happy path: [describe]
   - Edge cases: [list specific scenarios]
   - Failure modes: [how system degrades]
   
   Confirm test strategy before implementation?
   ```

3. **Implementation**
   ```
   Implementing in phases:
   Phase 1: [small testable unit]
   Phase 2: [build on Phase 1]
   Phase 3: [integration]
   
   Running tests after each phase.
   ```

4. **Validation**
   ```
   Validation checklist:
   - [ ] All tests passing (show output)
   - [ ] Linting clean (`make lint`)
   - [ ] Performance acceptable ([metric])
   - [ ] Documentation updated
   
   Request final review?
   ```

### Asking for Alternatives & Debate

**When Uncertain, Request Options**:
```
I see two approaches for [problem]:

Option A: [description]
Pros: [list]
Cons: [list]

Option B: [description]  
Pros: [list]
Cons: [list]

Which aligns better with [project goal]? Or is there a third option?
```

**Debugging Strategy**:
```
Issue: [describe problem]

Investigation:
1. Checked: [what I verified]
2. Found: [specific error/behavior]
3. Hypothesis: [what I think is wrong]

Should I:
A) [proposed fix]
B) [alternative approach]
C) Provide more diagnostic info first?
```

### Ethical AI Checks (For Trading Strategies)

**Before Implementing Trading Logic, Ask**:
```
Ethical Review for [strategy]:

1. Market Manipulation: Could this create wash trades or spoofing?
   - Check: [specific safeguards]

2. Fairness: Does this exploit informational asymmetry ethically?
   - Justification: [why this is acceptable]

3. Risk Management: What's max exposure/drawdown?
   - Limits: [hard stops]

4. Transparency: Can we explain decisions to regulators?
   - Documentation: [audit trail]

Proceed if all checks pass.
```

### Human Review Mandates

**ALWAYS request human review for**:
- Authentication/security changes
- Database schema modifications
- Trading execution logic (order placement)
- Configuration affecting production systems
- Large refactors (>500 lines changed)

**Prompt Template**:
```
⚠️ HUMAN REVIEW REQUIRED

Changes: [summary]
Files: [list modified files]
Risk: [potential impact]

Please review before I:
- [ ] Commit changes
- [ ] Run migrations
- [ ] Deploy to production
```

### Best Practices Integration

**Data Quality (Per LuxAlgo/QuantStart)**:
- Pre-trade validation: Outlier detection, sanity tests
- Backtests require out-of-sample validation
- Walk-forward optimization to avoid overfitting

**Risk-Adjusted Metrics (Focus on Real Performance)**:
- Sharpe, Calmar, Sortino > raw returns
- Acknowledge uncertainty: "Backtests suggest X, but real-world may vary"
- Include forward test degradation estimates (50-70% from backtest)

**Modular Architecture (Already Implemented)**:
- Services communicate via HTTP APIs only
- No cross-service imports
- Clear service boundaries per table above

### FKS Repository Structure (Monorepo)

```
fks/  (THIS REPOSITORY)
├── docker-compose.yml         # 8-service orchestration
├── docker-compose.gpu.yml     # GPU overrides for fks_ai (Ollama)
├── requirements.txt           # Python dependencies
├── Makefile                   # Dev commands (make up, make gpu-up)
├── manage.py                  # Django management
│
├── src/                       # All source code
│   ├── services/             # Microservices (each has own README)
│   │   ├── api/              # fks_api - FastAPI gateway
│   │   ├── app/              # fks_app - business logic
│   │   ├── ai/               # fks_ai - GPU ML/RAG
│   │   ├── data/             # fks_data - market data collection
│   │   ├── execution/        # fks_execution - Rust order execution
│   │   ├── ninja/            # fks_ninja - .NET NinjaTrader bridge
│   │   └── web/              # fks_web - Django UI
│   │
│   ├── monitor/              # Service registry & health (fks_main)
│   ├── authentication/       # Centralized auth (fks_main)
│   ├── core/                 # Core models, exceptions, database
│   ├── framework/            # Middleware, config, patterns
│   └── tests/                # Unit/integration tests
│
├── docs/                      # Comprehensive documentation
│   ├── AI_STRATEGY_INTEGRATION.md      # 5-phase AI plan
│   ├── CRYPTO_REGIME_BACKTESTING.md    # Regime detection research
│   ├── ARCHITECTURE.md                  # Detailed architecture
│   ├── PHASE_STATUS.md                  # Current status tracker
│   └── PHASE_*.md                       # Development phase plans
│
├── monitoring/                # Prometheus/Grafana config
│   ├── prometheus/           # Metrics + alert rules
│   └── grafana/              # Dashboards (quality_monitoring.json)
│
├── sql/                       # TimescaleDB init scripts + migrations
├── scripts/                   # Automation scripts
└── tests/                     # Orchestrator tests
```

## 🛠️ Developer Workflows

### Starting Services
```bash
# Standard stack (8 services)
make up              # Start all services
make logs            # Follow logs
make down            # Stop everything
make restart         # Restart

# GPU stack (adds Ollama + fks_ai)
make gpu-up          # Combines docker-compose.yml + docker-compose.gpu.yml
```

**Access Points**:
- **Health Dashboard**: http://localhost:8000/health/dashboard/
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- Django Admin: http://localhost:8000/admin
- Flower (Celery): http://localhost:5555

### Database & Shell Commands
```bash
make migrate         # Run Django migrations
make shell           # Django shell (ORM access)
make db-shell        # PostgreSQL psql shell
```

### Testing (TDD Approach)
```bash
# Run tests in Docker containers (NOT on host)
docker-compose exec fks_app pytest tests/unit/strategies/asmbtr/ -v  # ASMBTR (108)
docker-compose exec fks_app pytest tests/unit/validators/ -v          # Quality (34)
docker-compose exec fks_app pytest tests/unit/cache/ -v              # Redis (20)
docker-compose exec fks_app pytest tests/unit/metrics/ -v            # Monitoring (40)

# Service-specific tests
docker-compose exec fks_api pytest tests/
docker-compose exec fks_data pytest tests/

# With coverage
docker-compose exec fks_app pytest --cov=strategies.asmbtr --cov-report=term-missing
```

**Test Markers** (`pytest.ini`): unit, integration, slow, data, backtest, trading, api, web

**Current Status**: 188/188 tests passing (100% coverage for implemented features)

### Code Quality
```bash
make lint            # ruff + mypy + black
make format          # auto-format with black + isort
```

## 📝 Project-Specific Conventions

### File Organization
- **Django apps**: Directory-based under `src/` (e.g., `src/authentication/`, `src/trading/`)
- **Models**: `models.py` or `models/` subdirectory
- **Tests**: Mirror source structure in `tests/unit/` and `tests/integration/`
- **Naming**: `snake_case` for files/functions/variables; `PascalCase` for classes

### Import Patterns
```python
# Framework imports
from framework.middleware.circuit_breaker import CircuitBreaker
from framework.config.constants import TRADING_SYMBOLS

# Core models
from core.database.models import Trade, Position

# Django apps
from authentication.models import User
```

**Avoid**: Importing from `infrastructure/` or legacy `services/` modules

### Exception Hierarchy
All custom exceptions inherit from `FKSException` in `src/core/exceptions/__init__.py`:
- `TradingError`, `DataError`, `ModelError`, `ConfigError`
- `CircuitBreakerError`, `RateLimitError`
- Use specific exceptions, not generic `Exception`

### Configuration
- **Django**: Environment variables via `.env` → `services/web/src/django/settings.py`
- **Framework**: Type-safe dataclasses in `src/framework/config/`
- **Service-specific**: Each microservice has own config (e.g., `services/api/config.py`)
- **Never hardcode**: API keys, secrets, DB credentials

## 🔌 Critical Integration Points

### TimescaleDB + pgvector
- Hypertables for time-series data (trades, market data)
- pgvector for RAG embeddings
- Extensions: `timescaledb,vector` in shared_preload_libraries

### Redis Caching
- Feature cache with TTL (1m=60s, 1h=3600s, 1d=86400s, 1w=604800s)
- EODHD API response caching (fundamentals=24h, earnings=1h)
- 80-95% performance improvement on repeated queries

### RAG System (GPU Stack)
- **Embeddings**: sentence-transformers (local) + OpenAI fallback
- **Vector Store**: pgvector in PostgreSQL
- **LLM**: Ollama/llama.cpp with CUDA
- **Purpose**: AI-powered trading intelligence and daily recommendations

### Monitoring Stack
- **Prometheus**: 10 quality metrics, 15s evaluation interval
- **Grafana**: 8-panel quality dashboard at http://localhost:3000
- **Alertmanager**: Discord webhook for critical alerts
- **TimescaleDB**: Continuous aggregates for hourly/daily statistics

### Discord Integration
- Trade notifications via `DISCORD_WEBHOOK_URL` env var
- Quality alerts, system errors, MDD breaches

## 🎯 Current Development Priorities

### Phase 6: Multi-Agent Foundation (Weeks 1-4, 5-7 days each)

**Goal**: Establish LangGraph infrastructure for AI-powered trading decisions

**Phase 6.1: Agentic Foundation** (5-7 days)
- Setup LangChain/LangGraph with Ollama (llama3.2:3b)
- Define AgentState schema: market_data, signals, debates, memory
- Implement ChromaDB memory for agent interactions
- Create base agent factory with shared prompt templates

**Phase 6.2: Multi-Agent Debate** (7-10 days)
- **4 Analyst Agents**: Technical, Sentiment, Macro, Risk
- **3 Debate Agents**: Bull, Bear, Manager
- **3 Trader Personas + Judge**: Conservative, Moderate, Aggressive
- Adversarial debate loop with synthesis

**Phase 6.3: Graph Orchestration** (7-10 days)
- StateGraph: Analysts → Debaters → Manager → Trader → Reflection
- Conditional routing based on market regime
- Signal processor for unified outputs
- Reflection node for continuous learning

**Acceptance Criteria**:
- [ ] Ollama serving llama3.2:3b on fks_ai (8006)
- [ ] All 7 agents operational with debates generating contrasting views
- [ ] Graph execution <5 seconds, signal quality >60%
- [ ] ChromaDB memory functional with >1000 insights

**Code Location**: `services/ai/src/agents/`, `services/ai/src/graph/`, `services/ai/src/memory/`

---

### Medium-Term: Advanced AI (Weeks 5-12)

**Phase 7: Evaluation Framework** (3-5 days)
- Confusion matrices for ASMBTR/ML models
- LLM-judge audits for factual consistency
- Ground truth backtests vs. reality

**Phase 8: Hybrid Models & Risk** (5-7 days)
- LLM vetoes for signal validation
- Walk-forward optimization (WFO)
- MDD protection circuit breakers
- CPI-Gold hedging strategy

**Phase 9: Markov Integration** (5-7 days)
- Bull/bear/sideways state transitions
- Steady-state probability computation
- Hybrid ASMBTR+Markov signals

**Target Performance**: Calmar >0.45, Sharpe ~0.5, MDD <-0.5

---

### Long-Term: Production (Weeks 13-16)

**Phase 10: Deployment** (3-5 days)
- Grafana dashboards for agent metrics
- Discord alerts for critical events
- Resource limits and monitoring

**Phase 11: Iteration** (Ongoing)
- Paper trading (4 weeks)
- A/B testing (ASMBTR vs Hybrid vs Multi-agent)
- Ethics audit, v2 planning

**Target**: Real-world Sharpe >2.5 (vs. buy-hold 1.5)

## ⚠️ Common Pitfalls & Troubleshooting

### Critical Rules
1. **Don't bypass fks_execution** - ONLY service that talks to exchanges/brokers
2. **Don't query exchanges directly** - Use fks_data for ALL market data
3. **GPU commands differ** - Use `make gpu-up` (combines base + GPU compose files)
4. **Cross-service imports forbidden** - Services communicate via HTTP APIs only
5. **Django settings location** - `services/web/src/django/settings.py`, NOT `src/web/django/`
6. **DJANGO_SETTINGS_MODULE** - Root `manage.py` sets to `services.web.src.django.settings`

### Common Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| **Import Errors** | `ModuleNotFoundError: No module named 'config'` | Use `from framework.config.constants` instead |
| **Service Communication** | `ConnectionRefusedError` | Check `docker-compose ps`, use service name not localhost |
| **Test Discovery** | Pytest can't find tests | Files named `test_*.py` in `tests/` directory |
| **Docker Issues** | Services won't start | Check `.env` exists, run `make down && make up` |
| **Database Migrations** | Migration conflicts | Check `make migrate`, resolve in `src/*/migrations/` |
| **ASMBTR Tests** | Zero price changes failing | StateEncoder skips zero changes (not treated as DOWN) |
| **Container Resources** | Tests timeout/hang | Restart: `docker-compose down && docker-compose up -d` |

### ASMBTR Test Learnings (Oct 29, 2025)
- **Zero price changes**: Skipped entirely, not treated as DOWN movement
- **Attribute names**: Use `StateEncoder.encoder` (not `btr_encoder`), `PredictionTable.state_counts` (not `table`)
- **Dataclass properties**: `StatePrediction.prediction` is `@property`, not `__init__` param
- **API methods**: Use `save_to_dict()`/`load_from_dict()`, not `save()`/`load()`
- **Decay rate**: Must be 0.9-1.0, enforced in `PredictionTable.__init__`

### Getting Help
- **Logs**: `make logs` for error details
- **Health**: http://localhost:8000/health/dashboard/ for system status
- **Docs**: `docs/ARCHITECTURE.md` for detailed info
- **Tests**: `pytest tests/unit/test_X.py -v` to isolate issues

## 📚 Documentation & Key Files

### Strategic Documentation
- **AI Enhancement Plan**: `.github/copilot-instructions.md` - 12-phase AI implementation
- **Phase Status**: `docs/PHASE_STATUS.md` - Current progress tracker
- **Architecture**: `docs/ARCHITECTURE.md` - Detailed system design
- **AI Strategy**: `docs/AI_STRATEGY_INTEGRATION.md` - Original 5-phase plan
- **Regime Research**: `docs/CRYPTO_REGIME_BACKTESTING.md` - Research analysis

### Operational Files
- **Django Settings**: `src/services/web/src/django/settings.py`
- **Root Management**: `manage.py` (sets DJANGO_SETTINGS_MODULE)
- **Docker Orchestration**: `docker-compose.yml`, `docker-compose.gpu.yml`
- **Database**: `sql/fundamentals_schema.sql`, `sql/migrations/`
- **Monitoring**: `monitoring/prometheus/`, `monitoring/grafana/dashboards/`
- **Testing**: `pytest.ini`, tests in `tests/unit/` and `src/services/*/tests/`

## 🔧 When Making Changes

### Pre-Development Checklist
1. **Identify target service** - Determine which microservice needs changes
2. **Review service boundaries** - Ensure changes respect service responsibilities
3. **Check existing tests** - Understand test patterns before adding code
4. **Verify phase alignment** - Confirm work aligns with current Phase 6 goals

### TDD Workflow (Test-Driven Development)
1. **Write tests first** - Create test cases before implementation
2. **Implement changes** - Follow existing code patterns
3. **Run tests frequently** - `docker-compose exec <service> pytest tests/` after each change
4. **Validate syntax** - `make lint` to check style
5. **Format code** - `make format` for consistency

### Post-Development Checklist
1. **Run migrations** - `make migrate` after model changes
2. **Test locally** - `make up` + `make logs` to verify services
3. **Full test suite** - Run complete tests for affected service
4. **Check coverage** - Ensure >80% coverage for new code
5. **Update docs** - If changing architecture or major features
6. **Verify no regressions** - Ensure existing functionality still works

### Code Style & Quality
- **Formatting**: Black (line length 100) + isort
- **Type hints**: Add for function parameters and returns
- **Docstrings**: Google-style for classes and functions
- **Comments**: Only when code intent isn't obvious
- **DRY principle**: Extract repeated code into reusable components

## 📊 Test Status Summary

- ✅ **188/188 passing** - Complete test coverage for implemented features (Phase 5.6 complete, Oct 30, 2025)
- ✅ **ASMBTR Framework**: 108/108 passing (100%) - Baseline trading strategy fully validated
- ✅ **Redis Caching**: 20/20 passing (100%) - Feature cache and EODHD response caching
- ✅ **Quality Validators**: 34/34 passing (100%) - Outlier, freshness, completeness, scoring
- ✅ **Quality Monitoring**: 40/40 passing (100%) - Prometheus metrics, collector, TimescaleDB, E2E
- 🎯 **Next Goal**: Phase 6 - Multi-agent AI system (LangGraph + Ollama + ChromaDB)

**Test Execution**:
```bash
# Run all test suites
docker-compose exec fks_app pytest tests/unit/strategies/asmbtr/ -v  # ASMBTR (108)
docker-compose exec fks_app pytest tests/unit/cache/ -v              # Redis (20)
docker-compose exec fks_app pytest tests/unit/validators/ -v         # Quality (34)
docker-compose exec fks_app pytest tests/unit/metrics/ -v            # Monitoring (40)

# With coverage
docker-compose exec fks_app pytest --cov=strategies.asmbtr --cov-report=term-missing
```

**Target**: 80%+ coverage across all 8 microservices

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

### Phase 5 Key Files Created/Modified:
```
src/services/data/src/adapters/eodhd.py                     (355 lines) - EODHD API adapter
src/services/data/src/collectors/fundamentals_collector.py  (447 lines) - Async fundamentals collector  
src/services/app/src/features/feature_processor.py          (502 lines) - Feature engineering pipeline
src/services/app/src/cache/feature_cache.py                 (450 lines) - Redis caching layer
src/services/data/src/validators/*.py                       (1,316 lines) - Quality validators
src/services/data/src/metrics/*.py                          (670 lines) - Prometheus metrics + collector
sql/fundamentals_schema.sql                                 (450 lines) - Complete schema definition
sql/migrations/004_quality_metrics.sql                      (159 lines) - Quality metrics hypertable
monitoring/grafana/dashboards/quality_monitoring.json       (660 lines) - 8-panel dashboard
```

**Phase 5 Cumulative**: 9,227 lines added, 188/188 tests passing (Oct 30, 2025)

---
*Last Updated: October 30, 2025 | Copilot Instructions v5.1*  
*Phase 5.6 Complete - Quality Monitoring & Observability | Next: Phase 6 Multi-Agent Foundation*  
*Architecture: 8-Service Microservices | Test Status: 188/188 passing (100%)*
