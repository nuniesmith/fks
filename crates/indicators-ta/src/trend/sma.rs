//! Simple Moving Average (SMA).
//!
//! Python source: `indicators/trend/moving_average.py :: class SMA`
//!
//! # Python algorithm (to port)
//! ```python
//! sma = data[self.column].rolling(window=self.period).mean()
//! return pd.DataFrame({f"{self.name}_{self.period}": sma}, index=data.index)
//! ```
//!
//! Output column: `"SMA_{period}"` — e.g. `"SMA_20"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput, PriceColumn};
use crate::registry::{param_str, param_usize};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

/// Parameters for the SMA indicator.
///
/// Mirrors Python: `self.period = params.get("period", 20)` etc.
#[derive(Debug, Clone)]
pub struct SmaParams {
    /// Rolling window size.  Python default: 20.
    pub period: usize,
    /// Which OHLCV field to average.  Python default: `"close"`.
    pub column: PriceColumn,
}

impl Default for SmaParams {
    fn default() -> Self {
        Self {
            period: 20,
            column: PriceColumn::Close,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

/// Simple Moving Average.
///
/// Calculates the arithmetic mean of prices over a sliding window.
///
/// # Example
/// ```rust,ignore
/// let sma = Sma::new(SmaParams { period: 20, ..Default::default() });
/// let output = sma.calculate(&candles)?;
/// let values = output.get("SMA_20").unwrap();
/// ```
#[derive(Debug, Clone)]
pub struct Sma {
    pub params: SmaParams,
}

impl Sma {
    pub fn new(params: SmaParams) -> Self {
        Self { params }
    }

    /// Convenience constructor with just a period.
    pub fn with_period(period: usize) -> Self {
        Self::new(SmaParams {
            period,
            ..Default::default()
        })
    }

    /// Column label used in `IndicatorOutput`.
    /// Mirrors Python: `f"{self.name}_{self.period}"`.
    fn output_key(&self) -> String {
        format!("SMA_{}", self.params.period)
    }
}

impl Indicator for Sma {
    fn name(&self) -> &'static str {
        "SMA"
    }

    fn required_len(&self) -> usize {
        self.params.period
    }

    fn required_columns(&self) -> &[&'static str] {
        &["close"] // adjusts if column != Close, but close is the default
    }

    /// Ports `data[self.column].rolling(window=self.period).mean()`.
    ///
    /// Produces `NaN` for the first `period - 1` positions (matching pandas
    /// `rolling(window=N)` default of `min_periods=N`), then the arithmetic
    /// mean of the most recent `period` prices.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let prices = self.params.column.extract(candles);
        let period = self.params.period;
        let n = prices.len();

        let mut values = vec![f64::NAN; n];

        for i in (period - 1)..n {
            let sum: f64 = prices[(i + 1 - period)..=i].iter().sum();
            values[i] = sum / period as f64;
        }

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

/// Factory function registered under `"sma"` in the global registry.
pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let period = param_usize(params, "period", 20)?;
    let column = match param_str(params, "column", "close") {
        "open" => PriceColumn::Open,
        "high" => PriceColumn::High,
        "low" => PriceColumn::Low,
        "volume" => PriceColumn::Volume,
        _ => PriceColumn::Close,
    };
    Ok(Box::new(Sma::new(SmaParams { period, column })))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::Candle;

    fn make_candles(closes: &[f64]) -> Vec<Candle> {
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
    fn sma_insufficient_data() {
        let sma = Sma::with_period(5);
        let err = sma.calculate(&make_candles(&[1.0, 2.0])).unwrap_err();
        assert!(matches!(err, IndicatorError::InsufficientData { .. }));
    }

    #[test]
    fn sma_output_key() {
        let sma = Sma::with_period(20);
        assert_eq!(sma.output_key(), "SMA_20");
    }

    #[test]
    fn sma_first_value_is_nan() {
        let closes = vec![10.0, 11.0, 12.0, 13.0, 14.0];
        let sma = Sma::with_period(5);
        let out = sma.calculate(&make_candles(&closes)).unwrap();
        let vals = out.get("SMA_5").unwrap();
        assert!(vals[0].is_nan());
        assert!(vals[3].is_nan());
    }

    #[test]
    fn sma_last_value_correct() {
        // SMA(3) of [10, 20, 30] = 20
        let closes = vec![10.0, 20.0, 30.0];
        let sma = Sma::with_period(3);
        let out = sma.calculate(&make_candles(&closes)).unwrap();
        let vals = out.get("SMA_3").unwrap();
        assert!(
            (vals[2] - 20.0).abs() < 1e-9,
            "expected 20.0, got {}",
            vals[2]
        );
    }

    #[test]
    fn sma_rolling_window() {
        // [1,2,3,4,5], period=3 → NaN, NaN, 2.0, 3.0, 4.0
        let closes = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let sma = Sma::with_period(3);
        let out = sma.calculate(&make_candles(&closes)).unwrap();
        let vals = out.get("SMA_3").unwrap();
        assert!((vals[2] - 2.0).abs() < 1e-9);
        assert!((vals[3] - 3.0).abs() < 1e-9);
        assert!((vals[4] - 4.0).abs() < 1e-9);
    }

    #[test]
    fn factory_creates_sma() {
        let params = [("period".into(), "10".into())].into();
        let ind = factory(&params).unwrap();
        assert_eq!(ind.name(), "SMA");
        assert_eq!(ind.required_len(), 10);
    }
}
