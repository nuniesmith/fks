# FKS Trading System - Complete Architecture Documentation

**Version:** 1.0  
**Last Updated:** 2025-01-20  
**Author:** FKS Development Team

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Services](#core-services)
4. [Signal Flow Architecture](#signal-flow-architecture)
5. [Data Flow Pipeline](#data-flow-pipeline)
6. [Execution & Notification Flow](#execution--notification-flow)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [Service Details](#service-details)
9. [Environment Configuration](#environment-configuration)
10. [Port Reference](#port-reference)
11. [Key Clarifications](#key-clarifications)

---

## System Overview

The FKS Trading System is a high-performance, microservices-based algorithmic trading platform built with Rust and Python. The system handles:

- **Real-time market data ingestion** from multiple cryptocurrency exchanges
- **Technical indicator calculation** (EMA, RSI, MACD, ATR)
- **Trading signal generation** with multiple detection strategies
- **Order execution** with simulated, paper, and live trading modes
- **Risk management** and validation
- **Real-time notifications** via Discord webhooks
- **Comprehensive monitoring** with Prometheus and AlertManager
- **Historical analytics** and backtesting capabilities

### Technology Stack

- **Rust**: High-performance services (Data, Forward, Backward, Execution, CNS)
- **Python**: Orchestration layer (Gateway service with FastAPI)
- **Kotlin/JS**: Web interface (Compose Web)
- **QuestDB**: Time-series database for market data
- **PostgreSQL**: Relational database for analytics
- **Redis**: Pub/Sub coordination and caching
- **Prometheus**: Metrics collection
- **Grafana**: Visualization
- **Docker**: Containerization

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WEB INTERFACE (Kotlin/JS)                       │
│                     src/clients/web (Compose Web)                       │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │ • HTTP API Calls → /api/v1/* (via nginx proxy)               │      │
│  │ • WebSocket → /ws/signals, /ws/stream                        │      │
│  │ • Signal Matrix, Health Dashboard, Setup                     │      │
│  └──────────────────────────────────────────────────────────────┘      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTPS/WSS
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    GATEWAY SERVICE (Python FastAPI)                     │
│                  src/janus/services/gateway (Port 8000)                 │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │ REST Routers:                                                 │      │
│  │ • /api/signals - Signal generation & dispatch                │      │
│  │ • /api/control - Service orchestration                       │      │
│  │ • /api/dashboard - Metrics & status                          │      │
│  │ • /api/health - Health checks                                │      │
│  │                                                               │      │
│  │ Connections:                                                  │      │
│  │ • gRPC client → Forward (50051), Backward (7000)             │      │
│  │ • Redis Pub/Sub → Signal dispatcher                          │      │
│  │ • QuestDB HTTP → Data queries                                │      │
│  │ • Heartbeat task → 2s interval (Dead Man's Switch)           │      │
│  └──────────────────────────────────────────────────────────────┘      │
└─────┬──────────────────────┬────────────────────┬───────────────────────┘
      │                      │                    │
      │ Redis Pub/Sub        │ gRPC               │ HTTP Queries
      │ janus:signals        │                    │
      ▼                      ▼                    ▼
┌─────────────┐    ┌──────────────────┐   ┌────────────────┐
│   REDIS     │    │  FORWARD SERVICE │   │    QUESTDB     │
│  Port 6379  │    │      (Rust)      │   │  Ports 9000/   │
│             │    │   Port 50051     │   │      9009      │
└─────────────┘    └──────────────────┘   └────────────────┘
                            │
                            │ gRPC
                            ▼
                   ┌──────────────────┐
                   │  EXECUTION SVC   │
                   │      (Rust)      │
                   │   Port 50052     │
                   └──────────────────┘
```

---

## Core Services

### 1. **Web Interface** (Kotlin/JS - Compose Web)
- **Location**: `src/clients/web`
- **Purpose**: User interface for monitoring and control
- **Features**:
  - Signal Matrix display
  - Health dashboard
  - Setup and configuration
  - WebSocket streaming for real-time updates
- **Connections**:
  - HTTP REST API → Gateway `/api/v1/*`
  - WebSocket → Data Service `/ws/signals`, `/ws/stream`

### 2. **Gateway Service** (Python FastAPI)
- **Location**: `src/janus/services/gateway`
- **Port**: 8000 (HTTP)
- **Purpose**: Orchestration and API layer
- **Features**:
  - Signal generation and dispatch
  - Service coordination
  - Redis Pub/Sub signal dispatcher
  - gRPC client to Rust services
  - Heartbeat management (Dead Man's Switch)
- **Connections**:
  - Forward Service (gRPC 50051)
  - Backward Service (gRPC 7000)
  - Redis Pub/Sub (signal dispatch)
  - QuestDB (HTTP queries)

### 3. **Data Service** (Rust)
- **Location**: `src/data`
- **Port**: 8080 (HTTP/WebSocket)
- **Purpose**: Real-time market data ingestion and processing
- **Features**:
  - Multi-exchange WebSocket connections (Binance, Bybit, Kucoin)
  - Real-time technical indicators (EMA, RSI, MACD, ATR)
  - Signal generation (analysis only, not for execution)
  - Gap detection and backfill orchestration
  - WebSocket streaming for clients
- **Actor Model Architecture**:
  - Router Actor: Dispatches messages
  - Storage Actor: Batched ILP writes to QuestDB
  - Indicator Actor: Calculates technical indicators
  - Signal Actor: Generates analysis signals
- **Connections**:
  - Exchange WebSockets (external)
  - QuestDB (ILP port 9009)
  - Redis (deduplication and rate limiting)

### 4. **Forward Service** (Rust)
- **Location**: `src/janus/services/forward`
- **Ports**: 50051 (gRPC), 8080 (REST), 8081 (WebSocket), 9100 (Prometheus)
- **Purpose**: Real-time signal processing and execution coordination
- **Features**:
  - Subscribes to Redis `janus:signals` channel
  - Signal validation and enrichment
  - WebSocket streaming
  - Execution service integration via gRPC
  - Heartbeat monitoring (Dead Man's Switch)
- **Trading Modes**: Paper, Simulated, Live
- **Connections**:
  - Redis (Pub/Sub subscription)
  - Execution Service (gRPC 50052)
  - QuestDB (tick storage)

### 5. **Backward Service** (Rust)
- **Location**: `src/janus/services/backward`
- **Ports**: 8082 (HTTP), 9091 (Prometheus)
- **Purpose**: Historical analysis, persistence, and backtesting
- **Features**:
  - PostgreSQL-based analytics
  - Signal history tracking
  - Portfolio performance analysis
  - Position history and metrics
  - Job queue integration (Apalis + Redis)
  - Scheduled analytics jobs
- **Database Repositories**:
  - SignalRepository
  - PortfolioRepository
  - PositionRepository
  - PerformanceRepository
  - MetricsRepository
- **Connections**:
  - PostgreSQL (analytics database)
  - QuestDB (historical market data)
  - Redis (job queue)

### 6. **Execution Service** (Rust)
- **Location**: `src/execution`
- **Ports**: 50052 (gRPC), 8081 (HTTP)
- **Purpose**: Order execution and position management
- **Features**:
  - Risk validation (position size, exposure, daily loss limits)
  - Multi-mode execution (simulated, paper, live)
  - Bybit exchange integration (V5 API)
  - Order history tracking
  - Discord webhook notifications
- **Execution Modes**:
  - **Simulated**: Instant fills with configurable slippage/fees
  - **Paper**: Bybit testnet API
  - **Live**: Bybit mainnet with real money
- **Connections**:
  - Bybit API (external)
  - QuestDB (order history)
  - Redis (state management)
  - Discord Webhook (notifications)

### 7. **CNS Service** (Central Nervous System - Rust)
- **Location**: `src/janus/services/cns`
- **Port**: 9091 (HTTP + Prometheus)
- **Purpose**: Health monitoring and auto-recovery
- **Features**:
  - Probes all service health endpoints
  - Neuromorphic brain coordinator
  - Auto-recovery capabilities
  - Aggregated health status
- **Monitored Services**:
  - Forward, Backward, Gateway, Data, Execution
- **Health Check Interval**: 30 seconds

---

## Signal Flow Architecture

### **CRITICAL: Two Separate Signal Paths**

The FKS system has **TWO INDEPENDENT** signal flows:

#### **Path 1: Analysis Signals** (Monitoring Only)
**Purpose**: Real-time market analysis and monitoring  
**Does NOT trigger execution**

```
Exchange WebSockets
        ↓
Data Service (Rust)
        ↓
Indicator Actor → Technical indicators (EMA, RSI, MACD, ATR)
        ↓
Signal Actor → Detects patterns:
        • EMA Golden Cross / Death Cross
        • RSI Overbought / Oversold
        • MACD Bullish/Bearish Crossover
        • Confluence signals
        ↓
Three outputs:
1. QuestDB (historical storage)
2. Prometheus metrics
3. WebSocket stream: /ws/signals
        ↓
Web Interface / Monitoring Clients
(Display only, no execution)
```

**Key Points**:
- ⚠️ **Does NOT publish to Redis**
- ⚠️ **Does NOT trigger execution**
- ✅ Used for monitoring and analysis
- ✅ Streamed via WebSocket for real-time dashboards

---

#### **Path 2: Execution Signals** (Actual Trading)
**Purpose**: User-initiated trading signals that trigger execution

```
Web Interface
        ↓
User action (manual signal generation)
        ↓
HTTP POST → Gateway Service
        ↓
Gateway endpoints:
• /api/signals/generate
• /api/signals/dispatch
        ↓
SignalDispatcher (Python)
        ↓
Redis Pub/Sub PUBLISH
Channel: "janus:signals"
Format: JSON signal {
  "symbol": "BTCUSD",
  "side": "Buy" | "Sell",
  "strength": 0.0-1.0,
  "confidence": 0.0-1.0,
  "entry_price": float,
  "stop_loss": float,
  "take_profit": float
}
        ↓
Forward Service (Rust)
SignalReceiver subscribes to "janus:signals"
        ↓
Signal validation & enrichment
        ↓
IF ENABLE_EXECUTION=true:
        ↓
gRPC call → Execution Service
        ↓
Risk validation → Order execution → Discord notification
```

**Key Points**:
- ✅ User-initiated through Web Interface
- ✅ Gateway publishes to Redis Pub/Sub
- ✅ Forward subscribes and receives
- ✅ Triggers actual execution (if enabled)
- ✅ Discord notifications sent from Execution Service

---

## Data Flow Pipeline

### Market Data Ingestion

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Exchange WebSocket Connections                         │
│                                                                  │
│ Data Service establishes WebSocket connections:                 │
│ • Binance (primary) - wss://stream.binance.com:9443/ws         │
│ • Bybit (secondary, failover) - wss://stream.bybit.com/v5...   │
│ • Kucoin (tertiary) - REST polling + WebSocket                 │
│                                                                  │
│ Subscriptions:                                                  │
│ • Trade streams (real-time ticks)                              │
│ • Kline/Candlestick streams (1m, 5m, 15m, 1h, 4h, 1d)         │
│ • Ticker streams (24h stats)                                   │
│ • Order book snapshots (depth updates)                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Router Actor (Actor Model)                             │
│                                                                  │
│ Normalizes messages from different exchanges                    │
│ Applies deduplication (Redis-backed)                            │
│ Routes to appropriate actors:                                   │
│ • Storage Actor (for persistence)                              │
│ • Indicator Actor (for calculations)                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Storage Actor                                           │
│                                                                  │
│ Batches writes for high throughput                              │
│ Uses Influx Line Protocol (ILP)                                 │
│ Writes to QuestDB port 9009                                     │
│ Flush interval: 100ms (configurable)                            │
│ Buffer size: 1000 messages (configurable)                       │
│                                                                  │
│ Performance:                                                     │
│ • Sub-millisecond latency                                       │
│ • 100K+ ticks/second ingestion rate                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Indicator Actor                                         │
│                                                                  │
│ Subscribes to candle updates                                    │
│ Calculates indicators incrementally (O(1) updates):             │
│ • EMA-8, EMA-21, EMA-50, EMA-200                               │
│ • RSI-14                                                        │
│ • MACD (12, 26, 9)                                             │
│ • ATR-14                                                        │
│                                                                  │
│ Warmup: Loads historical candles from QuestDB on startup        │
│ Broadcasts updates via internal channel                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Signal Actor (Analysis Only)                            │
│                                                                  │
│ Subscribes to indicator updates                                 │
│ Pattern detection:                                              │
│ • EMA Crossovers (Golden Cross, Death Cross)                   │
│ • RSI Thresholds (>70 overbought, <30 oversold)                │
│ • MACD Crossovers (signal line crosses)                        │
│ • Confluence (multiple indicators align)                        │
│                                                                  │
│ Outputs:                                                         │
│ 1. QuestDB storage                                             │
│ 2. Prometheus metrics                                           │
│ 3. WebSocket broadcast: /ws/signals                            │
│                                                                  │
│ ⚠️  NOT sent to Redis (no execution trigger)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Execution & Notification Flow

### Order Execution Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Signal Reception (Forward Service)                     │
│                                                                  │
│ SignalReceiver (communication.rs):                              │
│ • Subscribes to Redis channel: "janus:signals"                 │
│ • Parses JSON signal messages                                  │
│ • Forwards to TradingEngine via mpsc channel                   │
│                                                                  │
│ HeartbeatMonitor:                                               │
│ • Subscribes to Redis channel: "janus:heartbeat"               │
│ • Expects heartbeat every 2s from Gateway                      │
│ • Timeout: 5 seconds (Dead Man's Switch)                       │
│ • Shuts down Forward if no heartbeat                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Signal Processing (Forward Service)                    │
│                                                                  │
│ TradingEngine (engine.rs):                                      │
│ • Receives signal from internal channel                        │
│ • Validates signal structure                                   │
│ • Enriches with current market data                            │
│ • Checks ENABLE_EXECUTION environment variable                 │
│                                                                  │
│ IF ENABLE_EXECUTION=true:                                       │
│   → Call ExecutionClient.submit_signal() via gRPC              │
│ ELSE:                                                            │
│   → Log signal and broadcast via WebSocket                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                         gRPC Call
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Risk Validation (Execution Service)                    │
│                                                                  │
│ OrderValidator checks:                                          │
│ ✓ Position size ≤ MAX_POSITION_SIZE_USD                        │
│ ✓ Portfolio exposure ≤ MAX_PORTFOLIO_EXPOSURE_USD              │
│ ✓ Open positions ≤ MAX_OPEN_POSITIONS                          │
│ ✓ Daily loss ≤ MAX_DAILY_LOSS_USD                              │
│ ✓ Symbol is tradeable                                          │
│ ✓ Quantity is valid                                            │
│                                                                  │
│ IF validation fails:                                            │
│   → Reject order                                               │
│   → Send Discord error notification                            │
│   → Return error to Forward Service                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                      Validation Passed
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Order Execution (Execution Service)                    │
│                                                                  │
│ ExecutionEngine (mode-dependent):                               │
│                                                                  │
│ MODE: SIMULATED                                                 │
│ • SimulatedExecutionEngine                                      │
│ • Instant fill with configurable slippage                      │
│ • Simulated fees (SIMULATION_FEE_BPS)                          │
│ • Fill delay (SIMULATION_FILL_DELAY_MS)                        │
│ • No external API calls                                        │
│                                                                  │
│ MODE: PAPER                                                     │
│ • Bybit testnet API integration                                │
│ • Real price discovery, no real money                          │
│ • BYBIT_TESTNET=true                                           │
│ • Uses Bybit V5 API                                            │
│                                                                  │
│ MODE: LIVE                                                      │
│ • Bybit mainnet API (V5)                                       │
│ • Real money execution                                         │
│ • Requires BYBIT_API_KEY + BYBIT_API_SECRET                    │
│ • BYBIT_TESTNET=false                                          │
│ • Production risk controls active                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                      Order Filled
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Post-Execution (Parallel Operations)                   │
│                                                                  │
│ 1. Order History → QuestDB (port 9009)                         │
│    • Audit trail with full order details                       │
│    • Fill information, timestamps                              │
│                                                                  │
│ 2. State Management → Redis                                    │
│    • Position tracking                                         │
│    • Portfolio state updates                                   │
│                                                                  │
│ 3. Metrics → Prometheus (built-in /metrics)                    │
│    • Order count, fill rate                                    │
│    • P&L metrics                                               │
│    • Execution latency                                         │
│                                                                  │
│ 4. Discord Notifications (if enabled)                          │
│    • Signal received (🎯)                                      │
│    • Order filled (✅ buy / 💰 sell)                          │
│    • Position update (📊 - optional)                          │
│    • Error notification (❌)                                   │
│                                                                  │
│ 5. gRPC Response → Forward Service                             │
│    • Success/failure status                                    │
│    • Order ID, fill price                                      │
│    • Timestamp                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Discord Notification Details

```
┌─────────────────────────────────────────────────────────────────┐
│ Discord Notifier (src/execution/src/notifications/discord.rs)   │
│                                                                  │
│ Configuration:                                                  │
│ • DISCORD_WEBHOOK_GENERAL - Discord webhook endpoint               │
│ • DISCORD_ENABLE_NOTIFICATIONS - Master enable/disable         │
│ • DISCORD_NOTIFY_ON_SIGNAL - Signal received notifications     │
│ • DISCORD_NOTIFY_ON_FILL - Order fill notifications            │
│ • DISCORD_NOTIFY_ON_ERROR - Error notifications                │
│ • DISCORD_NOTIFY_ON_POSITION - Position updates (optional)     │
│                                                                  │
│ Notification Types:                                             │
│                                                                  │
│ 1. SIGNAL RECEIVED (🎯)                                        │
│    • Symbol, side (Buy/Sell)                                   │
│    • Entry price, quantity                                     │
│    • Confidence level                                          │
│    • Strategy ID                                               │
│    • Timestamp                                                 │
│                                                                  │
│ 2. ORDER FILLED (✅ Buy / 💰 Sell)                            │
│    • Order ID (internal + exchange)                           │
│    • Symbol, side, quantity                                    │
│    • Fill price (average if partial)                          │
│    • Total cost/proceeds                                       │
│    • Fees and commission                                       │
│    • Execution mode (simulated/paper/live)                     │
│    • Timestamp                                                 │
│                                                                  │
│ 3. POSITION UPDATE (📊)                                        │
│    • Symbol, position size                                     │
│    • Entry price, current price                               │
│    • Unrealized P&L                                            │
│    • Realized P&L                                              │
│    • ROI percentage                                            │
│                                                                  │
│ 4. ERROR NOTIFICATION (❌)                                     │
│    • Error type and message                                    │
│    • Context (symbol, order ID)                               │
│    • Stack trace (if available)                               │
│    • Timestamp                                                 │
│                                                                  │
│ Format: Discord Embeds (rich formatting)                        │
│ • Color-coded by type (green/red/yellow/blue)                  │
│ • Structured fields for easy reading                           │
│ • Timestamps in ISO 8601 format                                │
│ • Emoji indicators for quick visual scanning                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Monitoring & Alerting

### Two Independent Alert Channels

#### **Channel 1: Execution Notifications** (Real-time, Per-Trade)

```
Execution Service
        ↓
DiscordNotifier
        ↓
Direct HTTP POST
        ↓
Discord Webhook API
        ↓
Discord Channel (e.g., #trading-signals)
```

**Characteristics**:
- ✅ Real-time, immediate notifications
- ✅ Per-trade granularity
- ✅ Sent directly from Execution Service
- ✅ Independent of monitoring infrastructure
- ✅ Configured via environment variables

**Use Case**: Trade execution alerts, fill confirmations, errors

---

#### **Channel 2: System Monitoring Alerts** (Infrastructure Health)

```
All Services
        ↓
Prometheus Exporters (/metrics endpoints)
        ↓
Prometheus (scrape every 15s)
        ↓
Alert Rules (evaluate every 30s)
        ↓
AlertManager (route by severity)
        ↓
Discord Bridge (port 9094)
        ↓
Transform to Discord embeds
        ↓
Discord Webhook API
        ↓
Discord Channel (e.g., #system-alerts)
```

**Characteristics**:
- ✅ Infrastructure and performance monitoring
- ✅ Aggregated metrics across all services
- ✅ Alert grouping and deduplication
- ✅ Severity-based routing
- ✅ Runbook and dashboard links

**Use Case**: Data quality issues, performance degradation, service health

---

### Prometheus Metrics Collection

```
┌─────────────────────────────────────────────────────────────────┐
│ PROMETHEUS (Port 9090)                                          │
│ config/prometheus/prometheus.yml                                │
│                                                                  │
│ Scrape Targets (15s interval):                                  │
│ • data:8080/metrics - Data Factory                             │
│ • forward:9100/metrics - Forward Service                       │
│ • backward:9091/metrics - Backward Service (⚠️  port conflict)│
│ • execution:8081/metrics - Execution Service                   │
│ • cns:9091/metrics - CNS Service (⚠️  port conflict)          │
│ • gateway:8000/metrics - Gateway Service                       │
│ • questdb:9003/metrics - QuestDB                               │
│                                                                  │
│ Alert Rules (30s evaluation):                                   │
│ • config/prometheus/alerts/data.yml                             │
│ • config/prometheus/alerts/market-data-pipeline.yml             │
│ • config/prometheus/alerts/technical-indicators.yml             │
│                                                                  │
│ Retention:                                                       │
│ • Time: 30 days (--storage.tsdb.retention.time=30d)            │
│ • Size: 10GB (--storage.tsdb.retention.size=10GB)              │
└─────────────────────────────────────────────────────────────────┘
```

### Example Alert Rules

```yaml
# Critical: Data Completeness Low
alert: DataCompletenessLow
expr: data_completeness_percent < 99.9
for: 5m
labels:
  severity: critical
  component: data-factory
annotations:
  summary: "Data completeness below SLO"
  description: "{{ $value }}% data completeness (target: 99.9%)"

# Critical: Ingestion Latency High
alert: IngestionLatencyHigh
expr: histogram_quantile(0.99, rate(ingestion_latency_ms_bucket[5m])) > 1000
for: 5m
labels:
  severity: critical
  component: data-factory
annotations:
  summary: "P99 ingestion latency above 1000ms"
  description: "{{ $value }}ms latency (target: <100ms)"

# Critical: Circuit Breaker Open
alert: CircuitBreakerOpen
expr: circuit_breaker_state == 1
for: 1m
labels:
  severity: critical
  component: rate-limiter
annotations:
  summary: "Rate limiter circuit breaker is OPEN"
  description: "Too many errors detected, circuit breaker triggered"

# Warning: QuestDB Write Errors
alert: QuestDBWriteErrors
expr: rate(questdb_write_errors_total[5m]) > 0.1
for: 5m
labels:
  severity: warning
  component: questdb
annotations:
  summary: "QuestDB write errors detected"
  description: "{{ $value }} errors/sec writing to QuestDB"
```

---

## Service Details

### Data Service (Rust)

**Location**: `src/data`  
**Main Entry**: `src/data/src/main.rs`

**Architecture**: Actor Model using Tokio

**Actors**:
1. **Router Actor** - Central message dispatcher
2. **Storage Actor** - Batched writes to QuestDB
3. **Indicator Actor** - Real-time indicator calculation
4. **Signal Actor** - Pattern detection and signal generation
5. **Connector Actors** - Per-exchange WebSocket handlers
6. **Metrics Pollers** - Alternative data sources

**Key Features**:
- Sub-millisecond latency for message processing
- 100K+ ticks/second ingestion to QuestDB
- O(1) incremental indicator updates
- Zero-copy deserialization
- Automatic failover between exchanges
- Gap detection and backfill orchestration
- Redis-backed deduplication
- Circuit breakers for rate limiting

**Endpoints**:
- `GET /health` - Service health check
- `GET /metrics` - Prometheus metrics
- `GET /api/v1/gaps` - Gap analysis
- `GET /api/v1/indicators` - Current indicator values
- `GET /api/v1/signals` - Recent signals
- `WS /ws/stream` - Real-time market data stream
- `WS /ws/signals` - Real-time signal stream

---

### Forward Service (Rust)

**Location**: `src/janus/services/forward`  
**Main Entry**: `src/janus/services/forward/src/main.rs`

**Purpose**: Real-time signal processing and execution coordination

**Key Components**:
1. **SignalReceiver** (`communication.rs`)
   - Subscribes to Redis `janus:signals`
   - Parses and validates incoming signals
   - Forwards to TradingEngine

2. **HeartbeatMonitor** (`communication.rs`)
   - Subscribes to Redis `janus:heartbeat`
   - Dead Man's Switch (5s timeout)
   - Graceful shutdown if no heartbeat

3. **TradingEngine** (`engine.rs`)
   - Main event loop
   - Signal processing and enrichment
   - ExecutionClient integration

4. **ExecutionClient** (`execution/client.rs`)
   - gRPC client to Execution Service
   - Signal submission
   - Error handling and retries

**Configuration**:
```rust
pub struct ForwardServiceConfig {
    pub host: String,                    // Default: "0.0.0.0"
    pub grpc_port: u16,                  // Default: 50051
    pub rest_port: u16,                  // Default: 8080
    pub websocket_port: u16,             // Default: 8081
    pub metrics_port: u16,               // Default: 9100
    pub enable_metrics: bool,            // Default: true
    pub execution_config: Option<ExecutionClientConfig>,
}
```

---

### Backward Service (Rust)

**Location**: `src/janus/services/backward`  
**Main Entry**: `src/janus/services/backward/src/main.rs`

**Purpose**: Historical analysis, persistence, and backtesting

**Database Repositories** (PostgreSQL via SQLx):
1. **SignalRepository** - Historical signal storage
2. **PortfolioRepository** - Portfolio performance tracking
3. **PositionRepository** - Position history and analytics
4. **PerformanceRepository** - Strategy performance metrics
5. **MetricsRepository** - Aggregated KPIs

**Features**:
- SQLx migrations (`migrations/` directory)
- Job queue (Apalis + Redis)
- Scheduled analytics jobs (planned)
- Performance aggregation
- Risk metrics calculation
- Signal metrics tracking

**Configuration**:
```rust
pub struct BackwardServiceConfig {
    pub host: String,
    pub http_port: u16,                  // Default: 8082
    pub metrics_port: u16,               // Default: 9091 (⚠️  conflicts with CNS)
    pub database_config: DatabaseConfig,
    pub redis_url: String,
    pub worker_threads: usize,           // Default: 4
    pub enable_scheduler: bool,          // Default: true
}
```

**TODO Items** (from source code):
- Implement job scheduler for periodic analytics
- Worker thread pool for background processing
- Backtesting engine
- Pattern recognition algorithms

---

### Execution Service (Rust)

**Location**: `src/execution`  
**Main Entry**: `src/execution/src/main.rs`

**Purpose**: Order execution, position management, risk controls

**Key Components**:
1. **OrderManager** - Order lifecycle management
2. **OrderValidator** - Risk validation
3. **ExecutionEngine** - Mode-dependent execution
4. **DiscordNotifier** - Webhook notifications
5. **NotificationManager** - Notification orchestration

**Execution Modes**:
```rust
pub enum ExecutionMode {
    Simulated,  // No external API, instant fills
    Paper,      // Bybit testnet API
    Live,       // Bybit mainnet, real money
}
```

**Risk Validation**:
- Position size limits
- Portfolio exposure limits
- Max open positions
- Daily loss limits
- Symbol validation
- Quantity validation

**Bybit Integration**:
- V5 API support
- Testnet and mainnet
- WebSocket for fills and updates
- REST API for order submission
- Rate limiting compliance

---

### CNS Service (Central Nervous System - Rust)

**Location**: `src/janus/services/cns`  
**Main Entry**: `src/janus/services/cns/src/main.rs`

**Purpose**: Health monitoring and auto-recovery

**Configuration**: `config/cns/cns.toml`
```toml
[endpoints]
forward_service = "http://forward:8080/api/v1/health"
backward_service = "http://backward:8082/health"
gateway_service = "http://gateway:8000/health"
data_service = "http://data:8080/health"
execution_service = "http://execution:8081/health"

[health_check]
interval_seconds = 30
timeout_seconds = 10
retries = 3
```

**Features**:
- Service health probing
- Neuromorphic brain coordinator
- Auto-recovery (planned)
- Aggregated health dashboard
- Prometheus metrics export

**Endpoints**:
- `GET /health` - CNS health
- `GET /health/detailed` - All service status
- `GET /metrics` - Prometheus metrics
- `GET /status` - Overall system status
- `GET /brain` - Brain status
- `GET /brain/regions` - Neuromorphic regions

---

### Gateway Service (Python)

**Location**: `src/janus/services/gateway`  
**Main Entry**: `src/janus/services/gateway/src/main.py`

**Framework**: FastAPI

**Routers**:
- `control.router` - Service control operations
- `view.router` - Data views and queries
- `training.router` - Model training operations
- `models.router` - Model management
- `tasks.router` - Task queue operations
- `health.router` - Health checks
- `signals.router` - Signal operations
- `dashboard.router` - Dashboard data
- `ai.router` - AI/ML endpoints
- `guidance.router` - Trading guidance
- `metrics.router` - Metrics queries
- `allocation.router` - Portfolio allocation
- `user_data.router` - User data management
- `experiments.router` - A/B testing

**Key Classes**:
1. **JanusClient** - gRPC client to Rust services
2. **SignalDispatcher** - Redis Pub/Sub publisher
3. **SignalService** - Signal file management

**Lifespan Management**:
- Connects to Forward and Backward via gRPC on startup
- Establishes Redis connection for signal dispatch
- Starts heartbeat task (2s interval)
- Graceful shutdown with connection cleanup

---

## Environment Configuration

### Complete Environment Variables

```bash
# ============================================================================
# TRADING CONFIGURATION
# ============================================================================
TRADING_MODE=simulated|paper|live       # Overall system trading mode
EXECUTION_MODE=simulated|paper|live     # Execution service mode
ENABLE_EXECUTION=true|false             # Forward → Execution integration

# ============================================================================
# DISCORD NOTIFICATIONS
# ============================================================================
# Execution Service Direct Notifications (Real-time per-trade)
DISCORD_WEBHOOK_GENERAL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
DISCORD_ENABLE_NOTIFICATIONS=true
DISCORD_NOTIFY_ON_SIGNAL=true          # 🎯 Signal received notifications
DISCORD_NOTIFY_ON_FILL=true            # ✅ Order filled notifications
DISCORD_NOTIFY_ON_ERROR=true           # ❌ Execution error notifications
DISCORD_NOTIFY_ON_POSITION=false       # 📊 Position update notifications

# Monitoring Alerts (Optional - separate webhook for system alerts)
# Configure in config/prometheus/alertmanager.yml

# ============================================================================
# REDIS CONFIGURATION
# ============================================================================
REDIS_URL=redis://redis:6379/0         # Pub/Sub + state management

# Channels (hardcoded in code):
# - janus:signals (Gateway → Forward signal dispatch)
# - janus:heartbeat (Gateway → Forward heartbeat, 2s interval)

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
# QuestDB (Time-series data)
QUESTDB_HOST=questdb
QUESTDB_HTTP_PORT=9000                  # HTTP queries
QUESTDB_ILP_PORT=9009                   # Influx Line Protocol writes
QUESTDB_HTTP_URL=http://questdb:9000

# PostgreSQL (Backward service analytics)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=janus
DB_USER=janus
DB_PASSWORD=janus_dev_password
DB_MAX_CONNECTIONS=10
DB_MIN_CONNECTIONS=2
DB_CONNECT_TIMEOUT=30

# ============================================================================
# FORWARD SERVICE
# ============================================================================
FORWARD_HOST=0.0.0.0
FORWARD_GRPC_PORT=50051                 # gRPC API
FORWARD_REST_PORT=8080                  # REST API
FORWARD_WS_PORT=8081                    # WebSocket streaming
FORWARD_METRICS_PORT=9100               # Prometheus metrics
FORWARD_ENABLE_METRICS=true

# Execution integration
EXECUTION_ENDPOINT=http://execution:50052
EXECUTION_CONNECT_TIMEOUT=10
EXECUTION_REQUEST_TIMEOUT=30
EXECUTION_ENABLE_TLS=false
EXECUTION_MAX_RETRIES=3
EXECUTION_RETRY_BACKOFF_MS=100

# ============================================================================
# BACKWARD SERVICE
# ============================================================================
BACKWARD_HOST=0.0.0.0
BACKWARD_HTTP_PORT=8082                 # HTTP API
BACKWARD_METRICS_PORT=9091              # Prometheus metrics (⚠️  conflicts with CNS!)
BACKWARD_ENABLE_METRICS=true
BACKWARD_ENABLE_SCHEDULER=true
BACKWARD_WORKERS=4

# ============================================================================
# EXECUTION SERVICE
# ============================================================================
GRPC_PORT=50052                         # gRPC API
HTTP_PORT=8081                          # HTTP API (health, metrics)

# Bybit Exchange Configuration
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_TESTNET=true                      # false for live trading

# Risk Limits
MAX_POSITION_SIZE_USD=10000
MAX_PORTFOLIO_EXPOSURE_USD=50000
MAX_OPEN_POSITIONS=10
MAX_DAILY_LOSS_USD=1000
ENABLE_RISK_CHECKS=true

# Simulation Configuration (EXECUTION_MODE=simulated)
SIMULATION_INITIAL_BALANCE=100000
SIMULATION_SLIPPAGE_BPS=5               # 5 basis points = 0.05%
SIMULATION_FEE_BPS=10                   # 10 basis points = 0.10%
SIMULATION_FILL_DELAY_MS=100
SIMULATION_ENABLE_SLIPPAGE=true

# ============================================================================
# DATA SERVICE
# ============================================================================
# Assets to track
ASSETS=BTC,ETH,SOL

# Exchanges
PRIMARY_EXCHANGE=binance
SECONDARY_EXCHANGE=bybit
TERTIARY_EXCHANGE=kucoin

# Alternative Metrics
ENABLE_FEAR_GREED=true
ENABLE_ETF_FLOWS=true
ENABLE_VOLATILITY=true
ENABLE_ALTCOIN_SEASON=false
METRICS_POLL_INTERVAL_SECS=300

# Operational
ENABLE_BACKFILL=true
MAX_BACKFILL_HOURS=24
ENABLE_FAILOVER=true
FAILOVER_LATENCY_THRESHOLD_MS=500
FAILOVER_ERROR_COUNT=10
HEALTH_CHECK_INTERVAL_SECS=30

# ============================================================================
# GATEWAY SERVICE
# ============================================================================
SERVICE_PORT=8000
JANUS_FORWARD_URL=forward:50051         # gRPC to Forward
JANUS_BACKWARD_URL=backward:7000        # gRPC to Backward
REDIS_SIGNAL_URL=redis://redis:6379/0   # For signal dispatch
PROMETHEUS_URL=http://prometheus:9090

# ============================================================================
# CNS SERVICE
# ============================================================================
SERVICE_PORT=9091
CNS_HEALTH_CHECK_INTERVAL=30
CNS_METRICS_PORT=9091

# ============================================================================
# LOGGING
# ============================================================================
RUST_LOG=info,janus_forward=debug,janus_backward=debug,fks_execution=debug,fks_data=debug,janus_cns=debug
RUST_BACKTRACE=1
TZ=America/New_York
```

---

## Port Reference

| Service | Protocol | Port | Purpose |
|---------|----------|------|---------|
| **Web Interface** | HTTP/WS | 80/443 | Nginx proxy |
| **Gateway** | HTTP | 8000 | REST API |
| **Data Service** | HTTP/WS | 8080 | API + WebSocket |
| **Forward** | gRPC | 50051 | gRPC service |
| **Forward** | HTTP | 8080 | REST API |
| **Forward** | WebSocket | 8081 | Signal streaming |
| **Forward** | HTTP | 9100 | Prometheus metrics |
| **Backward** | HTTP | 8082 | REST API |
| **Backward** | HTTP | 9091 | Prometheus metrics ⚠️ |
| **Execution** | gRPC | 50052 | gRPC service |
| **Execution** | HTTP | 8081 | Health + metrics |
| **CNS** | HTTP | 9091 | Health + metrics ⚠️ |
| **Redis** | TCP | 6379 | Pub/Sub + cache |
| **QuestDB** | HTTP | 9000 | HTTP queries |
| **QuestDB** | ILP | 9009 | Influx Line Protocol |
| **QuestDB** | HTTP | 9003 | Prometheus metrics |
| **PostgreSQL** | TCP | 5432 | Relational database |
| **Prometheus** | HTTP | 9090 | Metrics collection |
| **Grafana** | HTTP | 3000 | Visualization |
| **AlertManager** | HTTP | 9093 | Alert routing |
| **Discord Bridge** | HTTP | 9094 | Alert transformation |

**⚠️ Port Conflicts**: Backward and CNS both default to port 9091 for metrics. Configure different ports in production.

---

## Key Clarifications

### What You Should Know

#### ✅ **Correct Understanding**:
1. Data service feeds data into the system via QuestDB
2. Forward service processes trading signals
3. Signals output to execution service
4. Execution triggers fills (simulated, paper, live)
5. Discord webhooks are enabled and configurable
6. Prometheus feeds metrics and can trigger alerts

#### ⚠️ **Critical Clarifications**:

1. **Two Separate Signal Paths Exist**:
   - **Analysis Signals**: Data Service → WebSocket streaming (monitoring only, NO execution)
   - **Execution Signals**: Web Interface → Gateway → Redis → Forward → Execution

2. **Data Service Signals Do NOT Trigger Execution**:
   - They are for monitoring and analysis only
   - Streamed via WebSocket `/ws/signals`
   - Stored in QuestDB for historical analysis
   - Do NOT publish to Redis Pub/Sub

3. **Execution Signals Come From Gateway**:
   - User-initiated through Web Interface
   - Gateway publishes to Redis `janus:signals` channel
   - Forward subscribes and receives
   - Forward calls Execution Service (if `ENABLE_EXECUTION=true`)

4. **Discord Webhooks Have Two Independent Channels**:
   - **Channel 1**: Execution Service → Direct HTTP POST (per-trade notifications)
   - **Channel 2**: Prometheus → AlertManager → Discord Bridge (system monitoring)
   - These are completely independent systems
   - Can use different Discord webhooks/channels

5. **Backward Service Exists**:
   - Not missing, located in `src/janus/services/backward`
   - PostgreSQL-based analytics and persistence
   - Historical analysis, backtesting (planned), performance metrics
   - Has TODO items for scheduler and worker implementation

6. **Port Conflict Warning**:
   - Both Backward and CNS default to port 9091 for metrics
   - Must configure different ports in production
   - Recommended: Keep CNS on 9091, move Backward to 9200

### Common Misconceptions

❌ **WRONG**: Data service signals automatically trigger trades  
✅ **CORRECT**: Data service signals are for analysis only; trades are user-initiated via Gateway

❌ **WRONG**: All signals flow through the same path  
✅ **CORRECT**: Two independent paths: analysis (WebSocket) and execution (Redis Pub/Sub)

❌ **WRONG**: Discord notifications come only from Prometheus  
✅ **CORRECT**: Two sources: Execution Service (trade alerts) and Prometheus (system alerts)

❌ **WRONG**: Backward service is missing or incomplete  
✅ **CORRECT**: Backward service exists with full database repositories, scheduler is TODO

---

## Quick Start Guide

### Development Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/fks.git
cd fks

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# 3. Start infrastructure services
docker compose up -d redis questdb postgres prometheus grafana

# 4. Start FKS services
docker compose up -d data gateway forward execution backward cns

# 5. Verify health
curl http://localhost:8080/health  # Data service
curl http://localhost:8000/health  # Gateway
curl http://localhost:9091/health  # CNS

# 6. Access interfaces
# Web UI: http://localhost (nginx proxy)
# Grafana: http://localhost:3000
# Prometheus: http://localhost:9090
```

### Production Deployment

```bash
# Use production compose file
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Enable execution (after testing)
export ENABLE_EXECUTION=true
export EXECUTION_MODE=paper  # Start with paper trading
export DISCORD_ENABLE_NOTIFICATIONS=true

# Monitor logs
docker compose logs -f forward execution
```

---

## Support and Documentation

- **Main README**: `README.md`
- **Deployment Guide**: `docs/DEPLOY_NOW.sh`
- **Operations**: `docs/operations/`
- **Service Docs**: `docs/services/`
- **API Docs**: Generated by FastAPI at `http://localhost:8000/docs`

---

**Last Updated**: 2025-01-20  
**Maintainer**: FKS Development Team  
**License**: See LICENSE file