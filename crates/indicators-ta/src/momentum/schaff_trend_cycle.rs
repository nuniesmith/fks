//! Schaff Trend Cycle (STC).
//!
//! Readings above 75 → overbought; below 25 → oversold.
//! Oscillates 0–100.
//!
//! Output column: `"STC"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::functions::{self};
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

#[derive(Debug, Clone)]
pub struct StcParams {
    pub short_ema: usize,
    pub long_ema: usize,
    pub stoch_period: usize,
    pub signal_period: usize,
}
impl Default for StcParams {
    fn default() -> Self {
        Self {
            short_ema: 12,
            long_ema: 26,
            stoch_period: 10,
            signal_period: 3,
        }
    }
}

#[derive(Debug, Clone)]
pub struct SchaffTrendCycle {
    pub params: StcParams,
}

impl SchaffTrendCycle {
    pub fn new(params: StcParams) -> Self {
        Self { params }
    }
}

impl Default for SchaffTrendCycle {
    fn default() -> Self {
        Self::new(StcParams::default())
    }
}

impl Indicator for SchaffTrendCycle {
    fn name(&self) -> &'static str {
        "SchaffTrendCycle"
    }

    fn required_len(&self) -> usize {
        // The minimum data required for at least some non-NaN output is the
        // slow EMA warm-up period.  The stochastic and signal stages add
        // additional latency but do not require extra candles at the input
        // boundary — they simply produce NaN for their own warm-up bars.
        self.params.long_ema
    }

    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    /// Ports the three-stage MACD → Stochastic → EMA pipeline.
    ///
    /// # EMA seeding difference vs Python
    /// The Python source calls `ewm(span=...)` with the **default** `adjust=True`,
    /// which uses decaying weights rather than the recursive formula.
    /// `functions::ema()` implements the `adjust=False` (recursive) variant.
    /// For series longer than ~3× the span the two converge; for shorter series
    /// the warm-up values will differ slightly.
    ///
    /// # Zero-range stochastic handling
    /// When `max_macd_diff == min_macd_diff` across the window, Python produces
    /// `NaN` via `.replace(0, np.nan)` before division.  The Rust guards the
    /// same condition with an explicit `range == 0.0` check.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let close: Vec<f64> = candles.iter().map(|c| c.close).collect();
        let n = close.len();

        // Step 1: MACD components.
        let short_e = functions::ema(&close, self.params.short_ema)?;
        let long_e = functions::ema(&close, self.params.long_ema)?;
        let macd_line: Vec<f64> = (0..n)
            .map(|i| {
                if short_e[i].is_nan() || long_e[i].is_nan() {
                    f64::NAN
                } else {
                    short_e[i] - long_e[i]
                }
            })
            .collect();

        // Signal of MACD (span=9).
        // macd_line has leading NaN (warm-up from long_ema); use the NaN-aware
        // EMA so it seeds from the first valid value rather than propagating NaN.
        let macd_sig = functions::ema_nan_aware(&macd_line, 9)?;
        let macd_diff: Vec<f64> = (0..n)
            .map(|i| {
                if macd_line[i].is_nan() || macd_sig[i].is_nan() {
                    f64::NAN
                } else {
                    macd_line[i] - macd_sig[i]
                }
            })
            .collect();

        // Step 2: Stochastic of MACD diff.
        let sp = self.params.stoch_period;
        let mut stc = vec![f64::NAN; n];
        for i in (sp - 1)..n {
            let window = &macd_diff[(i + 1 - sp)..=i];
            let min_d = window.iter().copied().fold(f64::INFINITY, f64::min);
            let max_d = window.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            let range = max_d - min_d;
            if macd_diff[i].is_nan() || range == 0.0 {
                stc[i] = f64::NAN;
            } else {
                stc[i] = 100.0 * (macd_diff[i] - min_d) / range;
            }
        }

        // Step 3: optional EMA smoothing.
        // `stc` has leading NaN from the stochastic warm-up; use the NaN-aware
        // EMA so it seeds from the first valid stochastic value.
        let values = if self.params.signal_period > 0 {
            functions::ema_nan_aware(&stc, self.params.signal_period)?
        } else {
            stc
        };

        Ok(IndicatorOutput::from_pairs([("STC".to_string(), values)]))
    }
}

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(SchaffTrendCycle::new(StcParams {
        short_ema: param_usize(params, "short_ema", 12)?,
        long_ema: param_usize(params, "long_ema", 26)?,
        stoch_period: param_usize(params, "stoch_period", 10)?,
        signal_period: param_usize(params, "signal_period", 3)?,
    })))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn candles(n: usize) -> Vec<Candle> {
        (0..n)
            .map(|i| Candle {
                time: i64::try_from(i).expect("time index fits i64"),
                open: 10.0,
                high: 10.0 + (i % 5) as f64,
                low: 10.0 - (i % 3) as f64,
                close: 10.0 + (i as f64).sin(),
                volume: 100.0,
            })
            .collect()
    }

    #[test]
    fn stc_output_column() {
        let p = StcParams::default();
        let needed = p.long_ema + p.stoch_period + p.signal_period + 5;
        let out = SchaffTrendCycle::default()
            .calculate(&candles(needed))
            .unwrap();
        assert!(out.get("STC").is_some());
    }

    #[test]
    fn factory_creates_stc() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "SchaffTrendCycle");
    }
}
