# FKS API Service

Lightweight FastAPI service providing HTTP/WebSocket endpoints for the FKS platform.

## Features

- Health & info endpoints
- Synthetic chart + indicator data for UI development
- Optional background Ollama model pull (dev)
- Modular router loading with graceful degradation

## Quick Start (Standalone)

```bash
# Poetry (recommended)
poetry install --no-root
poetry run uvicorn fks_api.fastapi_main:app --reload --port 8000

# Or plain venv + pip
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install .[websocket,security]
uvicorn fks_api.fastapi_main:app --reload --port 8000
```

Visit: <http://localhost:8000/docs>

## Smoke Test

```bash
poetry run pytest -q
```

## Environment Vars

- API_SERVICE_NAME, API_SERVICE_PORT
- APP_ENV (development|production)
- OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_FAST_MODEL

## Modes

This service can run in two modes:

1. **Standalone (default)** – Uses lightweight stubs (`standalone_shared.py`) and does not require the external shared monorepo packages.
2. **Shared Mode** – Mounts shared repositories and sets `USE_SHARED=1` to prefer real shared utilities.

Switch via environment variable:

```bash
# Standalone (default)
docker compose up

# Shared
docker compose -f docker-compose.yml -f docker-compose.shared.yml up
```

Or manually:

```bash
USE_SHARED=1 uvicorn fastapi_main:app --reload
```

## Docker

```bash
# Dev (standalone editable install)
docker compose up --build

# Production (non-editable, lean image)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Pull-only sanity
docker compose -f docker-compose.yml -f docker-compose.pull-only.yml pull

# Build w/o editable install (alternative)
docker compose build --build-arg INSTALL_EDITABLE=0 fks_api
```

### Shared Mode Example

```bash
docker compose -f docker-compose.yml -f docker-compose.shared.yml up --build
```

This mounts `shared/` subdirectories and sets `USE_SHARED=1` so the runtime imports the real shared utilities instead of stubs.

Celery example task:

```bash
docker compose exec worker celery -A app.celery call fks_api.ping
```

## Next Steps

- Replace synthetic data endpoints with real data service
- AuthN/Z middleware integration
- Metrics & tracing
- Deeper Celery task modules / scheduling

