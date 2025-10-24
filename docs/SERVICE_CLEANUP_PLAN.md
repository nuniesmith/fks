# FKS Multi-Repo Service Cleanup Plan

## Architecture Overview

Based on your requirements, here's the clarified architecture:

### Service Roles

1. **FKS Main** (`nuniesmith/fks`) - **Orchestrator & Monitor**
   - Oversees all services via monitoring dashboard
   - Service registry and health checks
   - Django admin interface
   - Central configuration management
   - **Does NOT contain business logic** - delegates to services

2. **fks_api** (`repo/api`) - **API Gateway**
   - Internal service-to-service communication
   - External API endpoints (REST/GraphQL)
   - Authentication & authorization layer
   - Rate limiting & request validation
   - Routes requests to appropriate services (data, execution, web)

3. **fks_app** (`repo/app`) - **Main Application Logic**
   - Core trading application business logic
   - Strategy management and signal generation
   - Portfolio management and optimization
   - Backtesting engine
   - ML/AI model orchestration
   - **Primary service that coordinates data → execution flow**

4. **fks_data** (`repo/data`) - **Data Ingestion & Storage**
   - **Always-on data collection** for enabled assets
   - Multi-source data aggregation (Binance, Kraken, etc.)
   - Local caching and time-series storage (TimescaleDB)
   - Data normalization and validation
   - WebSocket feeds for real-time data
   - Other services query fks_data for market data (not exchanges directly)

5. **fks_execution** (`repo/execution`) - **Fast Rust Execution Engine**
   - **High-performance order execution** (Rust for speed)
   - Direct exchange/broker API integration
   - Order lifecycle management (create, update, cancel)
   - Position tracking and updates
   - Execution reports and fills
   - Other FKS services call fks_execution (never exchange APIs directly)

6. **fks_ninja** (`repo/ninja`) - **NinjaTrader 8 Bridge**
   - C#-based bridge for NinjaTrader 8 integration
   - Indicator/strategy to receive signals from FKS platform
   - Futures prop firm trading support (FXIFY, Topstep, etc.)
   - AT Interface API communication
   - Signal relay from fks_app → NinjaTrader

7. **fks_web** (`repo/web`) - **Django Web UI**
   - User-facing web interface
   - Django templates with Bootstrap 5
   - Forms for strategy configuration
   - Dashboard visualizations
   - Mermaid diagrams for workflows
   - Communicates with fks_api for all data/actions

---

## Current State Analysis

### ✅ What's Good

#### FKS Main (Orchestrator)
- ✅ Monitor app is well-structured (`src/monitor/`)
- ✅ Service registry models are comprehensive
- ✅ Health check automation with Celery
- ✅ Docker Compose orchestration is complete
- ✅ Makefile commands for multi-repo operations

#### fks_api (API Gateway)
- ✅ FastAPI-based (good for async performance)
- ✅ Has domain-driven directory structure
- ✅ Dockerfile and CI/CD setup exists

#### fks_data (Data Service)
- ✅ Has pytest setup and CI/CD
- ✅ Dockerfile exists
- ✅ README with clear purpose

#### fks_execution (Rust Execution)
- ✅ Rust Cargo project structure
- ✅ Dockerfile for containerization
- ✅ Clear separation of concerns (Rust for speed)

#### fks_ninja (NinjaTrader Bridge)
- ✅ C# .NET solution structure
- ✅ Comprehensive documentation
- ✅ Makefile for build automation

#### fks_web (Django UI)
- ✅ Basic structure exists
- ✅ Has src/ directory for templates/static

---

### ❌ What Needs Cleanup

#### FKS Main (Orchestrator)
**Issues:**
1. **Duplicate business logic** - Contains `src/trading/`, `src/data/`, `src/api/` which should be in respective services
2. **Monolith remnants** - `src/app.py`, `src/engine/`, `src/infrastructure/` are legacy
3. **Confusing structure** - Business logic mixed with orchestration
4. **Service overlap** - Monitor service should coordinate, not implement trading logic

**Proposed Structure:**
```
fks/ (main repo)
├── src/
│   ├── monitor/          # ✅ Keep - service registry & health checks
│   ├── authentication/   # ✅ Keep - centralized auth (delegates to fks_api)
│   ├── web/             # ❌ MOVE to repo/web - Django UI
│   ├── framework/       # ⚠️  EVALUATE - shared utilities (consider library)
│   ├── core/            # ⚠️  EVALUATE - database models (should be in services)
│   │
│   ├── api/             # ❌ REMOVE - belongs in repo/api
│   ├── trading/         # ❌ REMOVE - belongs in repo/app
│   ├── data/            # ❌ REMOVE - belongs in repo/data
│   ├── engine/          # ❌ REMOVE - legacy
│   ├── infrastructure/  # ❌ REMOVE - legacy
│   ├── services/        # ❌ REMOVE - legacy
│   └── app.py           # ❌ REMOVE - legacy monolith
│
├── docker-compose.yml   # ✅ Keep - orchestrates all services
├── Makefile            # ✅ Keep - multi-repo commands
└── docs/               # ✅ Keep - architecture docs
```

#### fks_api (API Gateway)
**Issues:**
1. **Too much domain logic** - Has `domain/trading/`, `domain/ml/`, `domain/market/` which belong in fks_app
2. **Should be thin** - API Gateway should route, not implement business logic
3. **Bridge logic misplaced** - `domain/trading/bridge/` belongs in respective services

**Proposed Structure:**
```
fks_api/
├── src/
│   ├── app.py                 # FastAPI application
│   ├── config.py              # Configuration
│   ├── middleware/            # Auth, rate limiting, CORS
│   ├── routes/                # Route definitions
│   │   ├── health.py          # Health check endpoint
│   │   ├── auth.py            # Authentication routes (delegates to main)
│   │   ├── data_proxy.py      # Proxy to fks_data
│   │   ├── app_proxy.py       # Proxy to fks_app
│   │   ├── execution_proxy.py # Proxy to fks_execution
│   │   └── web_proxy.py       # Proxy to fks_web
│   ├── dependencies/          # ✅ Keep - FastAPI dependencies
│   │   ├── auth.py
│   │   ├── database.py (minimal - only for API keys/sessions)
│   │   └── services.py (service clients)
│   │
│   └── domain/                # ❌ REMOVE ALL - move to fks_app
│       ├── trading/
│       ├── ml/
│       ├── market/
│       └── ...
│
├── Dockerfile
├── requirements.txt
└── README.md
```

**What fks_api Should Do:**
- Accept HTTP requests from external clients
- Validate request format and authentication
- Route to appropriate service (data/app/execution)
- Aggregate responses if needed
- Return formatted responses
- Handle rate limiting and caching

**What fks_api Should NOT Do:**
- Generate trading signals
- Execute ML models
- Manage portfolios
- Store market data
- Execute trades

#### fks_app (Main Application)
**Current State:** Minimal structure (LICENSE only)

**Proposed Structure:**
```
fks_app/
├── src/
│   ├── main.py                  # FastAPI application entry
│   ├── config.py                # Configuration
│   ├── health.py                # Health check
│   │
│   ├── domain/                  # Business logic (MOVE from fks_api)
│   │   ├── trading/
│   │   │   ├── strategies/       # Trading strategies
│   │   │   ├── signals/          # Signal generation
│   │   │   ├── backtesting/      # Backtesting engine
│   │   │   └── optimization/     # Strategy optimization
│   │   ├── portfolio/
│   │   │   ├── manager.py        # Portfolio management
│   │   │   ├── rebalancer.py    # Rebalancing logic
│   │   │   └── risk.py           # Risk management
│   │   ├── ml/
│   │   │   ├── models/           # ML models
│   │   │   ├── training/         # Training pipeline
│   │   │   └── prediction/       # Prediction service
│   │   └── analytics/
│   │       ├── performance.py    # Performance tracking
│   │       └── reporting.py      # Report generation
│   │
│   ├── services/                # Service layer
│   │   ├── data_service.py      # Client for fks_data
│   │   ├── execution_service.py # Client for fks_execution
│   │   └── notification_service.py # Discord, email, etc.
│   │
│   ├── routes/                  # API routes
│   │   ├── strategies.py
│   │   ├── signals.py
│   │   ├── portfolios.py
│   │   └── backtests.py
│   │
│   └── tasks/                   # Celery tasks
│       ├── strategy_tasks.py
│       ├── signal_tasks.py
│       └── backtest_tasks.py
│
├── Dockerfile
├── requirements.txt
├── docker-compose.yml (for local dev)
└── README.md
```

**What fks_app Should Do:**
- Generate trading signals based on strategies
- Manage portfolio allocation
- Run backtests on historical data
- Train and deploy ML models
- Optimize strategy parameters
- Send signals to fks_execution
- Coordinate data requests to fks_data
- Business logic orchestration

**What fks_app Should NOT Do:**
- Fetch raw market data (use fks_data)
- Execute orders directly (use fks_execution)
- Store time-series data (use fks_data)
- Handle HTTP routing (use fks_api)

#### fks_data (Data Service)
**Current State:** Has basic structure, needs expansion

**Proposed Structure:**
```
fks_data/
├── src/
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configuration
│   ├── health.py                  # Health check
│   │
│   ├── collectors/                # Data collection
│   │   ├── base.py                # Base collector interface
│   │   ├── binance_collector.py  # Binance data
│   │   ├── kraken_collector.py   # Kraken data
│   │   ├── coinbase_collector.py # Coinbase data
│   │   └── polygon_collector.py  # Stocks (future)
│   │
│   ├── storage/                   # Data persistence
│   │   ├── timescale_writer.py   # TimescaleDB writer
│   │   ├── redis_cache.py        # Redis caching
│   │   └── models.py             # SQLAlchemy models
│   │
│   ├── processors/                # Data processing
│   │   ├── normalizer.py         # Data normalization
│   │   ├── validator.py          # Data validation
│   │   └── aggregator.py         # OHLCV aggregation
│   │
│   ├── websocket/                 # Real-time feeds
│   │   ├── manager.py            # WebSocket manager
│   │   └── handlers.py           # Message handlers
│   │
│   ├── routes/                    # API routes
│   │   ├── market_data.py        # GET /market-data/{symbol}
│   │   ├── historical.py         # GET /historical/{symbol}
│   │   ├── websocket.py          # WebSocket subscriptions
│   │   └── assets.py             # GET /assets (enabled list)
│   │
│   └── tasks/                     # Celery tasks
│       ├── sync_tasks.py         # Periodic data sync
│       └── cleanup_tasks.py      # Old data cleanup
│
├── Dockerfile
├── requirements.txt
├── docker-compose.yml
└── README.md
```

**Asset Management:**
- Store enabled assets in database/config
- When asset is enabled, start collecting data
- When asset is disabled, stop collection (keep historical data)
- Auto-fill gaps in data if missing

**What fks_data Should Do:**
- Continuously collect market data for enabled assets
- Store data in TimescaleDB with hypertables
- Cache frequently accessed data in Redis
- Normalize data across exchanges
- Provide REST API for historical queries
- Provide WebSocket feeds for real-time data
- Validate and clean incoming data

**What fks_data Should NOT Do:**
- Generate trading signals
- Execute trades
- Manage strategies
- ML model training

#### fks_execution (Rust Execution Engine)
**Current State:** Has Cargo structure, needs implementation

**Proposed Structure:**
```
fks_execution/
├── src/
│   ├── main.rs                    # Application entry
│   ├── config.rs                  # Configuration
│   ├── health.rs                  # Health check endpoint
│   │
│   ├── api/                       # HTTP API (Actix-web/Axum)
│   │   ├── routes.rs              # Route definitions
│   │   └── handlers.rs            # Request handlers
│   │
│   ├── exchanges/                 # Exchange integrations
│   │   ├── binance.rs             # Binance API client
│   │   ├── kraken.rs              # Kraken API client
│   │   ├── coinbase.rs            # Coinbase API client
│   │   └── traits.rs              # Common exchange trait
│   │
│   ├── brokers/                   # Broker integrations (future)
│   │   └── interactive_brokers.rs
│   │
│   ├── orders/                    # Order management
│   │   ├── manager.rs             # Order lifecycle
│   │   ├── validator.rs           # Order validation
│   │   └── types.rs               # Order types
│   │
│   ├── positions/                 # Position tracking
│   │   ├── tracker.rs             # Position manager
│   │   └── models.rs              # Position models
│   │
│   ├── risk/                      # Risk checks
│   │   ├── limits.rs              # Position/order limits
│   │   └── circuit_breaker.rs    # Emergency stop
│   │
│   └── storage/                   # Persistence (PostgreSQL)
│       ├── database.rs            # Database client
│       └── models.rs              # SQLx models
│
├── Cargo.toml
├── Dockerfile
└── README.md
```

**Dependencies:**
- `tokio` - Async runtime
- `actix-web` or `axum` - HTTP server
- `sqlx` - PostgreSQL client
- `reqwest` - HTTP client for exchange APIs
- `serde` - Serialization
- `tracing` - Logging

**What fks_execution Should Do:**
- **ONLY entry point** for exchange/broker communication
- Execute orders with sub-millisecond latency
- Track positions across multiple exchanges
- Validate orders before submission
- Handle order fills and updates
- Provide order status queries
- Emergency stop/circuit breaker
- Rate limit exchange API calls

**What fks_execution Should NOT Do:**
- Generate trading signals (fks_app does this)
- Store market data (fks_data does this)
- Run strategies or backtests
- Make trading decisions

#### fks_ninja (NinjaTrader Bridge)
**Current State:** Good - has C# solution structure

**Proposed Structure:**
```
fks_ninja/
├── FKS.Indicators/                # NinjaTrader 8 Indicators
│   ├── FKSSignalIndicator.cs     # Display signals on chart
│   └── FKSStatusIndicator.cs     # Connection status
│
├── FKS.Strategies/                # NinjaTrader 8 Strategies
│   ├── FKSAutomatedStrategy.cs   # Receive & execute signals
│   └── FKSSignalRelay.cs         # Forward signals only
│
├── FKS.Bridge/                    # Bridge Service (C#)
│   ├── Program.cs                # Bridge application
│   ├── SignalReceiver.cs         # Receive from fks_app
│   ├── NTConnector.cs            # AT Interface connector
│   └── OrderManager.cs           # Order lifecycle
│
├── Dockerfile
├── FKS.sln
└── README.md
```

**What fks_ninja Should Do:**
- Receive signals from fks_app via HTTP/WebSocket
- Forward signals to NinjaTrader 8 via AT Interface
- Support manual and automated execution modes
- Display signals on NinjaTrader charts
- Report fills back to fks_execution
- Support prop firm accounts (separate NT instances)

**What fks_ninja Should NOT Do:**
- Generate signals
- Store market data
- Run backtests
- Direct exchange communication (NT handles this)

#### fks_web (Django UI)
**Current State:** Minimal (README only)

**Proposed Structure:**
```
fks_web/
├── src/
│   ├── manage.py
│   ├── web/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   │
│   ├── templates/                 # Django templates
│   │   ├── base.html             # Base template (Bootstrap 5, Mermaid)
│   │   ├── pages/
│   │   │   ├── dashboard.html    # Main dashboard
│   │   │   ├── strategies.html   # Strategy management
│   │   │   ├── signals.html      # Signal approvals
│   │   │   ├── portfolio.html    # Portfolio view
│   │   │   ├── backtests.html    # Backtest results
│   │   │   └── settings.html     # Configuration
│   │   └── components/
│   │       ├── navbar.html
│   │       └── charts.html
│   │
│   ├── static/                    # Static assets
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   │
│   ├── dashboard/                 # Dashboard app
│   │   ├── views.py
│   │   ├── forms.py
│   │   └── urls.py
│   │
│   ├── strategies/                # Strategy management app
│   ├── signals/                   # Signal management app
│   ├── portfolio/                 # Portfolio app
│   └── settings_app/              # Settings app
│
├── Dockerfile
├── requirements.txt
└── README.md
```

**What fks_web Should Do:**
- Provide user-facing web interface
- Display dashboards and visualizations
- Strategy configuration forms
- Signal approval/rejection UI
- Portfolio monitoring
- Backtest result viewing
- **All data fetched from fks_api**

**What fks_web Should NOT Do:**
- Direct database queries (use fks_api)
- Business logic (use fks_app)
- Execute trades (use fks_api → fks_execution)

---

## Data Flow Architecture

### Flow 1: Market Data Collection (Always-On)
```
Exchanges (Binance, Kraken, etc.)
    ↓
fks_data (collectors)
    ↓
TimescaleDB (storage) + Redis (cache)
    ↓
fks_app (queries for strategy execution)
```

### Flow 2: Signal Generation → Execution
```
fks_app (generates signal)
    ↓
fks_app (validates with fks_data)
    ↓
fks_execution (executes order on exchange)
    ↓
fks_execution (reports fill)
    ↓
fks_app (updates portfolio)
```

### Flow 3: External API Request
```
External Client
    ↓
fks_api (authentication & routing)
    ↓
fks_app (business logic)
    ↓
fks_data (market data query)
    ↓
fks_api (aggregated response)
    ↓
External Client
```

### Flow 4: Web UI Interaction
```
User (browser)
    ↓
fks_web (Django UI)
    ↓
fks_api (REST API)
    ↓
fks_app (business logic)
    ↓
fks_web (rendered page)
```

### Flow 5: NinjaTrader Signal Execution
```
fks_app (generates signal)
    ↓
fks_ninja (bridge receives signal)
    ↓
NinjaTrader 8 (executes via AT Interface)
    ↓
Prop Firm Broker (order executed)
    ↓
fks_ninja (reports fill)
    ↓
fks_app (updates records)
```

---

## Migration Plan

### Phase 1: Clean Up FKS Main (Week 1-2)
**Priority: HIGH**

1. **Move Django UI to fks_web**
   ```bash
   # Move web templates and static files
   git mv src/web/templates/ repo/web/src/templates/
   git mv src/web/static/ repo/web/src/static/
   git mv src/web/django/ repo/web/src/web/
   
   # Update fks_web README
   # Commit to fks_web repo
   # Update docker-compose.yml to use fks_web service
   ```

2. **Archive Legacy Code**
   ```bash
   mkdir -p archive/
   git mv src/app.py archive/
   git mv src/engine/ archive/
   git mv src/infrastructure/ archive/
   git mv src/services/ archive/
   ```

3. **Reorganize FKS Main**
   ```
   src/
   ├── monitor/        # ✅ Keep - orchestration
   ├── authentication/ # ✅ Keep - centralized auth
   ├── framework/      # ⚠️  Evaluate - consider shared library
   └── core/           # ⚠️  Evaluate - minimal shared models
   ```

4. **Update docker-compose.yml**
   - Point `fks_web_ui` to `repo/web/`
   - Remove business logic from main container
   - Keep only monitoring and orchestration

### Phase 2: Move Business Logic to fks_app (Week 2-3)
**Priority: HIGH**

1. **Move Trading Logic from fks_api**
   ```bash
   # In fks_api repo
   git mv src/domain/trading/ ../../fks_app/src/domain/trading/
   git mv src/domain/portfolio/ ../../fks_app/src/domain/portfolio/
   git mv src/domain/ml/ ../../fks_app/src/domain/ml/
   ```

2. **Move Trading Logic from FKS Main**
   ```bash
   # In main fks repo
   git mv src/trading/ repo/app/src/domain/trading_legacy/
   # Merge with existing domain/trading in fks_app
   ```

3. **Set Up fks_app FastAPI**
   - Create main.py with FastAPI app
   - Define routes for strategies, signals, portfolios
   - Add Celery tasks for async processing
   - Create service clients for fks_data and fks_execution

4. **Update docker-compose.yml**
   - Add fks_app service definition
   - Configure environment variables
   - Set up dependencies (fks_data, fks_execution)

### Phase 3: Slim Down fks_api (Week 3-4)
**Priority: MEDIUM**

1. **Remove All Domain Logic**
   ```bash
   # In fks_api repo
   git rm -rf src/domain/
   ```

2. **Create Proxy Routes**
   ```python
   # src/routes/app_proxy.py
   @router.get("/strategies")
   async def get_strategies():
       """Proxy to fks_app."""
       response = await app_service_client.get("/strategies")
       return response.json()
   ```

3. **Implement API Gateway Pattern**
   - Request validation middleware
   - Authentication middleware (JWT validation)
   - Rate limiting middleware
   - Response aggregation for complex queries

### Phase 4: Implement fks_data (Week 4-5)
**Priority: HIGH**

1. **Set Up Data Collectors**
   - Binance collector with CCXT
   - Kraken collector
   - WebSocket managers for real-time data

2. **Implement Storage Layer**
   - TimescaleDB hypertables for OHLCV
   - Redis caching for hot data
   - SQLAlchemy models

3. **Create REST API**
   - GET /market-data/{symbol} - Latest data
   - GET /historical/{symbol} - Historical OHLCV
   - WebSocket /ws - Real-time feeds
   - GET /assets - List enabled assets
   - POST /assets/enable - Enable asset collection

4. **Add Celery Tasks**
   - Periodic sync tasks (every 1 minute)
   - Gap-filling tasks (detect missing data)
   - Cleanup tasks (prune old data)

### Phase 5: Implement fks_execution (Week 5-6)
**Priority: HIGH**

1. **Set Up Rust Project**
   - Actix-web or Axum HTTP server
   - SQLx for PostgreSQL
   - Reqwest for exchange API calls

2. **Implement Exchange Clients**
   - Binance REST API + WebSocket
   - Kraken REST API
   - Common trait for all exchanges

3. **Create Order Manager**
   - Order lifecycle FSM (new → pending → filled/cancelled)
   - Position tracker
   - Risk limits and validation

4. **Build REST API**
   - POST /orders - Create order
   - GET /orders/{id} - Get order status
   - DELETE /orders/{id} - Cancel order
   - GET /positions - Get all positions
   - GET /positions/{symbol} - Get position for symbol

### Phase 6: Complete fks_ninja (Week 6-7)
**Priority: MEDIUM**

1. **Build Bridge Service (C#)**
   - Receive signals from fks_app via HTTP
   - Connect to NinjaTrader via AT Interface
   - Order lifecycle management

2. **Create NinjaTrader Indicators**
   - Display signals on chart
   - Connection status indicator

3. **Create NinjaTrader Strategies**
   - Automated signal execution
   - Manual signal relay

### Phase 7: Complete fks_web (Week 7-8)
**Priority: MEDIUM**

1. **Build Django Apps**
   - Dashboard app (main view)
   - Strategies app (strategy management)
   - Signals app (signal approvals)
   - Portfolio app (portfolio monitoring)

2. **Create Templates**
   - Bootstrap 5 layouts
   - Mermaid diagram integration
   - Real-time updates with WebSocket

3. **Integrate with fks_api**
   - All data fetched via fks_api
   - No direct database queries

---

## Docker Compose Updates

```yaml
services:
  # FKS Main - Orchestrator
  fks_main:
    build: ./
    container_name: fks_main
    ports:
      - "8000:8000"
    environment:
      - SERVICE_NAME=fks_main
      - SERVICE_TYPE=orchestrator
    depends_on:
      - db
      - redis
    networks:
      - fks-network

  # API Gateway
  fks_api:
    build: ./repo/api
    container_name: fks_api
    expose:
      - "8001"
    environment:
      - SERVICE_NAME=fks_api
      - FKS_APP_URL=http://fks_app:8002
      - FKS_DATA_URL=http://fks_data:8003
      - FKS_EXECUTION_URL=http://fks_execution:8004
      - MONITOR_URL=http://fks_main:8000/monitor/api/discover/
    depends_on:
      - fks_app
      - fks_data
      - fks_main
    networks:
      - fks-network

  # Main Application Logic
  fks_app:
    build: ./repo/app
    container_name: fks_app
    expose:
      - "8002"
    environment:
      - SERVICE_NAME=fks_app
      - FKS_DATA_URL=http://fks_data:8003
      - FKS_EXECUTION_URL=http://fks_execution:8004
      - MONITOR_URL=http://fks_main:8000/monitor/api/discover/
    depends_on:
      - fks_data
      - fks_execution
      - redis
    networks:
      - fks-network

  # Data Ingestion Service
  fks_data:
    build: ./repo/data
    container_name: fks_data
    expose:
      - "8003"
    environment:
      - SERVICE_NAME=fks_data
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_API_SECRET=${BINANCE_API_SECRET}
      - MONITOR_URL=http://fks_main:8000/monitor/api/discover/
    depends_on:
      - db
      - redis
    networks:
      - fks-network

  # Rust Execution Engine
  fks_execution:
    build: ./repo/execution
    container_name: fks_execution
    expose:
      - "8004"
    environment:
      - SERVICE_NAME=fks_execution
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_API_SECRET=${BINANCE_API_SECRET}
      - MONITOR_URL=http://fks_main:8000/monitor/api/discover/
    depends_on:
      - db
    networks:
      - fks-network

  # NinjaTrader Bridge
  fks_ninja:
    build: ./repo/ninja
    container_name: fks_ninja
    expose:
      - "8005"
    environment:
      - SERVICE_NAME=fks_ninja
      - FKS_APP_URL=http://fks_app:8002
      - NINJATRADER_HOST=${NINJATRADER_HOST:-host.docker.internal}
      - NINJATRADER_PORT=${NINJATRADER_PORT:-47740}
      - MONITOR_URL=http://fks_main:8000/monitor/api/discover/
    networks:
      - fks-network

  # Django Web UI
  fks_web:
    build: ./repo/web
    container_name: fks_web
    expose:
      - "8006"
    environment:
      - SERVICE_NAME=fks_web
      - FKS_API_URL=http://fks_api:8001
      - MONITOR_URL=http://fks_main:8000/monitor/api/discover/
    depends_on:
      - fks_api
    networks:
      - fks-network
```

---

## Success Criteria

### FKS Main (Orchestrator)
- [ ] Only contains monitoring and orchestration code
- [ ] No business logic (trading, ML, data collection)
- [ ] Monitor dashboard shows all services
- [ ] Health checks pass for all services
- [ ] Centralized auth delegates to fks_api

### fks_api (API Gateway)
- [ ] No domain/business logic
- [ ] Only routing and validation
- [ ] Successfully proxies to all services
- [ ] Authentication middleware working
- [ ] Rate limiting functional

### fks_app (Main Application)
- [ ] Contains all trading strategy logic
- [ ] Portfolio management working
- [ ] ML models training and predicting
- [ ] Backtesting engine functional
- [ ] Generates signals correctly
- [ ] Communicates with fks_data and fks_execution

### fks_data (Data Service)
- [ ] Continuously collects data for enabled assets
- [ ] Data stored in TimescaleDB
- [ ] REST API provides historical data
- [ ] WebSocket provides real-time data
- [ ] Other services query fks_data (not exchanges)

### fks_execution (Rust Execution)
- [ ] Executes orders on exchanges
- [ ] Sub-millisecond latency
- [ ] Tracks positions accurately
- [ ] Only service that talks to exchanges
- [ ] Other services use fks_execution

### fks_ninja (NinjaTrader Bridge)
- [ ] Receives signals from fks_app
- [ ] Forwards to NinjaTrader 8
- [ ] Indicators display signals
- [ ] Strategy executes automatically
- [ ] Reports fills back to fks_app

### fks_web (Django UI)
- [ ] User-facing web interface
- [ ] All data via fks_api
- [ ] No direct database queries
- [ ] Bootstrap 5 responsive design
- [ ] Mermaid diagrams working

---

## Next Steps

1. **Review this plan** - Confirm architecture aligns with vision
2. **Prioritize phases** - Decide which services to implement first
3. **Start with Phase 1** - Clean up FKS Main (high priority)
4. **Implement fks_data** - Critical for all other services
5. **Implement fks_execution** - Required for trading
6. **Build fks_app** - Core business logic
7. **Polish fks_api** - Gateway layer
8. **Complete fks_web** - User interface
9. **Finish fks_ninja** - Prop firm integration

---

**Document Version:** 1.0  
**Date:** October 24, 2025  
**Status:** Planning Phase
