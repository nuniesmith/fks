# Data Service Documentation

The Data Service is a high-performance real-time market data ingestion system that collects, normalizes, and stores cryptocurrency market data from multiple exchanges.

## Overview

The Data Service provides:
- Real-time data ingestion from multiple exchanges (Binance, Coinbase, Kraken)
- Sub-100ms ingestion latency (p99 < 85ms)
- 99.9% data completeness SLO
- Automatic deduplication using Redis
- Time-series storage in QuestDB
- Gap detection and recovery
- Comprehensive observability

## Documentation

### [Complete Development Summary](DATA_SERVICE_COMPLETE.md)
Comprehensive 8-week development journey from inception to production.

**Covers:**
- Week-by-week development milestones
- Architecture evolution
- Performance metrics
- Production deployment
- Lessons learned

### [QuestDB Production Optimization](questdb-production-optimization.md)
Detailed guide to optimizing QuestDB for production workloads.

**Topics:**
- WAL configuration tuning
- Commit lag optimization
- O3 max lag settings
- Partition management
- Query performance
- Resource utilization

### [Capacity Planning Model](capacity-planning-model.md)
Data-driven capacity planning for scaling the data service.

**Includes:**
- Throughput projections
- Resource requirements
- Scaling thresholds
- Cost modeling
- Growth planning

### [Multi-Region Architecture](multi-region-architecture.md)
Design for multi-region deployment and data replication.

**Covers:**
- Regional deployment patterns
- Data replication strategies
- Failover procedures
- Latency considerations
- Compliance requirements

## Architecture

```
┌─────────────────────────────────────────────┐
│         Exchange Adapters (WebSocket)       │
│  ┌─────────┐  ┌──────────┐  ┌────────┐    │
│  │ Binance │  │ Coinbase │  │ Kraken │    │
│  └────┬────┘  └─────┬────┘  └───┬────┘    │
└───────┼─────────────┼───────────┼──────────┘
        │             │           │
        └─────────────┼───────────┘
                      │
              ┌───────▼────────┐
              │  Data Service  │
              │   (Ingestion)  │
              └───────┬────────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
    ┌─────▼─────┐ ┌──▼──────┐ ┌──▼─────────┐
    │  QuestDB  │ │  Redis  │ │Prometheus  │
    │(Time-Series)│(Dedup)  │ │ (Metrics)  │
    └───────────┘ └─────────┘ └────────────┘
```

## Key Features

### Multi-Exchange Support
- **Binance**: Spot markets, WebSocket streaming
- **Coinbase**: Pro markets, WebSocket feed
- **Kraken**: Spot markets, WebSocket API
- Extensible adapter pattern for new exchanges

### High Performance
- Sub-100ms end-to-end latency (p99 < 85ms)
- 10,000+ messages/second sustained throughput
- Efficient batching and buffering
- Zero-copy deserialization where possible

### Reliability
- 99.9% data completeness SLO
- Automatic reconnection on connection loss
- Gap detection and backfill
- Circuit breakers for failing exchanges
- Health checks and liveness probes

### Observability
- Prometheus metrics on `/metrics`
- Health endpoint on `/health`
- Structured JSON logging
- Per-exchange metrics
- Latency histograms
- Error tracking

## Configuration

### Environment Variables

```bash
# Exchange API Keys (optional for public data)
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
COINBASE_API_KEY=your_key_here
COINBASE_API_SECRET=your_secret_here
KRAKEN_API_KEY=your_key_here
KRAKEN_API_SECRET=your_secret_here

# QuestDB Configuration
QUESTDB_HOST=questdb
QUESTDB_ILP_PORT=9009
QUESTDB_HTTP_PORT=9000

# Redis Configuration
REDIS_URL=redis://redis:6379
REDIS_KEY_PREFIX=fks:data:

# Service Configuration
DATA_SERVICE_PORT=8081
LOG_LEVEL=info
RUST_LOG=data_service=info

# Performance Tuning
BATCH_SIZE=100
BATCH_TIMEOUT_MS=50
MAX_CONCURRENT_EXCHANGES=10
```

### QuestDB Tuning

For production workloads, configure QuestDB with:
```properties
cairo.wal.enabled.default=true
cairo.max.uncommitted.rows=100000
line.tcp.maintenance.job.interval=100
cairo.commit.lag=5000
cairo.o3.max.lag=20000
```

See [QuestDB Production Optimization](questdb-production-optimization.md) for details.

## Metrics

### Key Metrics (Prometheus)

```
# Ingestion metrics
data_service_messages_received_total{exchange}
data_service_messages_processed_total{exchange}
data_service_messages_deduplicated_total{exchange}
data_service_messages_failed_total{exchange, reason}

# Latency metrics
data_service_ingestion_latency_seconds{exchange}
data_service_questdb_write_latency_seconds
data_service_redis_latency_seconds

# Health metrics
data_service_exchange_connected{exchange}
data_service_questdb_connected
data_service_redis_connected

# Data quality metrics
data_service_data_completeness_ratio{exchange}
data_service_gap_detection_total{exchange}
data_service_backfill_success_total{exchange}
```

### Grafana Dashboards

Available in `config/monitor/grafana/dashboards/`:
- `data-service-overview.json` - Service overview
- `data-service-per-exchange.json` - Per-exchange metrics
- `slo-dashboard.json` - SLO/SLI tracking
- `questdb-performance.json` - QuestDB metrics

## Performance

### Production Metrics (Week 8+)

| Metric | Target | Actual |
|--------|--------|--------|
| Ingestion Latency (p50) | < 20ms | 15ms |
| Ingestion Latency (p95) | < 50ms | 45ms |
| Ingestion Latency (p99) | < 100ms | 85ms |
| Data Completeness | > 99.9% | 99.95% |
| Uptime | > 99.9% | 99.98% |
| Error Rate | < 0.1% | 0.03% |

### Resource Utilization

| Resource | Development | Production |
|----------|-------------|------------|
| CPU | 5-10% | 15-25% |
| Memory | 512MB | 1-2GB |
| Network | 1-2 Mbps | 5-10 Mbps |
| Disk (QuestDB) | ~100MB/day | ~1GB/day |

## Deployment

### Docker Compose (Development)

```bash
docker-compose up -d data-service questdb redis
```

### Docker Compose (Production)

```bash
./scripts/deploy-home-production.sh
```

### Kubernetes

```bash
kubectl apply -f deployment/kubernetes/data-service/
```

See [Operations Deployment Guide](../../operations/deployment/PRODUCTION_DEPLOYMENT.md) for details.

## Development

### Building

```bash
# Debug build
cargo build -p data-service

# Release build
cargo build -p data-service --release

# With all features
cargo build -p data-service --all-features
```

### Running Locally

```bash
# Start dependencies
docker-compose up -d questdb redis

# Run data service
cargo run -p data-service

# Or with environment file
cargo run -p data-service -- --env-file .env.development
```

### Testing

```bash
# Unit tests
cargo test -p data-service

# Integration tests (requires QuestDB and Redis)
cargo test -p data-service --test integration_tests

# End-to-end tests
./scripts/test-data-service-e2e.sh
```

### Adding a New Exchange

1. Create adapter in `src/data/src/exchanges/`
2. Implement `ExchangeAdapter` trait
3. Add exchange configuration
4. Register in exchange factory
5. Add metrics and logging
6. Write tests
7. Update documentation

Example:
```rust
pub struct NewExchangeAdapter {
    client: WebSocketClient,
    config: ExchangeConfig,
}

#[async_trait]
impl ExchangeAdapter for NewExchangeAdapter {
    async fn connect(&mut self) -> Result<()> {
        // WebSocket connection logic
    }

    async fn subscribe(&mut self, symbols: Vec<String>) -> Result<()> {
        // Subscription logic
    }

    async fn next_message(&mut self) -> Result<MarketData> {
        // Message parsing logic
    }
}
```

## Troubleshooting

### Data Not Ingesting

1. Check exchange connectivity:
   ```bash
   curl http://localhost:8081/health
   ```

2. Verify QuestDB is running:
   ```bash
   curl http://localhost:9000/
   ```

3. Check Redis connectivity:
   ```bash
   redis-cli ping
   ```

4. Review logs:
   ```bash
   docker-compose logs -f data-service
   ```

### High Latency

1. Check QuestDB WAL settings (see optimization guide)
2. Review batch size and timeout configuration
3. Verify network latency to exchanges
4. Check CPU and memory utilization
5. Review Prometheus metrics for bottlenecks

### Data Gaps Detected

1. Check exchange connection status
2. Review circuit breaker state
3. Verify backfill is enabled
4. Check for rate limiting
5. Review gap detection logs

### Memory Issues

1. Review batch size settings
2. Check for memory leaks (use valgrind/heaptrack)
3. Verify QuestDB connection pool size
4. Review Redis connection settings
5. Enable memory profiling

## Monitoring & Alerts

### Critical Alerts

- **Exchange Disconnection**: Exchange connection lost > 1 minute
- **High Latency**: p95 latency > 100ms for 5 minutes
- **Low Completeness**: Data completeness < 99% for 10 minutes
- **High Error Rate**: Error rate > 1% for 5 minutes

### Warning Alerts

- **Elevated Latency**: p95 latency > 50ms for 10 minutes
- **Connection Flapping**: > 5 reconnections in 10 minutes
- **Gap Detection**: > 10 gaps detected in 1 hour

See [Runbooks](../../runbooks/README.md) for incident response procedures.

## Related Documentation

- [Main Documentation Index](../../README.md)
- [Service Documentation](../README.md)
- [Operations Guides](../../operations/README.md)
- [Runbooks](../../runbooks/README.md)
- [Architecture Documentation](../../architecture/README.md)

## Contributing

When updating Data Service documentation:
1. Keep performance metrics current
2. Update configuration examples
3. Test all code examples
4. Add troubleshooting entries for new issues
5. Update metrics documentation for new metrics
6. Keep architecture diagrams in sync with code

## Status

**Current Version**: 1.0  
**Status**: Production (Week 11+)  
**Deployment**: Home Production + Staging  
**Supported Exchanges**: Binance, Coinbase, Kraken  
**SLO Achievement**: 99.95% (Target: 99.9%)

## Future Enhancements

- [ ] Additional exchange adapters (Bybit, OKX)
- [ ] Level 2 order book data
- [ ] Trade execution data correlation
- [ ] Multi-region deployment
- [ ] Kafka streaming integration
- [ ] Machine learning feature extraction