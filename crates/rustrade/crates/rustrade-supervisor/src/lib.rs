//! # rustrade-supervisor
//!
//! Structured service lifecycle management for async trading bots.
//!
//! Every long-running task in a rustrade bot — market feeds, heartbeats,
//! candle pollers, the brain itself — implements [`TradingService`] and is
//! spawned through a [`Supervisor`]. The supervisor:
//!
//! - Tracks running tasks without accumulating their results (uses
//!   `TaskTracker` rather than `JoinSet`).
//! - Propagates graceful shutdown via a root `CancellationToken` that
//!   branches to each service.
//! - Restarts failed services with exponential backoff and per-service
//!   circuit breakers.
//! - Surfaces lifecycle state (starting / running / restarting / terminated)
//!   and metrics (restarts, active services, uptime) for observability.
//!
//! # Why this design
//!
//! The naive `tokio::spawn` approach leaks tasks that silently die, makes
//! graceful shutdown a nightmare, and has no concept of "this service failed
//! 20 times in a row — stop retrying." This module replaces that pattern
//! with a small supervision tree that makes failure modes explicit.
//!
//! # Port status
//!
//! Ported from `janus-main/lib/janus-core/src/supervisor/`. The atomic
//! counters in [`SupervisorMetrics`] are the authoritative source of truth;
//! downstream binaries can read them via [`SupervisorMetrics::snapshot`] and
//! publish to their own Prometheus registry. This crate does not own a
//! global Prometheus registry.

pub mod backoff;
pub mod lifecycle;
pub mod service;
pub mod supervisor;

pub use backoff::{BackoffAction, BackoffConfig, BackoffState};
pub use lifecycle::{
    ServiceLifecycle, ServiceLifecycleSnapshot, ServicePhase, TerminationReason, TransitionError,
};
pub use service::{RestartPolicy, TradingService};
pub use supervisor::{
    MetricsSnapshot, SpawnOptions, Supervisor, SupervisorConfig, SupervisorMetrics,
};
