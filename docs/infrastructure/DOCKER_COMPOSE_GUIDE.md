# Docker Compose Configuration Guide

This guide explains the three-tier Docker Compose configuration for the FKS trading system.

## 📋 Table of Contents

- [Overview](#overview)
- [Configuration Files](#configuration-files)
- [Quick Start](#quick-start)
- [Environment Setup](#environment-setup)
- [Service Architecture](#service-architecture)
- [Usage Scenarios](#usage-scenarios)
- [Monitoring & Debugging](#monitoring--debugging)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)

## 🎯 Overview

The FKS system uses a three-tier Docker Compose configuration:

1. **`docker-compose.yml`** - Base production-ready configuration
2. **`docker-compose.override.yml`** - Development overrides (auto-loaded)
3. **`docker-compose.prod.yml`** - Production overrides (explicit)

This approach provides:
- ✅ **Security by default** - Production-grade security settings
- ✅ **Developer-friendly** - Hot reload and debugging enabled locally
- ✅ **Environment parity** - Same base config for dev and prod
- ✅ **Easy deployment** - Single command for each environment

## 📁 Configuration Files

### `docker-compose.yml` (Base Configuration)

**Purpose**: Production-ready foundation for all environments

**Features**:
- Security hardening (user isolation, capability dropping, read-only where possible)
- Resource limits and reservations
- Health checks for all services
- Structured logging with rotation
- Proper dependency management
- Network isolation

**When to modify**: Only for changes that affect both dev and prod

### `docker-compose.override.yml` (Development)

**Purpose**: Local development optimizations

**Features**:
- Hot code reload for Rust and Python
- Debug logging enabled
- Source code volume mounts
- Exposed ports for debugging
- Relaxed resource limits
- Development tools (Redis Commander, pgAdmin)

**Auto-loaded**: Yes, by default with `docker compose up`

### `docker-compose.prod.yml` (Production)

**Purpose**: Production deployment hardening

**Features**:
- Read-only filesystems
- External image registry
- Secrets management
- Multiple replicas (gateway)
- Strict resource limits
- Compressed logging
- No debug ports exposed

**Explicitly loaded**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up`

## 🚀 Quick Start

### Development Environment

```bash
# 1. Clone and navigate to project
cd fks

# 2. Copy environment template
cp .env.example .env

# 3. Edit environment variables
nano .env

# 4. Start all services (auto-loads override file)
docker compose up -d

# 5. View logs
docker compose logs -f

# 6. Check service health
docker compose ps
```

### Production Environment

```bash
# 1. Set production environment variables
export TRADING_MODE=live
export REAL_ORDERS_ENABLED=true
export BYBIT_API_KEY=your_key
export BYBIT_API_SECRET=your_secret
export REDIS_PASSWORD=$(openssl rand -base64 32)
export QUESTDB_PASSWORD=$(openssl rand -base64 32)
export GRAFANA_PASSWORD=$(openssl rand -base64 32)

# 2. Build production images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 3. Deploy with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Verify deployment
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

## 🔧 Environment Setup

### Required Environment Variables

Create a `.env` file in the project root:

```bash
# ============================================================================
# FKS Trading System Environment Configuration
# ============================================================================

# Trading Configuration
TRADING_MODE=paper                    # paper | live
REAL_ORDERS_ENABLED=false            # false | true
BYBIT_TESTNET=true                   # true | false

# Bybit API Credentials
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# Redis Configuration
REDIS_PASSWORD=your_redis_password

# QuestDB Configuration
QUESTDB_PASSWORD=your_questdb_password

# Grafana Configuration
GRAFANA_USER=admin
GRAFANA_PASSWORD=your_grafana_password
GRAFANA_ROOT_URL=https://grafana.fkstrading.xyz

# Audit Service (LLM Integration)
AUDIT_LLM_ENABLED=true
XAI_API_KEY=your_xai_api_key
AUDIT_LLM_MODEL=grok-beta

# Docker Registry (Production)
REGISTRY=docker.io
TAG=latest

# Monitoring
MONITOR_LOG_LEVEL=info
AUDIT_LOG_LEVEL=info
```

### Development Environment Template

```bash
# Development optimized settings
TRADING_MODE=paper
REAL_ORDERS_ENABLED=false
BYBIT_TESTNET=true
BYBIT_API_KEY=test_key
BYBIT_API_SECRET=test_secret
REDIS_PASSWORD=devpassword
QUESTDB_PASSWORD=devpassword
GRAFANA_PASSWORD=admin
AUDIT_LLM_ENABLED=false
```

### Production Environment Template

```bash
# Production settings - USE STRONG PASSWORDS!
TRADING_MODE=live
REAL_ORDERS_ENABLED=true
BYBIT_TESTNET=false
BYBIT_API_KEY=${YOUR_PRODUCTION_API_KEY}
BYBIT_API_SECRET=${YOUR_PRODUCTION_API_SECRET}
REDIS_PASSWORD=$(openssl rand -base64 32)
QUESTDB_PASSWORD=$(openssl rand -base64 32)
GRAFANA_PASSWORD=$(openssl rand -base64 32)
GRAFANA_ROOT_URL=https://grafana.yourdomain.com
REGISTRY=docker.io
TAG=v1.0.0
```

## 🏗️ Service Architecture

### Core Trading Services

| Service | Port(s) | Purpose | Dependencies |
|---------|---------|---------|--------------|
| **forward** | 50051 (gRPC), 9100 (metrics) | Real-time execution engine | Redis, QuestDB |
| **backward** | 7000 (gRPC), 9200 (metrics) | Historical data & backtesting | QuestDB |
| **data-factory** | - | Market data ingestion | Redis, QuestDB |
| **gateway** | 8001 (HTTP) | API orchestration | Forward, Backward, Redis, QuestDB |
| **cns** | 9091 (HTTP) | Health monitoring | Redis |
| **audit** | 8080 (HTTP) | Code analysis & security | - |

### Infrastructure Services

| Service | Port(s) | Purpose | Data Volume |
|---------|---------|---------|-------------|
| **redis** | 6379 | Pub/Sub coordination | `redis_data` |
| **questdb** | 9000 (HTTP), 9009 (ILP), 8812 (PG) | Time-series database | `questdb_data` |
| **prometheus** | 9090 | Metrics collection | `prometheus_data` |
| **grafana** | 3001 | Visualization | `grafana_data` |
| **alertmanager** | 9093 | Alert routing | `alertmanager_data` |
| **jaeger** | 16686 (UI), 14268 (collector) | Distributed tracing | - |
| **nginx** | 80, 443 | Reverse proxy | - |

### Service Dependencies

```
nginx (reverse proxy)
  ├─→ gateway (API)
  │     ├─→ forward (execution)
  │     │     ├─→ redis
  │     │     └─→ questdb
  │     ├─→ backward (backtesting)
  │     │     └─→ questdb
  │     └─→ redis
  ├─→ audit (code analysis)
  ├─→ grafana (monitoring UI)
  │     └─→ prometheus
  │           ├─→ forward (metrics)
  │           ├─→ backward (metrics)
  │           ├─→ data-factory (metrics)
  │           ├─→ gateway (metrics)
  │           └─→ cns (metrics)
  └─→ cns (health monitoring)
        └─→ redis

data-factory (ingestion)
  ├─→ redis
  └─→ questdb
```

## 📚 Usage Scenarios

### Scenario 1: Local Development

```bash
# Start with hot reload enabled
docker compose up -d

# Tail logs for specific service
docker compose logs -f gateway

# Restart a service after code changes (if needed)
docker compose restart gateway

# Access services
# - Gateway API: http://localhost:8001
# - Audit UI: http://localhost:8080
# - Grafana: http://localhost:3001
# - Prometheus: http://localhost:9090
```

### Scenario 2: Integration Testing

```bash
# Start without override (pure base config)
docker compose -f docker-compose.yml up -d

# Run integration tests
cd src/janus && cargo test --test integration

# Cleanup
docker compose -f docker-compose.yml down -v
```

### Scenario 3: Production Deployment

```bash
# Build production images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Tag and push to registry
docker tag fks-forward:latest docker.io/nuniesmith/fks-forward:v1.0.0
docker push docker.io/nuniesmith/fks-forward:v1.0.0

# Deploy on production server
export TAG=v1.0.0
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Watch deployment
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
```

### Scenario 4: Rolling Update

```bash
# Build new version
docker compose -f docker-compose.yml -f docker-compose.prod.yml build gateway

# Update with zero downtime (requires deploy.update_config)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps gateway

# Verify new version
docker compose ps gateway
docker compose logs gateway | tail -20
```

### Scenario 5: Debugging a Service

```bash
# Development: Connect to running container
docker compose exec forward /bin/sh

# View real-time logs with timestamps
docker compose logs -f --timestamps forward

# Follow specific log pattern
docker compose logs -f forward | grep ERROR

# Enable trace logging
docker compose exec forward sh -c 'export RUST_LOG=trace && pkill -USR1 janus-forward'
```

## 📊 Monitoring & Debugging

### Health Checks

```bash
# Check all service health
docker compose ps

# Watch health status
watch -n 2 'docker compose ps'

# Inspect specific service health
docker inspect fks_forward --format='{{json .State.Health}}' | jq

# View health check logs
docker inspect fks_forward --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f gateway

# Last 100 lines
docker compose logs --tail=100 forward

# Since timestamp
docker compose logs --since 2024-01-01T00:00:00 forward

# JSON format for parsing
docker compose logs --json forward | jq -r '.log'
```

### Metrics

Access Prometheus metrics:
- **Prometheus UI**: http://localhost:9090
- **Forward metrics**: http://localhost:9100/metrics
- **Backward metrics**: http://localhost:9200/metrics
- **CNS metrics**: http://localhost:9091/metrics

### Tracing

Access Jaeger UI:
- **Jaeger UI**: http://localhost:16686
- Search for traces by service name
- Analyze latency bottlenecks

## 🔒 Security Considerations

### Security Features Enabled

1. **User Isolation**: All services run as non-root users
2. **Capability Dropping**: Minimal Linux capabilities
3. **Read-Only Filesystems**: Where possible (production)
4. **No New Privileges**: Prevents privilege escalation
5. **Network Isolation**: Services on private network
6. **Secrets Management**: Via environment variables or Docker secrets
7. **Resource Limits**: Prevent DoS via resource exhaustion

### Security Checklist

- [ ] Change all default passwords in `.env`
- [ ] Use strong passwords (32+ characters)
- [ ] Enable TLS/SSL for nginx
- [ ] Rotate API keys regularly
- [ ] Review and update security policies monthly
- [ ] Enable audit logging for all services
- [ ] Restrict network access (firewall rules)
- [ ] Use Docker secrets for production
- [ ] Regular security updates (`docker compose pull`)

### Secrets Management (Production)

```bash
# Create Docker secrets
echo "your_redis_password" | docker secret create redis_password -
echo "your_questdb_password" | docker secret create questdb_password -

# Update docker-compose.prod.yml to use secrets
secrets:
  redis_password:
    external: true

# Reference in service
services:
  redis:
    secrets:
      - redis_password
```

## 🔧 Troubleshooting

### Common Issues

#### Issue: Service won't start

```bash
# Check logs
docker compose logs service-name

# Check dependencies
docker compose ps

# Verify network
docker network inspect fks_network

# Restart with clean state
docker compose down -v
docker compose up -d
```

#### Issue: Port already in use

```bash
# Find process using port
sudo lsof -i :8001

# Change port in docker-compose.override.yml
ports:
  - "8002:8000"  # Use different host port
```

#### Issue: Out of memory

```bash
# Check resource usage
docker stats

# Increase service limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4g

# Or add swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### Issue: Database connection refused

```bash
# Verify service is healthy
docker compose ps questdb

# Check network connectivity
docker compose exec gateway ping questdb

# Verify credentials
docker compose exec questdb env | grep PASSWORD
```

#### Issue: Permission denied on volumes

```bash
# Check volume ownership
docker compose exec forward ls -la /app/data

# Fix permissions
sudo chown -R 1000:1000 ./data

# Or set user in docker-compose.yml
user: "${UID}:${GID}"
```

### Debug Mode

```bash
# Enable debug logging for all services
export RUST_LOG=debug
docker compose up -d

# Or per-service in docker-compose.override.yml
environment:
  - RUST_LOG=trace,service_name=trace
```

### Network Debugging

```bash
# Inspect network
docker network inspect fks_network

# Test connectivity between services
docker compose exec forward ping -c 3 redis

# Check DNS resolution
docker compose exec forward nslookup questdb

# Monitor network traffic
docker compose exec forward tcpdump -i any -n port 6379
```

## ⚡ Performance Tuning

### Resource Allocation

Adjust based on your hardware:

```yaml
# High-performance server (32GB RAM, 16 cores)
forward:
  deploy:
    resources:
      limits:
        cpus: "8.0"
        memory: 8g
      reservations:
        cpus: "4.0"
        memory: 4g

# Low-resource server (8GB RAM, 4 cores)
forward:
  deploy:
    resources:
      limits:
        cpus: "2.0"
        memory: 2g
      reservations:
        cpus: "1.0"
        memory: 1g
```

### Database Optimization

**QuestDB**:
```yaml
environment:
  - QDB_CAIRO_COMMIT_LAG=500  # Lower = more frequent commits
  - QDB_SHARED_WORKER_COUNT=4  # Match CPU cores
```

**Redis**:
```yaml
command: >
  redis-server
  --maxmemory 2gb
  --maxmemory-policy allkeys-lru
  --save 900 1
  --appendonly yes
```

### Network Performance

```bash
# Increase network buffer sizes
sysctl -w net.core.rmem_max=16777216
sysctl -w net.core.wmem_max=16777216

# Enable TCP BBR congestion control
sysctl -w net.ipv4.tcp_congestion_control=bbr
```

## 📖 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Production Deployment Guide](../deployment/PRODUCTION.md)
- [Monitoring Setup Guide](../monitoring/SETUP.md)

## 🆘 Getting Help

If you encounter issues:

1. Check this guide first
2. Review service logs: `docker compose logs -f service-name`
3. Check GitHub Issues: https://github.com/nuniesmith/fks/issues
4. Ask in Discord: [FKS Community](https://discord.gg/fks)

---

**Last Updated**: 2024-12-31  
**Maintainer**: nuniesmith