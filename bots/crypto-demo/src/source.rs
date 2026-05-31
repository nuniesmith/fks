//! Market-data sources implementing rustrade's [`CandleSource`].
//!
//! Two implementations:
//!
//! - [`KucoinCandleSource`] — polls KuCoin Futures klines through
//!   `exchange-apiws` (the same client the kucoin reference bot uses). Public
//!   market data, no API key required. This is the real path.
//! - [`SyntheticCandleSource`] — a random-walk generator used when
//!   `DEMO_SOURCE=synthetic` (or when the exchange is unreachable, e.g. CI /
//!   sandboxes that block exchange endpoints). Keeps the demo runnable
//!   anywhere so the framework wiring can be verified offline.
//!
//! rustrade's `CandlePollerService` calls `poll(...)` on a cadence, diffs the
//! returned candles against what it has already seen, and publishes each newly
//! closed candle to the bot's `MarketDataBus` as `MarketDataEvent::Candle`.

use std::sync::Mutex;
use std::time::Duration;

use async_trait::async_trait;
use exchange_apiws::{Credentials, KuCoinClient, KucoinEnv};
use rustrade::{Candle, CandleSource, Result, Symbol};
use tracing::{debug, warn};

/// Map a rustrade poll `interval` to a KuCoin granularity string (minutes).
fn kucoin_granularity(interval: Duration) -> &'static str {
    match interval.as_secs() {
        0..=60 => "1",
        61..=300 => "5",
        301..=900 => "15",
        901..=1800 => "30",
        1801..=3600 => "60",
        3601..=14400 => "240",
        _ => "1440",
    }
}

// ── Live KuCoin source ────────────────────────────────────────────────────────

/// Polls KuCoin Futures klines via `exchange-apiws`. No credentials needed for
/// public market data — we pass empty `Credentials` (klines are unauthenticated).
pub struct KucoinCandleSource {
    client: KuCoinClient,
}

impl KucoinCandleSource {
    /// Build a public-data client against KuCoin Futures.
    pub fn new() -> anyhow::Result<Self> {
        // Empty creds: the kline endpoint is public. Real trading would supply
        // KC_KEY / KC_SECRET / KC_PASSPHRASE, but this demo never places orders.
        let creds = Credentials::new(
            std::env::var("KC_KEY").unwrap_or_default(),
            std::env::var("KC_SECRET").unwrap_or_default(),
            std::env::var("KC_PASSPHRASE").unwrap_or_default(),
        );
        let client = KuCoinClient::new(creds, KucoinEnv::LiveFutures)
            .map_err(|e| anyhow::anyhow!("kucoin client: {e}"))?;
        Ok(Self { client })
    }
}

#[async_trait]
impl CandleSource for KucoinCandleSource {
    fn name(&self) -> &str {
        "kucoin"
    }

    async fn poll(&self, symbol: &Symbol, interval: Duration, limit: usize) -> Result<Vec<Candle>> {
        let gran = kucoin_granularity(interval);
        let raw = self
            .client
            .fetch_klines(symbol.0.as_str(), limit, gran)
            .await
            .map_err(|e| rustrade::Error::Exchange(format!("kucoin fetch_klines: {e}")))?;

        // exchange_apiws::Candle and rustrade::Candle share the same field
        // layout but are distinct types — convert at the boundary.
        let candles = raw
            .into_iter()
            .map(|c| Candle {
                time: c.time,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close,
                volume: c.volume,
            })
            .collect::<Vec<_>>();

        debug!(symbol = %symbol.0, granularity = gran, n = candles.len(), "kucoin klines polled");
        Ok(candles)
    }
}

// ── Synthetic offline source ──────────────────────────────────────────────────

/// Random-walk candle generator. Produces fresh "closed" candles on each poll
/// so the demo runs with no network. Each symbol walks from its own seed price.
pub struct SyntheticCandleSource {
    state: Mutex<Vec<(String, f64, i64)>>, // (symbol, last_close, last_time_ms)
}

impl SyntheticCandleSource {
    /// Seed each symbol at a plausible starting price.
    pub fn new(symbols: &[String]) -> Self {
        let seed = |s: &str| -> f64 {
            match s {
                x if x.starts_with("XBT") || x.starts_with("BTC") => 65_000.0,
                x if x.starts_with("ETH") => 3_200.0,
                x if x.starts_with("SOL") => 150.0,
                _ => 100.0,
            }
        };
        let now = chrono::Utc::now().timestamp_millis();
        let state = symbols.iter().map(|s| (s.clone(), seed(s), now)).collect();
        Self {
            state: Mutex::new(state),
        }
    }
}

#[async_trait]
impl CandleSource for SyntheticCandleSource {
    fn name(&self) -> &str {
        "synthetic"
    }

    async fn poll(&self, symbol: &Symbol, interval: Duration, limit: usize) -> Result<Vec<Candle>> {
        let step_ms = interval.as_millis() as i64;
        let mut guard = self.state.lock().unwrap();
        let entry = guard
            .iter_mut()
            .find(|(s, _, _)| *s == symbol.0)
            .ok_or_else(|| rustrade::Error::Exchange(format!("unknown symbol {}", symbol.0)))?;

        // Generate `limit` candles forward from the stored state so the poller
        // always has a full window; advance the state so the next poll
        // continues the walk (and the poller sees new closed bars).
        let mut price = entry.1;
        let mut t = entry.2;
        let mut out = Vec::with_capacity(limit);
        for _ in 0..limit {
            let drift: f64 = rand::random::<f64>() - 0.5; // [-0.5, 0.5)
            let vol = price * 0.002; // 0.2% per-bar vol
            let open = price;
            let close = (price + 2.0 * drift * vol).max(0.01);
            let high = open.max(close) + rand::random::<f64>() * vol;
            let low = open.min(close) - rand::random::<f64>() * vol;
            out.push(Candle {
                time: t,
                open,
                high,
                low,
                close,
                volume: 10.0 + rand::random::<f64>() * 5.0,
            });
            price = close;
            t += step_ms.max(1);
        }
        entry.1 = price;
        entry.2 = t;
        Ok(out)
    }
}

/// Build the configured source. Defaults to live KuCoin; falls back to the
/// synthetic generator when `DEMO_SOURCE=synthetic`, or when the KuCoin client
/// can't be constructed.
pub fn build_source(symbols: &[String]) -> std::sync::Arc<dyn CandleSource> {
    let want = std::env::var("DEMO_SOURCE").unwrap_or_else(|_| "kucoin".into());
    if want.eq_ignore_ascii_case("synthetic") {
        return std::sync::Arc::new(SyntheticCandleSource::new(symbols));
    }
    match KucoinCandleSource::new() {
        Ok(src) => std::sync::Arc::new(src),
        Err(e) => {
            warn!(error = %e, "kucoin source unavailable — falling back to synthetic");
            std::sync::Arc::new(SyntheticCandleSource::new(symbols))
        }
    }
}
