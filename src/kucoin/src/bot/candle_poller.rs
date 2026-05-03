//! Candle seeding and tick-to-candle stitching.
//!
//! On startup: fetches REST history to warm the indicator window.
//! During live trading: aggregates WS tick prices into closed candles.

use crate::BotSettings;
use exchange_apiws::KuCoinClient;
use exchange_apiws::types::Candle;

/// Fetch the historical candle window needed to warm up all indicators.
///
/// Wraps `client.fetch_klines` with the symbol and parameters from `BotSettings`.
pub async fn fetch_history(
    client: &KuCoinClient,
    settings: &BotSettings,
) -> anyhow::Result<Vec<Candle>> {
    let candles = client
        .fetch_klines(
            &settings.symbol,
            settings.history_candles,
            &settings.rest_kline_type,
        )
        .await?;

    let fetched = candles.len();
    let needed = settings.history_candles;

    if fetched < needed {
        tracing::warn!(
            symbol  = %settings.symbol,
            fetched,
            needed,
            "candle history shorter than requested — indicators will not be fully warmed up; \
             consider reducing history_candles or waiting for more market data",
        );
    } else {
        tracing::info!(
            symbol  = %settings.symbol,
            fetched,
            needed,
            "candle history loaded",
        );
    }

    Ok(candles)
}

/// Fetch only the most recent `limit` candles — used by the poll loop.
///
/// Requesting a small window (e.g. 3–5 candles) instead of the full
/// `history_candles` count avoids fetching 200+ candles every poll tick
/// just to find the 1–2 new ones, saving bandwidth and exchange rate-limit
/// budget. The returned slice is filtered by `last_candle_ts` in the caller.
pub async fn fetch_recent(
    client: &KuCoinClient,
    settings: &BotSettings,
    limit: usize,
) -> anyhow::Result<Vec<Candle>> {
    client
        .fetch_klines(&settings.symbol, limit, &settings.rest_kline_type)
        .await
        .map_err(Into::into)
}

// ── Live tick aggregation ─────────────────────────────────────────────────────

/// Accumulates raw trade ticks into a single in-progress candle.
///
/// Call `close()` at each candle boundary (e.g., every minute) to produce
/// a completed `Candle` and reset for the next period.
#[derive(Debug, Default)]
pub struct CandleBuilder {
    pub open: Option<f64>,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
    pub open_time_ms: i64,
}

impl CandleBuilder {
    pub fn update(&mut self, price: f64, qty: f64, time_ms: i64) {
        if self.open.is_none() {
            self.open = Some(price);
            self.high = price;
            self.low = price;
            self.open_time_ms = time_ms;
        } else {
            if price > self.high {
                self.high = price;
            }
            if price < self.low {
                self.low = price;
            }
        }
        self.close = price;
        self.volume += qty;
    }

    /// Produce a closed candle and reset the builder.
    /// Returns `None` if no ticks arrived during this period.
    pub fn close(&mut self) -> Option<Candle> {
        let open = self.open.take()?;
        let c = Candle {
            time: self.open_time_ms,
            open,
            high: self.high,
            low: self.low,
            close: self.close,
            volume: self.volume,
        };
        self.high = 0.0;
        self.low = 0.0;
        self.close = 0.0;
        self.volume = 0.0;
        self.open_time_ms = 0;
        Some(c)
    }
}
