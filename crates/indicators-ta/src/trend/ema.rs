//! Exponential Moving Average (EMA).
//!
//! Python source: `indicators/trend/moving_average.py :: class EMA`
//!
//! # Python algorithm (to port)
//! ```python
//! ema = data[self.column].ewm(span=self.period, adjust=False, alpha=self.alpha).mean()
//! ```
//!
//! Note: `self.alpha = params.get("alpha", 2 / (period + 1))`
//!
//! Output column: `"EMA_{period}"`.
//!
//! See also: `crate::functions::ema()` for the existing batch implementation
//! and `crate::functions::EMA` for the existing incremental struct — both
//! can serve as the porting target for the `calculate()` body here.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::functions::{self};
use crate::indicator::{Indicator, IndicatorOutput, PriceColumn};
use crate::registry::{param_f64, param_str, param_usize};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct EmaParams {
    /// Lookback period (span).  Python default: 20.
    pub period: usize,
    /// Smoothing factor.  Python default: `2 / (period + 1)`.
    /// Pass `None` to use the standard formula.
    pub alpha: Option<f64>,
    /// Price field.  Python default: `"close"`.
    pub column: PriceColumn,
}

impl Default for EmaParams {
    fn default() -> Self {
        Self {
            period: 20,
            alpha: None,
            column: PriceColumn::Close,
        }
    }
}

impl EmaParams {
    fn effective_alpha(&self) -> f64 {
        self.alpha
            .unwrap_or_else(|| 2.0 / (self.period as f64 + 1.0))
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Ema {
    pub params: EmaParams,
}

impl Ema {
    pub fn new(params: EmaParams) -> Self {
        Self { params }
    }

    pub fn with_period(period: usize) -> Self {
        Self::new(EmaParams {
            period,
            ..Default::default()
        })
    }

    fn output_key(&self) -> String {
        format!("EMA_{}", self.params.period)
    }
}

impl Indicator for Ema {
    fn name(&self) -> &'static str {
        "EMA"
    }

    fn required_len(&self) -> usize {
        self.params.period
    }

    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    /// Ports Python `ewm(span=period, adjust=False, alpha=alpha).mean()`.
    ///
    /// Delegates to `crate::functions::ema()` when alpha matches the standard
    /// `2/(period+1)` formula, and uses a local SMA-seeded EMA loop when a
    /// custom alpha is provided.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let prices = self.params.column.extract(candles);
        let alpha = self.params.effective_alpha();
        let period = self.params.period;
        let default_alpha = 2.0 / (period as f64 + 1.0);

        let values = if (alpha - default_alpha).abs() < f64::EPSILON {
            // Fast path: delegate to the shared batch implementation.
            functions::ema(&prices, period)?
        } else {
            // Custom alpha path: SMA-seed then apply caller-supplied smoothing factor.
            ema_with_alpha(&prices, period, alpha)?
        };

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/// SMA-seeded EMA with a caller-supplied smoothing factor.
///
/// Mirrors Python `series.ewm(span=period, adjust=False, alpha=alpha).mean()`.
/// The seed (index `period-1`) is the arithmetic mean of the first `period`
/// values; subsequent values follow `ema[i] = alpha * price[i] + (1-alpha) * ema[i-1]`.
fn ema_with_alpha(prices: &[f64], period: usize, alpha: f64) -> Result<Vec<f64>, IndicatorError> {
    if prices.len() < period {
        return Err(IndicatorError::InsufficientData {
            required: period,
            available: prices.len(),
        });
    }
    let mut result = vec![f64::NAN; prices.len()];
    let seed: f64 = prices.iter().take(period).sum::<f64>() / period as f64;
    result[period - 1] = seed;
    let one_minus = 1.0 - alpha;
    for i in period..prices.len() {
        result[i] = prices[i] * alpha + result[i - 1] * one_minus;
    }
    Ok(result)
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let period = param_usize(params, "period", 20)?;
    let alpha = if params.contains_key("alpha") {
        Some(param_f64(params, "alpha", 2.0 / (period as f64 + 1.0))?)
    } else {
        None
    };
    let column = match param_str(params, "column", "close") {
        "open" => PriceColumn::Open,
        "high" => PriceColumn::High,
        "low" => PriceColumn::Low,
        _ => PriceColumn::Close,
    };
    Ok(Box::new(Ema::new(EmaParams {
        period,
        alpha,
        column,
    })))
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
    fn ema_insufficient_data() {
        let ema = Ema::with_period(5);
        assert!(ema.calculate(&candles(&[1.0, 2.0])).is_err());
    }

    #[test]
    fn ema_output_column_named_correctly() {
        let ema = Ema::with_period(3);
        let out = ema.calculate(&candles(&[10.0, 20.0, 30.0])).unwrap();
        assert!(out.get("EMA_3").is_some());
    }

    #[test]
    fn ema_seed_equals_sma() {
        // EMA at index `period-1` should equal the SMA of first `period` values.
        let closes = vec![10.0, 20.0, 30.0];
        let ema = Ema::with_period(3);
        let out = ema.calculate(&candles(&closes)).unwrap();
        let vals = out.get("EMA_3").unwrap();
        let expected_seed = (10.0 + 20.0 + 30.0) / 3.0;
        assert!((vals[2] - expected_seed).abs() < 1e-9, "got {}", vals[2]);
    }

    #[test]
    fn ema_subsequent_value() {
        // alpha = 2/(3+1) = 0.5; EMA[3] = 40*0.5 + 20*0.5 = 30
        let closes = vec![10.0, 20.0, 30.0, 40.0];
        let ema = Ema::with_period(3);
        let out = ema.calculate(&candles(&closes)).unwrap();
        let vals = out.get("EMA_3").unwrap();
        let expected = 40.0 * 0.5 + 20.0 * 0.5;
        assert!((vals[3] - expected).abs() < 1e-6, "got {}", vals[3]);
    }

    #[test]
    fn ema_custom_alpha_differs_from_default() {
        // alpha=0.1 ≠ 2/(3+1)=0.5; after the seed the two paths diverge.
        let closes = vec![10.0, 20.0, 30.0, 40.0];
        let default_out = Ema::with_period(3).calculate(&candles(&closes)).unwrap();
        let custom_out = Ema::new(EmaParams {
            period: 3,
            alpha: Some(0.1),
            column: PriceColumn::Close,
        })
        .calculate(&candles(&closes))
        .unwrap();
        let d = default_out.get("EMA_3").unwrap();
        let c = custom_out.get("EMA_3").unwrap();
        // Seed (index 2) is the same SMA regardless of alpha.
        assert!((c[2] - d[2]).abs() < 1e-9);
        // After seed, alpha=0.1 must produce a different value than alpha=0.5.
        assert!(
            (c[3] - d[3]).abs() > 1e-6,
            "custom alpha should differ: {}",
            c[3]
        );
    }

    #[test]
    fn ema_custom_alpha_correct_value() {
        // Seed = (10+20+30)/3 = 20; EMA[3] = 40*0.1 + 20*0.9 = 22.0
        let closes = vec![10.0, 20.0, 30.0, 40.0];
        let ema = Ema::new(EmaParams {
            period: 3,
            alpha: Some(0.1),
            column: PriceColumn::Close,
        });
        let out = ema.calculate(&candles(&closes)).unwrap();
        let vals = out.get("EMA_3").unwrap();
        assert!((vals[3] - 22.0).abs() < 1e-9, "got {}", vals[3]);
    }

    #[test]
    fn factory_creates_ema() {
        let params = [("period".into(), "12".into())].into();
        let ind = factory(&params).unwrap();
        assert_eq!(ind.name(), "EMA");
    }
}
