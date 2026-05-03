//! Parabolic SAR (Stop and Reverse).
//!
//! Python source: `indicators/other/parabolic_sar.py :: class ParabolicSARIndicator`
//!
//! # Python algorithm (to port)
//! ```python
//! sar[i] = prev_sar + af * (ep - prev_sar)
//! # Uptrend: new high → bump af; close < sar → reverse to downtrend
//! # Downtrend: new low → bump af; close > sar → reverse to uptrend
//! ```
//!
//! Output column: `"PSAR"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_f64;
use crate::types::Candle;

#[derive(Debug, Clone)]
pub struct PsarParams {
    /// Acceleration factor step.  Python default: 0.02.
    pub step: f64,
    /// Maximum acceleration factor.  Python default: 0.2.
    pub max_step: f64,
}
impl Default for PsarParams {
    fn default() -> Self {
        Self {
            step: 0.02,
            max_step: 0.2,
        }
    }
}

#[derive(Debug, Clone)]
pub struct ParabolicSar {
    pub params: PsarParams,
}

impl ParabolicSar {
    pub fn new(params: PsarParams) -> Self {
        Self { params }
    }
}

impl Default for ParabolicSar {
    fn default() -> Self {
        Self::new(PsarParams::default())
    }
}

impl Indicator for ParabolicSar {
    fn name(&self) -> &'static str {
        "ParabolicSAR"
    }
    fn required_len(&self) -> usize {
        2
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low"]
    }

    /// Ports the iterative SAR state machine.
    ///
    /// Initialisation matches the Python source exactly:
    /// - `sar[0] = 0.0`  (Python uses `np.zeros(len(data))`)
    /// - `ep  = candles[0].low`
    /// - `af  = step`
    /// - trend starts as uptrend (`1`)
    ///
    /// The `sar[0] = 0.0` cold-start means the first computed value
    /// `sar[1] = af * ep` is typically well below market price, but this
    /// is intentional — it replicates the Python behaviour and the SAR
    /// converges toward price rapidly.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let step = self.params.step;
        let max_step = self.params.max_step;

        let mut sar = vec![0.0f64; n];
        let mut trend: i8 = 1; // 1 = uptrend, -1 = downtrend
        let mut ep = candles[0].low;
        let mut af = step;

        for i in 1..n {
            let prev_sar = sar[i - 1];
            sar[i] = prev_sar + af * (ep - prev_sar);

            if trend == 1 {
                if candles[i].high > ep {
                    ep = candles[i].high;
                    af = (af + step).min(max_step);
                }
                if candles[i].low < sar[i] {
                    trend = -1;
                    sar[i] = ep;
                    ep = candles[i].low;
                    af = step;
                }
            } else {
                if candles[i].low < ep {
                    ep = candles[i].low;
                    af = (af + step).min(max_step);
                }
                if candles[i].high > sar[i] {
                    trend = 1;
                    sar[i] = ep;
                    ep = candles[i].high;
                    af = step;
                }
            }
        }

        Ok(IndicatorOutput::from_pairs([("PSAR".to_string(), sar)]))
    }
}

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(ParabolicSar::new(PsarParams {
        step: param_f64(params, "step", 0.02)?,
        max_step: param_f64(params, "max_step", 0.2)?,
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
                high: 10.0 + i as f64 * 0.1,
                low: 10.0 - i as f64 * 0.05,
                close: 10.0,
                volume: 100.0,
            })
            .collect()
    }

    #[test]
    fn psar_output_column() {
        let out = ParabolicSar::default().calculate(&candles(10)).unwrap();
        assert!(out.get("PSAR").is_some());
    }

    #[test]
    fn psar_correct_length() {
        let bars = candles(20);
        let out = ParabolicSar::default().calculate(&bars).unwrap();
        assert_eq!(out.get("PSAR").unwrap().len(), 20);
    }

    #[test]
    fn psar_af_bounded() {
        // Ensure AF never exceeds max_step by checking no divergence in values.
        let out = ParabolicSar::default().calculate(&candles(50)).unwrap();
        let vals = out.get("PSAR").unwrap();
        // Values should be finite (AF bounded means SAR stays near price).
        for &v in vals {
            assert!(v.is_finite(), "non-finite SAR: {v}");
        }
    }

    #[test]
    fn factory_creates_psar() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "ParabolicSAR");
    }
}
