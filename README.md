# fks-full

**FKS Trading System — infrastructure, orchestration, and runtime.**

The operational home of the FKS platform. Wires together the framework
crates, builds Docker images, runs the full container stack, and owns
all CI/CD, monitoring config, and deployment tooling.

> 📋 **Heading toward private/orchestrator role.** See
> [`SPLIT_PLAN.md`](SPLIT_PLAN.md) for the repo-split blueprint. Each
> sub-codebase under `crates/` and `src/ruby`/`src/web` is being prepared
> to live in its own repo. This repo will eventually be **private** and
> hold the actual production strategies + secrets + deployment topology.

---

## Today's sub-codebases

Each will eventually live in its own repo. Most already have a
`CLAUDE.md` + `TODO.md` for split readiness.

| Path                       | Future repo                                     | Status |
|----------------------------|--------------------------------------------------|--------|
| `crates/rustrade/`         | `nuniesmith/rustrade` (public, crates.io)        | feature-complete 0.1.0 |
| `crates/indicators-ta/`    | `nuniesmith/indicators-ta` (public, crates.io)   | publishable |
| `crates/exchange-apiws/`   | `nuniesmith/exchange-apiws` (public, crates.io)  | publishable |
| `crates/spawner/`          | `nuniesmith/spawner` (public, crates.io)         | hardened (auth + tests) |
| `crates/janus/`            | `nuniesmith/janus` and/or `janus-private`        | mid-extraction — see `crates/janus/JANUS_EXTRACTION_PLAN.md` |
| `crates/kucoin/`           | ~~legacy~~                                       | 🪦 scheduled for deletion |
| `crates/rustcode/`         | ~~paused~~                                       | 🪦 scheduled for deletion (too much going on; revisit later) |
| `src/ruby/`                | `nuniesmith/ruby` (TBD)                          | active |
| `src/web/`                 | `nuniesmith/fks-web` (public)                    | active |
| `src/proto/`               | stays in `fks-full` (or sibling crates.io crate) | source of truth for `.proto` |

**External code that doesn't live here** (built by Dockerfiles via
`git clone --branch ${*_REF:-main}` once the splits happen):

- [janus](https://github.com/nuniesmith/janus) — Rust ML engine
- [ruby](https://github.com/nuniesmith/ruby) — Python trading system
- [fks-web](https://github.com/nuniesmith/fks-web) — SvelteKit WebUI
- [fks-kotlin](https://github.com/nuniesmith/fks-kotlin) — KMP mobile/desktop apps

---

## Stack (containers)

After the rustcode + openclaw removal, the stack is roughly 15 containers:

| Service | Container | Port(s) | Role |
|---------|-----------|---------|------|
| Nginx | `fks_nginx` | 80 | Reverse proxy (TLS via Tailscale) |
| Ruby | `fks_ruby` | 8000/8050/8080 | Data + Engine + Futures (supervisord) |
| Janus | `fks_janus` | 7000/7001/8080/8180 | ML inference + brain REST + gRPC |
| WebUI | `fks_webui` | 3001 | SvelteKit frontend |
| Spawner | `fks_bot_spawner` | 8090 | Bot container lifecycle (Docker socket) |
| Trainer | `fks_trainer` | 8200 | GPU model training (on-demand) |
| Postgres | `fks_postgres` | 5432 | Persistent storage (janus_db, ruby_db) |
| Redis | `fks_redis` | 6379 | State, caching, pub/sub |
| QuestDB | `fks_questdb` | 9000/9009 | Time-series data |
| Qdrant | `fks_qdrant` | 6333/6334 | Vector embeddings (optional) |
| Prometheus | `fks_prometheus` | 9090 | Metrics collection (incl. `fks-bots` SD) |
| Grafana | `fks_grafana` | 3000 | Dashboards (served at `/grafana/`) |
| Alertmanager | `fks_alertmanager` | 9093 | Signal routing + Discord bridge |
| Loki + Promtail | — | 3100 | Log aggregation |
| Jaeger | `fks_jaeger` | 16686 | Distributed tracing (memory storage) |

Plus the dynamically-spawned `fks-bot-*` containers managed by the
spawner (placed on `fks_network` with `cap_drop: ALL`, scraped by
Prometheus via the file_sd config the spawner writes).

## Access

All access via **Tailscale HTTPS** — `https://desktop.tailfef10.ts.net`.
No external ports. Nginx terminates TLS using Tailscale-issued certs.
No Authelia, no Let's Encrypt.

WebUI login: SHA-256 hashed password (`WEBUI_PASSWORD_HASH` in `.env`).
Internal services trust `X-Internal-Token` (set by nginx, validated by
e.g. the spawner).

## Getting started

```bash
# 1. Copy env template and fill in secrets
cp .env.example .env
# Edit .env — set XAI_API_KEY, KRAKEN_API_KEY, etc.

# 2. Generate remaining secrets
./run.sh generate-secrets

# 3. Pull and start everything
./run.sh all

# 4. Check health
./run.sh health
```

## run.sh commands

| Command | Description |
|---------|-------------|
| `./run.sh all` | Start full stack (build if needed, bootstrap DBs) |
| `./run.sh fresh` | Rebuild all images + restart (keeps volumes) |
| `./run.sh fresh --reset-volumes` | Full wipe + rebuild from scratch |
| `./run.sh fix-db` | Bootstrap/repair all Postgres databases |
| `./run.sh health` | Check all service health endpoints |
| `./run.sh build [service]` | Rebuild one or all images |
| `./run.sh restart [service]` | Restart one or all containers |
| `./run.sh logs [service]` | Tail container logs |
| `./run.sh retrain` | Trigger CNN model retraining |
| `./run.sh generate-secrets` | Generate all required secrets |

## How builds work today

Dockerfiles under `infrastructure/docker/services/` currently `COPY` the
source directories. The migration to `git clone --branch ${*_REF:-main}`
is in [`SPLIT_PLAN.md`](SPLIT_PLAN.md#sequencing) — moves to that
pattern as each sub-codebase becomes its own repo.

To pin specific commits or branches once that's done:

```bash
docker build --build-arg RUBY_REF=my-branch \
             -f infrastructure/docker/services/data/Dockerfile .
```

Or set the refs in `.env`:

```
RUBY_REF=main
JANUS_REF=main
WEB_REF=main
SPAWNER_REF=main
```

---

## Repository layout

```
fks-full/
├── README.md              # ← you are here
├── CLAUDE.md              # AI-assistant project rules
├── TODO.md                # cross-cutting roadmap
├── SPLIT_PLAN.md          # repo-split blueprint
├── Cargo.toml             # virtual workspace (currently src/proto + crates/spawner)
├── docker-compose.yml     # ~15-service unified compose
├── docker-compose.prod.yml
├── docker-compose.trainer.yml
├── run.sh
├── proto/fks/             # .proto source of truth
├── crates/
│   ├── rustrade/          # framework — has its own CLAUDE/TODO
│   ├── indicators-ta/     # publishable — has its own CLAUDE/TODO
│   ├── exchange-apiws/    # publishable — has its own CLAUDE/TODO
│   ├── spawner/           # bot lifecycle manager
│   ├── janus/             # ML engine (nested workspace)
│   ├── kucoin/            # 🪦 legacy, scheduled for deletion
│   └── rustcode/          # 🪦 paused, scheduled for deletion
├── src/
│   ├── ruby/              # Python trading system — has its own CLAUDE/TODO
│   ├── web/               # SvelteKit dashboard — has its own CLAUDE/TODO
│   └── proto/             # fks-proto Rust crate (protobuf build)
├── infrastructure/
│   ├── docker/
│   │   ├── base/          # base Rust / Python / Node Dockerfiles
│   │   └── services/      # per-service Dockerfiles (external apps mostly)
│   └── config/            # nginx, prometheus, grafana, alertmanager, …
├── scripts/               # operational scripts (DB bootstrap, retraining, …)
├── docs/                  # runbooks + architecture notes
└── models/                # model artifacts (mostly gitignored)
```

---

## Where to go next

- Working on the framework? → [`crates/rustrade/CLAUDE.md`](crates/rustrade/CLAUDE.md)
- Working on the ML engine? → [`crates/janus/CLAUDE.md`](crates/janus/CLAUDE.md)
- Working on bot lifecycles? → [`crates/spawner/CLAUDE.md`](crates/spawner/CLAUDE.md)
- Working on the Python data API? → [`src/ruby/CLAUDE.md`](src/ruby/CLAUDE.md)
- Working on the frontend? → [`src/web/CLAUDE.md`](src/web/CLAUDE.md)
- Planning the split? → [`SPLIT_PLAN.md`](SPLIT_PLAN.md)
- AI-assistant rules for this repo? → [`CLAUDE.md`](CLAUDE.md)
- Current roadmap? → [`TODO.md`](TODO.md)
