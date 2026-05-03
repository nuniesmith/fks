//! Adapter: `exchange_apiws::KuCoinClient` → `rustrade_core::ExchangeClient`.
//!
//! This is the *only* file that knows about KuCoin specifics from the
//! framework's perspective. Adding a Binance bot would mean writing an
//! analogous `BinanceExchangeAdapter`; nothing else in this crate would
//! need to change.
//!
//! # Why a wrapper instead of `impl ExchangeClient for KuCoinClient`?
//!
//! Two reasons:
//! 1. `KuCoinClient` lives in the `exchange-apiws` crate, which is published
//!    independently. We can't add trait impls there without coupling those
//!    two crates' release cycles.
//! 2. The framework trait is intentionally narrower than `KuCoinClient`'s
//!    full surface (no stop orders, no funding history, no WS token mgmt
//!    here — those are all framework-internal concerns). A wrapper lets us
//!    expose just the slice the framework needs, while leaving the rest of
//!    the API available via `kucoin_client()` for service-specific code.

use std::sync::Arc;

use async_trait::async_trait;

use exchange_apiws::{KuCoinClient, KucoinEnv, OrderType, Side as KcSide};
use rustrade_core::{
    Error, ExchangeClient, Order, OrderKind, Position, Result, Side as FrameworkSide,
};

pub struct KucoinExchangeAdapter {
    client: Arc<KuCoinClient>,
    #[allow(dead_code)] // kept for future env-aware behavior
    env: KucoinEnv,
}

impl KucoinExchangeAdapter {
    pub fn new(client: Arc<KuCoinClient>, env: KucoinEnv) -> Self {
        Self { client, env }
    }

    /// Escape hatch: get the underlying KuCoin client for service-specific
    /// calls (e.g. placing exchange-side stop orders, fetching kline history).
    pub fn kucoin_client(&self) -> &Arc<KuCoinClient> {
        &self.client
    }
}

// ── Trait conversions (free at runtime) ──────────────────────────────────────

fn to_kc_side(s: FrameworkSide) -> KcSide {
    match s {
        FrameworkSide::Buy => KcSide::Buy,
        FrameworkSide::Sell => KcSide::Sell,
    }
}

fn to_kc_order_type(k: OrderKind) -> OrderType {
    match k {
        OrderKind::Market => OrderType::Market,
        OrderKind::Limit | OrderKind::PostOnly | OrderKind::Ioc | OrderKind::Fok => {
            OrderType::Limit
        }
    }
}

#[async_trait]
impl ExchangeClient for KucoinExchangeAdapter {
    fn name(&self) -> &str {
        "kucoin"
    }

    async fn place_order(&self, order: &Order) -> Result<String> {
        // Map framework order → kucoin order placement parameters.
        // Note: leverage isn't part of the framework Order type — that's
        // service-side configuration. The framework's execution layer
        // resolves leverage from BotConfig before calling place_order.
        // For this skeleton we use a default of 5x; the real impl would
        // accept it as a constructor parameter or read from BotConfig.
        let leverage = 5u32; // TODO: thread from BotConfig

        let resp = self
            .client
            .place_order(
                &order.symbol,
                to_kc_side(order.side),
                order.size.0 as u32, // contracts
                leverage,
                to_kc_order_type(order.kind),
                order.limit_price.map(|p| p.0),
                None, // time-in-force — default GTC
                order.reduce_only,
                None, // STP
            )
            .await
            .map_err(|e| Error::exchange(e.to_string()))?;
        Ok(resp.order_id)
    }

    async fn cancel_all(&self, symbol: &str) -> Result<usize> {
        let _resp = self
            .client
            .cancel_all_orders(symbol)
            .await
            .map_err(|e| Error::exchange(e.to_string()))?;
        // KuCoin returns the cancelled order IDs in the response; the
        // framework just needs a count.  Real impl would parse `_resp`.
        Ok(0)
    }

    async fn close_position(&self, symbol: &str, position: &Position) -> Result<String> {
        let leverage = 5u32; // TODO: thread from BotConfig
        let resp = self
            .client
            .close_position(symbol, position.qty as i32, leverage)
            .await
            .map_err(|e| Error::exchange(e.to_string()))?;
        Ok(resp.order_id)
    }

    async fn get_position(&self, symbol: &str) -> Result<Position> {
        let info = self
            .client
            .get_position(symbol)
            .await
            .map_err(|e| Error::exchange(e.to_string()))?;
        Ok(Position {
            qty: f64::from(info.current_qty),
            entry_price: info.avg_entry_price,
            unrealised_pnl: info.unrealised_pnl.unwrap_or(0.0),
        })
    }

    async fn get_balance(&self, currency: &str) -> Result<f64> {
        self.client
            .get_balance(currency)
            .await
            .map_err(|e| Error::exchange(e.to_string()))
    }
}
