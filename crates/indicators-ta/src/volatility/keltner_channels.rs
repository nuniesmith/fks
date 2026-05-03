//! Keltner Channels.
//!
//! Ported from `keltner_channels.py` :: `class KeltnerChannelsIndicator`.
//!
//! # Algorithm
//!
//! 1. `middle[i] = EMA(close, period)`
//! 2. `true_range[i] = max(H−L, |H−prev_C|, |L−prev_C|)` (H−L for the first bar)
//! 3. `atr[i] = rolling mean of true_range` (min_periods=1, matching Python)
//! 4. `upper[i] = middle[i] + multiplier × atr[i]`
//! 5. `lower[i] = middle[i] − multiplier × atr[i]`
//!
//! Output columns: `"KC_upper"`, `"KC_lower"`, `"KC_middle"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::functions::{self};
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::{param_f64, param_usize};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct KeltnerParams {
    /// EMA period (also used for ATR look-back).  Python default: 20.
    pub period: usize,
    /// ATR multiplier for band width.  Python default: 2.0.
    pub multiplier: f64,
}

impl Default for KeltnerParams {
    fn default() -> Self {
        Self {
            period: 20,
            multiplier: 2.0,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct KeltnerChannels {
    pub params: KeltnerParams,
}

impl KeltnerChannels {
    pub fn new(params: KeltnerParams) -> Self {
        Self { params }
    }

    pub fn with_period(period: usize) -> Self {
        Self::new(KeltnerParams {
            period,
            ..Default::default()
        })
    }
}

// ── Indicator impl ────────────────────────────────────────────────────────────

impl Indicator for KeltnerChannels {
    fn name(&self) -> &'static str {
        "KeltnerChannels"
    }
    fn required_len(&self) -> usize {
        self.params.period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let p = self.params.period;
        let mult = self.params.multiplier;

        // EMA of close → middle band
        let close: Vec<f64> = candles.iter().map(|c| c.close).collect();
        let middle = functions::ema(&close, p)?;

        // True range (max of three measures; H-L only for bar 0)
        let mut tr = vec![0.0f64; n];
        for i in 0..n {
            let hl = candles[i].high - candles[i].low;
            tr[i] = if i == 0 {
                hl
            } else {
                let pc = candles[i - 1].close;
                hl.max((candles[i].high - pc).abs())
                    .max((candles[i].low - pc).abs())
            };
        }

        // Rolling mean of TR with min_periods=1 (matches Python's rolling(window, min_periods=1).mean())
        let mut atr = vec![0.0f64; n];
        for i in 0..n {
            let start = (i + 1).saturating_sub(p);
            atr[i] = tr[start..=i].iter().sum::<f64>() / (i - start + 1) as f64;
        }

        // Bands — only where middle is non-NaN (needs `period` bars of EMA warm-up)
        let mut upper = vec![f64::NAN; n];
        let mut lower = vec![f64::NAN; n];
        for i in 0..n {
            if !middle[i].is_nan() {
                upper[i] = middle[i] + mult * atr[i];
                lower[i] = middle[i] - mult * atr[i];
            }
        }

        Ok(IndicatorOutput::from_pairs([
            ("KC_upper".to_string(), upper),
            ("KC_lower".to_string(), lower),
            ("KC_middle".to_string(), middle),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(KeltnerChannels::new(KeltnerParams {
        period: param_usize(params, "period", 20)?,
        multiplier: param_f64(params, "multiplier", 2.0)?,
    })))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn candles(n: usize) -> Vec<Candle> {
        (0..n)
            .map(|i| Candle {
                time: i64::try_from(i).expect("time index fits i64"),
                open: 10.0 + i as f64 * 0.05,
                high: 11.0 + i as f64 * 0.10,
                low: 9.0 - i as f64 * 0.05,
                close: 10.0 + i as f64 * 0.10,
                volume: 100.0,
            })
            .collect()
    }

    #[test]
    fn kc_three_output_columns() {
        let out = KeltnerChannels::with_period(10)
            .calculate(&candles(15))
            .unwrap();
        assert!(out.get("KC_upper").is_some());
        assert!(out.get("KC_lower").is_some());
        assert!(out.get("KC_middle").is_some());
    }

    #[test]
    fn kc_upper_above_lower() {
        let out = KeltnerChannels::with_period(5)
            .calculate(&candles(20))
            .unwrap();
        let upper = out.get("KC_upper").unwrap();
        let lower = out.get("KC_lower").unwrap();
        for i in 0..20 {
            if !upper[i].is_nan() {
                assert!(upper[i] > lower[i], "upper <= lower at {i}");
            }
        }
    }

    #[test]
    fn kc_middle_is_ema() {
        // Middle band must equal EMA(close, period) exactly.
        use crate::functions;
        let bars = candles(20);
        let closes: Vec<f64> = bars.iter().map(|c| c.close).collect();
        let ema = functions::ema(&closes, 5).unwrap();
        let out = KeltnerChannels::with_period(5).calculate(&bars).unwrap();
        let middle = out.get("KC_middle").unwrap();
        for i in 0..20 {
            if !ema[i].is_nan() {
                assert!((middle[i] - ema[i]).abs() < 1e-9, "middle≠EMA at {i}");
            }
        }
    }

    #[test]
    fn kc_insufficient_data_errors() {
        assert!(
            KeltnerChannels::with_period(10)
                .calculate(&candles(5))
                .is_err()
        );
    }

    #[test]
    fn factory_creates_keltner() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "KeltnerChannels");
    }
}
