# fks — TODO (Infrastructure & Runtime)

> **Repo:** `github.com/nuniesmith/fks`
> **Last synced from master todo:** 2026-04-03
>
> This file tracks work that belongs to the infrastructure layer: Docker, compose, Dockerfiles, nginx, CI/CD, Postgres schemas, observability config, bot spawner service, and cross-cutting deployment tasks.

---

## P0 — Active Infra

### Remaining Housekeeping
- [ ] Test access from another tailnet device (requires physical second device — manual check)
- [ ] Verify trainer container GPU passthrough: `./run.sh all --profile training` + nvidia-container-toolkit (deferred)

### OpenClaw OOM Fix
- [ ] Debug Node.js OOM in `openclaw-gateway` — needs ~760MB V8 heap; investigate dependency bloat or memory leak in Discord client initialization
- [ ] Rebuild or replace OpenClaw image when fix is found — current workaround: `NODE_OPTIONS=--max-old-space-size=768` + 1.5g limit

---

can you review my codebase and help me with these tasks 



## P0 — Dockerfile: Build from Source

> Dockerfiles currently COPY source code. Change to clone from GitHub at build time.

- [ ] Update `infrastructure/docker/services/data/Dockerfile` — replace COPY with `git clone ${RUBY_REPO:-https://github.com/nuniesmith/ruby} --branch ${RUBY_REF:-main}`

- [ ] Update `infrastructure/docker/services/web/Dockerfile` — clone fks-web, `npm ci && npm run build`

- [ ] Update `infrastructure/docker/services/rustcode/Dockerfile` — clone rustcode repo

- [ ] Update `infrastructure/docker/base/rust/Dockerfile` for janus — clone fks-janus

- [ ] Add `RUBY_REF`, `JANUS_REF`, `WEB_REF`, `RUSTCODE_REF` build args to `docker-compose.yml` (default `main`)

- [ ] Document build args in `.env.example`

---

## P1 — FUTURES-MERGE: Nginx Routing Update (FMERGE-B)

- [ ] Add futures API proxy to nginx config (`infrastructure/config/nginx/conf.d/dev.conf`):

  ```

  location /futures-api/ {

      proxy_pass http://fks_ruby:8080/api/;

  }

  ```

- [ ] Update `infrastructure/docker/services/futures/Dockerfile` — remove Jinja2 + template COPY steps (after ruby FMERGE-A is done)

- [ ] Verify `ruby` starts clean with API-only mode: `docker compose restart ruby && curl localhost:8080/api/health`

---

## P1 — BOT-SPAWNER Service

### SPAWN-A: BotSpawner service

- [ ] Create `src/spawner/` — new Python FastAPI service (port 8090)

- [ ] `src/spawner/docker_client.py` — Docker SDK wrapper: `spawn()`, `stop()`, `restart()`, `remove()`, `status()`, `list_bots()`, `stream_logs()`, `auto_prune()`

- [ ] Safety guards: `ALLOWED_IMAGE_PREFIX=fks-bot-`, `MAX_CONCURRENT_BOTS=20`, `ALLOWED_NETWORK=fks_network`, CPU/mem limits

- [ ] Labels on all spawned containers: `fks.bot=true`, `fks.mode`, `fks.bot_id`, `fks.created_by=spawner`

- [ ] API routes: `POST /spawn`, `DELETE /container/{id}`, `POST /container/{id}/stop|restart`, `GET /containers`, `GET /container/{id}`, `GET /container/{id}/logs` (SSE), `GET /health`

- [ ] Create `infrastructure/docker/services/spawner/Dockerfile`

- [ ] Add `fks_bot_spawner` service to `docker-compose.yml` with Docker socket mount (`/var/run/docker.sock`)

- [ ] Add spawner proxy to Ruby API: `GET|POST /api/bots/*` → `http://fks_bot_spawner:8090/*`

### SPAWN-C: Postgres Schema

- [ ] Create and apply `src/ruby/sql/008_bots.sql`:

  - `bot_configs` (id, name, config_yaml, config_json, mode, template_name, timestamps)

  - `bot_runs` (id, bot_config_id, container_id, status, started_at, stopped_at, runtime_secs, pnl_final, signal_count, trade_count)

- [ ] Add `008_bots.sql` to postgres init scripts and `./run.sh fix-db`

### SPAWN-D: Prometheus Metrics for Bot Containers

- [ ] Each spawned bot exposes `:9091/metrics` — metrics: `fks_bot_pnl_dollars`, `fks_bot_signals_total`, `fks_bot_trades_total`, `fks_bot_win_rate`, `fks_bot_uptime_seconds`

- [ ] Spawner writes Prometheus SD config to `/prometheus-sd/bots.json` on spawn/stop

- [ ] Add `file_sd_configs` entry to `infrastructure/config/prometheus/prometheus.yml`

- [ ] Create `infrastructure/config/prometheus/alerts/bot-alerts.yml` — `BotStopped`, `BotHighDrawdown`, `BotNoSignals`





the new service spawner i want to see if i can build this with rust, to help create, manage and delete contrainers on the fly for running tasks, we can control the from the webui to start tasks of all sorts, this way things are isolated and we can capture the full logs for the session, sometimes running different tests, running long things like model training, optimization etc etc



i think our services are all use the shared dockerfiles under infrastructure/docker/base/* we need to update these to support src code repos, we can then pull the repo and build the container from source



the dockerfiles that are under services/ most we don't need for our own apps, they should be using our base images, then services is for external apps we want to use, like dbs, monitoring etc
---

## P1 — Multi-Account: Postgres Schema (ACCT-A)

- [ ] Create and apply `src/ruby/sql/009_accounts.sql`:
  - `exchange_accounts` (id, name, exchange_type, mode, is_active, credentials_ref, api_key_hint, timestamps, last_test status)
  - `asset_routing_rules` (id, symbol, account_id, size_pct, priority, is_active)
  - `profit_sweep_config` (id, source_account_id, threshold_usd, mode, schedule_time, timestamps)
  - `profit_sweep_targets` (id, sweep_config_id, account_id, allocation_pct)
- [ ] Apply via `./run.sh fix-db`

---

## P1 — Multi-Account: Janus Execution Router (ACCT-E)

- [ ] Update `janus/services/execution/` — add `RoutingClient` in `execution/src/routing.rs`: HTTP client calling `GET http://fks_ruby:8000/api/routing/{symbol}`, 60s cache TTL
- [ ] On signal: create `ExecutionTarget` per routing rule, fan out signal to each target with `account_id` label
- [ ] Add `ROUTING_API_URL=http://fks_ruby:8000` to janus execution env in `docker-compose.yml`

---

## P1 — Observability

- [ ] **PROM:** Sync Grafana config and restart — ensure all alert rules are loaded
- [ ] Add GPU metrics to Prometheus when trainer is running (nvidia-container-toolkit exporter)
- [ ] Alertmanager Discord bridge — container not running, causing noise in Alertmanager logs; either fix or remove bridge config

---

## P1 — RustCode Deployment

### LLM-D: Wire futures app to RC proxy
- [ ] Add `RC_BASE_URL`, `RC_API_KEY`, `RC_TIMEOUT_SECS`, `RC_MODEL`, `RC_REPO_ID` env vars to futures service in `docker-compose.yml`

### RC-INFRA
- [ ] Set all required secrets in `.env`: `DISCORD_BOT_TOKEN`, `OPENCLAW_GATEWAY_TOKEN`, `RC_PROXY_API_KEYS`, `TAILSCALE_IP`
- [ ] Re-enable CI/CD — move `.github/disabled/ci-cd.yml` back to `.github/workflows/` after OpenClaw OOM fix + Tailscale second-device check
- [ ] Fix GPU / restore Ollama CUDA passthrough (optional — only if using Ollama): `sudo dmesg | grep -i nvidia`, reinstall `nvidia-container-toolkit`, re-run `nvidia-smi`

---

## P1 — Proto (fks-proto shared crate)

- [ ] Centralize stray `forward/proto/janus/v1/janus.proto` → `proto/fks/janus/v1/signal_service.proto` — deferred until gRPC endpoint is actually needed

---

## P2 — CI/CD & Image Persistence

- [ ] Re-enable ARM64 / multi-arch builds in CI (disabled in batch-013, re-enable if needed)
- [ ] `docker push nuniesmith/fks:janus` — publish Janus image for faster deploys
- [ ] Postgres data migration (optional): use `pgloader` if dev data worth preserving across rebuilds

---

## P2 — Feature Work

### PAPER-TRADING: Live Validation
- [ ] Test Redis state persistence: `sim:session:{id}:*` keys written/readable
- [ ] Verify SSE streaming: `/sse/paper-trading/{id}` streams to WebUI

### PINE-INT: Manual Verification
- [ ] Paste generated `ruby.pine` into TradingView Pine editor, confirm it compiles

### CRITICAL-FIX-A: Rithmic (remaining)
- [ ] Live test — verify positions, L1/L2, PnL match dashboard against Rithmic paper account (needs credentials)
- [ ] Margin usage field — depends on Rithmic margin data availability

---

## P3 — Future (Post-Funding)

- [ ] Retrain: run bracket sweep (`scripts/bracket_sweep.py`), apply optimal brackets, retrain vs 93.5% baseline
- [ ] `POSINT-B`: Multi-account position aggregation (needs multiple funded accounts)
- [ ] `DOM-C`: DOM click-to-trade Phase 2 — click price level → limit order, drag stops
- [ ] Profit allocation dashboard: 50% reinvestment / 20% personal / 15% tax / 10% emergency / 5% education
- [ ] Multi-exchange: crypto.com, Netcoins, BTC hardware wallet xpub monitoring
- [ ] K8s manifests — `infrastructure/k8s/` for cloud scaling (post prop-firm funded)
