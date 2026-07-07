// =============================================================================
// health.rs — /health + /status + /positions server (FKS bot contract, :9091).
//
// Mirrors the spawner/bot health surface so the platform can see connector
// state whether or not Rithmic is reachable:
//   GET /health    → 200 {"status":"ok"}   (cheap liveness for Docker/Prometheus)
//   GET /status    → connector snapshot     (gate, connected, counters, invariants)
//   GET /positions → read-only positions book (open positions + account P&L)
// =============================================================================

use std::sync::Arc;

use axum::{Json, Router, extract::State, routing::get};
use serde_json::json;
use tracing::info;

use crate::positions::PositionsBook;
use crate::state::ConnectorState;

/// Combined server state: the connector snapshot source + the positions book.
#[derive(Clone)]
pub struct HealthState {
    /// Shared connector state (gate, counters, connection status).
    pub conn: Arc<ConnectorState>,
    /// Read-only positions book fed by the PnL plant.
    pub positions: PositionsBook,
}

/// Build the axum router for the health/status/positions surface.
pub fn router(conn: Arc<ConnectorState>, positions: PositionsBook) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/status", get(status))
        .route("/positions", get(positions_handler))
        .with_state(HealthState { conn, positions })
}

/// Cheap liveness probe. Always 200 while the process is up — it does NOT
/// depend on the Rithmic session (a gated-off connector is still healthy).
async fn health() -> Json<serde_json::Value> {
    Json(json!({ "status": "ok", "service": "rithmic-connector" }))
}

/// Full connector snapshot: gate decision, connection state, counters, and the
/// read-only/order-plant invariants. Includes the count of tracked positions.
async fn status(State(state): State<HealthState>) -> Json<serde_json::Value> {
    let mut snap = json!(state.conn.snapshot());
    if let Some(obj) = snap.as_object_mut() {
        obj.insert("positions_tracked".into(), json!(state.positions.len()));
    }
    Json(snap)
}

/// The read-only positions book: open positions + optional account P&L summary.
/// The `read_only`/`order_plant_open` invariants are surfaced in the payload.
async fn positions_handler(State(state): State<HealthState>) -> Json<serde_json::Value> {
    Json(json!(state.positions.view()))
}

/// Bind and serve the health surface until the process exits.
pub async fn serve(
    host: &str,
    port: u16,
    conn: Arc<ConnectorState>,
    positions: PositionsBook,
) -> anyhow::Result<()> {
    let addr = format!("{host}:{port}");
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!(%addr, "health/status server listening (GET /health, /status, /positions)");
    axum::serve(listener, router(conn, positions)).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::GateDecision;

    #[tokio::test]
    async fn router_builds_with_state() {
        // Smoke test: the router assembles with a gated-off state. Full HTTP
        // integration is left to the platform's health checks.
        let state = ConnectorState::new(GateDecision::Disabled, "rithmic:MES");
        let _ = router(state, PositionsBook::new());
    }

    #[tokio::test]
    async fn health_is_ok() {
        let Json(v) = health().await;
        assert_eq!(v["status"], "ok");
    }

    #[tokio::test]
    async fn positions_handler_reports_book() {
        use crate::positions::PositionSnapshot;
        let book = PositionsBook::new();
        book.upsert(PositionSnapshot {
            symbol: "ESU6".into(),
            exchange: "CME".into(),
            product_code: "ES".into(),
            net_quantity: 1,
            direction: "long",
            avg_open_price: 5000.0,
            open_pnl: 10.0,
            day_pnl: 12.0,
            buy_qty: 1,
            sell_qty: 0,
            open_quantity: 1,
            account_id: "ACCT1".into(),
        });
        let state = HealthState {
            conn: ConnectorState::new(GateDecision::Ready, "rithmic:ES"),
            positions: book,
        };
        let Json(v) = positions_handler(State(state)).await;
        assert_eq!(v["count"], 1);
        assert_eq!(v["read_only"], true);
        assert_eq!(v["order_plant_open"], false);
        assert_eq!(v["positions"][0]["symbol"], "ESU6");
    }

    #[tokio::test]
    async fn status_includes_positions_tracked() {
        let state = HealthState {
            conn: ConnectorState::new(GateDecision::Ready, "rithmic:ES"),
            positions: PositionsBook::new(),
        };
        let Json(v) = status(State(state)).await;
        assert_eq!(v["positions_tracked"], 0);
        // Doctrine invariant still present on /status.
        assert_eq!(v["order_plant_open"], false);
    }
}
