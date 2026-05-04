//! Wires the real `KuCoinClient` and `KucoinExchangeAdapter` into a
//! `rustrade::Bot` with a `StubBrain` (always `Hold`).
//!
//! This example does **not** place any orders — the brain is a no-op. Its
//! purpose is to verify that the adapter compiles against the published
//! `exchange-apiws` API and can be constructed into an `Arc<dyn ExchangeClient>`
//! that the framework accepts.
//!
//! Credentials default to the `KC_KEY` / `KC_SECRET` / `KC_PASSPHRASE`
//! environment variables (empty strings if unset). Since the brain only
//! returns `Hold`, no requests are actually made — we just construct the
//! adapter and run the bot for ~1 second under a programmatic shutdown.

use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;

use exchange_apiws::{Credentials, KuCoin, KucoinEnv};
use rustrade::{
    Bot, BotConfig, Brain, Decision, ExchangeClient, MarketDataEvent, Position, Result,
    SupervisorConfig,
};
use rustrade_kucoin::KucoinExchangeAdapter;

struct StubBrain;

#[async_trait]
impl Brain for StubBrain {
    fn name(&self) -> &str {
        "stub"
    }

    async fn on_event(&self, _event: &MarketDataEvent, _position: &Position) -> Result<Decision> {
        Ok(Decision::hold())
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    rustrade::logging::init();

    // Credentials from env (empty by default — adapter still constructs;
    // we just don't actually call the network).
    let creds = Credentials::new(
        std::env::var("KC_KEY").unwrap_or_default(),
        std::env::var("KC_SECRET").unwrap_or_default(),
        std::env::var("KC_PASSPHRASE").unwrap_or_default(),
    );

    let kucoin_rest = KuCoin::new(creds, KucoinEnv::LiveFutures).rest_client()?;
    let leverage: u32 = 5;
    let exchange: Arc<dyn ExchangeClient> =
        Arc::new(KucoinExchangeAdapter::new(Arc::new(kucoin_rest), leverage));

    tracing::info!(
        exchange = exchange.name(),
        leverage,
        contract_value_xbt = exchange.contract_value("XBTUSDTM").await.unwrap_or(0.0),
        "kucoin adapter constructed"
    );

    let brains: Vec<Arc<dyn Brain>> = vec![Arc::new(StubBrain)];

    let config = BotConfig::builder()
        .name("kucoin-stub-bot")
        .session_symbol("XBTUSDTM")
        .supervisor(
            SupervisorConfig::default()
                .without_signal_handler()
                .with_shutdown_timeout(Duration::from_secs(2)),
        )
        .build();

    let bot = Bot::new(config, exchange, brains);
    let cancel = bot.supervisor().cancel_token().clone();

    // Trigger a programmatic shutdown after 1s — this example proves wiring,
    // not live trading.
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_secs(1)).await;
        tracing::info!("triggering shutdown");
        cancel.cancel();
    });

    bot.run_until_shutdown().await?;
    tracing::info!("kucoin-stub-bot exited cleanly");
    Ok(())
}
