//! [`KrakenSpotAdapter`] — a [`rustrade::ExchangeClient`] over Kraken **spot**,
//! via [`exchange-apiws`]'s signed `KrakenPrivateClient`.
//!
//! Spot is a different shape from KuCoin Futures, and the adapter models it
//! honestly:
//!
//! - **Long-only, no leverage.** You hold the base asset; there are no
//!   contracts and no shorts. `contract_value` is `1.0` and the instrument is
//!   [`AssetClass::CryptoSpot`], so the framework's per-asset-class risk picks
//!   the spot rules.
//! - **A "position" is your balance.** [`get_position`](ExchangeClient::get_position)
//!   returns the base-asset balance as a (non-negative) qty; closing it is a
//!   market **sell** of that balance.
//! - **Orders are in base-asset units** (e.g. `0.5` BTC), not contracts.
//!   Market and limit only — Kraken's stop / IOC / FOK / post-only aren't on
//!   this surface, so the adapter rejects them and advertises them as
//!   unsupported.
//!
//! # Asset codes
//!
//! Kraken keys balances by its own asset codes (`XXBT`, `XETH`, `ZUSD`, `SOL`,
//! …), which aren't derivable from a pair string. So `get_position` needs a
//! `symbol → base-asset-code` map, supplied at construction — e.g.
//! `("XBTUSD", "XXBT")`. The trading `pair` is the symbol itself (use Kraken's
//! pair names, e.g. `XBTUSD`).
//!
//! # Example
//!
//! ```no_run
//! use rustrade_exchange_apiws::KrakenSpotAdapter;
//! # async fn demo() -> rustrade::Result<()> {
//! // KRAKEN_API_KEY / KRAKEN_API_SECRET from the env; map each pair to its
//! // Kraken base-asset code for balance/position lookups.
//! let exchange = KrakenSpotAdapter::from_env(&[("XBTUSD", "XXBT"), ("ETHUSD", "XETH")])?;
//! # let _ = exchange;
//! # Ok(())
//! # }
//! ```

use std::collections::HashMap;

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use rustrade::{
    AssetClass, Capability, ExchangeClient, InstrumentSpec, OpenOrder, Order, OrderKind,
    OrderStatus, Position, Price, Result, Side, Symbol, Volume,
};

use exchange_apiws::{KrakenCredentials, KrakenPrivateClient};

use crate::ex;

// ── Pure mapping helpers (unit-tested, no network) ───────────────────────────

/// framework [`Side`] → Kraken `"buy"` / `"sell"`.
fn kraken_side(side: Side) -> &'static str {
    match side {
        Side::Buy => "buy",
        Side::Sell => "sell",
    }
}

/// framework [`OrderKind`] → Kraken `ordertype`. Spot here supports market and
/// limit only; stop / IOC / FOK / post-only aren't on this REST surface.
fn kraken_order_type(kind: OrderKind) -> Result<&'static str> {
    match kind {
        OrderKind::Market => Ok("market"),
        OrderKind::Limit => Ok("limit"),
        OrderKind::Ioc | OrderKind::Fok | OrderKind::PostOnly => Err(rustrade::Error::exchange(
            format!("Kraken spot adapter supports market/limit only, not {kind:?}"),
        )),
    }
}

/// Format an amount as a plain decimal string (no scientific notation, trailing
/// zeros trimmed) — Kraken accepts decimal `volume`/`price` strings.
fn fmt_amount(v: f64) -> String {
    let s = format!("{v:.8}");
    // Trim trailing zeros, then a trailing dot.
    let s = s.trim_end_matches('0');
    s.trim_end_matches('.').to_string()
}

/// Parse a Kraken balance map entry into an `f64` (missing / unparseable ⇒ 0).
fn balance_of(balances: &HashMap<String, String>, asset: &str) -> f64 {
    balances
        .get(asset)
        .and_then(|s| s.parse::<f64>().ok())
        .unwrap_or(0.0)
}

/// Kraken order `status` string → framework [`OrderStatus`].
fn order_status(status: &str, filled: f64, size: f64) -> OrderStatus {
    match status {
        "pending" => OrderStatus::Pending,
        "open" => {
            if filled > 0.0 {
                OrderStatus::PartiallyFilled
            } else {
                OrderStatus::Open
            }
        }
        "closed" => OrderStatus::Filled,
        "canceled" | "expired" => {
            // A cancel after a partial fill still leaves some filled.
            if filled >= size && size > 0.0 {
                OrderStatus::Filled
            } else {
                OrderStatus::Cancelled
            }
        }
        _ => OrderStatus::Open,
    }
}

/// Kraken `opentm` (fractional Unix **seconds**) → `DateTime<Utc>`.
fn secs_to_dt(secs: f64) -> Option<DateTime<Utc>> {
    let whole = secs.trunc() as i64;
    let nanos = ((secs.fract()) * 1e9) as u32;
    DateTime::<Utc>::from_timestamp(whole, nanos)
}

// ── Adapter ──────────────────────────────────────────────────────────────────

/// A [`rustrade::ExchangeClient`] for Kraken **spot**. See this module's documentation.
#[derive(Clone)]
pub struct KrakenSpotAdapter {
    client: KrakenPrivateClient,
    /// symbol → Kraken base-asset code (for balance → position lookups).
    base_assets: HashMap<String, String>,
}

impl KrakenSpotAdapter {
    /// Wrap an existing [`KrakenPrivateClient`]. Register base-asset codes with
    /// [`with_base_asset`](Self::with_base_asset) before relying on
    /// [`get_position`](ExchangeClient::get_position).
    #[must_use]
    pub fn new(client: KrakenPrivateClient) -> Self {
        Self {
            client,
            base_assets: HashMap::new(),
        }
    }

    /// Register the Kraken base-asset code for a `symbol` (builder style) — e.g.
    /// `("XBTUSD", "XXBT")`. Needed so positions read the right balance.
    #[must_use]
    pub fn with_base_asset(
        mut self,
        symbol: impl Into<String>,
        asset_code: impl Into<String>,
    ) -> Self {
        self.base_assets.insert(symbol.into(), asset_code.into());
        self
    }

    /// Build from explicit credentials, registering each `(symbol, base-asset
    /// code)`.
    ///
    /// # Errors
    /// Fails if the HTTP client can't be built.
    pub fn connect(creds: KrakenCredentials, base_assets: &[(&str, &str)]) -> Result<Self> {
        let client = KrakenPrivateClient::new(creds).map_err(ex)?;
        let mut adapter = Self::new(client);
        for (sym, code) in base_assets {
            adapter = adapter.with_base_asset(*sym, *code);
        }
        Ok(adapter)
    }

    /// Build from `KRAKEN_API_KEY` / `KRAKEN_API_SECRET`, registering each
    /// `(symbol, base-asset code)`.
    ///
    /// # Errors
    /// Fails if a credential env var is missing or the client can't be built.
    pub fn from_env(base_assets: &[(&str, &str)]) -> Result<Self> {
        let creds = KrakenCredentials::from_env().map_err(ex)?;
        Self::connect(creds, base_assets)
    }

    /// Borrow the underlying signed client.
    #[must_use]
    pub fn client(&self) -> &KrakenPrivateClient {
        &self.client
    }
}

#[async_trait]
impl ExchangeClient for KrakenSpotAdapter {
    fn name(&self) -> &str {
        "kraken"
    }

    async fn place_order(&self, order: &Order) -> Result<String> {
        if order.stop.is_some() {
            return Err(rustrade::Error::exchange(
                "Kraken spot adapter does not support stop attachments",
            ));
        }
        let order_type = kraken_order_type(order.kind)?;
        let volume = fmt_amount(order.size.value());
        let price = if order.kind == OrderKind::Limit {
            order.limit_price.map(|p| fmt_amount(p.value()))
        } else {
            None
        };
        let resp = self
            .client
            .place_order(
                order.symbol.as_str(),
                kraken_side(order.side),
                order_type,
                &volume,
                price.as_deref(),
            )
            .await
            .map_err(ex)?;
        resp.txid
            .into_iter()
            .next()
            .ok_or_else(|| rustrade::Error::exchange("Kraken AddOrder returned no txid"))
    }

    async fn cancel_all(&self, symbol: &Symbol) -> Result<usize> {
        let open = self.client.get_open_orders().await.map_err(ex)?.open;
        let mut cancelled = 0;
        for (txid, order) in open {
            let pair_matches = order
                .descr
                .as_ref()
                .is_some_and(|d| d.pair == symbol.as_str());
            if pair_matches && self.client.cancel_order(&txid).await.is_ok() {
                cancelled += 1;
            }
        }
        Ok(cancelled)
    }

    async fn close_position(&self, symbol: &Symbol, position: &Position) -> Result<String> {
        if position.is_flat() {
            return Err(rustrade::Error::exchange(format!(
                "close_position: {} holds no balance",
                symbol.as_str()
            )));
        }
        // Spot is long-only: closing a holding is a market SELL of the balance.
        let volume = fmt_amount(position.qty.abs());
        let resp = self
            .client
            .place_order(symbol.as_str(), "sell", "market", &volume, None)
            .await
            .map_err(ex)?;
        resp.txid
            .into_iter()
            .next()
            .ok_or_else(|| rustrade::Error::exchange("Kraken AddOrder returned no txid"))
    }

    async fn get_position(&self, symbol: &Symbol) -> Result<Position> {
        let Some(asset) = self.base_assets.get(symbol.as_str()) else {
            // Without the base-asset code we can't read the holding; treat as flat.
            tracing::warn!(
                symbol = %symbol,
                "no Kraken base-asset code registered — reporting flat (use with_base_asset)"
            );
            return Ok(Position::FLAT);
        };
        let balances = self.client.get_balance().await.map_err(ex)?;
        let qty = balance_of(&balances, asset);
        Ok(Position {
            qty,
            // Spot has no exchange-side entry price (would need cost-basis tracking).
            entry_price: None,
            unrealised_pnl: 0.0,
        })
    }

    async fn get_balance(&self, currency: &str) -> Result<f64> {
        let balances = self.client.get_balance().await.map_err(ex)?;
        Ok(balance_of(&balances, currency))
    }

    fn supports(&self, capability: Capability) -> bool {
        // Spot via the REST AddOrder surface: only resting-order tracking.
        matches!(capability, Capability::OrderTracking)
    }

    fn contract_value(&self, _symbol: &Symbol) -> f64 {
        1.0
    }

    fn instrument_spec(&self, _symbol: &Symbol) -> InstrumentSpec {
        InstrumentSpec {
            asset_class: AssetClass::CryptoSpot,
            contract_value: 1.0,
            tick_size: 0.0,
            lot_size: 0.0,
            min_notional: 0.0,
        }
    }

    async fn get_open_orders(&self, symbol: &Symbol) -> Result<Vec<OpenOrder>> {
        let open = self.client.get_open_orders().await.map_err(ex)?.open;
        let mut out = Vec::new();
        for (txid, order) in open {
            let Some(descr) = &order.descr else { continue };
            if descr.pair != symbol.as_str() {
                continue;
            }
            let size = order.vol.parse::<f64>().unwrap_or(0.0);
            let filled = order.vol_exec.parse::<f64>().unwrap_or(0.0);
            out.push(OpenOrder {
                order_id: txid,
                client_id: None,
                symbol: symbol.clone(),
                side: if descr.side == "sell" {
                    Side::Sell
                } else {
                    Side::Buy
                },
                kind: if descr.ordertype == "limit" {
                    OrderKind::Limit
                } else {
                    OrderKind::Market
                },
                limit_price: descr
                    .price
                    .parse::<f64>()
                    .ok()
                    .filter(|p| *p > 0.0)
                    .map(Price),
                size: Volume(size),
                filled: Volume(filled),
                status: order_status(&order.status, filled, size),
                created_at: order.opentm.and_then(secs_to_dt),
            });
        }
        Ok(out)
    }

    async fn cancel_order(&self, _symbol: &Symbol, order_id: &str) -> Result<bool> {
        let resp = self.client.cancel_order(order_id).await.map_err(ex)?;
        Ok(resp.count > 0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn side_maps() {
        assert_eq!(kraken_side(Side::Buy), "buy");
        assert_eq!(kraken_side(Side::Sell), "sell");
    }

    #[test]
    fn order_type_market_limit_only() {
        assert_eq!(kraken_order_type(OrderKind::Market).unwrap(), "market");
        assert_eq!(kraken_order_type(OrderKind::Limit).unwrap(), "limit");
        assert!(kraken_order_type(OrderKind::Ioc).is_err());
        assert!(kraken_order_type(OrderKind::Fok).is_err());
        assert!(kraken_order_type(OrderKind::PostOnly).is_err());
    }

    #[test]
    fn amount_is_plain_decimal_trimmed() {
        assert_eq!(fmt_amount(0.5), "0.5");
        assert_eq!(fmt_amount(1000.0), "1000");
        assert_eq!(fmt_amount(0.001), "0.001");
        assert_eq!(fmt_amount(1.23456789), "1.23456789");
        // No scientific notation for small values.
        assert_eq!(fmt_amount(0.00000001), "0.00000001");
    }

    #[test]
    fn balance_lookup_parses_or_defaults_zero() {
        let mut b = HashMap::new();
        b.insert("XXBT".to_string(), "0.75".to_string());
        b.insert("ZUSD".to_string(), "1234.5".to_string());
        assert!((balance_of(&b, "XXBT") - 0.75).abs() < 1e-9);
        assert!((balance_of(&b, "ZUSD") - 1234.5).abs() < 1e-9);
        assert_eq!(balance_of(&b, "MISSING"), 0.0);
    }

    #[test]
    fn status_maps() {
        assert_eq!(order_status("open", 0.0, 1.0), OrderStatus::Open);
        assert_eq!(order_status("open", 0.5, 1.0), OrderStatus::PartiallyFilled);
        assert_eq!(order_status("closed", 1.0, 1.0), OrderStatus::Filled);
        assert_eq!(order_status("canceled", 0.0, 1.0), OrderStatus::Cancelled);
        assert_eq!(order_status("pending", 0.0, 1.0), OrderStatus::Pending);
    }

    #[test]
    fn instrument_spec_is_spot() {
        let a = KrakenSpotAdapter::new(
            KrakenPrivateClient::new(KrakenCredentials::new("k", "c2VjcmV0")).unwrap(),
        )
        .with_base_asset("XBTUSD", "XXBT");
        let spec = a.instrument_spec(&Symbol::from("XBTUSD"));
        assert_eq!(spec.asset_class, AssetClass::CryptoSpot);
        assert_eq!(spec.contract_value, 1.0);
        assert_eq!(a.name(), "kraken");
        assert!(a.supports(Capability::OrderTracking));
        assert!(!a.supports(Capability::StopOrders));
    }

    #[test]
    fn secs_to_dt_roundtrips() {
        let dt = secs_to_dt(1_700_000_000.5).expect("valid");
        assert_eq!(dt.timestamp(), 1_700_000_000);
    }
}
