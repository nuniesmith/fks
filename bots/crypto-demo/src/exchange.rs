//! Exchange selection for the demo.
//!
//! The default is [`MockExchange`] — **paper only**, it places no real orders
//! and reports `contract_value = 1.0`. This keeps the demo safe to leave
//! running anywhere (the "no autonomous execution" default of the FKS stack).
//!
//! Set `DEMO_EXCHANGE=kucoin` to route orders through the **live** KuCoin
//! Futures adapter ([`rustrade_exchange_apiws::KucoinExchangeAdapter`]), the
//! Track-1 bridge to `exchange-apiws`'s signed REST. That path requires
//! `KC_KEY` / `KC_SECRET` / `KC_PASSPHRASE` and is real trading — point those
//! at a sandbox/sub-account to paper-trade the identical code path. If the
//! adapter can't be built (missing creds, network), the demo logs loudly and
//! falls back to the paper `MockExchange` rather than trading on broken state.
//!
//! When the live adapter is selected, a [`KucoinFillSource`] is wired too so
//! the bot consumes **real fills** (which also enables the framework's
//! bracket/OCO handling). The demo's paper PnL simulator is disabled in that
//! mode to avoid double-counting (see `main.rs`).

use std::sync::Arc;
use std::time::Duration;

use rustrade::{ExchangeClient, FillSource};
use rustrade_exchange_apiws::{
    KrakenFillSource, KrakenSpotAdapter, KucoinExchangeAdapter, KucoinFillSource,
};
use tracing::{error, info, warn};

use crate::mock_exchange::MockExchange;

/// The selected exchange plus, when live, its real-fill source.
pub struct Selected {
    /// Where orders go (paper `MockExchange` or the live KuCoin adapter).
    pub exchange: Arc<dyn ExchangeClient>,
    /// Real fills from the exchange, present only on the live path. When
    /// `Some`, the caller must skip the paper PnL simulator (they'd
    /// double-count) — and the framework turns on bracket/OCO handling.
    pub fills: Option<Arc<dyn FillSource>>,
}

impl Selected {
    fn paper() -> Self {
        info!("exchange: MockExchange (paper — places no real orders)");
        Self {
            exchange: Arc::new(MockExchange),
            fills: None,
        }
    }
}

/// Build the configured exchange (+ fill source).
///
/// `leverage` should match the bot's `SizingConfig.leverage` so the per-order
/// leverage the adapter sends to KuCoin agrees with how positions were sized.
pub async fn build_exchange(symbols: &[String], leverage: u32) -> Selected {
    let want = std::env::var("DEMO_EXCHANGE").unwrap_or_else(|_| "mock".into());
    match want.to_ascii_lowercase().as_str() {
        "kucoin" => build_kucoin(symbols, leverage).await,
        "kraken" => build_kraken(symbols),
        _ => Selected::paper(),
    }
}

/// KuCoin Futures (live): adapter + real fills via the private WS + /recentFills.
async fn build_kucoin(symbols: &[String], leverage: u32) -> Selected {
    warn!(
        "DEMO_EXCHANGE=kucoin — routing orders through LIVE KuCoin Futures. \
         Confirm KC_KEY/KC_SECRET/KC_PASSPHRASE target the account you intend to trade \
         (use a sandbox/sub-account to paper-trade this exact path)."
    );

    let syms: Vec<&str> = symbols.iter().map(String::as_str).collect();
    match KucoinExchangeAdapter::from_env(leverage, &syms).await {
        Ok(adapter) => {
            // Reuse the adapter's signed client for the fill source (same creds,
            // KuCoin Futures). The source streams real executions via the private
            // tradeOrders WS + /recentFills.
            let fills = KucoinFillSource::connect(
                adapter.client().clone(),
                exchange_apiws::KucoinEnv::LiveFutures,
                symbols.to_vec(),
                Duration::from_secs(5),
            );
            info!(
                leverage,
                symbols = syms.len(),
                "exchange: KuCoin Futures adapter (LIVE) + real fill source — \
                 contract multipliers fetched, brackets enabled"
            );
            Selected {
                exchange: Arc::new(adapter),
                fills: Some(Arc::new(fills)),
            }
        }
        Err(e) => {
            error!(
                error = %e,
                "kucoin adapter unavailable — FALLING BACK to MockExchange (paper)"
            );
            Selected::paper()
        }
    }
}

/// Kraken **spot** (live): adapter + real fills via TradesHistory polling.
///
/// Spot is long-only with no leverage and `AssetClass::CryptoSpot`. Use Kraken
/// pair names in `DEMO_SYMBOLS` (e.g. `XBTUSD`) and tune the demo's sizing for
/// spot (a `contract_value` of 1.0 means margin × leverage is the notional).
fn build_kraken(symbols: &[String]) -> Selected {
    warn!(
        "DEMO_EXCHANGE=kraken — routing orders through LIVE Kraken spot. \
         Confirm KRAKEN_API_KEY/KRAKEN_API_SECRET target the account you intend to trade."
    );
    let base_assets = kraken_base_assets(symbols);
    let refs: Vec<(&str, &str)> = base_assets
        .iter()
        .map(|(s, c)| (s.as_str(), c.as_str()))
        .collect();
    match KrakenSpotAdapter::from_env(&refs) {
        Ok(adapter) => {
            // Kraken has no private own-trades WS through exchange-apiws, so real
            // fills come from polling TradesHistory. Fee is in the quote (USD).
            let fills = KrakenFillSource::connect_default(adapter.client().clone(), "USD");
            info!(
                symbols = symbols.len(),
                base_assets = refs.len(),
                "exchange: Kraken spot adapter (LIVE) + real fill source (CryptoSpot)"
            );
            Selected {
                exchange: Arc::new(adapter),
                fills: Some(Arc::new(fills)),
            }
        }
        Err(e) => {
            error!(error = %e, "kraken adapter unavailable — FALLING BACK to MockExchange (paper)");
            Selected::paper()
        }
    }
}

/// Resolve `symbol → Kraken base-asset code` from `DEMO_KRAKEN_BASE_ASSETS`
/// (`"XBTUSD:XXBT,ETHUSD:XETH"`) or a built-in default for common USD pairs.
/// Unmapped symbols report flat positions (the adapter warns).
fn kraken_base_assets(symbols: &[String]) -> Vec<(String, String)> {
    if let Ok(env) = std::env::var("DEMO_KRAKEN_BASE_ASSETS") {
        return env
            .split(',')
            .filter_map(|entry| entry.split_once(':'))
            .map(|(s, c)| (s.trim().to_string(), c.trim().to_string()))
            .collect();
    }
    // Best-effort defaults: Kraken uses legacy X-prefixed codes for BTC/ETH.
    let code_for = |sym: &str| -> Option<&'static str> {
        match sym {
            s if s.starts_with("XBT") => Some("XXBT"),
            s if s.starts_with("ETH") => Some("XETH"),
            s if s.starts_with("SOL") => Some("SOL"),
            s if s.starts_with("ADA") => Some("ADA"),
            s if s.starts_with("DOT") => Some("DOT"),
            _ => None,
        }
    };
    symbols
        .iter()
        .filter_map(|s| code_for(s).map(|c| (s.clone(), c.to_string())))
        .collect()
}
