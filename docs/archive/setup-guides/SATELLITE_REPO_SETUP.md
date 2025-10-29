# Satellite Repository Setup Guide

This guide provides step-by-step instructions for creating and configuring each FKS microservice repository.

## Table of Contents

1. [Repository Structure](#repository-structure)
2. [Common Setup (All Services)](#common-setup-all-services)
3. [Service-Specific Setup](#service-specific-setup)
   - [fks-api (API Gateway)](#fks-api-api-gateway)
   - [fks-data (Data Ingestion)](#fks-data-data-ingestion)
   - [fks-execution (Trade Execution)](#fks-execution-trade-execution)
   - [fks-ninja (NinjaTrader Bridge)](#fks-ninja-ninjatrader-bridge)
   - [fks-web-ui (React SPA)](#fks-web-ui-react-spa)
4. [Adding Repos as Submodules](#adding-repos-as-submodules)
5. [Testing the Setup](#testing-the-setup)

---

## Repository Structure

Each satellite repository should have the following structure:

```
fks-<service>/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── health.py               # Health check endpoint
│   └── routes/                 # API routes (service-specific)
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── test_health.py          # Health check tests
│   └── test_routes.py          # Route tests
├── .dockerignore
├── .gitignore
├── Dockerfile                  # Multi-stage Docker build
├── README.md                   # Service documentation
├── requirements.txt            # Python dependencies
└── requirements.dev.txt        # Development dependencies
```

---

## Common Setup (All Services)

### 1. Create Repository on GitHub

```bash
# Example for fks-api (repeat for each service)
gh repo create nuniesmith/fks-api --public --description "FKS API Gateway - External integrations and REST API"
```

### 2. Clone and Initialize

```bash
mkdir -p ~/projects/fks-repos
cd ~/projects/fks-repos
git clone https://github.com/nuniesmith/fks-api.git
cd fks-api
```

### 3. Create `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Environment variables
.env
.env.local
.env.*.local

# Logs
logs/
*.log

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Docker
.dockerignore
```

### 4. Create `.dockerignore`

```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
.git
.gitignore
README.md
.env
.env.*
tests/
.pytest_cache/
.coverage
htmlcov/
venv/
env/
*.log
```

### 5. Create Base `requirements.txt`

```txt
# FastAPI framework
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.0.0
pydantic-settings>=2.0.0

# HTTP client for inter-service communication
httpx>=0.27.0

# Monitoring & health
prometheus-client>=0.21.0
python-json-logger>=2.0.7

# Environment management
python-dotenv>=1.0.0
```

### 6. Create `requirements.dev.txt`

```txt
-r requirements.txt

# Testing
pytest>=8.0.0
pytest-asyncio>=0.24.0
pytest-cov>=6.0.0
pytest-mock>=3.14.0

# Linting & formatting
ruff>=0.8.0
black>=24.0.0
mypy>=1.13.0

# Development tools
ipython>=8.31.0
```

---

## Service-Specific Setup

### fks-api (API Gateway)

**Purpose**: External API gateway for REST endpoints, authentication, rate limiting

#### Create `src/main.py`

```python
"""FKS API Gateway - Main application entry point."""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

from src.config import settings
from src.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Lifecycle manager for FastAPI application."""
    # Startup: Register with monitor service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.MONITOR_URL,
                json={
                    "name": settings.SERVICE_NAME,
                    "service_type": "api",
                    "host": "fks_api",
                    "port": 8001,
                    "health_endpoint": "/health",
                    "version": "1.0.0",
                },
                timeout=5.0,
            )
            print(f"✅ Registered with monitor: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Failed to register with monitor: {e}")
    
    yield
    
    # Shutdown: Cleanup
    print("👋 API Gateway shutting down")


# Create FastAPI app
app = FastAPI(
    title="FKS API Gateway",
    description="External API gateway for FKS Trading Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "FKS API Gateway",
        "version": "1.0.0",
        "status": "operational",
    }
```

#### Create `src/config.py`

```python
"""Configuration management for FKS API Gateway."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # Service configuration
    SERVICE_NAME: str = "fks_api"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # Monitor service
    MONITOR_URL: str = "http://web:8000/monitor/api/discover/"
    
    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3001",  # fks-web-ui
        "http://localhost:8000",  # main web app
    ]
    
    # Database (if needed)
    DATABASE_URL: str = "postgresql://fks_user:password@db:5432/trading_db"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/2"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()
```

#### Create `src/health.py`

```python
"""Health check endpoint for FKS API Gateway."""
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> JSONResponse:
    """Standard health check endpoint.
    
    Returns:
        JSON response with service status and metadata
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "fks_api",
            "version": "1.0.0",
            "dependencies": {
                "database": "unknown",  # TODO: Add DB health check
                "redis": "unknown",     # TODO: Add Redis health check
            },
        },
    )
```

#### Create `Dockerfile`

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

#### Create `README.md`

```markdown
# FKS API Gateway

External API gateway for the FKS Trading Platform. Handles authentication, rate limiting, and external integrations.

## Features

- RESTful API endpoints
- JWT authentication
- Rate limiting per user/IP
- Request validation with Pydantic
- Automatic service registration with monitor
- Health check endpoint

## Development

\`\`\`bash
# Install dependencies
pip install -r requirements.dev.txt

# Run locally
uvicorn src.main:app --reload --port 8001

# Run tests
pytest tests/ -v

# Lint & format
ruff check src/
black src/
\`\`\`

## Docker

\`\`\`bash
# Build image
docker build -t fks-api:latest .

# Run container
docker run -p 8001:8001 --env-file .env fks-api:latest
\`\`\`

## API Endpoints

- `GET /` - Root endpoint (service info)
- `GET /health` - Health check
- `GET /api/v1/...` - API routes (TODO)
```

---

### fks-data (Data Ingestion)

**Purpose**: Market data ingestion from exchanges (Binance, etc.), WebSocket feeds, historical data management

#### Key Files to Create

1. **`src/main.py`** - Similar structure to fks-api, but include routes for:
   - `/api/market-data/{symbol}` - Get latest market data
   - `/api/historical/{symbol}` - Get historical data
   - `/api/websocket/subscribe` - Subscribe to WebSocket feeds

2. **`src/config.py`** - Add exchange API credentials:
   ```python
   BINANCE_API_KEY: str = ""
   BINANCE_API_SECRET: str = ""
   CCXT_EXCHANGE: str = "binance"
   ```

3. **`src/health.py`** - Check Binance API connectivity:
   ```python
   dependencies = {
       "binance_api": await check_binance_connection(),
       "database": await check_database(),
   }
   ```

4. **`requirements.txt`** - Add:
   ```txt
   ccxt>=4.0.0
   websockets>=14.0
   pandas>=2.0.0
   numpy>=1.24.0
   ```

---

### fks-execution (Trade Execution)

**Purpose**: Execute trades, manage positions, handle order lifecycle, risk management

#### Key Files to Create

1. **`src/main.py`** - Include routes for:
   - `POST /api/execute/order` - Execute a trade
   - `GET /api/positions` - Get current positions
   - `POST /api/positions/close` - Close a position
   - `GET /api/orders/{order_id}` - Get order status

2. **`src/config.py`** - Add:
   ```python
   DATA_SERVICE_URL: str = "http://fks_data:8002"
   MAX_POSITION_SIZE: float = 10000.0
   RISK_LIMIT_PERCENT: float = 2.0
   ```

3. **`src/health.py`** - Check data service connectivity:
   ```python
   dependencies = {
       "data_service": await check_service(settings.DATA_SERVICE_URL),
       "database": await check_database(),
   }
   ```

4. **`requirements.txt`** - Add:
   ```txt
   ccxt>=4.0.0
   celery>=5.5.0
   redis>=5.2.0
   ```

---

### fks-ninja (NinjaTrader Bridge)

**Purpose**: Bridge between FKS platform and NinjaTrader 8 for automated trading

#### Key Files to Create

1. **`src/main.py`** - Include routes for:
   - `POST /api/ninja/connect` - Connect to NinjaTrader
   - `POST /api/ninja/place-order` - Place order in NinjaTrader
   - `GET /api/ninja/positions` - Get NinjaTrader positions
   - `GET /api/ninja/account-info` - Get account information

2. **`src/config.py`** - Add:
   ```python
   NINJATRADER_HOST: str = "localhost"
   NINJATRADER_PORT: int = 47740  # Default AT Interface port
   EXECUTION_SERVICE_URL: str = "http://fks_execution:8003"
   DATA_SERVICE_URL: str = "http://fks_data:8002"
   ```

3. **`src/health.py`** - Check NinjaTrader connectivity:
   ```python
   dependencies = {
       "ninjatrader": await check_ninjatrader_connection(),
       "execution_service": await check_service(settings.EXECUTION_SERVICE_URL),
       "data_service": await check_service(settings.DATA_SERVICE_URL),
   }
   ```

4. **`requirements.txt`** - Add:
   ```txt
   aiohttp>=3.11.0
   python-socketio>=5.11.0
   ```

---

### fks-web-ui (React SPA)

**Purpose**: Modern React single-page application for alternative web interface

#### Repository Structure

```
fks-web-ui/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── App.tsx
│   └── main.tsx
├── .dockerignore
├── .gitignore
├── Dockerfile
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

#### Create `package.json`

```json
{
  "name": "fks-web-ui",
  "version": "1.0.0",
  "description": "FKS Trading Platform - React SPA",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext ts,tsx",
    "format": "prettier --write src/**/*.{ts,tsx,css}"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^7.1.1",
    "axios": "^1.7.9",
    "recharts": "^2.15.0",
    "zustand": "^5.0.2"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.2",
    "vite": "^6.0.5",
    "eslint": "^9.18.0",
    "prettier": "^3.4.2"
  }
}
```

#### Create `Dockerfile`

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3001 || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

#### Create `src/services/api.ts`

```typescript
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health check
export const checkHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};
```

---

## Adding Repos as Submodules

Once all satellite repos are created and pushed to GitHub:

```bash
cd ~/Nextcloud/code/repos/fks

# Add each repo as a submodule
git submodule add https://github.com/nuniesmith/fks-api.git repo/api
git submodule add https://github.com/nuniesmith/fks-data.git repo/data
git submodule add https://github.com/nuniesmith/fks-execution.git repo/execution
git submodule add https://github.com/nuniesmith/fks-ninja.git repo/ninja
git submodule add https://github.com/nuniesmith/fks-web-ui.git repo/web

# Commit submodule additions
git add .gitmodules repo/
git commit -m "feat: Add microservices as Git submodules"
git push origin main
```

### Updating Submodules

```bash
# Update all submodules to latest
git submodule update --remote --recursive

# Update specific submodule
git submodule update --remote repo/api

# Check submodule status
git submodule status
```

---

## Testing the Setup

### 1. Build All Services

```bash
cd ~/Nextcloud/code/repos/fks
make multi-build
```

### 2. Start All Services

```bash
make multi-up
```

### 3. Check Service Status

```bash
make multi-status
```

Expected output:
```
=== Microservices Status ===
NAME           IMAGE              STATUS      PORTS
fks_api        fks-api:latest     Up 30s      8001/tcp
fks_data       fks-data:latest    Up 30s      8002/tcp
fks_execution  fks-execution      Up 30s      8003/tcp
fks_ninja      fks-ninja:latest   Up 30s      8004/tcp
fks_web_ui     fks-web-ui:latest  Up 30s      3001/tcp

=== Health Checks ===
fks_api: ✅ Healthy
fks_data: ✅ Healthy
fks_execution: ✅ Healthy
fks_ninja: ✅ Healthy
fks_web_ui: ✅ Healthy
```

### 4. Register Services with Monitor

```bash
make register-services
```

### 5. Open Monitor Dashboard

```bash
make monitor-dashboard
```

Or visit: http://localhost:8000/monitor/

### 6. View Logs

```bash
# All microservices
make multi-logs

# Specific service
docker-compose logs -f fks_api
```

### 7. Test Health Endpoints

```bash
# Test each service health endpoint
curl http://localhost:8001/health  # fks_api (via nginx proxy)
curl http://localhost:8000/monitor/api/health/  # All services

# Run automated health check
make multi-health
```

---

## Common Issues & Solutions

### Issue: Service won't start

**Solution**: Check logs for the specific service
```bash
docker-compose logs fks_api
```

### Issue: Health check fails

**Solution**: Verify service is accessible on expected port
```bash
docker-compose exec web curl -f http://fks_api:8001/health
```

### Issue: Submodule not updating

**Solution**: Force update and checkout correct branch
```bash
git submodule update --remote --force repo/api
cd repo/api
git checkout main
git pull origin main
```

### Issue: Build fails for service

**Solution**: Check Dockerfile and requirements.txt
```bash
cd repo/api
docker build -t fks-api:test .
```

---

## Next Steps

1. **Implement Service Routes**: Add business logic to each service's routes
2. **Add Tests**: Write unit and integration tests for each service
3. **Set Up CI/CD**: Create GitHub Actions workflows for each repo
4. **Configure Secrets**: Add API keys and credentials to `.env` files
5. **Enable Service Communication**: Implement inter-service API calls
6. **Add Metrics**: Integrate Prometheus metrics in each service
7. **Document APIs**: Add OpenAPI/Swagger documentation
8. **Deploy**: Set up production deployment with Docker Compose or Kubernetes

---

## References

- [Multi-Repo Architecture](./MULTI_REPO_ARCHITECTURE.md)
- [FKS Main README](../README.md)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Git Submodules Guide](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
