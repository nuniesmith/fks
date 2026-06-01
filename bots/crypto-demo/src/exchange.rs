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

use std::sync::Arc;

use rustrade::ExchangeClient;
use rustrade_exchange_apiws::KucoinExchangeAdapter;
use tracing::{error, info, warn};

use crate::mock_exchange::MockExchange;

/// Build the configured [`ExchangeClient`].
///
/// `leverage` should match the bot's `SizingConfig.leverage` so the per-order
/// leverage the adapter sends to KuCoin agrees with how positions were sized.
pub async fn build_exchange(symbols: &[String], leverage: u32) -> Arc<dyn ExchangeClient> {
    let want = std::env::var("DEMO_EXCHANGE").unwrap_or_else(|_| "mock".into());

    if !want.eq_ignore_ascii_case("kucoin") {
        info!("exchange: MockExchange (paper — places no real orders)");
        return Arc::new(MockExchange);
    }

    warn!(
        "DEMO_EXCHANGE=kucoin — routing orders through LIVE KuCoin Futures. \
         Confirm KC_KEY/KC_SECRET/KC_PASSPHRASE target the account you intend to trade \
         (use a sandbox/sub-account to paper-trade this exact path)."
    );

    let syms: Vec<&str> = symbols.iter().map(String::as_str).collect();
    match KucoinExchangeAdapter::from_env(leverage, &syms).await {
        Ok(adapter) => {
            info!(
                leverage,
                symbols = syms.len(),
                "exchange: KuCoin Futures adapter (LIVE) — contract multipliers fetched"
            );
            Arc::new(adapter)
        }
        Err(e) => {
            error!(
                error = %e,
                "kucoin adapter unavailable — FALLING BACK to MockExchange (paper)"
            );
            Arc::new(MockExchange)
        }
    }
}
