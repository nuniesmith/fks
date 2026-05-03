//! Bollinger Bands.
//!
//! Ported from `bollinger.py` :: `class BollingerBands`.
//!
//! # Algorithm
//!
//! 1. `middle[i] = SMA(prices, period)`
//! 2. `std[i]    = rolling sample std-dev (ddof=1, matches pandas)`
//! 3. `upper[i]  = middle[i] + std_dev × std[i]`
//! 4. `lower[i]  = middle[i] − std_dev × std[i]`
//! 5. `bandwidth = (upper − lower) / middle`
//! 6. `percent_b = (price − lower) / (upper − lower)`
//!
//! Output columns: `"BB_middle"`, `"BB_upper"`, `"BB_lower"`,
//! `"BB_bandwidth"`, `"BB_pct_b"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput, PriceColumn};
use crate::registry::{param_f64, param_str, param_usize};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BollingerParams {
    /// Rolling window size.  Python default: 20.
    pub period: usize,
    /// Number of standard deviations.  Python default: 2.0.
    pub std_dev: f64,
    /// Price field.  Python default: `"close"`.
    pub column: PriceColumn,
}

impl Default for BollingerParams {
    fn default() -> Self {
        Self {
            period: 20,
            std_dev: 2.0,
            column: PriceColumn::Close,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BollingerBands {
    pub params: BollingerParams,
}

impl BollingerBands {
    pub fn new(params: BollingerParams) -> Self {
        Self { params }
    }

    pub fn with_period(period: usize) -> Self {
        Self::new(BollingerParams {
            period,
            ..Default::default()
        })
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/// Rolling sample standard deviation (ddof=1), matching `pandas rolling().std()`.
fn rolling_std(prices: &[f64], period: usize) -> Vec<f64> {
    let n = prices.len();
    let mut out = vec![f64::NAN; n];
    for i in (period - 1)..n {
        let window = &prices[(i + 1 - period)..=i];
        let mean: f64 = window.iter().sum::<f64>() / period as f64;
        let var: f64 =
            window.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / (period - 1) as f64; // ddof=1
        out[i] = var.sqrt();
    }
    out
}

// ── Indicator impl ────────────────────────────────────────────────────────────

impl Indicator for BollingerBands {
    fn name(&self) -> &'static str {
        "BollingerBands"
    }
    fn required_len(&self) -> usize {
        self.params.period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let prices = self.params.column.extract(candles);
        let num_bars = prices.len();
        let period = self.params.period;
        let std_mult = self.params.std_dev;

        // Rolling SMA
        let mut middle = vec![f64::NAN; num_bars];
        for i in (period - 1)..num_bars {
            middle[i] = prices[(i + 1 - period)..=i].iter().sum::<f64>() / period as f64;
        }

        let std = rolling_std(&prices, period);

        let mut upper = vec![f64::NAN; num_bars];
        let mut lower = vec![f64::NAN; num_bars];
        let mut bandwidth = vec![f64::NAN; num_bars];
        let mut pct_b = vec![f64::NAN; num_bars];

        for i in (period - 1)..num_bars {
            let upper_val = middle[i] + std_mult * std[i];
            let lower_val = middle[i] - std_mult * std[i];
            upper[i] = upper_val;
            lower[i] = lower_val;
            bandwidth[i] = if middle[i] == 0.0 {
                f64::NAN
            } else {
                (upper_val - lower_val) / middle[i]
            };
            let band_range = upper_val - lower_val;
            pct_b[i] = if band_range == 0.0 {
                f64::NAN
            } else {
                (prices[i] - lower_val) / band_range
            };
        }

        Ok(IndicatorOutput::from_pairs([
            ("BB_middle".to_string(), middle),
            ("BB_upper".to_string(), upper),
            ("BB_lower".to_string(), lower),
            ("BB_bandwidth".to_string(), bandwidth),
            ("BB_pct_b".to_string(), pct_b),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let period = param_usize(params, "period", 20)?;
    let std_dev = param_f64(params, "std_dev", 2.0)?;
    let column = match param_str(params, "column", "close") {
        "open" => PriceColumn::Open,
        "high" => PriceColumn::High,
        "low" => PriceColumn::Low,
        _ => PriceColumn::Close,
    };
    Ok(Box::new(BollingerBands::new(BollingerParams {
        period,
        std_dev,
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
                high: c + 1.0,
                low: c - 1.0,
                close: c,
                volume: 100.0,
            })
            .collect()
    }

    #[test]
    fn bb_five_output_columns() {
        let closes = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0];
        let out = BollingerBands::with_period(5)
            .calculate(&candles(&closes))
            .unwrap();
        assert!(out.get("BB_middle").is_some());
        assert!(out.get("BB_upper").is_some());
        assert!(out.get("BB_lower").is_some());
        assert!(out.get("BB_bandwidth").is_some());
        assert!(out.get("BB_pct_b").is_some());
    }

    #[test]
    fn bb_upper_always_above_lower() {
        let closes: Vec<f64> = (1..=20).map(|x| x as f64).collect();
        let out = BollingerBands::with_period(5)
            .calculate(&candles(&closes))
            .unwrap();
        let upper = out.get("BB_upper").unwrap();
        let lower = out.get("BB_lower").unwrap();
        for i in 4..20 {
            assert!(upper[i] >= lower[i], "upper < lower at {i}");
        }
    }

    #[test]
    fn bb_correct_warm_up() {
        let closes = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let out = BollingerBands::with_period(5)
            .calculate(&candles(&closes))
            .unwrap();
        let mid = out.get("BB_middle").unwrap();
        for (i, &v) in mid.iter().enumerate().take(4) {
            assert!(v.is_nan(), "expected NaN at {i}");
        }
        assert!(!mid[4].is_nan());
    }

    #[test]
    fn bb_constant_prices_bandwidth_zero() {
        let closes = vec![10.0f64; 10];
        let out = BollingerBands::with_period(5)
            .calculate(&candles(&closes))
            .unwrap();
        let bw = out.get("BB_bandwidth").unwrap();
        // std = 0 → upper == lower == middle → bandwidth = 0
        assert!(bw[9].abs() < 1e-9 || bw[9].is_nan());
    }

    #[test]
    fn bb_middle_equals_sma() {
        // SMA(5) of [1..5] = 3.0
        let closes = [1.0, 2.0, 3.0, 4.0, 5.0];
        let out = BollingerBands::with_period(5)
            .calculate(&candles(&closes))
            .unwrap();
        let mid = out.get("BB_middle").unwrap();
        assert!((mid[4] - 3.0).abs() < 1e-9, "SMA mismatch: {}", mid[4]);
    }

    #[test]
    fn factory_creates_bollinger() {
        assert_eq!(factory(&HashMap::new()).unwrap().name(), "BollingerBands");
    }
}
