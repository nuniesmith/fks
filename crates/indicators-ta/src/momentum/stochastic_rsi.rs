//! Stochastic RSI oscillator.
//!
//! Python source: `indicators/momentum/stochastic_rsi.py :: class StochasticRSI`
//!
//! # Algorithm
//!
//! 1. Compute RSI series (Wilder's method) with `rsi_period`.
//! 2. Apply the Stochastic formula to the RSI values over `stoch_period`:
//!    `%K_raw[i] = 100 * (rsi[i] - min_rsi) / (max_rsi - min_rsi)`
//! 3. Smooth %K with SMA over `k_smooth` bars.
//! 4. %D = SMA of smooth %K over `d_period` bars.
//!
//! Output columns: `"StochRSI_K"`, `"StochRSI_D"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::momentum::rsi::{Rsi, RsiParams};
use crate::registry::param_usize;
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct StochRsiParams {
    /// RSI period. Default: 14.
    pub rsi_period: usize,
    /// Rolling window over RSI values for stochastic. Default: 14.
    pub stoch_period: usize,
    /// SMA smoothing of raw %K. Default: 3.
    pub k_smooth: usize,
    /// SMA of smooth %K for %D. Default: 3.
    pub d_period: usize,
}

impl Default for StochRsiParams {
    fn default() -> Self {
        Self {
            rsi_period: 14,
            stoch_period: 14,
            k_smooth: 3,
            d_period: 3,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct StochasticRsi {
    pub params: StochRsiParams,
}

impl StochasticRsi {
    pub fn new(params: StochRsiParams) -> Self {
        Self { params }
    }
}

impl Default for StochasticRsi {
    fn default() -> Self {
        Self::new(StochRsiParams::default())
    }
}

impl Indicator for StochasticRsi {
    fn name(&self) -> &'static str {
        "StochasticRSI"
    }

    fn required_len(&self) -> usize {
        // RSI needs rsi_period+1 bars; stochastic then needs stoch_period RSI values;
        // then k_smooth and d_period smoothing on top.
        self.params.rsi_period
            + 1
            + self.params.stoch_period
            + self.params.k_smooth
            + self.params.d_period
            - 2
    }

    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let rsi_p = self.params.rsi_period;
        let stoch_p = self.params.stoch_period;
        let ks = self.params.k_smooth;
        let dp = self.params.d_period;

        // ── Step 1: RSI series ────────────────────────────────────────────────
        let rsi_out = Rsi::new(RsiParams {
            period: rsi_p,
            ..Default::default()
        })
        .calculate(candles)?;
        let rsi_key = format!("RSI_{rsi_p}");
        let rsi: &[f64] = rsi_out
            .get(&rsi_key)
            .ok_or_else(|| IndicatorError::InvalidParam("RSI output missing".into()))?;

        // ── Step 2: Stochastic of RSI ─────────────────────────────────────────
        let mut raw_k = vec![f64::NAN; n];
        for i in (stoch_p - 1)..n {
            // Window must be fully non-NaN.
            let window = &rsi[(i + 1 - stoch_p)..=i];
            if window.iter().any(|v| v.is_nan()) {
                continue;
            }
            let min_r = window.iter().copied().fold(f64::INFINITY, f64::min);
            let max_r = window.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            let range = max_r - min_r;
            raw_k[i] = if range == 0.0 {
                50.0
            }
            // flat RSI → neutral %K
            else {
                100.0 * (rsi[i] - min_r) / range
            };
        }

        // ── Step 3: smooth %K ─────────────────────────────────────────────────
        let smooth_k = if ks <= 1 {
            raw_k.clone()
        } else {
            sma_of(&raw_k, ks)
        };

        // ── Step 4: %D ────────────────────────────────────────────────────────
        let d = sma_of(&smooth_k, dp);

        Ok(IndicatorOutput::from_pairs([
            ("StochRSI_K".to_string(), smooth_k),
            ("StochRSI_D".to_string(), d),
        ]))
    }
}

fn sma_of(src: &[f64], period: usize) -> Vec<f64> {
    let n = src.len();
    let mut out = vec![f64::NAN; n];
    let mut consecutive = 0usize;
    for i in 0..n {
        if src[i].is_nan() {
            consecutive = 0;
        } else {
            consecutive += 1;
            if consecutive >= period {
                let sum: f64 = src[(i + 1 - period)..=i].iter().sum();
                out[i] = sum / period as f64;
            }
        }
    }
    out
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(StochasticRsi::new(StochRsiParams {
        rsi_period: param_usize(params, "rsi_period", 14)?,
        stoch_period: param_usize(params, "stoch_period", 14)?,
        k_smooth: param_usize(params, "k_smooth", 3)?,
        d_period: param_usize(params, "d_period", 3)?,
    })))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn make_candles(closes: &[f64]) -> Vec<Candle> {
        closes
            .iter()
            .enumerate()
            .map(|(i, &c)| Candle {
                time: i64::try_from(i).expect("time index fits i64"),
                open: c,
                high: c,
                low: c,
                close: c,
                volume: 1.0,
            })
            .collect()
    }

    #[test]
    fn stochrsi_insufficient_data() {
        let err = StochasticRsi::default()
            .calculate(&make_candles(&[1.0; 10]))
            .unwrap_err();
        assert!(matches!(err, IndicatorError::InsufficientData { .. }));
    }

    #[test]
    fn stochrsi_output_columns_exist() {
        let needed = StochasticRsi::default().required_len();
        let prices: Vec<f64> = (0..needed + 5)
            .map(|i| 100.0 + (i as f64 * 0.4).sin() * 5.0)
            .collect();
        let out = StochasticRsi::default()
            .calculate(&make_candles(&prices))
            .unwrap();
        assert!(out.get("StochRSI_K").is_some());
        assert!(out.get("StochRSI_D").is_some());
    }

    #[test]
    fn stochrsi_range_0_to_100() {
        let needed = StochasticRsi::default().required_len();
        let prices: Vec<f64> = (0..needed + 20)
            .map(|i| 100.0 + (i as f64 * 0.25).sin() * 8.0)
            .collect();
        let out = StochasticRsi::default()
            .calculate(&make_candles(&prices))
            .unwrap();
        for &v in out.get("StochRSI_K").unwrap() {
            if !v.is_nan() {
                assert!((0.0..=100.0).contains(&v), "K out of range: {v}");
            }
        }
        for &v in out.get("StochRSI_D").unwrap() {
            if !v.is_nan() {
                assert!((0.0..=100.0).contains(&v), "D out of range: {v}");
            }
        }
    }

    #[test]
    fn stochrsi_constant_prices_neutral() {
        // Constant closes → RSI=50 everywhere → StochRSI range=0 → %K=50 (flat-RSI guard).
        let needed = StochasticRsi::default().required_len();
        let prices = vec![100.0_f64; needed + 5];
        let out = StochasticRsi::default()
            .calculate(&make_candles(&prices))
            .unwrap();
        let k = out.get("StochRSI_K").unwrap();
        for &v in k.iter().filter(|v| !v.is_nan()) {
            assert!((v - 50.0).abs() < 1e-9, "expected 50.0 (neutral), got {v}");
        }
    }

    #[test]
    fn stochrsi_d_lags_k() {
        // %D is a 3-bar SMA of %K so it must have fewer non-NaN values than %K.
        let needed = StochasticRsi::default().required_len();
        let prices: Vec<f64> = (0..needed + 10)
            .map(|i| 100.0 + (i as f64 * 0.5).sin() * 5.0)
            .collect();
        let out = StochasticRsi::default()
            .calculate(&make_candles(&prices))
            .unwrap();
        let k_count = out
            .get("StochRSI_K")
            .unwrap()
            .iter()
            .filter(|v| !v.is_nan())
            .count();
        let d_count = out
            .get("StochRSI_D")
            .unwrap()
            .iter()
            .filter(|v| !v.is_nan())
            .count();
        assert!(d_count <= k_count, "D should have ≤ non-NaN values than K");
    }

    #[test]
    fn factory_creates_stochrsi() {
        let ind = factory(&HashMap::new()).unwrap();
        assert_eq!(ind.name(), "StochasticRSI");
    }
}
