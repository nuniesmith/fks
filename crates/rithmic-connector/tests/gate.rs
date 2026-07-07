// =============================================================================
// Integration tests — the capability gate end-to-end (no live Rithmic).
//
// These exercise the crate's public surface exactly as the binary does: parse
// config from a getter, evaluate the gate, and confirm the connector no-ops
// cleanly when not Ready. A live connection is intentionally NOT tested — it
// requires real credentials and a paid Rithmic account (spike §5.2).
// =============================================================================

use std::sync::Arc;

use rithmic_connector::config::{GateDecision, RithmicConfig};
use rithmic_connector::persistence::StubCandleSink;
use rithmic_connector::state::ConnectorState;
use rithmic_connector::{connector, health};

fn cfg(pairs: &[(&str, &str)]) -> RithmicConfig {
    let owned: Vec<(String, String)> = pairs
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();
    RithmicConfig::from_getter(move |k| {
        owned
            .iter()
            .find(|(key, _)| key == k)
            .map(|(_, v)| v.clone())
    })
}

#[tokio::test]
async fn disabled_by_default_and_connector_noops() {
    let config = cfg(&[]);
    assert_eq!(config.gate(), GateDecision::Disabled);

    let state = ConnectorState::new(config.gate(), "rithmic:MES");
    connector::run(config, state.clone(), Arc::new(StubCandleSink))
        .await
        .expect("disabled connector must return Ok");

    let snap = state.snapshot();
    assert!(!snap.connected);
    assert!(snap.read_only);
    assert!(!snap.order_plant_open, "order plant must never be open");
}

#[tokio::test]
async fn enabled_without_creds_noops() {
    let config = cfg(&[("RITHMIC_ENABLED", "true")]);
    assert!(matches!(
        config.gate(),
        GateDecision::MissingCredentials { .. }
    ));

    let state = ConnectorState::new(config.gate(), "rithmic:MES");
    connector::run(config, state.clone(), Arc::new(StubCandleSink))
        .await
        .expect("uncredentialed connector must return Ok");
    assert!(!state.snapshot().connected);
}

#[tokio::test]
async fn fully_credentialed_config_is_ready() {
    // Ready does NOT imply we connect here — we only assert the gate opens.
    // Actually opening the plant needs a live gateway + real creds.
    let config = cfg(&[
        ("RITHMIC_ENABLED", "true"),
        ("RITHMIC_GATEWAY_URL", "wss://rituz00100.rithmic.com:443"),
        ("RITHMIC_USER", "devuser"),
        ("RITHMIC_PASSWORD", "devpass"),
    ]);
    assert_eq!(config.gate(), GateDecision::Ready);
    assert!(config.gate().is_ready());
}

#[tokio::test]
async fn health_router_assembles_for_every_gate_state() {
    for gate in [
        GateDecision::Disabled,
        GateDecision::MissingCredentials {
            missing: vec!["RITHMIC_USER".to_string()],
        },
        GateDecision::Ready,
    ] {
        let state = ConnectorState::new(gate, "rithmic:MES");
        let _router = health::router(state);
    }
}
