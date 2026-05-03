//! Choppiness Index (CHOP).
//!
//! Python source: `indicators/other/choppiness_index.py :: class ChoppinessIndex`
//!
//! # Python algorithm (to port)
//! ```python
//! high_low_range = df["High"] - df["Low"]
//! atr_sum        = high_low_range.rolling(window=self.period).sum()
//! max_high       = df["High"].rolling(window=self.period).max()
//! min_low        = df["Low"].rolling(window=self.period).min()
//! denominator    = (max_high - min_low).replace(0, np.nan)
//! chop           = 100 * np.log10(atr_sum / denominator) / np.log10(self.period)
//! ```
//!
//! Readings above 61.8 → choppy/sideways; below 38.2 → trending.
//!
//! Output column: `"CHOP_{period}"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

#[derive(Debug, Clone)]
pub struct ChopParams {
    pub period: usize,
}
impl Default for ChopParams {
    fn default() -> Self {
        Self { period: 14 }
    }
}

#[derive(Debug, Clone)]
pub struct ChoppinessIndex {
    pub params: ChopParams,
}

impl ChoppinessIndex {
    pub fn new(params: ChopParams) -> Self {
        Self { params }
    }
    pub fn with_period(period: usize) -> Self {
        Self::new(ChopParams { period })
    }
    fn output_key(&self) -> String {
        format!("CHOP_{}", self.params.period)
    }
}

impl Indicator for ChoppinessIndex {
    fn name(&self) -> &'static str {
        "ChoppinessIndex"
    }
    fn required_len(&self) -> usize {
        self.params.period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low"]
    }

    /// Ports `100 * log10(sum_atr / (max_high - min_low)) / log10(period)`.
    ///
    /// `sum_atr` = rolling sum of `high - low` (true range for OHLC-equal bars).
    /// Returns `NaN` when the denominator or `log10(period)` is zero.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let p = self.params.period;
        let log_period = (p as f64).log10();

        let mut values = vec![f64::NAN; n];

        for i in (p - 1)..n {
            let window = &candles[(i + 1 - p)..=i];
            let atr_sum: f64 = window.iter().map(|c| c.high - c.low).sum();
            let max_h = window
                .iter()
                .map(|c| c.high)
                .fold(f64::NEG_INFINITY, f64::max);
            let min_l = window.iter().map(|c| c.low).fold(f64::INFINITY, f64::min);
            let denom = max_h - min_l;
            values[i] = if denom == 0.0 || log_period == 0.0 {
                f64::NAN
            } else {
                100.0 * (atr_sum / denom).log10() / log_period
            };
        }

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(ChoppinessIndex::new(ChopParams {
        period: param_usize(params, "period", 14)?,
    })))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn candles(n: usize, range: f64) -> Vec<Candle> {
        (0..n)
            .map(|i| Candle {
                time: i64::try_from(i).expect("time index fits i64"),
                open: 10.0,
                high: 10.0 + range,
                low: 10.0 - range,
                close: 10.0,
                volume: 100.0,
            })
            .collect()
    }

    #[test]
    fn chop_output_column() {
        let out = ChoppinessIndex::with_period(14)
            .calculate(&candles(20, 1.0))
            .unwrap();
        assert!(out.get("CHOP_14").is_some());
    }

    #[test]
    fn chop_constant_range_near_100() {
        // Constant H-L with the same max_h−min_l → ratio=1 → log10(1)=0 → CHOP=0?
        // Python: 100 * log10(sum_atr / (max_h - min_l)) / log10(period)
        // With constant bars: sum_atr = period * range, max_h-min_l = range
        // → log10(period) / log10(period) = 1 → CHOP = 100
        let out = ChoppinessIndex::with_period(14)
            .calculate(&candles(20, 1.0))
            .unwrap();
        let vals = out.get("CHOP_14").unwrap();
        let last = vals.iter().rev().find(|v| !v.is_nan()).copied().unwrap();
        assert!((last - 100.0).abs() < 1e-6, "got {last}");
    }

    #[test]
    fn factory_creates_chop() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "ChoppinessIndex");
    }
}
