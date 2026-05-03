//! Volume-Weighted Average Price (VWAP).
//!
//! Python source: `indicators/trend/moving_average.py :: class VWAP`
//!              + `indicators/volume/vwap.py`
//!
//! # Python algorithm (to port)
//! ```python
//! typical_price = (data["high"] + data["low"] + data["close"]) / 3
//! volume_price  = typical_price * data["volume"]
//!
//! # Cumulative (period=None):
//! vwap = volume_price.cumsum() / data["volume"].cumsum()
//!
//! # Rolling (period=N):
//! vwap = volume_price.rolling(N).sum() / data["volume"].rolling(N).sum()
//! ```
//!
//! Output column: `"VWAP"` (cumulative) or `"VWAP_{period}"` (rolling).

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Default)]
pub struct VwapParams {
    /// Rolling window.  `None` = cumulative VWAP (session-based).
    /// Python default: `None`.
    pub period: Option<usize>,
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Vwap {
    pub params: VwapParams,
}

impl Vwap {
    pub fn new(params: VwapParams) -> Self {
        Self { params }
    }
    pub fn cumulative() -> Self {
        Self::new(VwapParams { period: None })
    }
    pub fn rolling(period: usize) -> Self {
        Self::new(VwapParams {
            period: Some(period),
        })
    }

    fn output_key(&self) -> String {
        match self.params.period {
            None => "VWAP".to_string(),
            Some(p) => format!("VWAP_{p}"),
        }
    }
}

impl Indicator for Vwap {
    fn name(&self) -> &'static str {
        "VWAP"
    }

    fn required_len(&self) -> usize {
        self.params.period.unwrap_or(1)
    }

    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close", "volume"]
    }

    /// Cumulative VWAP:  `cumsum(tp * vol) / cumsum(vol)` — no NaN warm-up.
    /// Rolling VWAP:     `rolling_sum(tp * vol, N) / rolling_sum(vol, N)` —
    ///                   `NaN` for the first `period - 1` positions.
    ///
    /// `tp` (typical price) = `(high + low + close) / 3`.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let tp: Vec<f64> = candles
            .iter()
            .map(|c| (c.high + c.low + c.close) / 3.0)
            .collect();
        let vp: Vec<f64> = candles
            .iter()
            .zip(&tp)
            .map(|(c, &t)| t * c.volume)
            .collect();
        let vol: Vec<f64> = candles.iter().map(|c| c.volume).collect();

        let values = match self.params.period {
            None => {
                // Cumulative VWAP — produces a value for every bar.
                let mut cum_vp = 0.0f64;
                let mut cum_vol = 0.0f64;
                vp.iter()
                    .zip(&vol)
                    .map(|(&v, &vol)| {
                        cum_vp += v;
                        cum_vol += vol;
                        if cum_vol == 0.0 {
                            f64::NAN
                        } else {
                            cum_vp / cum_vol
                        }
                    })
                    .collect()
            }
            Some(period) => {
                // Rolling VWAP — NaN for first `period - 1` bars.
                let mut values = vec![f64::NAN; n];
                for i in (period - 1)..n {
                    let sum_vp: f64 = vp[(i + 1 - period)..=i].iter().sum();
                    let sum_vol: f64 = vol[(i + 1 - period)..=i].iter().sum();
                    values[i] = if sum_vol == 0.0 {
                        f64::NAN
                    } else {
                        sum_vp / sum_vol
                    };
                }
                values
            }
        };

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let period = if params.contains_key("period") {
        Some(param_usize(params, "period", 0)?)
    } else {
        None
    };
    Ok(Box::new(Vwap::new(VwapParams { period })))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn candles(data: &[(f64, f64, f64, f64)]) -> Vec<Candle> {
        // (high, low, close, volume)
        data.iter()
            .enumerate()
            .map(|(i, &(h, l, c, v))| Candle {
                time: i64::try_from(i).expect("time index fits i64"),
                open: c,
                high: h,
                low: l,
                close: c,
                volume: v,
            })
            .collect()
    }

    #[test]
    fn vwap_cumulative_single_bar() {
        let bars = [(10.0, 8.0, 9.0, 100.0)];
        let out = Vwap::cumulative().calculate(&candles(&bars)).unwrap();
        let vals = out.get("VWAP").unwrap();
        // tp = (10+8+9)/3 = 9; vwap = 9*100/100 = 9
        assert!((vals[0] - 9.0).abs() < 1e-9);
    }

    #[test]
    fn vwap_rolling_output_key() {
        let bars = vec![(10.0, 8.0, 9.0, 100.0); 5];
        let out = Vwap::rolling(3).calculate(&candles(&bars)).unwrap();
        assert!(out.get("VWAP_3").is_some());
    }

    #[test]
    fn factory_default_is_cumulative() {
        let ind = factory(&HashMap::new()).unwrap();
        assert_eq!(ind.name(), "VWAP");
    }
}
