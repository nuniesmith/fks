# FKS Platform Architecture

**Version**: 2.0 (Post-Refactor)  
**Date**: October 2025  
**Status**: Django Monolith + Celery

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  Web Browser  │  REST API Clients  │  Discord Bot  │  CLI Tools │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Load Balancer (Optional)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Django Application                        │
│                    (Gunicorn/uWSGI Workers)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Django Apps Layer                      │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  trading_app  │  api_app  │  web_app  │  config_app     │  │
│  │  core  │  data  │  rag  │  forecasting  │  chatbot      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Framework Layer                         │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  Circuit Breaker  │  Rate Limiter  │  Metrics  │  Cache  │  │
│  │  Exceptions  │  Services  │  Config  │  Lifecycle        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   PostgreSQL +   │  │      Redis       │  │  Celery Workers  │
│   TimescaleDB    │  │   (Cache/Broker) │  │  (Async Tasks)   │
│                  │  │                  │  │                  │
│  • Time-series   │  │  • Session store │  │  • 16 tasks      │
│  • Hypertables   │  │  • Task queue    │  │  • Beat scheduler│
│  • pgvector      │  │  • Rate limiting │  │  • Flower UI     │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 📦 Component Architecture

### 1. Web Layer

```
┌─────────────────────────────────────────────────────────────┐
│                      Django Web Layer                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │   web_app/     │  │   api_app/     │  │  admin.py    │ │
│  ├────────────────┤  ├────────────────┤  ├──────────────┤ │
│  │ • Templates    │  │ • REST API     │  │ • Django     │ │
│  │ • Views        │  │ • Serializers  │  │   Admin      │ │
│  │ • Forms        │  │ • Routes       │  │ • Bulk Ops   │ │
│  │ • Static files │  │ • Pagination   │  │ • Filters    │ │
│  └────────────────┘  └────────────────┘  └──────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2. Business Logic Layer

```
┌─────────────────────────────────────────────────────────────┐
│                   Django Apps (Business Logic)               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   trading_app/                        │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  • Trading Models (Trade, Position, Order)           │  │
│  │  • Trading Services (execution, risk, portfolio)     │  │
│  │  • Signal Generation (RSI, MACD, ATR, SMA)          │  │
│  │  • Backtesting Engine (strategy testing)            │  │
│  │  • Optimizer (Optuna parameter optimization)        │  │
│  │  • 16 Celery Tasks (async operations)               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                     core/                             │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  • Base Models (Account, Balance)                    │  │
│  │  • Core Utils (validation, formatting)               │  │
│  │  • Metrics (Prometheus integration)                  │  │
│  │  • Patterns (design patterns)                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   data/      │  │   rag/       │  │ forecasting/ │     │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤     │
│  │ • Providers  │  │ • Embeddings │  │ • ML Models  │     │
│  │ • Adapters   │  │ • Retrieval  │  │ • Predictions│     │
│  │ • CCXT       │  │ • Ingestion  │  │ • Analysis   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3. Framework Layer

```
┌─────────────────────────────────────────────────────────────┐
│                 framework/ (64 files, 928K)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │               Middleware Components                   │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  ┌────────────────┐  ┌────────────────┐            │  │
│  │  │ Circuit Breaker│  │  Rate Limiter  │            │  │
│  │  ├────────────────┤  ├────────────────┤            │  │
│  │  │ • State mgmt   │  │ • Token bucket │            │  │
│  │  │ • Fallbacks    │  │ • Sliding win  │            │  │
│  │  │ • Recovery     │  │ • Redis backed │            │  │
│  │  └────────────────┘  └────────────────┘            │  │
│  │                                                      │  │
│  │  ┌────────────────┐  ┌────────────────┐            │  │
│  │  │    Metrics     │  │  Exceptions    │            │  │
│  │  ├────────────────┤  ├────────────────┤            │  │
│  │  │ • Prometheus   │  │ • Hierarchy    │            │  │
│  │  │ • Counters     │  │ • Validation   │            │  │
│  │  │ • Histograms   │  │ • Service errs │            │  │
│  │  └────────────────┘  └────────────────┘            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │               Core Abstractions                       │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  Services  │  Config  │  Cache  │  Lifecycle         │  │
│  │  • Registry│  • Mgmt  │  • Abstraction │  • Hooks   │  │
│  │  • Templates│ • Validation│ • Backends│  • Startup  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4. Data Layer

```
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL + TimescaleDB                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Hypertables (Time-Series):                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │  ohlcv_data    │  │    trades      │  │balance_history││
│  ├────────────────┤  ├────────────────┤  ├──────────────┤ │
│  │ • Partitioned  │  │ • Compressed   │  │ • Aggregated │ │
│  │ • Compressed   │  │ • Indexed      │  │ • Retention  │ │
│  │ • Fast queries │  │ • PnL tracking │  │ • Analytics  │ │
│  └────────────────┘  └────────────────┘  └──────────────┘ │
│                                                              │
│  Regular Tables:                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │   accounts     │  │   positions    │  │   signals    │ │
│  │   strategies   │  │   orders       │  │   configs    │ │
│  └────────────────┘  └────────────────┘  └──────────────┘ │
│                                                              │
│  pgvector Extension (RAG):                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  embeddings  │  documents  │  semantic_search       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5. Async Task Layer

```
┌─────────────────────────────────────────────────────────────┐
│                     Celery Task Queue                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              trading_app.tasks (16 tasks)            │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │                                                       │  │
│  │  Trading Operations:                                 │  │
│  │  • execute_trade           • update_market_data      │  │
│  │  • generate_signals        • run_backtest            │  │
│  │  • optimize_strategy       • sync_exchange_balances  │  │
│  │  • update_position_status                            │  │
│  │                                                       │  │
│  │  Analytics:                                          │  │
│  │  • calculate_portfolio_metrics                       │  │
│  │  • calculate_risk_metrics                            │  │
│  │  • generate_daily_report                             │  │
│  │                                                       │  │
│  │  Maintenance:                                        │  │
│  │  • cleanup_old_data        • archive_old_logs        │  │
│  │  • refresh_cache           • health_check            │  │
│  │                                                       │  │
│  │  Integrations:                                       │  │
│  │  • send_discord_notification                         │  │
│  │  • process_webhook                                   │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │ Celery Worker  │  │  Celery Beat   │  │   Flower     │ │
│  ├────────────────┤  ├────────────────┤  ├──────────────┤ │
│  │ • Task exec    │  │ • Scheduler    │  │ • Monitoring │ │
│  │ • Concurrency  │  │ • Cron jobs    │  │ • Web UI     │ │
│  │ • Retries      │  │ • Intervals    │  │ • Metrics    │ │
│  └────────────────┘  └────────────────┘  └──────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request Flow Diagrams

### Web Request Flow

```
┌──────────┐
│  Client  │
└────┬─────┘
     │
     │ HTTP Request
     ▼
┌─────────────────────────────────────┐
│         Django Middleware           │
├─────────────────────────────────────┤
│  1. Rate Limiter (API protection)   │
│  2. Circuit Breaker (fault tolerance)│
│  3. Authentication (JWT/Session)    │
│  4. CSRF Protection                 │
│  5. CORS Headers                    │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│          URL Router                 │
│  • /api/v1/...  → api_app           │
│  • /admin/...   → Django admin      │
│  • /...         → web_app           │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│            View Layer               │
│  • Request validation               │
│  • Permission checks                │
│  • Service layer calls              │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│         Service Layer               │
│  • Business logic                   │
│  • Database operations              │
│  • Cache operations                 │
│  • Task queue dispatch              │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│      Response Generation            │
│  • JSON (API)                       │
│  • HTML (Web)                       │
│  • Error handling                   │
└────────────┬────────────────────────┘
             │
             ▼
┌──────────┐
│  Client  │
└──────────┘
```

### Async Task Flow

```
┌─────────────────┐
│  Django View    │
└────────┬────────┘
         │
         │ Task dispatch
         ▼
┌─────────────────────────────────────┐
│         Redis (Broker)              │
│  • Task serialization               │
│  • Queue management                 │
└────────────┬────────────────────────┘
             │
             │ Task pickup
             ▼
┌─────────────────────────────────────┐
│        Celery Worker                │
│  1. Task deserialization            │
│  2. Retry logic                     │
│  3. Error handling                  │
│  4. Task execution:                 │
│     • trading_app.tasks.*           │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│      Business Operations            │
│  • Database updates                 │
│  • External API calls               │
│  • File operations                  │
│  • Notifications                    │
└────────────┬────────────────────────┘
             │
             │ Result storage
             ▼
┌─────────────────────────────────────┐
│      Redis (Result Backend)         │
│  • Task result                      │
│  • Task state                       │
│  • Metadata                         │
└─────────────────────────────────────┘
```

### Data Ingestion Flow (RAG)

```
┌─────────────────┐
│  Trading Event  │
│  • New signal   │
│  • Backtest run │
│  • Trade exec   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│     RAG Ingestion Pipeline          │
│  1. Event capture                   │
│  2. Document creation               │
│  3. Chunking                        │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│      Embeddings Service             │
│  • Local: sentence-transformers     │
│  • Fallback: OpenAI                 │
│  • CUDA acceleration (if available) │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│    PostgreSQL (pgvector)            │
│  • Store embeddings                 │
│  • Index for similarity search      │
│  • Metadata storage                 │
└────────────┬────────────────────────┘
             │
             │ Query
             ▼
┌─────────────────────────────────────┐
│      Retrieval Service              │
│  • Semantic search                  │
│  • Context ranking                  │
│  • Result aggregation               │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────┐
│   LLM Service   │
│  • Local models │
│  • Ollama/llama │
│  • Trading AI   │
└─────────────────┘
```

---

## 🔌 Integration Points

### External Services

```
┌─────────────────────────────────────┐
│         FKS Platform                │
└────────────┬────────────────────────┘
             │
             ├─────────────────────────┐
             │                         │
             ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐
│  Binance API (CCXT) │   │   Discord Webhooks  │
├─────────────────────┤   ├─────────────────────┤
│ • Market data       │   │ • Trade alerts      │
│ • Order execution   │   │ • System status     │
│ • Balance queries   │   │ • Error notifs      │
└─────────────────────┘   └─────────────────────┘
             │                         │
             ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐
│    Ollama/LLaMA     │   │   Prometheus        │
├─────────────────────┤   ├─────────────────────┤
│ • Local LLM         │   │ • Metrics export    │
│ • CUDA acceleration │   │ • Time-series data  │
│ • Trading insights  │   │ • Alerting          │
└─────────────────────┘   └─────────────────────┘
```

---

## 📊 Deployment Architecture

### Docker Compose Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network: fks-network              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │    web     │  │ celery_    │  │ celery_    │           │
│  │  (Django)  │  │  worker    │  │   beat     │           │
│  │  Port:8000 │  │            │  │            │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │     db     │  │   redis    │  │   flower   │           │
│  │ (TimescaleDB)│ │  (Cache)  │  │  Port:5555 │           │
│  │  Port:5432 │  │  Port:6379 │  │            │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│                                                              │
│  ┌────────────┐                                             │
│  │  pgadmin   │                                             │
│  │ Port:5050  │                                             │
│  └────────────┘                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Service Dependencies

```
web
├── depends_on: db, redis
├── volumes: ./src, ./logs
└── environment: DATABASE_URL, REDIS_URL, CELERY_BROKER_URL

celery_worker
├── depends_on: web, redis, db
├── command: celery -A fks_project worker
└── concurrency: 4

celery_beat
├── depends_on: web, redis, db
├── command: celery -A fks_project beat
└── schedule: Django database scheduler

flower
├── depends_on: celery_worker, redis
├── port: 5555
└── authentication: basic auth

db (TimescaleDB)
├── image: timescale/timescaledb:latest-pg16
├── volumes: postgres_data
└── extensions: timescaledb, pgvector

redis
├── image: redis:7-alpine
├── volumes: redis_data
└── persistence: AOF enabled

pgadmin
├── depends_on: db
├── port: 5050
└── volumes: pgadmin_data
```

---

## 🔐 Security Architecture

### Authentication & Authorization

```
┌────────────────────────────────────────────┐
│           Django Security Layer            │
├────────────────────────────────────────────┤
│                                            │
│  Authentication:                           │
│  • Session-based (web)                     │
│  • JWT tokens (API)                        │
│  • Django admin authentication             │
│                                            │
│  Authorization:                            │
│  • Permission system                       │
│  • Group-based access                      │
│  • Object-level permissions                │
│                                            │
│  Security Features:                        │
│  • CSRF protection                         │
│  • XSS prevention                          │
│  • SQL injection protection (ORM)          │
│  • Rate limiting (API)                     │
│  • Circuit breaker (fault tolerance)       │
│                                            │
└────────────────────────────────────────────┘
```

---

## 📈 Monitoring & Observability

### Metrics Collection

```
┌─────────────────────────────────────────────────────────────┐
│                     Monitoring Stack                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Application Metrics (framework/middleware/metrics/):       │
│  • Request count/duration                                   │
│  • Error rates                                              │
│  • Cache hit/miss                                           │
│  • Database query time                                      │
│  • Celery task metrics                                      │
│                                                              │
│  Business Metrics:                                          │
│  • Active trades                                            │
│  • Portfolio value                                          │
│  • Signal generation rate                                   │
│  • Backtest performance                                     │
│                                                              │
│  Infrastructure Metrics:                                    │
│  • CPU/Memory usage                                         │
│  • Database connections                                     │
│  • Redis memory                                             │
│  • Celery queue length                                      │
│                                                              │
│  Export Format: Prometheus                                  │
│  Visualization: Grafana (optional)                          │
│  Alerting: Prometheus Alertmanager (optional)               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Logging

```
Application Logs → ./logs/ directory
├── django.log         (Django application logs)
├── celery.log         (Celery worker logs)
├── trading.log        (Trading operations)
├── rag.log            (RAG system logs)
└── error.log          (Error aggregation)

Log Rotation: Automatic (time/size based)
Log Level: INFO (production), DEBUG (development)
Format: JSON structured logs
```

---

## 🚀 Scaling Strategies

### Horizontal Scaling

```
┌─────────────────────────────────────────────────────────────┐
│                     Load Balancer (nginx)                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Django Web  │ │  Django Web  │ │  Django Web  │
│  Instance 1  │ │  Instance 2  │ │  Instance N  │
└──────────────┘ └──────────────┘ └──────────────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│    PostgreSQL    │          │   Redis Cluster  │
│  (Read Replicas) │          │  (Sentinel/Cluster)│
└──────────────────┘          └──────────────────┘
```

### Celery Scaling

```
Task Queues (Redis):
├── high_priority    (trading operations)
├── default          (general tasks)
└── low_priority     (maintenance, reports)

Worker Scaling:
├── trading_worker    (4 instances, high priority queue)
├── general_worker    (2 instances, default queue)
└── maintenance_worker (1 instance, low priority queue)

Task Routing:
• execute_trade → high_priority
• generate_signals → default
• cleanup_old_data → low_priority
```

---

## 📚 Technology Stack Summary

| Layer | Technologies |
|-------|-------------|
| **Web Framework** | Django 5.2.7, Django REST Framework |
| **Task Queue** | Celery 5.5.3, Redis (broker) |
| **Database** | PostgreSQL 16, TimescaleDB, pgvector |
| **Cache** | Redis 7 |
| **Web Server** | Gunicorn/uWSGI, Nginx (optional) |
| **AI/ML** | Ollama, llama.cpp, sentence-transformers |
| **Monitoring** | Prometheus, Flower (Celery UI) |
| **Container** | Docker, Docker Compose |
| **Exchange API** | CCXT (Binance) |
| **Testing** | pytest, Django test framework |

---

## 🔄 Migration Summary

### Before (Microservices)
- React frontend + 3 microservices
- Complex inter-service communication
- 214 files, ~707K to be removed
- Difficult to deploy and maintain

### After (Django Monolith)
- Single Django application
- Celery for async operations
- 10 modular Django apps
- Simplified deployment
- Framework layer for abstractions

### Benefits
- ✅ Reduced complexity
- ✅ Easier deployment
- ✅ Better testability
- ✅ Improved performance
- ✅ Simplified debugging
- ✅ Lower maintenance overhead

---

**Last Updated**: October 2025  
**Version**: 2.0 (Post-Refactor)  
**Status**: Production Ready (pending deployment testing)
