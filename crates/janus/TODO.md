# janus — TODO

> **Repo (future):** TBD — `github.com/nuniesmith/janus` and/or
> `github.com/nuniesmith/janus-private` per `JANUS_EXTRACTION_PLAN.md`.
> **Today's path:** `fks-full/crates/janus/`.
> **Last synced:** 2026-05-13

---

## P0 — CI health

- [ ] **`janus` job in `.github/workflows/rust.yml` has been red since PR #23.** Locally `cargo check --workspace` passes (1m 52s with protoc), `cargo test -p janus --no-run` compiles clean, but `cargo test --workspace` against the full workspace fails in CI within ~8 minutes. Without log access I can't pinpoint the offending test or sub-crate. Most likely candidates:
  - A test in one of the service crates that needs network or a live database
  - A flaky test that times out under CI's resource limits
  - Out-of-disk on the runner (janus's `target/` is multi-gigabyte)
  - Test-only code with a compile error that `cargo check` doesn't exercise

  **Fix path:** click into the latest janus job on Actions, copy the first `error:` or test-failure line, paste it back so the fix can be written surgically.

---

## P0 — Codebase health

- [ ] **318 `#[allow(dead_code)]` annotations** across the workspace. Most are benign serde-deserialization fields, but a pass to audit and remove the genuine dead code is overdue. Worst offenders: `services/api/src/grpc.rs` (11 annotations) and `services/optimizer/src/collector.rs` (10 annotations).
- [ ] **Tonic version split** — workspace declares `0.14.2` but some crates resolve `0.10.2` transitively via `apalis`. Track and resolve when `apalis` hits `1.0` stable.
- [ ] **Centralise stray `forward/proto/janus/v1/janus.proto`** → `proto/fks/janus/v1/signal_service.proto`. **Deferred** until the gRPC endpoint is actually used (dead code today).
- [ ] **Update `services/forward/build.rs`** to use the central `fks-proto` crate instead of compiling local protos. Blocked on the centralisation item above.
- [ ] Evaluate `shared_memory` IPC in containers — `/dev/shm` size limits may break Forward→Backward zero-copy Arrow IPC (crate was removed, but the protocol design question remains).

---

## P0 — `JANUS_EXTRACTION_PLAN.md` follow-through

The extraction plan in `JANUS_EXTRACTION_PLAN.md` lists per-sub-crate destinations (public sibling / private brain repo / stay in fks-full). Phase 1 sub-tasks that are tractable today:

- [ ] **1a — Decouple `janus-data-quality` + `janus-ml`** from `janus-core` / `janus-cns`. Most of the coupling is shared event types (`TradeEvent`, `KlineEvent`, `OrderBookEvent`); a real decoupling needs a smaller shared types crate, not just dropping deps.
- [ ] **1d — Port `bin/janus/` to `rustrade::Bot`.** Already done by the PR-#19 era "Janus port" commit — `bin/janus/main.rs` uses `rustrade_supervisor::Supervisor` and a local `ModuleService` adapter. The `janus-core::supervisor::*` module is now dead from janus's perspective; it can be deleted once nothing else inside janus-core references it. Verify with `grep -r "supervisor::" lib/janus-core/src/lib.rs` — anything left?

---

## P1 — Signal Flow (JFLOW)

### JFLOW-B: Dynamic asset config from Ruby
- [ ] Janus startup config overlay from Redis: read `fks:janus:config` at startup (`janus-core/config.rs`). Higher-level config like "which assets to trade" currently reads from env vars only.
- [ ] When a JanusAI session starts, write session-specific config to Redis (`fks:janus:config`).
- [ ] Optimizer reads asset list from Ruby's asset registry via gRPC or Redis.

### JFLOW-C: Two-way position feedback (remaining)
- [ ] Janus receives live position data and provides guidance: take-profit suggestions based on regime changes, stop adjustment based on volatility, exit urgency from amygdala.
- [ ] All feedback stored as execution memories for learning.

### JFLOW-D: Startup bootstrap (remaining)
- [ ] Full Postgres bootstrap path in Rust: query `janus_memories` directly from Rust at startup. Currently uses Python endpoint + Redis ring buffer as intermediate; direct Postgres requires sqlx setup in forward service `Cargo.toml`.

---

## P1 — Janus AI (remaining)

- [ ] Session metrics: wire signal pipeline (JFLOW-A) to call `POST /api/janus-ai/sessions/{id}/metrics`.

---

## P2 — Housekeeping

- [ ] **Proto: consolidate dual `ForwardService`** — `fks.janus.v1.ForwardService` (4 RPCs) vs `fks.forward.v1.ForwardService` (7 RPCs). **Deferred**: `janus.v1.JanusService` in `forward/proto/` is confirmed dead code (`GrpcServer` compiled but not wired into the main binary).
- [ ] **Delete dead janus-core supervisor module** once verified no remaining references — `lib/janus-core/src/supervisor/`.

---

## P3 — Future

- [ ] Janus optimizer reads asset list from Ruby's asset registry via gRPC or Redis (JFLOW-B).
- [ ] Neural architecture: 30-day live trading validation → document public API → stabilize neuromorphic crate for production use.

---

## ✅ Recently shipped (cross-cutting with `fks-full` PR arc)

- **rustrade-supervisor port** — `bin/janus/main.rs` was rewritten on top of `rustrade_supervisor::Supervisor` + local `ModuleService` adapter so the two supervisor implementations stop drifting. The old `janus-core::supervisor::*` module is now dead from janus's perspective and scheduled for deletion.
- **`rustrade-supervisor` dep pinning** — done in the same arc so the cross-workspace path dep from `bin/janus/Cargo.toml` to `crates/rustrade/crates/rustrade-supervisor` works cleanly without mirroring transitive deps.
- **CI matrix** — janus is one of the matrix jobs in `.github/workflows/rust.yml` (PR #23). Currently red; see P0.
- **`JANUS_EXTRACTION_PLAN.md`** — refreshed with the phase-1-attempted-execution findings (`fks-full` PR #9 / #27). It's now an honest blueprint for the public-vs-private carve-up rather than the optimistic original.

## What was here before that's now obsolete

The April-2026 version of this file had two large sections covering the
old `rustcode` agent (`crates/rustcode/` and its 9 sub-crates). Those
were removed in `fks-full` PR #21 cleanup — `rustcode`, `openclaw`,
`promptfoo`, `ollama` are all gone from the tree, docker-compose, and
nginx config. The Claude/Zed CLI + Claude API path covers that ground
today.
