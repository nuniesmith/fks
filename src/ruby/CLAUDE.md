# ruby — Claude Code Project Instructions

> **Repo (future):** `github.com/nuniesmith/ruby`
> **Today's path:** `fks-full/src/ruby/`
> Will become its own repo; the `nuniesmith/fks:ruby` Docker image gets
> built from a `git clone --branch ${RUBY_REF:-main}` step.

## What this is

The Python trading system. Data pipeline + ML models + HTMX dashboard +
broker integrations + GPU training. Three FastAPI apps under one
supervisord process: data (8000), engine, futures (8080). Janus
consumes its data API as the single source of truth for market data.

## Stack

| | |
|--|--|
| Python | 3.13+ |
| Web | FastAPI + uvicorn + HTMX + Jinja2 |
| ML | PyTorch (CPU + CUDA), scikit-learn, numpy, pandas |
| Data | Postgres (psycopg), Redis, QuestDB (PG wire) |
| Process model | supervisord runs all three services |
| Linting | ruff, mypy |
| Tests | pytest, pytest-asyncio |

## Build & run

```bash
# Local dev
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run one service
python -m lib.services.data.app
python -m lib.services.engine.app
python -m lib.services.web.app

# Tests
python -m pytest tests/                       # all
python -m pytest tests/ -k test_thing -v      # one
python -m pytest tests/ --cov=lib             # with coverage

# Lint / format / typecheck
ruff check lib/
ruff format lib/
mypy lib/

# Docker (from fks-full root)
docker compose build ruby
docker compose up -d ruby
docker compose logs -f ruby
```

## Repository layout

```
src/ruby/
├── pyproject.toml
├── lib/
│   ├── core/             # db.py, redis.py, config.py, logging_config.py
│   ├── analysis/         # market analysis (ICT, regime, CVD, ML inference)
│   ├── indicators/       # technical indicators (Python side)
│   ├── integrations/     # Kraken, Rithmic, Massive S3, Binance, …
│   ├── model/            # CNN inference
│   ├── services/         # FastAPI apps — data, engine, web, trainer
│   └── trading/          # ORB, signals, journal, execution gate
├── sql/                  # DB migrations (Postgres)
├── tests/
└── (after the in-flight reorg lands, the SQL migrations live here)
```

## Code conventions

- **Logging:** always use the project logger; never `print()` or `logging.basicConfig()`:
  ```python
  from lib.core.logging_config import get_logger
  logger = get_logger("my.module.name")
  logger.info("something happened", key=value)
  ```
- **Type hints:** required on all public functions. `from __future__ import annotations` at the top of every module.
- **Async:** FastAPI endpoints are `async def`. CPU-bound work goes in `asyncio.to_thread()` or a thread pool executor.
- **Imports:** absolute from `lib.*`. The Docker image sets `PYTHONPATH=/app/src`; locally, run from `src/ruby/` or set `PYTHONPATH` manually.
- **Config:** environment variables via `os.getenv()` with defaults. Never hardcode values. `.env` is gitignored.
- **Tests** mirror the source tree: `lib/foo/bar.py` ↔ `tests/foo/test_bar.py`.

## Critical invariants

- **No autonomous execution.** Every order goes through `lib.trading.execution_gate` which requires explicit operator confirmation. `EXECUTION_MODE=paper_trading` is the default. Never default to `live`.
- **Ruby is the data source of truth.** Janus pulls bars from `http://fks_ruby:8000` via `PYTHON_DATA_SERVICE_URL`. Don't add a second data path elsewhere.

## Service ports

| Port | Service | Notes |
|------|---------|-------|
| 8000 | data    | Public API consumed by Janus + WebUI |
| 8050 | data    | (legacy) — same app, different port |
| 8080 | futures | HTMX dashboard + futures-specific endpoints |

## Common workflows

### Add a new endpoint to the data API
1. Add the route in `lib/services/data/api/`.
2. Add a test in `tests/services/data/`.
3. If the WebUI needs it, also add an `$api/*` wrapper in `fks-full/src/web/src/lib/api/`.

### Add a new exchange integration
1. New module under `lib/integrations/<exchange>/`.
2. Implement a `Client` with `async fetch_bars()`, `async fetch_account()`, etc.
3. Wire into `lib.services.data.factory` so the data router can dispatch to it.
4. Tests under `tests/integrations/<exchange>/` — mocked, no live API calls.

### Retrain CNN models
See `lib/services/trainer/` and `scripts/train.sh` in the repo root.

## Pre-split gotchas

- **The `infrastructure/docker/services/data/Dockerfile`** in `fks-full` currently `COPY`s this directory. After the split it should `git clone --branch ${RUBY_REF:-main} https://github.com/nuniesmith/ruby` instead.
- **SQL migrations** currently in `fks-full/src/sql/ruby/`; an in-flight reorg moves them to `src/ruby/sql/` so they travel with the Python code. After the split, the schema is owned here.
- **`grpcio-tools`** is excluded from `pyproject.toml`'s dev extras because of a `protobuf` version conflict with `async-rithmic`. Install ad-hoc when regenerating gRPC stubs: `pip install grpcio-tools`.
- **Model files** are gitignored (`.onnx`, `.pt`, `.safetensors`). Only metadata + feature contracts are tracked; the binaries live in `fks-full/models/` and are mounted into the container.
