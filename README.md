# fks-full

**FKS Trading System — infrastructure, orchestration, and runtime.**

The operational home of the FKS platform. It wires the published framework
crates and the service repos into a running stack: builds the Docker images,
runs the full container stack, and owns all CI/CD, monitoring config, and
deployment tooling.

> 📋 **The repo split has happened.** `rustrade`, `janus`, `indicators-ta`,
> and `exchange-apiws` are now their own repos, and the libraries are on
> crates.io. This repo consumes them — it doesn't contain them. The full map
> is in [`docs/architecture/REPO_TOPOLOGY.md`](docs/architecture/REPO_TOPOLOGY.md);
> the remaining moves are in [`SPLIT_PLAN.md`](SPLIT_PLAN.md). `fks-full` is
> heading toward a **private orchestrator** role that holds the production
> strategies, secrets, and deployment topology.

---

## The pieces

`fks-full` orchestrates four external repos (each its own crate(s) /
service) plus the bits that stay here.

### External — consumed, not contained

| Repo | Role | Consumed as |
|------|------|-------------|
| [`rustrade`](https://github.com/nuniesmith/rustrade) | **Trading framework** (`Bot`, `Brain`, supervisor, risk, backtest) | crates.io — `rustrade-framework` 0.2 (imports as `rustrade`) |
| [`janus`](https://github.com/nuniesmith/janus) | **Trading brain** (neuromorphic + strategies + signals) | Docker image (`git clone` at `JANUS_REF`) + `jflow-*` crates |
| [`indicators-ta`](https://github.com/nuniesmith/indicators-ta) | **TA math** (indicators + regime detection) | crates.io — `indicators-ta` 0.1 |
| [`exchange-apiws`](https://github.com/nuniesmith/exchange-apiws) | **Exchange APIs/WS** (5 exchanges, REST + WebSocket) | crates.io — `exchange-apiws` 0.1 |

Other service repos built via `git clone` at a pinned ref:
[`ruby`](https://github.com/nuniesmith/ruby) (Python data system),
[`fks-web`](https://github.com/nuniesmith/fks-web) (SvelteKit UI),
[`fks-kotlin`](https://github.com/nuniesmith/fks-kotlin) (KMP apps).

### Stays in this repo

| Path | What |
|------|------|
| `docker-compose*.yml`, `infrastructure/` | The ~15-service stack + Dockerfiles + nginx/prometheus/grafana config |
| `proto/` + `src/proto/` | Protobuf source of truth (the `fks-proto` crate) |
| `scripts/` + `run.sh` | Operational tooling (DB bootstrap, retraining, …) |
| `crates/spawner/` | Bot-container lifecycle service (until it splits out) |
| `src/ruby/`, `src/web/` | Python data system + SvelteKit UI (until they split) |
| `bots/`, `strategies/` | Thin bots / private trading IP that consume the published crates *(planned)* |

> The dependency graph and exact crates.io coordinates are in
> [`docs/architecture/REPO_TOPOLOGY.md`](docs/architecture/REPO_TOPOLOGY.md).

---

## Stack (containers)

Roughly 15 containers:

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

Plus the dynamically-spawned `fks-bot-*` containers managed by the spawner
(placed on `fks_network` with `cap_drop: ALL`, scraped by Prometheus via the
file_sd config the spawner writes).

## Access

All access via **Tailscale HTTPS** — `https://desktop.tailfef10.ts.net`.
No external ports. Nginx terminates TLS using Tailscale-issued certs.
No Authelia, no Let's Encrypt.

WebUI login: SHA-256 hashed password (`WEBUI_PASSWORD_HASH` in `.env`).
Internal services trust `X-Internal-Token` (set by nginx, validated by e.g.
the spawner).

## Getting started

```bash
# 1. Copy env template and fill in secrets + repo refs
cp .env.example .env
# Edit .env — set XAI_API_KEY, KRAKEN_API_KEY, etc., and pin JANUS_REF /
# RUBY_REF / WEB_REF / SPAWNER_REF to the branches you want to deploy.

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

## How builds work

The base images under `infrastructure/docker/base/{rust,python,nodejs}/`
acquire source in **dual mode**:

- **`*_REPO` set** → `git clone --depth=1 --branch ${*_REF:-main}` (CI / prod).
- **`*_REPO` empty** → bind-mount the local context (dev, for sub-codebases
  that still live in this repo).

`janus` has no in-tree copy, so its image **always** builds via `git clone`
(`JANUS_REPO` defaults to `https://github.com/nuniesmith/janus`). `ruby`,
`web`, and `spawner` still have local copies and default to the bind-mount.

Pin a branch/commit at build time:

```bash
docker build --build-arg JANUS_REF=my-branch \
             --build-arg JANUS_REPO=https://github.com/nuniesmith/janus \
             -f infrastructure/docker/base/rust/Dockerfile .
```

Or set the refs in `.env`:

```
JANUS_REPO=https://github.com/nuniesmith/janus
JANUS_REF=main
RUBY_REF=main
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
├── SPLIT_PLAN.md          # remaining repo-split moves
├── Cargo.toml             # slim virtual workspace (src/proto)
├── docker-compose.yml     # ~15-service unified compose
├── docker-compose.prod.yml
├── docker-compose.trainer.yml
├── run.sh
├── proto/fks/             # .proto source of truth
├── bots/
│   └── fks-bot-example/   # standalone reference bot — consumes crates.io rustrade-framework
├── crates/
│   └── spawner/           # bot lifecycle manager (nested workspace)
├── src/
│   ├── ruby/              # Python trading system — has its own CLAUDE/TODO
│   ├── web/               # SvelteKit dashboard — has its own CLAUDE/TODO
│   └── proto/             # fks-proto Rust crate (protobuf build)
├── infrastructure/
│   ├── docker/
│   │   ├── base/          # base Rust / Python / Node Dockerfiles (git-clone capable)
│   │   └── services/      # per-service Dockerfiles (external apps mostly)
│   └── config/            # nginx, prometheus, grafana, alertmanager, …
├── scripts/               # operational scripts (DB bootstrap, retraining, …)
├── docs/                  # runbooks + architecture notes (see REPO_TOPOLOGY.md)
└── models/                # model artifacts (mostly gitignored)
```

> `bots/fks-bot-example/` is the reference bot the spawner launches — a
> standalone crate that consumes the published `rustrade-framework` from
> crates.io. It's the template for real bots (and the future `strategies/`).

---

## Where to go next

- The repo map + crates.io coordinates? → [`docs/architecture/REPO_TOPOLOGY.md`](docs/architecture/REPO_TOPOLOGY.md)
- Working on the framework? → [`nuniesmith/rustrade`](https://github.com/nuniesmith/rustrade)
- Working on the brain? → [`nuniesmith/janus`](https://github.com/nuniesmith/janus)
- Working on bot lifecycles? → [`crates/spawner/CLAUDE.md`](crates/spawner/CLAUDE.md)
- Working on the Python data API? → [`src/ruby/CLAUDE.md`](src/ruby/CLAUDE.md)
- Working on the frontend? → [`src/web/CLAUDE.md`](src/web/CLAUDE.md)
- Remaining split moves? → [`SPLIT_PLAN.md`](SPLIT_PLAN.md)
- AI-assistant rules for this repo? → [`CLAUDE.md`](CLAUDE.md)
- Current roadmap? → [`TODO.md`](TODO.md)
