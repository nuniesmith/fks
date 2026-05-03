//! Weighted Moving Average (WMA).
//!
//! Python source: `indicators/trend/moving_average.py :: class WMA`
//!              + `indicators/trend/weighted_moving_average.py :: class WMA`
//!
//! # Python algorithm (to port)
//! ```python
//! weights = np.arange(1, self.period + 1)          # [1, 2, ..., period]
//! wma = data[self.column].rolling(window=self.period).apply(
//!     lambda x: np.sum(weights * x) / weights.sum(), raw=True
//! )
//! ```
//!
//! Weight for index `i` (0-based within window) = `i + 1`.
//! Denominator = `period * (period + 1) / 2`.
//!
//! Output column: `"WMA_{period}"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput, PriceColumn};
use crate::registry::{param_str, param_usize};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct WmaParams {
    /// Lookback period.  Python default: 14 (weighted_moving_average.py) / 20 (moving_average.py).
    pub period: usize,
    /// Price field.  Python default: `"close"`.
    pub column: PriceColumn,
}

impl Default for WmaParams {
    fn default() -> Self {
        Self {
            period: 14,
            column: PriceColumn::Close,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Wma {
    pub params: WmaParams,
}

impl Wma {
    pub fn new(params: WmaParams) -> Self {
        Self { params }
    }

    pub fn with_period(period: usize) -> Self {
        Self::new(WmaParams {
            period,
            ..Default::default()
        })
    }

    fn output_key(&self) -> String {
        format!("WMA_{}", self.params.period)
    }
}

impl Indicator for Wma {
    fn name(&self) -> &'static str {
        "WMA"
    }
    fn required_len(&self) -> usize {
        self.params.period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    /// Ports `rolling(window=period).apply(lambda x: np.sum(weights * x) / weights.sum())`.
    ///
    /// Weights are linear: position `j` (0-based within the window) receives
    /// weight `j + 1`.  Denominator = `period * (period + 1) / 2`.
    /// Produces `NaN` for the first `period - 1` positions.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let prices = self.params.column.extract(candles);
        let period = self.params.period;
        let n = prices.len();
        let weight_sum = (period * (period + 1) / 2) as f64;

        let mut values = vec![f64::NAN; n];

        for i in (period - 1)..n {
            let window = &prices[(i + 1 - period)..=i];
            let weighted: f64 = window
                .iter()
                .enumerate()
                .map(|(j, &p)| (j + 1) as f64 * p)
                .sum();
            values[i] = weighted / weight_sum;
        }

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let period = param_usize(params, "period", 14)?;
    let column = match param_str(params, "column", "close") {
        "open" => PriceColumn::Open,
        "high" => PriceColumn::High,
        "low" => PriceColumn::Low,
        _ => PriceColumn::Close,
    };
    Ok(Box::new(Wma::new(WmaParams { period, column })))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn candles(closes: &[f64]) -> Vec<Candle> {
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
    fn wma_insufficient_data() {
        assert!(
            Wma::with_period(5)
                .calculate(&candles(&[1.0, 2.0]))
                .is_err()
        );
    }

    #[test]
    fn wma_period3_known_value() {
        // weights [1,2,3], sum=6; prices [1,2,3] → (1+4+9)/6 = 14/6 ≈ 2.333
        let out = Wma::with_period(3)
            .calculate(&candles(&[1.0, 2.0, 3.0]))
            .unwrap();
        let vals = out.get("WMA_3").unwrap();
        let expected = (1.0 * 1.0 + 2.0 * 2.0 + 3.0 * 3.0) / 6.0;
        assert!((vals[2] - expected).abs() < 1e-9, "got {}", vals[2]);
    }

    #[test]
    fn wma_leading_nans() {
        let out = Wma::with_period(3)
            .calculate(&candles(&[1.0, 2.0, 3.0, 4.0]))
            .unwrap();
        let vals = out.get("WMA_3").unwrap();
        assert!(vals[0].is_nan());
        assert!(vals[1].is_nan());
        assert!(!vals[2].is_nan());
    }

    #[test]
    fn factory_creates_wma() {
        let params = [("period".into(), "10".into())].into();
        assert_eq!(factory(&params).unwrap().name(), "WMA");
    }
}
