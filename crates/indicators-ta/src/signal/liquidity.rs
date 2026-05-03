//! Layer 5 — Liquidity Thermal Map.
//!
//! Rolling volume profile with configurable price bins. Tracks the Point of Control
//! (POC), Value Area High/Low, and buy/sell liquidity imbalance.

use std::collections::{HashMap, VecDeque};

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct LiquidityParams {
    /// Number of candles in the rolling volume-profile window.
    pub period: usize,
    /// Number of price bins in the volume profile.
    pub n_bins: usize,
}

impl Default for LiquidityParams {
    fn default() -> Self {
        Self {
            period: 50,
            n_bins: 20,
        }
    }
}

// ── Indicator wrapper ─────────────────────────────────────────────────────────

/// Batch `Indicator` adapter for [`LiquidityProfile`].
///
/// Replays candles through the rolling volume profile and emits per-bar:
/// `liq_poc`, `liq_buy_pct`, `liq_imbalance`, `liq_vah`, `liq_val`.
#[derive(Debug, Clone)]
pub struct LiquidityIndicator {
    pub params: LiquidityParams,
}

impl LiquidityIndicator {
    pub fn new(params: LiquidityParams) -> Self {
        Self { params }
    }
    pub fn with_defaults() -> Self {
        Self::new(LiquidityParams::default())
    }
}

impl Indicator for LiquidityIndicator {
    fn name(&self) -> &'static str {
        "Liquidity"
    }
    fn required_len(&self) -> usize {
        self.params.period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close", "volume"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;
        let p = &self.params;
        let mut liq = LiquidityProfile::new(p.period, p.n_bins);
        let n = candles.len();
        let mut poc = vec![f64::NAN; n];
        let mut buy_pct = vec![f64::NAN; n];
        let mut imbalance = vec![f64::NAN; n];
        let mut vah = vec![f64::NAN; n];
        let mut val = vec![f64::NAN; n];
        for (i, c) in candles.iter().enumerate() {
            liq.update(c);
            poc[i] = liq.poc_price.unwrap_or(f64::NAN);
            buy_pct[i] = liq.buy_pct;
            imbalance[i] = liq.imbalance;
            vah[i] = liq.vah.unwrap_or(f64::NAN);
            val[i] = liq.val.unwrap_or(f64::NAN);
        }
        Ok(IndicatorOutput::from_pairs([
            ("liq_poc", poc),
            ("liq_buy_pct", buy_pct),
            ("liq_imbalance", imbalance),
            ("liq_vah", vah),
            ("liq_val", val),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let period = param_usize(params, "period", 50)?;
    let n_bins = param_usize(params, "n_bins", 20)?;
    Ok(Box::new(LiquidityIndicator::new(LiquidityParams {
        period,
        n_bins,
    })))
}

/// Rolling volume-profile liquidity tracker.
#[derive(Debug)]
pub struct LiquidityProfile {
    period: usize,
    n_bins: usize,
    candles: VecDeque<Candle>,

    pub poc_price: Option<f64>,
    pub vah: Option<f64>,
    pub val: Option<f64>,
    pub buy_liq: f64,
    pub sell_liq: f64,
    pub imbalance: f64,
    pub buy_pct: f64,
}

impl LiquidityProfile {
    pub fn new(period: usize, n_bins: usize) -> Self {
        Self {
            period,
            n_bins,
            candles: VecDeque::with_capacity(period),
            poc_price: None,
            vah: None,
            val: None,
            buy_liq: 0.0,
            sell_liq: 0.0,
            imbalance: 0.0,
            buy_pct: 0.5,
        }
    }

    pub fn update(&mut self, candle: &Candle) {
        if self.candles.len() == self.period {
            self.candles.pop_front();
        }
        self.candles.push_back(candle.clone());

        if self.candles.len() < 5 {
            return;
        }

        let h: f64 = self
            .candles
            .iter()
            .map(|c| c.high)
            .fold(f64::NEG_INFINITY, f64::max);
        let l: f64 = self
            .candles
            .iter()
            .map(|c| c.low)
            .fold(f64::INFINITY, f64::min);
        let rng = h - l;
        if rng <= 0.0 {
            return;
        }

        let step = rng / self.n_bins as f64;
        let mut bins = vec![0.0_f64; self.n_bins];

        for c in &self.candles {
            let bar_rng = c.high - c.low;
            if bar_rng <= 0.0 || c.volume <= 0.0 {
                continue;
            }
            #[allow(clippy::needless_range_loop)]
            for i in 0..self.n_bins {
                let bin_lo = l + step * i as f64;
                let bin_hi = bin_lo + step;
                let overlap = c.high.min(bin_hi) - c.low.max(bin_lo);
                if overlap > 0.0 {
                    bins[i] += c.volume * overlap / bar_rng;
                }
            }
        }

        // Point of Control
        let poc_idx = bins
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map_or(0, |(i, _)| i);
        self.poc_price = Some(l + step * poc_idx as f64 + step / 2.0);

        // Value Area (70% of volume around POC)
        let total_vol: f64 = bins.iter().sum();
        let target = total_vol * 0.70;
        let mut area_vol = bins[poc_idx];
        let mut upper = poc_idx;
        let mut lower = poc_idx;

        while area_vol < target {
            let can_up = upper + 1 < self.n_bins;
            let can_down = lower > 0;
            if !can_up && !can_down {
                break;
            }
            let vol_up = if can_up { bins[upper + 1] } else { -1.0 };
            let vol_down = if can_down { bins[lower - 1] } else { -1.0 };
            if vol_up >= vol_down {
                upper += 1;
                area_vol += bins[upper];
            } else {
                lower -= 1;
                area_vol += bins[lower];
            }
        }

        self.vah = Some(l + step * upper as f64 + step / 2.0);
        self.val = Some(l + step * lower as f64 + step / 2.0);

        // Buy / sell liquidity split around close
        let cl = candle.close;
        self.buy_liq = (0..self.n_bins)
            .map(|i| {
                if l + step * i as f64 + step / 2.0 < cl {
                    bins[i]
                } else {
                    0.0
                }
            })
            .sum();
        self.sell_liq = (0..self.n_bins)
            .map(|i| {
                if l + step * i as f64 + step / 2.0 >= cl {
                    bins[i]
                } else {
                    0.0
                }
            })
            .sum();

        let total = self.buy_liq + self.sell_liq;
        self.buy_pct = if total > 0.0 {
            self.buy_liq / total
        } else {
            0.5
        };
        self.imbalance = self.buy_liq - self.sell_liq;
    }

    pub fn bullish(&self) -> bool {
        self.imbalance > 0.0
    }
}
