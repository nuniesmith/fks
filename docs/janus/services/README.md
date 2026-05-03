# Service Documentation

This directory contains comprehensive documentation for all microservices in the FKS platform.

## Services

### [Data Service](data-service/)
Real-time market data ingestion and storage service.

**Key Features:**
- Multi-exchange data ingestion (Binance, Coinbase, Kraken)
- QuestDB time-series storage
- Redis-based deduplication
- Prometheus metrics & health checks
- Sub-100ms ingestion latency

**Documentation:**
- [Complete Development Summary](data-service/DATA_SERVICE_COMPLETE.md)
- [QuestDB Production Optimization](data-service/questdb-production-optimization.md)
- [Capacity Planning Model](data-service/capacity-planning-model.md)
- [Multi-Region Architecture](data-service/multi-region-architecture.md)

### [CNS (Centralized Notification System)](cns/)
Centralized notification and alerting service.

**Key Features:**
- Multi-channel notifications (Slack, email, webhooks)
- Priority-based routing
- Rate limiting & throttling
- Notification templates

**Documentation:**
- [Architecture](cns/CNS_ARCHITECTURE.md)
- [Deployment Guide](cns/CNS_DEPLOYMENT.md)
- [Quick Start](cns/CNS_QUICKSTART.md)
- [Integration Checklist](cns/CNS_INTEGRATION_CHECKLIST.md)

### [Janus](../../src/janus/README.md)
Core trading intelligence and decision-making service with neuromorphic architecture.

**Key Features:**
- Adaptive neural trading algorithms
- Multi-phase decision making
- Real-time market analysis
- Gap detection & correction

**Documentation:** See `src/janus/` for detailed service documentation.

### [Execution Service](../../src/execution/README.md)
Order execution and management service.

**Key Features:**
- Smart order routing
- Multi-exchange execution
- Order lifecycle management
- Fill tracking & reconciliation

**Documentation:** See `src/execution/` for detailed service documentation.

### [Audit Service](../../src/audit/README.md)
LLM-powered code audit and documentation system.

**Key Features:**
- Automated code analysis
- Multi-LLM provider support (OpenAI, XAI)
- Janus framework integration
- Cost optimization

**Documentation:** See `src/audit/` for detailed service documentation.

## Service Architecture Patterns

### Common Patterns
All services follow these architectural patterns:

1. **Observability**
   - Prometheus metrics on `/metrics`
   - Health checks on `/health`
   - Structured logging

2. **Configuration**
   - Environment-based configuration
   - Secrets management via Vault (production)
   - Validation on startup

3. **Resilience**
   - Circuit breakers
   - Retry logic with backoff
   - Graceful degradation
   - Health checks

4. **API Design**
   - REST APIs for synchronous operations
   - WebSocket for real-time data
   - gRPC for inter-service communication (where applicable)

### Inter-Service Communication

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│   Janus     │────▶│    Data     │────▶│   QuestDB    │
│  (Trading)  │     │   Service   │     │ (Time-Series)│
└─────────────┘     └─────────────┘     └──────────────┘
      │                    │
      │                    ▼
      │             ┌─────────────┐
      │             │    Redis    │
      │             │(Dedup/Lock) │
      │             └─────────────┘
      ▼
┌─────────────┐
│  Execution  │
│   Service   │
└─────────────┘
      │
      ▼
┌─────────────┐     ┌─────────────┐
│     CNS     │────▶│   Slack/    │
│(Notifications)     │   Email     │
└─────────────┘     └─────────────┘
```

## Related Documentation

- [Architecture Overview](../architecture/README.md)
- [Operations Guides](../operations/README.md)
- [Deployment Guides](../operations/deployment/)
- [Runbooks](../runbooks/README.md)

## Quick Links

- [Main Documentation Index](../README.md)
- [Quick Start Guide](../guides/QUICKSTART.md)
- [Production Setup](../guides/HOME_PRODUCTION_SETUP.md)