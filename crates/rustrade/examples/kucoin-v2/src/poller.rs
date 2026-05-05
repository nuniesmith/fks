//! `KucoinCandlePoller` — a [`TradingService`] that polls KuCoin's REST kline
//! endpoint at a fixed interval and publishes newly-closed candles to the
//! framework's [`MarketDataBus`].
//!
//! This is the v2 replacement for the v1 `bot/candle_poller.rs` plus the
//! `candle_poll_task` in `main.rs`. The framework owns lifecycle and
//! supervision; this service owns the exchange-specific polling loop.
//!
//! # Why REST and not WS?
//!
//! v1 uses both: REST for warm-up + a candle-aligned poll loop, and WS for
//! tick aggregation into the in-progress candle. For v2 we only do REST
//! polling — closed candles only. The brain reacts on closed candles
//! anyway, so this loses no signal-relevant data and removes ~600 lines of
//! WS plumbing. WS aggregation can be added later as a second service if
//! latency on the most-recent bar matters for some strategy.

use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use exchange_apiws::KuCoinClient;
use parking_lot::Mutex;
use rustrade::{MarketDataBus, MarketDataEvent, RestartPolicy, Symbol, TradingService};
use tokio_util::sync::CancellationToken;

/// Polls a single KuCoin futures symbol on a fixed interval and publishes
/// any newly-closed candles to a [`MarketDataBus`].
///
/// The poller deduplicates by candle open-time so a single closed candle is
/// only published once even if multiple polls return overlapping windows.
pub struct KucoinCandlePoller {
    name: String,
    client: Arc<KuCoinClient>,
    bus: MarketDataBus,
    symbol: String,
    granularity: String,
    interval: Duration,
    /// Most recent candle open-time we've already published (ms since epoch).
    /// We only emit candles strictly newer than this.
    last_published_ms: Mutex<i64>,
}

impl KucoinCandlePoller {
    pub fn new(
        client: Arc<KuCoinClient>,
        bus: MarketDataBus,
        symbol: impl Into<String>,
        granularity: impl Into<String>,
        interval: Duration,
    ) -> Self {
        let symbol = symbol.into();
        Self {
            name: format!("kucoin-candles[{symbol}]"),
            client,
            bus,
            symbol,
            granularity: granularity.into(),
            interval,
            last_published_ms: Mutex::new(0),
        }
    }

    /// Fetch the recent kline window once and publish any new closed candles.
    async fn poll_once(&self) -> anyhow::Result<usize> {
        // Fetch a small recent window — most polls find 0–1 new candles.
        let candles = self
            .client
            .fetch_klines(&self.symbol, 5, &self.granularity)
            .await
            .map_err(|e| anyhow::anyhow!("fetch_klines: {e}"))?;

        let mut last_seen = self.last_published_ms.lock();
        let mut published = 0usize;

        // KuCoin returns candles newest-first — sort ascending so we publish in order.
        let mut sorted: Vec<_> = candles
            .into_iter()
            .filter(|c| c.time > *last_seen)
            .collect();
        sorted.sort_by_key(|c| c.time);

        for c in sorted {
            // The most-recent bar may still be in-progress on KuCoin's side.
            // We rely on the granularity to decide when a bar is "closed":
            // a candle whose open time is < (now - granularity) is closed.
            // This keeps the logic exchange-agnostic.
            if !is_closed_candle(c.time, self.interval) {
                tracing::trace!(
                    symbol = %self.symbol,
                    candle_time = c.time,
                    "skipping in-progress candle"
                );
                continue;
            }

            let event = MarketDataEvent::Candle {
                exchange: rustrade::Exchange::from("kucoin"),
                symbol: Symbol::from(self.symbol.as_str()),
                candle: rustrade::Candle {
                    time: c.time,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                    volume: c.volume,
                },
            };

            *last_seen = c.time;
            let _ = self.bus.publish(event);
            published += 1;
        }

        Ok(published)
    }
}

/// Returns `true` if the bar starting at `open_time_ms` is fully closed at
/// the time of this call. We add a small grace window (10% of the interval)
/// to absorb clock skew between the bot host and the exchange.
fn is_closed_candle(open_time_ms: i64, interval: Duration) -> bool {
    let now_ms = chrono::Utc::now().timestamp_millis();
    let interval_ms = interval.as_millis() as i64;
    let grace_ms = interval_ms / 10;
    open_time_ms + interval_ms + grace_ms <= now_ms
}

#[async_trait]
impl TradingService for KucoinCandlePoller {
    fn name(&self) -> &str {
        &self.name
    }

    fn restart_policy(&self) -> RestartPolicy {
        RestartPolicy::OnFailure
    }

    async fn run(&self, cancel: CancellationToken) -> anyhow::Result<()> {
        tracing::info!(
            symbol = %self.symbol,
            granularity = %self.granularity,
            interval_secs = self.interval.as_secs(),
            "kucoin candle poller starting"
        );

        // Run once immediately so the bus has fresh data without waiting
        // for the first interval.
        if let Err(e) = self.poll_once().await {
            tracing::warn!(symbol = %self.symbol, error = %e, "initial poll failed");
        }

        let mut ticker = tokio::time::interval(self.interval);
        ticker.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        // First tick fires immediately; consume it so the next is at +interval.
        ticker.tick().await;

        loop {
            tokio::select! {
                _ = cancel.cancelled() => {
                    tracing::info!(symbol = %self.symbol, "candle poller stopping");
                    return Ok(());
                }
                _ = ticker.tick() => {
                    match self.poll_once().await {
                        Ok(n) if n > 0 => {
                            tracing::debug!(symbol = %self.symbol, published = n, "polled");
                        }
                        Ok(_) => {}
                        Err(e) => {
                            // Don't crash the service on transient REST errors —
                            // log and let the next interval retry. The supervisor's
                            // backoff will only fire if the future itself returns Err.
                            tracing::warn!(symbol = %self.symbol, error = %e, "poll failed");
                        }
                    }
                }
            }
        }
    }
}
