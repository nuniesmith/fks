//! Average True Range (ATR).
//!
//! Python source: `indicators/trend/volatility/atr.py :: class ATR`
//!
//! # Python algorithm (to port)
//! ```python
//! high_low        = data["high"] - data["low"]
//! high_close_prev = abs(data["high"] - data["close"].shift(1))
//! low_close_prev  = abs(data["low"]  - data["close"].shift(1))
//! tr  = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
//! atr = tr.rolling(period).mean()           # method=="sma"
//! # or:
//! atr = tr.ewm(span=period, adjust=False).mean()  # method=="ema"
//!
//! normalized_atr = atr / data["close"] * 100   # percentage
//! ```
//!
//! Output columns: `"ATR_{period}"`, `"ATR_{period}_normalized"`.
//!
//! See also: `crate::functions::atr()` and `crate::functions::true_range()`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::functions::{self};
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::{param_str, param_usize};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AtrMethod {
    Sma,
    Ema,
}

#[derive(Debug, Clone)]
pub struct AtrParams {
    /// Period.  Python default: 14.
    pub period: usize,
    /// Smoothing method.  Python default: `"sma"`.
    pub method: AtrMethod,
}

impl Default for AtrParams {
    fn default() -> Self {
        Self {
            period: 14,
            method: AtrMethod::Sma,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Atr {
    pub params: AtrParams,
}

impl Atr {
    pub fn new(params: AtrParams) -> Self {
        Self { params }
    }
    pub fn with_period(period: usize) -> Self {
        Self::new(AtrParams {
            period,
            ..Default::default()
        })
    }

    fn output_key(&self) -> String {
        format!("ATR_{}", self.params.period)
    }
    fn norm_key(&self) -> String {
        format!("ATR_{}_normalized", self.params.period)
    }
}

impl Indicator for Atr {
    fn name(&self) -> &'static str {
        "ATR"
    }
    fn required_len(&self) -> usize {
        self.params.period + 1
    } // need prev close
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close"]
    }

    /// Ports the Python ATR calculation.
    ///
    /// True range = `max(H−L, |H−prev_C|, |L−prev_C|)`.  For the first bar
    /// there is no previous close, so `functions::true_range` is expected to
    /// use `H−L` alone (matching pandas `skipna=True` max behaviour).
    ///
    /// SMA path: `tr.rolling(period).mean()` — `NaN` for first `period` bars.
    /// EMA path: `tr.ewm(span=period, adjust=False).mean()` — value from bar 0.
    ///
    /// Normalised ATR = `atr / close * 100` (percentage of price).
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let high: Vec<f64> = candles.iter().map(|c| c.high).collect();
        let low: Vec<f64> = candles.iter().map(|c| c.low).collect();
        let close: Vec<f64> = candles.iter().map(|c| c.close).collect();

        let tr = functions::true_range(&high, &low, &close)?;

        let atr_vals = match self.params.method {
            // ema_nan_aware seeds from the first TR value (adjust=False),
            // matching Python's tr.ewm(span=period, adjust=False).mean().
            AtrMethod::Ema => functions::ema_nan_aware(&tr, self.params.period)?,
            AtrMethod::Sma => functions::sma(&tr, self.params.period)?,
        };

        let norm: Vec<f64> = atr_vals
            .iter()
            .zip(&close)
            .map(|(&a, &c)| if c == 0.0 { f64::NAN } else { a / c * 100.0 })
            .collect();

        Ok(IndicatorOutput::from_pairs([
            (self.output_key(), atr_vals),
            (self.norm_key(), norm),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let period = param_usize(params, "period", 14)?;
    let method = match param_str(params, "method", "sma") {
        "ema" => AtrMethod::Ema,
        _ => AtrMethod::Sma,
    };
    Ok(Box::new(Atr::new(AtrParams { period, method })))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

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

    #[test]
    fn atr_output_has_both_columns() {
        let bars: Vec<(f64, f64, f64)> = (1..=20)
            .map(|i| (i as f64 + 1.0, i as f64 - 1.0, i as f64))
            .collect();
        let atr = Atr::with_period(5);
        let out = atr.calculate(&candles(&bars)).unwrap();
        assert!(out.get("ATR_5").is_some());
        assert!(out.get("ATR_5_normalized").is_some());
    }

    #[test]
    fn atr_insufficient_data() {
        assert!(
            Atr::with_period(14)
                .calculate(&candles(&[(10.0, 8.0, 9.0)]))
                .is_err()
        );
    }

    #[test]
    fn atr_normalized_is_percentage() {
        let bars: Vec<(f64, f64, f64)> = (1..=20)
            .map(|i| (i as f64 + 1.0, i as f64 - 1.0, i as f64))
            .collect();
        let atr = Atr::with_period(5);
        let out = atr.calculate(&candles(&bars)).unwrap();
        let atr_vals = out.get("ATR_5").unwrap();
        let norm_vals = out.get("ATR_5_normalized").unwrap();
        let close: Vec<f64> = bars.iter().map(|&(_, _, c)| c).collect();
        for i in 0..bars.len() {
            if !atr_vals[i].is_nan() {
                let expected = atr_vals[i] / close[i] * 100.0;
                assert!((norm_vals[i] - expected).abs() < 1e-9);
            }
        }
    }

    #[test]
    fn factory_creates_atr() {
        let params = [
            ("period".into(), "14".into()),
            ("method".into(), "ema".into()),
        ]
        .into();
        let ind = factory(&params).unwrap();
        assert_eq!(ind.name(), "ATR");
    }
}
