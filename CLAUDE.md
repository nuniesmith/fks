# FKS — Claude Code Project Instructions

## What this repo is

**`fks` is the operational/orchestration root** for the FKS trading
platform. It runs the production stack, owns infrastructure config (Docker,
nginx, Prometheus, …), houses the deployment scripts, and **consumes** the
reusable pieces from their own repos / crates.io.

> 🎯 **The split already happened.** `rustrade`, `janus`, `indicators-ta`, and
> `exchange-apiws` are their own repos; the libraries are on crates.io. This
> repo wires them together at runtime as the **public orchestrator** — every
> secret/strategy/state lives outside it, in the private `fks-state` layer +
> encrypted snapshots (see [`docs/GO_PUBLIC.md`](docs/GO_PUBLIC.md) and
> [`docs/STATE_BACKUP.md`](docs/STATE_BACKUP.md)). The canonical repo map is
> [`docs/architecture/PLATFORM_ARCHITECTURE.md`](docs/architecture/PLATFORM_ARCHITECTURE.md);
> the split history is in [`SPLIT_PLAN.md`](SPLIT_PLAN.md).

**Stack:** Rust + SvelteKit + Docker. ~20 containers. (The Python "Ruby"
data/engine/trainer service was removed — janus is the platform now. See
[`docs/architecture/RUST_MIGRATION.md`](docs/architecture/RUST_MIGRATION.md).)

### External repos (consumed, not contained)

| Repo | Role | Consumed as |
|------|------|-------------|
| [`rustrade`](https://github.com/nuniesmith/rustrade) | trading framework | crates.io `rustrade-framework` 0.4 (imports as `rustrade`) |
| [`janus`](https://github.com/nuniesmith/janus) | trading brain | Docker image (`git clone` at `JANUS_REF`) + `jflow-*` crates |
| [`indicators-ta`](https://github.com/nuniesmith/indicators-ta) | TA math | crates.io `indicators-ta` 0.2 (imports as `indicators`) |
| [`exchange-apiws`](https://github.com/nuniesmith/exchange-apiws) | exchange REST/WS | crates.io `exchange-apiws` 0.9 |
| [`fks-web`](https://github.com/nuniesmith/fks-web) | SvelteKit UI | Docker image (`git clone` at `WEB_REF`) |
| [`fks-spawner`](https://github.com/nuniesmith/fks-spawner) | the **bot factory**: spawner lifecycle service + `crypto-bot-core` SDK + the bots (`spot-portfolio` **production**, `crypto-demo`, `fks-bot-example`, `rustrade-exchange-apiws`) | spawner image via `git clone` (`SPAWNER_REPO`); bot images build from the sibling checkout (`docker build -f bots/spot-portfolio/Dockerfile …` from its root) |
| `fks-state` *(private)* | trading edges (`bots/crypto-futures` funding bot), `crates/{rithmic-connector,advisor,orb,orb-backtest,orb-briefing}` (read-only Rithmic feed + Discord advisor/ORB decision-support), encrypted state snapshots, strategy docs (`docs/ARCHITECTURE.md`) | local checkout only — `advisor`/`orb-briefing` build via the compose `state` profile, `rithmic-connector` via `rithmic`; the funding image builds there; snapshots via `scripts/fks-state.sh` |

### Lives in this repo

| Path | Type | Owns its own docs |
|--|--|--|
| `src/web/` | SvelteKit dashboard stub (real UI = `fks-web`) | `CLAUDE.md` + `TODO.md` + `README.md` |
| `src/proto/` | `fks-proto` crate (protobuf) | — |
| `src/sql/` | DB bootstrap baked into the postgres image (`janus/`, `spawner/` — the spawner's schema deliberately stays here) | — |
| `strategies/` | private trading IP (consumes the published crates) | *(planned — superseded by `fks-state`)* |

> **fks is now a pure orchestrator**: compose topology, nginx/monitoring
> infra, DB bootstrap, proto, docs. All Rust services/bots live in their own
> repos. The `crypto` repo is dissolved: its spot bot + shared scaffolding are
> in `fks-spawner`; the futures/funding **trading edges** are in the
> **private `fks-state`** repo (which also holds `rithmic-connector` and the
> encrypted state snapshots).

> **When working in any sub-directory, read its sub-CLAUDE first.** This root
> file covers cross-cutting concerns: how the pieces wire together at the
> Docker layer, top-level conventions, and the consumption direction.

---

## Service map

| Service | Source | Host port(s) | Notes |
|---------|--------|--------------|-------|
| **Janus** | `nuniesmith/janus` (git-clone image) | 7000 / 7001 / 8080 / 8180 | Rust trading brain + native data ingestion + burn ML. The platform. |
| **WebUI** | `src/web/` (or `nuniesmith/fks-web`) | 3001 | SvelteKit 5 dashboard. Includes `/bots` for spawner control. |
| **Spawner** | `fks-spawner` repo (git-clone build via `SPAWNER_REPO`) | 8090 | Bot container lifecycle. Mounts `/var/run/docker.sock`, writes Prometheus SD. |
| **Postgres** | — | 5432 | `janus_db` + `fks_db` on one instance (`fks_db` = spawner schema; renamed from `ruby_db` 2026-07-21, env var `RUBY_DB` retained). |
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
# spawner + bots test in the fks-spawner repo; rithmic-connector in fks-state
cd src/web         && npm run check && npm run build
```

> To build a service from an external repo locally, set its `*_REPO`/`*_REF`
> (e.g. `JANUS_REPO`, `JANUS_REF`) or work in that repo directly. Don't
> re-vendor an external repo back into `crates/`.

### Docker compose profiles

| Profile | Adds |
|---------|------|
| `demo` | `crypto-demo` paper bot driving the janus brain end-to-end (image builds from the sibling `../fks-spawner`) |
| `state` | `advisor` + `orb-briefing` (Discord digests/briefings) — build from the **private** sibling `../fks-state`; `run.sh` auto-enables this profile when that checkout exists |
| `rithmic` | `rithmic-connector` (read-only futures feed, fks-state) — additionally runtime-gated on `RITHMIC_ENABLED=true` |
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
| `fks_db` (Postgres) | `src/sql/spawner/` (`002`–`011`: `bot_runs`/`bot_configs`, secrets, notifications, `ui_layouts`, `net_worth_snapshots`, treasury, edge factory, the scoped `fks_backtest` role, webui auth + `webui_alert_acks`) | Spawner (renamed from `ruby_db` 2026-07-21; env var `RUBY_DB` retained) |
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
exchange-apiws = "0.9"
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
- **WebUI M0–M3 buildout (landed 2026-07, in `nuniesmith/fks-web`):** installable
  iPhone PWA (manifest/icons/iOS meta/safe-areas); RBAC at the `routeRequest` seam
  (viewer < operator < admin — kill = operator+, rearm/keys/notifications/risk =
  admin-only); cockpit live-status (three-state `/status` live-twin feed +
  mode-mismatch guard) + alert-ack inbox (`webui_alert_acks`, sha256(labels+activeAt)
  identity); Money-snapshot landing panel. Auth Phase 1 (scrypt + DB sessions,
  scoped `fks_webui` role) is live. SQL for auth + acks: `010_webui_auth.sql`,
  `011_webui_alert_acks.sql`.

### Protocol Buffers

- All `.proto` files in `proto/fks/`.
- Package naming: `fks.<service>.v1` (e.g. `fks.signals.v1`, `fks.execution.v1`).
- `src/proto/` is the `fks-proto` Rust crate that compiles the protos.
- Regenerate with `./scripts/gen-proto.sh`. `buf` is the linter.

---

## Common workflows

### Adding a new bot/strategy

Create a crate under the **fks-spawner** repo's `bots/` (or, for private
edges, under `fks-state`'s `bots/`) that depends on the published `rustrade`
+ `indicators-ta` + `exchange-apiws`. Implement a `rustrade::Brain`. Ship it
as an `fks-bot-*` Docker image the spawner can launch.
`fks-spawner/bots/fks-bot-example/` is the working reference.

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
  on crates.io (facade `rustrade-framework`). The bots (fks-spawner repo)
  depend on it from crates.io — never re-vendor it into a tree.
- **Janus and the spawner are no longer in this tree.** Their images always
  build via `git clone` (`JANUS_REPO` defaults to the janus repo;
  `SPAWNER_REPO` is set in `.env` — empty fails, there's no local context
  since #196). `run.sh` sha-pins the clones (`*_COMMIT`). To hack on either,
  work in its repo and point the `*_REF` at your branch.
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
