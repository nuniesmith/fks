# janus — TODO

> **Repo (future):** TBD — `github.com/nuniesmith/janus` and/or
> `github.com/nuniesmith/janus-private` per `JANUS_EXTRACTION_PLAN.md`.
> **Today's path:** `fks-full/crates/janus/`.
> **Last synced:** 2026-05-13

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

---

## P3 — Future

- [ ] Janus optimizer reads asset list from Ruby's asset registry via gRPC or Redis (JFLOW-B).
- [ ] Neural architecture: 30-day live trading validation → document public API → stabilize neuromorphic crate for production use.

---

## ✅ Recently shipped (cross-cutting with `fks-full` PR arc)

- **rustrade-supervisor port** — `bin/janus/main.rs` was rewritten on top of `rustrade_supervisor::Supervisor` + local `ModuleService` adapter so the two supervisor implementations stop drifting.
- **Dead `janus-core::supervisor::*` deletion** — 3,812 lines across 5 files (`mod.rs`, `lifecycle.rs`, `backoff.rs`, `service.rs`, `adapters/mod.rs`) removed once `grep -r "janus_core::supervisor\|use janus_core::\(JanusSupervisor\|JanusService\|ModuleAdapter\|…\)"` came back clean.
- **`rustrade-supervisor` dep pinning** — done in the same arc so the cross-workspace path dep from `bin/janus/Cargo.toml` to `crates/rustrade/crates/rustrade-supervisor` works cleanly without mirroring transitive deps.
- **CI matrix** — janus is one of the matrix jobs in `.github/workflows/rust.yml` (PR #23). Now green after PR #33 fixed the vision diffgaf bench drift.
- **`JANUS_EXTRACTION_PLAN.md`** — refreshed with the phase-1-attempted-execution findings (`fks-full` PR #9 / #27). It's now an honest blueprint for the public-vs-private carve-up rather than the optimistic original.

## What was here before that's now obsolete

The April-2026 version of this file had two large sections covering the
old `rustcode` agent (`crates/rustcode/` and its 9 sub-crates). Those
were removed in `fks-full` PR #21 cleanup — `rustcode`, `openclaw`,
`promptfoo`, `ollama` are all gone from the tree, docker-compose, and
nginx config. The Claude/Zed CLI + Claude API path covers that ground
today.
