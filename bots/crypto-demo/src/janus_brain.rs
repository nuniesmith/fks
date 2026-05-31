//! `JanusBrain` — a `rustrade::Brain` that delegates the decision to **janus**.
//!
//! This is the janus ↔ rustrade tie-in: instead of deciding locally (like
//! [`crate::brain::EmaCrossBrain`]), this brain computes indicator features
//! from `indicators-ta`, POSTs them to janus's signal API, and maps janus's
//! reply onto a rustrade [`Decision`]. The framework wiring around it
//! (candle pollers, supervisor, risk gate, paper exchange, metrics) is
//! identical — only the brain changes.
//!
//! ```text
//!   candle ──► JanusBrain ──(EMA/RSI/ATR via indicators-ta)──► HTTP POST
//!                                                  │
//!                            janus /api/v1/signals/generate (port 8080)
//!                                                  │  TradingSignal
//!                                                  ▼
//!                              SignalType → rustrade::Decision
//! ```
//!
//! Resilience: if janus is unreachable or returns no signal, the brain holds
//! (never throws) so a long demo run survives janus restarts. Set
//! `JANUS_HTTP_URL` to point at the janus forward service
//! (default `http://localhost:8080`).

use std::collections::HashMap;
use std::sync::Mutex;

use async_trait::async_trait;
use indicators::{ATR, EMA};
use rustrade::{Brain, BrainHealth, Decision, MarketDataEvent, Position, Price, Result};
use serde::{Deserialize, Serialize};
use tracing::{debug, warn};

use crate::metrics;

// ── Wire types (mirror janus services/forward/src/api/server.rs) ──────────────

/// Request body for `POST /api/v1/signals/generate`.
#[derive(Debug, Serialize)]
struct GenerateSignalRequest {
    symbol: String,
    timeframe: String,
    analysis: IndicatorAnalysisDto,
    current_price: f64,
    enable_ml: bool,
}

/// Indicator features janus consumes. Field names match janus exactly.
#[derive(Debug, Default, Serialize)]
struct IndicatorAnalysisDto {
    ema_fast: Option<f64>,
    ema_slow: Option<f64>,
    ema_cross: f64,
    rsi: Option<f64>,
    rsi_signal: f64,
    macd_line: Option<f64>,
    macd_signal: Option<f64>,
    macd_histogram: Option<f64>,
    macd_cross: f64,
    bb_upper: Option<f64>,
    bb_middle: Option<f64>,
    bb_lower: Option<f64>,
    bb_position: f64,
    atr: Option<f64>,
    trend_strength: f64,
    volatility: f64,
}

/// Response body from `/api/v1/signals/generate`.
#[derive(Debug, Deserialize)]
struct SignalResponse {
    signal: Option<TradingSignalDto>,
    #[serde(default)]
    filtered: bool,
    #[serde(default)]
    processing_time_ms: f64,
}

#[derive(Debug, Deserialize)]
struct TradingSignalDto {
    /// janus serialises this via `{:?}` → "StrongBuy" / "Buy" / "Hold" /
    /// "Sell" / "StrongSell". We also accept the SCREAMING_SNAKE forms.
    signal_type: String,
    #[serde(default)]
    confidence: f64,
    #[serde(default)]
    stop_loss: Option<f64>,
    #[serde(default)]
    take_profit: Option<f64>,
}

/// Normalised janus decision direction.
#[derive(Clone, Copy, PartialEq)]
enum JanusSide {
    Buy,
    Sell,
    Hold,
}

fn parse_signal_type(s: &str) -> JanusSide {
    match s.to_ascii_lowercase().replace(['_', '-'], "").as_str() {
        "buy" | "strongbuy" => JanusSide::Buy,
        "sell" | "strongsell" => JanusSide::Sell,
        _ => JanusSide::Hold,
    }
}

// ── Per-symbol indicator state ────────────────────────────────────────────────

struct SymbolState {
    fast: EMA,
    slow: EMA,
    atr: ATR,
    /// Last side janus advised, to avoid re-emitting the same direction.
    last_side: JanusSide,
}

impl SymbolState {
    fn new(cfg: &JanusBrainConfig) -> Self {
        Self {
            fast: EMA::new(cfg.fast_period),
            slow: EMA::new(cfg.slow_period),
            atr: ATR::new(cfg.atr_period),
            last_side: JanusSide::Hold,
        }
    }
}

/// Configuration for the janus-backed brain.
#[derive(Debug, Clone)]
pub struct JanusBrainConfig {
    pub fast_period: usize,
    pub slow_period: usize,
    pub atr_period: usize,
    pub timeframe: String,
    /// Minimum confidence janus must report before we act.
    pub min_confidence: f64,
}

impl Default for JanusBrainConfig {
    fn default() -> Self {
        Self {
            fast_period: 9,
            slow_period: 21,
            atr_period: 14,
            timeframe: "1m".into(),
            min_confidence: 0.5,
        }
    }
}

/// A brain that asks janus for the decision on each closed candle.
pub struct JanusBrain {
    name: String,
    cfg: JanusBrainConfig,
    base_url: String,
    http: reqwest::Client,
    state: Mutex<HashMap<String, SymbolState>>,
    events: Mutex<u64>,
    signals: Mutex<u64>,
    errors: Mutex<u64>,
}

impl JanusBrain {
    /// Build the brain. `base_url` is the janus forward service, e.g.
    /// `http://localhost:8080` (read from `JANUS_HTTP_URL`).
    pub fn new(
        name: impl Into<String>,
        cfg: JanusBrainConfig,
        base_url: impl Into<String>,
    ) -> Self {
        let http = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(3))
            .build()
            .expect("reqwest client");
        Self {
            name: name.into(),
            cfg,
            base_url: base_url.into(),
            http,
            state: Mutex::new(HashMap::new()),
            events: Mutex::new(0),
            signals: Mutex::new(0),
            errors: Mutex::new(0),
        }
    }

    /// POST the analysis to janus; `Ok(None)` means "no actionable signal".
    async fn ask_janus(
        &self,
        symbol: &str,
        price: f64,
        analysis: IndicatorAnalysisDto,
    ) -> std::result::Result<Option<TradingSignalDto>, reqwest::Error> {
        let url = format!("{}/api/v1/signals/generate", self.base_url);
        let req = GenerateSignalRequest {
            symbol: symbol.to_string(),
            timeframe: self.cfg.timeframe.clone(),
            analysis,
            current_price: price,
            enable_ml: false,
        };
        let resp: SignalResponse = self
            .http
            .post(&url)
            .json(&req)
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;
        debug!(
            symbol,
            filtered = resp.filtered,
            ms = resp.processing_time_ms,
            "janus replied"
        );
        Ok(resp.signal)
    }
}

#[async_trait]
impl Brain for JanusBrain {
    fn name(&self) -> &str {
        &self.name
    }

    async fn on_event(&self, event: &MarketDataEvent, _position: &Position) -> Result<Decision> {
        let (symbol, candle) = match event {
            MarketDataEvent::Candle { symbol, candle, .. } => (symbol, candle),
            _ => return Ok(Decision::hold()),
        };

        *self.events.lock().unwrap() += 1;

        // Update indicators and snapshot the feature vector under the lock,
        // then release it before the await (HTTP) — Brain::on_event is async
        // and the MutexGuard isn't Send.
        let (analysis, atr_val, prev_side) = {
            let mut map = self.state.lock().unwrap();
            let st = map
                .entry(symbol.0.clone())
                .or_insert_with(|| SymbolState::new(&self.cfg));

            st.fast.update(candle.close);
            st.slow.update(candle.close);
            st.atr.update(candle.high, candle.low, candle.close);

            if !st.fast.is_ready() || !st.slow.is_ready() {
                return Ok(Decision::hold());
            }

            let fast = st.fast.value();
            let slow = st.slow.value();
            let atr = if st.atr.is_ready() {
                st.atr.value()
            } else {
                0.0
            };
            let ema_cross = (fast - slow).signum();

            let analysis = IndicatorAnalysisDto {
                ema_fast: Some(fast),
                ema_slow: Some(slow),
                ema_cross,
                atr: if atr > 0.0 { Some(atr) } else { None },
                // Rough volatility proxy = ATR as a fraction of price.
                volatility: if candle.close > 0.0 {
                    atr / candle.close
                } else {
                    0.0
                },
                trend_strength: ema_cross,
                ..Default::default()
            };
            (analysis, atr, st.last_side)
        };

        // Ask janus. On any transport error, hold (don't kill the run).
        let signal = match self.ask_janus(&symbol.0, candle.close, analysis).await {
            Ok(s) => s,
            Err(e) => {
                *self.errors.lock().unwrap() += 1;
                warn!(symbol = %symbol.0, error = %e, "janus request failed — holding");
                return Ok(Decision::hold());
            }
        };

        let Some(sig) = signal else {
            return Ok(Decision::hold());
        };

        let side = parse_signal_type(&sig.signal_type);
        if side == JanusSide::Hold || sig.confidence < self.cfg.min_confidence {
            return Ok(Decision::hold());
        }
        if side == prev_side {
            return Ok(Decision::hold()); // already on this side
        }

        // Record the new side.
        if let Some(st) = self.state.lock().unwrap().get_mut(&symbol.0) {
            st.last_side = side;
        }
        metrics::record_signal();
        *self.signals.lock().unwrap() += 1;

        // Prefer janus's own stop; fall back to a 2×ATR stop.
        let stop = sig.stop_loss.unwrap_or_else(|| {
            let dist = if atr_val > 0.0 {
                atr_val * 2.0
            } else {
                candle.close * 0.01
            };
            match side {
                JanusSide::Buy => candle.close - dist,
                _ => candle.close + dist,
            }
        });

        let conf = sig.confidence.clamp(0.0, 1.0);
        tracing::info!(
            symbol = %symbol.0, signal = %sig.signal_type, confidence = conf,
            close = candle.close, "janus signal → decision"
        );

        let mut decision = match side {
            JanusSide::Buy => Decision::buy(conf).with_stop(Price(stop)),
            _ => Decision::sell(conf).with_stop(Price(stop)),
        };
        if let Some(tp) = sig.take_profit {
            decision = decision.with_take_profit(Price(tp));
        }
        Ok(decision)
    }

    async fn health(&self) -> BrainHealth {
        let events = *self.events.lock().unwrap();
        let signals = *self.signals.lock().unwrap();
        let errors = *self.errors.lock().unwrap();
        BrainHealth {
            // Unhealthy only if every request so far has failed (janus down).
            healthy: events == 0 || errors < events,
            events_processed: events,
            non_hold_decisions: signals,
            details: serde_json::json!({
                "kind": "janus",
                "base_url": self.base_url,
                "janus_errors": errors,
            }),
        }
    }
}
