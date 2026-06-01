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
use rustrade_exchange_apiws::{KucoinExchangeAdapter, KucoinFillSource};
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

    if !want.eq_ignore_ascii_case("kucoin") {
        return Selected::paper();
    }

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
