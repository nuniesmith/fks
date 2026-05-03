//! Volume Zone Oscillator (VZO).
//!
//! Computes: `100 × (rolling_sum(pos_vol) − rolling_sum(neg_vol)) / rolling_sum(total_vol)`
//!
//! - `pos_vol` = bar volume when close > prev_close, else 0
//! - `neg_vol` = bar volume when close < prev_close, else 0
//!
//! Output column: `vzo_{period}` (range approximately −100 to +100).

use std::collections::HashMap;

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

// ── Indicator struct ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct VolumeZoneOscillator {
    pub period: usize,
}

impl VolumeZoneOscillator {
    pub fn new(period: usize) -> Self {
        Self { period }
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let period = param_usize(params, "period", 14)?;
    Ok(Box::new(VolumeZoneOscillator::new(period)))
}

// ── Indicator impl ────────────────────────────────────────────────────────────

impl Indicator for VolumeZoneOscillator {
    fn name(&self) -> &'static str {
        "VZO"
    }

    fn required_len(&self) -> usize {
        // Need `period` bars of direction-split volume plus one prior close to
        // compute the first diff, so the window fills after `period + 1` candles.
        self.period + 1
    }

    fn required_columns(&self) -> &[&'static str] {
        &["close", "volume"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;

        let n = candles.len();
        let p = self.period;
        let mut out = vec![f64::NAN; n];

        // Rolling sums over a sliding window of width `p`.
        // We accumulate three running totals and subtract the element that
        // falls out of the back of the window — O(n) without a VecDeque.
        let mut sum_pos = 0.0_f64;
        let mut sum_neg = 0.0_f64;
        let mut sum_tot = 0.0_f64;

        // Temporary per-bar splits (need random access for the drop step).
        let mut pos_vols = vec![0.0_f64; n];
        let mut neg_vols = vec![0.0_f64; n];

        for i in 0..n {
            let vol = candles[i].volume;
            let close = candles[i].close;

            // diff: undefined for the very first bar → treat as neutral (0 vol split).
            let (pv, nv) = if i == 0 {
                (0.0, 0.0)
            } else {
                let prev = candles[i - 1].close;
                if close > prev {
                    (vol, 0.0)
                } else if close < prev {
                    (0.0, vol)
                } else {
                    (0.0, 0.0) // flat close — neutral, same as original logic
                }
            };
            pos_vols[i] = pv;
            neg_vols[i] = nv;

            // Grow the rolling window.
            sum_pos += pv;
            sum_neg += nv;
            sum_tot += vol;

            // Drop the bar that just left the window.
            if i >= p {
                let drop = i - p;
                sum_pos -= pos_vols[drop];
                sum_neg -= neg_vols[drop];
                sum_tot -= candles[drop].volume;
            }

            // Emit once we have a full window (index >= p, i.e. p+1 bars seen).
            if i >= p && sum_tot > 0.0 {
                out[i] = 100.0 * (sum_pos - sum_neg) / sum_tot;
            }
        }

        let col_name = format!("vzo_{p}");
        Ok(IndicatorOutput::from_pairs([(col_name, out)]))
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn make_candle(close: f64, volume: f64) -> Candle {
        Candle {
            time: 0,
            open: close,
            high: close,
            low: close,
            close,
            volume,
        }
    }

    #[test]
    fn insufficient_data_returns_error() {
        let vzo = VolumeZoneOscillator::new(5);
        let candles: Vec<Candle> = (0..5)
            .map(|i| make_candle(100.0 + i as f64, 1000.0))
            .collect();
        assert!(vzo.calculate(&candles).is_err());
    }

    #[test]
    fn all_up_bars_gives_positive_vzo() {
        let vzo = VolumeZoneOscillator::new(5);
        // 7 candles, every close higher than the previous → all pos_vol, no neg_vol
        let candles: Vec<Candle> = (0..7)
            .map(|i| make_candle(100.0 + i as f64, 1_000.0))
            .collect();
        let out = vzo.calculate(&candles).unwrap();
        let vals = out.get("vzo_5").unwrap();
        // Last value must be exactly +100
        assert_eq!(*vals.last().unwrap(), 100.0);
    }

    #[test]
    fn all_down_bars_gives_negative_vzo() {
        let vzo = VolumeZoneOscillator::new(5);
        let candles: Vec<Candle> = (0..7)
            .map(|i| make_candle(200.0 - i as f64, 1_000.0))
            .collect();
        let out = vzo.calculate(&candles).unwrap();
        let vals = out.get("vzo_5").unwrap();
        assert_eq!(*vals.last().unwrap(), -100.0);
    }

    #[test]
    fn flat_bars_give_zero_vzo() {
        let vzo = VolumeZoneOscillator::new(5);
        // Flat close → no direction → pos_vol = neg_vol = 0
        let candles: Vec<Candle> = (0..7).map(|_| make_candle(100.0, 1_000.0)).collect();
        let out = vzo.calculate(&candles).unwrap();
        let vals = out.get("vzo_5").unwrap();
        assert_eq!(*vals.last().unwrap(), 0.0);
    }

    #[test]
    fn warm_up_bars_are_nan() {
        let period = 5;
        let vzo = VolumeZoneOscillator::new(period);
        let candles: Vec<Candle> = (0..10)
            .map(|i| make_candle(100.0 + i as f64, 1_000.0))
            .collect();
        let out = vzo.calculate(&candles).unwrap();
        let vals = out.get("vzo_5").unwrap();
        // First `period` values (indices 0..period) should be NaN
        for v in &vals[..period] {
            assert!(v.is_nan(), "expected NaN but got {v}");
        }
        // Values from index `period` onward should be finite
        for v in &vals[period..] {
            assert!(v.is_finite(), "expected finite but got {v}");
        }
    }

    #[test]
    fn output_length_matches_input() {
        let vzo = VolumeZoneOscillator::new(5);
        let candles: Vec<Candle> = (0..20)
            .map(|i| make_candle(100.0 + i as f64, 500.0))
            .collect();
        let out = vzo.calculate(&candles).unwrap();
        assert_eq!(out.len(), 20);
    }

    #[test]
    fn vzo_bounded_between_minus100_and_plus100() {
        let vzo = VolumeZoneOscillator::new(5);
        // Alternating up/down with varying volume
        let candles: Vec<Candle> = (0..30)
            .map(|i| {
                let close = if i % 2 == 0 {
                    100.0 + i as f64
                } else {
                    99.0 + i as f64
                };
                make_candle(close, (i + 1) as f64 * 100.0)
            })
            .collect();
        let out = vzo.calculate(&candles).unwrap();
        for &v in out.get("vzo_5").unwrap() {
            if v.is_finite() {
                assert!((-100.0..=100.0).contains(&v), "VZO out of range: {v}");
            }
        }
    }
}
