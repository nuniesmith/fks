//! The framework-side execution service.
//!
//! [`ExecutionService`] is what makes a [`Brain`] actually trade. It is a
//! [`TradingService`] (so the supervisor restarts it on failure) that:
//!
//! 1. Subscribes to a [`MarketDataBus`].
//! 2. On each event, fetches the current position from the exchange.
//! 3. Calls `brain.on_event(event, position)` to get a [`Decision`].
//! 4. Translates the `Decision` into an [`Order`] and places it via the
//!    [`ExchangeClient`] — but only if the bot's [`CircuitBreaker`] is
//!    closed and [`SessionPnl`] is not halted.
//! 5. Notifies the brain via `on_position_change` after the order is placed.
//!
//! # Sizing
//!
//! The framework defers sizing decisions to the brain via [`SizeHint`]:
//!
//! - `Quantity(v)`        → place an order for exactly `v` units.
//! - `NotionalUsd(usd)`   → `usd / last_price` units.
//! - `MarginFraction(_)`  → currently unsupported (skipped); needs a
//!   balance + leverage model the framework doesn't yet own.
//! - `Default`            → falls back to [`ExecutionConfig::default_size`]
//!   if set, otherwise the order is skipped.
//!
//! The [`PositionSizer`](rustrade_risk::PositionSizer) primitive in
//! `rustrade-risk` is intentionally *not* wired in here — it requires
//! contract-value information which is exchange-specific. Brains that want
//! it can use it directly when constructing their [`SizeHint`].

use std::sync::Arc;

use async_trait::async_trait;
use rustrade_core::{
    Brain, Decision, ExchangeClient, MarketDataBus, MarketDataEvent, Order, Position, Side,
    SignalType, SizeHint, Volume,
};
use rustrade_risk::{CircuitBreaker, SessionPnl};
use rustrade_supervisor::{RestartPolicy, TradingService};
use tokio::sync::Mutex;
use tokio_util::sync::CancellationToken;

/// Per-execution-service configuration.
#[derive(Debug, Clone, Default)]
pub struct ExecutionConfig {
    /// Fallback order size when the brain returns `SizeHint::Default`.
    /// If `None` and the brain returns `Default`, the event is skipped.
    pub default_size: Option<Volume>,
}

/// The service that wires a [`Brain`] to an [`ExchangeClient`] through a
/// [`MarketDataBus`].
///
/// One `ExecutionService` per brain. Multiple services share the same bus
/// (each gets its own broadcast subscription) so multi-brain bots fan out
/// market events to every brain.
pub struct ExecutionService {
    name: String,
    brain: Arc<dyn Brain>,
    exchange: Arc<dyn ExchangeClient>,
    bus: MarketDataBus,
    breaker: Arc<Mutex<CircuitBreaker>>,
    session_pnl: Arc<Mutex<SessionPnl>>,
    config: ExecutionConfig,
}

impl ExecutionService {
    pub fn new(
        brain: Arc<dyn Brain>,
        exchange: Arc<dyn ExchangeClient>,
        bus: MarketDataBus,
        breaker: Arc<Mutex<CircuitBreaker>>,
        session_pnl: Arc<Mutex<SessionPnl>>,
        config: ExecutionConfig,
    ) -> Self {
        let name = format!("execution[{}]", brain.name());
        Self {
            name,
            brain,
            exchange,
            bus,
            breaker,
            session_pnl,
            config,
        }
    }

    /// Resolve the brain's [`SizeHint`] into a concrete [`Volume`].
    fn resolve_size(&self, hint: SizeHint, last_price: f64) -> Option<Volume> {
        let v = match hint {
            SizeHint::Quantity(v) => v.value(),
            SizeHint::NotionalUsd(usd) if last_price > 0.0 => usd / last_price,
            SizeHint::NotionalUsd(_) => return None,
            SizeHint::Default => return self.config.default_size,
            SizeHint::MarginFraction(_) => {
                tracing::debug!(
                    brain = %self.brain.name(),
                    "MarginFraction sizing not yet supported by framework — skipping"
                );
                return None;
            }
        };

        if v > 0.0 {
            Some(Volume(v))
        } else {
            None
        }
    }

    /// Translate a [`Decision`] + current [`Position`] into an [`Order`].
    fn build_order(
        &self,
        symbol: &str,
        decision: &Decision,
        position: &Position,
        last_price: f64,
    ) -> Option<Order> {
        match decision.signal {
            SignalType::Hold => None,

            SignalType::Close => {
                if position.is_flat() {
                    return None;
                }
                let side = position.close_side()?;
                Some(Order::market(symbol, side, Volume(position.qty.abs())).with_reduce_only(true))
            }

            SignalType::Buy | SignalType::Sell => {
                let size = self.resolve_size(decision.size_hint, last_price)?;
                if size.value() <= 0.0 {
                    return None;
                }
                let side = if matches!(decision.signal, SignalType::Buy) {
                    Side::Buy
                } else {
                    Side::Sell
                };
                Some(Order::market(symbol, side, size))
            }
        }
    }

    async fn handle_event(&self, event: MarketDataEvent) -> anyhow::Result<()> {
        // Risk gates first — cheap, no I/O.
        {
            let breaker = self.breaker.lock().await;
            if breaker.is_tripped() {
                tracing::trace!(brain = %self.brain.name(), "circuit breaker tripped, skipping");
                return Ok(());
            }
        }
        {
            let pnl = self.session_pnl.lock().await;
            if pnl.is_session_halted() {
                tracing::trace!(brain = %self.brain.name(), "session PnL halted, skipping");
                return Ok(());
            }
        }

        let symbol = event.symbol().0.clone();

        let position = self
            .exchange
            .get_position(&symbol)
            .await
            .map_err(|e| anyhow::anyhow!("get_position failed: {e}"))?;

        let decision = self
            .brain
            .on_event(&event, &position)
            .await
            .map_err(|e| anyhow::anyhow!("brain.on_event failed: {e}"))?;

        if matches!(decision.signal, SignalType::Hold) {
            return Ok(());
        }

        let last_price = match &event {
            MarketDataEvent::Ticker { tick, .. } => tick.mid_price().value(),
            MarketDataEvent::Candle { candle, .. } => candle.close,
            MarketDataEvent::Trade { price, .. } => *price,
        };

        let Some(order) = self.build_order(&symbol, &decision, &position, last_price) else {
            return Ok(());
        };

        tracing::info!(
            brain = %self.brain.name(),
            symbol = %symbol,
            side = ?order.side,
            size = %order.size,
            confidence = decision.confidence,
            "placing order"
        );

        match self.exchange.place_order(&order).await {
            Ok(order_id) => {
                tracing::info!(brain = %self.brain.name(), order_id, "order placed");
                if let Ok(new_position) = self.exchange.get_position(&symbol).await {
                    let _ = self.brain.on_position_change(&symbol, &new_position).await;
                }
            }
            Err(e) => {
                tracing::error!(brain = %self.brain.name(), error = %e, "order placement failed");
            }
        }

        Ok(())
    }
}

#[async_trait]
impl TradingService for ExecutionService {
    fn name(&self) -> &str {
        &self.name
    }

    fn restart_policy(&self) -> RestartPolicy {
        RestartPolicy::OnFailure
    }

    async fn run(&self, cancel: CancellationToken) -> anyhow::Result<()> {
        let mut rx = self.bus.subscribe();

        tracing::info!(brain = %self.brain.name(), "execution service started");

        loop {
            tokio::select! {
                _ = cancel.cancelled() => {
                    tracing::info!(brain = %self.brain.name(), "execution service stopping");
                    return Ok(());
                }

                recv = rx.recv() => {
                    match recv {
                        Ok(event) => {
                            if let Err(e) = self.handle_event(event).await {
                                tracing::warn!(
                                    brain = %self.brain.name(),
                                    error = %e,
                                    "event handler failed; continuing"
                                );
                            }
                        }
                        Err(tokio::sync::broadcast::error::RecvError::Lagged(n)) => {
                            tracing::warn!(
                                brain = %self.brain.name(),
                                skipped = n,
                                "lagged behind market bus, skipping events"
                            );
                        }
                        Err(tokio::sync::broadcast::error::RecvError::Closed) => {
                            tracing::info!(brain = %self.brain.name(), "market bus closed");
                            return Ok(());
                        }
                    }
                }
            }
        }
    }
}
