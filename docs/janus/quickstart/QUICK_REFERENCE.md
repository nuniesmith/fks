# JANUS Quick Reference Guide

**Last Updated**: December 31, 2024  
**Version**: 1.0.0

---

## Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  JANUS Ecosystem                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Forward Service (Real-time)    Backward Service (Historical) │
│  ├─ Signal Generation           ├─ Database Persistence     │
│  ├─ WebSocket Streaming         ├─ Analytics Engine         │
│  ├─ Risk Management             ├─ Performance Metrics      │
│  ├─ ML Inference                ├─ Job Scheduler            │
│  └─ REST/gRPC APIs              └─ Background Workers       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Forward Service (Real-time)

```bash
# Navigate to forward service
cd src/janus/services/forward

# Build
cargo build --release

# Run
RUST_LOG=info,janus_forward=debug cargo run

# Test
cargo test
```

**Environment Variables**:
```bash
FORWARD_HOST=0.0.0.0
FORWARD_REST_PORT=8080
FORWARD_WS_PORT=8081
FORWARD_GRPC_PORT=50051
FORWARD_METRICS_PORT=9090
DATA_SERVICE_WS_URL=ws://localhost:8080/stream
```

### Backward Service (Historical)

```bash
# Navigate to backward service
cd src/janus/services/backward

# Build
cargo build --release

# Run (requires PostgreSQL)
RUST_LOG=info,janus_backward=debug cargo run

# Test
cargo test
```

**Environment Variables**:
```bash
BACKWARD_HOST=0.0.0.0
BACKWARD_HTTP_PORT=8082
BACKWARD_METRICS_PORT=9091
DB_HOST=localhost
DB_PORT=5432
DB_NAME=janus
DB_USER=postgres
DB_PASSWORD=postgres
REDIS_URL=redis://localhost:6379
```

---

## API Endpoints

### Forward Service

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/signals/generate` | Generate signal |
| POST | `/api/v1/signals/batch` | Batch generation |
| GET | `/api/v1/risk/config` | Get risk config |
| PUT | `/api/v1/risk/config` | Update risk config |
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| WS | `ws://host:8081/ws` | WebSocket streaming |

### Backward Service

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/signals` | Query signals |
| GET | `/api/v1/signals/:id` | Get signal by ID |
| GET | `/api/v1/performance` | Performance metrics |
| GET | `/api/v1/portfolio/:id` | Portfolio snapshot |
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |

---

## WebSocket Usage

### JavaScript Client

```javascript
const ws = new WebSocket('ws://localhost:8081/ws');

ws.onopen = () => {
    // Subscribe to signals
    ws.send(JSON.stringify({
        type: 'subscribe',
        symbols: ['BTCUSD', 'ETHUSDT'],
        min_confidence: 0.7,
        signal_types: ['Entry'],
        portfolio_updates: true,
        risk_alerts: true
    }));
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    switch (message.type) {
        case 'signal_update':
            console.log('Signal:', message.symbol, message.action);
            break;
        case 'risk_alert':
            console.warn('Risk Alert:', message.severity, message.message);
            break;
        case 'ping':
            ws.send(JSON.stringify({ type: 'pong' }));
            break;
    }
};
```

### Python Client

```python
import asyncio
import json
import websockets

async def connect():
    uri = "ws://localhost:8081/ws"
    async with websockets.connect(uri) as ws:
        # Subscribe
        await ws.send(json.dumps({
            "type": "subscribe",
            "symbols": ["BTCUSD"],
            "min_confidence": 0.7,
            "portfolio_updates": True,
            "risk_alerts": True
        }))
        
        # Listen
        async for message in ws:
            data = json.loads(message)
            print(f"Received: {data['type']}")

asyncio.run(connect())
```

---

## Common Commands

### Database Operations

```bash
# Run migrations (backward service)
cd services/backward
sqlx database create
sqlx migrate run

# Reset database
sqlx database drop
sqlx database create
sqlx migrate run
```

### Docker

```bash
# Build images
docker build -t janus-forward services/forward
docker build -t janus-backward services/backward

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f janus-forward
docker-compose logs -f janus-backward

# Stop services
docker-compose down
```

### Monitoring

```bash
# Check health
curl http://localhost:8080/health  # Forward
curl http://localhost:8082/health  # Backward

# Get metrics
curl http://localhost:9090/metrics  # Forward
curl http://localhost:9091/metrics  # Backward

# WebSocket stats (via metrics)
curl http://localhost:9090/metrics | grep janus_ws_
```

---

## Code Snippets

### Generate Signal (Forward Service)

```rust
use janus_forward::{SignalGenerator, SignalGeneratorConfig, IndicatorValues, Timeframe};

let config = SignalGeneratorConfig::default();
let generator = SignalGenerator::new(config);

let indicators = IndicatorValues::new()
    .with_ema(51.0, 50.0)
    .with_rsi(35.0)
    .with_strength(0.8);

let signal = generator
    .generate_from_indicators("BTCUSD".to_string(), Timeframe::H1, indicators)
    .await?;
```

### Persist Signal (Backward Service)

```rust
use janus_backward::{BackwardService, SignalRepository};

let service = BackwardService::new(config).await?;
let repo = service.signal_repository();

repo.create_signal(&signal).await?;
```

### Broadcast WebSocket Message

```rust
use janus_forward::websocket::{SignalBroadcaster, SignalUpdate};

let update = SignalUpdate {
    signal_id: Uuid::new_v4(),
    symbol: "BTCUSD".to_string(),
    timestamp: Utc::now(),
    confidence: 0.85,
    // ... other fields
};

broadcaster.broadcast_signal(update).await?;
```

---

## Port Reference

| Service | Type | Port | Purpose |
|---------|------|------|---------|
| Forward | gRPC | 50051 | gRPC API |
| Forward | REST | 8080 | REST API |
| Forward | WebSocket | 8081 | Real-time streaming |
| Forward | Metrics | 9090 | Prometheus metrics |
| Backward | HTTP | 8082 | Analytics API |
| Backward | Metrics | 9091 | Prometheus metrics |
| PostgreSQL | DB | 5432 | Database |
| Redis | Cache | 6379 | Job queue |

---

## Directory Structure

```
fks/src/janus/
├── services/
│   ├── forward/              # Real-time service
│   │   ├── src/
│   │   │   ├── api/         # REST/gRPC
│   │   │   ├── signal/      # Signal generation
│   │   │   ├── websocket/   # WebSocket streaming
│   │   │   ├── risk/        # Risk management
│   │   │   ├── lib.rs       # Service library
│   │   │   └── main.rs      # Entry point
│   │   └── Cargo.toml
│   │
│   └── backward/             # Historical service
│       ├── src/
│       │   ├── persistence/ # Database layer
│       │   ├── metrics/     # Metrics storage
│       │   ├── lib.rs       # Service library
│       │   └── main.rs      # Entry point
│       ├── migrations/      # SQL migrations
│       └── Cargo.toml
│
├── crates/                   # Shared libraries
│   ├── indicators/
│   ├── strategies/
│   ├── models/
│   └── ...
│
└── docs/                     # Documentation
    ├── QUICK_REFERENCE.md   # This file
    ├── SERVICE_MIGRATION.md
    ├── WEEK9_PROGRESS.md
    └── ...
```

---

## Troubleshooting

### Forward Service Won't Start

```bash
# Check if ports are available
netstat -an | grep -E "8080|8081|50051|9090"

# Check data service connection
curl http://localhost:8080/health  # Data service

# Check logs
RUST_LOG=debug cargo run
```

### Backward Service Database Issues

```bash
# Check PostgreSQL
psql -U postgres -d janus -c "SELECT 1"

# Reset database
sqlx database drop
sqlx database create
sqlx migrate run

# Check migrations
sqlx migrate info
```

### WebSocket Connection Issues

```bash
# Test WebSocket endpoint
wscat -c ws://localhost:8081/ws

# Check active connections
curl http://localhost:9090/metrics | grep janus_ws_connections_active

# Check logs for errors
docker-compose logs -f janus-forward | grep -i websocket
```

---

## Performance Tuning

### Forward Service

```bash
# Increase connection pool
FORWARD_MAX_CONNECTIONS=10000

# Adjust WebSocket settings
WS_CLIENT_TIMEOUT=120
WS_HEARTBEAT_INTERVAL=30
WS_MAX_MESSAGE_SIZE=2097152  # 2MB

# Enable compression
WS_ENABLE_COMPRESSION=true
```

### Backward Service

```bash
# Database connection pool
DB_MAX_CONNECTIONS=20
DB_MIN_CONNECTIONS=5

# Worker threads
BACKWARD_WORKERS=8

# Job queue
REDIS_URL=redis://redis-cluster:6379
```

---

## Metrics Reference

### Forward Service Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `janus_signals_generated_total` | Counter | Total signals generated |
| `janus_ws_connections_active` | Gauge | Active WebSocket connections |
| `janus_ws_messages_sent_total` | Counter | Total WebSocket messages sent |
| `janus_signal_broadcast_count` | Counter | Total signals broadcast |
| `janus_risk_alert_count` | Counter | Total risk alerts |
| `janus_ws_message_latency_seconds` | Histogram | Message latency |

### Backward Service Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `janus_db_connections_active` | Gauge | Active DB connections |
| `janus_signals_persisted_total` | Counter | Total signals persisted |
| `janus_analytics_queries_total` | Counter | Total analytics queries |
| `janus_job_queue_depth` | Gauge | Job queue depth |

---

## Testing

### Unit Tests

```bash
# Test forward service
cd services/forward
cargo test

# Test specific module
cargo test websocket::

# Test with output
cargo test -- --nocapture
```

### Integration Tests

```bash
# Start dependencies
docker-compose up -d postgres redis

# Run integration tests
cargo test --test integration

# Cleanup
docker-compose down
```

### Load Testing

```bash
# WebSocket connections (using autocannon or similar)
autocannon -c 1000 -d 60 ws://localhost:8081/ws

# API endpoints
ab -n 10000 -c 100 http://localhost:8080/health
```

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Port already in use | Change port in env vars or kill process |
| Database connection failed | Check PostgreSQL is running |
| WebSocket timeout | Adjust `WS_CLIENT_TIMEOUT` |
| High memory usage | Reduce `WS_MAX_CONNECTIONS` |
| Slow signal generation | Check ML model cache |
| Missing migrations | Run `sqlx migrate run` |

---

## Resources

- **Documentation**: `docs/`
- **Migration Guide**: `docs/SERVICE_MIGRATION.md`
- **WebSocket Guide**: `docs/WEBSOCKET_QUICKSTART.md`
- **Week 9 Progress**: `docs/WEEK9_PROGRESS.md`
- **Implementation Summary**: `docs/IMPLEMENTATION_COMPLETE.md`

---

## Support

For issues or questions:
1. Check service logs: `docker-compose logs -f [service]`
2. Review metrics dashboards
3. Enable debug logging: `RUST_LOG=debug`
4. Consult documentation in `docs/`

---

**Status**: Production Ready  
**Last Updated**: December 31, 2024