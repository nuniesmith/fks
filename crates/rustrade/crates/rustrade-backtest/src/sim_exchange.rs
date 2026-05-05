//! [`SimExchange`] — an in-memory [`ExchangeClient`] for backtests.
//!
//! Orders are accepted instantly and filled at the *next bar's open* price
//! adjusted by [`SimExchangeConfig::slippage_bps`]. Commission is deducted as
//! a fraction of notional. The exchange tracks position, balance, and a fill
//! log; the backtest engine drains the fill log at the end of each bar to
//! compute equity and trade outcomes.
//!
//! # Single-symbol assumption
//!
//! The MVP supports one open position at a time per backtest run. Multi-symbol
//! portfolio backtests can be built by running multiple [`SimExchange`]
//! instances in parallel — each one is just an `Arc<dyn ExchangeClient>`
//! the engine writes to.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};

use async_trait::async_trait;
use parking_lot::Mutex;
use rustrade_core::{Error, ExchangeClient, Fill, Order, OrderKind, Position, Result, Side};
use thiserror::Error;

#[derive(Debug, Clone)]
pub struct SimExchangeConfig {
    /// Starting balance in the quote currency (e.g. USDT).
    pub initial_balance: f64,

    /// Slippage applied to fill prices, in basis points. Buys pay
    /// `next_open * (1 + slippage_bps/1e4)`; sells receive
    /// `next_open * (1 - slippage_bps/1e4)`.
    pub slippage_bps: f64,

    /// Commission per trade, in basis points of notional.
    pub commission_bps: f64,

    /// Contract multiplier for symbols that aren't 1.0 (e.g. KuCoin futures).
    /// Looked up via [`SimExchangeConfig::with_contract_value`]; falls back
    /// to 1.0 for any symbol not in the table.
    pub contract_values: HashMap<String, f64>,

    /// Quote currency for `get_balance`. Anything else returns 0.0.
    pub quote_currency: String,
}

impl Default for SimExchangeConfig {
    fn default() -> Self {
        Self {
            initial_balance: 10_000.0,
            slippage_bps: 0.0,
            commission_bps: 0.0,
            contract_values: HashMap::new(),
            quote_currency: "USDT".to_string(),
        }
    }
}

impl SimExchangeConfig {
    pub fn with_initial_balance(mut self, b: f64) -> Self {
        self.initial_balance = b;
        self
    }
    pub fn with_slippage_bps(mut self, bps: f64) -> Self {
        self.slippage_bps = bps;
        self
    }
    pub fn with_commission_bps(mut self, bps: f64) -> Self {
        self.commission_bps = bps;
        self
    }
    pub fn with_contract_value(mut self, symbol: impl Into<String>, value: f64) -> Self {
        self.contract_values.insert(symbol.into(), value);
        self
    }
    pub fn with_quote_currency(mut self, c: impl Into<String>) -> Self {
        self.quote_currency = c.into();
        self
    }
}

#[derive(Debug, Error)]
pub enum SimExchangeError {
    #[error("no current price set for {0} — engine must call set_last_price before processing orders")]
    NoCurrentPrice(String),
}

/// A pending order waiting for the next bar's open to fill.
#[derive(Debug, Clone)]
struct PendingOrder {
    symbol: String,
    side: Side,
    size: f64,
    reduce_only: bool,
    client_id: Option<String>,
    order_id: String,
}

/// Internal mutable state of the simulated exchange.
#[derive(Debug, Default)]
struct State {
    /// Cash balance (quote currency).
    balance: f64,
    /// Per-symbol position (qty in contracts; entry price in quote).
    positions: HashMap<String, Position>,
    /// Most recent observed price per symbol (the engine updates this from
    /// the close of each candle; it's used as a fallback when no pending
    /// order applies).
    last_prices: HashMap<String, f64>,
    /// Orders accepted on bar `t` that fill at the open of bar `t+1`.
    pending: Vec<PendingOrder>,
    /// Drained by the engine after each fill to update metrics.
    pub fills_pending_publish: Vec<Fill>,
    /// Total realised PnL (net of fees) accumulated over the run.
    realised_pnl: f64,
    /// Order id counter for `next_order_id`.
    next_id: u64,
}

/// In-memory exchange used by [`crate::BacktestEngine`].
///
/// Cheap to clone (just `Arc<Mutex<State>>` + config). Implements
/// [`ExchangeClient`] so it slots into any code that already takes
/// `Arc<dyn ExchangeClient>`.
#[derive(Clone)]
pub struct SimExchange {
    config: SimExchangeConfig,
    state: std::sync::Arc<Mutex<State>>,
    /// Atomic counter used outside the lock for cheap order-id generation.
    seq: std::sync::Arc<AtomicU64>,
}

impl SimExchange {
    pub fn new(config: SimExchangeConfig) -> Self {
        let mut s = State::default();
        s.balance = config.initial_balance;
        Self {
            config,
            state: std::sync::Arc::new(Mutex::new(s)),
            seq: std::sync::Arc::new(AtomicU64::new(1)),
        }
    }

    /// Engine hook: record the most recently observed price (typically the
    /// close of the candle just dispatched to the brain). The price is used
    /// for mark-to-market on `get_position().unrealised_pnl` queries.
    pub fn set_last_price(&self, symbol: &str, price: f64) {
        self.state.lock().last_prices.insert(symbol.to_string(), price);
    }

    /// Engine hook: settle all pending orders against the given fill price
    /// (typically the next bar's open). Returns the fills produced so the
    /// engine can update the trade log.
    pub fn settle_pending_at(&self, symbol: &str, fill_price: f64) -> Vec<Fill> {
        let mut s = self.state.lock();
        let mut fills = Vec::new();
        let contract_value = self.contract_value_locked(symbol);

        // Take pending orders for this symbol; leave others intact.
        let mut remaining = Vec::with_capacity(s.pending.len());
        let pending = std::mem::take(&mut s.pending);
        for order in pending {
            if order.symbol != symbol {
                remaining.push(order);
                continue;
            }

            let adjusted_price = match order.side {
                Side::Buy => fill_price * (1.0 + self.config.slippage_bps / 10_000.0),
                Side::Sell => fill_price * (1.0 - self.config.slippage_bps / 10_000.0),
            };
            let notional = adjusted_price * order.size * contract_value;
            let fee = notional.abs() * (self.config.commission_bps / 10_000.0);

            // Compute new position state from a snapshot of the current position
            // BEFORE taking any borrow on `s` for balance/PnL updates.
            let cur_pos = s
                .positions
                .get(&order.symbol)
                .copied()
                .unwrap_or(Position::FLAT);

            let signed_delta = match order.side {
                Side::Buy => order.size,
                Side::Sell => -order.size,
            };
            let new_qty = cur_pos.qty + signed_delta;

            let realised_delta = if cur_pos.qty.signum() != 0.0
                && cur_pos.qty.signum() != signed_delta.signum()
            {
                let closed = signed_delta.abs().min(cur_pos.qty.abs());
                let entry = cur_pos.entry_price.unwrap_or(adjusted_price);
                let direction = cur_pos.qty.signum();
                direction * (adjusted_price - entry) * closed * contract_value
            } else {
                0.0
            };

            let new_entry = if new_qty == 0.0 {
                None
            } else if cur_pos.qty == 0.0 {
                Some(adjusted_price)
            } else if cur_pos.qty.signum() == new_qty.signum() {
                let total_notional = cur_pos.entry_price.unwrap_or(adjusted_price)
                    * cur_pos.qty.abs()
                    + adjusted_price * order.size;
                Some(total_notional / new_qty.abs())
            } else {
                // Flipped through zero — the remaining bit is a fresh open at
                // the fill price.
                Some(adjusted_price)
            };

            // Now write everything back. No simultaneous mutable borrows because
            // each field is touched in its own statement.
            s.realised_pnl += realised_delta - fee;
            s.balance += realised_delta - fee;

            let pos = s
                .positions
                .entry(order.symbol.clone())
                .or_insert(Position::FLAT);
            pos.qty = new_qty;
            pos.entry_price = new_entry;
            if new_qty == 0.0 {
                pos.unrealised_pnl = 0.0;
            }

            let fill = Fill {
                symbol: order.symbol.clone(),
                order_id: order.order_id.clone(),
                client_id: order.client_id.clone(),
                side: order.side,
                price: rustrade_core::Price(adjusted_price),
                size: rustrade_core::Volume(order.size),
                fee,
                fee_currency: self.config.quote_currency.clone(),
                timestamp: chrono::Utc::now(),
            };

            s.fills_pending_publish.push(fill.clone());
            fills.push(fill);
        }

        s.pending = remaining;
        fills
    }

    /// Realised PnL net of fees accumulated over the run.
    pub fn realised_pnl(&self) -> f64 {
        self.state.lock().realised_pnl
    }

    /// Snapshot of current cash balance.
    pub fn balance(&self) -> f64 {
        self.state.lock().balance
    }

    /// Drain the pending-fills queue. The engine calls this at end-of-run
    /// to feed the trade-log reconstructor in [`crate::metrics`].
    pub fn drain_fills(&self) -> Vec<Fill> {
        std::mem::take(&mut self.state.lock().fills_pending_publish)
    }

    /// Compute a mark-to-market equity number using the last set price for
    /// every open position. Used by the engine to record the equity curve.
    pub fn equity(&self) -> f64 {
        let s = self.state.lock();
        let mut equity = s.balance;
        for (sym, pos) in &s.positions {
            if pos.is_flat() {
                continue;
            }
            let cv = self
                .config
                .contract_values
                .get(sym)
                .copied()
                .unwrap_or(1.0);
            let last = s.last_prices.get(sym).copied().unwrap_or(0.0);
            let entry = pos.entry_price.unwrap_or(last);
            equity += (last - entry) * pos.qty * cv;
        }
        equity
    }

    fn contract_value_locked(&self, symbol: &str) -> f64 {
        self.config
            .contract_values
            .get(symbol)
            .copied()
            .unwrap_or(1.0)
    }

    fn next_order_id(&self) -> String {
        let n = self.seq.fetch_add(1, Ordering::Relaxed);
        format!("sim-{n}")
    }
}

#[async_trait]
impl ExchangeClient for SimExchange {
    fn name(&self) -> &str {
        "sim"
    }

    async fn place_order(&self, order: &Order) -> Result<String> {
        // The framework only routes Market orders through ExecutionService for
        // now; reject anything else cleanly so a future limit-order path doesn't
        // silently fill at the wrong price.
        if !matches!(order.kind, OrderKind::Market) {
            return Err(Error::exchange(format!(
                "SimExchange only supports market orders, got {:?}",
                order.kind
            )));
        }
        let order_id = self.next_order_id();
        let mut s = self.state.lock();
        s.pending.push(PendingOrder {
            symbol: order.symbol.clone(),
            side: order.side,
            size: order.size.value(),
            reduce_only: order.reduce_only,
            client_id: order.client_id.clone(),
            order_id: order_id.clone(),
        });
        Ok(order_id)
    }

    async fn cancel_all(&self, symbol: &str) -> Result<usize> {
        let mut s = self.state.lock();
        let before = s.pending.len();
        s.pending.retain(|o| o.symbol != symbol);
        Ok(before - s.pending.len())
    }

    async fn close_position(&self, symbol: &str, position: &Position) -> Result<String> {
        if position.is_flat() {
            return Err(Error::exchange("close_position: position is flat"));
        }
        let side = position.close_side().unwrap();
        let order = Order::market(symbol, side, rustrade_core::Volume(position.qty.abs()))
            .with_reduce_only(true);
        self.place_order(&order).await
    }

    async fn get_position(&self, symbol: &str) -> Result<Position> {
        let s = self.state.lock();
        let mut pos = s.positions.get(symbol).copied().unwrap_or(Position::FLAT);
        if let (Some(entry), Some(last)) = (pos.entry_price, s.last_prices.get(symbol).copied()) {
            let cv = self.contract_value_locked(symbol);
            pos.unrealised_pnl = (last - entry) * pos.qty * cv;
        }
        Ok(pos)
    }

    async fn get_balance(&self, currency: &str) -> Result<f64> {
        if currency == self.config.quote_currency {
            Ok(self.state.lock().balance)
        } else {
            Ok(0.0)
        }
    }

    async fn contract_value(&self, symbol: &str) -> Result<f64> {
        Ok(self.contract_value_locked(symbol))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn sim_fills_buy_at_next_open_with_slippage() {
        let sim = SimExchange::new(
            SimExchangeConfig::default()
                .with_slippage_bps(10.0)
                .with_initial_balance(1_000.0),
        );
        sim.set_last_price("BTCUSDT", 100.0);

        let order = Order::market("BTCUSDT", Side::Buy, rustrade_core::Volume(2.0));
        let order_id = sim.place_order(&order).await.unwrap();
        assert!(order_id.starts_with("sim-"));

        // Settle at next-bar open of 110.
        let fills = sim.settle_pending_at("BTCUSDT", 110.0);
        assert_eq!(fills.len(), 1);
        let f = &fills[0];
        // 110 * (1 + 0.001) = 110.11
        assert!((f.price.value() - 110.11).abs() < 1e-9);
        assert_eq!(f.size.value(), 2.0);

        let pos = sim.get_position("BTCUSDT").await.unwrap();
        assert_eq!(pos.qty, 2.0);
        // 110 * (1 + 0.001) = 110.11 — compare with epsilon for float precision.
        assert!((pos.entry_price.unwrap() - 110.11).abs() < 1e-6);
    }

    #[tokio::test]
    async fn sim_realises_pnl_on_close() {
        let sim = SimExchange::new(
            SimExchangeConfig::default()
                .with_slippage_bps(0.0)
                .with_commission_bps(0.0)
                .with_initial_balance(0.0),
        );
        sim.set_last_price("BTCUSDT", 100.0);

        // Buy 1 contract at 100, then sell at 110 → +10.
        sim.place_order(&Order::market("BTCUSDT", Side::Buy, rustrade_core::Volume(1.0)))
            .await
            .unwrap();
        sim.settle_pending_at("BTCUSDT", 100.0);

        sim.place_order(&Order::market("BTCUSDT", Side::Sell, rustrade_core::Volume(1.0)))
            .await
            .unwrap();
        sim.settle_pending_at("BTCUSDT", 110.0);

        assert!((sim.realised_pnl() - 10.0).abs() < 1e-9);
        assert_eq!(sim.balance(), 10.0);

        let pos = sim.get_position("BTCUSDT").await.unwrap();
        assert!(pos.is_flat());
    }

    #[tokio::test]
    async fn sim_rejects_limit_orders() {
        let sim = SimExchange::new(SimExchangeConfig::default());
        let order = Order::limit(
            "BTCUSDT",
            Side::Buy,
            rustrade_core::Volume(1.0),
            rustrade_core::Price(100.0),
        );
        assert!(sim.place_order(&order).await.is_err());
    }
}
