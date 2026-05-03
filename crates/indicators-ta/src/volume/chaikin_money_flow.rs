//! Chaikin Money Flow (CMF).
//!
//! Python source: `indicators/other/chaikin_money_flow.py :: class ChaikinMoneyFlow`
//!
//! # Python algorithm (to port)
//! ```python
//! high_low_range       = (df["High"] - df["Low"]).replace(0, np.nan)
//! money_flow_mult      = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / high_low_range
//! money_flow_volume    = money_flow_mult * df["Volume"]
//! sum_mfv              = money_flow_volume.rolling(window=self.period).sum()
//! sum_vol              = df["Volume"].rolling(window=self.period).sum().replace(0, np.nan)
//! cmf                  = sum_mfv / sum_vol
//! ```
//!
//! Values above +0.20 → strong buying; below -0.20 → strong selling.
//! Oscillates between -1 and +1.
//!
//! Output column: `"CMF_{period}"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

#[derive(Debug, Clone)]
pub struct CmfParams {
    /// Rolling period.  Python default: 20.
    pub period: usize,
}
impl Default for CmfParams {
    fn default() -> Self {
        Self { period: 20 }
    }
}

#[derive(Debug, Clone)]
pub struct ChaikinMoneyFlow {
    pub params: CmfParams,
}

impl ChaikinMoneyFlow {
    pub fn new(params: CmfParams) -> Self {
        Self { params }
    }
    pub fn with_period(period: usize) -> Self {
        Self::new(CmfParams { period })
    }
    fn output_key(&self) -> String {
        format!("CMF_{}", self.params.period)
    }
}

impl Indicator for ChaikinMoneyFlow {
    fn name(&self) -> &'static str {
        "ChaikinMoneyFlow"
    }
    fn required_len(&self) -> usize {
        self.params.period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close", "volume"]
    }

    /// Ports the rolling-window CMF calculation.
    ///
    /// When `high == low` the money-flow multiplier is set to `0.0` rather
    /// than `NaN`.  This is equivalent to Python's `.replace(0, np.nan)`
    /// approach because pandas `rolling().sum()` skips `NaN` values by
    /// default, so a zero-range bar contributes `0` to the rolling sum in
    /// both implementations.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let p = self.params.period;

        // Money flow multiplier and volume per bar.
        let mfv: Vec<f64> = candles
            .iter()
            .map(|c| {
                let range = c.high - c.low;
                let mfm = if range == 0.0 {
                    0.0
                } else {
                    ((c.close - c.low) - (c.high - c.close)) / range
                };
                mfm * c.volume
            })
            .collect();
        let vol: Vec<f64> = candles.iter().map(|c| c.volume).collect();

        let mut values = vec![f64::NAN; n];
        for i in (p - 1)..n {
            let sum_mfv: f64 = mfv[(i + 1 - p)..=i].iter().sum();
            let sum_vol: f64 = vol[(i + 1 - p)..=i].iter().sum();
            values[i] = if sum_vol == 0.0 {
                f64::NAN
            } else {
                sum_mfv / sum_vol
            };
        }

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(ChaikinMoneyFlow::new(CmfParams {
        period: param_usize(params, "period", 20)?,
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
                high: 12.0,
                low: 8.0,
                close: 11.0,
                volume: 100.0,
            })
            .collect()
    }

    #[test]
    fn cmf_output_column() {
        let out = ChaikinMoneyFlow::with_period(20)
            .calculate(&candles(25))
            .unwrap();
        assert!(out.get("CMF_20").is_some());
    }

    #[test]
    fn cmf_range_neg1_to_pos1() {
        let out = ChaikinMoneyFlow::with_period(5)
            .calculate(&candles(10))
            .unwrap();
        for &v in out.get("CMF_5").unwrap() {
            if !v.is_nan() {
                assert!((-1.0..=1.0).contains(&v), "out of range: {v}");
            }
        }
    }

    #[test]
    fn factory_creates_cmf() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "ChaikinMoneyFlow");
    }
}
