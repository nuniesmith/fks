// =============================================================================
// connector.rs — the read-only Rithmic connector.
//
// DOCTRINE (non-negotiable): READ-ONLY. This module opens ONLY the Ticker plant
// (`RithmicTickerPlant`) and subscribes market data. It NEVER imports or opens
// `RithmicOrderPlant` — there is no order-entry code path here or anywhere in
// this crate. See CLAUDE.md "no autonomous execution" and the spike doc §4
// "Phase ∞ — Autonomous execution: NEVER".
//
// Lifecycle:
//   * gate = Disabled            → log why, no-op (health server stays up).
//   * gate = MissingCredentials  → log which fields, no-op.
//   * gate = Ready               → open the Ticker plant, log received data,
//                                   bucket trades → the persistence stub.
// =============================================================================

use std::sync::Arc;

use tracing::{info, warn};

use crate::config::{GateDecision, RithmicConfig};
use crate::persistence::CandleSink;
use crate::positions::PositionsBook;
use crate::state::ConnectorState;

/// The venue tag applied to every symbol this connector emits (`rithmic:SYMBOL`).
pub const VENUE: &str = "rithmic";

/// Run the connector to completion (or until the gated no-op returns).
///
/// This is the single entry point the binary calls. It consults the capability
/// gate first and only ever opens a Rithmic session when `Ready`.
pub async fn run(
    config: RithmicConfig,
    state: Arc<ConnectorState>,
    sink: Arc<dyn CandleSink>,
    positions: PositionsBook,
) -> anyhow::Result<()> {
    match config.gate() {
        GateDecision::Disabled => {
            info!(reason = %GateDecision::Disabled.reason(), "connector idle (gate: disabled)");
            Ok(())
        }
        GateDecision::MissingCredentials { missing } => {
            let decision = GateDecision::MissingCredentials { missing };
            warn!(reason = %decision.reason(), "connector idle (gate: missing credentials)");
            Ok(())
        }
        GateDecision::Ready => {
            info!(
                environment = ?config.environment,
                symbol = %format!("{VENUE}:{}", config.instrument),
                exchange = %config.exchange,
                positions_read = config.positions_ready(),
                "capability gate READY — opening the read-only Ticker plant"
            );
            run_ready(config, state, sink, positions).await
        }
    }
}

/// Build the vendor crate's config from our env-driven [`RithmicConfig`]. We
/// build programmatically (not `RrConfig::from_env`) because the crate's own env
/// scheme differs from the spawner-injected RITHMIC_USER/RITHMIC_PASSWORD.
#[cfg(feature = "live-connect")]
fn build_rr_config(
    config: &RithmicConfig,
) -> anyhow::Result<rithmic_rs::RithmicConfig> {
    use rithmic_rs::{RithmicConfig as RrConfig, RithmicEnv};

    use crate::config::RithmicEnvironment;

    let env = match config.environment {
        RithmicEnvironment::Demo => RithmicEnv::Demo,
        RithmicEnvironment::Test => RithmicEnv::Test,
        RithmicEnvironment::Live => RithmicEnv::Live,
    };

    RrConfig::builder(env)
        .url(config.gateway_url.clone())
        .beta_url(config.gateway_alt_url.clone())
        .user(config.user.clone())
        .password(config.password.clone())
        .system_name(config.system_name.clone())
        .app_name(config.app_name.clone())
        .app_version(config.app_version.clone())
        .build()
        .map_err(|e| anyhow::anyhow!("failed to build Rithmic config: {e}"))
}

/// The `Ready` path. Split out so the gate handling above stays legible.
#[cfg(feature = "live-connect")]
async fn run_ready(
    config: RithmicConfig,
    state: Arc<ConnectorState>,
    sink: Arc<dyn CandleSink>,
    positions: PositionsBook,
) -> anyhow::Result<()> {
    use rithmic_rs::{ConnectStrategy, RithmicTickerPlant, rti::messages::RithmicMessage};

    use crate::aggregator::CandleAggregator;

    let rr_config = build_rr_config(&config)?;

    // Read-only positions reader (PnL plant). Runs concurrently with the ticker
    // ONLY when the account triple is configured; market data flows regardless.
    // Spawned as a detached task so a positions-side reconnect can't stall the
    // market-data loop, and vice versa. Never opens the order plant.
    let pnl_task = if config.positions_ready() {
        let account = rithmic_rs::RithmicAccount {
            account_id: config.account_id.clone(),
            fcm_id: config.fcm_id.clone(),
            ib_id: config.ib_id.clone(),
        };
        let pnl_config = build_rr_config(&config)?;
        let book = positions.clone();
        info!(account = %config.account_id, "starting read-only PnL/positions reader");
        Some(tokio::spawn(async move {
            if let Err(e) = crate::positions::run_pnl(pnl_config, account, book).await {
                warn!(error = %e, "PnL/positions reader exited with error");
            }
        }))
    } else {
        info!(
            "positions reader disabled (set RITHMIC_ACCOUNT_ID/FCM_ID/IB_ID to enable); \
             market data still flows"
        );
        None
    };

    // Ticker plant ONLY. Read-only by construction.
    let ticker_plant = RithmicTickerPlant::connect(&rr_config, ConnectStrategy::Retry)
        .await
        .map_err(|e| anyhow::anyhow!("ticker plant connect failed: {e}"))?;
    let mut handle = ticker_plant.get_handle();

    handle
        .login()
        .await
        .map_err(|e| anyhow::anyhow!("ticker plant login failed: {e}"))?;
    state.set_connected(true);
    info!("logged in to Rithmic ticker plant");

    handle
        .subscribe(&config.instrument, &config.exchange)
        .await
        .map_err(|e| anyhow::anyhow!("market-data subscribe failed: {e}"))?;
    let venue_symbol = format!("{VENUE}:{}", config.instrument);
    info!(symbol = %venue_symbol, exchange = %config.exchange, "subscribed to market data (read-only)");

    let mut aggregator = CandleAggregator::new(venue_symbol.clone(), config.exchange.clone(), sink);

    loop {
        match handle.subscription_receiver.recv().await {
            Ok(update) => {
                if let Some(err) = &update.error {
                    if err.is_connection_issue() {
                        warn!(error = %err, "connection issue on ticker stream — stopping loop");
                        break;
                    }
                    continue;
                }
                state.inc_messages();

                match update.message {
                    RithmicMessage::LastTrade(trade) => {
                        let price = trade.trade_price.unwrap_or(0.0);
                        let size = trade.trade_size.unwrap_or(0) as u64;
                        info!(symbol = %venue_symbol, price, size, "trade");
                        // Bucket into 1m bars; the stub sink logs the write.
                        let now_ms = chrono::Utc::now().timestamp_millis();
                        if aggregator.on_trade(now_ms, price, size) {
                            state.inc_candles();
                        }
                    }
                    RithmicMessage::BestBidOffer(bbo) => {
                        info!(
                            symbol = %venue_symbol,
                            bid = bbo.bid_price.unwrap_or(0.0),
                            ask = bbo.ask_price.unwrap_or(0.0),
                            "bbo"
                        );
                    }
                    _ => {}
                }
            }
            Err(e) => {
                warn!(error = %e, "ticker subscription channel closed — stopping loop");
                break;
            }
        }
    }

    // Flush any partial bar and shut the session down cleanly.
    if aggregator.flush() {
        state.inc_candles();
    }
    state.set_connected(false);
    let _ = handle.disconnect().await;
    info!("ticker plant disconnected");

    // Tear the positions reader down with the market-data loop.
    if let Some(task) = pnl_task {
        task.abort();
    }
    Ok(())
}

/// Fallback `Ready` path when the crate is built without the `live-connect`
/// feature: there is no client compiled in, so we log and idle instead of
/// pretending to connect.
#[cfg(not(feature = "live-connect"))]
async fn run_ready(
    _config: RithmicConfig,
    _state: Arc<ConnectorState>,
    _sink: Arc<dyn CandleSink>,
    _positions: PositionsBook,
) -> anyhow::Result<()> {
    warn!(
        "gate is READY but the crate was built without the `live-connect` feature — \
         no Rithmic client available; rebuild with default features to connect"
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::RithmicConfig;
    use crate::persistence::StubCandleSink;

    /// A disabled connector must be a clean no-op — it returns Ok without ever
    /// attempting a connection. (No live Rithmic connection is exercised in
    /// tests; that needs real creds + a paid account.)
    #[tokio::test]
    async fn disabled_connector_is_a_noop() {
        let cfg = RithmicConfig::from_getter(|_| None); // enabled=false
        let state = ConnectorState::new(cfg.gate(), "rithmic:MES");
        let sink = Arc::new(StubCandleSink);
        run(cfg, state.clone(), sink, PositionsBook::new())
            .await
            .unwrap();
        assert!(!state.snapshot().connected);
        assert_eq!(state.snapshot().messages_received, 0);
    }

    /// Enabled-but-uncredentialed is also a clean no-op (missing-creds gate).
    #[tokio::test]
    async fn missing_credentials_is_a_noop() {
        let cfg =
            RithmicConfig::from_getter(|k| (k == "RITHMIC_ENABLED").then(|| "true".to_string()));
        assert!(matches!(
            cfg.gate(),
            GateDecision::MissingCredentials { .. }
        ));
        let state = ConnectorState::new(cfg.gate(), "rithmic:MES");
        run(cfg, state.clone(), Arc::new(StubCandleSink), PositionsBook::new())
            .await
            .unwrap();
        assert!(!state.snapshot().connected);
    }
}
