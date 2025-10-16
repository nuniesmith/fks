# Advanced FKS Trading Platform

A sophisticated **Django-based** fks trading application with PostgreSQL + TimescaleDB, Redis caching, Celery async tasks, real-time updates, and comprehensive backtesting capabilities.

## 🎯 Features

### ✅ Phase 1: Utility Modules (Complete)
- **Data Fetcher** - Binance API integration with CCXT
- **Signal Generator** - Technical indicators (RSI, MACD, ATR, SMA)
- **Backtest Engine** - Strategy performance testing
- **Optimizer** - Optuna-based parameter optimization
- **Helper Utilities** - Validation and data processing

### ✅ Phase 2: Views & URL Routing (Complete)
- **15 Django Views** - Dashboard, data pull, optimization, signals, trades, positions, notifications
- **RESTful API Endpoints** - AJAX data endpoints for live updates
- **Professional Architecture** - MVC pattern with Django ORM

### ✅ Phase 3: Templates (Complete)
- **9 Responsive Templates** - Bootstrap 5.3.0 design
- **Interactive Charts** - Chart.js visualizations (equity curves, position distribution)
- **Real-Time Updates** - AJAX live price and position updates
- **DataTables** - Advanced filtering and sorting

### ✅ Phase 4: Forms (Complete)
- **7 Comprehensive Forms** - Field validation, cross-field validation, warning system
- **Auto-Rounding** - Clean user inputs for better UX
- **CSRF Protection** - Security built-in
- **Custom Validators** - Discord webhook, risk warnings

### ✅ Phase 5: Admin Interface (Complete)
- **7 Custom ModelAdmin Classes** - Account, Position, Trade, Balance, Strategy, Signal, Backtest
- **Colored Badges** - Visual status indicators
- **Calculated Fields** - P&L %, trade duration, risk amounts
- **Bulk Actions** - Activate/deactivate, close positions/trades
- **Advanced Filtering** - Multi-dimensional data exploration

### ✅ Phase 6: Celery Async Tasks (Complete)
- **11 Background Tasks** - Price fetching, signal generation, position updates, optimization
- **8 Scheduled Jobs** - Automatic execution (every 5 min, hourly, daily)
- **Discord Notifications** - Automated alerts and performance reports
- **Flower Monitoring** - Real-time task monitoring UI
- **Docker Orchestration** - Easy deployment with docker-compose

## 📁 Project Structure

```
fks/
├── docker/
│   └── Dockerfile
├── sql/
│   └── init.sql              # TimescaleDB schema and hypertables
├── src/
│   ├── __init__.py
│   ├── app.py                # Streamlit web interface
│   ├── backtest.py           # Backtesting engine
│   ├── cache.py              # Redis caching
│   ├── config.py             # Configuration
│   ├── data.py               # Binance API client
│   ├── database.py           # SQLAlchemy models
│   ├── db_utils.py           # Database helper functions
│   ├── data_sync_service.py  # Background data sync service
│   ├── optimizer.py          # Strategy optimizer
│   ├── signals.py            # Trading signals
│   └── utils.py              # Utilities
├── docker-compose.yml
├── requirements.txt
├── setup_database.sh         # Database setup script
├── .env.example
└── README.md
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- WSL (for Windows users)

### Option 1: Full Setup (Phase 1 + Phase 2)

```bash
# Clone/navigate to the repository
cd /path/to/fks

# Create environment file
cp .env.example .env
nano .env  # Edit with your credentials

# Run Phase 2 setup (includes Phase 1)
chmod +x start_phase2.sh
./start_phase2.sh
```

This will:
- Start TimescaleDB, Redis, pgAdmin
- Initialize database schema
- Start WebSocket service for live prices
- Launch enhanced Streamlit app
- Enable real-time features

### Option 2: Phase 1 Only (No WebSocket)

```bash
chmod +x quick_start.sh
./quick_start.sh
```

### 1. Initial Setup

```bash
# Clone the repository (if not already done)
cd /path/to/fks

# Create environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 2. Configure Environment

Edit `.env` file with your settings:

```env
DB_USER=fks_user
DB_PASSWORD=your_secure_password
DB_NAME=fks_db

PGADMIN_EMAIL=admin@fks.local
PGADMIN_PASSWORD=admin123

DISCORD_WEBHOOK_URL=  # Optional
```

### 3. Start Database Services

```bash
# Make setup script executable
chmod +x setup_database.sh

# Run database setup
./setup_database.sh
```

This will:
- Start PostgreSQL (TimescaleDB) and Redis
- Initialize database schema with hypertables
- Start pgAdmin for database management

### 4. Sync Historical Data

```bash
# Initial sync (fetches 2 years of data for all symbols/timeframes)
# This may take 15-30 minutes depending on your connection
docker-compose run --rm web python data_sync_service.py init

# Check sync status
docker-compose run --rm web python data_sync_service.py status
```

### 5. Start the Application

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f web
```

Access the application:
- **Web App**: http://localhost:8501
- **pgAdmin**: http://localhost:5050
- **Database**: localhost:5432

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
