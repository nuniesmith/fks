//! Layer 8 — Cumulative Volume Delta (OHLCV heuristic).
//!
//! Estimates buy/sell volume from OHLCV bars and tracks cumulative delta,
//! slope, and price-CVD divergence.

use std::collections::{HashMap, VecDeque};

use chrono::{NaiveDate, TimeZone, Utc};

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct CvdParams {
    pub slope_bars: usize,
    pub div_lookback: usize,
}

impl Default for CvdParams {
    fn default() -> Self {
        Self {
            slope_bars: 10,
            div_lookback: 20,
        }
    }
}

// ── Indicator wrapper ─────────────────────────────────────────────────────────

/// Batch `Indicator` adapter for [`CVDTracker`].
#[derive(Debug, Clone)]
pub struct CvdIndicator {
    pub params: CvdParams,
}

impl CvdIndicator {
    pub fn new(params: CvdParams) -> Self {
        Self { params }
    }
}

impl Indicator for CvdIndicator {
    fn name(&self) -> &'static str {
        "CVD"
    }
    fn required_len(&self) -> usize {
        self.params.div_lookback + 1
    }
    fn required_columns(&self) -> &[&'static str] {
        &["open", "high", "low", "close", "volume"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;
        let p = &self.params;
        let mut tracker = CVDTracker::new(p.slope_bars, p.div_lookback);
        let n = candles.len();
        let mut cvd_out = vec![f64::NAN; n];
        let mut slope = vec![f64::NAN; n];
        let mut div_out = vec![f64::NAN; n];
        for (i, c) in candles.iter().enumerate() {
            tracker.update(c);
            cvd_out[i] = tracker.cvd;
            slope[i] = tracker.cvd_slope;
            div_out[i] = tracker.divergence as f64;
        }
        Ok(IndicatorOutput::from_pairs([
            ("cvd", cvd_out),
            ("cvd_slope", slope),
            ("cvd_div", div_out),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let slope_bars = param_usize(params, "slope_bars", 10)?;
    let div_lookback = param_usize(params, "div_lookback", 20)?;
    Ok(Box::new(CvdIndicator::new(CvdParams {
        slope_bars,
        div_lookback,
    })))
}

#[derive(Debug)]
pub struct CVDTracker {
    slope_bars: usize,
    div_lookback: usize,

    day_cvd: f64,
    last_date: Option<NaiveDate>,
    cvd_hist: VecDeque<f64>,
    price_hist: VecDeque<f64>,

    pub cvd: f64,
    pub delta: f64,
    pub cvd_slope: f64,
    pub bullish: bool,
    /// `+1` = bullish divergence, `-1` = bearish divergence, `0` = none.
    pub divergence: i8,
}

impl CVDTracker {
    pub fn new(slope_bars: usize, div_lookback: usize) -> Self {
        let cap = (div_lookback + 10).max(50);
        Self {
            slope_bars,
            div_lookback,
            day_cvd: 0.0,
            last_date: None,
            cvd_hist: VecDeque::with_capacity(cap),
            price_hist: VecDeque::with_capacity(cap),
            cvd: 0.0,
            delta: 0.0,
            cvd_slope: 0.0,
            bullish: false,
            divergence: 0,
        }
    }

    pub fn update(&mut self, candle: &Candle) {
        let dt = Utc
            .timestamp_millis_opt(candle.time)
            .single()
            .unwrap_or_else(Utc::now);
        let date = dt.date_naive();

        if Some(date) != self.last_date {
            self.day_cvd = 0.0;
            self.last_date = Some(date);
        }

        let bar_rng = candle.high - candle.low;
        let buy_vol = if bar_rng > 0.0 {
            candle.volume * (candle.close - candle.low) / bar_rng
        } else {
            candle.volume * 0.5
        };
        self.delta = buy_vol - (candle.volume - buy_vol);
        self.day_cvd += self.delta;
        self.cvd = self.day_cvd;

        let cap = self.cvd_hist.capacity();
        if self.cvd_hist.len() == cap {
            self.cvd_hist.pop_front();
        }
        if self.price_hist.len() == cap {
            self.price_hist.pop_front();
        }
        self.cvd_hist.push_back(self.cvd);
        self.price_hist.push_back(candle.close);

        if self.cvd_hist.len() >= self.slope_bars {
            let arr: Vec<f64> = self.cvd_hist.iter().copied().collect();
            self.cvd_slope = arr[arr.len() - 1] - arr[arr.len() - self.slope_bars];
        }
        self.bullish = self.cvd_slope > 0.0;
        self.divergence = self.check_divergence();
    }

    fn check_divergence(&self) -> i8 {
        let n = self.cvd_hist.len().min(self.div_lookback);
        if n < 10 {
            return 0;
        }
        let prices: Vec<f64> = self.price_hist.iter().rev().take(n).copied().collect();
        let cvds: Vec<f64> = self.cvd_hist.iter().rev().take(n).copied().collect();

        let last_p = prices[0];
        let last_c = cvds[0];

        // Bullish divergence: price at new low but CVD is not
        let min_p = prices[1..].iter().copied().fold(f64::INFINITY, f64::min);
        let min_c = cvds[1..].iter().copied().fold(f64::INFINITY, f64::min);
        if last_p < min_p && last_c > min_c {
            return 1;
        }

        // Bearish divergence: price at new high but CVD is not
        let max_p = prices[1..]
            .iter()
            .copied()
            .fold(f64::NEG_INFINITY, f64::max);
        let max_c = cvds[1..].iter().copied().fold(f64::NEG_INFINITY, f64::max);
        if last_p > max_p && last_c < max_c {
            return -1;
        }

        0
    }
}
