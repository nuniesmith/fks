# FKS Monorepo - Quick Reference

**Updated**: October 27, 2025  
**Architecture**: Single repo + Multi-container services

---

## 🎯 Quick Start

```bash
# Start all services
make up

# View logs
make logs

# Stop all
make down
```

---

## 📁 Directory Structure

```
fks/ (Single Git Repo)
├── services/          # Microservices code
│   ├── api/          # fks_api (Gateway)
│   ├── app/          # fks_app (Business Logic)
│   ├── ai/           # fks_ai (ML/RAG)
│   ├── data/         # fks_data (Data Collection)
│   ├── execution/    # fks_execution (Rust)
│   ├── ninja/        # fks_ninja (.NET)
│   └── web/          # fks_web (UI)
│
├── src/              # FKS Main + Shared Code
│   ├── framework/    # Shared utilities
│   ├── core/         # Core models
│   ├── monitor/      # Service registry
│   └── web/django/   # Orchestrator
│
└── docker-compose.yml  # All services
```

---

## 🔧 Common Tasks

### Work on Specific Service

```bash
# 1. Edit code in services/app/
vim services/app/main.py

# 2. Rebuild just that service
docker-compose up -d --build fks_app

# 3. View logs
docker-compose logs -f fks_app

# 4. Enter container
docker-compose exec fks_app bash
```

### Run Tests

```bash
# Unit tests (inside service container)
docker-compose exec fks_app pytest tests/ -v

# Integration tests (from host)
pytest tests/integration/ -v

# Specific test file
docker-compose exec fks_app pytest tests/test_signals.py -v
```

### Database Operations

```bash
# Migrations
make migrate

# Shell
make shell

# Direct DB access
make db-shell
```

---

## 🚀 Development Workflow

### 1. Make Changes
```bash
# Edit service code
vim services/app/trading/signals/generator.py

# Or edit shared code
vim src/framework/config/constants.py
```

### 2. Rebuild & Test
```bash
# Rebuild service
docker-compose up -d --build fks_app

# Check logs
docker-compose logs -f fks_app

# Run tests
docker-compose exec fks_app pytest tests/ -v
```

### 3. Commit
```bash
git add services/app/trading/signals/generator.py
git commit -m "feat(app): Add new signal generator"
```

---

## 🔄 Service Communication

### API Gateway Pattern

**External Request** → nginx → **fks_api** → **fks_app/fks_data/fks_execution**

```python
# services/api/routers/gateway.py
@router.post("/signals")
async def generate_signals(request: SignalRequest):
    # Route to fks_app
    response = await http_client.post(
        "http://fks_app:8002/signals",
        json=request.dict()
    )
    return response.json()
```

### Service-to-Service

```python
# services/app/main.py
async def get_market_data(symbol: str):
    # Query fks_data service
    response = await http_client.get(
        f"http://fks_data:8003/ohlcv/{symbol}"
    )
    return response.json()
```

---

## 🧪 Testing Strategy

### Unit Tests (Per Service)
Located in service directories:
```
services/app/
  ├── trading/
  │   ├── signals/
  │   │   ├── generator.py
  │   │   └── test_generator.py  # Unit tests
```

Run:
```bash
docker-compose exec fks_app pytest tests/unit/ -v
```

### Integration Tests (Cross-Service)
Located in root `tests/integration/`:
```bash
pytest tests/integration/test_signal_flow.py -v
```

---

## 📦 Adding Dependencies

### Shared Dependencies
Edit root `requirements.txt`:
```python
# requirements.txt
django==5.1.2
psycopg2-binary
redis
```

### Service-Specific
Edit `services/[service]/requirements.txt`:
```python
# services/app/requirements.txt
fastapi
uvicorn
ta-lib
```

Rebuild:
```bash
docker-compose up -d --build fks_app
```

---

## 🎯 Service Ports (Internal Docker Network)

| Service | Port | Purpose |
|---------|------|---------|
| fks_main | 8000 | Orchestrator, health dashboard |
| fks_api | 8001 | API Gateway |
| fks_app | 8002 | Business Logic |
| fks_data | 8003 | Data Collection |
| fks_execution | 8004 | Execution Engine |
| fks_ninja | 8005 | NinjaTrader Bridge |
| fks_ai | 8006 | ML/RAG |
| fks_web | 3001 | Web UI |

**External Access**: Only nginx (80/443) and fks_main (8000) exposed

---

## 🔍 Debugging

### View Service Logs
```bash
# All services
make logs

# Specific service
docker-compose logs -f fks_app

# Last 100 lines
docker-compose logs --tail=100 fks_app
```

### Check Service Health
```bash
# Via health dashboard
curl http://localhost:8000/health/dashboard/

# Individual service
curl http://localhost:8000/monitor/api/services/fks_app

# Direct health check (inside network)
docker-compose exec fks_app curl http://fks_data:8003/health
```

### Enter Container
```bash
# Shell access
docker-compose exec fks_app bash

# Python shell
docker-compose exec fks_app python

# Django shell
make shell
```

---

## 🐛 Common Issues

### Service Won't Start
```bash
# Check logs
docker-compose logs fks_app

# Rebuild
docker-compose up -d --build fks_app

# Remove and recreate
docker-compose stop fks_app
docker-compose rm -f fks_app
docker-compose up -d fks_app
```

### Import Errors
```python
# Add shared code to Python path
import sys
sys.path.insert(0, '/app')

from src.framework.config.constants import SYMBOLS
```

### Connection Refused
```bash
# Use service name (not localhost)
# ❌ Wrong: http://localhost:8003
# ✅ Right: http://fks_data:8003

# Verify service is running
docker-compose ps fks_data
```

---

## 📊 Monitoring

### Health Dashboard
http://localhost:8000/health/dashboard/
- All service statuses
- Inter-service communication
- Recent issues

### Service Registry
http://localhost:8000/monitor/api/services/
- List all registered services
- Health check history
- Service metadata

### Grafana
http://localhost:3000 (admin/admin)
- System metrics
- Service metrics
- Custom dashboards

### Prometheus
http://localhost:9090
- Raw metrics
- Query language (PromQL)
- Alerts

---

## 🚢 Deployment

### Local Development
```bash
make up
```

### With GPU
```bash
make gpu-up  # For fks_ai service
```

### Production (Future)
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📝 Git Workflow

### Feature Branch
```bash
git checkout -b feature/new-signal-type
# Make changes
git add services/app/trading/signals/
git commit -m "feat(app): Add momentum signal type"
git push origin feature/new-signal-type
```

### Hotfix
```bash
git checkout -b hotfix/fix-division-by-zero
# Fix issue
git add services/app/trading/signals/generator.py
git commit -m "fix(app): Handle zero volume in signal calculation"
git push origin hotfix/fix-division-by-zero
```

---

## 🔧 Useful Commands

```bash
# Service management
docker-compose ps                      # List services
docker-compose restart fks_app         # Restart service
docker-compose stop fks_app            # Stop service
docker-compose up -d --build fks_app   # Rebuild & restart

# Logs
docker-compose logs -f                 # All logs
docker-compose logs -f fks_app         # Service logs
docker-compose logs --tail=50 fks_app  # Last 50 lines

# Cleanup
make down                              # Stop all
make clean                             # Deep clean (removes volumes)
docker system prune -f                 # Clean Docker

# Database
make migrate                           # Run migrations
make shell                             # Django shell
make db-shell                          # PostgreSQL shell
make backup-db                         # Backup database

# Testing
pytest tests/unit/ -v                  # Unit tests
pytest tests/integration/ -v           # Integration tests
make test                              # All tests

# Code Quality
make lint                              # Run linters
make format                            # Format code
```

---

## 🎓 Best Practices

### DO ✅
- Keep services independent (HTTP APIs only)
- Use `src/framework/` for shared utilities
- Write tests for new features
- Check health dashboard before deploying
- Use semantic commit messages

### DON'T ❌
- Import service code across services
- Hardcode service URLs (use env vars)
- Bypass fks_api gateway
- Let services other than fks_execution talk to exchanges
- Commit `.env` file

---

## 🆘 Getting Help

1. **Check logs**: `make logs` or `docker-compose logs -f fks_app`
2. **Health dashboard**: http://localhost:8000/health/dashboard/
3. **Service status**: `make multi-status`
4. **Documentation**: `docs/MONOREPO_ARCHITECTURE.md`
5. **Copilot instructions**: `.github/copilot-instructions.md`

---

## 📚 Key Files

- `docker-compose.yml` - Service orchestration
- `Makefile` - Development commands
- `services/*/main.py` - Service entry points
- `src/framework/` - Shared utilities
- `src/core/models.py` - Database models
- `tests/integration/` - Cross-service tests

---

**Last Updated**: October 27, 2025  
**Architecture**: Monorepo + Multi-container
