//! Stochastic Oscillator (%K and %D).
//!
//! Python source: `indicators/momentum/stochastic.py :: class Stochastic`
//!
//! # Algorithm
//!
//! 1. **Raw %K**:
//!    `%K[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)`
//!    where the window is `k_period` bars ending at `i`.
//!    Yields `NaN` when `highest_high == lowest_low`.
//!
//! 2. **Smooth %K** (optional): SMA of raw %K over `smooth_k` bars.
//!    `smooth_k = 1` means no smoothing (fast stochastic).
//!    `smooth_k = 3` is the standard slow stochastic.
//!
//! 3. **%D**: SMA of smooth %K over `d_period` bars.
//!
//! Output columns: `"Stoch_K"`, `"Stoch_D"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct StochParams {
    /// Look-back window for highest-high / lowest-low. Default: 14.
    pub k_period: usize,
    /// Smoothing of raw %K. 1 = no smoothing. Default: 3.
    pub smooth_k: usize,
    /// SMA period for %D. Default: 3.
    pub d_period: usize,
}

impl Default for StochParams {
    fn default() -> Self {
        Self {
            k_period: 14,
            smooth_k: 3,
            d_period: 3,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Stochastic {
    pub params: StochParams,
}

impl Stochastic {
    pub fn new(params: StochParams) -> Self {
        Self { params }
    }
}

impl Default for Stochastic {
    fn default() -> Self {
        Self::new(StochParams::default())
    }
}

impl Indicator for Stochastic {
    fn name(&self) -> &'static str {
        "Stochastic"
    }

    fn required_len(&self) -> usize {
        self.params.k_period + self.params.smooth_k + self.params.d_period - 2
    }

    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let kp = self.params.k_period;
        let sk = self.params.smooth_k;
        let dp = self.params.d_period;

        // ── Step 1: raw %K ────────────────────────────────────────────────────
        let mut raw_k = vec![f64::NAN; n];
        for i in (kp - 1)..n {
            let window = &candles[(i + 1 - kp)..=i];
            let hh = window
                .iter()
                .map(|c| c.high)
                .fold(f64::NEG_INFINITY, f64::max);
            let ll = window.iter().map(|c| c.low).fold(f64::INFINITY, f64::min);
            let range = hh - ll;
            raw_k[i] = if range == 0.0 {
                f64::NAN
            } else {
                100.0 * (candles[i].close - ll) / range
            };
        }

        // ── Step 2: smooth %K (SMA) ───────────────────────────────────────────
        let smooth_k = if sk <= 1 {
            raw_k.clone()
        } else {
            sma_of(&raw_k, sk)
        };

        // ── Step 3: %D (SMA of smooth_k) ─────────────────────────────────────
        let d = sma_of(&smooth_k, dp);

        Ok(IndicatorOutput::from_pairs([
            ("Stoch_K".to_string(), smooth_k),
            ("Stoch_D".to_string(), d),
        ]))
    }
}

/// Rolling SMA over a `Vec<f64>` that may contain leading or mid-series NaN values.
///
/// `consecutive` counts the unbroken run of non-NaN values ending at the current
/// position.  A window is only emitted once `consecutive >= period`, which
/// guarantees that every element of the slice `src[(i+1-period)..=i]` is
/// non-NaN — no special NaN-sum guard is needed in the inner loop.
fn sma_of(src: &[f64], period: usize) -> Vec<f64> {
    let n = src.len();
    let mut out = vec![f64::NAN; n];
    // Find the first index where `period` consecutive non-NaN values end.
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
    Ok(Box::new(Stochastic::new(StochParams {
        k_period: param_usize(params, "k_period", 14)?,
        smooth_k: param_usize(params, "smooth_k", 3)?,
        d_period: param_usize(params, "d_period", 3)?,
    })))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn make_candles(data: &[(f64, f64, f64)]) -> Vec<Candle> {
        // (high, low, close)
        data.iter()
            .enumerate()
            .map(|(i, &(h, l, c))| Candle {
                time: i64::try_from(i).expect("time index fits i64"),
                open: c,
                high: h,
                low: l,
                close: c,
                volume: 1.0,
            })
            .collect()
    }

    fn uniform_candles(n: usize, high: f64, low: f64, close: f64) -> Vec<Candle> {
        make_candles(&vec![(high, low, close); n])
    }

    #[test]
    fn stoch_insufficient_data() {
        let err = Stochastic::default()
            .calculate(&uniform_candles(5, 12.0, 8.0, 10.0))
            .unwrap_err();
        assert!(matches!(err, IndicatorError::InsufficientData { .. }));
    }

    #[test]
    fn stoch_output_columns_exist() {
        let out = Stochastic::default()
            .calculate(&uniform_candles(30, 12.0, 8.0, 10.0))
            .unwrap();
        assert!(out.get("Stoch_K").is_some());
        assert!(out.get("Stoch_D").is_some());
    }

    #[test]
    fn stoch_known_value_midpoint() {
        // high=12, low=8, close=10 for all bars.
        // raw %K = 100*(10-8)/(12-8) = 50.0.
        // smooth_k=3 SMA of [50,50,50,...] = 50. %D = 50.
        let out = Stochastic::new(StochParams {
            k_period: 5,
            smooth_k: 3,
            d_period: 3,
        })
        .calculate(&uniform_candles(20, 12.0, 8.0, 10.0))
        .unwrap();
        let k = out.get("Stoch_K").unwrap();
        let d = out.get("Stoch_D").unwrap();
        let last_k = k.iter().rev().find(|v| !v.is_nan()).copied().unwrap();
        let last_d = d.iter().rev().find(|v| !v.is_nan()).copied().unwrap();
        assert!(
            (last_k - 50.0).abs() < 1e-9,
            "K expected 50.0, got {last_k}"
        );
        assert!(
            (last_d - 50.0).abs() < 1e-9,
            "D expected 50.0, got {last_d}"
        );
    }

    #[test]
    fn stoch_close_at_high_is_100() {
        // close == high → raw %K = 100.
        let out = Stochastic::new(StochParams {
            k_period: 5,
            smooth_k: 1,
            d_period: 1,
        })
        .calculate(&uniform_candles(10, 12.0, 8.0, 12.0))
        .unwrap();
        let k = out.get("Stoch_K").unwrap();
        for &v in k.iter().filter(|v| !v.is_nan()) {
            assert!((v - 100.0).abs() < 1e-9, "expected 100.0, got {v}");
        }
    }

    #[test]
    fn stoch_close_at_low_is_0() {
        // close == low → raw %K = 0.
        let out = Stochastic::new(StochParams {
            k_period: 5,
            smooth_k: 1,
            d_period: 1,
        })
        .calculate(&uniform_candles(10, 12.0, 8.0, 8.0))
        .unwrap();
        let k = out.get("Stoch_K").unwrap();
        for &v in k.iter().filter(|v| !v.is_nan()) {
            assert!(v.abs() < 1e-9, "expected 0.0, got {v}");
        }
    }

    #[test]
    fn stoch_range_0_to_100() {
        // Rising then falling sequence.
        let mut data = vec![];
        for i in 0..15 {
            let f = i as f64;
            data.push((f + 1.0, f - 1.0, f));
        }
        for i in (0..10).rev() {
            let f = i as f64;
            data.push((f + 1.0, f - 1.0, f));
        }
        let out = Stochastic::default()
            .calculate(&make_candles(&data))
            .unwrap();
        for &v in out.get("Stoch_K").unwrap() {
            if !v.is_nan() {
                assert!((0.0..=100.0).contains(&v), "K out of range: {v}");
            }
        }
        for &v in out.get("Stoch_D").unwrap() {
            if !v.is_nan() {
                assert!((0.0..=100.0).contains(&v), "D out of range: {v}");
            }
        }
    }

    #[test]
    fn stoch_no_smoothing_fast_stochastic() {
        // smooth_k=1 → raw %K passed through directly.
        let out = Stochastic::new(StochParams {
            k_period: 3,
            smooth_k: 1,
            d_period: 1,
        })
        .calculate(&uniform_candles(10, 10.0, 0.0, 6.0))
        .unwrap();
        // close=6, range=10 → 60.0.
        let k = out.get("Stoch_K").unwrap();
        for &v in k.iter().filter(|v| !v.is_nan()) {
            assert!((v - 60.0).abs() < 1e-9, "expected 60.0, got {v}");
        }
    }

    #[test]
    fn factory_creates_stochastic() {
        let ind = factory(&HashMap::new()).unwrap();
        assert_eq!(ind.name(), "Stochastic");
    }
}
