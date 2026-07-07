// =============================================================================
// main.rs — rithmic-connector binary entry point.
//
// Boots the /health + /status server (always) and the connector task (which
// no-ops cleanly when the capability gate is not Ready). Shuts down on SIGINT.
// =============================================================================

use std::sync::Arc;

use anyhow::Context;
use tracing::info;
use tracing_subscriber::EnvFilter;

use rithmic_connector::config::RithmicConfig;
use rithmic_connector::connector;
use rithmic_connector::health;
use rithmic_connector::persistence::{CandleSink, QuestDbCandleSink, StubCandleSink};
use rithmic_connector::positions::PositionsBook;
use rithmic_connector::state::ConnectorState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing();

    let config = RithmicConfig::from_env();
    let gate = config.gate();
    info!(
        service = "rithmic-connector",
        version = env!("CARGO_PKG_VERSION"),
        enabled = config.enabled,
        environment = ?config.environment,
        gate = ?gate,
        "starting (READ-ONLY; order plant is never opened)"
    );
    // Log the gate decision plainly so operators see exactly why we did/didn't
    // connect — this is the capability gate visible in the logs.
    info!(reason = %gate.reason(), "capability gate decision");

    let state = ConnectorState::new(gate, format!("{}:{}", connector::VENUE, config.instrument));

    // Read-only positions book, shared between the PnL reader and the HTTP
    // server. Empty until the (optional) positions subscription fills it.
    let positions = PositionsBook::new();

    // Health/status server — always up, independent of the Rithmic session.
    let health_host = config.health_host.clone();
    let health_port = config.health_port;
    let health_state = state.clone();
    let health_positions = positions.clone();
    let health_task = tokio::spawn(async move {
        if let Err(e) =
            health::serve(&health_host, health_port, health_state, health_positions).await
        {
            tracing::error!(error = %e, "health server exited with error");
        }
    });

    // Persistence sink. Only stand up the real QuestDB ILP writer when the gate
    // is Ready (i.e. candles will actually flow); otherwise the connector is a
    // clean no-op and the stub sink just logs. The QuestDB writer connects
    // lazily on the first candle and shares the state's persistence counters so
    // `/status` reflects what reached QuestDB.
    let sink: Arc<dyn CandleSink> = if state.gate().is_ready() {
        info!(
            questdb = %config.questdb.ilp_addr(),
            "persisting candles_futures to QuestDB over ILP"
        );
        Arc::new(QuestDbCandleSink::connect(
            config.questdb.clone(),
            state.persist_metrics(),
        ))
    } else {
        Arc::new(StubCandleSink)
    };
    let connector_task = tokio::spawn(connector::run(config, state, sink, positions));

    // Wait for shutdown or the connector completing.
    tokio::select! {
        _ = tokio::signal::ctrl_c() => {
            info!("SIGINT received — shutting down");
        }
        res = connector_task => {
            match res {
                Ok(Ok(())) => info!("connector task finished"),
                Ok(Err(e)) => tracing::error!(error = %e, "connector task failed"),
                Err(e) => tracing::error!(error = %e, "connector task panicked"),
            }
        }
    }

    health_task.abort();
    Ok(())
}

fn init_tracing() {
    let filter = EnvFilter::try_from_default_env()
        .or_else(|_| EnvFilter::try_new("info,rithmic_connector=debug"))
        .context("building tracing filter")
        .unwrap();
    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .json()
        .init();
}
