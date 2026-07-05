# FKS Repo Topology

> **Superseded:** the canonical, current map is
> [`PLATFORM_ARCHITECTURE.md`](PLATFORM_ARCHITECTURE.md) — all nine repos
> (incl. fks-web, crypto, fks-kotlin, technical_papers) plus contracts and
> data flows. This file predates the web split and the fks → fks
> rename; kept for history.
>
> How the five repos fit together, what each owns, and how `fks`
> consumes the rest from crates.io / Docker.
>
> **Last updated:** 2026-05-31

This was the canonical map of the multi-repo split. The split has
**already happened** — `rustrade`, `janus`, `indicators-ta`, and
`exchange-apiws` are independent GitHub repos, and the libraries are
published on crates.io. `fks` is the orchestrator that wires them
together at runtime.

---

## The five repos

| Repo | Role | Kind | Published as |
|------|------|------|--------------|
| [`nuniesmith/rustrade`](https://github.com/nuniesmith/rustrade) | **Trading framework** — scaffolding every bot rewrites: `Bot`, `Brain`, supervisor, risk, backtest | Rust workspace (libraries) | crates.io |
| [`nuniesmith/janus`](https://github.com/nuniesmith/janus) | **Trading brain** — neuromorphic + strategies + signal generation (the IP) | Rust workspace (libraries + service binary) | crates.io (`jflow-*` libs) + Docker image |
| [`nuniesmith/indicators-ta`](https://github.com/nuniesmith/indicators-ta) | **TA math** — indicators + market-regime detection | Standalone crate | crates.io |
| [`nuniesmith/exchange-apiws`](https://github.com/nuniesmith/exchange-apiws) | **Exchange APIs/WS** — REST + WebSocket clients for 5 exchanges | Standalone crate | crates.io |
| **`nuniesmith/fks`** (this repo) | **Orchestrator** — docker-compose, infra, proto, scripts; runs the whole stack | Compose + infra + thin Rust (`src/proto`, `crates/spawner`) | — (heading private) |

---

## crates.io coordinates (current)

These are the **published, consumable** versions. Add them to a `Cargo.toml`
exactly as shown.

```toml
[dependencies]
# Framework facade — the bare name `rustrade` is taken on crates.io, so the
# facade publishes as `rustrade-framework` but is still imported as `rustrade`.
rustrade       = { package = "rustrade-framework", version = "0.3" }

# TA math — the crate is `indicators-ta`, the library imports as `indicators`.
indicators-ta  = "0.1"

# Exchange REST + WebSocket clients.
exchange-apiws = "0.7"
```

| Crate | Version | Import name | Notes |
|-------|--------:|-------------|-------|
| `rustrade-framework` | 0.3.0 | `rustrade` | facade; pulls in the four below |
| `rustrade-core` | 0.3.0 | `rustrade_core` | types, traits, buses |
| `rustrade-supervisor` | 0.3.0 | `rustrade_supervisor` | lifecycle, backoff, breakers |
| `rustrade-risk` | 0.3.0 | `rustrade_risk` | sizing, circuit breakers, session PnL |
| `rustrade-backtest` | 0.3.0 | `rustrade_backtest` | deterministic replay |
| `indicators-ta` | 0.1.5 | `indicators` | indicators + regime detection |
| `exchange-apiws` | 0.7.0 | `exchange_apiws` | signed REST (6 exchanges) + private user-data WS + `f64` order/position quantities |
| `jflow-core` | 0.1.0 | `jflow_core` | first janus lib live; rest of `jflow-*` prepped, not yet pushed |

> ✅ **`exchange-apiws` is published and current.** crates.io has **0.7.0**
> (signed REST across six exchanges, private user-data WS, `f64`
> order/position quantities). The bots and janus consume it from the registry;
> the earlier 0.1 ↔ 0.3 skew is resolved.
>
> ℹ️ **janus crate names.** `janus` / `janus-core` are taken on crates.io, so
> janus's publishable libraries ship under the `jflow-*` prefix (imported by
> their original names via Cargo's `package =` rename). See janus's
> `PUBLISHING.md`.

---

## Dependency graph

```
                              crates.io
   ┌──────────────────────────────────────────────────────────────┐
   │  rustrade-core ──┬── rustrade-supervisor ──┐                  │
   │                  ├── rustrade-risk          ├─ rustrade-       │
   │                  └── rustrade-backtest ─────┘   framework      │
   │                                                 (import:       │
   │                                                  `rustrade`)   │
   │                                                                │
   │  indicators-ta   (TA math)        exchange-apiws  (exchanges)  │
   └───────────────────────▲───────────────────────▲───────────────┘
                           │   consumed by          │
              ┌────────────┴────────────────────────┴────────────┐
              │  janus  (brain — own repo + Docker image)         │
              │     consumes rustrade + indicators-ta +           │
              │     exchange-apiws  ◄── TARGET (see note)          │
              │                                                    │
              │  bots/*  (thin strategy Brains)                    │
              │     consume the same three crates                 │
              └────────────────────────▲──────────────────────────┘
                                       │   orchestrated by
              ┌────────────────────────┴──────────────────────────┐
              │  fks  (this repo)                             │
              │     • docker-compose + infrastructure              │
              │     • proto/  +  src/proto  (fks-proto)            │
              │     • scripts/ (run.sh)                            │
              │     • builds janus/web/spawner images by           │
              │       `git clone` at a pinned ref                  │
              └────────────────────────────────────────────────────┘
```

> **TARGET, not current state.** Today `janus` is self-contained: it
> reimplements TA and exchange connectivity internally as `jflow-indicators`,
> `jflow-exchanges`, and `jflow-bybit-client`, and it no longer references
> `rustrade`. The agreed direction is to **consolidate** janus onto the shared
> crates (`indicators-ta` for math, `exchange-apiws` for connectivity,
> `rustrade` for the framework) and retire the duplicates over time. The first
> step has landed — `IncrementalEma`/`IncrementalAtr` were lifted out of janus
> into `indicators-ta`. See `TODO.md` → "Janus consolidation".

---

## How `fks` consumes the others

`fks` does **not** depend on these repos as path/workspace crates. It
consumes them two ways:

### 1. Service images — `git clone` at a pinned ref

The base Docker images (`infrastructure/docker/base/{rust,nodejs}/`)
acquire source in dual mode:

- `REPO_URL` **set** → `git clone --depth=1 --branch ${REPO_REF}` (CI / prod).
- `REPO_URL` **empty** → bind-mount the local build context (dev, for the
  sub-codebases that still live in this repo).

Refs are wired in `docker-compose.yml` and configured in `.env`:

| Service | Build arg | Repo | Default ref |
|---------|-----------|------|-------------|
| `janus` | `JANUS_REPO` / `JANUS_REF` | `nuniesmith/janus` | `main` |
| `webui` | `WEB_REPO` / `WEB_REF` | `nuniesmith/fks-web` | `main` |
| `spawner` | `SPAWNER_REPO` / `SPAWNER_REF` | `nuniesmith/spawner` | `main` |

> `janus` is no longer present in this repo's tree, so its image **always**
> builds via `git clone` — `JANUS_REPO` must resolve to the janus repo. The
> other two still have local copies under `src/`/`crates/`, so they default
> to the local bind-mount unless their `*_REPO` is set.
>
> The Python `ruby` service was **removed** (2026-06-07) — see
> [`RUST_MIGRATION.md`](RUST_MIGRATION.md).

### 2. Library crates — from crates.io

`janus` and any bots under `bots/` depend on `rustrade-framework`,
`indicators-ta`, and `exchange-apiws` from crates.io (see coordinates above).
`fks` itself only ships `src/proto` (the `fks-proto` crate) and
`crates/spawner` as Rust.

---

## What stays in `fks`

- `docker-compose*.yml` — the ~14-service stack
- `infrastructure/` — Dockerfiles + configs (nginx, prometheus, grafana, …)
- `proto/` + `src/proto/` — protobuf source of truth (`fks-proto`)
- `src/sql/` — postgres bootstrap baked into the image (`janus/`, `spawner/`)
- `scripts/` + `run.sh` — operational tooling
- `crates/spawner/` — bot-container lifecycle service (until it splits out)
- `src/web/` — SvelteKit UI (until it splits)
- `bots/` — thin strategy bots that consume the published crates *(planned)*
- `strategies/` — the private trading IP, once the repo flips private *(planned)*

See [`../../SPLIT_PLAN.md`](../../SPLIT_PLAN.md) for the remaining moves and
[`../../TODO.md`](../../TODO.md) for the active roadmap.
