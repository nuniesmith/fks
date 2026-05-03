//! Elder Ray Index.
//!
//! Python source: `indicators/other/elder_ray_index.py :: class ElderRayIndexIndicator`
//!
//! # Python algorithm (to port)
//! ```python
//! ema        = data["Close"].ewm(span=self.fast_period, adjust=False).mean()
//! bull_power = data["High"] - ema
//! bear_power = data["Low"]  - ema
//! ```
//!
//! Output columns: `"ElderRay_bull"`, `"ElderRay_bear"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::functions::{self};
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

#[derive(Debug, Clone)]
pub struct ElderRayParams {
    /// EMA period for the base line.  Python default: 14.
    pub fast_period: usize,
}
impl Default for ElderRayParams {
    fn default() -> Self {
        Self { fast_period: 14 }
    }
}

#[derive(Debug, Clone)]
pub struct ElderRayIndex {
    pub params: ElderRayParams,
}

impl ElderRayIndex {
    pub fn new(params: ElderRayParams) -> Self {
        Self { params }
    }
    pub fn with_period(period: usize) -> Self {
        Self::new(ElderRayParams {
            fast_period: period,
        })
    }
}

impl Indicator for ElderRayIndex {
    fn name(&self) -> &'static str {
        "ElderRayIndex"
    }
    fn required_len(&self) -> usize {
        self.params.fast_period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close"]
    }

    /// Ports `ema = Close.ewm(span=period, adjust=False).mean()` then
    /// `bull = High - ema` and `bear = Low - ema`.
    ///
    /// # Note on EMA seeding
    /// Python's `ewm(adjust=False)` seeds the EMA with the very first close
    /// value and emits a value for every bar (no leading `NaN` warm-up).
    /// `functions::ema` may use a different seeding strategy (e.g. SMA over
    /// the first `period` bars), so the first `fast_period - 1` rows can
    /// differ slightly between the two implementations.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let close: Vec<f64> = candles.iter().map(|c| c.close).collect();
        let high: Vec<f64> = candles.iter().map(|c| c.high).collect();
        let low: Vec<f64> = candles.iter().map(|c| c.low).collect();

        // Use ema_nan_aware to match Python's ewm(span=period, adjust=False),
        // which seeds from the first close value rather than an SMA over the
        // first `period` bars.  This aligns with the Python docstring above.
        let ema = functions::ema_nan_aware(&close, self.params.fast_period)?;

        let bull: Vec<f64> = high.iter().zip(&ema).map(|(&h, &e)| h - e).collect();
        let bear: Vec<f64> = low.iter().zip(&ema).map(|(&l, &e)| l - e).collect();

        Ok(IndicatorOutput::from_pairs([
            ("ElderRay_bull".to_string(), bull),
            ("ElderRay_bear".to_string(), bear),
        ]))
    }
}

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(ElderRayIndex::new(ElderRayParams {
        fast_period: param_usize(params, "fast_period", 14)?,
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
                close: 10.0 + i as f64 * 0.1,
                volume: 100.0,
            })
            .collect()
    }

    #[test]
    fn elder_ray_two_columns() {
        let out = ElderRayIndex::with_period(14)
            .calculate(&candles(20))
            .unwrap();
        assert!(out.get("ElderRay_bull").is_some());
        assert!(out.get("ElderRay_bear").is_some());
    }

    #[test]
    fn bull_power_is_high_minus_ema() {
        // Bull power must always be >= bear power (high >= low).
        let out = ElderRayIndex::with_period(5)
            .calculate(&candles(20))
            .unwrap();
        let bull = out.get("ElderRay_bull").unwrap();
        let bear = out.get("ElderRay_bear").unwrap();
        for i in 5..20 {
            if !bull[i].is_nan() {
                assert!(bull[i] >= bear[i], "bull < bear at {i}");
            }
        }
    }

    #[test]
    fn factory_creates_elder_ray() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "ElderRayIndex");
    }
}
