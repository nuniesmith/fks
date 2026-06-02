//! [`KrakenCandleSource`] — a [`rustrade::CandleSource`] over Kraken's public
//! OHLC REST endpoint (via [`exchange-apiws`]'s `KrakenRestClient`).
//!
//! A multi-venue bot needs each symbol's candles from its **own** venue;
//! pairing this with [`RoutingCandleSource`](crate::RoutingCandleSource) gives
//! Kraken spot symbols real Kraken candles instead of another venue's data.
//! Public market data — no credentials.

use std::time::Duration;

use async_trait::async_trait;
use rustrade::{Candle, CandleSource, Result, Symbol};
use serde_json::Value;
use tracing::debug;

use exchange_apiws::KrakenRestClient;

use crate::ex;

/// Map a rustrade poll `interval` to a Kraken OHLC interval (minutes). Kraken
/// supports `1/5/15/30/60/240/1440/…`; snap to the nearest supported value.
fn kraken_interval_mins(interval: Duration) -> u32 {
    match interval.as_secs() {
        0..=60 => 1,
        61..=300 => 5,
        301..=900 => 15,
        901..=1800 => 30,
        1801..=3600 => 60,
        3601..=14400 => 240,
        _ => 1440,
    }
}

/// Parse a Value field Kraken sends as a decimal **string** (or, defensively, a
/// number) into `f64` — `0.0` if absent/unparseable.
fn cell_f64(v: &Value) -> f64 {
    v.as_str()
        .and_then(|s| s.parse().ok())
        .or_else(|| v.as_f64())
        .unwrap_or(0.0)
}

/// Parse Kraken's OHLC response into rustrade candles, keeping the most recent
/// `limit`. The response shape is
/// `{ "<PAIR>": [[time, open, high, low, close, vwap, volume, count], …], "last": N }`
/// — one pair array under a pair-named key. Times are Kraken Unix **seconds**,
/// converted to milliseconds to match the other sources.
fn parse_ohlc(raw: &Value, limit: usize) -> Vec<Candle> {
    // The single pair array lives under a pair-named key (anything but "last").
    let Some(rows) = raw
        .as_object()
        .and_then(|obj| {
            obj.iter()
                .find(|(k, v)| k.as_str() != "last" && v.is_array())
        })
        .and_then(|(_, v)| v.as_array())
    else {
        return Vec::new();
    };

    let mut candles: Vec<Candle> = rows
        .iter()
        .filter_map(|row| {
            let r = row.as_array()?;
            if r.len() < 7 {
                return None;
            }
            Some(Candle {
                time: r[0].as_i64()? * 1_000, // seconds → milliseconds
                open: cell_f64(&r[1]),
                high: cell_f64(&r[2]),
                low: cell_f64(&r[3]),
                close: cell_f64(&r[4]),
                volume: cell_f64(&r[6]), // r[5] is vwap; volume is r[6]
            })
        })
        .collect();

    // Kraken returns oldest→newest; keep the most recent `limit`.
    if candles.len() > limit {
        candles.drain(0..candles.len() - limit);
    }
    candles
}

/// A [`rustrade::CandleSource`] backed by Kraken's public `/0/public/OHLC`.
pub struct KrakenCandleSource {
    client: KrakenRestClient,
}

impl KrakenCandleSource {
    /// Build a public-data client against Kraken's live API.
    ///
    /// # Errors
    /// Fails if the HTTP client can't be built.
    pub fn new() -> Result<Self> {
        Ok(Self {
            client: KrakenRestClient::new().map_err(ex)?,
        })
    }

    /// Wrap an existing [`KrakenRestClient`].
    #[must_use]
    pub fn with_client(client: KrakenRestClient) -> Self {
        Self { client }
    }
}

#[async_trait]
impl CandleSource for KrakenCandleSource {
    fn name(&self) -> &str {
        "kraken"
    }

    async fn poll(&self, symbol: &Symbol, interval: Duration, limit: usize) -> Result<Vec<Candle>> {
        let mins = kraken_interval_mins(interval);
        // The demo's Kraken symbols are Kraken pair names (e.g. "XBTUSD").
        let raw = self
            .client
            .get_ohlc(symbol.as_str(), mins)
            .await
            .map_err(ex)?;
        let candles = parse_ohlc(&raw, limit);
        debug!(symbol = %symbol, interval_mins = mins, n = candles.len(), "kraken OHLC polled");
        Ok(candles)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn interval_snaps_to_supported_minutes() {
        assert_eq!(kraken_interval_mins(Duration::from_secs(60)), 1);
        assert_eq!(kraken_interval_mins(Duration::from_secs(300)), 5);
        assert_eq!(kraken_interval_mins(Duration::from_secs(3600)), 60);
        assert_eq!(kraken_interval_mins(Duration::from_secs(86_400)), 1440);
    }

    #[test]
    fn parses_pair_array_and_converts_seconds_to_millis() {
        let raw = json!({
            "XXBTZUSD": [
                [1_700_000_000i64, "65000.0", "65100.5", "64950.0", "65080.0", "65020.0", "12.5", 42],
                [1_700_000_060i64, "65080.0", "65200.0", "65050.0", "65150.0", "65120.0", "8.0", 30]
            ],
            "last": 1_700_000_060i64
        });
        let candles = parse_ohlc(&raw, 10);
        assert_eq!(candles.len(), 2);
        assert_eq!(candles[0].time, 1_700_000_000_000); // secs → ms
        assert!((candles[0].open - 65000.0).abs() < 1e-9);
        assert!((candles[0].high - 65100.5).abs() < 1e-9);
        assert!((candles[0].volume - 12.5).abs() < 1e-9); // index 6, not vwap
        assert!((candles[1].close - 65150.0).abs() < 1e-9);
    }

    #[test]
    fn keeps_only_the_most_recent_limit() {
        let rows: Vec<Value> = (0..5)
            .map(|i| json!([1_700_000_000i64 + i * 60, "1", "1", "1", "1", "1", "1", 1]))
            .collect();
        let raw = json!({ "XXBTZUSD": rows, "last": 0 });
        let candles = parse_ohlc(&raw, 2);
        assert_eq!(candles.len(), 2);
        // Most recent two (i=3, i=4).
        assert_eq!(candles[0].time, (1_700_000_000 + 3 * 60) * 1_000);
        assert_eq!(candles[1].time, (1_700_000_000 + 4 * 60) * 1_000);
    }

    #[test]
    fn empty_or_error_shape_yields_no_candles() {
        assert!(parse_ohlc(&json!({ "last": 0 }), 10).is_empty());
        assert!(parse_ohlc(&json!({}), 10).is_empty());
        assert!(parse_ohlc(&json!("nonsense"), 10).is_empty());
    }
}
