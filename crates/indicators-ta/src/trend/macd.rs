//! Moving Average Convergence Divergence (MACD).
//!
//! Python source: `indicators/trend/macd.py :: class MACD`
//!
//! # Python algorithm (to port)
//! ```python
//! fast_ema = data[self.column].ewm(span=self.fast_period, adjust=False).mean()
//! slow_ema = data[self.column].ewm(span=self.slow_period, adjust=False).mean()
//! macd_line = fast_ema - slow_ema
//! signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
//! histogram = macd_line - signal_line
//! ```
//!
//! Output columns: `"MACD_line"`, `"MACD_signal"`, `"MACD_histogram"`.
//!
//! See also: `crate::functions::macd()` — already implemented for batch use.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::functions::{self};
use crate::indicator::{Indicator, IndicatorOutput, PriceColumn};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MacdParams {
    /// Fast EMA period.  Python default: 12.
    pub fast_period: usize,
    /// Slow EMA period.  Python default: 26.
    pub slow_period: usize,
    /// Signal line period.  Python default: 9.
    pub signal_period: usize,
    /// Price field.  Python default: `"close"`.
    pub column: PriceColumn,
}

impl Default for MacdParams {
    fn default() -> Self {
        Self {
            fast_period: 12,
            slow_period: 26,
            signal_period: 9,
            column: PriceColumn::Close,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Macd {
    pub params: MacdParams,
}

impl Macd {
    pub fn new(params: MacdParams) -> Self {
        Self { params }
    }
}

impl Default for Macd {
    fn default() -> Self {
        Self::new(MacdParams::default())
    }
}

impl Indicator for Macd {
    fn name(&self) -> &'static str {
        "MACD"
    }

    fn required_len(&self) -> usize {
        // Only need enough bars for the slow EMA to produce at least one value.
        // The signal line uses ema_nan_aware, which seeds from the first valid
        // MACD value, so it doesn't add to the minimum requirement.
        self.params.slow_period
    }

    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    /// Delegates to the existing `crate::functions::macd()`.
    ///
    /// Output key names `"MACD_line"`, `"MACD_signal"`, `"MACD_histogram"` match
    /// the Python pattern `f"{self.name}_{suffix}"` where `self.name = "MACD"`.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let prices = self.params.column.extract(candles);
        let (macd_line, signal_line, histogram) = functions::macd(
            &prices,
            self.params.fast_period,
            self.params.slow_period,
            self.params.signal_period,
        )?;

        Ok(IndicatorOutput::from_pairs([
            ("MACD_line".to_string(), macd_line),
            ("MACD_signal".to_string(), signal_line),
            ("MACD_histogram".to_string(), histogram),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(Macd::new(MacdParams {
        fast_period: crate::registry::param_usize(params, "fast_period", 12)?,
        slow_period: crate::registry::param_usize(params, "slow_period", 26)?,
        signal_period: crate::registry::param_usize(params, "signal_period", 9)?,
        column: PriceColumn::Close,
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
    fn macd_insufficient_data() {
        let macd = Macd::default();
        assert!(macd.calculate(&candles(&[1.0; 10])).is_err());
    }

    #[test]
    fn macd_output_has_three_columns() {
        let macd = Macd::default();
        let closes: Vec<f64> = (1..=50).map(|x| x as f64).collect();
        let out = macd.calculate(&candles(&closes)).unwrap();
        assert!(out.get("MACD_line").is_some(), "missing MACD_line");
        assert!(out.get("MACD_signal").is_some(), "missing MACD_signal");
        assert!(
            out.get("MACD_histogram").is_some(),
            "missing MACD_histogram"
        );
    }

    #[test]
    fn macd_histogram_is_line_minus_signal() {
        let macd = Macd::default();
        let closes: Vec<f64> = (1..=50).map(|x| x as f64).collect();
        let out = macd.calculate(&candles(&closes)).unwrap();
        let line = out.get("MACD_line").unwrap();
        let signal = out.get("MACD_signal").unwrap();
        let hist = out.get("MACD_histogram").unwrap();
        for i in 0..line.len() {
            if !line[i].is_nan() && !signal[i].is_nan() {
                assert!((hist[i] - (line[i] - signal[i])).abs() < 1e-9);
            }
        }
    }

    #[test]
    fn factory_creates_macd() {
        let params = HashMap::new();
        let ind = factory(&params).unwrap();
        assert_eq!(ind.name(), "MACD");
    }
}
