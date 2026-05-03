//! Signal aggregator — combines all 11 indicator layers into a single trading signal.
//!
//! pure math, no exchange I/O.
//!
//! # Usage
//! ```rust,ignore
//! use indicators::{compute_signal, SignalStreak, IndicatorConfig};
//!
//! let cfg = IndicatorConfig::default();
//! let mut streak = SignalStreak::new(cfg.signal_confirm_bars);
//!
//! // per-candle:
//! let (raw, components) = compute_signal(close, &ind, &liq, &conf, &ms, &cfg, Some(&cvd), Some(&vol));
//! if streak.update(raw) { /* confirmed signal */ }
//! ```

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::indicator_config::IndicatorConfig;
use crate::registry::param_usize;
use crate::signal::confluence::{ConfluenceEngine, ConfluenceParams};
use crate::signal::cvd::{CVDTracker, CvdParams};
use crate::signal::engine::Indicators;
use crate::signal::liquidity::{LiquidityParams, LiquidityProfile};
use crate::signal::structure::{MarketStructure, StructureParams};
use crate::signal::vol_regime::VolatilityPercentile;
use crate::types::Candle;

// ── Indicator wrapper ─────────────────────────────────────────────────────────

/// Batch `Indicator` adapter for the full signal pipeline.
///
/// Constructs all sub-components with their default configurations, replays the
/// candle slice through each, calls [`compute_signal`] per bar, and emits:
/// - `signal`  — `+1` long, `-1` short, `0` neutral
/// - `bull_score` / `bear_score` — raw confluence scores
///
/// For production use, prefer constructing the sub-components individually with
/// tuned configs and calling `compute_signal` directly; this adapter is intended
/// for backtesting and registry-driven workflows.
#[derive(Debug, Clone)]
pub struct SignalIndicator {
    pub engine_cfg: IndicatorConfig,
    pub conf_params: ConfluenceParams,
    pub liq_params: LiquidityParams,
    pub struct_params: StructureParams,
    pub cvd_params: CvdParams,
    pub signal_confirm_bars: usize,
}

impl SignalIndicator {
    pub fn new(
        engine_cfg: IndicatorConfig,
        conf_params: ConfluenceParams,
        liq_params: LiquidityParams,
        struct_params: StructureParams,
        cvd_params: CvdParams,
        signal_confirm_bars: usize,
    ) -> Self {
        Self {
            engine_cfg,
            conf_params,
            liq_params,
            struct_params,
            cvd_params,
            signal_confirm_bars,
        }
    }
    pub fn with_defaults() -> Self {
        Self::new(
            IndicatorConfig::default(),
            ConfluenceParams::default(),
            LiquidityParams::default(),
            StructureParams::default(),
            CvdParams::default(),
            3,
        )
    }
}

impl Indicator for SignalIndicator {
    fn name(&self) -> &'static str {
        "Signal"
    }
    fn required_len(&self) -> usize {
        // Engine training_period is the dominant warm-up requirement.
        self.engine_cfg
            .training_period
            .max(self.conf_params.trend_len + 1)
            .max(self.liq_params.period)
            .max(self.cvd_params.div_lookback + 1)
            .max(self.struct_params.swing_len * 4 + 10)
    }
    fn required_columns(&self) -> &[&'static str] {
        &["open", "high", "low", "close", "volume"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;
        let cp = &self.conf_params;
        let lp = &self.liq_params;
        let sp = &self.struct_params;

        let mut ind = Indicators::new(self.engine_cfg.clone());
        let mut liq = LiquidityProfile::new(lp.period, lp.n_bins);
        let mut conf = ConfluenceEngine::new(
            cp.fast_len,
            cp.slow_len,
            cp.trend_len,
            cp.rsi_len,
            cp.adx_len,
        );
        let mut ms = MarketStructure::new(sp.swing_len, sp.atr_mult);
        let mut cvd = CVDTracker::new(self.cvd_params.slope_bars, self.cvd_params.div_lookback);
        let mut vol = VolatilityPercentile::new(100);
        let cfg = IndicatorConfig::default();
        let mut streak = SignalStreak::new(self.signal_confirm_bars);

        let n = candles.len();
        let mut signal_out = vec![f64::NAN; n];
        let mut bull_out = vec![f64::NAN; n];
        let mut bear_out = vec![f64::NAN; n];

        for (i, c) in candles.iter().enumerate() {
            ind.update(c);
            liq.update(c);
            conf.update(c);
            ms.update(c);
            cvd.update(c);
            vol.update(ind.atr);

            let (raw, comps) = compute_signal(
                c.close,
                &ind,
                &liq,
                &conf,
                &ms,
                &cfg,
                Some(&cvd),
                Some(&vol),
            );
            let confirmed = if streak.update(raw) { raw } else { 0 };
            signal_out[i] = confirmed as f64;
            bull_out[i] = comps.bull_score;
            bear_out[i] = comps.bear_score;
        }
        Ok(IndicatorOutput::from_pairs([
            ("signal", signal_out),
            ("signal_bull_score", bull_out),
            ("signal_bear_score", bear_out),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let signal_confirm_bars = param_usize(params, "confirm_bars", 3)?;
    Ok(Box::new(SignalIndicator::new(
        IndicatorConfig::default(),
        ConfluenceParams::default(),
        LiquidityParams::default(),
        StructureParams::default(),
        CvdParams::default(),
        signal_confirm_bars,
    )))
}

// ── Signal components ─────────────────────────────────────────────────────────

/// All per-layer votes and supporting diagnostic values.
#[derive(Debug, Clone)]
pub struct SignalComponents {
    // Votes: +1 = bull, -1 = bear, 0 = neutral
    pub v_vwap: i8,
    pub v_ema: i8,
    pub v_st: i8,
    pub v_ts: i8,
    pub v_liq: i8,
    pub v_conf_bull: i8,
    pub v_conf_bear: i8,
    pub v_struct: i8,
    pub v_cvd: i8,
    pub v_ao: i8,
    pub v_hurst: i8,
    pub v_accel_bull: i8,
    pub v_accel_bear: i8,
    // Supporting values (for logging / debugging)
    pub hurst: f64,
    pub price_accel: f64,
    pub bull_score: f64,
    pub bear_score: f64,
    pub conf_min_adj: f64,
    pub liq_imbalance: f64,
    pub liq_buy_pct: f64,
    pub poc: Option<f64>,
    pub struct_bias: i8,
    pub fib618: Option<f64>,
    pub fib_zone: &'static str,
    pub fib_ok: bool,
    pub bos: bool,
    pub choch: bool,
    pub ts_norm: f64,
    pub dominance: f64,
    pub cvd_slope: Option<f64>,
    pub cvd_div: i8,
    pub ao: f64,
    pub ao_rising: bool,
    pub wr_pct: f64,
    pub mom_pct: f64,
    pub wave_ok_long: bool,
    pub wave_ok_short: bool,
    pub mom_ok_long: bool,
    pub mom_ok_short: bool,
    pub vol_pct: Option<f64>,
    pub vol_regime: Option<&'static str>,
}

// ── compute_signal ────────────────────────────────────────────────────────────

/// Aggregate all layers into a single trading signal.
///
/// Returns `(signal, components)`:
/// - `1`  → long
/// - `-1` → short
/// - `0`  → neutral / no trade
pub fn compute_signal(
    close: f64,
    ind: &Indicators,
    liq: &LiquidityProfile,
    conf: &ConfluenceEngine,
    ms: &MarketStructure,
    cfg: &IndicatorConfig,
    cvd: Option<&CVDTracker>,
    vol: Option<&VolatilityPercentile>,
) -> (i32, SignalComponents) {
    if ind.vwap.is_none() || ind.ema.is_none() || ind.st.is_none() {
        return (0, empty_components(ind, liq, conf, ms, cvd, vol));
    }

    let vwap = ind.vwap.unwrap();
    let ema = ind.ema.unwrap();

    // ── Layer votes ───────────────────────────────────────────────────────────
    let v1 = if close > vwap { 1_i8 } else { -1 }; // L1 VWAP
    let v2 = if close > ema { 1 } else { -1 }; // L2 EMA
    let v3 = if ind.st_dir_pub == -1 { -1 } else { 1 }; // L3 SuperTrend
    let v4 = if ind.ts_bullish { 1 } else { -1 }; // L4 TrendSpeed
    let v5 = if liq.bullish() { 1 } else { -1 }; // L5 Liquidity

    let conf_adj = vol.map_or(1.0, |v| v.conf_adj);
    let adj_min = cfg.conf_min_score * conf_adj;
    let v6_bull = if conf.bull_score >= adj_min { 1_i8 } else { -1 };
    let v6_bear = if conf.bear_score >= adj_min { 1_i8 } else { -1 };

    let v7 = ms.bias; // L7 Market Structure

    let v8: i8 = cvd.map_or(0, |c| {
        if c.divergence != 0 {
            c.divergence
        } else if c.bullish {
            1
        } else {
            -1
        }
    }); // L8 CVD

    let v9: i8 = if ind.highs.len() >= 34 {
        if ind.ao_rising { 1 } else { -1 }
    } else {
        0
    }; // L9 AO

    let v10: i8 = if (ind.hurst - 0.5).abs() < 0.005 {
        0
    } else if ind.hurst >= cfg.hurst_threshold {
        1
    } else {
        -1
    }; // L10 Hurst

    let (v11_bull, v11_bear): (i8, i8) = if ind.price_accel.abs() < 0.005 {
        (0, 0)
    } else {
        (
            if ind.price_accel > 0.0 { 1 } else { -1 },
            if ind.price_accel < 0.0 { 1 } else { -1 },
        )
    }; // L11 PriceAccel

    // Fibonacci zone gates
    let fib_ok_long = !cfg.fib_zone_enabled || ms.in_discount || ms.fib500.is_none();
    let fib_ok_short = !cfg.fib_zone_enabled || ms.in_premium || ms.fib500.is_none();

    // ── Signal logic ──────────────────────────────────────────────────────────
    let (bull, bear) = match cfg.signal_mode.as_str() {
        "strict" => {
            let bull = v1 == 1
                && v2 == 1
                && v3 == -1
                && v4 == 1
                && v5 == 1
                && v6_bull == 1
                && v7 == 1
                && fib_ok_long
                && (v8 == 1 || v8 == 0);
            let bear = v1 == -1
                && v2 == -1
                && v3 == 1
                && v4 == -1
                && v5 == -1
                && v6_bear == 1
                && v7 == -1
                && fib_ok_short
                && (v8 == -1 || v8 == 0);
            (bull, bear)
        }
        "majority" => {
            let core_bull = v1 == 1 && v2 == 1 && v3 == -1 && v4 == 1;
            let core_bear = v1 == -1 && v2 == -1 && v3 == 1 && v4 == -1;

            let ext_bull = [
                v5 == 1,
                v6_bull == 1,
                v7 == 1,
                fib_ok_long,
                v8 == 1,
                v9 == 1,
                ind.wave_ok_long,
                ind.mom_ok_long,
                v10 == 1,
                v11_bull == 1,
            ]
            .iter()
            .filter(|&&b| b)
            .count();

            let ext_bear = [
                v5 == -1,
                v6_bear == 1,
                v7 == -1,
                fib_ok_short,
                v8 == -1,
                v9 == -1,
                ind.wave_ok_short,
                ind.mom_ok_short,
                v10 == 1,
                v11_bear == 1,
            ]
            .iter()
            .filter(|&&b| b)
            .count();

            (core_bull && ext_bull >= 2, core_bear && ext_bear >= 2)
        }
        _ => {
            // "any" / default — core layers only
            let bull = v1 == 1 && v2 == 1 && v3 == -1 && v4 == 1;
            let bear = v1 == -1 && v2 == -1 && v3 == 1 && v4 == -1;
            (bull, bear)
        }
    };

    let fib_zone = if ms.in_discount {
        "discount"
    } else if ms.in_premium {
        "premium"
    } else {
        "mid"
    };

    let comps = SignalComponents {
        v_vwap: v1,
        v_ema: v2,
        v_st: v3,
        v_ts: v4,
        v_liq: v5,
        v_conf_bull: v6_bull,
        v_conf_bear: v6_bear,
        v_struct: v7,
        v_cvd: v8,
        v_ao: v9,
        v_hurst: v10,
        v_accel_bull: v11_bull,
        v_accel_bear: v11_bear,
        hurst: ind.hurst,
        price_accel: ind.price_accel,
        bull_score: conf.bull_score,
        bear_score: conf.bear_score,
        conf_min_adj: adj_min,
        liq_imbalance: liq.imbalance,
        liq_buy_pct: liq.buy_pct * 100.0,
        poc: liq.poc_price,
        struct_bias: ms.bias,
        fib618: ms.fib618,
        fib_zone,
        fib_ok: if bull { fib_ok_long } else { fib_ok_short },
        bos: ms.bos,
        choch: ms.choch,
        ts_norm: ind.ts_norm,
        dominance: ind.dominance,
        cvd_slope: cvd.map(|c| c.cvd_slope),
        cvd_div: cvd.map_or(0, |c| c.divergence),
        ao: ind.ao,
        ao_rising: ind.ao_rising,
        wr_pct: ind.wr_pct,
        mom_pct: ind.mom_pct,
        wave_ok_long: ind.wave_ok_long,
        wave_ok_short: ind.wave_ok_short,
        mom_ok_long: ind.mom_ok_long,
        mom_ok_short: ind.mom_ok_short,
        vol_pct: vol.map(|v| v.vol_pct),
        vol_regime: vol.map(|v| v.vol_regime),
    };

    if bull {
        return (1, comps);
    }
    if bear {
        return (-1, comps);
    }
    (0, comps)
}

fn empty_components(
    ind: &Indicators,
    liq: &LiquidityProfile,
    conf: &ConfluenceEngine,
    ms: &MarketStructure,
    cvd: Option<&CVDTracker>,
    vol: Option<&VolatilityPercentile>,
) -> SignalComponents {
    SignalComponents {
        v_vwap: 0,
        v_ema: 0,
        v_st: 0,
        v_ts: 0,
        v_liq: 0,
        v_conf_bull: 0,
        v_conf_bear: 0,
        v_struct: 0,
        v_cvd: 0,
        v_ao: 0,
        v_hurst: 0,
        v_accel_bull: 0,
        v_accel_bear: 0,
        hurst: ind.hurst,
        price_accel: ind.price_accel,
        bull_score: conf.bull_score,
        bear_score: conf.bear_score,
        conf_min_adj: 0.0,
        liq_imbalance: liq.imbalance,
        liq_buy_pct: liq.buy_pct * 100.0,
        poc: liq.poc_price,
        struct_bias: ms.bias,
        fib618: ms.fib618,
        fib_zone: "mid",
        fib_ok: false,
        bos: false,
        choch: false,
        ts_norm: 0.5,
        dominance: 0.0,
        cvd_slope: cvd.map(|c| c.cvd_slope),
        cvd_div: 0,
        ao: ind.ao,
        ao_rising: false,
        wr_pct: 0.5,
        mom_pct: 0.5,
        wave_ok_long: false,
        wave_ok_short: false,
        mom_ok_long: false,
        mom_ok_short: false,
        vol_pct: vol.map(|v| v.vol_pct),
        vol_regime: vol.map(|v| v.vol_regime),
    }
}

// ── SignalStreak ──────────────────────────────────────────────────────────────

/// Confirmation filter — signal must agree for `required` consecutive bars.
///
/// `update()` returns `true` only when the streak reaches `required` and the
/// signal is non-zero.
pub struct SignalStreak {
    required: usize,
    direction: i32,
    count: usize,
}

impl SignalStreak {
    pub fn new(required: usize) -> Self {
        Self {
            required,
            direction: 0,
            count: 0,
        }
    }

    /// Feed a raw signal (`+1`, `-1`, or `0`).
    /// Returns `true` when streak reaches `required` and signal is non-zero.
    pub fn update(&mut self, signal: i32) -> bool {
        if signal != 0 && signal == self.direction {
            self.count += 1;
        } else {
            self.direction = signal;
            self.count = usize::from(signal != 0);
        }
        self.count >= self.required && signal != 0
    }

    pub fn reset(&mut self) {
        self.direction = 0;
        self.count = 0;
    }
    pub fn current_direction(&self) -> i32 {
        self.direction
    }
    pub fn current_count(&self) -> usize {
        self.count
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── SignalStreak tests ────────────────────────────────────────────────────

    #[test]
    fn streak_fires_after_required_consecutive() {
        let mut s = SignalStreak::new(3);
        assert!(!s.update(1));
        assert!(!s.update(1));
        assert!(s.update(1)); // third consecutive → fires
        assert!(s.update(1)); // keeps firing
    }

    #[test]
    fn streak_resets_on_direction_change() {
        let mut s = SignalStreak::new(2);
        assert!(!s.update(1));
        assert!(s.update(1)); // fires
        assert!(!s.update(-1)); // direction changed → resets
        assert!(s.update(-1)); // fires again
    }

    #[test]
    fn streak_zero_signal_breaks_streak() {
        let mut s = SignalStreak::new(2);
        s.update(1);
        s.update(0); // zero resets
        assert!(!s.update(1)); // back to count=1
    }

    #[test]
    fn streak_required_1_fires_immediately() {
        let mut s = SignalStreak::new(1);
        assert!(s.update(1));
        assert!(s.update(-1));
        assert!(!s.update(0));
    }

    #[test]
    fn streak_tracks_direction_and_count() {
        let mut s = SignalStreak::new(3);
        s.update(1);
        s.update(1);
        assert_eq!(s.current_direction(), 1);
        assert_eq!(s.current_count(), 2);
        s.update(-1);
        assert_eq!(s.current_direction(), -1);
        assert_eq!(s.current_count(), 1);
    }

    #[test]
    fn streak_reset_clears_state() {
        let mut s = SignalStreak::new(2);
        s.update(1);
        s.update(1);
        s.reset();
        assert_eq!(s.current_count(), 0);
        assert_eq!(s.current_direction(), 0);
        assert!(!s.update(1)); // must rebuild from zero
    }
}
