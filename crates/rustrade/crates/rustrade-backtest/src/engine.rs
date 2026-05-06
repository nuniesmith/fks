//! [`BacktestEngine`] — replay loop tying a [`Brain`] to a [`SimExchange`]
//! over a chronological [`Vec<Candle>`].
//!
//! At each bar the engine:
//!
//!   1. Settles any pending orders at *this* bar's open (so an order placed
//!      on bar `t-1` fills at the open of `t` — no lookahead).
//!   2. Updates the sim exchange's last-price to this bar's close.
//!   3. Builds a [`MarketDataEvent::Candle`] from the bar.
//!   4. Calls `brain.on_event()`.
//!   5. Translates the returned [`Decision`] into an [`Order`] (mirroring
//!      [`rustrade::ExecutionService`]'s logic for `Hold`/`Buy`/`Sell`/`Close`
//!      and `SizeHint::Quantity` / `NotionalUsd` / `Default`).
//!   6. Records the equity point.
//!
//! At the end of the run the equity curve plus the [`SimExchange`]'s fill
//! log are run through [`crate::metrics`] to produce a [`BacktestRun`].

use std::sync::Arc;

use rustrade_core::{
    Brain, Candle, Decision, ExchangeClient, Exchange as ExchangeId, MarketDataEvent, Order,
    Position, Side, SignalType, SizeHint, Symbol, Volume,
};
use thiserror::Error;

use crate::metrics::{
    BacktestMetrics, EquityPoint, MetricsConfig, TradeRecord, build_trade_log,
};
use crate::sim_exchange::SimExchange;

/// Configuration for a [`BacktestEngine`].
#[allow(missing_docs)] // each field has its own /// doc
#[derive(Debug, Clone)]
pub struct BacktestConfig {
    /// Exchange identifier stamped onto each `MarketDataEvent` (purely
    /// cosmetic — useful in logs / brain metadata).
    pub exchange_id: String,

    /// Fallback order size when the brain returns `SizeHint::Default`.
    /// `None` means: skip the bar — same behaviour as the live framework.
    pub default_size: Option<Volume>,

    /// Annualisation hint for Sharpe / Sortino. See
    /// [`MetricsConfig::periods_per_year`].
    pub metrics: MetricsConfig,
}

impl Default for BacktestConfig {
    fn default() -> Self {
        Self {
            exchange_id: "sim".to_string(),
            default_size: None,
            metrics: MetricsConfig::default(),
        }
    }
}

/// Errors produced by [`BacktestEngine::run`].
#[allow(missing_docs)] // variants are self-evident from the message format
#[derive(Debug, Error)]
pub enum BacktestError {
    #[error("brain returned an error: {0}")]
    Brain(String),

    #[error("exchange error: {0}")]
    Exchange(String),
}

/// The output of a single backtest run.
#[allow(missing_docs)] // self-evident: aggregated metrics, the equity curve, and the trade log
#[derive(Debug, Clone)]
pub struct BacktestRun {
    pub metrics: BacktestMetrics,
    pub equity_curve: Vec<EquityPoint>,
    pub trades: Vec<TradeRecord>,
}

/// A configured replay engine. Build one per run; calling [`Self::run`]
/// consumes the candle stream end-to-end.
pub struct BacktestEngine {
    config: BacktestConfig,
    sim: SimExchange,
    brain: Arc<dyn Brain>,
}

impl BacktestEngine {
    /// Build an engine. The same [`SimExchange`] is borrowed by the
    /// engine; if you need to inspect it post-run, hold a clone.
    pub fn new(config: BacktestConfig, sim: SimExchange, brain: Arc<dyn Brain>) -> Self {
        Self { config, sim, brain }
    }

    /// Borrow the underlying sim exchange (e.g. to inspect realised PnL or
    /// inject orders directly).
    pub fn sim(&self) -> &SimExchange {
        &self.sim
    }

    /// Replay candles through the brain. Candles must be sorted ascending
    /// by `time` — the engine doesn't sort them itself because in production
    /// they normally already are, and silent reordering would mask bugs.
    /// Replay `candles` through the brain and return aggregated metrics +
    /// the equity curve + the reconstructed trade log.
    pub async fn run(
        &self,
        symbol: &str,
        candles: Vec<Candle>,
    ) -> std::result::Result<BacktestRun, BacktestError> {
        let mut equity_curve = Vec::with_capacity(candles.len());

        let exchange_id = ExchangeId::from(self.config.exchange_id.as_str());
        let symbol_id = Symbol::from(symbol);

        for candle in candles.into_iter() {
            // 1. Settle any pending orders at this bar's open. An order placed
            //    on the previous bar fills here — no lookahead.
            let _fills = self.sim.settle_pending_at(symbol, candle.open);

            // 2. Update the sim's last-price to this bar's close so the brain
            //    sees a fresh `Position::unrealised_pnl` if it asks for one.
            self.sim.set_last_price(symbol, candle.close);

            // 3. Dispatch the candle to the brain.
            let event = MarketDataEvent::Candle {
                exchange: exchange_id.clone(),
                symbol: symbol_id.clone(),
                candle,
            };

            let position = self
                .sim
                .get_position(symbol)
                .await
                .map_err(|e| BacktestError::Exchange(e.to_string()))?;

            let decision = self
                .brain
                .on_event(&event, &position)
                .await
                .map_err(|e| BacktestError::Brain(e.to_string()))?;

            // 4. Translate the decision into an order.
            if let Some(order) = self
                .build_order(symbol, &decision, &position, candle.close)
                .await
            {
                self.sim
                    .place_order(&order)
                    .await
                    .map_err(|e| BacktestError::Exchange(e.to_string()))?;
            }

            // 5. Record equity AFTER the brain has reacted to this bar.
            equity_curve.push(EquityPoint {
                timestamp_ms: candle.time,
                equity: self.sim.equity(),
            });
        }

        // Drain the fill log for trade reconstruction.
        let fills = self.sim.drain_fills();
        let trades = build_trade_log(&fills);
        let metrics = BacktestMetrics::compute(&equity_curve, &trades, self.config.metrics);

        Ok(BacktestRun {
            metrics,
            equity_curve,
            trades,
        })
    }

    async fn build_order(
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
                let size = self.resolve_size(decision.size_hint, last_price, symbol).await?;
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

    async fn resolve_size(
        &self,
        hint: SizeHint,
        last_price: f64,
        symbol: &str,
    ) -> Option<Volume> {
        let v = match hint {
            SizeHint::Quantity(v) => v.value(),
            SizeHint::NotionalUsd(usd) if last_price > 0.0 => {
                let cv = self
                    .sim
                    .contract_value(symbol)
                    .await
                    .unwrap_or(1.0)
                    .max(f64::MIN_POSITIVE);
                usd / (last_price * cv)
            }
            SizeHint::NotionalUsd(_) => return None,
            SizeHint::Default => return self.config.default_size,
            SizeHint::MarginFraction(_) => {
                tracing::debug!(
                    brain = %self.brain.name(),
                    "MarginFraction sizing not supported in backtest engine — skipping"
                );
                return None;
            }
        };
        if v > 0.0 { Some(Volume(v)) } else { None }
    }
}
