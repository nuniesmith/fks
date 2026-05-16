# spawner — TODO

> **Repo (future):** `github.com/nuniesmith/spawner`
> **Last synced:** 2026-05-13

## P0 — Pre-publish

- [ ] **Name conflict on crates.io.** `spawner` is almost certainly taken. Rename candidates: `fks-spawner`, `bot-spawner`, `docker-bot-spawner`. Decide before publish.
- [ ] **Cargo.toml metadata.** Missing fields: `license`, `repository`, `documentation`, `readme`, `keywords`, `categories`. See `PRE_PUBLISH_AUDIT.md` in the repo root for the full list.
- [ ] **`LICENSE` file at the crate root** — required by crates.io and missing today.
- [ ] **Edition bump 2021 → 2024** to match the other publishable crates.
- [ ] **Decide whether to publish at all.** It's a binary-only Docker service; crates.io makes sense only if downstream users want it as a library. If not, drop the publish goal and ship via Docker Hub only.

## P0 — Hardening follow-ups

- [ ] **Bollard 0.19 deprecation migration** — `bollard::container::*Options` → `bollard::query_parameters::*OptionsBuilder`. The `#![allow(deprecated)]` shim in `src/docker_client.rs` masks the warnings. Integration tests already cover the round-trip, so regressions are caught immediately. ~half day mechanical.

## P1 — Feature work

- [ ] **`bot_configs` template UI** — the `bot_configs` table is part of the schema but unused. Add a preset library: save spawn-form values as a named row, then `POST /spawn?from_config=<name>` fills the rest.
- [ ] **Persistent log capture** — when a container is pruned, its logs disappear. Loki/Promtail already collects all container logs by label, so consider whether spawner needs its own capture or can just point at Loki for archived runs.
- [ ] **Mobile / narrow-screen polish** on `/bots` — current grid assumes desktop terminal layout.

## P1 — Test coverage

- [ ] **Restart/SSE/runs tests** — the integration suite covers spawn/list/remove + auth, but not restart, log SSE streaming, or `/runs` history. Each is one extra `tokio::test` with the existing `MockDockerClient`.
- [ ] **Postgres test fixture** — today the `db` feature is exercised only when `DATABASE_URL` is set. A `testcontainers`-backed integration test that exercises the real `BotRunStore` would catch SQL changes.

## P2 — Quality of life

- [ ] **Per-container resource limits in the UI** — today the spawn form has CPU and memory inputs. Add cgroup-pid-limits + disk-quota knobs when they matter for training jobs.
- [ ] **Container lifecycle events on the bus** — broadcast spawn/stop/restart events on Redis pub/sub so other services (e.g. Grafana alerting) can react.

## P3 — Future

- [ ] **Multi-host Docker** — today the spawner talks to one Docker daemon via the socket. For scaling, accept a `DOCKER_HOST` env var per spawner instance and route bot containers across multiple hosts.
- [ ] **Image build endpoint** — `POST /build` that builds a `fks-bot-*` image from a git URL + ref + path. Sketchy from a security standpoint; tabled until there's a clear use case.

---

## ✅ Recently shipped

- HTTP API + Docker SDK wrapper + Prometheus self-metrics + file_sd writer (initial PRs in `fks-full`).
- Postgres persistence via `BotRunStore` (PR #12).
- `/bots` WebUI route (PR #13).
- Build rot + Axum 0.8 path syntax + Bollard 0.19 cleanup (PRs #11, #14, #18).
- `X-Internal-Token` auth middleware + `DockerOps` trait + 10 HTTP integration tests (PR #18).
- `fks-bot-example` reference image demonstrating the `:9091/metrics` contract (PR #17).
- Auto-scroll on the `/bots` log viewer + `api.*` callsite fixes (PR #19).
- Promoted from `src/spawner/` to `crates/spawner/` as its own nested workspace (PR #21 cleanup + reorg).
- Root `Cargo.toml` workspace-members refreshed so `cargo check` from repo root works (PR #21).
- Per-workspace CI job in `.github/workflows/rust.yml` (PR #23) — spawner's job has been passing throughout the CI green-up arc.
- The "README polish — no fks-full path references" item from earlier was verified clean (zero `fks-full` references in `crates/spawner/README.md`).
