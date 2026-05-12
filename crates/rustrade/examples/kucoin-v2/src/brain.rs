//! `SarBrain` — the SAR strategy ported to the rustrade `Brain` trait.
//!
//! Equivalent in behaviour to the v1 `bot/strategy.rs` (post-Apr-21 patch),
//! but expressed as a single trait impl. The framework calls `on_event` once
//! per closed candle; this method does what `plan_candle` + the early gates
//! used to do, and returns a `Decision` instead of calling `execute_sar`
//! directly.
//!
//! Execution is now the framework's job. The brain does *not* place orders.
//! Instead it returns `Decision::buy(conf).with_stop(price)` (or `Sell`,
//! `Close`, `Hold`) and the framework's execution layer:
//!   1. Asks `rustrade-risk::PositionSizer` to convert the size hint into
//!      contracts.
//!   2. Asks `rustrade-risk::CircuitBreaker` whether entries are blocked.
//!   3. Calls the `ExchangeClient` to place the order and the hard stop.
//!   4. Routes the resulting `Fill` back to the brain via `on_fill`.
//!
//! This separation is what makes the same brain code usable by the live
//! bot, the backtest engine, and (eventually) the janus neuromorphic
//! orchestrator without changes.

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use async_trait::async_trait;
use parking_lot::Mutex;

use indicators::{
    CVDTracker, ConfluenceEngine, Indicators, LiquidityProfile, MarketRegime, MarketStructure,
    SignalStreak, VolatilityPercentile,
};
use rustrade_core::{
    Brain, BrainHealth, Decision, Fill, MarketDataEvent, Position, Price, Result, SignalType,
    SizeHint,
};

use crate::settings::BotSettings;

// (Reuse the rolling indicator wrapper from v1 — it's strategy code, not
// framework code, so it stays in the service repo.)
use crate::rolling_indicators::{RollingConfig, RollingIndicators};

/// Per-symbol indicator stack. Owned by `SarBrain` behind a Mutex because the
/// `Brain` trait takes `&self` (so brains can be shared as `Arc<dyn Brain>`).
struct IndicatorStack {
    ind: Indicators,
    liq: LiquidityProfile,
    conf: ConfluenceEngine,
    structure: MarketStructure,
    cvd: CVDTracker,
    vol: VolatilityPercentile,
    regime: MarketRegime,
    streak: SignalStreak,
    rol: RollingIndicators,
    /// Open time (ms) of the most recent fully-closed candle we processed.
    /// Replaces the v1 `last_candle_ts_ms` field; same semantics.
    last_candle_ts_ms: i64,
    /// Bars since the current position opened. Reset on flat → entry transition.
    /// Tracked here (in the brain) because it's strategy state, not framework state.
    bars_since_entry: usize,
    /// Last confirmed signal direction. Used to suppress duplicate same-side entries.
    last_signal: i8,
}

/// The SAR brain. One instance per traded symbol.
///
/// Internally:
/// - `indicators` is `Mutex` because we need `&mut self` access during
///   `Indicators::update`, but the trait gives us `&self`.
/// - `events_processed` and `non_hold_decisions` are atomics so `health()`
///   can read them without locking the indicator stack.
pub struct SarBrain {
    name: String,
    symbol: String,
    settings: Arc<BotSettings>,
    indicators: Mutex<IndicatorStack>,
    events_processed: AtomicU64,
    non_hold_decisions: AtomicU64,
}

impl SarBrain {
    pub fn new(symbol: String, settings: Arc<BotSettings>) -> Self {
        let stack = IndicatorStack {
            ind: Indicators::new(settings.as_indicator_config()),
            liq: LiquidityProfile::new(settings.liq_period, settings.liq_bins),
            conf: ConfluenceEngine::new(
                settings.conf_ema_fast,
                settings.conf_ema_slow,
                settings.conf_ema_trend,
                settings.conf_rsi_len,
                settings.conf_adx_len,
            ),
            structure: MarketStructure::new(settings.struct_swing_len, settings.struct_atr_mult),
            cvd: CVDTracker::new(settings.cvd_slope_bars, settings.cvd_div_lookback),
            vol: VolatilityPercentile::new(settings.vol_pct_window),
            regime: MarketRegime::default(),
            streak: SignalStreak::new(settings.signal_confirm_bars),
            rol: RollingIndicators::new(RollingConfig::from_settings(&settings)),
            last_candle_ts_ms: 0,
            bars_since_entry: 0,
            last_signal: 0,
        };

        Self {
            name: format!("sar-brain[{symbol}]"),
            symbol,
            settings,
            indicators: Mutex::new(stack),
            events_processed: AtomicU64::new(0),
            non_hold_decisions: AtomicU64::new(0),
        }
    }
}

#[async_trait]
impl Brain for SarBrain {
    fn name(&self) -> &str {
        &self.name
    }

    async fn on_event(&self, event: &MarketDataEvent, position: &Position) -> Result<Decision> {
        // Brain only acts on closed candles. Tickers and trades are ignored
        // (they're useful for other brains — VWAP scalpers, microstructure
        // strategies — so the framework still pushes them all through).
        let MarketDataEvent::Candle { candle, symbol, .. } = event else {
            return Ok(Decision::hold());
        };

        // Defensive: a brain instance is bound to one symbol; the framework
        // shouldn't route off-symbol events here, but if it ever does we hold.
        if symbol.0 != self.symbol {
            return Ok(Decision::hold());
        }

        self.events_processed.fetch_add(1, Ordering::Relaxed);

        // ── Indicator update + signal computation (sync, holds the mutex) ──
        let mut stack = self.indicators.lock();

        // Skip duplicate / out-of-order candles (catch-up safety).
        if candle.time <= stack.last_candle_ts_ms {
            return Ok(Decision::hold());
        }
        stack.last_candle_ts_ms = candle.time;

        // Increment bars-held counter *before* this candle's decision so a
        // newly-opened position counts as "1 bar held" by the time the next
        // candle arrives — matches v1 semantics.
        if !position.is_flat() {
            stack.bars_since_entry = stack.bars_since_entry.saturating_add(1);
        } else {
            stack.bars_since_entry = 0;
        }

        let ic = candle_to_indicators_candle(candle);
        let ready = stack.ind.update(&ic);
        stack.liq.update(&ic);
        stack.conf.update(&ic);
        stack.structure.update(&ic);
        stack.cvd.update(&ic);
        if let Some(atr) = stack.ind.atr {
            stack.vol.update(Some(atr));
        }
        stack.rol.update(&ic);

        if !ready {
            return Ok(Decision::hold());
        }

        let (raw, _components) = indicators::compute_signal(
            candle.close,
            &stack.ind,
            &stack.liq,
            &stack.conf,
            &stack.structure,
            &self.settings.as_indicator_config(),
            Some(&stack.cvd),
            Some(&stack.vol),
        );
        let raw_i8 = raw as i8;
        let confirmed = if stack.streak.update(raw) { raw_i8 } else { 0 };

        // Same-side suppression: don't keep firing entries when we're already
        // in the desired direction.
        if confirmed == 0 || confirmed == stack.last_signal {
            return Ok(Decision::hold());
        }

        // ── Brain-side soft gates ──────────────────────────────────────────
        // (The framework also has a risk layer with the circuit breaker and
        // session loss cap — those live in `rustrade-risk`, not here. These
        // gates are signal-quality filters that only the brain has the
        // context to evaluate.)
        let s = &self.settings;
        let vol_pct = stack.vol.vol_pct;
        if vol_pct < s.min_vol_pct {
            tracing::debug!(symbol = %self.symbol, vol_pct, "vol gate: blocked");
            return Ok(Decision::hold());
        }
        if stack.rol.is_choppy() {
            tracing::debug!(symbol = %self.symbol, "chop gate: blocked");
            return Ok(Decision::hold());
        }
        let vzo_dir = stack.rol.vzo_direction();
        if vzo_dir != 0 && vzo_dir != confirmed {
            tracing::debug!(symbol = %self.symbol, "vzo gate: blocked");
            return Ok(Decision::hold());
        }
        let elder_bias = stack.rol.elder_bias();
        if elder_bias != 0.0 && (elder_bias.signum() as i8) != confirmed {
            tracing::debug!(symbol = %self.symbol, "elder gate: blocked");
            return Ok(Decision::hold());
        }
        // STC extreme-entry gate (the Apr 21 patch).
        if let Some(stc_val) = stack.rol.stc_value() {
            if confirmed == 1 && stc_val >= s.stc_long_max {
                tracing::info!(symbol = %self.symbol, stc = stc_val, "stc gate: overbought — long blocked");
                return Ok(Decision::hold());
            }
            if confirmed == -1 && stc_val <= s.stc_short_min {
                tracing::info!(symbol = %self.symbol, stc = stc_val, "stc gate: oversold — short blocked");
                return Ok(Decision::hold());
            }
        }

        // Min-hold gate (don't flip an existing position too early).
        if !position.is_flat() && stack.bars_since_entry < s.min_hold_candles {
            tracing::debug!(symbol = %self.symbol, "min-hold gate: blocked");
            return Ok(Decision::hold());
        }

        // ── Build the decision ─────────────────────────────────────────────
        let atr = stack.ind.atr.unwrap_or(0.0);
        let stop_distance = s.stop_atr_mult * atr;
        let stop_price = if confirmed == 1 {
            Price(candle.close - stop_distance)
        } else {
            Price(candle.close + stop_distance)
        };

        // Update last_signal *before* releasing the lock so a duplicate
        // candle delivery (catch-up) doesn't double-fire.
        stack.last_signal = confirmed;
        // Reset the bars counter — the new entry restarts the clock. The
        // framework will confirm-or-deny via on_fill; if the order is
        // rejected, on_fill is never called and the next candle still sees
        // bars_since_entry == 0 (correct: there's no position to count).
        stack.bars_since_entry = 0;
        drop(stack);

        let signal = if confirmed == 1 {
            SignalType::Buy
        } else {
            SignalType::Sell
        };
        self.non_hold_decisions.fetch_add(1, Ordering::Relaxed);

        Ok(Decision {
            signal,
            confidence: 1.0,
            // The kucoin strategy uses fixed-USD margin sizing per trade.
            // The framework's PositionSizer translates this hint into
            // contracts using the current price + leverage.
            size_hint: SizeHint::NotionalUsd(s.trade_size_usd * f64::from(s.leverage)),
            stop_price: (atr > 0.0).then_some(stop_price),
            take_profit_price: None,
            metadata: serde_json::json!({
                "atr": atr,
                "vol_pct": vol_pct,
                "vzo_dir": vzo_dir,
                "elder_bias": elder_bias,
                "bars_held_at_entry": 0,
            }),
        })
    }

    async fn on_fill(&self, fill: &Fill) -> Result<()> {
        if fill.symbol != self.symbol {
            return Ok(());
        }
        // Reset our bar counter on the *first* fill of a new position.
        // Subsequent partial-fills of the same order are handled by the
        // framework — we only react to the position transition.
        let mut stack = self.indicators.lock();
        stack.bars_since_entry = 0;
        // Note: we do NOT mutate last_signal here. last_signal already
        // reflects our *intent* from the candle that produced this fill.
        // If the fill arrived for an order placed in error (e.g. external
        // tooling), on_position_change is the right hook — see below.
        drop(stack);

        tracing::info!(
            symbol = %self.symbol,
            order_id = %fill.order_id,
            side = ?fill.side,
            price = %fill.price,
            size = %fill.size,
            fee = fill.fee,
            "brain saw fill"
        );
        Ok(())
    }

    async fn on_position_change(&self, symbol: &str, position: &Position) -> Result<()> {
        if symbol != self.symbol {
            return Ok(());
        }
        // If the exchange reports flat (e.g. our hard stop fired, or an
        // external close happened) clear our tracked signal so the next
        // candle can fire a fresh entry. Mirrors the v1 reconciliation
        // logic in `private_ws_task::PositionChange`.
        if position.is_flat() {
            let mut stack = self.indicators.lock();
            stack.last_signal = 0;
            stack.bars_since_entry = 0;
        }
        Ok(())
    }

    async fn health(&self) -> BrainHealth {
        let stack = self.indicators.lock();
        BrainHealth {
            healthy: stack.ind.atr.is_some(), // ATR readiness == warmed up
            events_processed: self.events_processed.load(Ordering::Relaxed),
            non_hold_decisions: self.non_hold_decisions.load(Ordering::Relaxed),
            details: serde_json::json!({
                "symbol": self.symbol,
                "last_candle_ts_ms": stack.last_candle_ts_ms,
                "bars_since_entry": stack.bars_since_entry,
                "last_signal": stack.last_signal,
            }),
        }
    }
}

// ── Conversion shim ──────────────────────────────────────────────────────────
// rustrade-core's Candle and indicators-ta's Candle have the same shape but
// are nominally different types (one is "framework", one is "math library").
// The conversion is free at runtime — it's the same f64 fields.
fn candle_to_indicators_candle(c: &rustrade_core::Candle) -> indicators::types::Candle {
    indicators::types::Candle {
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
    }
}
