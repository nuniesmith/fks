# FKS Multi-Repo Microservices Architecture

## Overview

The FKS Trading Platform uses a **microservices architecture** with a **monorepo-as-master** approach:

- **Main FKS Repo**: Master orchestrator containing shared infrastructure, monitoring, and core services
- **Satellite Repos**: Independent microservices for specialized functionality (api, data, execution, ninja, web)

## Repository Structure

```
/mnt/c/Users/jordan/Nextcloud/code/repos/
├── fks/                          # Main master repo (THIS REPO)
│   ├── src/
│   │   ├── authentication/       # Auth system (API keys, sessions, rate limiting)
│   │   ├── core/                 # Core models (Trade, Position, Account)
│   │   ├── trading/              # Trading strategies, signals, backtesting
│   │   ├── web/                  # Django web UI (Bootstrap 5)
│   │   ├── api/                  # REST API routes (FastAPI - being migrated)
│   │   └── monitor/              # ✅ Service monitoring & health checks (NEW)
│   ├── repo/                     # Git submodules for satellite services
│   │   ├── api/                  # → fks-api repo
│   │   ├── data/                 # → fks-data repo
│   │   ├── execution/            # → fks-execution repo
│   │   ├── ninja/                # → fks-ninja repo
│   │   └── web/                  # → fks-web-ui repo
│   ├── docker-compose.yml        # Orchestrates all services
│   ├── docker-compose.gpu.yml    # Adds GPU stack (RAG, Ollama)
│   └── Makefile                  # Commands for all repos
│
├── fks-api/                      # Satellite: API Gateway
├── fks-data/                     # Satellite: Data ingestion (Binance, etc.)
├── fks-execution/                # Satellite: Trade execution engine
├── fks-ninja/                    # Satellite: NinjaTrader integration
└── fks-web-ui/                   # Satellite: Alternative web UI (React/Vue?)
```

## Service Architecture

### **FKS Main (Monitor & Orchestrator)**
- **Role**: Master service registry, health check aggregator, dashboard
- **Port**: 8000 (Django + Gunicorn)
- **Health**: `http://localhost:8000/monitor/api/ping/`
- **Dashboard**: `http://localhost:8000/monitor/`

### **Satellite Services**

#### 1. **fks-api** (API Gateway)
- **Role**: External API gateway for third-party integrations
- **Port**: 8001
- **Health**: `http://fks_api:8001/api/health`
- **Tech Stack**: FastAPI, Pydantic, httpx
- **Dependencies**: fks_main (auth), fks_data (market data)

#### 2. **fks-data** (Data Ingestion)
- **Role**: Market data sync from exchanges (Binance, others)
- **Port**: 8002
- **Health**: `http://fks_data:8002/health`
- **Tech Stack**: FastAPI, ccxt, TimescaleDB
- **Dependencies**: fks_main (DB), redis (caching)

#### 3. **fks-execution** (Trade Execution)
- **Role**: Execute trades, manage positions, risk checks
- **Port**: 8003
- **Health**: `http://fks_execution:8003/health`
- **Tech Stack**: FastAPI, Celery, PostgreSQL
- **Dependencies**: fks_data (prices), fks_main (strategies)

#### 4. **fks-ninja** (NinjaTrader Integration)
- **Role**: Bridge to NinjaTrader for futures trading
- **Port**: 8004
- **Health**: `http://fks_ninja:8004/health`
- **Tech Stack**: C# .NET service or Python bridge
- **Dependencies**: fks_execution (orders), fks_data (symbols)

#### 5. **fks-web-ui** (Alternative Web UI)
- **Role**: Modern SPA UI (React/Vue) as alternative to Django templates
- **Port**: 3000
- **Health**: `http://fks_web:3000/health`
- **Tech Stack**: React/Vue, Vite, Tailwind CSS
- **Dependencies**: fks_main (auth), fks-api (data)

## Inter-Service Communication

### **Health Check Protocol**

All services implement a **standard health endpoint**:

```json
GET /health

Response:
{
  "status": "healthy" | "degraded" | "down",
  "service": "service_name",
  "version": "1.0.0",
  "timestamp": "2025-10-23T22:00:00Z",
  "dependencies": {
    "database": "healthy",
    "redis": "healthy",
    "external_api": "degraded"
  },
  "metadata": {
    "uptime_seconds": 3600,
    "requests_per_minute": 42
  }
}
```

### **Service Discovery**

Services register themselves with the **FKS Monitor** on startup:

```bash
# Each service sends a POST to monitor on startup
POST http://fks_main:8000/monitor/api/discover/
{
  "name": "fks_data",
  "service_type": "data",
  "host": "fks_data",
  "port": 8002,
  "health_endpoint": "/health",
  "version": "1.0.0"
}
```

### **Automated Health Checks**

The **FKS Monitor** runs periodic health checks via Celery Beat:

```python
# Celery Beat Schedule (every 2 minutes)
@shared_task(name="monitor.check_all_services")
def check_all_services_task():
    with HealthCheckService() as checker:
        results = checker.check_all_services()
    # Results logged to database and Discord notifications sent on failures
```

## Docker Networking

All services run on a **shared Docker network** (`fks_network`):

```yaml
networks:
  fks_network:
    driver: bridge
```

Services communicate using Docker DNS:
- `fks_main` → Main Django app
- `fks_api` → API Gateway
- `fks_data` → Data service
- `fks_execution` → Execution engine
- `fks_ninja` → NinjaTrader bridge
- `fks_web` → Alternative web UI

## Setup Instructions

### **1. Clone All Repos (First Time Setup)**

```bash
cd /mnt/c/Users/jordan/Nextcloud/code/repos/

# Clone satellite repos
git clone https://github.com/nuniesmith/fks-api.git
git clone https://github.com/nuniesmith/fks-data.git
git clone https://github.com/nuniesmith/fks-execution.git
git clone https://github.com/nuniesmith/fks-ninja.git
git clone https://github.com/nuniesmith/fks-web-ui.git

# Add as submodules to main FKS repo
cd fks/
git submodule add ../fks-api repo/api
git submodule add ../fks-data repo/data
git submodule add ../fks-execution repo/execution
git submodule add ../fks-ninja repo/ninja
git submodule add ../fks-web-ui repo/web

git commit -m "feat: Add microservices as Git submodules"
```

### **2. Initialize Submodules (Existing Clones)**

```bash
cd /mnt/c/Users/jordan/Nextcloud/code/repos/fks/
git submodule update --init --recursive
```

### **3. Start All Services**

```bash
make multi-up        # Start all microservices
make multi-logs      # Follow logs from all services
make multi-down      # Stop all services
```

### **4. Register Services with Monitor**

```bash
# Automatically run on first startup via Django management command
docker-compose exec web python manage.py register_services
```

### **5. View Monitoring Dashboard**

```
http://localhost:8000/monitor/
```

## Development Workflow

### **Working on a Satellite Service**

```bash
# 1. Navigate to the service repo
cd repo/data/  # or repo/api/, repo/execution/, etc.

# 2. Make changes
# ... edit files ...

# 3. Test locally
docker-compose -f ../../docker-compose.yml up fks_data

# 4. Commit to satellite repo
git add .
git commit -m "feat: Add new feature"
git push origin main

# 5. Update submodule pointer in main FKS repo
cd ../../  # Back to fks/
git add repo/data
git commit -m "chore: Update fks-data submodule"
git push origin main
```

### **Updating Submodules**

```bash
# Update all submodules to latest commits
git submodule update --remote

# Or update a specific submodule
git submodule update --remote repo/data

# Commit the updated pointers
git add repo/
git commit -m "chore: Update submodules"
```

## Makefile Commands

```bash
make multi-up              # Start all microservices
make multi-down            # Stop all services
make multi-logs            # Follow logs from all services
make multi-build           # Build all Docker images
make multi-update          # Update all submodules
make monitor-dashboard     # Open monitoring dashboard in browser
make health-check          # Run health check on all services
```

## API Endpoints

### **Monitor Service APIs**

```
GET  /monitor/                          # Monitoring dashboard (UI)
GET  /monitor/api/health/               # Check all services
GET  /monitor/api/health/<id>/          # Check specific service
GET  /monitor/api/registry/             # List all registered services
POST /monitor/api/discover/             # Register default services
GET  /monitor/api/ping/                 # Ping monitor service
```

## Database Models

### **ServiceRegistry**
- Tracks all microservices (name, host, port, status)
- Auto-updated by health checks

### **HealthCheck**
- Records every health check ping
- Tracks response time, success rate, errors

### **ServiceDependency**
- Maps service dependencies (e.g., execution depends on data)
- Flags critical vs optional dependencies

### **ServiceMetric**
- Time-series metrics (CPU, memory, requests, latency)
- Used for Prometheus/Grafana integration

## Monitoring & Alerts

### **Discord Notifications**

Health check failures automatically send Discord alerts:

```
❌ **Service Down Alert**
Service: fks_data
Status: Down
Error: Connection timeout
Last Seen: 2 minutes ago
```

### **Grafana Integration**

Metrics exported to Prometheus → visualized in Grafana:
- Service uptime %
- Average response times
- Request rates
- Error rates

Dashboard: `http://localhost:3000` (admin/admin)

## Next Steps

1. ✅ **Monitor service created** in main FKS repo
2. ⏳ **Create satellite repos** (fks-api, fks-data, etc.)
3. ⏳ **Update docker-compose.yml** with all service definitions
4. ⏳ **Add Makefile commands** for multi-repo operations
5. ⏳ **Create dashboard template** for monitoring UI
6. ⏳ **Set up Celery Beat** for automated health checks
7. ⏳ **Configure Discord webhooks** for alerts

---

**Last Updated**: October 23, 2025  
**Status**: Monitoring service implemented, satellite repos pending
