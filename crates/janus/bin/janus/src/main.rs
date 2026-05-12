//! JANUS — Unified FKS Service (rustrade-supervisor edition)
//!
//! Main entry point for the consolidated JANUS service. Manages multiple
//! sub-services (API, Forward, Backward, CNS, Data) under a single
//! supervision tree.
//!
//! # Port history
//!
//! The supervisor logic that used to live in
//! `janus-core::supervisor::*` was extracted into the open-source
//! `rustrade-supervisor` crate in PR #1. This binary now uses
//! `rustrade-supervisor` directly so the two implementations stop
//! drifting. The trait surface and behaviour are unchanged — names move:
//!
//! | Was                                         | Is                                           |
//! |---------------------------------------------|----------------------------------------------|
//! | `janus_core::supervisor::JanusSupervisor`   | `rustrade_supervisor::Supervisor`            |
//! | `janus_core::supervisor::JanusService`      | `rustrade_supervisor::TradingService`        |
//! | `janus_core::supervisor::ModuleAdapter`     | `crate::adapter::ModuleService` (local)      |
//! | `janus_core::supervisor::ApiModuleAdapter`  | `ModuleService::always_restart(...)`         |
//! | `janus_core::supervisor::SupervisorConfig`  | `rustrade_supervisor::SupervisorConfig`      |
//! | `janus_core::supervisor::BackoffConfig`     | `rustrade_supervisor::BackoffConfig`         |
//! | `janus_core::supervisor::SpawnOptions`      | `rustrade_supervisor::SpawnOptions`          |
//!
//! Once no other crate uses `janus-core::supervisor::*`, the entire
//! `crates/janus/lib/janus-core/src/supervisor/` tree can be deleted.
//!
//! # Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────┐
//! │             rustrade_supervisor::Supervisor             │
//! │                                                         │
//! │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐ │
//! │  │   API   │ │ Forward │ │Backward │ │ CNS  │ Data  │ │
//! │  │ Always  │ │OnFailure│ │OnFailure│ │OnFail│OnFail │ │
//! │  └─────────┘ └─────────┘ └─────────┘ └──────────────┘ │
//! │                                                         │
//! │  TaskTracker        ◄── tracks all, no leaks            │
//! │  CancellationToken  ◄── Ctrl+C / SIGTERM propagation    │
//! │  BackoffConfig[]    ◄── per-service jitter + circuit    │
//! │  ServiceLifecycle[] ◄── Starting→Running→BackingOff→… │
//! └─────────────────────────────────────────────────────────┘
//! ```

mod adapter;

use std::sync::Arc;

use janus_core::{Config, JanusState, init_logging, logging::LoggingConfig};
use rustrade_supervisor::{BackoffConfig, SpawnOptions, Supervisor, SupervisorConfig};
use tracing::{info, warn};

use crate::adapter::ModuleService;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // ── 1. Environment & Logging ─────────────────────────────────────
    let _ = dotenvy::dotenv();

    // Initialize multi-layer logging:
    //   Layer 1 (Ops):  stdout, filtered by RUST_LOG, runtime-reloadable
    //   Layer 2 (HFT):  non-blocking rolling file → ./logs/hft/hft.log
    //
    // The guard MUST live until the end of main() to flush HFT buffers.
    let logging_config = LoggingConfig::default();
    let logging_guard = init_logging(logging_config)?;

    info!("Starting JANUS v1.0.0 (rustrade-supervisor)");
    info!("═══════════════════════════════════════════════════════════");

    // ── 2. Configuration ─────────────────────────────────────────────
    let config = Config::load()?;
    config.validate()?;

    info!("Configuration loaded:");
    info!("  Environment: {}", config.service.environment);
    info!("  HTTP Port: {}", config.ports.http);
    info!("  Metrics Port: {}", config.ports.metrics);
    info!("  Modules Enabled:");
    info!("    - Forward:  {}", config.modules.forward);
    info!("    - Backward: {}", config.modules.backward);
    info!("    - CNS:      {}", config.modules.cns);
    info!("    - API:      {}", config.modules.api);
    info!("    - Data:     {}", config.modules.data);

    // Auto-start flag controls whether processing modules begin work
    // immediately or wait for an explicit API command. This is
    // INDEPENDENT of supervisor spawning — the supervisor always
    // manages all enabled modules; this flag flips
    // `state.service_state` from Standby → Running, which unblocks
    // modules that call `state.wait_for_services_start()` inside their
    // `start_module()`.
    let auto_start = std::env::var("JANUS_AUTO_START")
        .unwrap_or_else(|_| "false".to_string())
        .parse::<bool>()
        .unwrap_or(false);

    // ── 3. Shared State ──────────────────────────────────────────────
    let state = Arc::new(JanusState::new(config.clone()).await?);
    info!("Shared state initialized (service_state: standby)");

    // Probe Redis once at startup so the `janus_redis_connected` metric
    // reflects reality before Prometheus' `for: 3m` alert window opens.
    state.probe_redis().await;

    // Install runtime log-level controller so `POST /api/log-level` works.
    if let Some(ctrl) = logging_guard.create_controller() {
        state.set_log_level_controller(ctrl).await;
        info!("Runtime log-level controller installed into JanusState");
    } else {
        warn!("No reload handle available — runtime log-level changes will be disabled");
    }

    // ── 4. Build Supervisor ──────────────────────────────────────────
    let supervisor_config = SupervisorConfig::default()
        .with_shutdown_timeout(std::time::Duration::from_secs(30))
        .with_default_backoff(
            BackoffConfig::new(
                std::time::Duration::from_millis(100), // base delay
                std::time::Duration::from_secs(60),    // max delay
            )
            .with_cooldown(std::time::Duration::from_secs(300)) // reset after 5 min stable
            .with_circuit_breaker(10, std::time::Duration::from_secs(600)), // trip after 10 failures in 10 min
        );

    let supervisor = Supervisor::new(supervisor_config);

    // ── 5. Spawn Services ────────────────────────────────────────────
    //
    // Each existing service's `start_module(Arc<JanusState>)` is wrapped
    // in `ModuleService` (local — see adapter.rs) which bridges the
    // supervisor's `CancellationToken` into `state.request_shutdown()`.

    // API: always-on, always restarts (even on clean exit).
    if config.modules.api {
        info!("Spawning API module (policy: always)…");
        let svc = ModuleService::always_restart("api", state.clone(), |s| {
            Box::pin(janus_api::start_module(s))
        });
        supervisor.spawn_service(Box::new(svc));
    }

    // Forward: restarts on failure only.
    if config.modules.forward {
        info!("Spawning Forward module (policy: on_failure)…");
        let svc = ModuleService::on_failure("forward", state.clone(), |s| {
            Box::pin(janus_forward::start_module(s))
        });
        supervisor.spawn_service(Box::new(svc));
    }

    // Backward: restarts on failure only.
    if config.modules.backward {
        info!("Spawning Backward module (policy: on_failure)…");
        let svc = ModuleService::on_failure("backward", state.clone(), |s| {
            Box::pin(janus_backward::start_module(s))
        });
        supervisor.spawn_service(Box::new(svc));
    }

    // CNS: restarts on failure only.
    if config.modules.cns {
        info!("Spawning CNS module (policy: on_failure)…");
        let svc = ModuleService::on_failure("cns", state.clone(), |s| {
            Box::pin(janus_cns_service::start_module(s))
        });
        supervisor.spawn_service(Box::new(svc));
    }

    // Data: restarts on failure with a tighter circuit breaker. Data
    // integrity is critical — stop faster on persistent failures.
    if config.modules.data {
        info!("Spawning Data module (policy: on_failure, tight circuit breaker)…");
        let svc = ModuleService::on_failure("data", state.clone(), |s| {
            Box::pin(janus_data::start_module(s))
        });
        let data_backoff = BackoffConfig::new(
            std::time::Duration::from_millis(200),
            std::time::Duration::from_secs(30),
        )
        .with_circuit_breaker(5, std::time::Duration::from_secs(300));

        supervisor
            .spawn_service_with_options(Box::new(svc), SpawnOptions::with_backoff(data_backoff));
    }

    // ── 6. Service State Management ──────────────────────────────────
    info!("═══════════════════════════════════════════════════════════");
    info!(
        "Supervisor active: {} services spawned",
        supervisor.service_count().await
    );
    info!("API is live on port {}", config.ports.http);

    if auto_start {
        info!("JANUS_AUTO_START=true — starting processing services immediately");
        state.start_services();
    } else {
        info!("JANUS is in STANDBY mode");
        info!("  Processing modules are waiting for a start command.");
        info!("  Use one of:");
        info!(
            "    POST http://localhost:{}/api/services/start",
            config.ports.http
        );
        info!("    or the web interface to begin processing.");
    }

    info!("Press Ctrl+C to stop.");
    info!("═══════════════════════════════════════════════════════════");

    // ── 7. Run Until Shutdown ────────────────────────────────────────
    //
    // Blocks until Ctrl+C / SIGTERM is received, then:
    //   1. Cancels the root CancellationToken (propagates to all services)
    //   2. Closes the TaskTracker (prevents new task spawning)
    //   3. Waits for all tasks to drain (with the shutdown_timeout)
    //   4. Logs final supervisor metrics

    supervisor.run_until_shutdown().await?;

    // ── 8. Post-Shutdown Cleanup ─────────────────────────────────────
    let metrics = supervisor.metrics().snapshot();
    info!("═══════════════════════════════════════════════════════════");
    info!("Supervisor Metrics (final):");
    info!("  Services spawned:      {}", metrics.spawned_total);
    info!("  Services terminated:   {}", metrics.terminated_total);
    info!("  Total restarts:        {}", metrics.restarts_total);
    info!("  Circuit breaker trips: {}", metrics.circuit_breaker_trips);

    // Per-service lifecycle summary.
    let snapshots = supervisor.lifecycle_snapshots().await;
    if !snapshots.is_empty() {
        info!("Service Lifecycle Summary:");
        for snap in &snapshots {
            info!(
                "  {} [{}] starts={} failures={} running={:.1}s",
                snap.service_name,
                snap.phase,
                snap.start_count,
                snap.total_failures,
                snap.cumulative_running_secs,
            );
            if let Some(ref reason) = snap.termination_reason {
                info!("    termination: {}", reason);
            }
            if let Some(ref err) = snap.last_error {
                warn!("    last error: {}", err);
            }
        }
    }

    // Final state cleanup (close Redis, flush WAL, etc.)
    state.shutdown().await?;

    info!("═══════════════════════════════════════════════════════════");
    info!("JANUS shutdown complete — all services drained cleanly");
    info!("═══════════════════════════════════════════════════════════");

    // logging_guard drops here — HFT non-blocking buffer is flushed.
    drop(logging_guard);

    Ok(())
}
