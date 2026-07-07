// =============================================================================
// state.rs — shared, observable connector state.
//
// A cheap snapshot the /status endpoint (and later Prometheus) reads. Atomics
// so the connector task can update it without locks on the hot path.
// =============================================================================

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

use crate::config::GateDecision;

/// Live connector state, shared between the connector task and the HTTP server.
#[derive(Debug)]
pub struct ConnectorState {
    /// The gate decision computed at startup (drives the whole lifecycle).
    gate: GateDecision,
    /// The instrument this connector is configured to watch (e.g. `rithmic:MES`).
    symbol: String,
    /// Whether an authenticated Rithmic session is currently open.
    connected: AtomicBool,
    /// Count of market-data updates received since start.
    messages_received: AtomicU64,
    /// Count of candles handed to the persistence sink since start.
    candles_written: AtomicU64,
}

impl ConnectorState {
    /// Construct from the startup gate decision and configured symbol.
    pub fn new(gate: GateDecision, symbol: impl Into<String>) -> Arc<Self> {
        Arc::new(Self {
            gate,
            symbol: symbol.into(),
            connected: AtomicBool::new(false),
            messages_received: AtomicU64::new(0),
            candles_written: AtomicU64::new(0),
        })
    }

    /// Mark the Rithmic session as up/down.
    pub fn set_connected(&self, up: bool) {
        self.connected.store(up, Ordering::Relaxed);
    }

    /// Increment the received-message counter.
    pub fn inc_messages(&self) {
        self.messages_received.fetch_add(1, Ordering::Relaxed);
    }

    /// Increment the candles-written counter.
    pub fn inc_candles(&self) {
        self.candles_written.fetch_add(1, Ordering::Relaxed);
    }

    /// Gate decision recorded at startup.
    pub fn gate(&self) -> &GateDecision {
        &self.gate
    }

    /// Render an observable snapshot for the `/status` endpoint.
    pub fn snapshot(&self) -> StatusSnapshot {
        StatusSnapshot {
            gate: self.gate.clone(),
            gate_reason: self.gate.reason(),
            symbol: self.symbol.clone(),
            connected: self.connected.load(Ordering::Relaxed),
            messages_received: self.messages_received.load(Ordering::Relaxed),
            candles_written: self.candles_written.load(Ordering::Relaxed),
            read_only: true,
            order_plant_open: false,
        }
    }
}

/// JSON-serialisable status payload. `read_only`/`order_plant_open` are constant
/// invariants surfaced deliberately: the order plant is never opened.
#[derive(Debug, Clone, serde::Serialize)]
pub struct StatusSnapshot {
    /// The startup gate decision.
    pub gate: GateDecision,
    /// Human-readable gate reason.
    pub gate_reason: String,
    /// Configured instrument symbol.
    pub symbol: String,
    /// Whether an authenticated session is currently open.
    pub connected: bool,
    /// Market-data updates received since start.
    pub messages_received: u64,
    /// Candles handed to the persistence sink since start.
    pub candles_written: u64,
    /// Always true — this connector is read-only by construction.
    pub read_only: bool,
    /// Always false — the order plant is never opened (doctrine invariant).
    pub order_plant_open: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snapshot_reflects_updates_and_invariants() {
        let state = ConnectorState::new(GateDecision::Ready, "rithmic:MES");
        state.set_connected(true);
        state.inc_messages();
        state.inc_messages();
        state.inc_candles();

        let snap = state.snapshot();
        assert!(snap.connected);
        assert_eq!(snap.messages_received, 2);
        assert_eq!(snap.candles_written, 1);
        assert_eq!(snap.symbol, "rithmic:MES");
        // Doctrine invariants must always hold.
        assert!(snap.read_only);
        assert!(!snap.order_plant_open);
    }
}
