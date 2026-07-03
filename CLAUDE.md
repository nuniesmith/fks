# FKS — Claude Code Project Instructions

## What this repo is

**`fks-full` is the operational/orchestration root** for the FKS trading
platform. It runs the production stack, owns infrastructure config (Docker,
nginx, Prometheus, …), houses the deployment scripts, and **consumes** the
reusable pieces from their own repos / crates.io.

> 🎯 **The split already happened.** `rustrade`, `janus`, `indicators-ta`, and
> `exchange-apiws` are their own repos; the libraries are on crates.io. This
> repo wires them together at runtime and is heading toward a **private
> orchestrator** role (production strategies + secrets + topology). The repo
> map is in [`docs/architecture/REPO_TOPOLOGY.md`](docs/architecture/REPO_TOPOLOGY.md);
> remaining moves are in [`SPLIT_PLAN.md`](SPLIT_PLAN.md).

**Stack:** Rust + SvelteKit + Docker. ~14 containers. (The Python "Ruby"
data/engine/trainer service was removed — janus is the platform now. See
[`docs/architecture/RUST_MIGRATION.md`](docs/architecture/RUST_MIGRATION.md).)

### External repos (consumed, not contained)

| Repo | Role | Consumed as |
|------|------|-------------|
| [`rustrade`](https://github.com/nuniesmith/rustrade) | trading framework | crates.io `rustrade-framework` 0.4 (imports as `rustrade`) |
| [`janus`](https://github.com/nuniesmith/janus) | trading brain | Docker image (`git clone` at `JANUS_REF`) + `jflow-*` crates |
| [`indicators-ta`](https://github.com/nuniesmith/indicators-ta) | TA math | crates.io `indicators-ta` 0.2 (imports as `indicators`) |
| [`exchange-apiws`](https://github.com/nuniesmith/exchange-apiws) | exchange REST/WS | crates.io `exchange-apiws` 0.8 |
| [`fks-web`](https://github.com/nuniesmith/fks-web) | SvelteKit UI | Docker image (`git clone` at `WEB_REF`) |

### Lives in this repo

| Path | Type | Owns its own docs |
|--|--|--|
| `crates/spawner/` | Bot-container lifecycle service | `CLAUDE.md` + `TODO.md` + `README.md` |
| `src/web/` | SvelteKit dashboard | `CLAUDE.md` + `TODO.md` + `README.md` |
| `src/proto/` | `fks-proto` crate (protobuf) | — |
| `src/sql/` | DB bootstrap baked into the postgres image (`janus/`, `spawner/`) | — |
| `bots/fks-bot-example/` | reference bot — consumes the published crates | own `[workspace]` |
| `bots/crypto-demo/` | working multi-symbol demo bot (paper by default) | own `[workspace]` |
| `bots/rustrade-exchange-apiws/` | `rustrade::ExchangeClient` over `exchange-apiws` (KuCoin) — the live order path | `README.md` + own `[workspace]` |
| `strategies/` | private trading IP (consumes the published crates) | *(planned)* |

> `bots/fks-bot-example/` is the canonical example of consuming the published
> crates: a standalone crate depending on `rustrade-framework` from crates.io.
> It's what the spawner launches and the template for real bots.

> **When working in any sub-directory, read its sub-CLAUDE first.** This root
> file covers cross-cutting concerns: how the pieces wire together at the
> Docker layer, top-level conventions, and the consumption direction.

---

## Service map

| Service | Source | Host port(s) | Notes |
|---------|--------|--------------|-------|
| **Janus** | `nuniesmith/janus` (git-clone image) | 7000 / 7001 / 8080 / 8180 | Rust trading brain + native data ingestion + burn ML. The platform. |
| **WebUI** | `src/web/` (or `nuniesmith/fks-web`) | 3001 | SvelteKit 5 dashboard. Includes `/bots` for spawner control. |
| **Spawner** | `crates/spawner/` | 8090 | Bot container lifecycle. Mounts `/var/run/docker.sock`, writes Prometheus SD. |
| **Postgres** | — | 5432 | `janus_db` + `ruby_db` on one instance (`ruby_db` = spawner schema). |
| **Redis** | — | 6379 | Shared pub/sub, state, caching. |
| **QuestDB** | — | 9000 / 9009 / 8812 | Time-series market data. |
| **Qdrant** | — | 6333 / 6334 | Vector embeddings (optional). |
| **Nginx** | — | 80 | Reverse proxy (TLS via Tailscale). Sets `X-Internal-Token`. |
| **Prometheus** | — | 9090 | Metrics. Scrapes `fks-bots` via spawner's file_sd. |
| **Grafana** | — | 3000 | Served at `/grafana/`. |
| **Alertmanager** | — | 9093 | Alerts + Discord bridge. |
| **Loki + Promtail** | — | 3100 | Log aggregation. |
| **Jaeger** | — | 16686 | Distributed tracing UI (memory storage). |

All ports bind to `127.0.0.1` — only reachable via localhost or Tailscale.
Spawned `fks-bot-*` containers go on `fks_network` with `cap_drop: ALL`,
`no-new-privileges:true`, forced `fks.bot=true` + `fks.bot_id=<uuid>` +
`fks.mode=...` labels, and expose `:9091/metrics`.

---

## Build & run commands (top level)

```bash
# Whole stack
./run.sh all                # build + start everything
./run.sh fresh              # rebuild images + restart
./run.sh health             # check service /health endpoints
./run.sh logs <service>     # tail one service

# Rust that lives HERE (the external repos build in their own repos / via git-clone):
cd src/proto       && cargo check                      # fks-proto
cd crates/spawner  && cargo test --workspace           # 11 unit + 10 integration
cd src/web         && npm run check && npm run build
```

> To build a service from an external repo locally, set its `*_REPO`/`*_REF`
> (e.g. `JANUS_REPO`, `JANUS_REF`) or work in that repo directly. Don't
> re-vendor an external repo back into `crates/`.

### Docker compose profiles

| Profile | Adds |
|---------|------|
| `demo` | `crypto-demo` paper bot driving the janus brain end-to-end |
| `qdrant` | Qdrant vector database (now always-on; profile is legacy) |

---

## Architecture principles

### CRITICAL: no autonomous execution

The system is a **manual trading co-pilot**. All signal flow terminates at a
human decision point. The execution gate requires explicit operator
confirmation before any order. `EXECUTION_MODE=paper_trading` is the default —
never flip to `live` without full understanding. (The gate is being ported to
Rust inside janus — see RUST_MIGRATION.md §6 Phase 3 — with exhaustive parity
tests; the invariant holds throughout.)

```
Janus (signal) → execution gate → Human confirmation → Broker API
```

### Data flow

**Janus is the source of truth** for market data: it ingests natively over
`exchange-apiws` / exchange WebSockets (`DATA_SOURCE`/`DATA_EXCHANGE`/`DATA_WS_URL`)
and writes QuestDB/Postgres/Redis directly. The old Python data service was
removed; don't add a second data path elsewhere.

### Security

- All access via Tailscale HTTPS. No external ports.
- Nginx terminates TLS with Tailscale certs (`infrastructure/certs/`, gitignored).
- Internal services trust `X-Internal-Token` (set by nginx on every proxied request, validated by the spawner; other services will follow).
- All containers run with `no-new-privileges:true` and `cap_drop: ALL`.
- Secrets in `.env` only — never hardcoded, never committed.

### Databases

| DB | Schema location | Used by |
|--|--|--|
| `janus_db` (Postgres) | janus repo `sql/` + `src/sql/janus/` bootstrap | Janus services |
| `ruby_db` (Postgres) | `src/sql/spawner/` (`002_spawner.sql` = `bot_runs`/`bot_configs`) | Spawner (legacy DB name) |
| QuestDB | — | Tick / bar storage |
| Qdrant | — | Vector embeddings (optional) |

### Observability

- **Metrics:** Prometheus scrapes spawner self-metrics + dynamic `fks-bots` via file_sd.
- **Logs:** All containers log JSON to stdout; Promtail ships to Loki; view in Grafana.
- **Tracing:** Jaeger (memory storage; not durable).
- **Alerting:** Alertmanager → Discord bridge.

---

## Cross-cutting code conventions

### Consuming the published crates

When `janus` or a `bots/*` crate needs the framework, TA, or exchange code,
depend on crates.io — never re-vendor:

```toml
rustrade       = { package = "rustrade-framework", version = "0.4" }  # import as `rustrade`
indicators-ta  = "0.2"                                                # import as `indicators` (0.2.2)
exchange-apiws = "0.8"
```

### Rust

- **Edition 2024**, minimum `rust-version = "1.94.1"`.
- **Error handling:** `anyhow` in binaries, `thiserror` in libraries.
- **Async:** Tokio. Each crate picks the minimum features it needs.
- **Lints:** clippy + `unsafe_code = "warn"`. Fix warnings before committing.

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

### Adding a new bot/strategy

Create a crate under `bots/` (or `strategies/` once private) that depends on
the published `rustrade` + `indicators-ta` + `exchange-apiws`. Implement a
`rustrade::Brain`. Ship it as a Docker image the spawner can launch.
`bots/fks-bot-example/` is the working reference.

### Adding a new service to the stack

1. Decide which repo owns it.
2. Add the Dockerfile to `infrastructure/docker/services/<name>/` (or reuse a
   base image from `infrastructure/docker/base/`). External code builds via the
   base image's `git clone` path (`*_REPO`/`*_REF`).
3. Add the compose entry with the standard security defaults
   (`security_opt: no-new-privileges:true`, `cap_drop: ALL`,
   `restart: unless-stopped`, healthcheck, logging).
4. Bind the host port to `127.0.0.1` only.
5. If it needs scraping, add a Prometheus scrape config.
6. If it needs to be reachable via the WebUI, add an nginx location block.

### Regenerating proto stubs

```bash
./scripts/gen-proto.sh
```

---

## Gotchas

- **No in-tree framework copy.** `rustrade` lives at `nuniesmith/rustrade`
  on crates.io (facade `rustrade-framework`). Bots under `bots/` depend on it
  from crates.io — never re-vendor it into the tree.
- **Janus is no longer in this tree.** Its image always builds via
  `git clone` (`JANUS_REPO` defaults to the janus repo). To hack on janus,
  work in the janus repo and point `JANUS_REF` at your branch.
- **External volumes** are declared `external: true` in `docker-compose.yml`
  (`prometheus_data`, `grafana_data`, `alertmanager_data`). Create them once:
  ```bash
  docker volume create prometheus_data
  docker volume create grafana_data
  docker volume create alertmanager_data
  ```
- **Model files** are gitignored (`.onnx`, `.pt`, `.safetensors`). Only
  champion model metadata + feature contracts are tracked. Binaries live in
  `models/` and get mounted into janus.
- **Tailscale certs** under `infrastructure/certs/` are gitignored. Generate
  with `scripts/generate-certs.sh` after `tailscale serve` is set up.

---

## Where to dig deeper

- **The platform map (canonical):** [`docs/architecture/PLATFORM_ARCHITECTURE.md`](docs/architecture/PLATFORM_ARCHITECTURE.md) — all nine repos, per-repo deep dives, contracts (bot/signal/secrets/observability paths), ports, security model, integration status.
- **The repo map (historical):** [`docs/architecture/REPO_TOPOLOGY.md`](docs/architecture/REPO_TOPOLOGY.md) — superseded by the above.
- **Remaining split moves:** [`SPLIT_PLAN.md`](SPLIT_PLAN.md).
- **The cross-cutting roadmap:** [`TODO.md`](TODO.md).
- **Per-sub-codebase CLAUDE.md files** — read these *first* when working in that directory.
