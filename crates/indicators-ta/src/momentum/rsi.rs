//! Relative Strength Index (RSI) — Wilder's smoothed method.
//!
//! Python source: `indicators/momentum/rsi.py :: class RSI`
//!
//! # Algorithm
//!
//! 1. `delta[i] = close[i] - close[i-1]`
//! 2. **Seed** (bars 1..=period): simple mean of gains and losses.
//! 3. **Wilder smoothing** (bar > period):
//!    `avg_gain = (prev * (period-1) + gain) / period`
//! 4. `RSI = 100 - 100 / (1 + avg_gain / avg_loss)`
//!
//! This matches TA-Lib and TradingView (Wilder seeding, not SMA).
//!
//! Output column: `"RSI_{period}"` — e.g. `"RSI_14"`.

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput, PriceColumn};
use crate::registry::{param_str, param_usize};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct RsiParams {
    /// Look-back period. Wilder's original default: 14.
    pub period: usize,
    /// Price field. Default: Close.
    pub column: PriceColumn,
}

impl Default for RsiParams {
    fn default() -> Self {
        Self {
            period: 14,
            column: PriceColumn::Close,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Rsi {
    pub params: RsiParams,
}

impl Rsi {
    pub fn new(params: RsiParams) -> Self {
        Self { params }
    }
    pub fn with_period(period: usize) -> Self {
        Self::new(RsiParams {
            period,
            ..Default::default()
        })
    }
    fn output_key(&self) -> String {
        format!("RSI_{}", self.params.period)
    }
}

impl Indicator for Rsi {
    fn name(&self) -> &'static str {
        "RSI"
    }

    /// Need `period + 1` bars: `period` deltas to seed, output starts at index `period`.
    fn required_len(&self) -> usize {
        self.params.period + 1
    }

    fn required_columns(&self) -> &[&'static str] {
        &["close"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let prices = self.params.column.extract(candles);
        let n = prices.len();
        let p = self.params.period;
        let mut values = vec![f64::NAN; n];

        // ── Seed: SMA of first `p` deltas ────────────────────────────────────
        let mut avg_gain = 0.0_f64;
        let mut avg_loss = 0.0_f64;
        for i in 1..=p {
            let delta = prices[i] - prices[i - 1];
            if delta > 0.0 {
                avg_gain += delta;
            } else {
                avg_loss += -delta;
            }
        }
        avg_gain /= p as f64;
        avg_loss /= p as f64;
        values[p] = rsi_from(avg_gain, avg_loss);

        // ── Wilder smoothing for remaining bars ───────────────────────────────
        let w = (p - 1) as f64;
        for i in (p + 1)..n {
            let delta = prices[i] - prices[i - 1];
            let gain = if delta > 0.0 { delta } else { 0.0 };
            let loss = if delta < 0.0 { -delta } else { 0.0 };
            avg_gain = (avg_gain * w + gain) / p as f64;
            avg_loss = (avg_loss * w + loss) / p as f64;
            values[i] = rsi_from(avg_gain, avg_loss);
        }

        Ok(IndicatorOutput::from_pairs([(self.output_key(), values)]))
    }
}

#[inline]
fn rsi_from(avg_gain: f64, avg_loss: f64) -> f64 {
    if avg_loss == 0.0 {
        if avg_gain == 0.0 { 50.0 } else { 100.0 }
    } else {
        100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
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
        "volume" => PriceColumn::Volume,
        _ => PriceColumn::Close,
    };
    Ok(Box::new(Rsi::new(RsiParams { period, column })))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

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
    fn rsi_insufficient_data() {
        let err = Rsi::with_period(14)
            .calculate(&make_candles(&[1.0; 10]))
            .unwrap_err();
        assert!(matches!(err, IndicatorError::InsufficientData { .. }));
    }

    #[test]
    fn rsi_leading_nans() {
        let prices: Vec<f64> = (0..20).map(|i| i as f64).collect();
        let out = Rsi::with_period(14)
            .calculate(&make_candles(&prices))
            .unwrap();
        let vals = out.get("RSI_14").unwrap();
        for (i, &v) in vals.iter().enumerate().take(14) {
            assert!(v.is_nan(), "expected NaN at [{i}], got {v}");
        }
        assert!(!vals[14].is_nan());
    }

    #[test]
    fn rsi_constant_gains_is_100() {
        // All deltas positive → avg_loss=0, avg_gain>0 → RSI=100.
        let prices: Vec<f64> = (0..20).map(|i| i as f64).collect();
        let out = Rsi::with_period(14)
            .calculate(&make_candles(&prices))
            .unwrap();
        for &v in out.get("RSI_14").unwrap().iter().filter(|v| !v.is_nan()) {
            assert!((v - 100.0).abs() < 1e-9, "expected 100.0, got {v}");
        }
    }

    #[test]
    fn rsi_constant_losses_is_0() {
        // All deltas negative → avg_gain=0, avg_loss>0 → RSI=0.
        let prices: Vec<f64> = (0..20).map(|i| 100.0 - i as f64).collect();
        let out = Rsi::with_period(14)
            .calculate(&make_candles(&prices))
            .unwrap();
        for &v in out.get("RSI_14").unwrap().iter().filter(|v| !v.is_nan()) {
            assert!(v.abs() < 1e-9, "expected 0.0, got {v}");
        }
    }

    #[test]
    fn rsi_alternating_equal_moves_is_50() {
        // +1, -1, +1, -1 ... with 14 deltas: 7×(+1) and 7×(−1).
        // avg_gain = 7/14 = 0.5, avg_loss = 7/14 = 0.5 → RSI = 50 exactly.
        let mut prices = vec![100.0_f64];
        for i in 0..19 {
            let last = *prices.last().unwrap();
            prices.push(if i % 2 == 0 { last + 1.0 } else { last - 1.0 });
        }
        let out = Rsi::with_period(14)
            .calculate(&make_candles(&prices))
            .unwrap();
        assert!((out.get("RSI_14").unwrap()[14] - 50.0).abs() < 1e-9);
    }

    #[test]
    fn rsi_known_seed_value() {
        // period=3, prices=[10, 11, 9, 11].
        // Deltas: +1, -2, +2.
        // avg_gain=(1+0+2)/3=1.0, avg_loss=(0+2+0)/3=0.667
        // RSI[3] = 100 - 100/(1 + 1.0/(2/3)) = 100 - 100/2.5 = 60.0
        let out = Rsi::with_period(3)
            .calculate(&make_candles(&[10.0, 11.0, 9.0, 11.0]))
            .unwrap();
        assert!((out.get("RSI_3").unwrap()[3] - 60.0).abs() < 1e-6);
    }

    #[test]
    fn rsi_wilder_smoothing_step() {
        // Extend by one bar: prices=[10, 11, 9, 11, 10], delta[4]=-1.
        // After seed: avg_gain=1.0, avg_loss=2/3.
        // Wilder: avg_gain=(1.0*2+0)/3=2/3, avg_loss=(2/3*2+1)/3=7/9
        let out = Rsi::with_period(3)
            .calculate(&make_candles(&[10.0, 11.0, 9.0, 11.0, 10.0]))
            .unwrap();
        let ag = (1.0_f64 * 2.0) / 3.0;
        let al = (2.0_f64 / 3.0 * 2.0 + 1.0) / 3.0;
        let expected = 100.0 - 100.0 / (1.0 + ag / al);
        assert!((out.get("RSI_3").unwrap()[4] - expected).abs() < 1e-9);
    }

    #[test]
    fn rsi_stays_in_range() {
        let prices: Vec<f64> = (0..50)
            .map(|i| 100.0 + (i as f64 * 0.3).sin() * 10.0)
            .collect();
        let out = Rsi::with_period(14)
            .calculate(&make_candles(&prices))
            .unwrap();
        for &v in out.get("RSI_14").unwrap() {
            if !v.is_nan() {
                assert!((0.0..=100.0).contains(&v), "out of range: {v}");
            }
        }
    }

    #[test]
    fn factory_creates_rsi() {
        let ind = factory(&HashMap::new()).unwrap();
        assert_eq!(ind.name(), "RSI");
        assert_eq!(ind.required_len(), 15);
    }
}
