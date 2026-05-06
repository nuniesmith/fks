//! The [`Supervisor`] — manages a fleet of [`TradingService`]s.
//!
//! Hierarchical service lifecycle management built on:
//!
//! - [`TaskTracker`] — tracks spawned tasks without accumulating results
//!   (unlike `JoinSet`), preventing memory leaks in long-running processes.
//! - [`CancellationToken`] — propagates graceful shutdown signals through
//!   the service hierarchy.
//!
//! Each service is wrapped in a restart loop governed by its [`RestartPolicy`]
//! and [`BackoffConfig`]. The supervisor also tracks per-service
//! [`ServiceLifecycle`] state and exposes [`SupervisorMetrics`] atomics for
//! external observability.

use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use tokio::sync::RwLock;
use tokio_util::sync::CancellationToken;
use tokio_util::task::TaskTracker;

use crate::backoff::{BackoffAction, BackoffConfig, BackoffState};
use crate::lifecycle::{
    ServiceLifecycle, ServiceLifecycleSnapshot, ServicePhase, TerminationReason,
};
use crate::service::{RestartPolicy, TradingService};

// ---------------------------------------------------------------------------
// SupervisorConfig
// ---------------------------------------------------------------------------

/// Configuration for the [`Supervisor`].
#[allow(missing_docs)] // each field has its own /// doc; struct itself is the API surface
#[derive(Debug, Clone)]
pub struct SupervisorConfig {
    /// Default backoff applied to services without their own override.
    pub default_backoff: BackoffConfig,
    /// Maximum time to wait for services to drain on shutdown.
    pub shutdown_timeout: Duration,
    /// Install a Ctrl-C / SIGTERM handler automatically.
    pub install_signal_handler: bool,
}

impl Default for SupervisorConfig {
    fn default() -> Self {
        Self {
            default_backoff: BackoffConfig::default(),
            shutdown_timeout: Duration::from_secs(30),
            install_signal_handler: true,
        }
    }
}

impl SupervisorConfig {
    /// Builder: override the shutdown timeout.
    pub fn with_shutdown_timeout(mut self, timeout: Duration) -> Self {
        self.shutdown_timeout = timeout;
        self
    }

    /// Builder: override the default backoff.
    pub fn with_default_backoff(mut self, backoff: BackoffConfig) -> Self {
        self.default_backoff = backoff;
        self
    }

    /// Builder: disable the auto-installed Ctrl-C / SIGTERM handler.
    pub fn without_signal_handler(mut self) -> Self {
        self.install_signal_handler = false;
        self
    }
}

// ---------------------------------------------------------------------------
// SupervisorMetrics
// ---------------------------------------------------------------------------

/// Atomic counters for supervisor-level metrics.
///
/// These are the authoritative source of truth. When the `prometheus` feature
/// is enabled, downstream binaries can read them via [`SupervisorMetrics::snapshot`]
/// and publish to their own registry — rustrade-supervisor does not own a
/// global Prometheus registry.
#[allow(missing_docs)] // counter names are self-evident; see [`MetricsSnapshot`]
#[derive(Debug, Default)]
pub struct SupervisorMetrics {
    pub restarts_total: AtomicU64,
    pub active_services: AtomicU64,
    pub spawned_total: AtomicU64,
    pub terminated_total: AtomicU64,
    pub circuit_breaker_trips: AtomicU64,
}

impl SupervisorMetrics {
    fn new() -> Self {
        Self::default()
    }

    fn record_spawn(&self) {
        self.spawned_total.fetch_add(1, Ordering::Relaxed);
        self.active_services.fetch_add(1, Ordering::Relaxed);
    }

    fn record_restart(&self) {
        self.restarts_total.fetch_add(1, Ordering::Relaxed);
    }

    fn record_termination(&self) {
        self.terminated_total.fetch_add(1, Ordering::Relaxed);
        let _ = self
            .active_services
            .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |v| {
                Some(v.saturating_sub(1))
            });
    }

    fn record_circuit_breaker_trip(&self) {
        self.circuit_breaker_trips.fetch_add(1, Ordering::Relaxed);
    }

    /// Snapshot the current metric values.
    pub fn snapshot(&self) -> MetricsSnapshot {
        MetricsSnapshot {
            restarts_total: self.restarts_total.load(Ordering::Relaxed),
            active_services: self.active_services.load(Ordering::Relaxed),
            spawned_total: self.spawned_total.load(Ordering::Relaxed),
            terminated_total: self.terminated_total.load(Ordering::Relaxed),
            circuit_breaker_trips: self.circuit_breaker_trips.load(Ordering::Relaxed),
        }
    }
}

/// Plain-data snapshot of supervisor metrics.
#[allow(missing_docs)] // counter names mirror [`SupervisorMetrics`]; same semantics
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct MetricsSnapshot {
    pub restarts_total: u64,
    pub active_services: u64,
    pub spawned_total: u64,
    pub terminated_total: u64,
    pub circuit_breaker_trips: u64,
}

// ---------------------------------------------------------------------------
// SpawnOptions
// ---------------------------------------------------------------------------

/// Per-service spawn configuration.
#[derive(Debug, Clone, Default)]
pub struct SpawnOptions {
    /// Override the supervisor's default backoff config for this service.
    pub backoff: Option<BackoffConfig>,
}

impl SpawnOptions {
    /// Build options carrying a per-service backoff override.
    pub fn with_backoff(backoff: BackoffConfig) -> Self {
        Self {
            backoff: Some(backoff),
        }
    }
}

// ---------------------------------------------------------------------------
// Supervisor
// ---------------------------------------------------------------------------

/// Tracks a fleet of [`TradingService`]s, manages their lifecycle, and
/// orchestrates graceful shutdown on Ctrl-C / SIGTERM.
///
/// Unlike `JoinSet`, [`TaskTracker`] does **not** accumulate task return
/// values, so completed-task memory is reclaimed immediately. This makes the
/// supervisor safe for long-running processes that may restart services
/// hundreds of times over weeks of operation.
pub struct Supervisor {
    config: SupervisorConfig,
    tracker: TaskTracker,
    cancel_token: CancellationToken,
    metrics: Arc<SupervisorMetrics>,
    lifecycles: Arc<RwLock<HashMap<String, ServiceLifecycle>>>,
}

impl Supervisor {
    /// Build a supervisor with the given config.
    pub fn new(config: SupervisorConfig) -> Self {
        Self {
            config,
            tracker: TaskTracker::new(),
            cancel_token: CancellationToken::new(),
            metrics: Arc::new(SupervisorMetrics::new()),
            lifecycles: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Build a supervisor with [`SupervisorConfig::default`].
    pub fn with_defaults() -> Self {
        Self::new(SupervisorConfig::default())
    }

    /// Borrow the root cancellation token (cancel it to trigger graceful
    /// shutdown of every service).
    pub fn cancel_token(&self) -> &CancellationToken {
        &self.cancel_token
    }

    /// Borrow the shared metrics handle.
    pub fn metrics(&self) -> &Arc<SupervisorMetrics> {
        &self.metrics
    }

    /// Snapshot every tracked service's lifecycle.
    pub async fn lifecycle_snapshots(&self) -> Vec<ServiceLifecycleSnapshot> {
        let lifecycles = self.lifecycles.read().await;
        lifecycles
            .values()
            .map(ServiceLifecycleSnapshot::from)
            .collect()
    }

    /// Snapshot a single service's lifecycle by name.
    pub async fn service_lifecycle(&self, name: &str) -> Option<ServiceLifecycleSnapshot> {
        let lifecycles = self.lifecycles.read().await;
        lifecycles.get(name).map(ServiceLifecycleSnapshot::from)
    }

    /// Number of tracked services (alive + terminated).
    pub async fn service_count(&self) -> usize {
        self.lifecycles.read().await.len()
    }

    /// Cancel the root token, signalling every service to stop.
    #[tracing::instrument(skip(self))]
    pub fn trigger_shutdown(&self) {
        tracing::info!("Supervisor: shutdown triggered");
        self.cancel_token.cancel();
    }

    /// `true` once [`Self::trigger_shutdown`] has been called.
    pub fn is_shutting_down(&self) -> bool {
        self.cancel_token.is_cancelled()
    }

    // ── Spawn ─────────────────────────────────────────────────────────

    /// Spawn a service into the supervisor with default options.
    /// Spawn a service with default options.
    pub fn spawn_service(&self, service: Box<dyn TradingService>) {
        self.spawn_service_with_options(service, SpawnOptions::default());
    }

    /// Spawn a service with custom per-service options.
    #[tracing::instrument(
        skip(self, service, options),
        fields(service = %service.name(), policy = %service.restart_policy())
    )]
    /// Spawn a service with custom options.
    pub fn spawn_service_with_options(
        &self,
        service: Box<dyn TradingService>,
        options: SpawnOptions,
    ) {
        let service_name = service.name().to_string();
        let restart_policy = service.restart_policy();
        let backoff_config = options
            .backoff
            .unwrap_or_else(|| self.config.default_backoff.clone());

        let cancel = self.cancel_token.child_token();
        let metrics = Arc::clone(&self.metrics);
        let lifecycles = Arc::clone(&self.lifecycles);

        metrics.record_spawn();

        self.tracker.spawn(Self::service_loop(
            service,
            service_name,
            restart_policy,
            backoff_config,
            cancel,
            metrics,
            lifecycles,
        ));
    }

    /// The core restart loop for a single service.
    #[tracing::instrument(
        skip_all,
        fields(service = %service_name, policy = %restart_policy)
    )]
    async fn service_loop(
        service: Box<dyn TradingService>,
        service_name: String,
        restart_policy: RestartPolicy,
        backoff_config: BackoffConfig,
        cancel: CancellationToken,
        metrics: Arc<SupervisorMetrics>,
        lifecycles: Arc<RwLock<HashMap<String, ServiceLifecycle>>>,
    ) {
        let mut backoff = BackoffState::new(backoff_config);
        let mut lifecycle = ServiceLifecycle::new(&service_name);

        {
            let mut lc_map = lifecycles.write().await;
            lc_map.insert(service_name.clone(), lifecycle.clone());
        }

        loop {
            if cancel.is_cancelled() {
                tracing::info!(service = %service_name, "cancellation detected, not starting service");
                let _ = lifecycle.transition_to_stopping();
                let _ = lifecycle.transition_to_terminated(TerminationReason::Cancelled);
                Self::update_lifecycle(&lifecycles, &service_name, &lifecycle).await;
                metrics.record_termination();
                return;
            }

            if lifecycle.phase() == ServicePhase::Starting {
                let _ = lifecycle.transition_to_running();
            } else if lifecycle.phase() == ServicePhase::BackingOff {
                let _ = lifecycle.transition_to_restarting();
                let _ = lifecycle.transition_to_running();
                metrics.record_restart();
            }

            backoff.record_start();
            Self::update_lifecycle(&lifecycles, &service_name, &lifecycle).await;

            tracing::info!(
                service = %service_name,
                attempt = lifecycle.start_count(),
                "running service"
            );

            // Run the service. We do NOT race cancel.cancelled() against
            // service.run() — doing so could drop the service's future
            // before it can perform cleanup. The shutdown timeout in
            // wait_for_drain is the safety net for non-responsive services.
            let result = service.run(cancel.clone()).await;

            if cancel.is_cancelled() {
                tracing::info!(service = %service_name, "service exited after cancellation");
                let _ = lifecycle.transition_to_stopping();
                let _ = lifecycle.transition_to_terminated(TerminationReason::Cancelled);
                Self::update_lifecycle(&lifecycles, &service_name, &lifecycle).await;
                metrics.record_termination();
                return;
            }

            match result {
                Ok(()) => {
                    tracing::info!(service = %service_name, "service exited cleanly");
                    backoff.maybe_reset_on_cooldown();

                    match restart_policy {
                        RestartPolicy::Always => {
                            // Clean exit means service completed successfully —
                            // explicitly reset backoff state so stale attempt
                            // counts don't bleed into clean-exit restart cycles.
                            backoff.reset();

                            tracing::info!(
                                service = %service_name,
                                "restart_policy=always, will restart after backoff"
                            );
                            let delay = Duration::from_millis(100);
                            let _ = lifecycle
                                .transition_to_backing_off("clean exit, policy=always", delay);
                            Self::update_lifecycle(&lifecycles, &service_name, &lifecycle).await;

                            tokio::select! {
                                _ = cancel.cancelled() => {
                                    let _ = lifecycle.transition_to_stopping();
                                    let _ = lifecycle.transition_to_terminated(TerminationReason::Cancelled);
                                    Self::update_lifecycle(&lifecycles, &service_name, &lifecycle).await;
                                    metrics.record_termination();
                                    return;
                                }
                                _ = tokio::time::sleep(delay) => {}
                            }
                            continue;
                        }
                        RestartPolicy::OnFailure | RestartPolicy::Never => {
                            let _ =
                                lifecycle.transition_to_terminated(TerminationReason::Completed);
                            Self::update_lifecycle(&lifecycles, &service_name, &lifecycle).await;
                            metrics.record_termination();
                            return;
                        }
                    }
                }

                Err(err) => {
                    let error_msg = format!("{err:#}");
                    tracing::error!(
                        service = %service_name,
                        error = %error_msg,
                        "service failed"
                    );

                    backoff.maybe_reset_on_cooldown();

                    match restart_policy {
                        RestartPolicy::Never => {
                            tracing::warn!(
                                service = %service_name,
                                "restart_policy=never, service will not be restarted"
                            );
                            let _ = lifecycle.transition_to_terminated(
                                TerminationReason::Unrecoverable(error_msg),
                            );
                            Self::update_lifecycle(&lifecycles, &service_name, &lifecycle).await;
                            metrics.record_termination();
                            return;
                        }

                        RestartPolicy::OnFailure | RestartPolicy::Always => {
                            match backoff.next_backoff() {
                                BackoffAction::Retry(delay) => {
                                    tracing::info!(
                                        service = %service_name,
                                        delay_ms = delay.as_millis() as u64,
                                        attempt = backoff.attempt(),
                                        "scheduling restart after backoff"
                                    );

                                    let _ =
                                        lifecycle.transition_to_backing_off(&error_msg, delay);
                                    Self::update_lifecycle(&lifecycles, &service_name, &lifecycle)
                                        .await;

                                    tokio::select! {
                                        _ = cancel.cancelled() => {
                                            tracing::info!(
                                                service = %service_name,
                                                "cancellation during backoff"
                                            );
                                            let _ = lifecycle.transition_to_stopping();
                                            let _ = lifecycle.transition_to_terminated(
                                                TerminationReason::Cancelled,
                                            );
                                            Self::update_lifecycle(&lifecycles, &service_name, &lifecycle).await;
                                            metrics.record_termination();
                                            return;
                                        }
                                        _ = tokio::time::sleep(delay) => {}
                                    }
                                }

                                BackoffAction::CircuitOpen {
                                    failures,
                                    max_retries,
                                } => {
                                    tracing::error!(
                                        service = %service_name,
                                        failures = failures,
                                        max_retries = max_retries,
                                        "CIRCUIT BREAKER OPEN — too many failures, giving up"
                                    );
                                    metrics.record_circuit_breaker_trip();

                                    let _ = lifecycle.transition_to_terminated(
                                        TerminationReason::CircuitBreakerOpen {
                                            failures,
                                            max_retries,
                                        },
                                    );
                                    Self::update_lifecycle(&lifecycles, &service_name, &lifecycle)
                                        .await;
                                    metrics.record_termination();
                                    return;
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    async fn update_lifecycle(
        lifecycles: &Arc<RwLock<HashMap<String, ServiceLifecycle>>>,
        name: &str,
        lifecycle: &ServiceLifecycle,
    ) {
        let mut lc_map = lifecycles.write().await;
        lc_map.insert(name.to_string(), lifecycle.clone());
    }

    // ── Shutdown coordination ─────────────────────────────────────────

    /// Close the tracker and wait for all tasks to complete, with timeout.
    #[tracing::instrument(skip(self), fields(timeout_secs = self.config.shutdown_timeout.as_secs()))]
    /// Close the task tracker and wait for every spawned task to exit, up
    /// to [`SupervisorConfig::shutdown_timeout`].
    pub async fn wait_for_drain(&self) {
        self.tracker.close();

        tracing::info!(
            timeout_secs = self.config.shutdown_timeout.as_secs(),
            "waiting for all services to drain"
        );

        match tokio::time::timeout(self.config.shutdown_timeout, self.tracker.wait()).await {
            Ok(()) => tracing::info!("all services drained successfully"),
            Err(_) => tracing::warn!(
                timeout_secs = self.config.shutdown_timeout.as_secs(),
                "shutdown timeout exceeded, some services may not have exited cleanly"
            ),
        }
    }

    /// Run the supervisor until a shutdown signal is received.
    #[tracing::instrument(skip(self), fields(signal_handler = self.config.install_signal_handler))]
    /// Block until shutdown is triggered (signal or programmatic), then
    /// drain. Returns once every supervised service has exited or the
    /// drain timeout has fired.
    pub async fn run_until_shutdown(&self) -> anyhow::Result<()> {
        if self.config.install_signal_handler {
            self.wait_for_signal_and_shutdown().await?;
        } else {
            self.cancel_token.cancelled().await;
            tracing::info!("external shutdown signal received");
        }

        self.wait_for_drain().await;

        let snap = self.metrics.snapshot();
        tracing::info!(
            restarts = snap.restarts_total,
            spawned = snap.spawned_total,
            terminated = snap.terminated_total,
            circuit_trips = snap.circuit_breaker_trips,
            "supervisor shutdown complete"
        );

        Ok(())
    }

    async fn wait_for_signal_and_shutdown(&self) -> anyhow::Result<()> {
        #[cfg(unix)]
        {
            use tokio::signal::unix::{SignalKind, signal};

            let mut sigterm = signal(SignalKind::terminate())?;
            let mut sigint = signal(SignalKind::interrupt())?;

            tokio::select! {
                _ = sigterm.recv() => tracing::info!("received SIGTERM"),
                _ = sigint.recv()  => tracing::info!("received SIGINT"),
                _ = self.cancel_token.cancelled() => {
                    tracing::info!("shutdown triggered programmatically");
                    return Ok(());
                }
            }
        }

        #[cfg(not(unix))]
        {
            tokio::select! {
                result = tokio::signal::ctrl_c() => {
                    result?;
                    tracing::info!("received Ctrl+C");
                }
                _ = self.cancel_token.cancelled() => {
                    tracing::info!("shutdown triggered programmatically");
                    return Ok(());
                }
            }
        }

        self.cancel_token.cancel();
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    struct CountingService {
        name: String,
        policy: RestartPolicy,
        run_count: Arc<AtomicU64>,
    }

    impl CountingService {
        fn new(name: &str, policy: RestartPolicy) -> (Self, Arc<AtomicU64>) {
            let count = Arc::new(AtomicU64::new(0));
            (
                Self {
                    name: name.to_string(),
                    policy,
                    run_count: count.clone(),
                },
                count,
            )
        }
    }

    #[async_trait::async_trait]
    impl TradingService for CountingService {
        fn name(&self) -> &str {
            &self.name
        }

        fn restart_policy(&self) -> RestartPolicy {
            self.policy
        }

        async fn run(&self, cancel: CancellationToken) -> anyhow::Result<()> {
            self.run_count.fetch_add(1, Ordering::SeqCst);
            cancel.cancelled().await;
            Ok(())
        }
    }

    struct FailNTimes {
        name: String,
        fail_count: u32,
        current: Arc<AtomicU64>,
    }

    impl FailNTimes {
        fn new(name: &str, fail_count: u32) -> (Self, Arc<AtomicU64>) {
            let current = Arc::new(AtomicU64::new(0));
            (
                Self {
                    name: name.to_string(),
                    fail_count,
                    current: current.clone(),
                },
                current,
            )
        }
    }

    #[async_trait::async_trait]
    impl TradingService for FailNTimes {
        fn name(&self) -> &str {
            &self.name
        }

        async fn run(&self, cancel: CancellationToken) -> anyhow::Result<()> {
            let attempt = self.current.fetch_add(1, Ordering::SeqCst) as u32;
            if attempt < self.fail_count {
                tokio::time::sleep(Duration::from_millis(1)).await;
                anyhow::bail!("simulated failure #{}", attempt + 1);
            }
            cancel.cancelled().await;
            Ok(())
        }
    }

    struct AlwaysFailService {
        name: String,
        attempts: Arc<AtomicU64>,
    }

    impl AlwaysFailService {
        fn new(name: &str) -> (Self, Arc<AtomicU64>) {
            let attempts = Arc::new(AtomicU64::new(0));
            (
                Self {
                    name: name.to_string(),
                    attempts: attempts.clone(),
                },
                attempts,
            )
        }
    }

    #[async_trait::async_trait]
    impl TradingService for AlwaysFailService {
        fn name(&self) -> &str {
            &self.name
        }

        async fn run(&self, _cancel: CancellationToken) -> anyhow::Result<()> {
            self.attempts.fetch_add(1, Ordering::SeqCst);
            tokio::time::sleep(Duration::from_millis(1)).await;
            anyhow::bail!("permanent failure");
        }
    }

    #[tokio::test]
    async fn test_supervisor_creation() {
        let sup = Supervisor::with_defaults();
        assert!(!sup.is_shutting_down());
        assert_eq!(sup.service_count().await, 0);
    }

    #[tokio::test]
    async fn test_spawn_and_cancel_single_service() {
        let config = SupervisorConfig::default().without_signal_handler();
        let sup = Supervisor::new(config);

        let (svc, count) = CountingService::new("test-svc", RestartPolicy::OnFailure);
        sup.spawn_service(Box::new(svc));

        tokio::time::sleep(Duration::from_millis(50)).await;

        assert_eq!(count.load(Ordering::SeqCst), 1);
        assert_eq!(sup.metrics().active_services.load(Ordering::Relaxed), 1);

        sup.trigger_shutdown();
        sup.wait_for_drain().await;

        let snap = sup.metrics().snapshot();
        assert_eq!(snap.spawned_total, 1);
        assert_eq!(snap.terminated_total, 1);
        assert_eq!(snap.active_services, 0);
    }

    #[tokio::test]
    async fn test_service_restart_on_failure() {
        let config = SupervisorConfig::default()
            .without_signal_handler()
            .with_default_backoff(
                BackoffConfig::new(Duration::from_millis(10), Duration::from_millis(50))
                    .without_circuit_breaker(),
            );

        let sup = Supervisor::new(config);

        let (svc, attempts) = FailNTimes::new("fail-3", 3);
        sup.spawn_service(Box::new(svc));

        tokio::time::sleep(Duration::from_millis(500)).await;

        assert!(
            attempts.load(Ordering::SeqCst) >= 4,
            "expected >= 4 attempts, got {}",
            attempts.load(Ordering::SeqCst)
        );

        sup.trigger_shutdown();
        sup.wait_for_drain().await;

        let snap = sup.metrics().snapshot();
        assert!(snap.restarts_total >= 3);
    }

    #[tokio::test]
    async fn test_circuit_breaker_trips() {
        let config = SupervisorConfig::default()
            .without_signal_handler()
            .with_default_backoff(
                BackoffConfig::new(Duration::from_millis(5), Duration::from_millis(20))
                    .with_circuit_breaker(3, Duration::from_secs(60)),
            );

        let sup = Supervisor::new(config);

        let (svc, attempts) = AlwaysFailService::new("always-fail");
        sup.spawn_service(Box::new(svc));

        tokio::time::sleep(Duration::from_millis(500)).await;

        let att = attempts.load(Ordering::SeqCst);
        assert!(att >= 3, "expected at least 3 attempts, got {att}");

        let snap = sup.metrics().snapshot();
        assert_eq!(snap.circuit_breaker_trips, 1);
        assert_eq!(snap.terminated_total, 1);

        sup.trigger_shutdown();
        sup.wait_for_drain().await;
    }

    #[tokio::test]
    async fn test_lifecycle_snapshots() {
        let config = SupervisorConfig::default().without_signal_handler();
        let sup = Supervisor::new(config);

        let (svc, _) = CountingService::new("lifecycle-test", RestartPolicy::OnFailure);
        sup.spawn_service(Box::new(svc));

        tokio::time::sleep(Duration::from_millis(50)).await;

        let snapshots = sup.lifecycle_snapshots().await;
        assert_eq!(snapshots.len(), 1);
        assert_eq!(snapshots[0].phase, ServicePhase::Running);

        sup.trigger_shutdown();
        sup.wait_for_drain().await;

        let snapshots = sup.lifecycle_snapshots().await;
        assert_eq!(snapshots[0].phase, ServicePhase::Terminated);
    }

    #[tokio::test]
    async fn test_shutdown_timeout() {
        let config = SupervisorConfig::default()
            .without_signal_handler()
            .with_shutdown_timeout(Duration::from_millis(100));

        let sup = Supervisor::new(config);

        struct HangingService;

        #[async_trait::async_trait]
        impl TradingService for HangingService {
            fn name(&self) -> &str {
                "hanger"
            }
            async fn run(&self, _cancel: CancellationToken) -> anyhow::Result<()> {
                tokio::time::sleep(Duration::from_secs(3600)).await;
                Ok(())
            }
        }

        sup.spawn_service(Box::new(HangingService));
        tokio::time::sleep(Duration::from_millis(20)).await;

        sup.trigger_shutdown();

        let start = std::time::Instant::now();
        sup.wait_for_drain().await;
        let elapsed = start.elapsed();

        assert!(elapsed < Duration::from_secs(1), "drain took too long: {elapsed:?}");
    }

    #[tokio::test]
    async fn test_chaos_mixed_fleet() {
        let backoff = BackoffConfig::new(Duration::from_millis(10), Duration::from_millis(100))
            .with_circuit_breaker(3, Duration::from_secs(60));

        let config = SupervisorConfig::default()
            .with_shutdown_timeout(Duration::from_secs(5))
            .with_default_backoff(backoff)
            .without_signal_handler();

        let sup = Supervisor::new(config);

        let (healthy, _) = CountingService::new("healthy-api", RestartPolicy::OnFailure);
        let (bad, _) = AlwaysFailService::new("bad-data");
        let (recovering, recovering_attempts) = FailNTimes::new("flaky-cns", 2);

        sup.spawn_service(Box::new(healthy));
        sup.spawn_service(Box::new(bad));
        sup.spawn_service(Box::new(recovering));

        let deadline = tokio::time::Instant::now() + Duration::from_secs(10);
        loop {
            let bad_done = sup
                .service_lifecycle("bad-data")
                .await
                .is_some_and(|s| s.phase == ServicePhase::Terminated);
            let recovered = recovering_attempts.load(Ordering::SeqCst) >= 3;
            if bad_done && recovered {
                break;
            }
            if tokio::time::Instant::now() > deadline {
                panic!("mixed fleet did not reach expected state in time");
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }

        let healthy_snap = sup.service_lifecycle("healthy-api").await.unwrap();
        assert!(healthy_snap.phase.is_alive());

        let bad_snap = sup.service_lifecycle("bad-data").await.unwrap();
        assert_eq!(bad_snap.phase, ServicePhase::Terminated);
        assert!(
            bad_snap
                .termination_reason
                .as_deref()
                .is_some_and(|r| r.contains("circuit breaker"))
        );

        sup.trigger_shutdown();
        sup.wait_for_drain().await;

        let metrics = sup.metrics().snapshot();
        assert_eq!(metrics.active_services, 0);
        assert_eq!(metrics.spawned_total, 3);
        assert_eq!(metrics.terminated_total, 3);
    }
}
