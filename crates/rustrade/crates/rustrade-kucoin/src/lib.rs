//! # rustrade-kucoin
//!
//! [`KucoinExchangeAdapter`] bridges
//! [`exchange_apiws::KuCoinClient`](exchange_apiws::KuCoinClient) into the
//! [`rustrade_core::ExchangeClient`] trait so any rustrade-based bot can
//! trade on KuCoin Futures without depending on KuCoin specifics.
//!
//! # Why a wrapper instead of `impl ExchangeClient for KuCoinClient`?
//!
//! Two reasons:
//!
//! 1. `KuCoinClient` lives in the `exchange-apiws` crate, which is published
//!    independently. Adding trait impls there would couple the two crates'
//!    release cycles.
//! 2. The framework trait is intentionally narrower than `KuCoinClient`'s
//!    full surface (no stop orders, no funding history, no WS token mgmt
//!    here — those are framework-internal or service-specific concerns).
//!    A wrapper exposes just the slice the framework needs while leaving
//!    the rest available via [`KucoinExchangeAdapter::client`].
//!
//! # Quick start
//!
//! ```ignore
//! use std::sync::Arc;
//! use exchange_apiws::{Credentials, KuCoin, KucoinEnv};
//! use rustrade::ExchangeClient;
//! use rustrade_kucoin::KucoinExchangeAdapter;
//!
//! let creds  = Credentials::new(api_key, api_secret, passphrase);
//! let kucoin = KuCoin::new(creds, KucoinEnv::LiveFutures).rest_client()?;
//! let adapter: Arc<dyn ExchangeClient> =
//!     Arc::new(KucoinExchangeAdapter::new(Arc::new(kucoin), 5));
//! ```

#![warn(missing_docs)]

use std::sync::Arc;

use async_trait::async_trait;

use exchange_apiws::{KuCoinClient, OrderType, Side as KcSide};
use rustrade_core::{
    Error, ExchangeClient, Order, OrderKind, Position, Result, Side as FrameworkSide,
};

/// Adapter wrapping an `exchange-apiws` [`KuCoinClient`] so it implements
/// [`rustrade_core::ExchangeClient`].
///
/// Leverage is fixed per-adapter at construction time. This is the recommended
/// design choice for the v0 framework trait — per-account leverage covers
/// 95% of strategies; per-trade leverage adjustment requires a wider trait
/// surface that's not justified yet. Build a second adapter with a different
/// leverage if you genuinely need both at once.
pub struct KucoinExchangeAdapter {
    client: Arc<KuCoinClient>,
    leverage: u32,
}

impl KucoinExchangeAdapter {
    /// Build an adapter with the given leverage. The leverage is sent on
    /// every `place_order` and `close_position` call.
    pub fn new(client: Arc<KuCoinClient>, leverage: u32) -> Self {
        Self { client, leverage }
    }

    /// Builder helper: change the leverage post-construction.
    pub fn with_leverage(mut self, leverage: u32) -> Self {
        self.leverage = leverage;
        self
    }

    /// Escape hatch: get the underlying KuCoin client for service-specific
    /// calls outside the framework trait surface (stop orders, kline history,
    /// account overview, …).
    pub fn client(&self) -> &Arc<KuCoinClient> {
        &self.client
    }

    /// Configured leverage.
    pub fn leverage(&self) -> u32 {
        self.leverage
    }
}

// ── Type conversions (free at runtime) ────────────────────────────────────────

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

/// Contract multiplier (base-asset units per contract) for major KuCoin
/// Futures symbols.
///
/// KuCoin Futures uses small fractional multipliers — `XBTUSDTM` represents
/// 0.001 BTC per contract, `ETHUSDTM` 0.01 ETH per contract, etc. The
/// framework uses this to translate `SizeHint::NotionalUsd` into a contract
/// count via `contracts = notional / (price * contract_value)`.
///
/// Returns `1.0` for unknown symbols; the adapter logs a warning the first
/// time an unknown symbol is queried so it surfaces in dev. Add a missing
/// symbol by extending this match — there's no runtime registration because
/// these multipliers don't change once a contract is listed.
pub fn contract_value_for(symbol: &str) -> f64 {
    match symbol {
        // BTC-quoted USDT-margined contracts: 0.001 BTC per contract.
        "XBTUSDTM" => 0.001,
        // ETH: 0.01 ETH per contract.
        "ETHUSDTM" => 0.01,
        // SOL: 1.0 SOL per contract.
        "SOLUSDTM" => 1.0,
        // DOGE: 1000 DOGE per contract.
        "DOGEUSDTM" => 1000.0,
        // XRP: 10 XRP per contract.
        "XRPUSDTM" => 10.0,
        // ADA: 10 ADA per contract.
        "ADAUSDTM" => 10.0,
        // LINK: 1 LINK per contract.
        "LINKUSDTM" => 1.0,
        // AVAX: 1 AVAX per contract.
        "AVAXUSDTM" => 1.0,
        _ => {
            tracing::warn!(
                symbol,
                "unknown contract — using contract_value=1.0; \
                 add the multiplier to rustrade_kucoin::contract_value_for"
            );
            1.0
        }
    }
}

#[async_trait]
impl ExchangeClient for KucoinExchangeAdapter {
    fn name(&self) -> &str {
        "kucoin"
    }

    async fn place_order(&self, order: &Order) -> Result<String> {
        // KuCoin order size is u32 contracts. Fractional contracts can't be
        // placed; we floor here. Brains targeting a notional should work in
        // contract counts upstream.
        let size = order.size.0 as u32;
        if size == 0 {
            return Err(Error::exchange("order size rounded to 0 contracts"));
        }

        let resp = self
            .client
            .place_order(
                &order.symbol,
                to_kc_side(order.side),
                size,
                self.leverage,
                to_kc_order_type(order.kind),
                order.limit_price.map(|p| p.value()),
                None, // time-in-force — default GTC
                order.reduce_only,
                None, // STP
            )
            .await
            .map_err(|e| Error::exchange(e.to_string()))?;
        Ok(resp.order_id)
    }

    async fn cancel_all(&self, symbol: &str) -> Result<usize> {
        // KuCoin returns the cancelled order IDs in `cancelledOrderIds`; we
        // parse the array length when present and fall back to 0.
        let resp = self
            .client
            .cancel_all_orders(symbol)
            .await
            .map_err(|e| Error::exchange(e.to_string()))?;
        let count = resp
            .get("cancelledOrderIds")
            .and_then(|v| v.as_array())
            .map(|arr| arr.len())
            .unwrap_or(0);
        Ok(count)
    }

    async fn close_position(&self, symbol: &str, position: &Position) -> Result<String> {
        if position.is_flat() {
            return Err(Error::exchange("close_position: position is flat"));
        }
        let qty = position.qty as i32;
        let resp = self
            .client
            .close_position(symbol, qty, self.leverage)
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

    async fn contract_value(&self, symbol: &str) -> Result<f64> {
        Ok(contract_value_for(symbol))
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_known_contract_values() {
        assert_eq!(contract_value_for("XBTUSDTM"), 0.001);
        assert_eq!(contract_value_for("ETHUSDTM"), 0.01);
        assert_eq!(contract_value_for("SOLUSDTM"), 1.0);
        assert_eq!(contract_value_for("DOGEUSDTM"), 1000.0);
    }

    #[test]
    fn test_unknown_contract_value_falls_back_to_one() {
        assert_eq!(contract_value_for("UNKNOWN-SYMBOL"), 1.0);
    }

    #[test]
    fn test_side_conversion() {
        assert!(matches!(to_kc_side(FrameworkSide::Buy), KcSide::Buy));
        assert!(matches!(to_kc_side(FrameworkSide::Sell), KcSide::Sell));
    }

    #[test]
    fn test_order_type_conversion() {
        assert!(matches!(to_kc_order_type(OrderKind::Market), OrderType::Market));
        assert!(matches!(to_kc_order_type(OrderKind::Limit), OrderType::Limit));
        assert!(matches!(to_kc_order_type(OrderKind::PostOnly), OrderType::Limit));
        assert!(matches!(to_kc_order_type(OrderKind::Ioc), OrderType::Limit));
        assert!(matches!(to_kc_order_type(OrderKind::Fok), OrderType::Limit));
    }
}
