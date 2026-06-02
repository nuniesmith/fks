//! `JanusBrain` — a `rustrade::Brain` that delegates the decision to **janus**.
//!
//! This is the janus ↔ rustrade tie-in: instead of deciding locally (like
//! [`crate::brain::EmaCrossBrain`]), this brain computes indicator features
//! from `indicators-ta`, POSTs them to janus's signal API, and maps janus's
//! reply onto a rustrade [`Decision`]. The framework wiring around it
//! (candle pollers, supervisor, risk gate, paper exchange, metrics) is
//! identical — only the brain changes.
//!
//! **v2 — risk-verdict aware.** Beyond the directional signal, the brain routes
//! it through janus's **risk engine** instead of acting on the raw signal:
//!
//! ```text
//!   candle ─► JanusBrain ─(EMA/ATR)─► POST /api/v1/signals/generate ─► direction+conf
//!                                                  │
//!                 POST /api/v1/risk/validate  ◄────┤   (veto? → Hold)
//!                 POST /api/v1/risk/calculate/position-size  ◄─ (risk-sized quantity)
//!                                                  ▼
//!                   rustrade::Decision { side, SizeHint::Quantity(janus qty), stop, tp }
//!
//!   on_fill ─► POST /api/v1/risk/portfolio/positions   (feed janus's portfolio + affinity)
//! ```
//!
//! So janus's risk layer is the authority on **whether** to trade (validate) and
//! **how big** (position-size), and it sees realised fills. Toggle with
//! [`JanusBrainConfig::use_risk_engine`].
//!
//! Resilience: every janus call **fails open** — if the signal or risk API is
//! unreachable the brain holds or falls back to framework sizing (never throws),
//! so a long demo run survives janus being down or partial. Set `JANUS_HTTP_URL`
//! to the forward service (default `http://localhost:8080`).

use std::collections::HashMap;
use std::sync::Mutex;

use async_trait::async_trait;
use indicators::{ATR, EMA};
use rustrade::{
    Brain, BrainHealth, Decision, Fill, MarketDataEvent, Position, Price, Result, SizeHint, Volume,
};
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

// ── Risk-API wire types (mirror janus services/forward/src/api/risk_rest.rs) ──
// v2: instead of acting on the raw signal, the brain asks janus's risk engine
// to *validate* the signal and *size* the position, then reports fills back so
// janus's portfolio + affinity stay current.

#[derive(Debug, Serialize)]
struct SignalDto {
    symbol: String,
    signal_type: String, // "Buy" / "Sell" / "Hold"
    timeframe: String,
    confidence: f64,
    entry_price: Option<f64>,
    stop_loss: Option<f64>,
    take_profit: Option<f64>,
}

#[derive(Debug, Serialize)]
struct MarketDataDto {
    current_price: f64,
    atr: Option<f64>,
    support: Option<f64>,
    resistance: Option<f64>,
    volatility: Option<f64>,
    recent_high: Option<f64>,
    recent_low: Option<f64>,
}

#[derive(Debug, Serialize)]
struct PositionDto {
    symbol: String,
    entry_price: f64,
    quantity: f64,
    side: String, // "Long" / "Short"
    stop_loss: Option<f64>,
    take_profit: Option<f64>,
    position_value: f64,
    risk_amount: Option<f64>,
}

#[derive(Debug, Serialize)]
struct ValidateSignalRequest {
    signal: SignalDto,
}

#[derive(Debug, Deserialize)]
struct ValidateSignalResponse {
    is_valid: bool,
    #[serde(default)]
    validation_errors: Vec<String>,
    #[serde(default)]
    warnings: Vec<String>,
}

#[derive(Debug, Serialize)]
struct CalculatePositionSizeRequest {
    signal: SignalDto,
    market_data: MarketDataDto,
    sizing_method: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PositionSizeResponse {
    quantity: f64,
    #[serde(default)]
    position_value: f64,
    #[serde(default)]
    risk_amount: f64,
}

#[derive(Debug, Serialize)]
struct AddPositionRequest {
    position: PositionDto,
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
    /// v2: route the directional signal through janus's **risk engine**
    /// (`/risk/validate` + `/risk/calculate/position-size`) and report fills to
    /// its portfolio (`/risk/portfolio/positions`). When janus's risk API is
    /// unreachable the brain degrades gracefully to v1 behaviour (direct sizing
    /// + the signal's own stop), so a demo run survives janus being partial.
    pub use_risk_engine: bool,
}

impl Default for JanusBrainConfig {
    fn default() -> Self {
        Self {
            fast_period: 9,
            slow_period: 21,
            atr_period: 14,
            timeframe: "1m".into(),
            min_confidence: 0.5,
            use_risk_engine: true,
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

    /// Ask janus's risk engine to validate the signal. `Ok(true)` = approved (or
    /// the endpoint is absent/old and returns nothing parseable — fail open so a
    /// missing risk service doesn't silently halt trading).
    async fn risk_validate(&self, signal: &SignalDto) -> std::result::Result<bool, reqwest::Error> {
        let url = format!("{}/api/v1/risk/validate", self.base_url);
        let resp: ValidateSignalResponse = self
            .http
            .post(&url)
            .json(&ValidateSignalRequest {
                signal: signal.clone_shallow(),
            })
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;
        if !resp.is_valid {
            warn!(
                errors = ?resp.validation_errors,
                warnings = ?resp.warnings,
                "janus risk vetoed the signal"
            );
        }
        Ok(resp.is_valid)
    }

    /// Ask janus's risk engine to size the position. Returns the quantity
    /// (base/contract units) it recommends, or `None` if it declines / errors.
    async fn risk_size(
        &self,
        signal: &SignalDto,
        market: MarketDataDto,
    ) -> std::result::Result<Option<f64>, reqwest::Error> {
        let url = format!("{}/api/v1/risk/calculate/position-size", self.base_url);
        let resp: PositionSizeResponse = self
            .http
            .post(&url)
            .json(&CalculatePositionSizeRequest {
                signal: signal.clone_shallow(),
                market_data: market,
                sizing_method: None,
            })
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;
        debug!(
            quantity = resp.quantity,
            notional = resp.position_value,
            risk = resp.risk_amount,
            "janus risk sized the position"
        );
        Ok((resp.quantity > 0.0).then_some(resp.quantity))
    }

    /// Report an opened position to janus's portfolio so its account-level risk
    /// + affinity learning see it. Best-effort — logged, never fatal.
    async fn report_position(&self, position: PositionDto) {
        let url = format!("{}/api/v1/risk/portfolio/positions", self.base_url);
        if let Err(e) = self
            .http
            .post(&url)
            .json(&AddPositionRequest { position })
            .send()
            .await
            .and_then(reqwest::Response::error_for_status)
        {
            debug!(error = %e, "janus portfolio position report failed (non-fatal)");
        }
    }
}

impl SignalDto {
    /// Cheap clone for re-sending the same signal to multiple risk endpoints.
    fn clone_shallow(&self) -> Self {
        Self {
            symbol: self.symbol.clone(),
            signal_type: self.signal_type.clone(),
            timeframe: self.timeframe.clone(),
            confidence: self.confidence,
            entry_price: self.entry_price,
            stop_loss: self.stop_loss,
            take_profit: self.take_profit,
        }
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

        let conf = sig.confidence.clamp(0.0, 1.0);

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

        // ── v2: route through janus's risk engine (validate + size) ─────
        // Degrades gracefully: a transport error fails open (don't halt on a
        // blip); a reachable veto holds; sizing falls back to the framework's.
        let mut size_hint = SizeHint::Default;
        if self.cfg.use_risk_engine {
            let signal_dto = SignalDto {
                symbol: symbol.0.clone(),
                signal_type: if side == JanusSide::Buy {
                    "Buy"
                } else {
                    "Sell"
                }
                .into(),
                timeframe: self.cfg.timeframe.clone(),
                confidence: conf,
                entry_price: Some(candle.close),
                stop_loss: Some(stop),
                take_profit: sig.take_profit,
            };
            match self.risk_validate(&signal_dto).await {
                Ok(false) => return Ok(Decision::hold()), // janus risk vetoed
                Ok(true) => {}
                Err(e) => {
                    *self.errors.lock().unwrap() += 1;
                    warn!(error = %e, "risk validate failed — proceeding without veto");
                }
            }
            let market = MarketDataDto {
                current_price: candle.close,
                atr: (atr_val > 0.0).then_some(atr_val),
                volatility: (candle.close > 0.0).then(|| atr_val / candle.close),
                support: None,
                resistance: None,
                recent_high: None,
                recent_low: None,
            };
            match self.risk_size(&signal_dto, market).await {
                Ok(Some(qty)) => size_hint = SizeHint::Quantity(Volume(qty)),
                Ok(None) => {}
                Err(e) => {
                    *self.errors.lock().unwrap() += 1;
                    warn!(error = %e, "risk size failed — default sizing");
                }
            }
        }

        // Record + count only now that the risk engine didn't veto.
        if let Some(st) = self.state.lock().unwrap().get_mut(&symbol.0) {
            st.last_side = side;
        }
        metrics::record_signal();
        *self.signals.lock().unwrap() += 1;

        tracing::info!(
            symbol = %symbol.0, signal = %sig.signal_type, confidence = conf,
            close = candle.close, ?size_hint, "janus signal → risk-checked decision"
        );

        let mut decision = match side {
            JanusSide::Buy => Decision::buy(conf),
            _ => Decision::sell(conf),
        }
        .with_stop(Price(stop))
        .with_size_hint(size_hint);
        if let Some(tp) = sig.take_profit {
            decision = decision.with_take_profit(Price(tp));
        }
        Ok(decision)
    }

    async fn on_fill(&self, fill: &Fill) -> Result<()> {
        // v2: report the fill to janus's portfolio so its account-level risk +
        // affinity learning see realised exposure. Best-effort.
        if !self.cfg.use_risk_engine {
            return Ok(());
        }
        let (side, qty) = match fill.side {
            rustrade::Side::Buy => ("Long", fill.size.value()),
            rustrade::Side::Sell => ("Short", fill.size.value()),
        };
        let price = fill.price.value();
        self.report_position(PositionDto {
            symbol: fill.symbol.as_str().to_string(),
            entry_price: price,
            quantity: qty,
            side: side.to_string(),
            stop_loss: None,
            take_profit: None,
            position_value: price * qty,
            risk_amount: None,
        })
        .await;
        Ok(())
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
