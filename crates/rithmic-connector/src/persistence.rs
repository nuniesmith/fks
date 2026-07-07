// =============================================================================
// persistence.rs — STUB. Where futures market data will be persisted.
//
// ┌─────────────────────────────────────────────────────────────────────────┐
// │ THIS IS DELIBERATELY A STUB (foundation PR).                             │
// │                                                                          │
// │ The full QuestDB futures schema is NOT implemented here. This module    │
// │ defines the seam (`CandleSink`) that the real ILP writer will slot into │
// │ and, for now, only logs what *would* be written. See the TODOs below.   │
// └─────────────────────────────────────────────────────────────────────────┘
//
// TODO(P12 Phase 1): implement a real `QuestDbCandleSink` that writes to the
// `candles_futures` table over the QuestDB ILP line protocol (:9009), mirroring
// janus's `candle_sink.rs` (which currently hardcodes `candles_crypto`). Rules
// carried over from the spike (docs/architecture/RITHMIC_INTEGRATION_SPIKE.md
// §3.2):
//
//   * Table:  candles_futures            (NOT candles_crypto — separate
//             instrument namespace; conflating them corrupts series).
//   * Symbol: venue-tagged `rithmic:MESU6` — futures carry an expiry/contract
//             month that crypto symbols lack; front-month rolls are an open
//             question (spike §8) to resolve before this becomes real.
//   * Columns (proposed, to be finalised against janus's P11 multi-asset work):
//             ts (designated timestamp), venue SYMBOL, symbol SYMBOL,
//             interval SYMBOL, open/high/low/close DOUBLE, volume LONG.
//   * DOM/depth is a SEPARATE, higher-volume table (`book_events_futures`) and
//             is explicitly out of scope for this foundation PR (spike Phase 3).
//
// The order plant is never a source here — read-only market data only.

use tracing::info;

/// A single 1-minute futures candle the connector would persist.
///
/// Kept minimal on purpose: the real schema is decided by janus's P11 work and
/// the spike's DOM-volume measurement, not invented here.
#[derive(Debug, Clone)]
pub struct FuturesCandle {
    /// Venue-tagged symbol, e.g. `rithmic:MESU6`.
    pub symbol: String,
    /// Bar interval label, e.g. `1m`.
    pub interval: String,
    /// Epoch-millisecond timestamp of the bar's open.
    pub ts_ms: i64,
    /// OHLC.
    pub open: f64,
    /// OHLC.
    pub high: f64,
    /// OHLC.
    pub low: f64,
    /// OHLC.
    pub close: f64,
    /// Aggregated traded volume within the bar.
    pub volume: u64,
}

/// The persistence seam. The real implementation (a QuestDB ILP writer) will
/// replace [`StubCandleSink`] without the connector loop changing.
pub trait CandleSink: Send + Sync {
    /// Persist one completed candle. Errors are the sink's concern (buffering,
    /// reconnect) and must never propagate back far enough to kill ingestion.
    fn write_candle(&self, candle: &FuturesCandle);
}

/// No-op sink that logs what a real writer *would* persist. This is the wire
/// that proves the read path end-to-end without standing up QuestDB.
#[derive(Debug, Default, Clone)]
pub struct StubCandleSink;

impl CandleSink for StubCandleSink {
    fn write_candle(&self, candle: &FuturesCandle) {
        // TODO(P12 Phase 1): replace with QuestDB ILP write to `candles_futures`.
        info!(
            target: "rithmic_connector::persistence",
            symbol = %candle.symbol,
            interval = %candle.interval,
            ts_ms = candle.ts_ms,
            open = candle.open,
            high = candle.high,
            low = candle.low,
            close = candle.close,
            volume = candle.volume,
            "STUB candles_futures write (no QuestDB writer wired yet)"
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stub_sink_accepts_a_candle() {
        // The stub must be callable through the trait object the connector holds.
        let sink: Box<dyn CandleSink> = Box::new(StubCandleSink);
        sink.write_candle(&FuturesCandle {
            symbol: "rithmic:MESU6".to_string(),
            interval: "1m".to_string(),
            ts_ms: 1_720_000_000_000,
            open: 5000.0,
            high: 5001.0,
            low: 4999.5,
            close: 5000.5,
            volume: 42,
        });
    }
}
