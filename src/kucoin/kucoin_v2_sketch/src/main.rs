//! `kucoin` v2 — running on the rustrade framework.
//!
//! Compare with the original `main.rs` (~1240 lines, 5 hand-spawned tasks,
//! manual reconciliation, manual SIGTERM handling, manual Discord wiring).
//! This version is ~120 lines and does the same thing because the framework
//! owns the lifecycle, retries, and shutdown.
//!
//! The strategy logic — the SAR brain, the indicator stack, the gates — is
//! exactly the same code as before; it now lives in `brain.rs` as an `impl
//! Brain for SarBrain`. See `brain.rs` for that.

use std::sync::Arc;

use anyhow::Context;
use clap::Parser;
use tracing::info;

use exchange_apiws::{Credentials, KuCoinClient, KucoinEnv};
use indicators::IndicatorConfig;
use rustrade::{Bot, BotConfig};
use rustrade_core::{Brain, ExchangeClient};

mod adapter;       // exchange_apiws ↔ rustrade_core::ExchangeClient
mod brain;         // the SAR strategy as a Brain impl
mod settings;      // BotSettings (per-symbol Optuna params) — unchanged from v1

use crate::adapter::KucoinExchangeAdapter;
use crate::brain::SarBrain;
use crate::settings::BotSettings;

#[derive(Parser, Debug)]
#[command(name = "kucoin", about = "KuCoin Futures SAR trading bot (rustrade v2)")]
struct Args {
    #[arg(long, conflicts_with = "live")]
    sim: bool,
    #[arg(long, conflicts_with = "sim")]
    live: bool,
    #[arg(long, value_delimiter = ',', default_value = "XBTUSDTM")]
    symbols: Vec<String>,
    #[arg(long, default_value_t = 20)]
    poll_secs: u64,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    rustrade::logging::init_default()
        .context("logging init failed")?;

    let sim_mode = if args.live { false } else { args.sim };

    info!(
        mode    = if sim_mode { "SIM" } else { "LIVE" },
        symbols = ?args.symbols,
        "kucoin v2 starting",
    );

    // ── Build the exchange adapter ──────────────────────────────────────────
    // Bridges the published `exchange_apiws::KuCoinClient` to the framework's
    // `rustrade_core::ExchangeClient` trait.  See adapter.rs for the impl.
    let env = match std::env::var("KUCOIN_ENV").as_deref() {
        Ok("spot") => KucoinEnv::LiveSpot,
        Ok("unified") => KucoinEnv::Unified,
        _ => KucoinEnv::LiveFutures,
    };
    let creds = Credentials::new(
        std::env::var("KC_KEY").unwrap_or_default(),
        std::env::var("KC_SECRET").unwrap_or_default(),
        std::env::var("KC_PASSPHRASE").unwrap_or_default(),
    );
    let kucoin = Arc::new(KuCoinClient::new(creds, env)?);
    let exchange: Arc<dyn ExchangeClient> = Arc::new(KucoinExchangeAdapter::new(Arc::clone(&kucoin), env));

    // ── Build one brain per symbol ──────────────────────────────────────────
    // Each symbol gets its own indicator stack + tuning, so each gets its own
    // brain instance. The framework supervises them as separate services.
    let mut brains: Vec<Arc<dyn Brain>> = Vec::with_capacity(args.symbols.len());
    for sym in &args.symbols {
        let settings = Arc::new(BotSettings::by_symbol(sym));
        let brain = SarBrain::new(sym.clone(), settings);
        brains.push(Arc::new(brain));
    }

    // ── Configure and run the bot ───────────────────────────────────────────
    // Bot::run_until_shutdown installs the SIGTERM/Ctrl-C handler, spawns the
    // candle pollers, heartbeats, public + private WS feeds, and the param
    // watcher under a single supervisor — and gracefully closes positions on
    // shutdown when configured to do so.
    let config = BotConfig::builder()
        .name("kucoin")
        .symbols(args.symbols.clone())
        .poll_secs(args.poll_secs)
        .sim_mode(sim_mode)
        .close_positions_on_shutdown(!sim_mode)
        .with_optional_discord_from_env() // looks for DISCORD_WEBHOOK
        .with_optional_redis_from_env()   // looks for REDIS_URL
        .build()?;

    let bot = Bot::new(config, exchange, brains);
    bot.run_until_shutdown().await
}
