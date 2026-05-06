//! Service lifecycle state machine for the [`Supervisor`](crate::Supervisor).
//!
//! Each service progresses through a deterministic state machine:
//!
//! ```text
//!   ┌──────────┐
//!   │ Starting │──────────────────────────┐
//!   └────┬─────┘                          │
//!        │ run() entered                  │ init error
//!        ▼                                ▼
//!   ┌──────────┐                    ┌────────────┐
//!   │ Running  │───── error ──────▶│ BackingOff │
//!   └────┬─────┘                    └──────┬─────┘
//!        │                                 │
//!        │ cancel / Ok(())                 │ retry
//!        │                                 │
//!        │    ┌────────────────────────────┘
//!        ▼    ▼
//!   ┌──────────┐         ┌────────────┐
//!   │ Stopping │────────▶│ Terminated │
//!   └──────────┘         └────────────┘
//! ```

use std::fmt;
use std::time::{Duration, Instant};

/// Lifecycle phase of a supervised service.
#[allow(missing_docs)] // names mirror the state-machine diagram in the module-level docs
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ServicePhase {
    Starting,
    Running,
    BackingOff,
    Stopping,
    Terminated,
}

impl fmt::Display for ServicePhase {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Starting => write!(f, "starting"),
            Self::Running => write!(f, "running"),
            Self::BackingOff => write!(f, "backing_off"),
            Self::Stopping => write!(f, "stopping"),
            Self::Terminated => write!(f, "terminated"),
        }
    }
}

impl ServicePhase {
    /// `true` if the phase is `Terminated`.
    pub fn is_terminal(&self) -> bool {
        matches!(self, Self::Terminated)
    }

    /// `true` if the service is in any non-terminal phase that the
    /// supervisor still considers running.
    pub fn is_alive(&self) -> bool {
        matches!(self, Self::Starting | Self::Running | Self::BackingOff)
    }
}

/// Why a service reached the `Terminated` phase.
#[allow(missing_docs)] // variants describe themselves; the enum doc covers the meaning
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TerminationReason {
    Completed,
    Cancelled,
    CircuitBreakerOpen {
        /// Failures observed at the moment of trip.
        failures: u32,
        /// Configured trip threshold.
        max_retries: u32,
    },
    Unrecoverable(String),
}

impl fmt::Display for TerminationReason {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Completed => write!(f, "completed"),
            Self::Cancelled => write!(f, "cancelled"),
            Self::CircuitBreakerOpen {
                failures,
                max_retries,
            } => write!(f, "circuit breaker open ({failures}/{max_retries} failures)"),
            Self::Unrecoverable(msg) => write!(f, "unrecoverable: {msg}"),
        }
    }
}

/// Returned when an invalid state transition is attempted on a
/// [`ServiceLifecycle`].
#[allow(missing_docs)] // self-evident from/to fields
#[derive(Debug, Clone, thiserror::Error)]
#[error("invalid lifecycle transition: {from} → {to}")]
pub struct TransitionError {
    pub from: ServicePhase,
    pub to: ServicePhase,
}

/// Full lifecycle tracker for a single supervised service.
#[derive(Debug, Clone)]
pub struct ServiceLifecycle {
    phase: ServicePhase,
    service_name: String,
    created_at: Instant,
    phase_entered_at: Instant,
    start_count: u32,
    total_failures: u32,
    last_error: Option<String>,
    termination_reason: Option<TerminationReason>,
    cumulative_running: Duration,
    running_since: Option<Instant>,
}

impl ServiceLifecycle {
    /// Build a fresh lifecycle in the `Starting` phase.
    pub fn new(service_name: impl Into<String>) -> Self {
        let now = Instant::now();
        Self {
            phase: ServicePhase::Starting,
            service_name: service_name.into(),
            created_at: now,
            phase_entered_at: now,
            start_count: 1,
            total_failures: 0,
            last_error: None,
            termination_reason: None,
            cumulative_running: Duration::ZERO,
            running_since: None,
        }
    }

    /// Current phase.
    pub fn phase(&self) -> ServicePhase {
        self.phase
    }

    /// Name passed to [`Self::new`].
    pub fn service_name(&self) -> &str {
        &self.service_name
    }

    /// Wall-clock time since first construction.
    pub fn age(&self) -> Duration {
        self.created_at.elapsed()
    }

    /// Time elapsed since the most recent phase transition.
    pub fn time_in_current_phase(&self) -> Duration {
        self.phase_entered_at.elapsed()
    }

    /// Total number of times the service has entered `Starting`.
    pub fn start_count(&self) -> u32 {
        self.start_count
    }

    /// Total failures observed across the lifetime of this service.
    pub fn total_failures(&self) -> u32 {
        self.total_failures
    }

    /// Stringified message of the most recent failure, if any.
    pub fn last_error(&self) -> Option<&str> {
        self.last_error.as_deref()
    }

    /// `Some` once the service has terminated.
    pub fn termination_reason(&self) -> Option<&TerminationReason> {
        self.termination_reason.as_ref()
    }

    /// Cumulative time spent in the `Running` phase.
    pub fn cumulative_running_time(&self) -> Duration {
        let extra = self
            .running_since
            .map(|since| since.elapsed())
            .unwrap_or(Duration::ZERO);
        self.cumulative_running + extra
    }

    /// Transition `Starting → Running`.
    pub fn transition_to_running(&mut self) -> Result<(), TransitionError> {
        self.validate_transition(ServicePhase::Running)?;
        self.set_phase(ServicePhase::Running);
        self.running_since = Some(Instant::now());
        tracing::info!(
            service = %self.service_name,
            start_count = self.start_count,
            "service entered Running phase"
        );
        Ok(())
    }

    /// Transition any alive phase → `BackingOff` after a failure.
    pub fn transition_to_backing_off(
        &mut self,
        error: &str,
        backoff_duration: Duration,
    ) -> Result<(), TransitionError> {
        self.validate_transition(ServicePhase::BackingOff)?;
        self.accumulate_running_time();
        self.total_failures += 1;
        self.last_error = Some(error.to_string());
        self.set_phase(ServicePhase::BackingOff);
        tracing::warn!(
            service = %self.service_name,
            error = %error,
            attempt = self.total_failures,
            backoff_ms = backoff_duration.as_millis() as u64,
            "service failed, entering BackingOff phase"
        );
        Ok(())
    }

    /// Transition `BackingOff → Starting` for a restart attempt.
    pub fn transition_to_restarting(&mut self) -> Result<(), TransitionError> {
        self.validate_transition(ServicePhase::Starting)?;
        self.start_count += 1;
        self.set_phase(ServicePhase::Starting);
        tracing::info!(
            service = %self.service_name,
            start_count = self.start_count,
            "service restarting (entering Starting phase)"
        );
        Ok(())
    }

    /// Transition any alive phase → `Stopping` (graceful shutdown).
    pub fn transition_to_stopping(&mut self) -> Result<(), TransitionError> {
        self.validate_transition(ServicePhase::Stopping)?;
        self.accumulate_running_time();
        self.set_phase(ServicePhase::Stopping);
        tracing::info!(
            service = %self.service_name,
            "service entering Stopping phase"
        );
        Ok(())
    }

    /// Transition any phase → `Terminated` with a reason.
    pub fn transition_to_terminated(
        &mut self,
        reason: TerminationReason,
    ) -> Result<(), TransitionError> {
        self.validate_transition(ServicePhase::Terminated)?;
        self.accumulate_running_time();
        self.termination_reason = Some(reason.clone());
        self.set_phase(ServicePhase::Terminated);
        tracing::info!(
            service = %self.service_name,
            reason = %reason,
            total_starts = self.start_count,
            total_failures = self.total_failures,
            cumulative_running_secs = self.cumulative_running.as_secs_f64(),
            "service terminated"
        );
        Ok(())
    }

    fn validate_transition(&self, target: ServicePhase) -> Result<(), TransitionError> {
        let valid = matches!(
            (self.phase, target),
            (ServicePhase::Starting, ServicePhase::Running)
                | (ServicePhase::Starting, ServicePhase::Terminated)
                | (ServicePhase::Starting, ServicePhase::Stopping)
                | (ServicePhase::Starting, ServicePhase::BackingOff)
                | (ServicePhase::Running, ServicePhase::BackingOff)
                | (ServicePhase::Running, ServicePhase::Stopping)
                | (ServicePhase::Running, ServicePhase::Terminated)
                | (ServicePhase::BackingOff, ServicePhase::Starting)
                | (ServicePhase::BackingOff, ServicePhase::Stopping)
                | (ServicePhase::BackingOff, ServicePhase::Terminated)
                | (ServicePhase::Stopping, ServicePhase::Terminated)
        );

        if valid {
            Ok(())
        } else {
            Err(TransitionError {
                from: self.phase,
                to: target,
            })
        }
    }

    fn set_phase(&mut self, phase: ServicePhase) {
        self.phase = phase;
        self.phase_entered_at = Instant::now();
    }

    fn accumulate_running_time(&mut self) {
        if let Some(since) = self.running_since.take() {
            self.cumulative_running += since.elapsed();
        }
    }
}

impl fmt::Display for ServiceLifecycle {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{}[{}] starts={} failures={} running={:.1}s",
            self.service_name,
            self.phase,
            self.start_count,
            self.total_failures,
            self.cumulative_running_time().as_secs_f64(),
        )
    }
}

/// Point-in-time snapshot of a service's lifecycle, suitable for
/// serialization (e.g. into a `/health` endpoint).
#[allow(missing_docs)] // self-evident from the matching `ServiceLifecycle` field/getter docs
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ServiceLifecycleSnapshot {
    pub service_name: String,
    pub phase: ServicePhase,
    pub start_count: u32,
    pub total_failures: u32,
    pub last_error: Option<String>,
    pub cumulative_running_secs: f64,
    pub age_secs: f64,
    pub time_in_phase_secs: f64,
    pub termination_reason: Option<String>,
}

impl From<&ServiceLifecycle> for ServiceLifecycleSnapshot {
    fn from(lc: &ServiceLifecycle) -> Self {
        Self {
            service_name: lc.service_name.clone(),
            phase: lc.phase,
            start_count: lc.start_count,
            total_failures: lc.total_failures,
            last_error: lc.last_error.clone(),
            cumulative_running_secs: lc.cumulative_running_time().as_secs_f64(),
            age_secs: lc.age().as_secs_f64(),
            time_in_phase_secs: lc.time_in_current_phase().as_secs_f64(),
            termination_reason: lc.termination_reason.as_ref().map(|r| r.to_string()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_lifecycle_starts_in_starting() {
        let lc = ServiceLifecycle::new("test-svc");
        assert_eq!(lc.phase(), ServicePhase::Starting);
        assert_eq!(lc.start_count(), 1);
        assert_eq!(lc.total_failures(), 0);
        assert!(lc.last_error().is_none());
        assert!(lc.termination_reason().is_none());
    }

    #[test]
    fn test_happy_path() {
        let mut lc = ServiceLifecycle::new("happy");
        lc.transition_to_running().unwrap();
        lc.transition_to_stopping().unwrap();
        lc.transition_to_terminated(TerminationReason::Cancelled)
            .unwrap();
        assert_eq!(lc.phase(), ServicePhase::Terminated);
        assert_eq!(lc.termination_reason(), Some(&TerminationReason::Cancelled));
    }

    #[test]
    fn test_failure_and_restart_cycle() {
        let mut lc = ServiceLifecycle::new("flaky");
        lc.transition_to_running().unwrap();
        lc.transition_to_backing_off("connection refused", Duration::from_millis(200))
            .unwrap();
        assert_eq!(lc.phase(), ServicePhase::BackingOff);
        assert_eq!(lc.total_failures(), 1);

        lc.transition_to_restarting().unwrap();
        assert_eq!(lc.phase(), ServicePhase::Starting);
        assert_eq!(lc.start_count(), 2);

        lc.transition_to_running().unwrap();
        assert_eq!(lc.phase(), ServicePhase::Running);
    }

    #[test]
    fn test_invalid_transition_terminated_to_anything() {
        let mut lc = ServiceLifecycle::new("dead");
        lc.transition_to_running().unwrap();
        lc.transition_to_terminated(TerminationReason::Completed)
            .unwrap();

        assert!(lc.transition_to_running().is_err());
        assert!(lc.transition_to_stopping().is_err());
        assert!(
            lc.transition_to_terminated(TerminationReason::Cancelled)
                .is_err()
        );
        assert!(lc.transition_to_restarting().is_err());
    }

    #[test]
    fn test_phase_display() {
        assert_eq!(ServicePhase::Starting.to_string(), "starting");
        assert_eq!(ServicePhase::Running.to_string(), "running");
        assert_eq!(ServicePhase::BackingOff.to_string(), "backing_off");
        assert_eq!(ServicePhase::Stopping.to_string(), "stopping");
        assert_eq!(ServicePhase::Terminated.to_string(), "terminated");
    }

    #[test]
    fn test_phase_predicates() {
        assert!(ServicePhase::Terminated.is_terminal());
        assert!(!ServicePhase::Running.is_terminal());
        assert!(ServicePhase::Starting.is_alive());
        assert!(ServicePhase::Running.is_alive());
        assert!(ServicePhase::BackingOff.is_alive());
        assert!(!ServicePhase::Stopping.is_alive());
        assert!(!ServicePhase::Terminated.is_alive());
    }

    #[test]
    fn test_snapshot_from_lifecycle() {
        let mut lc = ServiceLifecycle::new("snapshot-svc");
        lc.transition_to_running().unwrap();
        lc.transition_to_backing_off("oops", Duration::from_millis(100))
            .unwrap();

        let snap = ServiceLifecycleSnapshot::from(&lc);
        assert_eq!(snap.service_name, "snapshot-svc");
        assert_eq!(snap.phase, ServicePhase::BackingOff);
        assert_eq!(snap.start_count, 1);
        assert_eq!(snap.total_failures, 1);
        assert_eq!(snap.last_error.as_deref(), Some("oops"));
        assert!(snap.termination_reason.is_none());
        assert!(snap.age_secs >= 0.0);
    }
}
