# fks

**FKS Trading System — infrastructure, orchestration, and runtime.**

The operational home of the FKS platform. It wires the published framework
crates and the service repos into a running stack: builds the Docker images,
runs the full container stack, and owns all CI/CD, monitoring config, and
deployment tooling.

> 📋 **The repo split has happened.** `rustrade`, `janus`, `indicators-ta`,
> and `exchange-apiws` are now their own repos, and the libraries are on
> crates.io. This repo consumes them — it doesn't contain them. The full map
> is in [`docs/architecture/PLATFORM_ARCHITECTURE.md`](docs/architecture/PLATFORM_ARCHITECTURE.md);
> the split history is in [`SPLIT_PLAN.md`](SPLIT_PLAN.md). `fks` is the
> **public orchestrator**: production strategies, secrets, and live state
> live outside it — in the private `fks-state` repo and the encrypted
> snapshots managed by [`docs/STATE_BACKUP.md`](docs/STATE_BACKUP.md).

---

## The pieces

`fks` orchestrates four external repos (each its own crate(s) /
service) plus the bits that stay here.

### External — consumed, not contained

| Repo | Role | Consumed as |
|------|------|-------------|
| [`rustrade`](https://github.com/nuniesmith/rustrade) | **Trading framework** (`Bot`, `Brain`, supervisor, risk, backtest) | crates.io — `rustrade-framework` 0.4 (imports as `rustrade`) |
| [`janus`](https://github.com/nuniesmith/janus) | **Trading brain** (neuromorphic + strategies + signals) | Docker image (`git clone` at `JANUS_REF`) + `jflow-*` crates |
| [`indicators-ta`](https://github.com/nuniesmith/indicators-ta) | **TA math** (indicators + regime detection) | crates.io — `indicators-ta` 0.2 |
| [`exchange-apiws`](https://github.com/nuniesmith/exchange-apiws) | **Exchange APIs/WS** (5 exchanges, REST + WebSocket) | crates.io — `exchange-apiws` 0.9 |

Other service repos built via `git clone` at a pinned ref:
[`fks-spawner`](https://github.com/nuniesmith/fks-spawner) (bot factory: spawner
service + bot SDK + the bots), [`fks-web`](https://github.com/nuniesmith/fks-web)
(SvelteKit UI), [`fks-kotlin`](https://github.com/nuniesmith/fks-kotlin) (KMP apps).
The **private** `fks-state` sibling holds the trading edges, the
`advisor`/`orb-briefing`/`rithmic-connector` services (compose profiles
`state`/`rithmic`, built from the local `../fks-state` checkout), and the
encrypted state snapshots.

> The Python "Ruby" data/engine/trainer service was **removed** (2026-06-07) —
> janus is the platform now. See
> [`docs/architecture/RUST_MIGRATION.md`](docs/architecture/RUST_MIGRATION.md).

### Stays in this repo

| Path | What |
|------|------|
| `docker-compose*.yml`, `infrastructure/` | The ~20-service stack + Dockerfiles + nginx/prometheus/grafana config |
| `proto/` + `src/proto/` | Protobuf source of truth (the `fks-proto` crate) |
| `src/sql/` | Postgres bootstrap baked into the image (`janus/`, `spawner/`) |
| `scripts/` + `run.sh` | Operational tooling (DB bootstrap, build, health, `fks-state.sh` encrypted backups, …) |

> **Nothing bot-shaped lives here anymore** (the #196 prune): the spawner
> service, the `crypto-bot-core` SDK, and all the bots (incl. the production
> `spot-portfolio`) live in [`fks-spawner`](https://github.com/nuniesmith/fks-spawner);
> the private trading edges (`bots/crypto-futures`) plus `rithmic-connector`,
> `advisor`, and `orb-briefing` live in the **private `fks-state`** repo. The
> once-planned `strategies/` directory is superseded by `fks-state`.

> The SvelteKit UI moved to its own repo —
> [`nuniesmith/fks-web`](https://github.com/nuniesmith/fks-web). The `webui`
> image git-clones it at build time (`WEB_REPO` / `WEB_REF` in `.env`); set
> `WEB_REPO=` empty only for local bind-mount dev against a manual checkout.

> The dependency graph and per-repo deep dives are in
> [`docs/architecture/PLATFORM_ARCHITECTURE.md`](docs/architecture/PLATFORM_ARCHITECTURE.md)
> (the superseded historical map is `REPO_TOPOLOGY.md`).

---

## Stack (containers)

Roughly 20 containers (the core ones):

| Service | Container | Port(s) | Role |
|---------|-----------|---------|------|
| Nginx | `fks_nginx` | 80 | Reverse proxy (TLS via Tailscale) |
| Janus | `fks_janus` | 7000/7001/8080/8180 | Native data ingestion + burn ML + brain REST/gRPC |
| WebUI | `fks_webui` | 3001 | SvelteKit frontend |
| Spawner | `fks_bot_spawner` | 8090 | Bot container lifecycle (Docker socket) |
| Postgres | `fks_postgres` | 5432 | Persistent storage (janus_db, ruby_db=spawner) |
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
file_sd config the spawner writes), and — behind the **`state`** compose
profile on hosts with the private `../fks-state` sibling checkout — the
`fks_advisor` (daily/weekly Discord digests) and `fks_orb_briefing` (pre-market
briefing + sized ORB day-plan) services. `run.sh` auto-enables the `state`
profile when `../fks-state` exists.

## Access

All access via **Tailscale HTTPS** — `https://<your-tailnet-host>.ts.net`.
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
# WEB_REF / SPAWNER_REF to the branches you want to deploy.

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
| `./run.sh generate-secrets` | Generate all required secrets |

## How builds work

The base images under `infrastructure/docker/base/{rust,nodejs}/`
acquire source in **dual mode**:

- **`*_REPO` set** → `git clone --depth=1 --branch ${*_REF:-main}` (CI / prod).
- **`*_REPO` empty** → bind-mount the local context (dev, for sub-codebases
  that still live in this repo).

`janus` and `spawner` have no in-tree copies, so their images **always** build
via `git clone` (`JANUS_REPO` defaults to `https://github.com/nuniesmith/janus`;
`SPAWNER_REPO` must point at `nuniesmith/fks-spawner` — the `.env` template
sets it, and leaving it empty would try the pruned local context and fail).
`run.sh` pins each clone to the remote head sha at build time (`*_COMMIT` via
`git ls-remote`) so a cached clone layer can't silently ship stale code. `web`
defaults to the `fks-web` git-clone too; the in-tree `src/web` is a dev
fallback only.

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
WEB_REF=main
SPAWNER_REF=main
```

---

## Repository layout

```
fks/
├── README.md              # ← you are here
├── CLAUDE.md              # AI-assistant project rules
├── TODO.md                # cross-cutting roadmap
├── SPLIT_PLAN.md          # remaining repo-split moves
├── Cargo.toml             # slim virtual workspace (src/proto)
├── docker-compose.yml     # ~20-service unified compose
├── docker-compose.prod.yml
├── run.sh
├── proto/fks/             # .proto source of truth
│                          # (no bots/ or crates/ — the bot factory lives in the
│                          #  fks-spawner repo; rithmic-connector in fks-state)
├── src/
│   ├── web/               # SvelteKit dashboard — has its own CLAUDE/TODO
│   ├── proto/             # fks-proto Rust crate (protobuf build)
│   └── sql/               # postgres bootstrap (janus/, spawner/) baked into the image
├── infrastructure/
│   ├── docker/
│   │   ├── base/          # base Rust / Node Dockerfiles (git-clone capable)
│   │   └── services/      # per-service Dockerfiles (external apps mostly)
│   └── config/            # nginx, prometheus, grafana, alertmanager, …
├── scripts/               # operational scripts (DB bootstrap, build, health, …)
├── docs/                  # runbooks + architecture notes (see PLATFORM_ARCHITECTURE.md)
└── models/                # model artifacts (mostly gitignored)
```

> **The bots live in the [`fks-spawner`](https://github.com/nuniesmith/fks-spawner)
> repo** (moved in the #196 prune) as standalone crates that consume the
> published crates and ship as `fks-bot-*` images the spawner can launch.
> `./run.sh build-bots` builds the reference images from the **sibling
> checkout** (`../fks-spawner`, override with `SPAWNER_DIR`), then spawn from
> the WebUI `/bots`:
> - `fks-bot-example` — the minimal template (heartbeat + `fks_bot_*` metrics).
> - `crypto-demo` — a working bot exercising the whole stack (rustrade +
>   indicators-ta + exchange-apiws), with an optional `JanusBrain` that
>   delegates decisions to janus.
>
> `bots/spot-portfolio` (fks-spawner) is the **production** spot rebalancer
> (dry-run image by default); its image builds from the fks-spawner root:
> `docker build -f bots/spot-portfolio/Dockerfile -t fks-bot-crypto-spot:latest .`
> The futures/funding trading edges live in the **private `fks-state`** repo
> (`bots/crypto-futures`), which also holds the encrypted state snapshots.

---

## Where to go next

- The repo map + per-repo deep dives? → [`docs/architecture/PLATFORM_ARCHITECTURE.md`](docs/architecture/PLATFORM_ARCHITECTURE.md)
- Working on the framework? → [`nuniesmith/rustrade`](https://github.com/nuniesmith/rustrade)
- Working on the brain? → [`nuniesmith/janus`](https://github.com/nuniesmith/janus)
- Working on bot lifecycles? → the [`fks-spawner`](https://github.com/nuniesmith/fks-spawner) repo (`crates/spawner/CLAUDE.md` there)
- Finishing the Python→Rust port? → [`docs/architecture/RUST_MIGRATION.md`](docs/architecture/RUST_MIGRATION.md)
- Working on the frontend? → [`nuniesmith/fks-web`](https://github.com/nuniesmith/fks-web)
- Remaining split moves? → [`SPLIT_PLAN.md`](SPLIT_PLAN.md)
- AI-assistant rules for this repo? → [`CLAUDE.md`](CLAUDE.md)
- Current roadmap? → [`TODO.md`](TODO.md)
