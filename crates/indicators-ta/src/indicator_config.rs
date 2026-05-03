//! `IndicatorConfig` — the indicator-math subset of `BotSettings`.
//!
//! Pure configuration: no I/O, no runtime, no exchange types.
//! This struct is what `compute_signal` and all indicator constructors need.
//!

use serde::{Deserialize, Serialize};

/// All tunable parameters that live inside indicators and `compute_signal`.
/// Every field maps 1-to-1 to a key in the Python `SETTINGS` dict so
/// Optuna-tuned JSON files load with zero field renaming.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndicatorConfig {
    // ── Engine Buffer ────────────────────────────────────────────────────────
    /// Candle buffer capacity
    pub history_candles: usize,

    // ── Layer 1-2: VWAP & EMA ────────────────────────────────────────────────
    pub ema_len: usize,

    // ── Layer 3: ML SuperTrend ───────────────────────────────────────────────
    pub atr_len: usize,
    pub st_factor: f64,
    pub training_period: usize,
    pub highvol_pct: f64,
    pub midvol_pct: f64,
    pub lowvol_pct: f64,

    // ── Layer 4: Trend Speed ─────────────────────────────────────────────────
    pub ts_max_length: usize,
    pub ts_accel_mult: f64,
    pub ts_rma_len: usize,
    pub ts_hma_len: usize,
    pub ts_collen: usize,
    pub ts_lookback: usize,
    pub ts_speed_exit_threshold: Option<f64>,

    // ── Layer 5: Liquidity Profile ───────────────────────────────────────────
    pub liq_period: usize,
    pub liq_bins: usize,

    // ── Layer 6: Confluence ──────────────────────────────────────────────────
    pub conf_ema_fast: usize,
    pub conf_ema_slow: usize,
    pub conf_ema_trend: usize,
    pub conf_rsi_len: usize,
    pub conf_adx_len: usize,
    pub conf_min_score: f64,

    // ── Layer 7: Market Structure + Fibonacci ────────────────────────────────
    pub struct_swing_len: usize,
    pub struct_atr_mult: f64,
    pub fib_zone_enabled: bool,

    // ── Signal mode ──────────────────────────────────────────────────────────
    /// `"majority"` | `"strict"` | `"any"`
    pub signal_mode: String,
    pub signal_confirm_bars: usize,

    // ── Layer 8: CVD ─────────────────────────────────────────────────────────
    pub cvd_slope_bars: usize,
    pub cvd_div_lookback: usize,

    // ── Layer 9: AO + Percentile gates ──────────────────────────────────────
    pub wave_pct_l: f64,
    pub wave_pct_s: f64,
    pub mom_pct_min: f64,
    pub vol_pct_window: usize,

    // ── Layer 10: Hurst ──────────────────────────────────────────────────────
    pub hurst_threshold: f64,
    pub hurst_lookback: usize,

    // ── Layer 11: Price Acceleration / Stop ──────────────────────────────────
    pub stop_atr_mult: f64,

    // ── Entry gates ──────────────────────────────────────────────────────────
    pub min_vol_pct: f64,
    pub min_hold_candles: usize,
}

impl Default for IndicatorConfig {
    fn default() -> Self {
        Self {
            history_candles: 200,
            ema_len: 9,
            atr_len: 10,
            st_factor: 3.0,
            training_period: 100,
            highvol_pct: 0.75,
            midvol_pct: 0.50,
            lowvol_pct: 0.25,
            ts_max_length: 50,
            ts_accel_mult: 5.0,
            ts_rma_len: 10,
            ts_hma_len: 5,
            ts_collen: 100,
            ts_lookback: 50,
            ts_speed_exit_threshold: None,
            liq_period: 100,
            liq_bins: 31,
            conf_ema_fast: 9,
            conf_ema_slow: 21,
            conf_ema_trend: 55,
            conf_rsi_len: 13,
            conf_adx_len: 14,
            conf_min_score: 5.0,
            struct_swing_len: 10,
            struct_atr_mult: 0.5,
            fib_zone_enabled: true,
            signal_mode: "majority".into(),
            signal_confirm_bars: 2,
            cvd_slope_bars: 10,
            cvd_div_lookback: 30,
            wave_pct_l: 0.25,
            wave_pct_s: 0.75,
            mom_pct_min: 0.30,
            vol_pct_window: 200,
            hurst_threshold: 0.52,
            hurst_lookback: 20,
            stop_atr_mult: 1.5,
            min_vol_pct: 0.20,
            min_hold_candles: 2,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_signal_mode_is_majority() {
        assert_eq!(IndicatorConfig::default().signal_mode, "majority");
    }

    #[test]
    fn serde_round_trip() {
        let cfg = IndicatorConfig::default();
        let json = serde_json::to_string(&cfg).unwrap();
        let back: IndicatorConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(back.ema_len, cfg.ema_len);
        assert_eq!(back.signal_mode, cfg.signal_mode);
    }
}
