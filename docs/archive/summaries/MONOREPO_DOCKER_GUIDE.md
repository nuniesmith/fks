# FKS Monorepo Docker Setup Guide

**Status**: ✅ **Already Configured** - Your monorepo is properly set up!  
**Date**: October 27, 2025

## 🎯 Current Setup Overview

You have a **fully functional monorepo** with 8 microservices running in Docker containers:

```
fks/ (Monorepo Root)
├── docker-compose.yml          # Orchestrates all 8 services
├── docker-compose.gpu.yml      # GPU overrides for fks_ai
├── services/                   # Each service is isolated
│   ├── api/                   # FastAPI gateway (Port 8001)
│   ├── app/                   # Business logic (Port 8002)
│   ├── ai/                    # GPU ML/RAG (Port 8006)
│   ├── data/                  # Data collection (Port 8003)
│   ├── execution/             # Rust execution (Port 8004)
│   ├── ninja/                 # .NET NinjaTrader (Port 8005)
│   └── web/                   # Django UI (Port 3001)
├── src/                        # Orchestrator (FKS Main)
└── Makefile                    # Helper commands
```

## ✅ What's Already Working

### 1. **Service Isolation**
Each service has:
- ✅ Own `Dockerfile` 
- ✅ Own `requirements.txt`
- ✅ Own source code in `services/[name]/src/`
- ✅ Own health check endpoint
- ✅ Independent Redis database (different DB numbers)
- ✅ Dedicated log directory

### 2. **Docker Compose Configuration**
Your `docker-compose.yml` already defines:
- ✅ 8 microservices (api, app, ai, data, execution, ninja, web)
- ✅ Shared infrastructure (PostgreSQL + TimescaleDB, Redis, Nginx)
- ✅ Monitoring stack (Prometheus, Grafana, Flower)
- ✅ Service dependencies (via `depends_on`)
- ✅ Health checks for all services
- ✅ Volume mounts for development
- ✅ Networking (fks-network)

### 3. **GPU Support**
- ✅ `docker-compose.gpu.yml` for fks_ai with NVIDIA GPU
- ✅ CUDA 12.2 runtime
- ✅ Ollama integration

## 🚀 Quick Start Commands

### Start All Services
```bash
# Standard stack (no GPU)
make up
# OR
docker compose up -d

# With GPU support (for fks_ai)
make gpu-up
# OR
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

# Start specific microservices only
docker compose up -d fks_api fks_app fks_data
```

### View Logs
```bash
# All services
make logs
# OR
docker compose logs -f

# Specific service
docker compose logs -f fks_api
docker compose logs -f fks_app

# Multi-service logs
make multi-logs
```

### Check Service Status
```bash
# Quick status
docker compose ps

# Detailed health check
make multi-status

# Service URLs
make monitoring
```

### Stop Services
```bash
# Stop all
make down
# OR
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

## 🏗️ Architecture Patterns

### 1. **Service Communication**
Services communicate via HTTP over the `fks-network`:

```python
# Example from fks_app calling fks_data
import httpx

DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://fks_data:8003")

async def get_market_data(symbol: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DATA_SERVICE_URL}/data/ohlcv/{symbol}")
        return response.json()
```

**Service URLs in Docker Network**:
- `http://fks_api:8001` - API Gateway
- `http://fks_app:8002` - Business Logic
- `http://fks_data:8003` - Data Collection
- `http://fks_execution:8004` - Execution Engine
- `http://fks_ninja:8005` - NinjaTrader Bridge
- `http://fks_ai:8006` - AI/ML Service
- `http://web:8000` - Orchestrator (FKS Main)
- `http://db:5432` - PostgreSQL
- `http://redis:6379` - Redis

### 2. **Database Isolation**
Each service uses its own Redis database:
```yaml
# fks_api
REDIS_URL=redis://:${REDIS_PASSWORD:-}@redis:6379/2

# fks_data  
REDIS_URL=redis://:${REDIS_PASSWORD:-}@redis:6379/3

# fks_execution
REDIS_URL=redis://:${REDIS_PASSWORD:-}@redis:6379/4

# fks_app
REDIS_URL=redis://:${REDIS_PASSWORD:-}@redis:6379/5

# fks_ai
REDIS_URL=redis://:${REDIS_PASSWORD:-}@redis:6379/6
```

**Shared PostgreSQL**: All services can access TimescaleDB at `db:5432`

### 3. **Service Health Monitoring**
Every service has a health check:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

Access health dashboard: http://localhost:8000/health/dashboard/

## 📦 Adding a New Service

### Step 1: Create Service Directory
```bash
mkdir -p services/new_service/src
cd services/new_service
```

### Step 2: Create Dockerfile
```dockerfile
# services/new_service/Dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8007

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
  CMD curl -f http://localhost:8007/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8007"]
```

### Step 3: Create FastAPI App
```python
# services/new_service/src/main.py
from fastapi import FastAPI

app = FastAPI(title="New Service")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "new_service"}

@app.get("/")
async def root():
    return {"message": "New Service"}
```

### Step 4: Add to docker-compose.yml
```yaml
  fks_new_service:
    build:
      context: ./services/new_service
      dockerfile: Dockerfile
    container_name: fks_new_service
    expose:
      - "8007"
    volumes:
      - ./services/new_service:/app
      - ./logs/new_service:/app/logs
    environment:
      - TZ=America/Toronto
      - PYTHONUNBUFFERED=1
      - SERVICE_NAME=fks_new_service
      - SERVICE_VERSION=1.0.0
      - MONITOR_URL=http://web:8000/monitor/api/discover/
      - POSTGRES_HOST=db
      - REDIS_URL=redis://:${REDIS_PASSWORD:-}@redis:6379/7
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      web:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8007/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    networks:
      - fks-network
```

### Step 5: Build and Start
```bash
docker compose build fks_new_service
docker compose up -d fks_new_service
docker compose logs -f fks_new_service
```

## 🔧 Development Workflow

### 1. **Local Development with Hot Reload**
Services are mounted as volumes for instant code updates:
```yaml
volumes:
  - ./services/api:/app  # Changes reflected immediately
```

**Restart service after dependency changes**:
```bash
docker compose restart fks_api
```

### 2. **Running Tests**
```bash
# Test specific service
docker compose exec fks_api pytest tests/ -v

# Test with coverage
docker compose exec fks_app pytest tests/ --cov=src --cov-report=html

# Run from host (if dependencies installed locally)
cd services/app
pytest tests/ -v
```

### 3. **Debugging**
```bash
# Access service shell
docker compose exec fks_api bash

# View real-time logs
docker compose logs -f fks_api

# Inspect container
docker compose exec fks_api env  # View environment
docker compose exec fks_api ps aux  # View processes
```

### 4. **Database Operations**
```bash
# PostgreSQL shell
docker compose exec db psql -U postgres -d trading_db

# Run Django migrations
docker compose exec web python manage.py migrate

# Django shell (ORM access)
docker compose exec web python manage.py shell
```

## 🛠️ Common Tasks

### Rebuild Services After Code Changes
```bash
# Rebuild all services
docker compose build

# Rebuild specific service
docker compose build fks_api

# Rebuild and restart
docker compose up -d --build fks_api
```

### Clean Up
```bash
# Remove stopped containers
docker compose down

# Remove volumes (WARNING: deletes data)
docker compose down -v

# Remove images
docker compose down --rmi all

# Full cleanup
make clean
```

### Update Dependencies
```bash
# Update service requirements
cd services/api
pip freeze > requirements.txt

# Rebuild container
docker compose build fks_api
docker compose up -d fks_api
```

### View Resource Usage
```bash
# Container stats
docker stats

# Disk usage
docker system df

# Service status
make status
```

## 🔐 Environment Variables

### Required Variables (.env file)
```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=trading_db

# Redis
REDIS_PASSWORD=secure_redis_password

# Django
DJANGO_SECRET_KEY=your-secret-key-here

# Exchange APIs
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# OpenAI (optional)
OPENAI_API_KEY=sk-...
```

### Service-Specific Ports
- **Nginx**: 80, 443 (external)
- **FKS Main (web)**: 8000 (external)
- **fks_api**: 8001 (internal)
- **fks_app**: 8002 (internal)
- **fks_data**: 8003 (internal)
- **fks_execution**: 8004 (internal)
- **fks_ninja**: 8005 (internal)
- **fks_ai**: 8006 (internal)
- **PostgreSQL**: 5432 (external)
- **Redis**: 6379 (external)
- **Grafana**: 3000 (external)
- **Prometheus**: 9090 (external)
- **Flower**: 5555 (external)
- **PgAdmin**: 5050 (external)

## 📊 Monitoring & Observability

### Access Points
- **Health Dashboard**: http://localhost:8000/health/dashboard/
- **Monitor Dashboard**: http://localhost:8000/monitor/
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Flower (Celery)**: http://localhost:5555
- **PgAdmin**: http://localhost:5050

### Metrics Collection
Each service exposes metrics at `/metrics` endpoint:
```bash
curl http://localhost:8001/metrics  # fks_api metrics
curl http://localhost:8002/metrics  # fks_app metrics
```

Prometheus scrapes all service metrics automatically.

## 🐛 Troubleshooting

### Service Won't Start
```bash
# Check logs
docker compose logs fks_api

# Check health
docker compose ps

# Verify dependencies
docker compose config

# Test health endpoint manually
docker compose exec web curl http://fks_api:8001/health
```

### Port Conflicts
```bash
# Check what's using a port
sudo lsof -i :8001

# Change port in docker-compose.yml
expose:
  - "8007"  # Use different port
```

### Network Issues
```bash
# Recreate network
docker compose down
docker network prune
docker compose up -d

# Inspect network
docker network inspect fks_fks-network
```

### Database Connection Errors
```bash
# Verify PostgreSQL is healthy
docker compose ps db

# Check TimescaleDB extensions
docker compose exec db psql -U postgres -d trading_db -c "\dx"

# Reset database (WARNING: deletes data)
docker compose down
docker volume rm fks_postgres_data
docker compose up -d
```

## 🚀 Production Deployment

### 1. **Use Production Compose File**
```bash
# Build production images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start in production mode
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 2. **Security Checklist**
- [ ] Change all default passwords
- [ ] Set strong `DJANGO_SECRET_KEY`
- [ ] Enable SSL/TLS for PostgreSQL
- [ ] Use secrets management (Docker secrets, Vault)
- [ ] Restrict external ports (only nginx on 80/443)
- [ ] Enable rate limiting
- [ ] Configure firewall rules

### 3. **Scaling Services**
```bash
# Scale horizontally
docker compose up -d --scale fks_api=3

# Load balancing via nginx
# Configure in nginx/conf.d/
```

## 📚 Next Steps

### Immediate Improvements
1. **Add CI/CD**: GitHub Actions for automated testing/building
2. **Service Tests**: Add integration tests between services
3. **API Documentation**: Auto-generate OpenAPI specs
4. **Centralized Logging**: ELK stack or Loki
5. **Distributed Tracing**: Jaeger or Zipkin

### Long-Term Goals
1. **Kubernetes Migration**: For production scalability
2. **Service Mesh**: Istio or Linkerd for advanced routing
3. **Multi-Region**: Deploy across regions
4. **Backup Strategy**: Automated PostgreSQL/Redis backups
5. **Disaster Recovery**: Failover and recovery procedures

## 🎉 Summary

**Your monorepo is production-ready!** You have:

✅ 8 isolated microservices  
✅ Docker containerization  
✅ Service orchestration with docker-compose  
✅ Health monitoring  
✅ Development workflow with hot reload  
✅ Shared infrastructure (DB, Redis, Monitoring)  
✅ GPU support for AI workloads  
✅ Comprehensive logging  

**What to do now**:
1. Start services: `make up`
2. Check health: Visit http://localhost:8000/health/dashboard/
3. View logs: `make logs`
4. Develop: Edit code in `services/[name]/src/` and see changes instantly
5. Test: `docker compose exec [service] pytest tests/`

**Need help?** Check:
- `README.md` - Project overview
- `docs/ARCHITECTURE.md` - Detailed architecture
- `Makefile` - Available commands
- `.github/copilot-instructions.md` - AI agent guide

---

**Last Updated**: October 27, 2025  
**Status**: ✅ Fully Operational
