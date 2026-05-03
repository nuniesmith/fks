//! Accumulation/Distribution Line (ADL).
//!
//! Python source: `indicators/trend/accumulation_distribution_line.py :: class ADLineIndicator`
//!
//! # Python algorithm (to port)
//! ```python
//! # Money Flow Multiplier (MFM):
//! mfm = ((close - low) - (high - close)) / (high - low)
//! mfm[high == low] = 0          # avoid division by zero
//!
//! # Money Flow Volume:
//! mfv = mfm * volume
//!
//! # ADL = cumulative sum of MFV
//! adl = mfv.cumsum()
//! ```
//!
//! Output column: `"ADL"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::types::Candle;

// ── Indicator struct ──────────────────────────────────────────────────────────

/// Accumulation/Distribution Line.  No configurable parameters.
#[derive(Debug, Clone, Default)]
pub struct Adl;

impl Adl {
    pub fn new() -> Self {
        Self
    }
}

impl Indicator for Adl {
    fn name(&self) -> &'static str {
        "ADL"
    }
    fn required_len(&self) -> usize {
        1
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close", "volume"]
    }

    /// Ports `mfv.cumsum()` where `mfv = mfm * volume` and
    /// `mfm = ((close - low) - (high - close)) / (high - low)`.
    ///
    /// When `high == low` the multiplier is clamped to `0` (matching the
    /// Python `mfm[high == low] = 0` mask), so no divide-by-zero can occur.
    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let mut adl = 0.0f64;
        let values: Vec<f64> = candles
            .iter()
            .map(|c| {
                let range = c.high - c.low;
                let mfm = if range == 0.0 {
                    0.0
                } else {
                    ((c.close - c.low) - (c.high - c.close)) / range
                };
                adl += mfm * c.volume;
                adl
            })
            .collect();

        Ok(IndicatorOutput::from_pairs([("ADL".to_string(), values)]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    _params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    Ok(Box::new(Adl::new()))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn candle(h: f64, l: f64, c: f64, v: f64) -> Candle {
        Candle {
            time: 0,
            open: c,
            high: h,
            low: l,
            close: c,
            volume: v,
        }
    }

    #[test]
    fn adl_zero_range_no_panic() {
        // high == low should produce mfm=0, not a divide-by-zero
        let bars = vec![candle(5.0, 5.0, 5.0, 1000.0)];
        let out = Adl::new().calculate(&bars).unwrap();
        let vals = out.get("ADL").unwrap();
        assert_eq!(vals[0], 0.0);
    }

    #[test]
    fn adl_full_positive_bar() {
        // close==high → mfm=1, mfv=volume, adl=volume
        let bars = vec![candle(10.0, 8.0, 10.0, 500.0)];
        let out = Adl::new().calculate(&bars).unwrap();
        let vals = out.get("ADL").unwrap();
        // mfm = ((10-8)-(10-10))/(10-8) = 2/2 = 1; mfv = 500
        assert!((vals[0] - 500.0).abs() < 1e-9, "got {}", vals[0]);
    }

    #[test]
    fn adl_is_cumulative() {
        // Two identical bars: ADL[1] = 2 * ADL[0]
        let bars = vec![candle(10.0, 8.0, 9.0, 100.0); 2];
        let out = Adl::new().calculate(&bars).unwrap();
        let vals = out.get("ADL").unwrap();
        assert!((vals[1] - 2.0 * vals[0]).abs() < 1e-9);
    }

    #[test]
    fn factory_creates_adl() {
        let ind = factory(&HashMap::new()).unwrap();
        assert_eq!(ind.name(), "ADL");
    }
}
