# FKS — Claude Code Project Instructions

## Project Overview

**FKS (Freddy Krueger Sniper)** is a manual trading co-pilot — a unified algorithmic trading platform
that surfaces signals and analysis to a human trader who makes all final execution decisions.
**The system NEVER executes trades autonomously.** Every order requires explicit manual confirmation.

**Stack:** Rust + Python + SvelteKit + Docker (20+ containerised services)

| Component        | Language   | Description                                                                 |
|------------------|------------|-----------------------------------------------------------------------------|
| **Janus**        | Rust       | Neuromorphic ML engine — live signals, regime detection, backtesting        |
| **Ruby**         | Python     | Data pipeline, ML models, HTMX dashboard, broker integrations, GPU training |
| **WebUI**        | SvelteKit  | SvelteKit 5 frontend — replaces the HTMX dashboard. Includes `/bots` for spawner control. |
| **RustCode**     | Rust       | AI agent, LLM routing, semantic search, OpenAI-compatible proxy             |
| **rustrade**     | Rust       | Open-source trading framework — supervisor, risk, backtest, kucoin adapter |
| **Spawner**      | Rust       | Bot container lifecycle manager — spawns/stops/streams logs of `fks-bot-*` containers via Docker socket |
| **OpenClaw**     | Node.js    | Discord bot + GitHub integration — routes LLM calls through RustCode        |
| **Infrastructure** | Docker   | Postgres, Redis, QuestDB, Qdrant, Prometheus, Grafana, Nginx, Jaeger        |

---

## Service Map

| Service           | Path                  | Host Port(s)           | Container Port(s) | Notes                              |
|-------------------|-----------------------|------------------------|-------------------|------------------------------------|
| **Janus**         | `crates/janus/`       | 7000 (HTTP), 9051 (gRPC), 9092 (metrics) | 8080, 50051, 9092 | Rust ML/neuromorphic engine |
| **Ruby**          | `src/ruby/`           | 8050 (data API), 8080 (HTMX web) | 8000, 8080 | Python trading system (supervisord) |
| **WebUI**         | `src/web/`            | 3001                   | 3000              | SvelteKit frontend                 |
| **RustCode**      | `crates/rustcode/`    | 3500                   | 3500              | Rust AI assistant (workspace currently has 32 build errors — incomplete TASK-A/B work) |
| **rustrade**      | `crates/rustrade/`    | —                      | —                 | Open-source trading framework (library, not a service) |
| **Spawner**       | `src/spawner/`        | 8090                   | 8090              | Bot container lifecycle (mounts `/var/run/docker.sock`, writes Prometheus SD) |
| **Kotlin**        | `src/kotlin/`         | —                      | —                 | KMP cross-platform apps (excluded from workspace) |
| **Trainer**       | —                     | 8200                   | 8200              | GPU CNN retraining (profile: training) |
| **Postgres**      | —                     | 5432                   | 5432              | `janus_db` + `ruby_db` on one instance |
| **Redis**         | —                     | 6379                   | 6379              | Shared pub/sub, state, caching     |
| **QuestDB**       | —                     | 9000, 9009, 8812       | 9000, 9009, 8812  | Time-series market data            |
| **Qdrant**        | —                     | 6333, 6334             | 6333, 6334        | Vector embeddings                  |
| **Nginx**         | —                     | 80                     | 80                | Reverse proxy (TLS via Tailscale)  |
| **Grafana**       | —                     | 3000                   | 3000              | Dashboards (served at `/grafana/`) |
| **Prometheus**    | —                     | 9090                   | 9090              | Metrics                            |
| **Alertmanager**  | —                     | 9093                   | 9093              | Alerts + Discord bridge            |
| **RustCode Postgres** | —                 | 5433                   | 5432              | RustCode-only database             |
| **RustCode Redis**    | —                 | 6380                   | 6379              | RustCode cache                     |
| **OpenClaw**      | —                     | 18789, 18790           | 18789, 18790      | Discord bot WebSocket              |
| **Jaeger**        | —                     | 16686                  | 16686             | Distributed tracing UI             |

> ⚠️ **All ports are bound to `127.0.0.1`** — only reachable via localhost or Tailscale serve.
> RustCode and RustCode Redis bind to `${TAILSCALE_IP}` instead of `127.0.0.1`.
>
> **Spawned bot containers** (anything matching `ALLOWED_IMAGE_PREFIX=fks-bot-`)
> are placed on the `fks_network` Docker network with `cap_drop: ALL`,
> `security_opt: no-new-privileges:true`, CPU/memory caps from the
> spawn request (or spawner defaults), and forced `fks.bot=true` +
> `fks.bot_id=<uuid>` + `fks.mode=<paper|live|backtest|optimise|train>`
> labels. They expose `:9091/metrics` to be scraped by Prometheus via
> the file_sd config the spawner writes to `/prometheus-sd/bots.json`.

---

## Build & Run Commands

### Rust (Janus + RUSTCODE)

```bash
# Type-check entire workspace (fast — no codegen)
cargo check --workspace

# Build Janus binary
cargo build -p janus

# Build RustCode
cargo build -p rustcode

# Build all (slow — ~50 crates)
cargo build --workspace

# Run tests for a specific crate
cargo test -p janus-core

# Lint
cargo clippy --workspace

# Format
cargo fmt --all

# Generate sqlx offline query cache (required before building RUSTCODE without a live DB)
cargo sqlx prepare --workspace
```

### SvelteKit (WebUI)

```bash
cd src/web

# Dev server (hot reload, port 5173)
npm run dev

# Type-check
npm run check

# Watch mode type-check
npm run check:watch

# E2E tests (Playwright)
npm run test:e2e

# Build for production
npm run build
```

### Python (Ruby)

```bash
# Install deps (from repo root, using pyproject.toml)
pip install -e ".[dev]"

# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=src/ruby

# Lint / format
ruff check src/ruby/
ruff format src/ruby/

# Type-check
mypy src/ruby/
```

### Docker

```bash
# Start all core services
docker compose up -d

# Start with GPU trainer
docker compose --profile training up -d

# Start with optional tools (Ollama, promptfoo, etc.)
docker compose --profile tools up -d
docker compose --profile ollama up -d

# Build a single service image
docker compose build janus
docker compose build ruby
docker compose build webui

# View logs
docker compose logs -f janus
docker compose logs -f ruby

# Restart a service
docker compose restart janus

# Stop everything
docker compose down

# Rebuild the Python base layer (speeds up CI)
docker compose --profile base build base
```

---

## Testing Commands

| Stack      | Command                                       | Notes                              |
|------------|-----------------------------------------------|------------------------------------|
| Rust       | `cargo test --workspace`                      | All unit + integration tests       |
| Rust       | `cargo test -p <crate>`                       | Single crate tests                 |
| Python     | `python -m pytest tests/`                     | All Python tests                   |
| Python     | `python -m pytest tests/ -k test_name`        | Single test                        |
| Python     | `python -m pytest tests/ -x --tb=short`       | Fail fast                          |
| SvelteKit  | `npm run test:e2e`                            | Playwright E2E (from `src/web/`) |
| SvelteKit  | `npm run test:e2e:ui`                         | Playwright with interactive UI     |
| Proto      | `./proto/validate.sh`                         | Validate .proto files with buf     |
| Proto      | `./scripts/gen-proto.sh`                      | Regenerate gRPC stubs              |

---

## Key Files & Conventions

### Repository Layout

```
fks/
├── Cargo.toml                  # Rust workspace root — all shared deps defined here
├── pyproject.toml              # Python project root (Ruby)
├── docker-compose.yml          # Unified compose — all 20+ services
├── docker-compose.prod.yml     # Production overrides
├── docker-compose.trainer.yml  # Dedicated GPU rig compose
├── run.sh                      # Main management script
├── buf.yaml                    # Buf config for proto linting
├── proto/fks/                  # Protocol Buffer definitions (.proto files)
│   ├── common/                 # Shared types
│   ├── janus/                  # Janus-specific protos
│   ├── signals/                # Signal types
│   ├── execution/              # Order execution protos
│   ├── forward/                # Forward service protos
│   ├── backward/               # Backward service protos
│   ├── data/                   # Data service protos
│   ├── rc/                     # RustCode protos
│   └── ...
├── crates/                      # Rust crates outside the root virtual workspace
│   ├── janus/                   # Janus ML/neuromorphic engine (28 sub-crates, 8 services)
│   │   ├── bin/janus/           # Main binary entry point
│   │   ├── bin/backtest-cli/    # Backtest CLI tool
│   │   ├── lib/janus-core/      # Core types & traits
│   │   ├── lib/janus-api/       # HTTP API layer
│   │   ├── crates/              # Feature crates (indicators, risk, regime, ml, …)
│   │   ├── services/            # Service crates (forward, backward, data, execution, …)
│   │   └── neuromorphic/        # Brain-region modules
│   ├── rustrade/                # Open-source trading framework (rustrade-{core,supervisor,risk,backtest,kucoin,notify} + facade + examples)
│   ├── rustcode/                # AI coding assistant (workspace currently broken — see TODO.md)
│   ├── indicators-ta/           # Standalone technical-analysis crate (publishable)
│   └── exchange-apiws/          # Standalone exchange REST/WS client (publishable)
├── src/                         # Top-level virtual workspace (proto + spawner)
│   ├── ruby/                    # Python trading system
│   │   ├── lib/
│   │   │   ├── core/            # DB, Redis, config, logging_config
│   │   │   ├── analysis/        # Market analysis (ICT, regime, CVD, ML)
│   │   │   ├── indicators/      # Technical indicators
│   │   │   ├── integrations/    # Kraken, Rithmic, Massive, Binance, etc.
│   │   │   ├── model/           # CNN inference
│   │   │   ├── services/        # FastAPI apps (data, engine, web, trainer)
│   │   │   └── trading/         # ORB, signals, journal
│   │   └── tests/               # Python test suite
│   ├── spawner/                 # Bot container lifecycle service (Rust + bollard + axum + sqlx)
│   │   └── src/                 # api.rs, db.rs, docker_client.rs, prometheus_sd.rs, …
│   ├── web/                     # SvelteKit 5 WebUI
│   │   └── src/routes/          # Includes /bots route for spawner control
│   ├── proto/                   # fks-proto Rust crate (protobuf build)
│   └── sql/                     # SQL schemas and migrations
│       ├── ruby/                # Ruby DB migrations (incl. 007_spawner.sql for bot_runs/bot_configs)
│       ├── janus/               # Janus DB migrations
│       └── rustcode/            # RustCode migrations
├── infrastructure/
│   ├── docker/                 # All Dockerfiles
│   │   ├── base/rust/          # Rust multi-stage build
│   │   ├── base/python/        # Python multi-stage build
│   │   ├── base/python-gpu/    # GPU trainer build
│   │   └── services/           # Per-service Dockerfiles
│   └── configs/                # Runtime configs (prometheus, grafana, nginx, loki, …)
└── scripts/                    # Operational scripts
```

### Proto Files

- All proto definitions live in `proto/fks/`
- Package naming convention: `fks.{service}.v1` (e.g. `fks.signals.v1`, `fks.execution.v1`)
- The `src/proto/` crate is the Rust protobuf build crate (`fks-proto`) — it `include_proto!()`s
  the generated code and re-exports it
- Regenerate stubs with `./scripts/gen-proto.sh` (requires `buf` and `grpcio-tools`)

### Environment Variables

- Copy `.env.example` → `.env` and fill in all values before starting services
- **Never hardcode secrets** — all secrets must come from `.env`
- Generate random secrets with: `openssl rand -base64 32`
- The `.env` file is gitignored; `.env.example` is tracked

### Docker Compose Profiles

| Profile     | Services Added                        |
|-------------|---------------------------------------|
| `training`  | GPU trainer container                 |
| `ollama`    | Ollama local LLM + model puller       |
| `base`      | Python base image (CI cache layer)    |
| `qdrant`    | Qdrant vector database                |
| `tools`     | promptfoo and other eval tools        |

---

## Code Conventions

### Rust

- **Edition:** 2024 (`edition = "2024"` in all `Cargo.toml` files)
- **Workspace deps:** All shared dependencies are declared once in the root `Cargo.toml`
  under `[workspace.dependencies]`. Individual crates use `dep = { workspace = true }`.
  Do NOT add new version pins inside crate-level `Cargo.toml` files if the dep is already
  in the workspace.
- **Rust version:** Minimum 1.92.0 (`rust-version = "1.92.0"`)
- **Error handling:** `anyhow` for application errors, `thiserror` for library errors
- **Async runtime:** Tokio with `features = ["full"]`
- **Logging/tracing:** `tracing` crate with structured `tracing-subscriber` (JSON output in Docker)
- **Lints:** Workspace lints enforce `clippy::all`, `clippy::pedantic`, `clippy::nursery`.
  Fix warnings before committing. `unsafe_code = "warn"`.
- **Release profile:** `panic = "abort"` — panics terminate the process cleanly for supervisor restart
- **RustCode note:** `crates/rustcode` is a nested workspace and currently uses its own dependency versions
  (axum 0.7, reqwest 0.11, redis 0.24) instead of inheriting from the root. The workspace also has
  32 build errors from incomplete TASK-A/B in-flight work — see `TODO.md` for the decision needed.

### Python (Ruby)

- **Version:** Python 3.13+
- **Logging:** Always use `structlog` via the project logger — never `print()` or `logging.basicConfig()`:
  ```python
  from lib.core.logging_config import get_logger
  logger = get_logger("my.module.name")
  logger.info("something happened", key=value)
  ```
- **Type hints:** Required on all public functions. Use `from __future__ import annotations` at top.
- **Async:** FastAPI endpoints are `async def`. CPU-bound work goes in `asyncio.to_thread()`.
- **Config:** Environment variables accessed via `os.getenv()` with defaults. Never hardcode values.
- **Testing:** pytest + pytest-asyncio. Test files mirror the source tree under `tests/`.
- **Linting:** `ruff` for lint + format, `mypy` for type checking.
- **Imports:** Absolute imports from `lib.*` — the `PYTHONPATH` is set to `/app/src` in Docker.

### SvelteKit (WebUI)

- **Svelte version:** Svelte 5 with runes syntax
- **Reactivity:** Use `$state`, `$derived`, `$effect` runes — NOT the legacy `let` + reactive statements
  ```svelte
  let count = $state(0);
  let doubled = $derived(count * 2);
  $effect(() => { console.log(count); });
  ```
- **Types:** Import shared types from `$lib/types` — do not redefine types inline
- **API calls:** All data fetching goes through `src/lib/api/` modules, not raw `fetch()` in components
- **Adapter:** `@sveltejs/adapter-node` (runs as Node.js server in Docker)
- **Ports:** Dev server on 5173, production container on 3000 (mapped to host 3001)
- **Testing:** Playwright for E2E tests in `tests/` directory

### Protocol Buffers

- Package naming: `fks.{service}.v1` (e.g. `package fks.signals.v1;`)
- All proto files validated and linted with `buf` (`buf.yaml` in repo root)
- Service and message names use `PascalCase`; field names use `snake_case`

---

## Architecture Principles

### CRITICAL: No Autonomous Execution

> **Janus signals NEVER execute directly.** The system is a manual trading co-pilot.
> All signal flow terminates at a human decision point. The execution gate in Ruby
> (`execution_gate.py`) requires explicit operator confirmation before any order
> is placed. `EXECUTION_MODE=paper_trading` by default — never set to `live` without
> full understanding of the implications.

The flow is:
```
Janus (signal generation) → Ruby execution gate → Human confirmation → Broker API
```

### Janus → Ruby Signal Flow

Janus routes signals through Ruby's execution gate (not directly to the broker):
```
EXECUTION_ENDPOINT=http://fks_ruby:8000/api/execute
```
This ensures all trade signals pass through Python's risk layer and audit trail.

### Data Flow

```
External APIs (Massive, Kraken, Rithmic, Binance)
    → Ruby data service (Redis cache → Postgres → API fallback)
        → Janus DataServiceProvider (HTTP client in janus-data crate)
```

Ruby's Python data service is the **single source of truth** for all market data.
Janus consumes it via `PYTHON_DATA_SERVICE_URL=http://fks_ruby:8000`.

### Neuromorphic Architecture (Janus)

Janus is organised into brain-region inspired modules under `src/janus/neuromorphic/`:

> Path note: this code now lives at `crates/janus/neuromorphic/` after the
> rustrade extraction. The brain-region structure described below is unchanged.

| Module            | Brain Region       | Function                                      |
|-------------------|--------------------|-----------------------------------------------|
| `amygdala`        | Fear response      | Circuit breakers, kill switch                 |
| `hippocampus`     | Memory             | Pattern consolidation, replay                 |
| `cerebellum`      | Timing             | Precision coordination                        |
| `prefrontal`      | Decision making    | Strategy selection                            |
| `basal_ganglia`   | Action selection   | Reward learning                               |
| `thalamus`        | Signal routing     | Attention gating                              |
| `hypothalamus`    | Homeostasis        | Resource management                           |
| `visual_cortex`   | Visual processing  | GAF image processing, pattern recognition     |

### Security

- **All secrets in `.env`** — never hardcoded, never committed
- **All access via Tailscale** — no public internet exposure
- **Self-signed certs for HTTPS** on the Tailscale interface (see `scripts/generate-certs.sh`)
- `infrastructure/certs/` is gitignored
- Ports bound to `127.0.0.1` (or `TAILSCALE_IP` for RUSTCODE services) — not `0.0.0.0`
- All containers run with `no-new-privileges:true` and `cap_drop: ALL`

### Databases

- **Postgres** (`fks_postgres`): Two logical databases on one instance
  - `janus_db` — Janus schema (signals, regime, backtest)
  - `ruby_db` — Ruby schema (bars, journal, ORB events, tasks)
- **RUSTCODE Postgres** (`rc-postgres`): Separate instance for RustCode only
- **Redis** (`fks_redis`): Shared FKS instance (namespaced by prefix)
- **RUSTCODE Redis** (`rc-redis`): Separate Redis for RustCode cache
- **QuestDB**: Time-series for market data / tick storage
- **Qdrant**: Vector embeddings (disabled by default, start with `--profile qdrant`)

### Observability

- **Metrics:** Prometheus scrapes all services; Grafana dashboards at `/grafana/`
- **Logs:** All containers log JSON to stdout; Promtail ships to Loki; view in Grafana
- **Tracing:** Jaeger for distributed traces (UI at port 16686)
- **Alerting:** Alertmanager → Discord bridge → `#signals` / `#general` channels

---

## Common Workflows

### Adding a New Rust Crate

1. Create the crate under the appropriate path (e.g. `crates/janus/crates/my-crate/`)
2. Add it to the `members` list in the root `Cargo.toml`
3. Add an entry under `[workspace.dependencies]` if other crates will depend on it
4. Use `dependency = { workspace = true }` in dependent crates

### Adding a New Python Module

1. Create the module under `src/ruby/src/` in the appropriate sub-package
2. Import the logger: `from lib.core.logging_config import get_logger`
3. Add tests under `src/ruby/tests/` mirroring the module path
4. Register any new env vars in `.env.example`

### Adding a New Proto Service

1. Create the `.proto` file under `proto/fks/{service}/v1/`
2. Use package `fks.{service}.v1`
3. Run `./scripts/gen-proto.sh` to regenerate stubs
4. Implement the server trait in the relevant Rust crate

### Updating Docker Images

```bash
# Rebuild and push (CI handles this normally)
docker compose build <service>
docker compose push <service>

# Force full rebuild (no cache)
docker compose build --no-cache <service>
```

---

## Gotchas & Notes

- **`crates/rustcode` dependency mismatch:** RustCode uses older dep versions than the workspace.
  When adding deps to RustCode, check the existing `crates/rustcode/Cargo.toml` versions first
  before using `workspace = true`. The crate is also currently broken (32 errors) — needs decision
  documented in `TODO.md`.
- **Python imports in Docker:** `PYTHONPATH=/app/src` is set in all Python containers. Locally,
  run from `src/ruby/` or set `PYTHONPATH` manually.
- **QuestDB auth:** HTTP console (port 9000) and ILP (9009) are unauthenticated by default.
  Access is restricted via Nginx in production. Set `QDB_HTTP_SECURITY_ENABLED=true` to require auth.
- **Trainer profile:** The `trainer` service is not gated by a profile in the default compose
  (commented out). It runs unless explicitly stopped. GPU requires `nvidia-container-toolkit`.
- **sqlx offline mode:** RUSTCODE builds with `SQLX_OFFLINE=true` — query metadata is pre-generated.
  Run `cargo sqlx prepare --workspace` after changing SQL queries in RUSTCODE.
- **Proto generation:** `grpcio-tools` is excluded from `pyproject.toml` dev extras due to a
  `protobuf` version conflict with `async-rithmic`. Install it ad-hoc: `pip install grpcio-tools`.
- **Model files:** Large `.onnx`, `.pt`, `.safetensors` files are gitignored. Only champion model
  metadata and feature contracts are tracked. Models live in `models/` (partially tracked).
- **External volumes:** Several Docker volumes are declared `external: true` (`fks_postgres_data`,
  `fks_redis_data`, `fks_questdb_data`, `fks_prometheus_data`, `fks_grafana_data`,
  `fks_alertmanager_data`). Create them before first run:
  ```bash
  docker volume create fks_postgres_data
  docker volume create fks_redis_data
  docker volume create fks_questdb_data
  docker volume create fks_prometheus_data
  docker volume create fks_grafana_data
  docker volume create fks_alertmanager_data
  ```

# Futures Trader — Claude Code Project Instructions

## Project Overview

**Futures** is a multi-asset perpetual futures scalper targeting **KuCoin Futures** via CCXT.
It runs in **sim** (paper trading with live WebSocket feeds) or **live** mode. The bot uses a
supervisor pattern — one async worker per asset — with an embedded HTMX dashboard, Redis state
management, Discord notifications, and a CNN-based ML signal gating layer.

**Stack:** Python 3.13 · PyTorch · CCXT Pro · FastAPI · Redis · Docker

| Component | Path | Description |
|-----------|------|-------------|
| **Supervisor + Workers** | `src/main.py` | Entry point — spawns one `AssetWorker` per coin |
| **ML Pipeline** | `src/ml/` | CNN training, inference, feature extraction, labeling |
| **Analysis** | `src/analysis/` | Regime detection, ICT concepts, breakout filters, wave analysis |
| **Indicators** | `src/indicators/` | Full technical indicator library (EMA, RSI, MACD, VWAP, etc.) |
| **Services** | `src/services/` | Config loader, Redis store, Discord notifier, report generator |
| **Web Dashboard** | `src/web/` | FastAPI + HTMX + Jinja2 dashboard |
| **Training Script** | `scripts/train.sh` | Two-tier CNN training pipeline (per-asset → master → git promote) |

---

## Build & Run Commands

```bash
# ── Local development ─────────────────────────────────────────────────────

# Create venv and install deps
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the trading bot (sim mode by default)
python -m src.main

# Run with live trading (requires .env with KuCoin credentials)
TRADING_MODE=live python -m src.main

# ── CNN Training ──────────────────────────────────────────────────────────

# Full pipeline: per-asset CNNs → master model → git promote champions
bash scripts/train.sh

# Train all 10 assets + master model directly
python -m src.ml.train --all --bars 60000 --epochs 60

# Train a single asset
python -m src.ml.train --asset btc

# Dry run (fetch + label + stats, no training)
python -m src.ml.train --asset btc --dry-run

# Custom training params
python -m src.ml.train --asset eth --epochs 100 --bars 40000 --lr 1e-4

# Train master model only (requires per-asset models to exist)
python -m src.ml.train --master-only

# ── Docker ────────────────────────────────────────────────────────────────

# Build and start (2 containers: redis + futures)
docker compose up -d --build

# Logs
docker logs futures-app -f

# Restart (picks up config changes)
docker compose restart futures

# Full rebuild
docker compose down && docker compose up -d --build
```

---

## Testing Commands

```bash
# Run all tests
pytest -v --tb=short -q

# Run a specific test file
pytest tests/test_main_helpers.py -v

# Run a specific test
pytest tests/test_main_helpers.py -k test_calc_size -v

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

---

## Key Files & Conventions

### Repository Layout

```
futures/
├── config/
│   └── futures.yaml              # Single YAML config (env-var interpolation)
├── docker/
│   ├── futures/Dockerfile        # Python 3.13, PYTHONPATH=/app/src
│   └── redis/Dockerfile          # Redis 7.4-alpine
├── docker-compose.yml            # 2 services: redis (6379) + futures (8081)
├── models/                       # CNN checkpoints (.pt) + metadata (.json)
├── scripts/
│   └── train.sh                  # Full training pipeline script
├── src/
│   ├── main.py                   # ★ ENTRY POINT — supervisor + AssetWorker (~2800 lines)
│   ├── ml/                       # CNN training & inference
│   │   ├── features.py           # 20-channel feature extractor (N_FEATURES=20)
│   │   ├── labeler.py            # Breakout label generation + kline fetching
│   │   ├── dataset.py            # AssetDataset + PortfolioDataset (precomputed features)
│   │   ├── model.py              # PerAssetCNN (72K params) + MasterCNN
│   │   ├── train.py              # Training loop (focal loss, mixup, cosine LR)
│   │   ├── inference.py          # CNNInference + MasterInference (live gating)
│   │   └── kline_cache.py        # Redis page/dataset cache for training data
│   ├── analysis/
│   │   ├── regime_hmm.py         # 3-state Gaussian HMM regime detector
│   │   ├── ict.py                # ICT: FVGs, Order Blocks, Liquidity Sweeps
│   │   ├── breakout_filters.py   # NR7, VWAP, EMA trend, volume, ATR gates
│   │   ├── signal_quality.py     # Signal quality scoring
│   │   ├── volatility.py         # Volatility analysis + K-Means clustering
│   │   ├── wave_analysis.py      # Wave analysis (dynamic EMA, bull/bear waves)
│   │   └── cvd.py                # Cumulative Volume Delta
│   ├── indicators/               # Full indicator library
│   │   ├── momentum/             # RSI, Stochastic
│   │   ├── trend/                # EMA, MACD, SMA, WMA, Bollinger, ATR
│   │   ├── volume/               # VWAP, VZO
│   │   └── other/                # CMF, Choppiness, Keltner, SAR, etc.
│   ├── services/
│   │   ├── config_loader.py      # YAML → FuturesConfig dataclass
│   │   ├── redis_store.py        # All Redis ops (state, PnL, orders, heartbeats)
│   │   ├── discord_notify.py     # Discord webhook alerts
│   │   ├── report_generator.py   # Grok-powered daily/weekly reports
│   │   └── asset_registry.py     # KuCoin contract specs (50+ symbols)
│   ├── utils/
│   │   ├── logging_config.py     # setup_logging() + get_logger()
│   │   ├── performance.py        # Sharpe, Sortino, Calmar, expectancy, drawdown
│   │   └── system_monitor.py     # MemoryMonitor + MaintenanceChecker
│   └── web/
│       ├── app.py                # FastAPI + HTMX dashboard (port 8080)
│       ├── static/app.css        # Dark theme design system
│       └── templates/            # Jinja2 templates + HTMX partials
├── tests/                        # pytest test suite
├── pyproject.toml                # Project metadata, ruff/mypy config
├── requirements.txt              # pip dependencies
├── run.sh                        # Management script
└── todo.md                       # Project roadmap and task tracking
```

### Configuration

Single YAML file: `infrastructure/config/futures.yaml` with `${ENV_VAR:-default}` interpolation.

Major sections: `mode`, `exchange`, `assets` (10 coins), `capital`, `risk`, `ml`,
`strategy`, `wave`, `volatility`, `quality`, `optuna`, `candles`, `streams`, `redis`,
`simulation`, `monitoring`, `discord`, `logging`.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `KUCOIN_API_KEY` | Live only | — | KuCoin API key |
| `KUCOIN_API_SECRET` | Live only | — | KuCoin API secret |
| `KUCOIN_PASSPHRASE` | Live only | — | KuCoin passphrase |
| `REDIS_PASSWORD` | Yes | — | Redis auth password |
| `REDIS_URL` | No | `redis://futures-redis:6379/0` | Redis connection URL |
| `XAI_API_KEY` | For reports | — | xAI API key for Grok reports |
| `TRADING_MODE` | No | `sim` | `sim` or `live` |
| `CAPITAL` | No | `30.0` | Starting balance USDT |
| `DISCORD_WEBHOOK_URL` | No | — | Discord notifications |
| `LOG_LEVEL` | No | `INFO` | Logging level |

### Docker Services

| Service | Container | Port | Notes |
|---------|-----------|------|-------|
| Redis | futures-redis | 127.0.0.1:6379 | State, PnL, signals, heartbeats |
| Trader + Dashboard | futures-app | 0.0.0.0:8081 → 8080 | Bot + HTMX web UI |

---

## Code Conventions

### Python

- **Version:** Python 3.13+
- **Type hints:** Required on all public functions. Use `from __future__ import annotations`.
- **Logging:** Use the project logger:
  ```python
  from src.utils.logging_config import get_logger
  logger = get_logger("module.name")
  ```
  For ML training code, use stdlib `logging.getLogger("train")`.
- **Async:** The main trading loop is fully async (`asyncio`). CPU-bound work (Optuna, ML
  inference) runs in `asyncio.to_thread()` or thread pool executors.
- **Config:** Environment variables via `os.getenv()` with defaults. Secrets in `.env` (gitignored).
- **Linting:** `ruff` (target py313, 100-char lines). Config in `pyproject.toml`.
- **Type checking:** `mypy` (relaxed — `ignore_missing_imports = true`).

### ML Code (`src/ml/`)

- **Framework:** PyTorch (CPU and CUDA)
- **Features:** 20 channels x 60-bar window. Feature list defined in `features.py`.
  A shared `_compute_channels()` function is the single source of truth for all 20
  feature channels — both `extract_features()` (live inference) and
  `precompute_all_features()` (bulk training) delegate to it, eliminating code
  duplication and preventing silent train/inference divergence.
- **Training perturbation (channels 7-9):** Channels 7 (book_imbalance), 8 (wave_ratio),
  and 9 (vol_percentile) depend on live orderbook/wave/vol state unavailable in
  historical training data. During training (`training=True`), these channels use
  random walks instead of constants so the CNN learns useful filters. During live
  inference, actual values are broadcast as before.
- **Labels:** Breakout-based labeling via `generate_labels_breakout()` in `labeler.py`.
  Labels are {0=flat, 1=long, 2=short} based on future ATR-bracket outcomes.
- **Models:** `PerAssetCNN` (per-coin, 3-class) and `MasterCNN` (portfolio risk, binary).
  Saved as `.pt` + `.json` sidecar in `models/`.
- **MasterCNN architecture:** Uses a shared `_AssetEncoder` (with configurable
  `encoder_dropout`, default 0.25 for master vs 0.15 for per-asset) to encode each
  asset's window into a 48-dim embedding (reduced from 64 to limit overfitting),
  then applies `_CrossAssetAttention` (multi-head self-attention with 4 heads + FFN)
  to learn inter-asset correlations before a reduced-capacity FC risk head
  (96→24→1). ~142K parameters (down from ~200K). Master-specific CLI args:
  `--master-embedding-dim`, `--master-dropout`, `--master-encoder-dropout`.
- **Training recipe (per-asset):** Focal loss (gamma=2.0), mixup (alpha=0.2), label
  smoothing (0.10), warmup+cosine LR, early stopping on macro F1, class weight
  boosting, gradient accumulation (4x), SWA at 60%.
- **Training recipe (master):** Now matches per-asset sophistication — class-weighted
  BCEWithLogitsLoss, mixup, gradient accumulation (4x), SWA (activates at 75%),
  EMA-smoothed early stopping on val F1, encoder warm-start from averaged per-asset
  weights (shape-mismatch tolerant for differing embedding_dim), minimum quality
  gate (F1 >= 0.35), degenerate model rejection, model confidence analysis.
- **Temperature calibration:** Post-training `scipy.optimize.minimize_scalar` finds
  the optimal softmax temperature T on the validation set, minimising NLL. Stored in
  metadata as `temperature`, `ece_before`, `ece_after`. The inference layer applies
  `logits / T` before softmax for well-calibrated confidence scores.
- **Encoder warm-start:** `_init_encoder_from_per_asset()` averages all available
  per-asset encoder weights and loads them into the master model's shared encoder,
  giving it a head start from pre-trained feature representations. Shape-mismatched
  layers (e.g. when master embedding_dim=48 vs per-asset embedding_dim=64) are
  automatically skipped with a log message, so blocks 1-2 still warm-start.
- **Inference:** `CNNInference` wraps a trained model for live signal gating.
  `MasterInference` provides portfolio-level risk scoring.

### Trading Architecture

The signal pipeline is rule-based:
```
Tick stream → 5s candles → Indicators (EMA, AO, wave, vol, regime)
  → Signal quality score → CNN confidence gate → Entry/Exit decision
```

Position management: entry with confirmation bars, stacking up to `max_stack` adds
with wave + regime gates, close on TP/SL/reversal with min_hold + min_profit guards.

---

## Architecture Principles

### Supervisor + Worker Pattern

`main()` spawns one `AssetWorker` per enabled asset as an `asyncio.Task`. The supervisor
loop monitors heartbeats, auto-restarts crashed workers, enforces portfolio-level circuit
breakers (aggregate loss, margin cap), and handles exchange session recycling.

### Signal Flow

```
WebSocket Feeds (trades + orderbook)
  → AssetWorker._trading_loop()
    → Build 5s candles from ticks
    → Compute indicators (wave, vol, regime, AO, EMA, imbalance)
    → Compute signal quality score
    → CNN gate (if ml.enabled and model exists)
    → Entry / Add / Close decision
    → Execute via ccxt (live) or simulate (sim)
    → Log to Redis + Discord
```

### CNN Integration

CNN models are optional — the bot gracefully disables ML features when no `.pt` files
exist. When enabled:
- `CNNInference.predict()` returns `(signal, probability)` from the per-asset model
- Signal must match the rule-based signal direction AND exceed the confidence threshold
- Confidence scores are temperature-calibrated (`logits / T`) for well-calibrated probabilities
- `MasterInference.portfolio_risk()` provides a portfolio-level risk score using
  cross-asset attention to detect dangerous multi-asset configurations
- Both run on CPU in the async event loop (inference is fast — ~1ms per call)

### Redis Key Patterns

| Pattern | Type | Contents |
|---------|------|----------|
| `futures:signals:{asset}` | List | Trading signals |
| `futures:pnl:{asset}` | Sorted Set | PnL entries (score=timestamp) |
| `futures:orders:{asset}` | List | Order history |
| `futures:worker_state` | Hash | Per-asset worker state |
| `futures:heartbeat:{asset}` | String | Worker heartbeat (TTL 120s) |
| `futures:reports:{type}:{date}` | String | Generated reports |
| `futures:candles:{asset}:{tf}` | String | Cached candle data |
| `train:klines:*` | String | ML training kline cache |

---

## Common Workflows

### Adding a New Asset

1. Add the symbol mapping in `src/services/asset_registry.py` (`ASSET_REGISTRY` dict)
2. Add the asset config block in `infrastructure/config/futures.yaml` under `assets:`
3. Add the asset key → KuCoin symbol mapping in `src/ml/train.py` (`ASSET_SYMBOLS` dict)
4. Train a CNN model: `python -m src.ml.train --asset <key> --bars 60000`

### Retraining CNN Models

```bash
# Delete old models (required if N_FEATURES changed)
rm models/cnn_*.pt models/cnn_*.json

# Full pipeline (trains all assets → master → promotes champions to git)
bash scripts/train.sh

# Or train directly
python -m src.ml.train --all --bars 60000 --epochs 60
```

### Adding a New Feature Channel to CNN

1. Add the computation in `_compute_channels()` in `src/ml/features.py` — this is the
   **single source of truth** for all 20 channels (both training and inference)
2. Update `N_FEATURES` constant (currently 20)
3. Update `feature_names()` list
4. Delete old models and retrain — `N_FEATURES` change is a breaking model change

### Modifying Trading Logic

All trading logic lives in `src/main.py` inside the `AssetWorker` class:
- `_trading_loop()` — main loop (runs every `loop_sleep_sec`)
- `_handle_trades()` / `_handle_orderbook()` — WebSocket feed handlers
- Signal computation: `compute_quality()`, `wave_gate_ok()`, `regime_stack_ok()`
- Position management: entry, stacking, close, reversal logic
- Adaptive TP: `adaptive_tp()` varies take-profit by volatility + regime

---

## CNN Training Reference

### Training Defaults

| Parameter | Default | Notes |
|-----------|---------|-------|
| `--bars` | 60,000 | ~42 days of 1m data (increased from 30K for better generalization) |
| `--epochs` | 60 | Early stopping patience=20 (EMA-smoothed) |
| `--window` | 60 | 1 hour of 1m bars per sample |
| `--loss-type` | `focal` | FocalLoss(γ=2.0) — focuses on hard cases |
| `--class-weight-boost` | 1.0 | Extra multiplier for long/short weights (1.0 = base inverse-frequency only) |
| `--early-stop-metric` | `macro_f1` | Avg F1 across flat/long/short |
| `--early-stop-patience` | 20 | EMA-smoothed (α=0.3) to reduce val noise |
| `--min-val-accuracy` | 0.38 | Min macro_f1 to save model |
| `--mixup-alpha` | 0.20 | Beta distribution; λ clamped ≥ 0.5 |
| `--label-smoothing` | 0.10 | Prevents overconfident predictions |
| `--lr` | 3e-4 | Lower LR for stable training; warmup (5 ep) + cosine decay + SWA |
| `--weight-decay` | 5e-4 | Stronger L2 regularization (increased from 1e-4) |
| `--batch-size` | 64 | Effective 256 via 4× gradient accumulation |

### Master-Specific Defaults

| Parameter | Default | Notes |
|-----------|---------|-------|
| `--master-embedding-dim` | 48 | Smaller than per-asset's 64 to reduce capacity (~142K vs ~200K params) |
| `--master-dropout` | 0.4 | Higher than per-asset for stronger regularization |
| `--master-encoder-dropout` | 0.25 | Higher than per-asset encoder dropout (0.15) |

### Training Enhancements

| Feature | Description |
|---------|-------------|
| **SE Attention** | Squeeze-and-Excitation blocks after each conv layer learn per-channel importance weights, improving minority class detection |
| **SWA** | Stochastic Weight Averaging activates at 60% of per-asset training (75% for master) to smooth val loss instability |
| **Gradient Accumulation** | 4-step accumulation -> effective batch size 256 for more stable gradients |
| **Focal + Mixup Fix** | Soft-label path now correctly applies focal modulation + class weights (was bypassed before) |
| **Mixup lambda Clamp** | `lam = max(lam, 1-lam)` ensures original sample always dominates the mix |
| **EMA Early Stopping** | Early-stop metric smoothed with EMA (alpha=0.3) to prevent premature stopping from val noise |
| **Directional Gating** | Models with long or short recall < 15% are flagged in metadata (`directional_gate: long_only/short_only/flat_only`) so inference can gate per-direction |
| **Temperature Calibration** | Post-training `scipy.optimize.minimize_scalar` finds optimal softmax temperature T on val set by minimising NLL, stored in metadata (`temperature`, `ece_before`, `ece_after`) |
| **Cross-Asset Attention** | MasterCNN uses multi-head self-attention (4 heads) over asset embeddings before the FC risk head, learning inter-asset correlations (e.g. BTC dumping + SOL breakout = high risk) |
| **Encoder Warm-Start** | Master encoder is initialised from averaged per-asset encoder weights, giving it pre-trained feature representations rather than random init |
| **Training Perturbation** | Channels 7-9 (book_imbalance, wave_ratio, vol_percentile) use random walks during training instead of constant broadcast, fixing the train/inference distribution mismatch |
| **ATR-Relative Labels** | PortfolioDataset uses ATR-relative drawdown thresholds (2x ATR) instead of fixed 2% — adapts per-asset based on current volatility |
| **Shared Feature Code** | `_compute_channels()` is the single source of truth for all 20 feature channels, eliminating duplication between `extract_features()` and `precompute_all_features()` |

### Feature Vector (20 channels)

| # | Name | Range | Description |
|---|------|-------|-------------|
| 0 | log_return | ~[-1,1] | log(close_t / close_{t-1}) |
| 1 | norm_close | ~[-3,3] | Z-score of close over window |
| 2 | norm_atr | [0,1] | ATR-14 / close |
| 3 | volume_ratio | [0,5+] | volume / 20-bar mean volume |
| 4 | rsi | [0,1] | RSI-14 / 100 |
| 5 | range_tightness | [0,1] | 20-bar range / ATR, normalized |
| 6 | close_vs_range | [0,1] | Position within 20-bar range |
| 7 | book_imbalance | [0,1] | bid / (bid + ask) — scalar broadcast |
| 8 | wave_ratio | [-1,1] | Wave state ratio, normalized |
| 9 | vol_percentile | [0,1] | ATR percentile — scalar broadcast |
| 10 | body_ratio | [0,1] | |close - open| / (high - low) |
| 11 | upper_wick | [0,1] | Upper shadow ratio |
| 12 | lower_wick | [0,1] | Lower shadow ratio |
| 13 | candle_dir | {-1,0,1} | Sign of (close - open) |
| 14 | hurst_exponent | [0,1] | R/S Hurst: <0.4 reverting, >0.6 trending |
| 15 | atr_trend | [0,1] | ATR expanding (1.0) vs contracting (0.0) |
| 16 | volume_trend | [0,1] | 5-bar volume slope, normalized |
| 17 | norm_velocity | [-1,1] | 3-bar momentum / rolling stdev, scaled |
| 18 | price_acceleration | [-1,1] | Change of velocity (2nd derivative) |
| 19 | market_phase | [0,1] | Phase: 0=accumulation, 0.33=uptrend, 0.67=downtrend, 1=distribution |

### Labeling

Labels are generated by `generate_labels_breakout()` in `labeler.py`:
1. Detect consolidation zones (20-bar range < 5.5× ATR)
2. Detect breakouts from consolidation
3. Walk forward with ATR bracket (TP=1.5×ATR, SL=1.0×ATR, max 90 bars)
4. Label: flat (no breakout or no resolution), long (TP hit upward), short (TP hit downward)

---

## Gotchas & Notes

- **`src/main.py` is large (~2800 lines)** — it contains the supervisor, all worker logic,
  and trading functions. This is intentional to keep the hot path in one file, but be aware
  of its size when making changes.
- **Feature precomputation is critical** — `AssetDataset` precomputes all 20 features once
  in `__init__` via `precompute_all_features()`. Without this, training is ~12,000x slower
  (8s/batch vs 0.7ms/batch) because `extract_features()` recomputes indicators per sample.
- **Feature code is shared** — both `extract_features()` and `precompute_all_features()`
  delegate to `_compute_channels()`. Never duplicate feature logic — edit the shared
  function only.
- **Channels 7-9 use training perturbation** — during training, `precompute_all_features()`
  is called with `training=True`, generating random walks for book_imbalance, wave_ratio,
  and vol_percentile. During live inference, `extract_features()` passes real values. This
  ensures the CNN learns useful filters for these channels.
- **N_FEATURES changes are breaking** — any change to the feature count requires deleting
  all existing `.pt` model files and retraining from scratch.
- **Master model uses timestamp alignment** — `train_master()` aligns multi-asset
  DataFrames by timestamp (not just tail-trimming) to ensure bars correspond in time.
- **Master encoder warm-start** — `_init_encoder_from_per_asset()` averages available
  per-asset encoder weights and loads them into the master's shared encoder, so train
  per-asset models first before running `--master-only`.
- **Temperature calibration runs automatically** — `_calibrate_temperature()` runs after
  per-asset training and stores the optimal temperature in model metadata. If `scipy`
  fails, it falls back to T=1.0 gracefully.
- **PortfolioDataset uses ATR-relative labels** — `drawdown_pct` is now an ATR multiplier
  (default 2.0 = 2x ATR-14) rather than a fixed percentage, adapting thresholds per asset.
- **CNN is optional** — the bot works fine without any `.pt` files. CNN gating is silently
  disabled per-asset when no model file exists.
- **Sim vs Live** — in sim mode, fills are simulated locally with configurable slippage.
  In live mode, actual orders are placed via CCXT. The `TRADING_MODE` env var controls this.
- **Redis is required** — the bot needs Redis for state, heartbeats, and inter-component
  communication. An in-memory fallback exists but is limited.
- **Model files are gitignored by default** — use `git add -f models/cnn_*.pt` to promote
  champion models. The `scripts/train.sh` script handles this automatically.
- **Training uses tqdm progress bars** — batch-level progress, per-epoch summaries, kline
  fetch progress, and asset counters are all displayed during training.
- **The `fks/` directory** is a reference copy of the FKS (Freddy Krueger Sniper) monorepo,
  a more complex CME/crypto trading platform. It's used as a source of algorithms and patterns
  but is not part of the futures build or runtime.
