// =============================================================================
// health.rs — /health + /status server (FKS bot contract, :9091).
//
// Mirrors the spawner/bot health surface so the platform can see connector
// state whether or not Rithmic is reachable:
//   GET /health → 200 {"status":"ok"}   (cheap liveness for Docker/Prometheus)
//   GET /status → connector snapshot     (gate, connected, counters, invariants)
// =============================================================================

use std::sync::Arc;

use axum::{Json, Router, extract::State, routing::get};
use serde_json::json;
use tracing::info;

use crate::state::ConnectorState;

/// Build the axum router for the health/status surface.
pub fn router(state: Arc<ConnectorState>) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/status", get(status))
        .with_state(state)
}

/// Cheap liveness probe. Always 200 while the process is up — it does NOT
/// depend on the Rithmic session (a gated-off connector is still healthy).
async fn health() -> Json<serde_json::Value> {
    Json(json!({ "status": "ok", "service": "rithmic-connector" }))
}

/// Full connector snapshot: gate decision, connection state, counters, and the
/// read-only/order-plant invariants.
async fn status(State(state): State<Arc<ConnectorState>>) -> Json<serde_json::Value> {
    Json(json!(state.snapshot()))
}

/// Bind and serve the health surface until the process exits.
pub async fn serve(host: &str, port: u16, state: Arc<ConnectorState>) -> anyhow::Result<()> {
    let addr = format!("{host}:{port}");
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!(%addr, "health/status server listening (GET /health, GET /status)");
    axum::serve(listener, router(state)).await?;
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
        let _ = router(state);
    }

    #[tokio::test]
    async fn health_is_ok() {
        let Json(v) = health().await;
        assert_eq!(v["status"], "ok");
    }
}
