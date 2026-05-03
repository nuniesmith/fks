//! Williams %R.
//!
//! Python source: `indicators/other/williams_r.py :: class WilliamsRIndicator`
//!
//! # Python algorithm (to port)
//! ```python
//! highest_high = data["High"].rolling(window=self.period).max()
//! lowest_low   = data["Low"].rolling(window=self.period).min()
//! will_r       = -100 * (highest_high - data["Close"]) / (highest_high - lowest_low)
//! ```
//!
//! Oscillates between -100 and 0.  Above -20 → overbought; below -80 → oversold.
//!
//! Output column: `"WR_{period}"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

#[derive(Debug, Clone)]
pub struct WrParams {
    pub period: usize,
}
impl Default for WrParams {
    fn default() -> Self {
        Self { period: 14 }
    }
}

#[derive(Debug, Clone)]
pub struct WilliamsR {
    pub params: WrParams,
}

impl WilliamsR {
    pub fn new(params: WrParams) -> Self {
        Self { params }
    }
    pub fn with_period(period: usize) -> Self {
        Self::new(WrParams { period })
    }
    fn output_key(&self) -> String {
        format!("WR_{}", self.params.period)
    }
}

impl Indicator for WilliamsR {
    fn name(&self) -> &'static str {
        "WilliamsR"
    }
    fn required_len(&self) -> usize {
        self.params.period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close"]
    }

    /// Ports `-100 * (highest_high - close) / (highest_high - lowest_low)`.
    ///
    /// When `highest_high == lowest_low` Python produces `NaN` via float
    /// division by zero; the Rust guards this explicitly with a
    /// `range == 0.0` check.  Both paths produce `NaN` for that bar.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let p = self.params.period;
        let mut values = vec![f64::NAN; n];

        for i in (p - 1)..n {
            let window = &candles[(i + 1 - p)..=i];
            let highest_h = window
                .iter()
                .map(|c| c.high)
                .fold(f64::NEG_INFINITY, f64::max);
            let lowest_l = window.iter().map(|c| c.low).fold(f64::INFINITY, f64::min);
            let range = highest_h - lowest_l;
            values[i] = if range == 0.0 {
                f64::NAN
            } else {
                -100.0 * (highest_h - candles[i].close) / range
            };
        }

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(WilliamsR::new(WrParams {
        period: param_usize(params, "period", 14)?,
    })))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn candles(data: &[(f64, f64, f64)]) -> Vec<Candle> {
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

    fn rising(n: usize) -> Vec<Candle> {
        (0..n)
            .map(|i| {
                let f = i as f64;
                Candle {
                    time: i64::try_from(i).expect("time index fits i64"),
                    open: f,
                    high: f + 1.0,
                    low: f - 1.0,
                    close: f + 0.5,
                    volume: 1.0,
                }
            })
            .collect()
    }

    #[test]
    fn wr_range_neg100_to_0() {
        let out = WilliamsR::with_period(14).calculate(&rising(20)).unwrap();
        for &v in out.get("WR_14").unwrap() {
            if !v.is_nan() {
                assert!((-100.0..=0.0).contains(&v), "out of range: {v}");
            }
        }
    }

    #[test]
    fn wr_close_at_high_is_zero() {
        // close == highest_high → WR = 0.
        let bars = vec![(12.0f64, 8.0, 12.0); 14];
        let bars = candles(&bars);
        let out = WilliamsR::with_period(14).calculate(&bars).unwrap();
        let vals = out.get("WR_14").unwrap();
        assert!((vals[13] - 0.0).abs() < 1e-9, "got {}", vals[13]);
    }

    #[test]
    fn wr_close_at_low_is_neg100() {
        let bars = vec![(12.0f64, 8.0, 8.0); 14];
        let bars = candles(&bars);
        let out = WilliamsR::with_period(14).calculate(&bars).unwrap();
        let vals = out.get("WR_14").unwrap();
        assert!((vals[13] - (-100.0)).abs() < 1e-9, "got {}", vals[13]);
    }

    #[test]
    fn factory_creates_wr() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "WilliamsR");
    }
}
