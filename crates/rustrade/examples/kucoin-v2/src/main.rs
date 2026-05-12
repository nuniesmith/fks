//! `kucoin-v2` — KuCoin Futures SAR trading bot built on the rustrade framework.
//!
//! Compare with v1's `src/main.rs` (~1310 lines, 5 hand-spawned tasks, manual
//! reconciliation, manual SIGTERM handling). This version is ~120 lines because
//! the framework owns the lifecycle: spawn services, restart on failure with
//! exponential backoff, propagate graceful shutdown via cancellation tokens,
//! optionally flatten positions before exiting.
//!
//! What's in this binary:
//!   - `SarBrain` (per-symbol indicator stack + SAR strategy) — `brain.rs`
//!   - `KucoinCandlePoller` (REST kline polling → MarketDataBus) — `poller.rs`
//!   - `BotSettings` (per-symbol Optuna params, lifted verbatim from v1) — `settings.rs`
//!   - `RollingIndicators` (Choppiness/VZO/STC/ElderRay) — `rolling_indicators.rs`
//!   - This `main.rs` (CLI + framework wiring)
//!
//! What's *not* in this binary anymore (the framework owns it):
//!   - Restart loop / backoff / circuit breaker (rustrade-supervisor + rustrade-risk)
//!   - Position sizing (rustrade::ExecutionService + SizeHint::NotionalUsd)
//!   - Session PnL tracking (rustrade-risk::SessionPnl)
//!   - Order execution (rustrade::ExecutionService)
//!   - Graceful shutdown / signal handling (rustrade::Bot::run_until_shutdown)

use std::sync::Arc;
use std::time::Duration;

use clap::Parser;
use exchange_apiws::{Credentials, KuCoin, KucoinEnv};
use rustrade::{Bot, BotConfig, Brain, ExchangeClient, SupervisorConfig};
use rustrade_kucoin::KucoinExchangeAdapter;
use tracing::info;

mod brain;
mod poller;
mod rolling_indicators;
mod settings;

use crate::brain::SarBrain;
use crate::poller::KucoinCandlePoller;
use crate::settings::BotSettings;

#[derive(Parser, Debug)]
#[command(
    name = "kucoin-v2",
    about = "KuCoin Futures SAR trading bot (rustrade v2)"
)]
struct Args {
    #[arg(long, conflicts_with = "live")]
    sim: bool,
    #[arg(long, conflicts_with = "sim")]
    live: bool,
    #[arg(long, value_delimiter = ',', default_value = "XBTUSDTM")]
    symbols: Vec<String>,
    /// Polling interval in seconds. Should match the kline granularity for
    /// closed-bar trading; 60s is the natural choice for 1-minute klines.
    #[arg(long, default_value_t = 20)]
    poll_secs: u64,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    rustrade::logging::init();

    let sim_mode = if args.live {
        false
    } else {
        args.sim || !args.live
    };

    info!(
        mode = if sim_mode { "SIM" } else { "LIVE" },
        symbols = ?args.symbols,
        poll_secs = args.poll_secs,
        "kucoin-v2 starting",
    );

    // ── Build the KuCoin REST client ────────────────────────────────────────
    let creds = Credentials::new(
        std::env::var("KC_KEY").unwrap_or_default(),
        std::env::var("KC_SECRET").unwrap_or_default(),
        std::env::var("KC_PASSPHRASE").unwrap_or_default(),
    );
    let env = KucoinEnv::LiveFutures;
    let kucoin_rest = Arc::new(KuCoin::new(creds, env).rest_client()?);

    // ── Bridge to the framework trait via the published adapter ─────────────
    // Leverage is per-adapter at construction time (per DESIGN_NOTES.md).
    // Pull from the first symbol's settings for now; if you trade multiple
    // symbols with different leverages, build separate adapters + bots.
    let leverage = BotSettings::by_symbol(&args.symbols[0]).leverage;
    let adapter = Arc::new(KucoinExchangeAdapter::new(
        Arc::clone(&kucoin_rest),
        leverage,
    ));
    let exchange: Arc<dyn ExchangeClient> = adapter;

    // ── Build one brain per symbol ──────────────────────────────────────────
    let mut brains: Vec<Arc<dyn Brain>> = Vec::with_capacity(args.symbols.len());
    for sym in &args.symbols {
        let settings = Arc::new(BotSettings::by_symbol(sym));
        let brain = SarBrain::new(sym.clone(), settings);
        brains.push(Arc::new(brain));
    }

    // ── Configure and build the bot ─────────────────────────────────────────
    let config = BotConfig::builder()
        .name("kucoin-v2")
        .session_symbol(args.symbols[0].clone())
        .close_positions_on_shutdown(!sim_mode)
        .flatten_symbols(args.symbols.clone())
        .supervisor(SupervisorConfig::default().with_shutdown_timeout(Duration::from_secs(15)))
        .build();

    let bot = Bot::new(config, Arc::clone(&exchange), brains);

    // ── Optional Discord heartbeat ──────────────────────────────────────────
    // If KC_DISCORD_WEBHOOK is set, spawn a 5-minute heartbeat service
    // through the supervisor. Failures inside the heartbeat (transient
    // Discord outages) are logged and swallowed; the supervisor's restart
    // loop handles the case where the future itself returns Err.
    if let Ok(webhook) = std::env::var("KC_DISCORD_WEBHOOK") {
        match rustrade_notify::DiscordNotifier::new(webhook) {
            Ok(notifier) => {
                let heartbeat = rustrade_notify::WebhookHeartbeatService::new(
                    "kucoin-v2-heartbeat",
                    Arc::new(notifier.with_username("kucoin-v2")),
                    Duration::from_secs(300),
                    format!(
                        ":heartbeat: kucoin-v2 alive — symbols={:?}, mode={}",
                        args.symbols,
                        if sim_mode { "SIM" } else { "LIVE" },
                    ),
                );
                bot.supervisor().spawn_service(Box::new(heartbeat));
                info!("kucoin-v2-heartbeat spawned (KC_DISCORD_WEBHOOK set)");
            }
            Err(e) => {
                tracing::warn!(error = %e, "KC_DISCORD_WEBHOOK invalid; skipping heartbeat");
            }
        }
    }

    // ── Spawn one candle poller per symbol on the bot's supervisor ──────────
    // The supervisor manages their lifecycle the same way it manages the
    // execution services — restart on failure with exponential backoff,
    // graceful shutdown via the shared cancellation token.
    let poll_interval = Duration::from_secs(args.poll_secs);
    for sym in &args.symbols {
        let poller = KucoinCandlePoller::new(
            Arc::clone(&kucoin_rest),
            bot.market_bus().clone(),
            sym.clone(),
            BotSettings::by_symbol(sym).rest_kline_type.clone(),
            poll_interval,
        );
        bot.supervisor().spawn_service(Box::new(poller));
    }

    // ── Run until Ctrl-C / SIGTERM ──────────────────────────────────────────
    bot.run_until_shutdown().await
}
