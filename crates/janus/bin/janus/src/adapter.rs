//! Adapter layer between Janus's existing module entry points and the
//! `rustrade-supervisor::TradingService` trait.
//!
//! Existing Janus services (Forward, Backward, CNS, Data, API) expose a
//! `start_module(state: Arc<JanusState>) -> janus_core::Result<()>` entry
//! point that polls `state.is_shutdown_requested()` for lifecycle control.
//! `rustrade-supervisor` manages services through the [`TradingService`]
//! trait which passes a [`CancellationToken`].
//!
//! [`ModuleService`] is the bridge:
//!
//! 1. Wraps any `start_module`-style async function into a [`TradingService`].
//! 2. Spawns a small bridge task that watches the supervisor's
//!    `CancellationToken` and translates cancellation into
//!    `JanusState::request_shutdown()`.
//! 3. Aborts the bridge on natural module exit so the global shutdown flag
//!    isn't set when one module crashes (the supervisor needs the flag
//!    `false` so it can restart it).
//! 4. Registers per-module health on `JanusState` before/after the run, so
//!    `/api/health` reflects supervised lifecycle state.
//!
//! This is a verbatim port of `janus_core::supervisor::adapters::ModuleAdapter`
//! with two changes:
//!   - The trait being implemented is now `rustrade_supervisor::TradingService`
//!     (was `janus_core::supervisor::JanusService`). The two are functionally
//!     identical — see PR #1 for the verbatim port.
//!   - The convenience constructors are folded into one (`new` + the policy
//!     enum) instead of three named ones (`on_failure` / `always_restart` /
//!     `one_shot`). This binary only needs `OnFailure` and `Always` so the
//!     reduced surface is enough.

use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;

use async_trait::async_trait;
use rustrade_supervisor::{RestartPolicy, TradingService};
use tokio_util::sync::CancellationToken;
use tracing::{info, warn};

use janus_core::JanusState;

/// Boxed async function that takes `Arc<JanusState>` and returns a
/// `janus_core::Result<()>`. Matches the signature of every existing
/// Janus service's `start_module()` function.
pub type ModuleStartFn = Box<
    dyn Fn(Arc<JanusState>) -> Pin<Box<dyn Future<Output = janus_core::Result<()>> + Send>>
        + Send
        + Sync,
>;

/// Adapts an existing `start_module(Arc<JanusState>) -> Result<()>`
/// function into a [`TradingService`] the rustrade supervisor can manage.
pub struct ModuleService {
    name: String,
    state: Arc<JanusState>,
    start_fn: ModuleStartFn,
    policy: RestartPolicy,
}

impl ModuleService {
    /// Build a new module service with an explicit restart policy.
    pub fn new<F>(
        name: &str,
        state: Arc<JanusState>,
        start_fn: F,
        policy: RestartPolicy,
    ) -> Self
    where
        F: Fn(Arc<JanusState>) -> Pin<Box<dyn Future<Output = janus_core::Result<()>> + Send>>
            + Send
            + Sync
            + 'static,
    {
        Self {
            name: name.to_string(),
            state,
            start_fn: Box::new(start_fn),
            policy,
        }
    }

    /// Convenience: restart only on `Err` (the default).
    pub fn on_failure<F>(name: &str, state: Arc<JanusState>, start_fn: F) -> Self
    where
        F: Fn(Arc<JanusState>) -> Pin<Box<dyn Future<Output = janus_core::Result<()>> + Send>>
            + Send
            + Sync
            + 'static,
    {
        Self::new(name, state, start_fn, RestartPolicy::OnFailure)
    }

    /// Convenience: always restart (even on clean exit). Used for the
    /// always-on API module.
    pub fn always_restart<F>(name: &str, state: Arc<JanusState>, start_fn: F) -> Self
    where
        F: Fn(Arc<JanusState>) -> Pin<Box<dyn Future<Output = janus_core::Result<()>> + Send>>
            + Send
            + Sync
            + 'static,
    {
        Self::new(name, state, start_fn, RestartPolicy::Always)
    }
}

#[async_trait]
impl TradingService for ModuleService {
    fn name(&self) -> &str {
        &self.name
    }

    fn restart_policy(&self) -> RestartPolicy {
        self.policy
    }

    #[tracing::instrument(skip(self, cancel), fields(module = %self.name, policy = %self.policy))]
    async fn run(&self, cancel: CancellationToken) -> anyhow::Result<()> {
        // Defensive: warn if the global shutdown flag is already true.
        // The supervisor checks `cancel.is_cancelled()` before each
        // restart attempt and the bridge task is aborted on natural
        // module exit, so reaching this branch means an invariant has
        // been violated upstream.
        if self.state.is_shutdown_requested() {
            warn!(
                module = %self.name,
                "JanusState.shutdown_requested is already true at module start \
                 — the module may exit immediately. This indicates a stale \
                 shutdown flag from a previous lifecycle or a concurrent \
                 shutdown in progress."
            );
        }

        // Bridge task: translates supervisor cancellation → JanusState
        // shutdown flag, so existing modules don't have to grow a
        // CancellationToken parameter.
        let bridge_state = self.state.clone();
        let bridge_cancel = cancel.clone();
        let bridge_handle = tokio::spawn(async move {
            bridge_cancel.cancelled().await;
            info!("ModuleService shutdown bridge: cancellation received, requesting state shutdown");
            bridge_state.request_shutdown();
        });

        self.state
            .register_module_health(&self.name, true, Some("starting".to_string()))
            .await;

        let state_clone = self.state.clone();
        let module_result = (self.start_fn)(state_clone).await;

        // Abort the bridge so we don't set the global shutdown flag if
        // this module exited on its own (other modules + supervisor
        // restart logic depend on the flag staying false).
        bridge_handle.abort();

        match &module_result {
            Ok(()) => {
                self.state
                    .register_module_health(&self.name, true, Some("stopped".to_string()))
                    .await;
            }
            Err(e) => {
                self.state
                    .register_module_health(&self.name, false, Some(format!("error: {e}")))
                    .await;
            }
        }

        module_result.map_err(|e| anyhow::anyhow!("{}: {}", self.name, e))
    }
}

impl std::fmt::Debug for ModuleService {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ModuleService")
            .field("name", &self.name)
            .field("policy", &self.policy)
            .finish_non_exhaustive()
    }
}
