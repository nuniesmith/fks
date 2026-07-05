# spawner — Claude Code Project Instructions

> **Repo (future):** `github.com/nuniesmith/spawner`
> **Today's path:** `fks/crates/spawner/` (recently moved from
> `src/spawner/`). Will become its own published crate.

## What this is

Rust HTTP service that creates, manages, and deletes Docker containers
on the fly. Designed for "spawn a bot from the WebUI, watch its logs
stream, see its run history in Postgres, let Prometheus discover it
automatically." Hybrid lib + bin crate so the supervisor logic is
testable.

## Stack

| | |
|--|--|
| Edition | Rust 2024 |
| HTTP | axum 0.8 |
| Docker SDK | bollard 0.19 |
| Async | Tokio |
| Persistence | sqlx + Postgres (optional `db` feature, default on) |
| Auth | `X-Internal-Token` middleware validated against `NGINX_INTERNAL_TOKEN` |
| Metrics | prometheus crate + file_sd_configs writer |

## Build & test

```bash
# Default (db) build
cargo check -p spawner
cargo build -p spawner

# Stateless mode (no Postgres)
cargo check -p spawner --no-default-features

# Unit + HTTP integration tests
cargo test -p spawner            # unit (incl. stats math) + HTTP integration tests
```

## API surface

| Method | Path | Auth | Notes |
|--------|------|:----:|-------|
| `GET` | `/health` | none | Docker healthcheck friendly |
| `GET` | `/metrics` | none | Prometheus scrapes here |
| `GET` | `/containers` | yes | Live list of `fks.bot=true` containers |
| `GET` | `/container/{id}` | yes | Inspect one |
| `POST` | `/spawn` | yes | Create + start a new bot |
| `DELETE` | `/container/{id}` | yes | Force-remove |
| `POST` | `/container/{id}/stop` | yes | 30s graceful stop |
| `POST` | `/container/{id}/restart` | yes | 10s graceful stop + start |
| `GET` | `/container/{id}/logs` | yes | SSE stream |
| `GET` | `/runs` | yes (db only) | Recent `bot_runs` history |
| `POST` | `/secrets` | yes (db only) | Store exchange API credentials (never read back) |
| `GET` | `/secrets/status` | yes (db only) | Which exchanges have keys configured |
| `GET` `POST` | `/configs` | yes (db only) | List / save (UPSERT) reusable spawn configs |
| `DELETE` | `/configs/{name}` | yes (db only) | Soft-delete a saved config |

Auth = `X-Internal-Token: ${NGINX_INTERNAL_TOKEN}` set by nginx.
Empty token = dev passthrough.

## Code conventions

- **`DockerOps` trait** abstracts the Docker daemon. Handlers depend on `Arc<dyn DockerOps>`; production wires `DockerClient`, integration tests wire `MockDockerClient`.
- **Hybrid lib + bin crate.** `src/lib.rs` declares `pub mod` for everything; `src/main.rs` uses `spawner::*`. Lets `tests/integration.rs` exercise the real `axum::Router` via `tower::ServiceExt::oneshot`.
- **DB writes never block the response.** Every record is fired via `tokio::spawn` after the Docker call returns. Failures `warn!` and move on.
- **Constant-time token compare** in `src/auth.rs` so a byte mismatch doesn't leak via timing.
- **Routes use axum 0.8 `{id}` syntax**, not the old `:id`. The old syntax panics at startup.

## Safety guards on `/spawn`

- Image must start with `ALLOWED_IMAGE_PREFIX` (default `fks-bot-`).
- Max concurrent containers capped by `MAX_CONCURRENT_BOTS` (default 20).
- Every spawned container is forced onto `ALLOWED_NETWORK` (default `fks_network`).
- `cap_drop: ALL` + `security_opt: no-new-privileges:true` are unconditional.
- Every container gets `fks.bot=true`, `fks.bot_id=<uuid>`, `fks.mode=...` labels.
- **Request input is validated** before any Docker call: `bot_id`/`mode` must
  match the Docker name charset (`[A-Za-z0-9._-]`, ≤64/32 chars); `cpu_limit`
  and `memory_limit_mb` are bounded by `MAX_CPU_LIMIT` (default 8 cores) and
  `MAX_MEMORY_LIMIT_MB` (default 16384); `env`/`labels` are capped (100/50).
  Anything out of range → `400 Bad Request`. (`cmd`/`entrypoint` overrides are
  still accepted — restricting those is a separate, behaviour-changing decision.)

## Common workflows

### Spawn a bot from curl
```bash
curl -X POST http://localhost:8090/spawn \
  -H 'X-Internal-Token: <token>' \
  -H 'Content-Type: application/json' \
  -d '{"image":"fks-bot-example:latest","mode":"paper"}'
```

### Tail logs over SSE
```bash
curl -N http://localhost:8090/container/<id>/logs?tail=100 \
  -H 'X-Internal-Token: <token>'
```

### Add a new Docker daemon operation
1. Add the method to the `DockerOps` trait in `src/docker_client.rs`.
2. Implement on `DockerClient` (delegating to bollard).
3. Implement on `MockDockerClient` in `tests/integration.rs`.
4. Add an HTTP handler in `src/api.rs` (or extend an existing one).
5. Cover it with an integration test.

## Pre-split / pre-publish gotchas

- **Currently a binary crate.** Going to crates.io, decide whether to publish as `spawner-bin` (just a binary) or refactor so most of `lib.rs` is reusable (`spawner` library + thin `spawner-bin` for the binary).
- **Docker image tag `nuniesmith/fks:spawner`.** Will eventually move to `nuniesmith/spawner:latest` on Docker Hub.
- **bollard 0.19 migration is complete** — `src/docker_client.rs` uses the
  `bollard::query_parameters::*Options` API throughout; there is **no**
  `#![allow(deprecated)]` shim. Verified by the blocking `clippy -D warnings`
  gate (which denies the `deprecated` lint), so a regression would fail CI.
- **Postgres schema** lives in `fks/src/sql/ruby/007_spawner.sql` (or `src/ruby/sql/` after the in-flight reorg lands). Either way, the schema isn't owned by this crate — it travels with the Ruby DB migrations. Don't duplicate it here.

## Status

Hardened (auth + HTTP integration tests) and DB-backed in `ruby_db`:
- `bot_runs` history (`/runs`), `bot_configs` saved spawn templates
  (`GET`/`POST /configs`, `DELETE /configs/{name}`), and `exchange_secrets`
  credential storage (`POST /secrets`, `GET /secrets/status`) — all db-gated.
- `/containers` enriches running bots with live CPU% + memory from the Docker
  stats API (pure CPU%/mem math is unit-tested).
- Wired into the WebUI `/bots` route; `fks-bot-example` / `crypto-demo` demo the
  spawn contract end-to-end.
