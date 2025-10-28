# FKS Monorepo Architecture

**Date**: October 27, 2025  
**Architecture**: Single repo + Multi-container services  
**Status**: Implemented ✅

---

## 🎯 Architecture Overview

FKS uses a **monorepo with multi-container architecture**:
- **Single Git repository** - All code in one place
- **Multiple Docker services** - Each service runs in its own container
- **Shared dependencies** - Common code in `src/framework/`, `src/core/`
- **Service isolation** - Services communicate via HTTP APIs

### Benefits
✅ Simple development (no submodule complexity)  
✅ Atomic commits across services  
✅ Shared code reuse  
✅ Independent scaling per service  
✅ Easy local testing

---

## 📁 Directory Structure

```
fks/  (SINGLE GIT REPOSITORY)
│
├── src/                          # Shared code + FKS Main orchestrator
│   ├── framework/                # Shared utilities (all services)
│   │   ├── middleware/          # Circuit breaker, rate limiter
│   │   ├── config/              # Configuration management
│   │   ├── cache/               # Redis abstraction
│   │   └── exceptions/          # Custom exceptions
│   │
│   ├── core/                     # Core domain models (shared)
│   │   ├── models.py            # SQLAlchemy models
│   │   └── utils.py             # Database utilities
│   │
│   ├── monitor/                  # FKS Main: Service registry & health
│   ├── authentication/           # FKS Main: Centralized auth
│   │
│   └── web/                      # FKS Main: Django orchestrator
│       └── django/
│           ├── settings.py
│           ├── celery.py
│           └── wsgi.py
│
├── services/                     # Microservices code
│   ├── api/                     # fks_api - Gateway service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py              # FastAPI entry point
│   │   └── routers/
│   │       ├── gateway.py       # Route to other services
│   │       └── auth.py          # JWT validation
│   │
│   ├── app/                     # fks_app - Business logic service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py              # FastAPI entry point
│   │   ├── trading/
│   │   │   ├── strategies/
│   │   │   ├── signals/
│   │   │   ├── backtest/
│   │   │   └── optimizer/
│   │   └── tasks.py             # Celery tasks
│   │
│   ├── ai/                      # fks_ai - ML/RAG service
│   │   ├── Dockerfile.gpu
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   ├── rag/
│   │   │   ├── embeddings.py
│   │   │   ├── retrieval.py
│   │   │   └── intelligence.py
│   │   └── models/
│   │       ├── regime.py
│   │       └── forecasting.py
│   │
│   ├── data/                    # fks_data - Data collection service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── collectors/
│   │       ├── binance.py
│   │       └── polygon.py
│   │
│   ├── execution/               # fks_execution - Rust engine
│   │   ├── Dockerfile
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── main.rs
│   │       └── exchange/
│   │
│   ├── ninja/                   # fks_ninja - NinjaTrader bridge
│   │   ├── Dockerfile
│   │   └── src/
│   │       └── Program.cs
│   │
│   └── web/                     # fks_web - Web UI
│       ├── Dockerfile
│       ├── package.json
│       ├── src/
│       └── public/
│
├── docker-compose.yml           # All services orchestration
├── Makefile                     # Development commands
├── requirements.txt             # Python deps (shared)
├── tests/                       # Integration tests
│   ├── integration/            # Cross-service tests
│   └── e2e/                    # End-to-end tests
│
└── docs/                        # Documentation
    ├── ARCHITECTURE.md
    └── MONOREPO_ARCHITECTURE.md (this file)
```

---

## 🔄 Service Communication

### Data Flow
```
External Request
      ↓
  [fks_api:8001] ← Gateway (auth, routing)
      ↓
  [fks_app:8002] ← Business Logic
      ↓                ↓
[fks_data:8003]  [fks_ai:8006] ← Support Services
      ↓
[fks_execution:8004] ← ONLY talks to exchanges
```

### API Patterns

**Gateway Pattern** (fks_api):
```python
# services/api/routers/gateway.py
@router.post("/signals")
async def generate_signals(request: SignalRequest):
    # Validate auth
    # Forward to fks_app
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://fks_app:8002/signals",
            json=request.dict()
        )
    return response.json()
```

**Business Logic** (fks_app):
```python
# services/app/trading/signals/generator.py
async def generate_signal(symbol: str):
    # Query fks_data for market data
    data = await http_client.get(f"http://fks_data:8003/ohlcv/{symbol}")
    
    # Query fks_ai for regime detection
    regime = await http_client.post(
        "http://fks_ai:8006/regime",
        json={"symbol": symbol, "data": data}
    )
    
    # Generate signal
    return create_signal(data, regime)
```

---

## 🚀 Development Workflow

### Start All Services
```bash
# Standard mode (no GPU)
make up

# With GPU for fks_ai
make gpu-up

# View logs
make logs
docker-compose logs -f fks_app  # Specific service
```

### Work on Specific Service
```bash
# 1. Make changes in services/app/
cd services/app
vim trading/signals/generator.py

# 2. Rebuild just that service
docker-compose up -d --build fks_app

# 3. View logs
docker-compose logs -f fks_app

# 4. Test
pytest tests/integration/test_app_service.py
```

### Add New Service
```bash
# 1. Create directory
mkdir -p services/new_service

# 2. Add Dockerfile
cat > services/new_service/Dockerfile <<EOF
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
EOF

# 3. Add to docker-compose.yml
# (see docker-compose.yml pattern)

# 4. Start
docker-compose up -d fks_new_service
```

---

## 🧪 Testing Strategy

### Unit Tests (Per Service)
Each service directory has its own tests:
```
services/app/
  ├── trading/
  │   └── signals/
  │       ├── generator.py
  │       └── test_generator.py  # Unit tests here
```

Run:
```bash
# Inside service container
docker-compose exec fks_app pytest tests/unit/ -v
```

### Integration Tests (Cross-Service)
Located in root `tests/integration/`:
```python
# tests/integration/test_signal_flow.py
async def test_signal_generation_flow():
    """Test API → App → Data → AI flow"""
    # Call fks_api
    response = await client.post("/api/signals", json={...})
    assert response.status_code == 200
    
    # Verify fks_app processed it
    signal = await verify_signal_created()
    assert signal.symbol == "BTCUSDT"
```

Run:
```bash
pytest tests/integration/ -v
```

### E2E Tests (Full System)
Located in `tests/e2e/`:
```python
# tests/e2e/test_trading_workflow.py
async def test_full_trading_cycle():
    """Test: Signal generation → Execution → Position tracking"""
    # Generate signal via API
    # Execute via fks_execution
    # Verify position in fks_app
```

---

## 🔧 Shared Code Strategy

### When to Share
Put code in `src/framework/` or `src/core/` if:
- ✅ Used by 2+ services
- ✅ Stable interface
- ✅ Low change frequency

Examples:
- `src/framework/middleware/circuit_breaker.py` (all services use)
- `src/framework/config/constants.py` (SYMBOLS, FEE_RATE)
- `src/core/models.py` (database models)

### How to Use Shared Code

**From service code**:
```python
# services/app/main.py
import sys
sys.path.insert(0, '/app/src')  # Mount in Dockerfile

from framework.middleware.circuit_breaker import CircuitBreaker
from framework.config.constants import SYMBOLS
from core.models import Trade, Position
```

**Dockerfile pattern**:
```dockerfile
# services/app/Dockerfile
FROM python:3.13-slim
WORKDIR /app

# Copy shared code
COPY src/framework /app/src/framework
COPY src/core /app/src/core

# Copy service code
COPY services/app /app/services/app

# Install deps
RUN pip install -r services/app/requirements.txt
```

### When NOT to Share
Keep separate if:
- ❌ Service-specific logic
- ❌ Rapid iteration/experimentation
- ❌ Different tech stacks (Rust, .NET)

Examples:
- `services/app/trading/strategies/` (business logic)
- `services/ai/rag/` (AI-specific)
- `services/execution/src/` (Rust code)

---

## 📦 Dependency Management

### Shared Dependencies
```
requirements.txt  (root)
├── Django==5.1.2
├── psycopg2-binary
├── redis
└── sqlalchemy
```

Used by: FKS Main orchestrator

### Service-Specific Dependencies
```
services/app/requirements.txt
├── fastapi
├── uvicorn
├── ta-lib
├── optuna
└── -r ../../requirements.txt  # Include shared
```

```
services/ai/requirements.txt
├── torch
├── sentence-transformers
├── ollama
└── -r ../../requirements.txt
```

### Install Pattern
```dockerfile
# services/app/Dockerfile
COPY requirements.txt /tmp/shared_requirements.txt
COPY services/app/requirements.txt .
RUN pip install -r /tmp/shared_requirements.txt && \
    pip install -r requirements.txt
```

---

## 🔒 Security Considerations

### Service Isolation
- Services communicate via internal Docker network
- Only fks_api exposed to external traffic (via nginx)
- fks_execution is ONLY service with exchange API keys

### Secrets Management
```yaml
# docker-compose.yml
services:
  fks_execution:
    environment:
      - BINANCE_API_KEY=${BINANCE_API_KEY}  # From .env
      - BINANCE_API_SECRET=${BINANCE_API_SECRET}
  
  fks_app:
    environment:
      # NO exchange credentials
```

### Health Checks
Every service must implement:
```python
# services/*/main.py
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "fks_app"}
```

Monitored by FKS Main:
```python
# src/monitor/services.py
class HealthCheckService:
    async def check_service(self, url: str):
        response = await client.get(f"{url}/health")
        return response.json()
```

---

## 🚢 Deployment

### Local Development
```bash
make up                    # All services
docker-compose logs -f     # Watch logs
```

### Staging
```bash
# Build production images
docker-compose build

# Tag for registry
docker tag fks_app myregistry/fks_app:staging

# Deploy
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

### Production
```bash
# Use separate compose file
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📊 Monitoring

### Service Discovery
FKS Main tracks all services:
```python
# Register on startup
await register_service({
    "name": "fks_app",
    "url": "http://fks_app:8002",
    "version": "1.0.0"
})
```

### Health Dashboard
http://localhost:8000/health/dashboard/
- Shows all service statuses
- Alerts on failures
- Inter-service communication graph

### Prometheus Metrics
Each service exposes `/metrics`:
```python
from prometheus_client import Counter, Histogram

request_count = Counter('fks_app_requests_total', 'Total requests')
request_duration = Histogram('fks_app_request_duration_seconds', 'Request duration')
```

Scraped by Prometheus → Visualized in Grafana

---

## 🔄 Migration from Current State

### Current Issues
1. **Code in `repo/` instead of `services/`**
   - Move `repo/api/` → `services/api/`
   - Move `repo/app/` → `services/app/`
   - etc.

2. **Git submodules configured** (not needed for monorepo)
   - Remove `.gitmodules`
   - Remove submodule refs

3. **Import errors** (legacy microservices pattern)
   - Fix imports to use shared code from `src/`

### Migration Steps

#### Step 1: Rename `repo/` to `services/`
```bash
mv repo services
git add -A
git commit -m "refactor: Rename repo/ to services/ for monorepo clarity"
```

#### Step 2: Remove Git Submodules
```bash
# Remove submodule config (if exists)
rm -f .gitmodules
git config --file .git/config --remove-section submodule.repo/api 2>/dev/null || true
git config --file .git/config --remove-section submodule.repo/app 2>/dev/null || true
# ... repeat for all

git add -A
git commit -m "refactor: Remove git submodules (using monorepo)"
```

#### Step 3: Update docker-compose.yml
```yaml
# Change all paths from repo/ to services/
fks_api:
  build:
    context: ./services/api  # Was: ./repo/api
```

#### Step 4: Fix Imports
```python
# services/app/main.py
import sys
sys.path.insert(0, '/app')  # Add root to path

from src.framework.config.constants import SYMBOLS
from src.core.models import Trade
```

#### Step 5: Update Dockerfiles
```dockerfile
# services/app/Dockerfile
FROM python:3.13-slim
WORKDIR /app

# Copy shared framework
COPY src/ /app/src/

# Copy service code
COPY services/app/ /app/services/app/

# Install
COPY requirements.txt .
COPY services/app/requirements.txt ./service_requirements.txt
RUN pip install -r requirements.txt && \
    pip install -r service_requirements.txt

WORKDIR /app/services/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

---

## 📝 Checklist: Monorepo Transition

### Phase 1: Structure (1-2 hours)
- [ ] Rename `repo/` → `services/`
- [ ] Remove `.gitmodules` and submodule configs
- [ ] Update `docker-compose.yml` paths
- [ ] Update `Makefile` commands
- [ ] Test: `make up` starts all services

### Phase 2: Shared Code (2-3 hours)
- [ ] Create `src/framework/config/constants.py`
- [ ] Fix imports in all services
- [ ] Update Dockerfiles to copy shared code
- [ ] Test: Services can import from `src/`

### Phase 3: Testing (1-2 hours)
- [ ] Run unit tests per service
- [ ] Create integration tests in `tests/integration/`
- [ ] Verify service-to-service communication
- [ ] Test: All tests pass

### Phase 4: Documentation (1 hour)
- [ ] Update README.md
- [ ] Update .github/copilot-instructions.md
- [ ] Create this file (MONOREPO_ARCHITECTURE.md)
- [ ] Document service APIs

---

## 🎯 Best Practices

### DO
✅ Use `services/` for service code  
✅ Use `src/` for shared code  
✅ Mount shared code in Dockerfiles  
✅ Run integration tests  
✅ Keep services independent (HTTP APIs)

### DON'T
❌ Import service code across services  
❌ Share mutable state  
❌ Use shared database connections (use connection pooling per service)  
❌ Bypass fks_api gateway  
❌ Let services other than fks_execution talk to exchanges

---

**Generated**: October 27, 2025  
**Status**: Architecture documented, migration pending  
**Next**: Rename repo/ → services/, fix imports, test
