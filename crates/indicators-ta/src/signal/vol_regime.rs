//! Volume-regime helpers: rolling percentile tracker, volatility regime classifier,
//! and a simple MA-slope market regime classifier.
//!
//! These are ported from the Python `VolatilityPercentile`, `PercentileTracker`,
//! and `MarketRegime` classes in `indicators.py`.
//!
//! Note: `MarketRegimeTracker` is distinct from the statistical `MarketRegime` enum
//! in `types.rs` — it is a simpler slope-based classifier used by the signal engine.

use std::collections::{HashMap, VecDeque};

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct VolumeRegimeParams {
    /// ATR period for computing true-range inputs to the percentile tracker.
    pub atr_period: usize,
    /// Rolling window for the [`PercentileTracker`].
    pub pct_window: usize,
}

impl Default for VolumeRegimeParams {
    fn default() -> Self {
        Self {
            atr_period: 14,
            pct_window: 100,
        }
    }
}

// ── Indicator struct ──────────────────────────────────────────────────────────

/// Batch `Indicator` wrapping [`VolatilityPercentile`].
///
/// Computes a rolling ATR, feeds it into the percentile tracker, and outputs
/// `vol_pct` (0–1) and `vol_regime` (encoded as 0=VERY_LOW … 4=VERY_HIGH).
#[derive(Debug, Clone)]
pub struct VolumeRegime {
    pub params: VolumeRegimeParams,
}

impl VolumeRegime {
    pub fn new(params: VolumeRegimeParams) -> Self {
        Self { params }
    }
    pub fn with_defaults() -> Self {
        Self::new(VolumeRegimeParams::default())
    }
}

impl Indicator for VolumeRegime {
    fn name(&self) -> &'static str {
        "VolumeRegime"
    }
    fn required_len(&self) -> usize {
        self.params.atr_period + 1
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;
        let p = &self.params;
        let mut tracker = VolatilityPercentile::new(p.pct_window);

        // Incremental ATR (RMA / Wilder smoothing).
        let mut prev_close: Option<f64> = None;
        let mut atr_rma: Option<f64> = None;
        let alpha = 1.0 / p.atr_period as f64;

        let n = candles.len();
        let mut vol_pct = vec![f64::NAN; n];
        let mut vol_regime = vec![f64::NAN; n];

        for (i, c) in candles.iter().enumerate() {
            let tr = match prev_close {
                None => c.high - c.low,
                Some(pc) => (c.high - c.low)
                    .max((c.high - pc).abs())
                    .max((c.low - pc).abs()),
            };
            atr_rma = Some(match atr_rma {
                None => tr,
                Some(a) => alpha * tr + (1.0 - alpha) * a,
            });
            prev_close = Some(c.close);

            tracker.update(atr_rma);
            vol_pct[i] = tracker.vol_pct;
            vol_regime[i] = match tracker.vol_regime {
                "VERY LOW" => 0.0,
                "LOW" => 1.0,
                "HIGH" => 3.0,
                "VERY HIGH" => 4.0,
                _ => 2.0, // MED
            };
        }

        Ok(IndicatorOutput::from_pairs([
            ("vol_pct", vol_pct),
            ("vol_regime", vol_regime),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let atr_period = param_usize(params, "atr_period", 14)?;
    let pct_window = param_usize(params, "pct_window", 100)?;
    Ok(Box::new(VolumeRegime::new(VolumeRegimeParams {
        atr_period,
        pct_window,
    })))
}

// ── PercentileTracker ─────────────────────────────────────────────────────────

/// Rolling percentile calculator over a fixed-size window.
pub struct PercentileTracker {
    buf: VecDeque<f64>,
}

impl PercentileTracker {
    pub fn new(maxlen: usize) -> Self {
        Self {
            buf: VecDeque::with_capacity(maxlen),
        }
    }

    /// Seed the buffer with alternating `lo` / `hi` values so it is never empty.
    pub fn seeded(maxlen: usize, seed_lo: f64, seed_hi: f64) -> Self {
        let mut t = Self::new(maxlen);
        for i in 0..(maxlen / 2) {
            t.buf.push_back(if i % 2 == 0 { seed_lo } else { seed_hi });
        }
        t
    }

    pub fn push(&mut self, val: f64) {
        if self.buf.len() == self.buf.capacity() {
            self.buf.pop_front();
        }
        self.buf.push_back(val);
    }

    /// Fraction of buffered values strictly less than `val`.
    pub fn pct(&self, val: f64) -> f64 {
        let n = self.buf.len();
        if n == 0 {
            return 0.5;
        }
        self.buf.iter().filter(|&&v| v < val).count() as f64 / n as f64
    }
}

// ── VolatilityPercentile ──────────────────────────────────────────────────────

/// Classifies ATR into a volatility regime by comparing the current ATR to its
/// own rolling percentile history.
pub struct VolatilityPercentile {
    tracker: PercentileTracker,
    pub vol_pct: f64,
    pub vol_regime: &'static str,
    pub vol_mult: f64,
    /// Confidence score adjustment applied to `conf_min_score`.
    pub conf_adj: f64,
}

impl VolatilityPercentile {
    pub fn new(maxlen: usize) -> Self {
        let tracker = PercentileTracker::seeded(maxlen, 20.0, 200.0);
        Self {
            tracker,
            vol_pct: 0.5,
            vol_regime: "MED",
            vol_mult: 1.2,
            conf_adj: 1.0,
        }
    }

    pub fn update(&mut self, atr: Option<f64>) {
        let Some(v) = atr else { return };
        if v <= 0.0 {
            return;
        }
        self.tracker.push(v);
        let p = self.tracker.pct(v);
        self.vol_pct = p;
        (self.vol_regime, self.vol_mult, self.conf_adj) = if p >= 0.8 {
            ("VERY HIGH", 1.8, 1.15)
        } else if p >= 0.6 {
            ("HIGH", 1.5, 1.05)
        } else if p <= 0.2 {
            ("VERY LOW", 0.8, 0.9)
        } else if p <= 0.4 {
            ("LOW", 1.0, 0.95)
        } else {
            ("MED", 1.2, 1.0)
        };
    }
}

// ── MarketRegimeTracker ───────────────────────────────────────────────────────

/// Simple slope + volatility regime tracker (ported from Python `MarketRegime` class).
///
/// Uses a 200-bar MA slope and return volatility to classify as:
/// `"TRENDING↑"`, `"TRENDING↓"`, `"VOLATILE"`, `"RANGING"`, or `"NEUTRAL"`.
pub struct MarketRegimeTracker {
    closes: VecDeque<f64>,
    ma200_hist: VecDeque<f64>,
    ret_hist: VecDeque<f64>,

    pub regime: &'static str,
    pub is_trending_u: bool,
    pub is_trending_d: bool,
    pub is_ranging: bool,
    pub is_volatile: bool,
}

impl MarketRegimeTracker {
    pub fn new() -> Self {
        Self {
            closes: VecDeque::with_capacity(220),
            ma200_hist: VecDeque::with_capacity(120),
            ret_hist: VecDeque::with_capacity(110),
            regime: "NEUTRAL",
            is_trending_u: false,
            is_trending_d: false,
            is_ranging: false,
            is_volatile: false,
        }
    }

    pub fn update(&mut self, close: f64) {
        let prev_cl = self.closes.back().copied().unwrap_or(close);

        if self.closes.len() == 220 {
            self.closes.pop_front();
        }
        self.closes.push_back(close);

        if self.closes.len() < 200 {
            return;
        }

        // 200-bar SMA
        let ma200: f64 = self.closes.iter().rev().take(200).sum::<f64>() / 200.0;

        if self.ma200_hist.len() == 120 {
            self.ma200_hist.pop_front();
        }
        self.ma200_hist.push_back(ma200);

        let ret = if prev_cl != 0.0 {
            (close - prev_cl) / prev_cl
        } else {
            0.0
        };
        if self.ret_hist.len() == 110 {
            self.ret_hist.pop_front();
        }
        self.ret_hist.push_back(ret);

        if self.ma200_hist.len() < 21 || self.ret_hist.len() < 51 {
            return;
        }

        // Slope of MA200 over last 20 bars, normalised by average MA change
        let ma_arr: Vec<f64> = self.ma200_hist.iter().copied().collect();
        let diffs: Vec<f64> = ma_arr.windows(2).map(|w| (w[1] - w[0]).abs()).collect();
        let avg_chg = if diffs.is_empty() {
            1e-9
        } else {
            let tail: Vec<f64> = diffs.iter().rev().take(100).copied().collect();
            tail.iter().sum::<f64>() / tail.len() as f64
        };
        let slope_n = if avg_chg > 0.0 {
            (ma200 - ma_arr[ma_arr.len() - 21]) / (avg_chg * 20.0)
        } else {
            0.0
        };

        // Return volatility
        let ret_arr: Vec<f64> = self.ret_hist.iter().copied().collect();
        let tail100: Vec<f64> = ret_arr.iter().rev().take(100).copied().collect();
        let ret_s = std_dev(&tail100);
        let tail50: Vec<f64> = ret_arr.iter().rev().take(50).map(|r| r.abs()).collect();
        let ret_sma = if tail50.is_empty() {
            ret_s.max(1e-9)
        } else {
            (tail50.iter().sum::<f64>() / tail50.len() as f64).max(1e-9)
        };
        let vol_n = ret_s / ret_sma;

        self.regime = if slope_n > 1.0 {
            "TRENDING↑"
        } else if slope_n < -1.0 {
            "TRENDING↓"
        } else if vol_n > 1.5 {
            "VOLATILE"
        } else if vol_n < 0.8 {
            "RANGING"
        } else {
            "NEUTRAL"
        };

        self.is_trending_u = self.regime == "TRENDING↑";
        self.is_trending_d = self.regime == "TRENDING↓";
        self.is_ranging = self.regime == "RANGING";
        self.is_volatile = self.regime == "VOLATILE";
    }
}

impl Default for MarketRegimeTracker {
    fn default() -> Self {
        Self::new()
    }
}

// ── helpers ───────────────────────────────────────────────────────────────────

fn std_dev(data: &[f64]) -> f64 {
    if data.len() < 2 {
        return 0.0;
    }
    let mean = data.iter().sum::<f64>() / data.len() as f64;
    let var = data.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / data.len() as f64;
    var.sqrt()
}
