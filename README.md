# FKS Trading Platform - Orchestrator & Monitor

[![Tests](https://github.com/nuniesmith/fks/actions/workflows/tests.yml/badge.svg)](https://github.com/nuniesmith/fks/actions/workflows/tests.yml)

**FKS Main** is the orchestrator and monitoring hub for an **8-service microservices architecture**. It provides centralized authentication, service registry, health monitoring, and Celery Beat scheduling for the entire FKS trading ecosystem.

> **Architecture**: Multi-repo microservices with FKS Main as orchestrator (October 2025)  
> **Status**: Phase 1 Complete ✅ - Legacy monolith archived, clean orchestrator structure  
> **See**: [`docs/SERVICE_CLEANUP_PLAN.md`](docs/SERVICE_CLEANUP_PLAN.md) for migration plan and [`archive/legacy_monolith/README.md`](archive/legacy_monolith/README.md) for archived code

## 🎯 Microservices Architecture

### Service Overview

**FKS Main (This Repository)** - Orchestrator & Monitor
- **Role**: Service registry, health monitoring, centralized auth, Celery Beat scheduler
- **Port**: 8000 (Django + Gunicorn)
- **What It Does**: 
  - Monitors all microservices via health checks every 2 minutes
  - Provides service discovery endpoint for inter-service communication
  - Centralized authentication (delegates to fks_api for validation)
  - Celery Beat schedules periodic tasks across all services
- **What It Doesn't Do**: 
  - NO business logic (trading, signals, portfolio, etc.)
  - NO direct exchange communication
  - NO data collection or storage

**fks_api** - Thin API Gateway ([`repo/api/`](https://github.com/nuniesmith/api))
- **Role**: Routing, authentication, rate limiting
- **Port**: 8001 (FastAPI)
- **Responsibilities**: 
  - Route requests to appropriate services (fks_app, fks_data, fks_execution)
  - JWT authentication and API key validation
  - Rate limiting and request throttling
  - NO domain logic - pure gateway pattern

**fks_app** - Business Logic Service ([`repo/app/`](https://github.com/nuniesmith/app))
- **Role**: ALL trading logic, strategies, signals, portfolio management
- **Port**: 8002 (FastAPI)
- **Responsibilities**:
  - Strategy development and backtesting
  - Signal generation (RSI, MACD, Bollinger Bands, etc.)
  - Portfolio optimization with Optuna
  - Celery tasks for async operations
  - Queries fks_ai for ML predictions and RAG insights

**fks_ai** - AI/ML/RAG Service ([`repo/ai/`](https://github.com/nuniesmith/ai))
- **Role**: GPU-accelerated machine learning and RAG intelligence
- **Port**: 8006 (FastAPI)
- **GPU**: CUDA-enabled for local LLM inference
- **Responsibilities**:
  - Local LLM inference with Ollama/llama.cpp
  - RAG system with pgvector semantic search
  - Embeddings generation (sentence-transformers + OpenAI fallback)
  - Document processing and chunking
  - ML model training and forecasting
  - Zero-cost AI inference (no API fees)

**fks_data** - Data Collection Service ([`repo/data/`](https://github.com/nuniesmith/data))
- **Role**: Always-on market data collection and caching
- **Port**: 8003 (FastAPI)
- **Responsibilities**:
  - Continuous data collection for enabled assets
  - CCXT integration with Binance, Kraken, etc.
  - TimescaleDB storage with hypertables
  - Redis caching for fast queries
  - Other services query fks_data, NEVER exchanges directly

**fks_execution** - Execution Engine ([`repo/execution/`](https://github.com/nuniesmith/execution))
- **Role**: High-performance order execution
- **Port**: 8004 (Rust - Actix-web/Axum)
- **Responsibilities**:
  - ONLY service that talks to exchanges/brokers
  - Order lifecycle management with FSM
  - Position tracking and updates
  - Fast, reliable execution with circuit breaker

**fks_ninja** - NinjaTrader Bridge ([`repo/ninja/`](https://github.com/nuniesmith/ninja))
- **Role**: Bridge between FKS and NinjaTrader 8 for prop firm futures trading
- **Port**: 8005 (C# .NET)
- **Responsibilities**:
  - Receive signals from fks_app
  - Forward to NinjaTrader 8 via AT Interface
  - NinjaTrader indicators and strategies
  - Support prop firm accounts (FXIFY, Topstep, etc.)

**fks_web** - Web UI ([`repo/web/`](https://github.com/nuniesmith/web))
- **Role**: User interface with Django templates
- **Port**: 3001 (Django or Vite)
- **Responsibilities**:
  - Dashboard, strategies, signals, portfolio views
  - Bootstrap 5 templates with Mermaid diagrams
  - All data fetched via fks_api (no direct DB queries)
  - Real-time updates with WebSocket

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                         FKS Main                            │
│              (Orchestrator & Monitor)                       │
│  - Service Registry                                         │
│  - Health Monitoring                                        │
│  - Centralized Auth                                         │
│  - Celery Beat Scheduler                                    │
└─────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
    ┌─────────┐       ┌──────────┐     ┌──────────┐
    │fks_api  │◄─────►│ fks_app  │◄───►│fks_data  │
    │Gateway  │       │Business  │     │Collector │
    │         │       │Logic     │     │          │
    └─────────┘       └──────────┘     └──────────┘
          │                 │                 │
          │                 ▼                 │
          │           ┌──────────┐            │
          │           │ fks_ai   │            │
          │           │GPU/ML/RAG│            │
          │           │          │            │
          │           └──────────┘            │
          │                 │                 │
          │                 ▼                 │
          │           ┌──────────┐            │
          └──────────►│fks_exec  │◄───────────┘
                      │Rust      │
                      │Engine    │
                      └──────────┘
                            │
                            ▼
                      [Exchanges]
                      Binance, Kraken, etc.

          ┌──────────┐
          │fks_ninja │
          │NT Bridge │◄─── Signals from fks_app
          └──────────┘
                │
                ▼
          [NinjaTrader 8] → [Prop Firms]
```

**Market Data Flow**: `Exchanges → fks_data (collect) → TimescaleDB/Redis → fks_app (query)`  
**Signal Execution**: `fks_app (signal) → fks_execution (order) → Exchange → fks_app (fill)`  
**AI/ML Flow**: `fks_app (request) → fks_ai (GPU inference/RAG) → fks_app (prediction/insight)`  
**External API**: `Client → fks_api (auth) → fks_app (logic) → fks_data (data) → fks_api (response)`  
**NinjaTrader**: `fks_app (signal) → fks_ninja (bridge) → NinjaTrader 8 → Prop Firm`

## 📁 Project Structure (FKS Main Only)

```
fks/  (THIS REPOSITORY - Orchestrator only)
├── manage.py                  # Django CLI
├── docker-compose.yml         # Multi-service orchestration
├── requirements.txt           # Python dependencies
├── Makefile                   # Development commands
├── pytest.ini                 # Test configuration
│
├── docker/
│   ├── Dockerfile            # FKS Main container
│   └── Dockerfile.gpu        # GPU-accelerated image (for RAG)
│
├── repo/                      # Git submodules (microservices)
│   ├── api/                  # fks_api service (FastAPI gateway)
│   ├── app/                  # fks_app service (business logic)
│   ├── ai/                   # fks_ai service (GPU-accelerated ML/RAG)
│   ├── data/                 # fks_data service (data collection)
│   ├── execution/            # fks_execution service (Rust engine)
│   ├── ninja/                # fks_ninja service (NinjaTrader bridge)
│   └── web/                  # fks_web service (Django UI)
│
├── sql/
│   └── init.sql              # TimescaleDB schema + hypertables
│
├── src/                       # FKS Main Django app (orchestrator only)
│   ├── web/
│   │   └── django/           # Django project settings
│   │       ├── settings.py   # Configuration
│   │       ├── urls.py       # URL routing
│   │       ├── wsgi.py       # WSGI application
│   │       └── celery.py     # Celery configuration
│   │
│   ├── monitor/              # ✅ Service registry & health monitoring
│   │   ├── models.py         # Service, HealthCheck models
│   │   ├── services.py       # HealthMonitorService, ServiceRegistry
│   │   ├── tasks.py          # Celery health check tasks
│   │   ├── views.py          # Health dashboard, API endpoints
│   │   └── admin.py          # Django admin
│   │
│   ├── authentication/       # ✅ Centralized auth (delegates to fks_api)
│   │   ├── models.py         # User, APIKey models
│   │   ├── middleware.py     # Auth middleware
│   │   ├── views.py          # Login/logout views
│   │   └── admin.py          # Django admin
│   │
│   ├── framework/            # ⚠️ Shared utilities (evaluate for extraction)
│   │   ├── middleware/       # Circuit breaker, rate limiter, metrics
│   │   ├── exceptions/       # Custom exception hierarchy
│   │   ├── services/         # Service templates & registry
│   │   ├── config/           # Configuration management
│   │   ├── cache/            # Caching abstraction
│   │   └── lifecycle/        # App lifecycle hooks
│   │
│   └── core/                 # ⚠️ Minimal shared models (evaluate for extraction)
│       ├── models/           # Base models (if any)
│       └── utils/            # Helper functions
│
├── archive/                   # ✅ Archived legacy monolith code
│   └── legacy_monolith/
│       ├── README.md         # Documentation of archive
│       ├── app.py            # Old FastAPI monolith entry point
│       ├── engine/           # Old trading engine
│       ├── infrastructure/   # Old infrastructure
│       ├── services/         # Old service layer
│       ├── api/              # Old API routes
│       ├── trading/          # Old trading logic
│       └── data/             # Old data handling
│
├── tests/                     # Test suite (orchestrator tests only)
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
│
├── docs/                      # Documentation
│   ├── SERVICE_CLEANUP_PLAN.md   # 7-phase migration plan
│   ├── ARCHITECTURE.md           # Architecture documentation
│   ├── QUICKSTART.md             # Quick start guide
│   └── ...
│
├── logs/                      # Application logs
├── monitoring/                # Prometheus/Grafana config
│   ├── prometheus/
│   └── grafana/
│
└── scripts/                   # Utility scripts
    ├── setup.sh
    └── ...
```

### Microservice Repositories (Git Submodules)

Each service is a separate Git repository under `repo/`:

- **`repo/api/`** ([github.com/nuniesmith/api](https://github.com/nuniesmith/api)) - Thin API gateway
- **`repo/app/`** ([github.com/nuniesmith/app](https://github.com/nuniesmith/app)) - Business logic service
- **`repo/ai/`** ([github.com/nuniesmith/ai](https://github.com/nuniesmith/ai)) - GPU-accelerated ML/RAG service
- **`repo/data/`** ([github.com/nuniesmith/data](https://github.com/nuniesmith/data)) - Data collection service
- **`repo/execution/`** ([github.com/nuniesmith/execution](https://github.com/nuniesmith/execution)) - Rust execution engine
- **`repo/ninja/`** ([github.com/nuniesmith/ninja](https://github.com/nuniesmith/ninja)) - NinjaTrader C# bridge
- **`repo/web/`** ([github.com/nuniesmith/web](https://github.com/nuniesmith/web)) - Django web UI

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose** (v24+ recommended)
- **Git** (for submodule management)
- **WSL** (for Windows users)

### 1. Clone with Submodules

```bash
# Clone FKS Main with all microservice submodules
git clone --recurse-submodules https://github.com/nuniesmith/fks.git
cd fks

# Or if already cloned, initialize submodules
git submodule update --init --recursive
```

### 2. Security Setup (CRITICAL!)

**🔒 Generate secure passwords before starting:**

```bash
# Run the security setup helper
make security-setup

# This generates strong passwords and creates .env file
# NEVER commit .env to git!
```

This will:

- Generate strong passwords using OpenSSL
- Create/update your `.env` file with secure credentials
- Enable PostgreSQL SSL and Redis authentication
- Verify `.env` is not tracked by git

**⚠️ Never use default passwords in production!**

### 3. Configure Environment

Your `.env` file should have strong passwords (generated by `make security-setup`):

```env
# Generated by security setup
POSTGRES_PASSWORD=<secure-random-password>
REDIS_PASSWORD=<secure-random-password>
DJANGO_SECRET_KEY=<secure-random-key>
PGADMIN_PASSWORD=<secure-random-password>
GRAFANA_PASSWORD=<secure-random-password>

# PostgreSQL SSL enabled by default
POSTGRES_SSL_ENABLED=on
POSTGRES_HOST_AUTH_METHOD=scram-sha-256

# Optional external services
DISCORD_WEBHOOK_URL=  # Optional - Discord notifications
BINANCE_API_KEY=      # Optional - Binance API
BINANCE_API_SECRET=   # Optional - Binance API
OPENAI_API_KEY=       # Optional - RAG system fallback
TAILSCALE_AUTH_KEY=   # Optional - VPN access
```

### 4. Start All Services

```bash
# Start all 8 microservices + infrastructure (standard mode)
make up

# Or with GPU support for fks_ai (Ollama LLM + ML inference)
make gpu-up

# View logs for all services
make logs

# View logs for specific service
docker-compose logs -f fks_api
docker-compose logs -f fks_app
docker-compose logs -f fks_ai  # GPU ML/RAG service
```

**GPU Requirements** (for `make gpu-up`):
- NVIDIA GPU with CUDA 12.2+ support
- nvidia-docker2 runtime installed
- At least 8GB VRAM for LLM models

### 5. Access Services

**FKS Main (Orchestrator)**:

- Health Dashboard: <http://localhost:8000/health/dashboard/>
- Service Registry: <http://localhost:8000/monitor/api/services/>
- Django Admin: <http://localhost:8000/admin>

**Microservices**:

- fks_api (Gateway): <http://localhost:8001/docs> (Swagger UI)
- fks_app (Business Logic): <http://localhost:8002/docs>
- fks_data (Data Collection): <http://localhost:8003/health>
- fks_execution (Rust Engine): <http://localhost:8004/health>
- fks_ninja (NinjaTrader): <http://localhost:8005/health>
- fks_ai (GPU/ML/RAG): <http://localhost:8006/docs>
- fks_web (Web UI): <http://localhost:3001>

**Infrastructure**:

- Grafana (Monitoring): <http://localhost:3000> (admin/admin)
- Prometheus (Metrics): <http://localhost:9090>
- pgAdmin (Database): <http://localhost:5050>
- Flower (Celery): <http://localhost:5555>

### 6. Verify System Health

```bash
# Check all services are healthy
make multi-status

# Or manually check health dashboard
curl http://localhost:8000/health/dashboard/ | jq

# Run orchestrator tests
pytest tests/unit/ -v
```

### 7. Development Workflow

```bash
# Stop all services
make down

# Restart specific service after code changes
docker-compose restart fks_app

# Rebuild service after dependency changes
docker-compose up -d --build fks_app

# Enter service shell
docker-compose exec fks_app bash

# View service logs
docker-compose logs -f fks_app
```

## 🔒 Security Features

### Implemented Security Hardening
- **django-axes**: Login attempt tracking and lockout (5 attempts, 1-hour cooldown)
- **django-ratelimit**: API rate limiting (100/hour anon, 1000/hour authenticated)
- **PostgreSQL SSL**: TLS encryption with scram-sha-256 authentication
- **Redis Authentication**: Password-protected Redis connections
- **Strong Passwords**: All credentials use `openssl rand -base64` generation
- **Security Headers**: HSTS, XSS filter, content-type nosniff, X-Frame-Options
- **Session Security**: HTTP-only, SameSite cookies with Redis-backed sessions

### Security Checklist Before Production
- [ ] Run `make security-setup` to generate strong passwords
- [ ] Verify `.env` is NOT in git: `git log --all -- .env`
- [ ] Change default Grafana password (admin/admin)
- [ ] Set up HTTPS/SSL certificates for nginx
- [ ] Remove exposed ports (5432, 6379) from docker-compose.yml
- [ ] Run `pip-audit -r requirements.txt` for vulnerability scan
- [ ] Enable automated backups
- [ ] Set up monitoring alerts

See [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md) for complete security documentation.

## 📊 Database Schema

### Hypertables (Optimized for Time-Series)

1. **ohlcv_data** - Market data for all symbols/timeframes
   - Partitioned by time
   - Compressed after 7 days
   - Indexes: symbol, timeframe, time

2. **trades** - Complete trade history
   - Partitioned by time
   - Tracks all executions with PnL

3. **balance_history** - Account balance snapshots
   - Partitioned by time
   - Compressed after 30 days
   - Used for equity curves

4. **indicators_cache** - Pre-calculated technical indicators
   - Partitioned by time
   - Improves backtest performance

### Regular Tables

5. **accounts** - Personal and prop firm accounts
6. **positions** - Current open positions
7. **sync_status** - Data synchronization state
8. **strategy_parameters** - Optimized strategy configs

### Continuous Aggregates (Materialized Views)

- **daily_account_performance** - Pre-aggregated daily metrics
  - Win rate, total PnL, average trade, fees
  - Auto-refreshes every hour

## 🔧 Usage

### Data Sync Service

```bash
# Initial full sync (2 years of data)
docker-compose run --rm web python data_sync_service.py init

# Update latest data only
docker-compose run --rm web python data_sync_service.py update

# Run continuous sync (updates every 60 seconds)
docker-compose run --rm web python data_sync_service.py continuous

# Check sync status
docker-compose run --rm web python data_sync_service.py status
```

### Database Management

**Using pgAdmin** (http://localhost:5050):

1. Login with credentials from `.env`
2. Add server:
   - Name: Crypto DB
   - Host: db
   - Port: 5432
   - Username: (from .env)
   - Password: (from .env)

3. Explore tables, run queries, view hypertable stats

**Direct PostgreSQL Access**:

```bash
# Connect to database
docker-compose exec db psql -U fks_user -d fks_db

# View tables
\dt

# Check hypertable info
SELECT * FROM timescaledb_information.hypertables;

# Check compression stats
SELECT * FROM timescaledb_information.compression_settings;

# View recent OHLCV data
SELECT * FROM ohlcv_data 
WHERE symbol = 'BTCUSDT' AND timeframe = '1h' 
ORDER BY time DESC LIMIT 10;
```

### Python API Examples

```python
from db_utils import *
from datetime import datetime, timedelta

# Get OHLCV data as DataFrame
df = get_ohlcv_data('BTCUSDT', '1h', limit=1000)

# Create an account
account = create_account(
    name='My Trading Account',
    account_type='personal',
    initial_balance=10000.0,
    broker='Binance'
)

# Get all accounts
accounts = get_accounts()

# Record a trade
trade = record_trade(
    account_id=1,
    symbol='BTCUSDT',
    trade_type='BUY',
    quantity=0.1,
    price=45000.0,
    fee=4.5,
    order_type='MARKET'
)

# Get account balance history
balance_df = get_balance_history(account_id=1, limit=30)

# Check sync status
status = get_sync_status(symbol='BTCUSDT')
```

## 🛠️ Development

### Add New Symbol

1. Edit `src/config.py`:
```python
MAINS = ['BTCUSDT', 'ETHUSDT']
ALTS = ['SOLUSDT', 'AVAXUSDT', 'SUIUSDT', 'NEWCOINUSDT']
```

2. Add sync status records:
```bash
docker-compose exec db psql -U fks_user -d fks_db -c "
INSERT INTO sync_status (symbol, timeframe, sync_status)
SELECT 'NEWCOINUSDT', tf, 'pending'
FROM unnest(ARRAY['1m','5m','15m','30m','1h','4h','1d','1w','1M']) AS tf
ON CONFLICT DO NOTHING;"
```

3. Sync data:
```bash
docker-compose run --rm web python data_sync_service.py init
```

### Database Migrations

For schema changes, use Alembic:

```bash
# Generate migration
docker-compose run --rm web alembic revision --autogenerate -m "description"

# Apply migration
docker-compose run --rm web alembic upgrade head
```

## 🧪 Testing

### Run Backtest

```bash
# Access the web interface
# Navigate to "Optimization & Backtest" tab
# Pull data, optimize parameters, run backtest
```

### Check Data Quality

```sql
-- Check for gaps in data
SELECT symbol, timeframe, 
       COUNT(*) as candles,
       MIN(time) as oldest,
       MAX(time) as newest,
       MAX(time) - MIN(time) as time_range
FROM ohlcv_data
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;

-- Check for null values
SELECT symbol, timeframe, COUNT(*) 
FROM ohlcv_data 
WHERE close IS NULL OR volume IS NULL
GROUP BY symbol, timeframe;
```

## 📈 Performance Optimization

TimescaleDB automatically optimizes for:
- **Compression**: Data older than 7 days is compressed (20-90% reduction)
- **Chunking**: Data is partitioned in time-based chunks
- **Indexing**: Optimized indexes for time-series queries
- **Continuous Aggregates**: Pre-computed metrics for fast queries

### Query Performance Tips

```sql
-- Use time-based WHERE clauses
SELECT * FROM ohlcv_data
WHERE symbol = 'BTCUSDT' 
  AND timeframe = '1h'
  AND time > NOW() - INTERVAL '30 days';

-- Leverage continuous aggregates
SELECT * FROM daily_account_performance
WHERE account_id = 1 
  AND day > NOW() - INTERVAL '90 days';
```

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check database is running
docker-compose ps

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Data Sync Errors
```bash
# Check sync status
docker-compose run --rm web python data_sync_service.py status

# Re-sync specific symbol
docker-compose run --rm web python -c "
from data_sync_service import DataSyncService
service = DataSyncService()
service.sync_historical_data('BTCUSDT', '1h')
"
```

### Clear All Data and Restart
```bash
# Stop services
docker-compose down

# Remove volumes (WARNING: deletes all data!)
docker volume rm fks_postgres_data fks_redis_data fks_pgadmin_data

# Restart
./setup_database.sh
docker-compose run --rm web python data_sync_service.py init
docker-compose up -d
```

## 📝 Useful Commands

```bash
# View all containers
docker-compose ps

# View logs
docker-compose logs -f [service_name]

# Restart service
docker-compose restart [service_name]

# Stop all services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# Access Python shell with DB access
docker-compose run --rm web python
```

## 🔐 Security Notes

- Never commit `.env` file
- Use strong passwords for database
- Encrypt API keys in production
- Restrict database access in production
- Enable SSL for PostgreSQL in production

## 📚 Next Steps

1. ✅ Database setup complete
2. ✅ Historical data sync ready
3. ⏳ Add WebSocket support for real-time prices
4. ⏳ Implement persistent session state
5. ⏳ Add more trading strategies
6. ⏳ Build portfolio analytics dashboard
7. ⏳ Add automated trading capabilities

## 📖 Resources

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [Binance API Documentation](https://binance-docs.github.io/apidocs/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [TA-Lib Documentation](https://ta-lib.org/)

## 📧 Support

For issues or questions, check the logs and database status first:
```bash
docker-compose logs
docker-compose exec db psql -U fks_user -d fks_db -c "SELECT version();"
```
