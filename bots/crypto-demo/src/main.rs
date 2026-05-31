//! `crypto-demo` — a working rustrade bot over crypto pairs.
//!
//! Wires the full published FKS stack together and paper-trades over time:
//!
//! ```text
//!   exchange-apiws (KuCoin Futures klines)
//!        │  CandleSource::poll
//!        ▼
//!   rustrade CandlePollerService ──► MarketDataBus ──► EmaCrossBrain
//!        (one per symbol)                               (indicators-ta)
//!                                                          │ Decision
//!                                                          ▼
//!   rustrade ExecutionService (risk gate: sizing + session PnL + breaker)
//!                                                          ▼
//!                                                   MockExchange (paper)
//! ```
//!
//! Safe to leave running for days: PAPER mode only (no real orders), live
//! KuCoin market data by default, synthetic fallback when offline. Exposes
//! `:9091/metrics` with the `fks_bot_*` series so the FKS spawner / Prometheus
//! can scrape it exactly like `fks-bot-example`.
//!
//! ```bash
//! cargo run -p crypto-demo                                  # live XBT/ETH/SOL, paper
//! DEMO_SYMBOLS=XBTUSDTM,ETHUSDTM cargo run -p crypto-demo   # pick pairs
//! DEMO_SOURCE=synthetic cargo run -p crypto-demo            # offline
//! ```

use std::sync::Arc;
use std::time::{Duration, Instant};

use rustrade::{Bot, BotConfig, Brain, ExchangeClient, SizingConfig};
use rustrade::{CircuitBreakerConfig, SessionPnlConfig};
use tokio_util::sync::CancellationToken;
use tracing::info;

mod brain;
mod metrics;
mod mock_exchange;
mod paper;
mod server;
mod source;

use crate::brain::{EmaCrossBrain, EmaCrossConfig};
use crate::mock_exchange::MockExchange;

/// Read a comma-separated env list, falling back to `default`.
fn env_list(key: &str, default: &[&str]) -> Vec<String> {
    std::env::var(key)
        .ok()
        .map(|v| {
            v.split(',')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect::<Vec<_>>()
        })
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| default.iter().map(|s| s.to_string()).collect())
}

fn env_u64(key: &str, default: u64) -> u64 {
    std::env::var(key)
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    rustrade::logging::init_tracing();

    // ── Config from env ───────────────────────────────────────────────────
    let bot_id = std::env::var("FKS_BOT_ID").unwrap_or_else(|_| "crypto-demo".into());
    // KuCoin Futures perpetual symbols (XBT = BTC on KuCoin). Override with
    // DEMO_SYMBOLS=... ; use spot-style names if you point at a spot source.
    let symbols = env_list("DEMO_SYMBOLS", &["XBTUSDTM", "ETHUSDTM", "SOLUSDTM"]);
    let poll_secs = env_u64("DEMO_POLL_SECS", 60);
    let interval_secs = env_u64("DEMO_CANDLE_SECS", 60); // 1m candles
    let warmup = env_u64("DEMO_WARMUP_CANDLES", 100) as usize;
    let metrics_port = std::env::var("BOT_METRICS_PORT")
        .ok()
        .and_then(|s| s.parse::<u16>().ok())
        .unwrap_or(9091);

    info!(
        bot_id = %bot_id,
        symbols = ?symbols,
        poll_secs,
        source = %std::env::var("DEMO_SOURCE").unwrap_or_else(|_| "kucoin".into()),
        "crypto-demo starting (PAPER mode)"
    );

    // ── Market data: one CandleSource shared across symbols ────────────────
    let candle_source = source::build_source(&symbols);
    info!(source = candle_source.name(), "market data source selected");

    // ── Strategy + paper exchange ──────────────────────────────────────────
    let brain: Arc<dyn Brain> = Arc::new(EmaCrossBrain::new(
        format!("ema-cross-{bot_id}"),
        EmaCrossConfig::default(),
    ));
    let exchange: Arc<dyn ExchangeClient> = Arc::new(MockExchange);

    // ── Bot config: multi-symbol + risk gates ─────────────────────────────
    let config = BotConfig::builder()
        .name(format!("crypto-demo-{bot_id}"))
        .symbols(symbols.iter().cloned())
        .shutdown_timeout(Duration::from_secs(10))
        // Paper sizing. The MockExchange reports contract_value = 1.0, so
        // notional (margin × leverage) must exceed the asset price to size
        // ≥ 1 contract. BTC ≈ 65k ⇒ 50k margin × 5x = 250k notional ⇒ a few
        // contracts. Against a real KuCoin adapter (XBTUSDTM contract_value
        // = 0.001 BTC) far smaller margin would suffice — tune per deployment.
        .sizing_config(SizingConfig {
            margin_per_trade: 50_000.0,
            leverage: 5,
            max_contracts: 100,
        })
        // Stop the session if paper PnL drops past this (per UTC day).
        .session_pnl_config(SessionPnlConfig::default())
        // Trip after repeated losses, cool down, resume.
        .circuit_breaker_config(CircuitBreakerConfig::default())
        .build()?;

    let mut bot = Bot::new(config, exchange, vec![brain])?;

    // Attach one supervised candle poller per symbol. The poller calls
    // CandleSource::poll on `poll_cadence`, diffs newly-closed candles, and
    // publishes them to the bus as MarketDataEvent::Candle.
    let interval = Duration::from_secs(interval_secs);
    let cadence = Duration::from_secs(poll_secs);
    for sym in &symbols {
        bot = bot.with_candle_poller(
            Arc::clone(&candle_source),
            sym.clone(),
            interval,
            cadence,
            warmup,
        );
    }

    let handle = bot.handle();

    // ── Auxiliary services (metrics HTTP + uptime), torn down with the bot ──
    let aux_cancel = CancellationToken::new();

    // Paper-PnL tracker: signals → simulated round trips → metrics + risk PnL.
    paper::spawn(
        handle.clone(),
        bot.market_data_bus().clone(),
        bot.signal_bus().clone(),
        aux_cancel.clone(),
    );

    let start = Arc::new(Instant::now());
    tokio::spawn(metrics::uptime_loop(Arc::clone(&start)));

    {
        let cancel = aux_cancel.clone();
        tokio::spawn(async move {
            if let Err(e) = server::run(metrics_port, cancel).await {
                tracing::error!(error = %e, "metrics server crashed");
            }
        });
    }

    // Periodic health + PnL snapshot to the log so a long run is observable.
    {
        let h = handle.clone();
        let cancel = aux_cancel.clone();
        tokio::spawn(async move {
            let mut tick = tokio::time::interval(Duration::from_secs(300));
            loop {
                tokio::select! {
                    _ = cancel.cancelled() => break,
                    _ = tick.tick() => {
                        let health = h.health().await;
                        info!(
                            healthy = health.healthy,
                            "crypto-demo heartbeat — see :{}/metrics for fks_bot_* series",
                            metrics_port,
                        );
                    }
                }
            }
        });
    }

    info!(port = metrics_port, "metrics live at /metrics and /health");

    // ── Run until SIGTERM / Ctrl-C ─────────────────────────────────────────
    let result = bot.run_until_shutdown().await;
    aux_cancel.cancel();
    info!("crypto-demo exited");
    result
}
