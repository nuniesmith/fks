# FKS Trading Engine - System Architecture

## Overview

FKS is a neuro-symbolic trading engine split across two deployment clusters for optimal performance and cost efficiency.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FKS TRADING SYSTEM                              │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────┐         ┌──────────────────────────────┐
│       HOME CLUSTER 🏠            │         │      CLOUD CLUSTER ☁️        │
│   (GPU/Training/Signals)         │         │   (Lightweight Execution)    │
│                                  │         │                              │
│  ┌────────────────────────────┐ │         │ ┌──────────────────────────┐ │
│  │  Forward Service           │ │         │ │  Execution Service (Sim) │ │
│  │  - Signal Generation       │ │         │ │  - Backtesting           │ │
│  │  - DSP Pipeline            │ │         │ │  - Strategy Validation   │ │
│  │  - LTN Inference           │ │         │ │  - Simulated Exchange    │ │
│  └────────────┬───────────────┘ │         │ └───────────┬──────────────┘ │
│               │                  │         │             │                │
│  ┌────────────▼───────────────┐ │         │ ┌───────────▼──────────────┐ │
│  │  Backward Service          │ │         │ │  Execution Service       │ │
│  │  - Model Training          │ │         │ │  (Paper)                 │ │
│  │  - LTN Optimization        │ │         │ │  - Live Market Data      │ │
│  │  - Hyperparameter Tuning   │ │         │ │  - Testnet Exchange      │ │
│  └────────────┬───────────────┘ │         │ │  - Simulated Orders      │ │
│               │                  │         │ └───────────┬──────────────┘ │
│  ┌────────────▼───────────────┐ │         │             │                │
│  │  Data Service              │ │         │ ┌───────────▼──────────────┐ │
│  │  - WebSocket Feeds         │ │         │ │  Execution Service       │ │
│  │  - Market Data Collection  │ │         │ │  (Live) ⚠️               │ │
│  │  - Order Book Processing   │ │         │ │  - Real Money            │ │
│  └────────────┬───────────────┘ │         │ │  - Mainnet Exchange      │ │
│               │                  │         │ │  - Real Orders           │ │
│  ┌────────────▼───────────────┐ │         │ └───────────┬──────────────┘ │
│  │  Gateway Service           │ │         │             │                │
│  │  - REST API                │ │         │ ┌───────────▼──────────────┐ │
│  │  - WebSocket API           │ │         │ │  Prometheus              │ │
│  │  - Service Orchestration   │ │         │ │  - Execution Metrics     │ │
│  └────────────┬───────────────┘ │         │ │  - Latency Monitoring    │ │
│               │                  │         │ └──────────────────────────┘ │
│  ┌────────────▼───────────────┐ │         │                              │
│  │  CNS Service               │ │         └──────────────────────────────┘
│  │  - Coordination            │ │                      ▲
│  │  - Health Monitoring       │ │                      │
│  │  - Alerting                │ │                      │
│  └────────────┬───────────────┘ │         ┌────────────┴─────────────────┐
│               │                  │         │   Secure Communication       │
│ ┌─────────────▼────────────────┐│         │   • Tailscale VPN            │
│ │  INFRASTRUCTURE              ││         │   • WireGuard                │
│ │                              ││         │   • SSH Tunnel               │
│ │  ┌──────────┐ ┌───────────┐ ││         │   • Encrypted Redis Pub/Sub  │
│ │  │PostgreSQL│ │  Redis    │ ││◄────────┤   • Metrics via QuestDB      │
│ │  │(Models)  │ │ (Signals) │ ││         └──────────────────────────────┘
│ │  └──────────┘ └───────────┘ ││
│ │                              ││
│ │  ┌──────────┐ ┌───────────┐ ││
│ │  │ QuestDB  │ │Prometheus │ ││
│ │  │ (Metrics)│ │ (Monitor) │ ││
│ │  └──────────┘ └───────────┘ ││
│ │                              ││
│ │  ┌──────────────────────────┐││
│ │  │      Grafana             │││
│ │  │   (Dashboards)           │││
│ │  └──────────────────────────┘││
│ └──────────────────────────────┘│
└──────────────────────────────────┘
```

## Data Flow

### 1. Market Data Flow
```
Exchange (Bybit)
      │
      │ WebSocket
      ▼
┌─────────────┐
│ Data Service│ (Home)
└─────┬───────┘
      │
      ├─────► QuestDB (Raw OHLCV, Order Book, Trades)
      │
      └─────► Redis Cache (Latest Prices)
```

### 2. Signal Generation Flow
```
QuestDB
   │
   ▼
┌────────────────┐
│ Forward Service│ (Home)
│  - DSP Pipeline│
│  - LTN Model   │
└────────┬───────┘
         │
         │ Publish Signal
         ▼
    Redis Pub/Sub ───────────────────┐
         │                           │
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│ Execution (Sim) │ (Cloud) │ Execution (Paper)│ (Cloud)
└─────────────────┘         └─────────────────┘
         │                           │
         │ Simulated Fill            │ Testnet Fill
         ▼                           ▼
    Redis Pub/Sub ◄──────────────────┘
         │
         ▼
┌─────────────────┐
│ QuestDB         │ (Home)
│ (Audit Trail)   │
└─────────────────┘
```

### 3. Training Flow
```
┌─────────────┐
│  QuestDB    │ (Historical Data)
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ Backward Service    │ (Home)
│ - Feature Engineering│
│ - LTN Training      │
│ - Validation        │
└──────────┬──────────┘
           │
           ├─────► PostgreSQL (Model Checkpoints)
           │
           └─────► /models volume (Trained Models)
                         │
                         ▼
                  ┌──────────────┐
                  │Forward Service│ (Loads New Models)
                  └──────────────┘
```

## Component Details

### Home Cluster Components

#### Forward Service (janus-forward)
- **Purpose**: Real-time signal generation
- **Technology**: Rust, Burn-rs (neural inference)
- **Key Features**:
  - DSP pipeline (Sevcik → Hurst → FRAMA)
  - LTN inference (8→32→64→32→3 MLP)
  - Zero-allocation hot path
  - Sub-microsecond latency target
- **Inputs**: Market data from QuestDB/Redis
- **Outputs**: Trading signals to Redis pub/sub
- **Resources**: 2-4 CPU cores, 2-4GB RAM

#### Backward Service (janus-backward)
- **Purpose**: Model training and optimization
- **Technology**: Rust, Burn-rs (training)
- **Key Features**:
  - Hybrid loss (supervised + semantic)
  - Walk-forward validation
  - Hyperparameter optimization
  - GPU acceleration (optional)
- **Inputs**: Historical data from QuestDB
- **Outputs**: Trained models, checkpoints
- **Resources**: 4-8 CPU cores, 4-8GB RAM, GPU (optional)

#### Data Service
- **Purpose**: Market data collection and normalization
- **Technology**: Rust
- **Key Features**:
  - WebSocket connection to Bybit
  - Order book reconstruction
  - Real-time OHLCV aggregation
  - Backfill capability
- **Inputs**: Exchange WebSocket feeds
- **Outputs**: QuestDB (time-series), Redis (cache)
- **Resources**: 2-4 CPU cores, 1-4GB RAM

#### Gateway Service
- **Purpose**: REST/WebSocket API for external access
- **Technology**: Rust (Axum/Actix)
- **Key Features**:
  - Authentication & authorization
  - Rate limiting
  - WebSocket subscriptions
  - Service orchestration
- **Inputs**: HTTP/WebSocket requests
- **Outputs**: Aggregated responses from all services
- **Resources**: 0.5-2 CPU cores, 256MB-1GB RAM

#### CNS Service (janus-cns)
- **Purpose**: Coordination, notification, health monitoring
- **Technology**: Rust
- **Key Features**:
  - Service discovery
  - Health checks
  - Discord/Slack notifications
  - Circuit breaker coordination
- **Inputs**: Service health metrics
- **Outputs**: Alerts, status updates
- **Resources**: 0.25-1 CPU core, 256-512MB RAM

### Cloud Cluster Components

#### Execution Service (Multiple Environments)
- **Purpose**: Trade execution and order management
- **Technology**: Rust
- **Environments**:
  1. **Simulation**: Backtesting, strategy validation
  2. **Paper**: Live market, simulated orders (testnet)
  3. **Live**: Real money, real orders (mainnet)
- **Key Features**:
  - Signal subscription via Redis
  - Order lifecycle management
  - Position tracking
  - Risk controls (circuit breaker, limits)
  - Slippage simulation
- **Inputs**: Signals from Redis, market data from exchange
- **Outputs**: Orders to exchange, fills to QuestDB
- **Resources**: 0.25-2 CPU cores, 256MB-1GB RAM (per environment)

## Network Architecture

### Communication Patterns

#### Home → Cloud (Signal Distribution)
```
Forward Service (Home)
    │
    │ Redis PUBLISH
    ▼
Redis Server (Home)
    │
    │ Tailscale/VPN Tunnel
    ▼
Execution Services (Cloud) ── SUBSCRIBE
    │
    │ Execute trades
    ▼
Exchange API
```

#### Cloud → Home (Metrics & Audit)
```
Execution Services (Cloud)
    │
    │ Fill data
    ▼
QuestDB ILP (Home) ◄─── Tailscale/VPN
    │
    ▼
Prometheus (Home) ── scrape metrics
    │
    ▼
Grafana (Home) ── visualize
```

### Security Layers

1. **Network Isolation**
   - Home cluster: Private network
   - Cloud cluster: Minimal attack surface
   - VPN tunnel (Tailscale) for inter-cluster communication

2. **Service Security**
   - No privileged containers
   - Read-only filesystems where possible
   - Dropped capabilities (CAP_DROP: ALL)
   - Resource limits enforced

3. **Data Security**
   - API keys in environment variables
   - Secrets management (Docker secrets in production)
   - TLS for all external communication
   - Redis AUTH for pub/sub channels

4. **Application Security**
   - Input validation
   - Rate limiting
   - Circuit breakers
   - Audit logging

## Scaling Strategies

### Horizontal Scaling

#### Execution Services
```
┌────────────────────────────────────┐
│        Load Balancer (nginx)       │
└────────┬───────────────────────────┘
         │
    ┌────┴────┬─────────┬──────────┐
    │         │         │          │
    ▼         ▼         ▼          ▼
┌─────────┐ ┌─────┐ ┌─────┐ ┌─────────┐
│Exec-Sim1│ │Sim2 │ │Sim3 │ │Sim-N    │
└─────────┘ └─────┘ └─────┘ └─────────┘
```

Deploy multiple execution instances:
- Simulation: Multiple instances for parallel backtesting
- Paper: 1-2 instances for redundancy
- Live: 1 primary + 1 hot standby

#### Signal Generation (Forward)
- Deploy multiple forward instances with different strategies
- Load balance via Redis streams
- Aggregate signals before execution

### Vertical Scaling

#### Training (Backward)
- Add GPU for faster training
- Increase RAM for larger datasets
- More CPU cores for parallel hyperparameter search

#### Data Collection
- Increase buffer sizes for high-volume periods
- Add more worker threads
- Scale QuestDB storage

## Deployment Topology

### Development
```
┌──────────────────────────┐
│  Single Machine          │
│  - All services local    │
│  - Docker Compose        │
│  - Simulation only       │
└──────────────────────────┘
```

### Staging
```
┌────────────────┐         ┌────────────────┐
│  Home Server   │◄───────►│  Cloud VM      │
│  - Training    │ VPN     │  - Paper Trade │
│  - Signals     │         │  - Simulation  │
└────────────────┘         └────────────────┘
```

### Production
```
┌────────────────┐         ┌────────────────┐
│  Home Cluster  │         │  Cloud Region 1│
│  - Training    │         │  - Live Trade  │
│  - Signals     │◄───────►│  - Paper Trade │
│  - Storage     │ VPN     │  - Monitoring  │
└────────────────┘         └────────────────┘
                                    │
                           ┌────────┴────────┐
                           │  Cloud Region 2 │
                           │  - Failover     │
                           │  - DR Site      │
                           └─────────────────┘
```

## Technology Stack

### Languages & Frameworks
- **Rust**: Core services (forward, backward, execution, data, gateway, cns)
- **Burn-rs**: Neural network inference & training
- **Tokio**: Async runtime
- **Axum/Actix**: HTTP/WebSocket servers

### Data Storage
- **QuestDB**: Time-series data (market data, metrics, audit trail)
- **PostgreSQL**: Relational data (model metadata, user data)
- **Redis**: Caching, pub/sub, session storage

### Monitoring & Observability
- **Prometheus**: Metrics collection
- **Grafana**: Visualization & dashboards
- **Jaeger**: Distributed tracing (optional)
- **Loki**: Log aggregation (optional)

### Infrastructure
- **Docker**: Containerization
- **Docker Compose**: Orchestration
- **Tailscale**: VPN networking
- **Nginx**: Reverse proxy, load balancing

### External Services
- **Bybit**: Exchange (spot & derivatives)
- **Discord**: Alerting & notifications
- **Cloudflare**: DNS, DDoS protection (optional)

## Resource Requirements

### Home Cluster (Minimum)
- CPU: 8 cores (16+ recommended)
- RAM: 16GB (32GB+ recommended)
- Storage: 100GB SSD (500GB+ for historical data)
- Network: 100 Mbps stable connection
- GPU: Optional (NVIDIA RTX 3060+ for training acceleration)

### Cloud Cluster (Minimum per environment)
- CPU: 1 core (2+ recommended)
- RAM: 512MB (1GB+ recommended)
- Storage: 10GB
- Network: Good connectivity to exchange & home cluster
- Cost: ~$4-6/month per VM (Hetzner/DigitalOcean)

### Estimated Monthly Costs
- **Home**: Electricity (~$20-50/month depending on usage)
- **Cloud Execution (3 environments)**: $12-30/month
- **Total**: ~$30-80/month operational costs

## Performance Characteristics

### Latency Targets
- **Data Ingestion**: <10ms (exchange → QuestDB)
- **Signal Generation**: <1ms (P50), <10ms (P99)
- **Signal Distribution**: <5ms (home Redis → cloud)
- **Order Execution**: <50ms (signal → exchange)
- **End-to-End**: <100ms (market event → order placed)

### Throughput Targets
- **Market Data**: 10,000+ ticks/second
- **DSP Pipeline**: 250,000+ ticks/second
- **Signal Generation**: 1,000+ signals/second
- **Order Execution**: 100+ orders/second per environment

### Reliability Targets
- **Uptime**: 99.9% (cloud execution)
- **Data Loss**: 0% (all trades audited)
- **Recovery Time**: <5 minutes (automatic failover)

## Future Enhancements

### Phase 4: Advanced Features (Months 5-8)
- Multi-exchange support (Binance, OKX, etc.)
- Advanced order types (TWAP, VWAP, iceberg)
- Portfolio optimization
- Cross-asset arbitrage

### Phase 5: Scale & Optimize (Months 9-12)
- Kubernetes deployment
- Multi-region active-active
- Real-time backtesting
- Custom hardware (FPGA for ultra-low latency)

### Phase 6: ML Enhancements (Months 13+)
- Reinforcement learning integration
- Ensemble models
- Meta-learning for strategy selection
- Automated hyperparameter optimization

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: FKS Engineering Team