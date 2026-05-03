//! Core `Indicator` trait and `IndicatorOutput` type.
//!
//! Mirrors `indicators/base.py`:
//! - `Indicator` ↔ `class Indicator(Component, ABC)`
//! - `IndicatorOutput` ↔ `pd.DataFrame` return value
//! - `required_columns()` ↔ `@classmethod required_columns()`
//! - `calculate()` ↔ `def calculate(self, data, price_column)`
//!
//! Every indicator in `trend/`, `momentum/`, `volume/`, and `other/`
//! must implement this trait.  The registry (`registry.rs`) stores
//! `Box<dyn Indicator>` values so they can be created by name at
//! runtime, matching Python's `@register_indicator` / `IndicatorRegistry`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::types::Candle;

// ── IndicatorOutput ───────────────────────────────────────────────────────────

/// Named column output, analogous to `pd.DataFrame` returned by Python `calculate()`.
///
/// Keys are column names such as `"SMA_20"`, `"MACD_line"`, `"ATR_14"`.
/// Values are aligned `Vec<f64>` of the same length as the input slice.
/// Leading warm-up entries are `f64::NAN`.
#[derive(Debug, Clone, Default)]
pub struct IndicatorOutput {
    columns: HashMap<String, Vec<f64>>,
}

impl IndicatorOutput {
    /// Create an empty output.
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert a named column.
    pub fn insert(&mut self, name: impl Into<String>, values: Vec<f64>) {
        self.columns.insert(name.into(), values);
    }

    /// Build from an iterator of `(name, values)` pairs.
    pub fn from_pairs<K: Into<String>>(pairs: impl IntoIterator<Item = (K, Vec<f64>)>) -> Self {
        let mut out = Self::new();
        for (k, v) in pairs {
            out.insert(k, v);
        }
        out
    }

    /// Get the values for a named column.
    pub fn get(&self, name: &str) -> Option<&[f64]> {
        self.columns.get(name).map(Vec::as_slice)
    }

    /// Get the *last* (most recent) value of a named column, skipping `NaN`.
    ///
    /// Mirrors Python's `indicator.get_value(-1)`.
    pub fn latest(&self, name: &str) -> Option<f64> {
        self.columns
            .get(name)?
            .iter()
            .rev()
            .find(|v| !v.is_nan())
            .copied()
    }

    /// All column names present in this output.
    pub fn columns(&self) -> impl Iterator<Item = &str> {
        self.columns.keys().map(String::as_str)
    }

    /// Number of rows (length of any column; all columns are guaranteed equal length).
    pub fn len(&self) -> usize {
        self.columns.values().next().map_or(0, Vec::len)
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Consume into the underlying map.
    pub fn into_inner(self) -> HashMap<String, Vec<f64>> {
        self.columns
    }
}

// ── Indicator trait ───────────────────────────────────────────────────────────

/// The core trait every indicator must implement.
///
/// Analogous to `indicators/base.py :: class Indicator(ABC)`.
///
/// # Implementing an indicator
///
/// ```rust,ignore
/// use crate::indicator::{Indicator, IndicatorOutput};
/// use crate::error::IndicatorError;
/// use crate::types::Candle;
///
/// pub struct Sma {
///     pub period: usize,
///     pub column: PriceColumn,
/// }
///
/// impl Indicator for Sma {
///     fn name(&self) -> &str { "SMA" }
///
///     fn required_len(&self) -> usize { self.period }
///
///     fn required_columns(&self) -> &[&str] { &["close"] }
///
///     fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
///     }
/// }
/// ```
pub trait Indicator: Send + Sync + std::fmt::Debug {
    /// Short canonical name, e.g. `"SMA"`, `"RSI"`, `"MACD"`.
    fn name(&self) -> &'static str;

    /// Minimum number of candles required before output is non-`NaN`.
    /// Mirrors Python's implicit warm-up period used for validation.
    fn required_len(&self) -> usize;

    /// Which OHLCV fields this indicator reads.
    ///
    /// Mirrors `@classmethod required_columns()` in Python.
    /// Valid values: `"open"`, `"high"`, `"low"`, `"close"`, `"volume"`.
    fn required_columns(&self) -> &[&'static str];

    /// Compute the indicator over a full candle slice (batch mode).
    ///
    /// Mirrors `def calculate(self, data: pd.DataFrame, price_column) -> pd.DataFrame`.
    ///
    /// - Returns `IndicatorOutput` with one or more named columns.
    /// - Leading warm-up rows should be `f64::NAN`.
    /// - Returns `Err(IndicatorError::InsufficientData)` if `candles.len() < required_len()`.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError>;

    /// Validate that enough data was supplied, returning a descriptive error if not.
    ///
    /// Call this at the top of every `calculate()` implementation.
    fn check_len(&self, candles: &[Candle]) -> Result<(), IndicatorError> {
        let required = self.required_len();
        if candles.len() < required {
            Err(IndicatorError::InsufficientData {
                required,
                available: candles.len(),
            })
        } else {
            Ok(())
        }
    }
}

// ── PriceColumn helper ────────────────────────────────────────────────────────

/// Which single OHLCV field to extract as a price series.
///
/// Mirrors the `column` / `price_column` parameter in Python indicators.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum PriceColumn {
    Open,
    High,
    Low,
    #[default]
    Close,
    Volume,
    /// `(High + Low + Close) / 3`
    TypicalPrice,
    /// `(High + Low) / 2`
    HL2,
}

impl PriceColumn {
    /// Extract the column as a `Vec<f64>` from a candle slice.
    pub fn extract(self, candles: &[Candle]) -> Vec<f64> {
        candles
            .iter()
            .map(|c| match self {
                PriceColumn::Open => c.open,
                PriceColumn::High => c.high,
                PriceColumn::Low => c.low,
                PriceColumn::Close => c.close,
                PriceColumn::Volume => c.volume,
                PriceColumn::TypicalPrice => (c.high + c.low + c.close) / 3.0,
                PriceColumn::HL2 => (c.high + c.low) / 2.0,
            })
            .collect()
    }

    pub fn as_str(self) -> &'static str {
        match self {
            PriceColumn::Open => "open",
            PriceColumn::High => "high",
            PriceColumn::Low => "low",
            PriceColumn::Close => "close",
            PriceColumn::Volume => "volume",
            PriceColumn::TypicalPrice => "typical_price",
            PriceColumn::HL2 => "hl2",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn indicator_output_insert_and_get() {
        let mut out = IndicatorOutput::new();
        out.insert("SMA_20", vec![f64::NAN, f64::NAN, 10.0, 12.0]);
        assert_eq!(out.len(), 4);
        assert_eq!(out.latest("SMA_20"), Some(12.0));
        assert!(out.get("MISSING").is_none());
    }

    #[test]
    fn indicator_output_from_pairs() {
        let out = IndicatorOutput::from_pairs([
            ("MACD_line", vec![1.0, 2.0]),
            ("MACD_signal", vec![0.5, 1.5]),
        ]);
        assert!(out.get("MACD_line").is_some());
        assert!(out.get("MACD_signal").is_some());
    }

    #[test]
    fn price_column_extract() {
        let candle = Candle {
            time: 0,
            open: 1.0,
            high: 4.0,
            low: 2.0,
            close: 3.0,
            volume: 100.0,
        };
        let candles = vec![candle];
        assert_eq!(PriceColumn::Close.extract(&candles), vec![3.0]);
        assert_eq!(
            PriceColumn::TypicalPrice.extract(&candles),
            vec![(4.0 + 2.0 + 3.0) / 3.0]
        );
    }
}
