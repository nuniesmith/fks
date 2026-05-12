//! [`Bot`] — the entry point most users will use directly.
//!
//! Wires a fleet of [`Brain`]s and one [`ExchangeClient`] into a supervised
//! runtime. See the crate-level docs for usage.

use std::sync::Arc;

use rustrade_core::{Brain, ExchangeClient, MarketDataBus};
use rustrade_risk::{CircuitBreaker, CircuitBreakerConfig, SessionPnl, SessionPnlConfig};
use rustrade_supervisor::{Supervisor, SupervisorConfig};
use tokio::sync::Mutex;

use crate::execution::{ExecutionConfig, ExecutionService};

/// User-facing bot configuration.
///
/// Reasonable defaults; override only the bits you care about.
#[allow(missing_docs)] // each field has its own /// doc; struct itself is the API surface
#[derive(Debug, Clone)]
pub struct BotConfig {
    pub name: String,
    pub supervisor: SupervisorConfig,
    pub execution: ExecutionConfig,
    pub circuit_breaker: CircuitBreakerConfig,
    pub session_pnl: SessionPnlConfig,
    /// PnL accounting symbol for [`SessionPnl`]. Most single-symbol bots
    /// pass the trading symbol here; multi-symbol bots can pass `"portfolio"`
    /// or similar.
    pub session_symbol: String,
    /// On graceful shutdown, attempt to close any open positions on the
    /// exchange before exiting.
    pub close_positions_on_shutdown: bool,
    /// Symbols to flatten on shutdown (only consulted when
    /// `close_positions_on_shutdown` is `true`). If empty, no positions
    /// are closed even if the flag is set — the bot doesn't attempt to
    /// enumerate every symbol the exchange knows about.
    pub flatten_symbols: Vec<String>,
}

impl BotConfig {
    /// Build a config with the given name and defaults everywhere else.
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            supervisor: SupervisorConfig::default(),
            execution: ExecutionConfig::default(),
            circuit_breaker: CircuitBreakerConfig::default(),
            session_pnl: SessionPnlConfig::default(),
            session_symbol: "portfolio".to_string(),
            close_positions_on_shutdown: false,
            flatten_symbols: Vec::new(),
        }
    }

    /// Fluent builder. Equivalent to chaining the `with_*` methods on
    /// [`BotConfig::new`], but reads more naturally for multi-line configs.
    ///
    /// ```ignore
    /// let cfg = BotConfig::builder()
    ///     .name("kucoin")
    ///     .session_symbol("XBTUSDTM")
    ///     .close_positions_on_shutdown(true)
    ///     .flatten_symbols(["XBTUSDTM", "ETHUSDTM"])
    ///     .build();
    /// ```
    pub fn builder() -> BotConfigBuilder {
        BotConfigBuilder::default()
    }

    /// Builder: override the supervisor config.
    pub fn with_supervisor(mut self, supervisor: SupervisorConfig) -> Self {
        self.supervisor = supervisor;
        self
    }

    /// Builder: override the execution config.
    pub fn with_execution(mut self, execution: ExecutionConfig) -> Self {
        self.execution = execution;
        self
    }

    /// Builder: override the circuit-breaker config.
    pub fn with_circuit_breaker(mut self, cfg: CircuitBreakerConfig) -> Self {
        self.circuit_breaker = cfg;
        self
    }

    /// Builder: override the session-PnL config.
    pub fn with_session_pnl(mut self, cfg: SessionPnlConfig) -> Self {
        self.session_pnl = cfg;
        self
    }

    /// Builder: set the symbol attached to the [`SessionPnl`] tracker.
    pub fn with_session_symbol(mut self, symbol: impl Into<String>) -> Self {
        self.session_symbol = symbol.into();
        self
    }

    /// Builder: enable position-flatten-on-shutdown.
    pub fn with_close_positions_on_shutdown(mut self, close: bool) -> Self {
        self.close_positions_on_shutdown = close;
        self
    }

    /// Builder: list the symbols to flatten on shutdown (only consulted
    /// when `close_positions_on_shutdown == true`).
    pub fn with_flatten_symbols<I, S>(mut self, symbols: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.flatten_symbols = symbols.into_iter().map(Into::into).collect();
        self
    }
}

/// Fluent builder for [`BotConfig`].
///
/// Every field has a sensible default, so building is infallible.
#[derive(Debug, Default, Clone)]
pub struct BotConfigBuilder {
    name: Option<String>,
    supervisor: Option<SupervisorConfig>,
    execution: Option<ExecutionConfig>,
    circuit_breaker: Option<CircuitBreakerConfig>,
    session_pnl: Option<SessionPnlConfig>,
    session_symbol: Option<String>,
    close_positions_on_shutdown: bool,
    flatten_symbols: Vec<String>,
}

impl BotConfigBuilder {
    /// Set the bot name.
    pub fn name(mut self, name: impl Into<String>) -> Self {
        self.name = Some(name.into());
        self
    }

    /// Set the supervisor config.
    pub fn supervisor(mut self, cfg: SupervisorConfig) -> Self {
        self.supervisor = Some(cfg);
        self
    }

    /// Set the execution-service config.
    pub fn execution(mut self, cfg: ExecutionConfig) -> Self {
        self.execution = Some(cfg);
        self
    }

    /// Set the circuit-breaker config.
    pub fn circuit_breaker(mut self, cfg: CircuitBreakerConfig) -> Self {
        self.circuit_breaker = Some(cfg);
        self
    }

    /// Set the session-PnL config.
    pub fn session_pnl(mut self, cfg: SessionPnlConfig) -> Self {
        self.session_pnl = Some(cfg);
        self
    }

    /// Set the symbol attached to the session-PnL tracker.
    pub fn session_symbol(mut self, symbol: impl Into<String>) -> Self {
        self.session_symbol = Some(symbol.into());
        self
    }

    /// Enable position-flatten-on-shutdown.
    pub fn close_positions_on_shutdown(mut self, close: bool) -> Self {
        self.close_positions_on_shutdown = close;
        self
    }

    /// Symbols to flatten on shutdown.
    pub fn flatten_symbols<I, S>(mut self, symbols: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.flatten_symbols = symbols.into_iter().map(Into::into).collect();
        self
    }

    /// Finalise into a [`BotConfig`].
    pub fn build(self) -> BotConfig {
        BotConfig {
            name: self.name.unwrap_or_else(|| "rustrade-bot".to_string()),
            supervisor: self.supervisor.unwrap_or_default(),
            execution: self.execution.unwrap_or_default(),
            circuit_breaker: self.circuit_breaker.unwrap_or_default(),
            session_pnl: self.session_pnl.unwrap_or_default(),
            session_symbol: self
                .session_symbol
                .unwrap_or_else(|| "portfolio".to_string()),
            close_positions_on_shutdown: self.close_positions_on_shutdown,
            flatten_symbols: self.flatten_symbols,
        }
    }
}

/// The framework runtime. Holds the supervisor, market bus, and shared
/// risk primitives that all spawned execution services see.
pub struct Bot {
    config: BotConfig,
    exchange: Arc<dyn ExchangeClient>,
    bus: MarketDataBus,
    breaker: Arc<Mutex<CircuitBreaker>>,
    session_pnl: Arc<Mutex<SessionPnl>>,
    supervisor: Supervisor,
}

impl Bot {
    /// Build a bot from config + exchange + brains. One execution service
    /// is spawned per brain; all of them share the same market bus, circuit
    /// breaker, and session PnL.
    pub fn new(
        config: BotConfig,
        exchange: Arc<dyn ExchangeClient>,
        brains: Vec<Arc<dyn Brain>>,
    ) -> Self {
        let bus = MarketDataBus::new();
        let breaker = Arc::new(Mutex::new(CircuitBreaker::new(
            config.circuit_breaker.clone(),
        )));
        let session_pnl = Arc::new(Mutex::new(SessionPnl::new(
            config.session_symbol.clone(),
            config.session_pnl.clone(),
        )));
        let supervisor = Supervisor::new(config.supervisor.clone());

        for brain in brains {
            let svc = ExecutionService::new(
                brain,
                Arc::clone(&exchange),
                bus.clone(),
                Arc::clone(&breaker),
                Arc::clone(&session_pnl),
                config.execution.clone(),
            );
            supervisor.spawn_service(Box::new(svc));
        }

        Self {
            config,
            exchange,
            bus,
            breaker,
            session_pnl,
            supervisor,
        }
    }

    /// Borrow the market bus so external code (a feed adapter, a test
    /// harness, a backtest replay) can publish events to the brain fleet.
    pub fn market_bus(&self) -> &MarketDataBus {
        &self.bus
    }

    /// Borrow the supervisor for advanced uses (custom services, lifecycle
    /// inspection, programmatic shutdown).
    pub fn supervisor(&self) -> &Supervisor {
        &self.supervisor
    }

    /// Shared circuit breaker — exchange-side or brain-side code can
    /// `record_loss()` / `record_win()` on it.
    pub fn circuit_breaker(&self) -> Arc<Mutex<CircuitBreaker>> {
        Arc::clone(&self.breaker)
    }

    /// Shared session PnL tracker.
    pub fn session_pnl(&self) -> Arc<Mutex<SessionPnl>> {
        Arc::clone(&self.session_pnl)
    }

    /// Run until Ctrl-C / SIGTERM, then drain services and (optionally)
    /// flatten positions before returning.
    pub async fn run_until_shutdown(self) -> anyhow::Result<()> {
        tracing::info!(bot = %self.config.name, "bot starting");

        self.supervisor.run_until_shutdown().await?;

        if self.config.close_positions_on_shutdown && !self.config.flatten_symbols.is_empty() {
            tracing::info!(
                bot = %self.config.name,
                symbols = ?self.config.flatten_symbols,
                "closing positions on shutdown"
            );
            for symbol in &self.config.flatten_symbols {
                match self.exchange.get_position(symbol).await {
                    Ok(pos) if !pos.is_flat() => {
                        match self.exchange.close_position(symbol, &pos).await {
                            Ok(order_id) => {
                                tracing::info!(symbol, order_id, "position closed on shutdown");
                            }
                            Err(e) => {
                                tracing::error!(symbol, error = %e, "close_position failed on shutdown");
                            }
                        }
                    }
                    Ok(_) => {
                        tracing::debug!(symbol, "already flat at shutdown");
                    }
                    Err(e) => {
                        tracing::error!(symbol, error = %e, "get_position failed at shutdown");
                    }
                }
            }
        }

        tracing::info!(bot = %self.config.name, "bot shutdown complete");
        Ok(())
    }
}
