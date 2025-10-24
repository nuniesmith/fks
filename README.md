# Advanced FKS Trading Platform

[![Tests](https://github.com/nuniesmith/fks/actions/workflows/tests.yml/badge.svg)](https://github.com/nuniesmith/fks/actions/workflows/tests.yml)

A sophisticated **Django 5.2.7 monolith** trading application with PostgreSQL + TimescaleDB, Redis caching, Celery 5.5.3 async tasks, comprehensive backtesting, and **AI-powered RAG system with local LLM support**.

> **Architecture**: Migrated from microservices to Django monolith (October 2025)  
> **Status**: Phase 9 Complete ✅ | Overall 90% Complete (9/10 phases)  
> **See**: [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md) for breaking changes

## 🎯 Features

### ✅ Core Trading Platform
- **Data Management** - Binance API integration with CCXT
- **Signal Generation** - Technical indicators (RSI, MACD, ATR, SMA, Bollinger Bands)
- **Backtesting Engine** - Strategy performance testing with comprehensive metrics
- **Strategy Optimizer** - Optuna-based parameter optimization
- **Portfolio Analytics** - Real-time P&L tracking and risk metrics
- **16 Celery Tasks** - Async background processing (`trading_app.tasks.*`)
- **REST API** - Full API with circuit breaker and rate limiting
- **Web Interface** - Django templates with Bootstrap 5
- **Admin Panels** - Advanced filtering, bulk actions, data export
- **Discord Integration** - Automated trade notifications and alerts

### ✅ RAG System (AI-Powered Intelligence)
- **Local LLM Support** - CUDA-accelerated inference with Ollama/llama.cpp
- **pgvector Integration** - Semantic search with vector similarity
- **Document Processing** - Automated chunking for trading data
- **Embeddings Service** - Local (sentence-transformers) + OpenAI fallback
- **Retrieval Service** - Context-aware semantic search
- **Intelligence Orchestrator** - RAG system for trading insights
- **Auto-Ingestion Pipeline** - Real-time data ingestion from signals/backtests/trades
- **Zero-Cost Inference** - No API fees with local models

### ✅ Architecture & Infrastructure
- **Django 5.2.7** - Monolith architecture with modular apps
- **Celery 5.5.3** - Distributed task queue with Redis broker
- **PostgreSQL + TimescaleDB** - High-performance time-series database
- **Redis** - Caching and session management
- **Docker + Compose** - Containerized deployment
- **Framework Layer** - Circuit breaker, rate limiter, metrics, caching (64 files, 928K)
- **69+ Test Cases** - Unit, integration, and performance tests
- **CI/CD Pipeline** - GitHub Actions automation
- **GPU Support** - CUDA acceleration for ML models

## 📁 Project Structure

```
fks/
├── manage.py                  # Django CLI
├── docker-compose.yml         # Service orchestration
├── requirements.txt           # Python dependencies
├── Makefile                   # Development commands
├── start.sh                   # Startup script
├── pytest.ini                 # Test configuration
│
├── docker/
│   ├── Dockerfile            # Main container image
│   └── Dockerfile.gpu        # GPU-accelerated image
│
├── sql/
│   └── init.sql              # TimescaleDB schema + hypertables
│
├── src/                       # Django monolith
│   ├── fks_project/          # Django project settings
│   │   ├── settings.py       # Configuration
│   │   ├── urls.py           # URL routing
│   │   ├── wsgi.py           # WSGI application
│   │   └── celery.py         # Celery configuration
│   │
│   ├── core/                 # Core models and utilities
│   │   ├── models/           # Base models (Account, Trade, Position)
│   │   ├── utils/            # Helper functions
│   │   ├── cache/            # Caching utilities
│   │   ├── metrics/          # Prometheus metrics
│   │   └── patterns/         # Design patterns
│   │
│   ├── config_app/           # Configuration management
│   │   ├── models.py         # Config models
│   │   ├── views.py          # Config views
│   │   └── admin.py          # Admin interface
│   │
│   ├── trading_app/          # Trading logic (NEW - Phase 9C)
│   │   ├── models/           # Trading models
│   │   ├── services/         # Business logic
│   │   ├── tasks.py          # 16 Celery tasks
│   │   ├── views/            # Trading views
│   │   ├── signals.py        # Signal generation
│   │   ├── backtest.py       # Backtesting engine
│   │   └── optimizer.py      # Strategy optimization
│   │
│   ├── api_app/              # REST API
│   │   ├── routes/           # API endpoints
│   │   ├── serializers/      # DRF serializers
│   │   ├── middleware/       # API middleware
│   │   │   ├── circuit_breaker/  # Fault tolerance
│   │   │   └── rate_limiter/     # Rate limiting
│   │   └── views.py          # API views
│   │
│   ├── web_app/              # Web interface
│   │   ├── views/            # Web views
│   │   ├── templates/        # Django templates
│   │   ├── static/           # CSS, JS, images
│   │   └── forms.py          # Form definitions
│   │
│   ├── framework/            # Core abstractions (Phase 9D - kept as-is)
│   │   ├── middleware/       # Framework middleware
│   │   │   ├── circuit_breaker/  # Circuit breaker pattern
│   │   │   ├── rate_limiter/     # Rate limiting
│   │   │   └── metrics/          # Prometheus metrics
│   │   ├── exceptions/       # Custom exception hierarchy
│   │   ├── services/         # Service templates & registry
│   │   ├── config/           # Configuration management
│   │   ├── cache/            # Caching abstraction
│   │   └── lifecycle/        # App lifecycle hooks
│   │
│   ├── data/                 # Data management
│   │   ├── providers/        # Data provider adapters
│   │   ├── adapters/         # Exchange adapters
│   │   └── models/           # Data models
│   │
│   ├── rag/                  # RAG system
│   │   ├── services/         # RAG services
│   │   ├── embeddings/       # Embedding generation
│   │   ├── retrieval/        # Document retrieval
│   │   └── ingestion/        # Data ingestion pipeline
│   │
│   ├── forecasting/          # Forecasting models
│   │   ├── models/           # ML models
│   │   └── services/         # Forecasting services
│   │
│   ├── chatbot/              # Chatbot interface
│   │   ├── handlers/         # Message handlers
│   │   └── integrations/     # Discord, Telegram, etc.
│   │
│   ├── engine/               # Core trading engine
│   │   ├── execution/        # Trade execution
│   │   └── risk/             # Risk management
│   │
│   └── infrastructure/       # Infrastructure services
│       ├── database/         # DB connections
│       ├── cache/            # Redis client
│       └── external/         # External API clients
│
├── tests/                     # Test suite (69+ tests)
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── performance/          # Performance tests
│
├── docs/                      # Documentation
│   ├── MIGRATION_GUIDE.md    # Migration instructions (NEW)
│   ├── PHASE9_FINAL_SUMMARY.md
│   ├── PHASE9D_FRAMEWORK_ANALYSIS.md
│   ├── QUICKSTART.md
│   ├── RAG_SETUP_GUIDE.md
│   └── ...
│
├── logs/                      # Application logs
├── ml_models/                 # ML model artifacts
└── scripts/                   # Utility scripts
    ├── setup.sh
    ├── deploy-fks.sh
    └── ...
```

### Key Directories

- **`src/trading_app/`** - Main trading functionality (migrated from `src/trading/`)
  - Contains 16 Celery tasks for async operations
  - All tasks use `trading_app.tasks.*` naming convention
  
- **`src/framework/`** - Core abstractions (64 files, 928K)
  - Kept as-is per Phase 9D analysis
  - Provides circuit breaker, rate limiter, exceptions, services, config, caching, lifecycle, metrics
  - 26 external imports across codebase

- **`src/api_app/`** - REST API with middleware
  - Circuit breaker for fault tolerance
  - Rate limiter for API protection
  
- **`src/rag/`** - AI-powered intelligence
  - Local LLM support with CUDA acceleration
  - pgvector for semantic search
  - Automated document ingestion

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- WSL (for Windows users)

### 1. Security Setup (IMPORTANT!)

**🔒 Generate secure passwords before starting:**

```bash
# Run the security setup helper
make security-setup

# Or manually:
bash scripts/setup-security.sh
```

This will:
- Generate strong passwords using OpenSSL
- Create/update your `.env` file with secure credentials
- Enable PostgreSQL SSL and Redis authentication
- Verify `.env` is not tracked by git

**⚠️ Never use default passwords in production!**

### 2. Initial Setup

```bash
# Clone the repository (if not already done)
cd /path/to/fks

# Run security setup (creates .env with secure passwords)
make security-setup

# Or manually copy and edit
cp .env.example .env
nano .env  # Update all passwords marked with CHANGE_ME
```

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
DISCORD_WEBHOOK_URL=  # Optional
BINANCE_API_KEY=      # Optional
OPENAI_API_KEY=       # Optional
```

### 4. Start Services

```bash
chmod +x setup_database.sh

# Start all services (standard)
make up

# Or with GPU support for RAG/LLM
make gpu-up

# View logs
make logs
```

Access the application:
- **Web App**: http://localhost:8000
- **Health Dashboard**: http://localhost:8000/health/dashboard/
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **pgAdmin**: http://localhost:5050
- **Flower (Celery)**: http://localhost:5555
- **Database**: localhost:5432

### 5. Verify Security

```bash
# Check security configuration
make security-check

# Run security tests
pytest tests/unit/test_security.py -v
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
