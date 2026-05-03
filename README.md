# fks

**FKS Trading System — infrastructure, orchestration, and runtime.**

This is the operational home of the FKS platform. It wires together source repos, builds Docker images (pulling code from GitHub at build time), runs the full 23-container stack, and owns all CI/CD, monitoring config, and deployment tooling.

**Source repos (no infra here):**
- [janus](https://github.com/nuniesmith/janus) — Rust ML engine
- [ruby](https://github.com/nuniesmith/ruby) — Python trading system
- [rustcode](https://github.com/nuniesmith/rustcode) — AI coding assistant
- [fks-web](https://github.com/nuniesmith/fks-web) — SvelteKit WebUI
- [fks-kotlin](https://github.com/nuniesmith/fks-kotlin) — KMP mobile/desktop apps

---

## Stack

| Service | Container | Port | Role |
|---------|-----------|------|------|
| Nginx | `fks_nginx` | 80 | Reverse proxy (TLS via Tailscale) |
| Ruby | `fks_ruby` | 8000/8050/8080 | Data + Engine + Futures (supervisord) |
| Janus | `fks_janus` | 7000/7001/8080/8180 | ML inference + brain REST + gRPC |
| Trainer | `fks_trainer` | — | GPU model training (on-demand) |
| WebUI | `fks_webui` | 3001 | SvelteKit frontend |
| Postgres | `fks_postgres` | 5432 | Persistent storage (janus_db, ruby_db) |
| Redis | `fks_redis` | 6379 | State, caching, pub/sub |
| QuestDB | `fks_questdb` | 9000/9009 | Time-series data |
| Alertmanager | `fks_alertmanager` | 9093 | Signal routing, notifications |
| Prometheus | `fks_prometheus` | 9090 | Metrics collection |
| Grafana | `fks_grafana` | 3000 | Monitoring dashboards |
| Loki | `fks_loki` | 3100 | Log aggregation |
| RustCode | `fks_rustcode` | 3500 | AI assistant (OpenAI-compatible proxy, RAG) |
| OpenClaw | `fks_openclaw` | 18789/18790 | Discord bot + GitHub interface |
| Ollama | `fks_ollama` | 11434 | Local LLM (optional, GPU) |

## Access

All access via **Tailscale HTTPS** — `https://desktop.tailfef10.ts.net`. No external ports. No Authelia. No Let's Encrypt. Nginx terminates TLS using Tailscale-issued certs.

WebUI login: SHA-256 hashed password (`WEBUI_PASSWORD_HASH` in `.env`).

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
| `./run.sh fix-db` | Bootstrap/repair all three Postgres databases |
| `./run.sh health` | Check all service health endpoints |
| `./run.sh build [service]` | Rebuild one or all images |
| `./run.sh restart [service]` | Restart one or all containers |
| `./run.sh logs [service]` | Tail container logs |
| `./run.sh retrain` | Trigger CNN model retraining |
| `./run.sh rc` | RustCode-specific commands |
| `./run.sh generate-secrets` | Generate all required secrets |

## How builds work

Dockerfiles in `infrastructure/docker/services/` build images by cloning source repos from GitHub at build time:

```dockerfile
# Example — Ruby service
ARG RUBY_REPO=https://github.com/nuniesmith/ruby
ARG RUBY_REF=main

RUN git clone --depth=1 --branch=${RUBY_REF} ${RUBY_REPO} /app
WORKDIR /app
RUN pip install -e ".[prod]"
```

To pin a specific commit or branch:
```bash
docker build --build-arg RUBY_REF=my-branch infrastructure/docker/services/data/
```

Or set in `.env`:
```
RUBY_REF=main
JANUS_REF=main
WEB_REF=main
RUSTCODE_REF=main
```

## What lives here

```
infrastructure/
├── docker/
│   ├── base/                    # Base images (python, python-gpu, rust, rust-gpu)
│   └── services/                # Per-service Dockerfiles
├── config/
│   ├── nginx/                   # Nginx config + TLS setup
│   ├── postgres/                # Init SQL scripts
│   ├── monitoring/              # Prometheus rules, Grafana dashboards, Alertmanager config
│   ├── promptfoo/               # LLM eval configs
│   ├── rustcode/                # RustCode plugin manifests
│   └── sim-templates/           # Bot/sim YAML templates
├── certs/                       # TLS certs (gitignored)
└── k8s/                         # Kubernetes manifests (future)

src/
└── proto/                       # Shared fks-proto crate (Rust protobuf definitions)

scripts/
├── generate-secrets.sh          # Secret generation
├── generate-certs.sh            # Self-signed cert generation
├── testing/
│   └── test-signal-pipeline.sh  # End-to-end signal pipeline test (29 PASS)
└── backfill/                    # Data backfill scripts

docker-compose.yml               # Development stack
docker-compose.prod.yml          # Production overrides
docker-compose.trainer.yml       # Training profile
run.sh                           # Master operations script (~35 commands)
.env.example                     # All ~401 env vars documented
CLAUDE.md                        # Claude Code project instructions
```

## Databases

Three Postgres databases on a single `fks_postgres` instance:

| Database | Owner | Used by |
|----------|-------|---------|
| `janus_db` | janus_user | Janus services |
| `ruby_db` | ruby_user | Ruby (8 migrations: 001–008) |
| `rustcode` | rustcode_user | RustCode (20 migrations) |

`./run.sh fix-db` bootstraps all three idempotently.

## Monitoring

- **Prometheus** scrapes 8 targets (all UP)
- **Grafana** — 27-panel signal pipeline dashboard + service health dashboards
- **Alertmanager** — signal routing: prop-firm → WebUI, crypto → Kraken, wallet → monitor
- **Loki** — log aggregation from all containers
- **Promptfoo** — LLM eval (profile `tools`, port 4000)

## Signal pipeline test

```bash
./scripts/testing/test-signal-pipeline.sh
# Expected: 29 PASS / 0 FAIL / 0 WARN
```

## CI/CD

GitHub Actions workflows in `.github/workflows/`. Currently: `llm-audit.yml` (manual trigger). `ci-cd.yml` is in `.github/disabled/` — re-enable after OpenClaw OOM fix and second-device Tailscale verification.
# fks-full
