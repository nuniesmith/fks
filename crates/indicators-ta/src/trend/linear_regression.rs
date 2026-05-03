//! Linear Regression Slope.
//!
//! Python source: `indicators/other/linear_regression.py :: class LinearRegressionIndicator`
//!
//! # Python algorithm (to port)
//! ```python
//! X = np.arange(self.period)
//! slopes = data["Close"].rolling(window=self.period).apply(
//!     lambda y: np.polyfit(X, y, 1)[0], raw=True
//! )
//! ```
//!
//! Output column: `"LR_slope_{period}"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput, PriceColumn};
use crate::registry::param_usize;
use crate::types::Candle;

#[derive(Debug, Clone)]
pub struct LrParams {
    /// Rolling window.  Python default: 14.
    pub period: usize,
    /// Price field.  Python default: close.
    pub column: PriceColumn,
}
impl Default for LrParams {
    fn default() -> Self {
        Self {
            period: 14,
            column: PriceColumn::Close,
        }
    }
}

#[derive(Debug, Clone)]
pub struct LinearRegression {
    pub params: LrParams,
}

impl LinearRegression {
    pub fn new(params: LrParams) -> Self {
        Self { params }
    }
    pub fn with_period(period: usize) -> Self {
        Self::new(LrParams {
            period,
            ..Default::default()
        })
    }
    fn output_key(&self) -> String {
        format!("LR_slope_{}", self.params.period)
    }

    /// OLS slope: `sum((x - x_mean)(y - y_mean)) / sum((x - x_mean)^2)`
    /// where `x = 0..period`.
    fn ols_slope(y: &[f64]) -> f64 {
        let n = y.len() as f64;
        let x_mean = (n - 1.0) / 2.0;
        let y_mean: f64 = y.iter().sum::<f64>() / n;
        let mut num = 0.0f64;
        let mut den = 0.0f64;
        for (i, &yi) in y.iter().enumerate() {
            let xi = i as f64 - x_mean;
            num += xi * (yi - y_mean);
            den += xi * xi;
        }
        if den == 0.0 { 0.0 } else { num / den }
    }
}

impl Indicator for LinearRegression {
    fn name(&self) -> &'static str {
        "LinearRegression"
    }
    fn required_len(&self) -> usize {
        self.params.period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    /// Ports `rolling(window=period).apply(lambda y: np.polyfit(X, y, 1)[0])`.
    ///
    /// OLS slope = `Σ(xᵢ − x̄)(yᵢ − ȳ) / Σ(xᵢ − x̄)²` where `xᵢ = i`.
    /// This is algebraically identical to `np.polyfit`'s degree-1 coefficient.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let prices = self.params.column.extract(candles);
        let n = prices.len();
        let p = self.params.period;
        let mut values = vec![f64::NAN; n];

        for i in (p - 1)..n {
            values[i] = Self::ols_slope(&prices[(i + 1 - p)..=i]);
        }

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(LinearRegression::new(LrParams {
        period: param_usize(params, "period", 14)?,
        ..Default::default()
    })))
}

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
    fn lr_perfect_line_slope_one() {
        // y = x → slope should be 1.0
        let closes: Vec<f64> = (0..14).map(|x| x as f64).collect();
        let out = LinearRegression::with_period(14)
            .calculate(&candles(&closes))
            .unwrap();
        let vals = out.get("LR_slope_14").unwrap();
        assert!((vals[13] - 1.0).abs() < 1e-9, "got {}", vals[13]);
    }

    #[test]
    fn lr_constant_slope_zero() {
        let closes = vec![5.0f64; 14];
        let out = LinearRegression::with_period(14)
            .calculate(&candles(&closes))
            .unwrap();
        let vals = out.get("LR_slope_14").unwrap();
        assert!(vals[13].abs() < 1e-9);
    }

    #[test]
    fn lr_leading_nans() {
        let closes: Vec<f64> = (0..20).map(|x| x as f64).collect();
        let out = LinearRegression::with_period(14)
            .calculate(&candles(&closes))
            .unwrap();
        let vals = out.get("LR_slope_14").unwrap();
        assert!(vals[0].is_nan());
        assert!(!vals[13].is_nan());
    }

    #[test]
    fn factory_creates_lr() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "LinearRegression");
    }
}
