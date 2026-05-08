# spawner — FKS Bot Spawner

> Rust HTTP service that creates, manages, and deletes Docker containers on
> the fly so the WebUI can run **isolated, observable, ad-hoc workloads** —
> bots, model training, optimisation runs, tests — and stream their full
> session logs back to the browser.

| | |
|---|---|
| **Container** | `fks_bot_spawner` (image `nuniesmith/fks:spawner`) |
| **Port (host)** | `127.0.0.1:8090` |
| **Reverse proxy** | `https://desktop.tailfef10.ts.net/api/bots/*` |
| **Status** | 0.1 — HTTP API + DB persistence + Prometheus SD complete |

---

## What it does

1. **Spawns labelled bot containers** from a whitelisted image prefix
   (`fks-bot-` by default), with CPU/memory caps and `no-new-privileges`
   security. Every container gets `fks.bot=true`, `fks.bot_id=<uuid>`,
   `fks.mode=<paper|live|backtest|optimise|train>` labels.
2. **Streams container logs over Server-Sent Events** at
   `GET /container/:id/logs` so the WebUI can `<EventSource>` a long-running
   training job and show output in real time.
3. **Records every spawn / stop / remove in `bot_runs`** (Postgres) so the
   WebUI can show run history, runtime, and exit reason — the table is
   defined in `src/sql/ruby/007_spawner.sql` with a trigger that computes
   `runtime_secs` automatically.
4. **Writes a Prometheus file_sd config** to `/prometheus-sd/bots.json` on
   every lifecycle event, so each bot's `:9091/metrics` is scraped without a
   Prometheus reload.
5. **Auto-prunes** exited/dead containers after a configurable threshold
   (default 5 minutes) so old runs don't accumulate.

---

## API

| Method | Path | Body / Query | Returns |
|---|---|---|---|
| `GET` | `/health` | — | `{status, running_bots, max_bots, ...}` |
| `GET` | `/metrics` | — | Prometheus text |
| `POST` | `/spawn` | `SpawnRequest` JSON | `SpawnResponse` (201) |
| `GET` | `/containers` | — | `{containers: [...], total, running}` |
| `GET` | `/container/:id` | — | `ContainerInfo` |
| `DELETE` | `/container/:id` | — | `ActionResponse` |
| `POST` | `/container/:id/stop` | — | `ActionResponse` |
| `POST` | `/container/:id/restart` | — | `ActionResponse` |
| `GET` | `/container/:id/logs` | `?tail=N` | SSE stream of `event: log` |
| `GET` | `/runs` *(db only)* | `?limit=N` | `{runs: [...], total, db_enabled}` |

### `SpawnRequest`

```json
{
  "image": "fks-bot-arbitrage:latest",
  "bot_id": "my-bot",                  // optional — auto-generated UUID if omitted
  "mode": "paper",                      // paper | live | backtest | optimise | train
  "env": { "EXCHANGE": "kucoin" },
  "labels": { "team": "trading" },
  "cpu_limit": 0.5,                     // fractional cores; defaults to DEFAULT_CPU_LIMIT
  "memory_limit_mb": 256,               // defaults to DEFAULT_MEMORY_LIMIT_MB
  "cmd": ["/bin/bot", "--flag"],        // optional CMD override
  "entrypoint": ["/sbin/tini", "--"]    // optional ENTRYPOINT override
}
```

### Safety guards (returned as `400` / `429`)

- `image` must start with `ALLOWED_IMAGE_PREFIX` (defaults to `fks-bot-`).
- Refuses to spawn when `MAX_CONCURRENT_BOTS` is already running.
- Every container is forced onto `ALLOWED_NETWORK` (default `fks_network`).
- `cap_drop: ALL` and `security_opt: no-new-privileges:true` are applied
  unconditionally (in `docker_client.rs::spawn`).

---

## Configuration

All settings come from environment variables; defaults are baked into the
`Config::from_env()` constructor.

| Var | Default | Purpose |
|---|---|---|
| `SPAWNER_HOST` | `0.0.0.0` | Bind address |
| `SPAWNER_PORT` | `8090` | Bind port |
| `ALLOWED_IMAGE_PREFIX` | `fks-bot-` | Image whitelist prefix |
| `MAX_CONCURRENT_BOTS` | `20` | Hard cap on running bots |
| `ALLOWED_NETWORK` | `fks_network` | Docker network to attach containers to |
| `DEFAULT_CPU_LIMIT` | `1.0` | Fractional cores per bot (override per-spawn) |
| `DEFAULT_MEMORY_LIMIT_MB` | `512` | Memory cap per bot (override per-spawn) |
| `DEFAULT_CPU_SHARES` | `1024` | Relative CPU weight |
| `PROMETHEUS_SD_PATH` | `/prometheus-sd/bots.json` | File_sd output path |
| `BOT_METRICS_PORT` | `9091` | Port each bot exposes `/metrics` on |
| `PRUNE_AFTER_SECS` | `300` | Stopped-container retention |
| `PRUNE_INTERVAL_SECS` | `60` | Auto-prune sweep interval |
| `SPAWNER_DATABASE_URL` / `DATABASE_URL` | *(empty)* | Postgres URL — empty = stateless mode |
| `RUST_LOG` | `info,spawner=debug` | tracing-subscriber filter |

---

## Postgres persistence (`db` feature, on by default)

The crate has two feature configurations:

```bash
# Default — DB writes enabled
cargo build -p spawner

# Stateless — no sqlx, no Postgres writes
cargo build -p spawner --no-default-features
```

When `db` is enabled and `DATABASE_URL` is set, the spawner:

1. Connects with a 5-conn pool on startup. **Connection failure is
   non-fatal** — it logs a warning and runs stateless.
2. Probes for the `bot_runs` table. **Missing schema is non-fatal** — it
   logs a warning and skips writes.
3. Writes one row per spawn (`status='running'`).
4. Updates `status='stopped'` + `stopped_at=NOW()` on stop/remove. The
   `compute_bot_run_runtime` trigger fills `runtime_secs` automatically.
5. Exposes `GET /runs?limit=N` for the WebUI to render history.

All DB writes happen in `tokio::spawn` — they **never block** the HTTP
response on a slow Postgres. Failures are logged with `warn!`.

To apply the schema:

```bash
docker compose exec postgres \
  psql -U fks_user -d ruby_db -f /docker-entrypoint-initdb.d/007_spawner.sql
```

---

## Deployment

Already wired up in the repo — no further infra changes are required:

| Where | What |
|---|---|
| `docker-compose.yml` | `fks_bot_spawner` service, port `127.0.0.1:8090`, mounts `/var/run/docker.sock` and `prometheus_sd:/prometheus-sd` |
| `infrastructure/docker/services/spawner/Dockerfile` | Multi-stage Rust build (`workspace` target → `runtime`) |
| `infrastructure/config/nginx/conf.d/dev.conf` | `/api/bots/*` (rewritten) and `/api/spawner/*` (passthrough) routes to the service |
| `infrastructure/config/prometheus/prometheus.yml` | `fks-spawner` scrape job + `fks-bots` `file_sd_configs` |
| `src/sql/ruby/007_spawner.sql` | `bot_configs` + `bot_runs` schema |

To bring it up:

```bash
docker compose up -d fks_bot_spawner
curl http://localhost:8090/health
# {"status":"ok","running_bots":0,"max_bots":20,...}
```

---

## Testing

```bash
# Unit tests (10 tests across config, models, db)
cargo test -p spawner

# Stateless-mode build
cargo check -p spawner --no-default-features

# Default (db) build
cargo check -p spawner
```

The current tests cover the data layer (config defaults, request/response
serialisation, DB URL sanitisation). HTTP-level integration tests would
require mocking bollard's `Docker` client behind a trait — left for a
follow-up if needed.

---

## Known limitations / future work

- **bollard 0.19 deprecation drift**: `bollard::container::*Options` are
  deprecated in favour of `bollard::query_parameters::*Options` builders.
  The current code uses the legacy types and silences deprecation warnings
  in `docker_client.rs` — every method needs a small rewrite when we
  migrate. Not blocking; the deprecated types still work.
- **No `DockerOps` trait yet**: handlers depend on the concrete
  `DockerClient`, so HTTP integration tests can't mock the Docker daemon.
- **`bot_configs` table is unused**: the schema models reusable bot
  configuration profiles (templates), but the spawner doesn't read or
  write them yet. The WebUI is expected to manage `bot_configs`
  directly via Ruby's API; the spawner only manages `bot_runs`.
- **No log persistence**: the SSE log endpoint streams from the live
  Docker socket. When a container is pruned, its logs are gone. If we
  need durable logs, mount Loki/Promtail at the bot level (the existing
  Loki stack already collects all container logs by label).
