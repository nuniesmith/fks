//! Rolling-window bridge from the `indicators-ta` batch API to per-tick values.
//!
//! The indicators crate exposes most of its implementations as batch
//! `Indicator::calculate(&[Candle])` functions.  The bot works in streaming
//! mode (one candle at a time), so we keep a fixed-size ring buffer of
//! [`indicators::types::Candle`]s and run the batch calculation on every tick,
//! retaining only the last (current) value.
//!
//! # Why a separate struct?
//!
//! The core [`Indicators`] engine already owns several tightly coupled
//! incremental states (SuperTrend, HMA, Hurst, …).  The indicators below are
//! harder to port to O(1) incremental form but cheap enough at their window
//! sizes to recalculate fully each tick from the ring buffer.
//!
//! # Indicators included
//!
//! | Field         | Type                   | Range      | Interpretation                          |
//! |---------------|------------------------|------------|-----------------------------------------|
//! | `chop`        | `ChoppinessIndex`      | 0–100      | >61.8 choppy, <38.2 trending            |
//! | `vzo`         | `VolumeZoneOscillator` | −100..+100 | volume momentum direction               |
//! | `stc`         | `SchaffTrendCycle`     | 0–100      | >75 overbought, <25 oversold            |
//! | `elder_bull`  | `ElderRayIndex`        | unbounded  | High − EMA; positive = bullish pressure |
//! | `elder_bear`  | `ElderRayIndex`        | unbounded  | Low  − EMA; negative = bearish pressure |

use std::collections::VecDeque;

use indicators::{
    indicator::Indicator,
    momentum::SchaffTrendCycle,
    momentum::schaff_trend_cycle::StcParams,
    types::Candle,
    volatility::choppiness_index::ChopParams,
    volatility::elder_ray_index::ElderRayParams,
    volatility::{ChoppinessIndex, ElderRayIndex},
    volume::VolumeZoneOscillator,
};

// ── Configuration ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct RollingConfig {
    /// Window size for ChoppinessIndex (bars).
    pub chop_period: usize,
    /// Window size for VolumeZoneOscillator (bars).
    pub vzo_period: usize,
    /// Slow EMA for SchaffTrendCycle (bars).
    pub stc_long_ema: usize,
    /// Fast EMA for SchaffTrendCycle (bars).
    pub stc_short_ema: usize,
    /// Stochastic period for SchaffTrendCycle (bars).
    pub stc_stoch_period: usize,
    /// EMA period for ElderRayIndex (bars).
    pub elder_period: usize,
    /// Choppiness threshold above which entries are blocked (default 61.8).
    pub chop_max: f64,
}

impl Default for RollingConfig {
    fn default() -> Self {
        Self {
            chop_period: 14,
            vzo_period: 14,
            stc_long_ema: 26,
            stc_short_ema: 12,
            stc_stoch_period: 10,
            elder_period: 14,
            chop_max: 61.8,
        }
    }
}

impl RollingConfig {
    /// Build a `RollingConfig` from the corresponding fields on
    /// [`crate::settings::BotSettings`]. Used by the brain to keep the
    /// indicator stack and the per-symbol Optuna params in lockstep.
    pub fn from_settings(s: &crate::settings::BotSettings) -> Self {
        Self {
            chop_period: s.chop_period,
            vzo_period: s.vzo_period,
            stc_long_ema: s.stc_long_ema,
            stc_short_ema: s.stc_short_ema,
            stc_stoch_period: s.stc_stoch_period,
            elder_period: s.elder_period,
            chop_max: s.chop_max,
        }
    }
}

// ── Struct ────────────────────────────────────────────────────────────────────

pub struct RollingIndicators {
    cfg: RollingConfig,
    /// Ring buffer sized to the largest window needed across all indicators.
    buf: VecDeque<Candle>,
    buf_cap: usize,

    // ── Cached last values (None until the buffer has filled enough) ──────────
    /// Choppiness Index: >61.8 = choppy/sideways, <38.2 = trending.
    pub chop: Option<f64>,
    /// Volume Zone Oscillator: positive -> buying pressure, negative -> selling.
    pub vzo: Option<f64>,
    /// Schaff Trend Cycle: >75 overbought, <25 oversold.
    pub stc: Option<f64>,
    /// Elder Ray bull power (High - EMA).  Positive and growing = bullish.
    pub elder_bull: Option<f64>,
    /// Elder Ray bear power (Low - EMA).  Negative and shrinking = bearish.
    pub elder_bear: Option<f64>,
}

impl RollingIndicators {
    pub fn new(cfg: RollingConfig) -> Self {
        // Buffer must be at least as long as the greediest indicator.
        // STC needs slow_ema + stoch_period warm-up; others need their period.
        let buf_cap = [
            cfg.chop_period,
            cfg.vzo_period + 1, // VZO needs one extra bar for the first diff
            cfg.stc_long_ema + cfg.stc_stoch_period + 4,
            cfg.elder_period,
        ]
        .into_iter()
        .max()
        .unwrap_or(50);

        Self {
            cfg,
            buf: VecDeque::with_capacity(buf_cap),
            buf_cap,
            chop: None,
            vzo: None,
            stc: None,
            elder_bull: None,
            elder_bear: None,
        }
    }

    pub fn with_defaults() -> Self {
        Self::new(RollingConfig::default())
    }

    /// Feed one candle.  Updates all cached values once the buffer is full enough.
    pub fn update(&mut self, c: &Candle) {
        if self.buf.len() == self.buf_cap {
            self.buf.pop_front();
        }
        self.buf.push_back(c.clone());

        let slice: Vec<Candle> = self.buf.iter().cloned().collect();

        self.chop = self.calc_chop(&slice);
        self.vzo = self.calc_vzo(&slice);
        self.stc = self.calc_stc(&slice);
        (self.elder_bull, self.elder_bear) = self.calc_elder(&slice);
    }

    // ── Private calculators ───────────────────────────────────────────────────

    fn calc_chop(&self, slice: &[Candle]) -> Option<f64> {
        let key = format!("CHOP_{}", self.cfg.chop_period);
        let ind = ChoppinessIndex::new(ChopParams {
            period: self.cfg.chop_period,
        });
        ind.calculate(slice)
            .ok()
            .and_then(|out| out.get(&key).and_then(last_valid))
    }

    fn calc_vzo(&self, slice: &[Candle]) -> Option<f64> {
        let key = format!("vzo_{}", self.cfg.vzo_period);
        let ind = VolumeZoneOscillator::new(self.cfg.vzo_period);
        ind.calculate(slice)
            .ok()
            .and_then(|out| out.get(&key).and_then(last_valid))
    }

    fn calc_stc(&self, slice: &[Candle]) -> Option<f64> {
        let ind = SchaffTrendCycle::new(StcParams {
            short_ema: self.cfg.stc_short_ema,
            long_ema: self.cfg.stc_long_ema,
            stoch_period: self.cfg.stc_stoch_period,
            signal_period: 3,
        });
        ind.calculate(slice)
            .ok()
            .and_then(|out| out.get("STC").and_then(last_valid))
    }

    fn calc_elder(&self, slice: &[Candle]) -> (Option<f64>, Option<f64>) {
        let ind = ElderRayIndex::new(ElderRayParams {
            fast_period: self.cfg.elder_period,
        });
        let Ok(out) = ind.calculate(slice) else {
            return (None, None);
        };
        let bull = out.get("ElderRay_bull").and_then(last_valid);
        let bear = out.get("ElderRay_bear").and_then(last_valid);
        (bull, bear)
    }

    // ── Gate helpers ──────────────────────────────────────────────────────────

    /// Returns `true` when ChoppinessIndex says the market is ranging.
    /// Returns `false` (allow entry) when the value is not yet ready.
    pub fn is_choppy(&self) -> bool {
        self.chop.is_some_and(|v| v > self.cfg.chop_max)
    }

    /// VZO direction: +1 if bullish, -1 if bearish, 0 if not ready.
    pub fn vzo_direction(&self) -> i8 {
        match self.vzo {
            Some(v) if v > 0.0 => 1,
            Some(v) if v < 0.0 => -1,
            _ => 0,
        }
    }

    /// Current STC reading, or `None` until the indicator is warm.
    /// Exposed for the strategy's overbought / oversold entry gate.
    pub const fn stc_value(&self) -> Option<f64> {
        self.stc
    }

    /// Signed Elder Ray bias score.
    /// Positive = bullish pressure, negative = bearish, 0 = neutral/not ready.
    pub const fn elder_bias(&self) -> f64 {
        match (self.elder_bull, self.elder_bear) {
            (Some(bull), Some(bear)) => {
                let b = bull.signum();
                let r = bear.signum();
                // Bull power counts twice; bear is a confirming factor.
                b.mul_add(2.0, r)
            }
            _ => 0.0,
        }
    }
}

// ── Utility ───────────────────────────────────────────────────────────────────

/// Extract the last non-NaN value from a series slice.
fn last_valid(series: &[f64]) -> Option<f64> {
    series.iter().copied().rev().find(|v| !v.is_nan())
}
