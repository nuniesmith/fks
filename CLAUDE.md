# FKS — Claude Code Project Instructions

## What this repo is

**`fks-full` is the operational/orchestration root** for the FKS trading
platform. It runs the production stack, owns infrastructure config
(Docker, nginx, Prometheus, …), and houses the deployment scripts.

> 🎯 **Direction:** this repo is heading toward a **private orchestrator**
> role. Each reusable piece (rustrade framework, indicators-ta,
> exchange-apiws, spawner, janus, ruby, fks-web) is being prepared to
> live in its own repo and ship via crates.io / PyPI / npm. The full
> plan is in [`SPLIT_PLAN.md`](SPLIT_PLAN.md).

**Stack:** Rust + Python + SvelteKit + Docker. ~15 containers post-cleanup.

| Sub-codebase | Type | Owns its own |
|--|--|--|
| `crates/rustrade/` | Rust workspace (framework) | `CLAUDE.md` + `TODO.md` + `README.md` + `CONTRIBUTING.md` |
| `crates/janus/` | Rust workspace (ML engine) | `CLAUDE.md` + `TODO.md` + `README.md` + `JANUS_EXTRACTION_PLAN.md` |
| `crates/indicators-ta/` | Standalone publishable crate | `CLAUDE.md` + `TODO.md` + `README.md` |
| `crates/exchange-apiws/` | Standalone publishable crate | `CLAUDE.md` + `TODO.md` + `README.md` |
| `crates/spawner/` | Bot lifecycle service | `CLAUDE.md` + `TODO.md` + `README.md` |
| `src/ruby/` | Python trading system | `CLAUDE.md` + `TODO.md` + `README.md` |
| `src/web/` | SvelteKit dashboard | `CLAUDE.md` + `TODO.md` + `README.md` |
| `crates/kucoin/` | 🪦 legacy, scheduled for deletion | see its `README.md` |
| `crates/rustcode/` | 🪦 paused, scheduled for deletion | see its `TODO.md` |

> **When working in any of those directories, read the sub-CLAUDE first.**
> This root file only covers cross-cutting concerns: how the pieces wire
> together at the Docker layer, top-level conventions, and the split
> direction. Anything specific to a sub-codebase lives in its own
> CLAUDE.md.

---

## Service map

| Service | Path | Host port(s) | Notes |
|---------|------|--------------|-------|
| **Janus** | `crates/janus/` | 7000 / 9051 / 9092 | Rust ML engine. Uses `rustrade-supervisor` (cross-workspace path dep). |
| **Ruby** | `src/ruby/` | 8000 / 8050 / 8080 | Python (FastAPI + supervisord). Data source of truth. |
| **WebUI** | `src/web/` | 3001 | SvelteKit 5 dashboard. Includes `/bots` for spawner control. |
| **Spawner** | `crates/spawner/` | 8090 | Bot container lifecycle. Mounts `/var/run/docker.sock`, writes Prometheus SD. |
| **rustrade** | `crates/rustrade/` | — | Library workspace (no service). Consumed by janus + spawner-example. |
| **Trainer** | — | 8200 | GPU CNN retraining (profile: training). |
| **Postgres** | — | 5432 | `janus_db` + `ruby_db` on one instance. |
| **Redis** | — | 6379 | Shared pub/sub, state, caching. |
| **QuestDB** | — | 9000 / 9009 / 8812 | Time-series market data. |
| **Qdrant** | — | 6333 / 6334 | Vector embeddings (optional). |
| **Nginx** | — | 80 | Reverse proxy (TLS via Tailscale). Sets `X-Internal-Token`. |
| **Prometheus** | — | 9090 | Metrics. Scrapes `fks-bots` via spawner's file_sd. |
| **Grafana** | — | 3000 | Served at `/grafana/`. |
| **Alertmanager** | — | 9093 | Alerts + Discord bridge. |
| **Loki + Promtail** | — | 3100 | Log aggregation. |
| **Jaeger** | — | 16686 | Distributed tracing UI (memory storage). |

All ports bind to `127.0.0.1` — only reachable via localhost or
Tailscale. Spawned `fks-bot-*` containers go on `fks_network` with
`cap_drop: ALL`, `no-new-privileges:true`, forced `fks.bot=true` +
`fks.bot_id=<uuid>` + `fks.mode=...` labels, and expose `:9091/metrics`.

---

## Build & run commands (top level)

```bash
# Whole stack
./run.sh all                # build + start everything
./run.sh fresh              # rebuild images + restart
./run.sh health             # check service /health endpoints
./run.sh logs <service>     # tail one service

# Per-stack details live in the sub-CLAUDE files. Cheat sheet:
cd crates/rustrade && cargo check --workspace
cd crates/janus    && cargo check --workspace
cd crates/spawner  && cargo test --workspace        # 11 unit + 10 integration
cd src/web         && npm run check && npm run build
cd src/ruby        && python -m pytest tests/
```

### Docker compose profiles

| Profile | Adds |
|---------|------|
| `training` | GPU trainer container |
| `base` | Python base image (CI cache layer) |
| `qdrant` | Qdrant vector database (now always-on; profile is legacy) |

---

## Architecture principles

### CRITICAL: no autonomous execution

The system is a **manual trading co-pilot**. All signal flow terminates
at a human decision point. The Ruby `execution_gate.py` requires
explicit operator confirmation before any order. `EXECUTION_MODE=paper_trading`
is the default — never flip to `live` without full understanding.

```
Janus (signal) → Ruby execution gate → Human confirmation → Broker API
```

### Data flow

Ruby's Python data service is the **single source of truth** for market
data. Janus consumes it via `PYTHON_DATA_SERVICE_URL=http://fks_ruby:8000`.
Don't add a second data path elsewhere.

### Security

- All access via Tailscale HTTPS. No external ports.
- Nginx terminates TLS with Tailscale certs (`infrastructure/certs/`, gitignored).
- Internal services trust `X-Internal-Token` (set by nginx on every proxied request, validated by the spawner; other services will follow).
- All containers run with `no-new-privileges:true` and `cap_drop: ALL`.
- Secrets in `.env` only — never hardcoded, never committed.

### Databases

| DB | Schema location | Used by |
|--|--|--|
| `janus_db` (Postgres) | `crates/janus/sql/` | Janus services |
| `ruby_db` (Postgres) | `src/ruby/sql/` (incl. `007_spawner.sql` for `bot_runs`/`bot_configs`) | Ruby, Spawner |
| QuestDB | — | Tick / bar storage |
| Qdrant | — | Vector embeddings (optional) |

### Observability

- **Metrics:** Prometheus scrapes spawner self-metrics + dynamic `fks-bots` via file_sd.
- **Logs:** All containers log JSON to stdout; Promtail ships to Loki; view in Grafana.
- **Tracing:** Jaeger (memory storage; not durable).
- **Alerting:** Alertmanager → Discord bridge.

---

## Cross-cutting code conventions

### Rust

- **Edition 2024**, minimum `rust-version = "1.94.1"` workspace-wide.
- **Error handling:** `anyhow` in binaries, `thiserror` in libraries.
- **Async:** Tokio. Each crate picks the minimum features it needs.
- **Lints:** workspace-wide clippy + `unsafe_code = "warn"`. Fix warnings before committing.
- **Cross-workspace path deps:** when a crate (e.g. `rustrade-supervisor`) needs to be consumed via path from a *foreign* workspace (e.g. `crates/janus/bin/janus/`), pin its deps with explicit versions (not `workspace = true`). This is also what crates.io publishing requires.

### Python (Ruby)

- **Python 3.13+.** Type hints required. `from __future__ import annotations` everywhere.
- **Logging:** project logger via `lib.core.logging_config.get_logger`. Never `print` or `logging.basicConfig`.
- **Linting:** `ruff` (check + format) + `mypy`.

### SvelteKit (WebUI)

- **Svelte 5 runes only** (`$state`, `$derived`, `$effect`, `$props`, `$snippet`).
- **No `slot="..."`** — use snippets.
- **`api` from `$lib/api/client.ts` is an object**, not a callable. `api.get(url)`, `api.post(url, body)`, …
- **Adapter:** `@sveltejs/adapter-node`. Dev on 5173, prod container on 3000 (mapped to host 3001).

### Protocol Buffers

- All `.proto` files in `proto/fks/`.
- Package naming: `fks.<service>.v1` (e.g. `fks.signals.v1`, `fks.execution.v1`).
- `src/proto/` is the `fks-proto` Rust crate that compiles the protos.
- Regenerate with `./scripts/gen-proto.sh`. `buf` is the linter.

---

## Common workflows

### Adding a new Rust sub-crate

Decide first: is it a member of an existing nested workspace (rustrade,
janus, rustcode), or a new standalone? Follow the host workspace's
conventions. Don't add new top-level workspace members to the **root**
`Cargo.toml` unless the crate is genuinely standalone — the trend is
that everything lives inside a sub-workspace that will eventually be a
separate repo.

### Adding a new service to the stack

1. Decide which sub-codebase owns it.
2. Add the Dockerfile to `infrastructure/docker/services/<name>/` (or
   reuse a base image from `infrastructure/docker/base/`).
3. Add the compose entry to `docker-compose.yml` with the standard
   security defaults (`security_opt: no-new-privileges:true`,
   `cap_drop: ALL`, `restart: unless-stopped`, healthcheck, logging).
4. Bind the host port to `127.0.0.1` only.
5. If it needs scraping, add a Prometheus scrape config.
6. If it needs to be reachable via the WebUI, add an nginx location block.

### Updating Docker images

```bash
docker compose build <service>
docker compose push <service>
docker compose build --no-cache <service>   # force fresh
```

### Regenerating proto stubs

```bash
./scripts/gen-proto.sh
```

---

## Gotchas

- **The root workspace is currently broken.** `src/spawner/` was moved to `crates/spawner/` (uncommitted at time of writing) but `Cargo.toml`'s `members` still lists `src/spawner`. Either commit the move and update the workspace, or revert.
- **rustcode + openclaw are scheduled for deletion.** Don't sink time into reviving them. The Claude/Zed CLI + Claude API path covers the assistant need today. See `SPLIT_PLAN.md` for the removal recipe.
- **`crates/kucoin/`** is the pre-rustrade legacy bot, also scheduled for deletion. Use `crates/rustrade/examples/kucoin-v2/` as the reference instead.
- **External volumes** are declared `external: true` in `docker-compose.yml` (`prometheus_data`, `grafana_data`, `alertmanager_data`). Create them once before first run:
  ```bash
  docker volume create prometheus_data
  docker volume create grafana_data
  docker volume create alertmanager_data
  ```
- **Model files** are gitignored (`.onnx`, `.pt`, `.safetensors`). Only champion model metadata + feature contracts are tracked. The binaries live in `models/` and get mounted into Ruby/Trainer.
- **Tailscale certs** under `infrastructure/certs/` are gitignored. Generate with `scripts/generate-certs.sh` after `tailscale serve` is set up.

---

## Where to dig deeper

- **The split plan:** [`SPLIT_PLAN.md`](SPLIT_PLAN.md) — how and when each piece becomes its own repo.
- **Janus extraction roadmap:** [`crates/janus/JANUS_EXTRACTION_PLAN.md`](crates/janus/JANUS_EXTRACTION_PLAN.md) — phase-by-phase Janus carve-up.
- **rustrade design invariants:** [`crates/rustrade/CONTRIBUTING.md`](crates/rustrade/CONTRIBUTING.md) — the 5 rules that held through 10 PRs.
- **The cross-cutting roadmap:** [`TODO.md`](TODO.md).
- **Per-sub-codebase CLAUDE.md files** — read these *first* when working in that directory; they're more specific than this file.
