# JANUS Supervisor Architecture Refactor

**Date:** 2026-02-16
**Status:** Proposed
**Scope:** Replace fire-and-forget task spawning in `main.rs` with a supervised service tree

---

## 1. Problem Statement

JANUS spawns five module tasks (`api`, `forward`, `backward`, `cns`, `data`) using bare `tokio::spawn` into a `Vec<JoinHandle>`. When a module panics or returns an error, the process continues in a degraded state with no restart attempt and no structured notification. Shutdown is polling-based (`AtomicBool` checked every 1 second). There is no log separation between high-frequency market data and operational telemetry.

### What exists today

| Concern | Current State | File |
|---------|--------------|------|
| Task lifecycle | `tokio::spawn` → `Vec<("name", JoinHandle)>` | `src/janus/bin/janus/src/main.rs:59-165` |
| Shutdown signal | `AtomicBool` + 1s poll loop | `main.rs:190`, `janus-core/src/state.rs` |
| Service start gate | `tokio::watch<ServiceState>` (Standby/Running/Stopped) | `janus-core/src/state.rs` — works well, keep it |
| Worker coordination | `CancellationToken` in Backward service only; other modules use `abort()` or AtomicBool poll | `services/backward/src/lib.rs:120,145,251` |
| Restart on failure | None | — |
| Shutdown hooks | `ShutdownCoordinator` exists in `janus-health` but is **not wired in** | `crates/health/src/shutdown.rs` |
| Logging | Single-layer `EnvFilter` + `fmt::layer()` | `main.rs:228-238` |

### Concrete risks

1. **Silent module death.** If `forward` panics, `main` only discovers this at shutdown when the `JoinHandle` resolves. Meanwhile, the system accepts orders with no signal processing. For a trading system, operating on stale signals is worse than halting.

2. **Polling shutdown wastes a full second.** Every module checks `is_shutdown_requested()` in a `sleep(1s)` loop. During that 1 second window, orders could still be submitted after SIGINT.

3. **Inconsistent cancellation.** `BackwardService` uses `CancellationToken` (the correct pattern). Forward, CNS, and Data use `state.is_shutdown_requested()` polls. This inconsistency makes reasoning about shutdown ordering difficult.

4. **No restart logic.** A transient database disconnect kills a module permanently. The only recovery is a full process restart.

---

## 2. Proposed Architecture

### 2.1 Core Primitives

| Primitive | Why |
|-----------|-----|
| `tokio_util::task::TaskTracker` | Tracks spawned tasks without accumulating results (unlike `JoinSet`). `wait()` resolves when tracker is closed AND empty — clean drain pattern. Already in workspace deps via `tokio-util`. |
| `tokio_util::sync::CancellationToken` | Push-based cancellation. Already used in `BackwardService`. Unify all modules to this. Replaces `AtomicBool` polling. |
| `tokio::watch<ServiceState>` | **Keep as-is.** The Standby→Running→Stopped state machine works. Supervisor composes with it. |

**Not needed:**
- `async_trait` — Rust 1.92+ (edition 2024) supports native `async fn` in traits. This project already targets Rust 1.92+.
- `tokio-retry` — Exponential backoff is trivial to implement with `tokio::time::sleep`. Adding a crate for 10 lines of code adds a dependency for no reason.

### 2.2 The JanusSupervisor Struct

```rust
use tokio_util::sync::CancellationToken;
use tokio_util::task::TaskTracker;

pub struct JanusSupervisor {
    tracker: TaskTracker,
    cancel: CancellationToken,
    state: Arc<JanusState>,
}
```

**Location:** `src/janus/lib/janus-core/src/supervisor.rs` (lives in `janus-core` alongside `JanusState`).

### 2.3 The JanusModule Trait

```rust
pub trait JanusModule: Send + 'static {
    fn name(&self) -> &'static str;

    /// Run the module until completion or cancellation.
    /// The CancellationToken replaces AtomicBool polling.
    async fn run(
        self,
        state: Arc<JanusState>,
        cancel: CancellationToken,
    ) -> anyhow::Result<()>;
}
```

**Design notes:**
- Takes `self` by value (not `&mut self`). Services are re-constructed on restart, which guarantees clean state. The Backward service already follows this pattern — `BackwardService::new()` creates a fresh instance.
- No `Box<dyn JanusModule>` needed. The supervisor spawns each module generically. Dynamic dispatch buys nothing here since the set of modules is fixed and known at compile time.

### 2.4 Restart Policy

```rust
pub struct RestartPolicy {
    pub max_retries: u32,        // 0 = no restart (API module)
    pub base_delay_ms: u64,      // 100
    pub max_delay_ms: u64,       // 60_000
    pub cooldown_secs: u64,      // 300 — reset retry count after this uptime
}
```

**Backoff formula:** `delay = min(base * 2^attempt, max) + rand(0..base)`

**Per-module policies:**

| Module | Restart? | Rationale |
|--------|----------|-----------|
| `api` | No (max_retries=0) | If API dies, no way to issue start/stop commands. Escalate to process crash. |
| `forward` | Yes (max_retries=5) | Transient WebSocket disconnects are common. Restart with backoff. |
| `backward` | Yes (max_retries=5) | Database reconnection is recoverable. |
| `cns` | Yes (max_retries=3) | Watchdog/health — should be lightweight and stable. |
| `data` | Yes (max_retries=5) | Exchange connector failures are transient. |

**Circuit breaker:** If `forward` or `data` exhaust retries, the supervisor triggers a full shutdown via `cancel.cancel()`. A trading system without market data or signal processing must not continue executing orders.

### 2.5 Supervisor Lifecycle

```
main()
  │
  ├── init_logging()          // Phase 3: layered tracing
  ├── Config::load()
  ├── JanusState::new()
  │
  └── JanusSupervisor::new(state, cancel)
        │
        ├── spawn(ApiModule, RestartPolicy::no_restart())
        ├── spawn(ForwardModule, RestartPolicy::default())
        ├── spawn(BackwardModule, RestartPolicy::default())
        ├── spawn(CnsModule, RestartPolicy::default())
        ├── spawn(DataModule, RestartPolicy::default())
        │
        └── run_until_shutdown()
              │
              ├── tokio::select! {
              │     _ = ctrl_c / SIGTERM  => cancel.cancel(),
              │     _ = critical_failure  => cancel.cancel(),
              │   }
              │
              ├── tracker.close()
              ├── tracker.wait()        // drain all tasks
              └── state.shutdown()
```

### 2.6 Shutdown Sequence (replaces current polling)

**Current:** `main` polls `is_shutdown_requested()` every 1s, then iterates JoinHandles with 30s total timeout.

**Proposed:**
1. OS signal → `cancel.cancel()` (instant propagation to all modules via `CancellationToken`)
2. Each module's `run()` listens on `cancel.cancelled()` in its `tokio::select!` — breaks immediately
3. `tracker.close()` — prevents new tasks from being spawned
4. `timeout(30s, tracker.wait())` — waits for all tasks to drain
5. If timeout: log warning and exit (tasks are dropped by runtime)
6. `state.shutdown()` — final cleanup (Redis disconnect, etc.)

**Wire in `ShutdownCoordinator`:** The existing `janus-health::ShutdownCoordinator` should be integrated between steps 4 and 5. It already has LIFO hook ordering, per-hook timeouts, and a `DeadMansSwitch` for emergency position closure. Currently unused — this refactor is the right time to activate it.

---

## 3. Logging Refactor

### Current state

```rust
// main.rs:228-238
fn init_logging() {
    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| log_level.into()))
        .with(tracing_subscriber::fmt::layer())
        .init();
}
```

Single layer, single destination (stdout), no HFT separation.

### Proposed: Two-Layer Registry

```rust
fn init_logging() -> tracing_appender::non_blocking::WorkerGuard {
    // Layer 1: Operational logs → stdout
    let (ops_filter, _reload_handle) = tracing_subscriber::reload::Layer::new(
        EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| "info,janus=debug".parse().unwrap()),
    );
    let ops_layer = tracing_subscriber::fmt::layer()
        .with_target(true)
        .with_filter(ops_filter);

    // Layer 2: HFT data → non-blocking file appender
    let file_appender = tracing_appender::rolling::daily("./logs", "hft.log");
    let (non_blocking, guard) = tracing_appender::non_blocking(file_appender);
    let hft_layer = tracing_subscriber::fmt::layer()
        .json()
        .with_writer(non_blocking)
        .with_filter(
            tracing_subscriber::filter::Targets::new()
                .with_target("janus::hft", tracing::Level::TRACE),
        );

    tracing_subscriber::registry()
        .with(ops_layer)
        .with(hft_layer)
        .init();

    guard // MUST be held in main() until process exit
}
```

**Key points:**
- `_reload_handle` enables runtime log level changes via API endpoint (useful for debugging live systems without restart)
- HFT layer uses `Targets` filter — only events with `target: "janus::hft"` route to the file. Zero overhead for non-HFT events.
- `WorkerGuard` returned to `main()` to prevent premature buffer flush. Dropping it early loses log data.
- HFT layer uses JSON format for machine parsing. Ops layer stays human-readable.

---

## 4. Implementation Plan

### Phase 1: Supervisor Foundation

**Files to create/modify:**

| Action | File |
|--------|------|
| Create | `src/janus/lib/janus-core/src/supervisor.rs` |
| Create | `src/janus/lib/janus-core/src/module.rs` (JanusModule trait) |
| Modify | `src/janus/lib/janus-core/src/lib.rs` (add mod supervisor, mod module) |
| Modify | `src/janus/bin/janus/src/main.rs` (replace Vec<JoinHandle> with JanusSupervisor) |

**Steps:**
1. Define `JanusModule` trait in `module.rs`
2. Implement `JanusSupervisor` with `spawn()`, `run_until_shutdown()`
3. Implement backoff logic inline (no external crate)
4. Replace `main.rs` spawn loop with supervisor calls
5. Test: verify `cargo build` succeeds, manual smoke test with SIGINT

### Phase 2: Module Migration

Wrap each existing `start_module()` function in a struct implementing `JanusModule`.

**Migration order** (least risk first):
1. **Backward** — already uses `CancellationToken`. Easiest to adapt. Use as reference impl.
2. **CNS** — lightweight module, low blast radius if broken
3. **Data** — exchange connectors need careful cancellation testing
4. **Forward** — most complex module (event loop, brain runtime). Migrate last.
5. **API** — no-restart policy, simplest adapter (just wraps `janus_api::start_module`)

**Per-module work:**
- Replace `state.is_shutdown_requested()` polling with `cancel.cancelled()` in `tokio::select!`
- Remove internal `tokio::spawn` where possible; use supervisor's `TaskTracker` for sub-tasks
- Ensure `run()` returns `Err` on failure (not silent `Ok(())`)

### Phase 3: Logging & ShutdownCoordinator

1. Replace `init_logging()` with two-layer registry
2. Wire `ShutdownCoordinator` from `janus-health` into supervisor shutdown path
3. Add `#[instrument]` to critical paths (order submission, signal generation)
4. Add supervisor metrics:
   - `janus_supervisor_restarts_total{module="forward"}` (Counter)
   - `janus_supervisor_active_modules` (Gauge)
   - `janus_supervisor_module_uptime_seconds{module="forward"}` (Histogram)

---

## 5. Verification

### Success Criteria

| Test | Expected Behavior |
|------|-------------------|
| `SIGINT` during normal operation | All modules log "received shutdown", drain within 5s, exit code 0 |
| `forward` module panic (inject via test flag) | Supervisor logs error, waits backoff, restarts. After max retries, full shutdown. |
| `data` module transient failure | Restart with backoff, retry count resets after 5 min stable uptime |
| `api` module crash | Immediate full process shutdown (no-restart policy) |
| High-frequency tick logging | `./logs/hft.log` contains JSON tick events. stdout contains only ops logs. |
| Runtime log level change | API call changes `RUST_LOG` filter without restart |

### What NOT to change

- `JanusState` — keep as-is. The `watch::Sender<ServiceState>` pattern for Standby/Running/Stopped is good. Supervisor uses it, doesn't replace it.
- `BrainRuntime` boot sequence — pre-flight checks, watchdog registration, pipeline init. This runs inside `ForwardModule::run()`, untouched.
- `TradingPipeline` — signal flow through brain regions is orthogonal to process supervision.
- Exchange connector internals — WebSocket reconnection logic stays per-connector. Supervisor handles module-level restarts, not connection-level.

---

## 6. Dependencies

All required crates are **already in the workspace**:

| Crate | Current Version | Feature Needed |
|-------|----------------|----------------|
| `tokio-util` | workspace | `rt` (provides `TaskTracker`, `CancellationToken`) |
| `tracing-subscriber` | workspace | `env-filter`, `json` |
| `tracing-appender` | workspace | — |

**No new dependencies required.**

---

## 7. References

- [TaskTracker docs](https://docs.rs/tokio-util/latest/tokio_util/task/task_tracker/struct.TaskTracker.html) — Memory model, close/wait semantics
- [Tokio Graceful Shutdown guide](https://tokio.rs/tokio/topics/shutdown) — CancellationToken patterns
- [WorkerGuard docs](https://docs.rs/tracing-appender/latest/tracing_appender/non_blocking/struct.WorkerGuard.html) — Guard lifetime requirements
- [tracing-subscriber Targets filter](https://docs.rs/tracing-subscriber/latest/tracing_subscriber/filter/targets/struct.Targets.html) — Per-layer filtering
