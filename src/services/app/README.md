# FKS App - Business Logic Service

**Port**: 8002  
**Framework**: Python 3.13 + FastAPI  
**Role**: Core trading intelligence - strategies, signals, backtesting, portfolio optimization

## Overview

FKS App is the **business logic hub** of the FKS Trading Platform. It contains ALL trading intelligence:
- Strategy development and execution
- Technical indicator signals (RSI, MACD, Bollinger Bands)
- Backtesting engine with comprehensive metrics
- Portfolio optimization using Optuna
- Integration with fks_ai for ML predictions and RAG insights

**Data Flow**:
```
Market Data: fks_data → fks_app (query)
AI/ML: fks_app → fks_ai (request) → fks_app (prediction)
Execution: fks_app (signal) → fks_execution (order)
External API: fks_api → fks_app (business logic) → fks_api
```

## Architecture Principles

### What FKS App DOES:
✅ Generate trading signals based on technical indicators  
✅ Run backtests on historical data  
✅ Optimize portfolio parameters with Optuna  
✅ Query fks_data for market data (NEVER queries exchanges directly)  
✅ Request ML predictions from fks_ai  
✅ Send execution signals to fks_execution  
✅ Apply risk management and position sizing  

### What FKS App DOES NOT DO:
❌ NO direct exchange communication (use fks_execution)  
❌ NO data collection (use fks_data service)  
❌ NO GPU-intensive ML training (use fks_ai service)  
❌ NO order execution (use fks_execution service)  
❌ NO user authentication (handled by fks_main → fks_api)  

## Tech Stack

- **Language**: Python 3.13
- **Framework**: FastAPI + uvicorn
- **Trading**: TA-Lib, pandas, numpy
- **Optimization**: Optuna
- **Backtesting**: backtrader, custom engine
- **Database Client**: SQLAlchemy (queries fks_main's TimescaleDB)
- **Cache**: Redis client
- **Task Queue**: Celery worker (consumes tasks from fks_main)

## API Endpoints

### Signals
- `GET /signals/latest/{symbol}` - Get latest signal for symbol
- `POST /signals/generate` - Generate signal for symbol with strategy
- `GET /signals/history` - Historical signals with filters

### Strategies
- `GET /strategies` - List all strategies
- `GET /strategies/{strategy_id}` - Get strategy details
- `POST /strategies` - Create new strategy
- `PUT /strategies/{strategy_id}` - Update strategy
- `DELETE /strategies/{strategy_id}` - Delete strategy

### Backtesting
- `POST /backtest/run` - Run backtest with parameters
- `GET /backtest/{backtest_id}` - Get backtest results
- `GET /backtest/history` - List backtests with filters

### Portfolio
- `GET /portfolio/optimize` - Optimize portfolio allocation
- `GET /portfolio/analysis` - Get portfolio analytics
- `POST /portfolio/rebalance` - Calculate rebalancing trades

### Health
- `GET /health` - Service health check
- `GET /metrics` - Prometheus metrics

## Directory Structure

```
repo/app/
├── src/
│   ├── main.py              # FastAPI application
│   ├── strategies/          # Strategy implementations
│   │   ├── base.py         # Base strategy class
│   │   ├── rsi.py          # RSI strategy
│   │   ├── macd.py         # MACD strategy
│   │   └── bollinger.py    # Bollinger Bands strategy
│   ├── signals/             # Signal generation
│   │   ├── generator.py    # Signal generator
│   │   └── indicators.py   # Technical indicators
│   ├── backtest/            # Backtesting engine
│   │   ├── engine.py       # Backtest executor
│   │   └── metrics.py      # Performance metrics
│   ├── portfolio/           # Portfolio optimization
│   │   ├── optimizer.py    # Optuna optimizer
│   │   └── analytics.py    # Portfolio analytics
│   ├── integrations/        # Service integrations
│   │   ├── data_client.py  # fks_data HTTP client
│   │   └── ai_client.py    # fks_ai HTTP client
│   └── tasks/               # Celery tasks
│       ├── signals.py      # Signal generation tasks
│       └── backtest.py     # Backtest tasks
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── Dockerfile              # Container definition
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Development Setup

### Prerequisites
- Python 3.13
- Docker + Docker Compose
- Access to fks_data service (port 8003)
- Access to fks_ai service (port 8006)
- Redis (for Celery)
- PostgreSQL (for signal storage)

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/unit/ -v
pytest tests/integration/ -v

# Run locally (dev mode)
uvicorn src.main:app --reload --port 8002

# Run in Docker
docker-compose up fks_app
```

### Environment Variables

```bash
# Service configuration
FKS_APP_PORT=8002
FKS_APP_HOST=0.0.0.0

# Database (TimescaleDB via fks_main)
DATABASE_URL=postgresql://fks_user:password@db:5432/trading_db

# Redis (Celery)
REDIS_URL=redis://redis:6379/0

# Service dependencies
FKS_DATA_URL=http://fks_data:8003
FKS_AI_URL=http://fks_ai:8006
FKS_EXECUTION_URL=http://fks_execution:8004

# Feature flags
ENABLE_AI_PREDICTIONS=true
ENABLE_PORTFOLIO_OPTIMIZATION=true

# Logging
LOG_LEVEL=INFO
```

## Integration with Other Services

### fks_data (Port 8003)
- Query market data: `GET /data/ohlcv/{symbol}`
- Query fundamentals: `GET /data/fundamentals/{symbol}`
- Query features: `GET /data/features/{symbol}`

### fks_ai (Port 8006)
- Regime detection: `GET /ai/regime?symbol={symbol}`
- Strategy generation: `POST /ai/generate-strategy`
- Predictions: `POST /ai/predict`

### fks_execution (Port 8004)
- Submit order: `POST /orders`
- Check order status: `GET /orders/{order_id}`
- Get positions: `GET /positions`

### fks_main (Port 8000)
- Celery tasks consumed from fks_main's Beat scheduler
- Stores signals/backtests in fks_main's TimescaleDB

## Testing

```bash
# Unit tests (no external dependencies)
pytest tests/unit/ -v

# Integration tests (requires services running)
docker-compose up -d db redis fks_data fks_ai
pytest tests/integration/ -v

# Coverage
pytest tests/ --cov=src --cov-report=html

# Lint
ruff check src/
mypy src/
```

## Deployment

### Docker Build
```bash
docker build -t fks_app:latest .
```

### Health Checks
- **Endpoint**: `GET /health`
- **Expected**: `{"status": "healthy", "service": "fks_app"}`
- **Dependencies**: fks_data, Redis, PostgreSQL

## Performance Considerations

- **Caching**: Redis caches for frequent queries (signals, strategies)
- **Async**: FastAPI async endpoints for I/O-bound operations
- **Batch Processing**: Celery tasks for long-running backtests
- **Database**: Connection pooling with SQLAlchemy
- **Rate Limiting**: Respect fks_data rate limits

## Common Issues

**Signal generation slow**:
- Check fks_data service latency
- Verify Redis cache is enabled
- Use batch endpoints for multiple symbols

**Backtest failures**:
- Ensure sufficient historical data in fks_data
- Check memory limits for large datasets
- Use Celery tasks for long backtests (>1 hour)

**Portfolio optimization timeout**:
- Reduce Optuna trials for faster results
- Use fks_ai for regime-aware optimization
- Cache previous optimization results

## Contributing

1. Write tests for new strategies
2. Follow TA-Lib conventions for indicators
3. Document strategy parameters and expected returns
4. Use Optuna for parameter optimization
5. Ensure no direct exchange communication

## License

MIT License - See LICENSE file for details

---

**Status**: Active Development  
**Maintainer**: FKS Trading Platform Team  
**Last Updated**: October 2025
