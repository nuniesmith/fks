//! Confluence Engine.
//!
//! Scores bullish/bearish confluence from EMA stack, MACD, RSI, ADX, and volume.

use std::collections::{HashMap, VecDeque};

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::param_usize;
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ConfluenceParams {
    pub fast_len: usize,
    pub slow_len: usize,
    pub trend_len: usize,
    pub rsi_len: usize,
    pub adx_len: usize,
}

impl Default for ConfluenceParams {
    fn default() -> Self {
        Self {
            fast_len: 8,
            slow_len: 21,
            trend_len: 50,
            rsi_len: 14,
            adx_len: 14,
        }
    }
}

// ── Indicator wrapper ─────────────────────────────────────────────────────────

/// Batch `Indicator` adapter for [`ConfluenceEngine`].
///
/// Replays the candle slice through the streaming engine and collects per-bar
/// `bull_score` and `bear_score`.
#[derive(Debug, Clone)]
pub struct ConfluenceIndicator {
    pub params: ConfluenceParams,
}

impl ConfluenceIndicator {
    pub fn new(params: ConfluenceParams) -> Self {
        Self { params }
    }
}

impl Indicator for ConfluenceIndicator {
    fn name(&self) -> &'static str {
        "Confluence"
    }
    fn required_len(&self) -> usize {
        self.params.trend_len + 1
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close", "volume"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;
        let p = &self.params;
        let mut eng =
            ConfluenceEngine::new(p.fast_len, p.slow_len, p.trend_len, p.rsi_len, p.adx_len);
        let n = candles.len();
        let mut bull = vec![f64::NAN; n];
        let mut bear = vec![f64::NAN; n];
        for (i, c) in candles.iter().enumerate() {
            eng.update(c);
            bull[i] = eng.bull_score;
            bear[i] = eng.bear_score;
        }
        Ok(IndicatorOutput::from_pairs([
            ("confluence_bull", bull),
            ("confluence_bear", bear),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let fast_len = param_usize(params, "fast_len", 8)?;
    let slow_len = param_usize(params, "slow_len", 21)?;
    let trend_len = param_usize(params, "trend_len", 50)?;
    let rsi_len = param_usize(params, "rsi_len", 14)?;
    let adx_len = param_usize(params, "adx_len", 14)?;
    Ok(Box::new(ConfluenceIndicator::new(ConfluenceParams {
        fast_len,
        slow_len,
        trend_len,
        rsi_len,
        adx_len,
    })))
}

#[derive(Debug)]
pub struct ConfluenceEngine {
    fast_len: usize,
    slow_len: usize,
    trend_len: usize,
    rsi_len: usize,
    adx_len: usize,

    closes: VecDeque<f64>,
    volumes: VecDeque<f64>,
    highs: VecDeque<f64>,
    lows: VecDeque<f64>,

    // EMAs
    ema_f: Option<f64>,
    ema_s: Option<f64>,
    ema_t: Option<f64>,
    // MACD
    macd_ema12: Option<f64>,
    macd_ema26: Option<f64>,
    macd_sig: Option<f64>,
    // RSI (RMA)
    rsi_prev_c: Option<f64>,
    rsi_gain: Option<f64>,
    rsi_loss: Option<f64>,
    // ADX (RMA)
    adx_prev_h: Option<f64>,
    adx_prev_l: Option<f64>,
    adx_prev_c: Option<f64>,
    adx_val: Option<f64>,
    di_plus: Option<f64>,
    di_minus: Option<f64>,
    atr_adx: Option<f64>,

    pub bull_score: f64,
    pub bear_score: f64,
    pub ema_fast: Option<f64>,
    pub ema_slow: Option<f64>,
}

impl ConfluenceEngine {
    pub fn new(fast: usize, slow: usize, trend: usize, rsi_len: usize, adx_len: usize) -> Self {
        let maxlen = (slow * 3).max(trend + 10).max(300);
        Self {
            fast_len: fast,
            slow_len: slow,
            trend_len: trend,
            rsi_len,
            adx_len,
            closes: VecDeque::with_capacity(maxlen),
            volumes: VecDeque::with_capacity(maxlen),
            highs: VecDeque::with_capacity(maxlen),
            lows: VecDeque::with_capacity(maxlen),
            ema_f: None,
            ema_s: None,
            ema_t: None,
            macd_ema12: None,
            macd_ema26: None,
            macd_sig: None,
            rsi_prev_c: None,
            rsi_gain: None,
            rsi_loss: None,
            adx_prev_h: None,
            adx_prev_l: None,
            adx_prev_c: None,
            adx_val: None,
            di_plus: None,
            di_minus: None,
            atr_adx: None,
            bull_score: 0.0,
            bear_score: 0.0,
            ema_fast: None,
            ema_slow: None,
        }
    }

    #[inline]
    fn ema_step(prev: Option<f64>, val: f64, len: usize) -> f64 {
        let k = 2.0 / (len as f64 + 1.0);
        prev.map_or(val, |p| val * k + p * (1.0 - k))
    }

    #[inline]
    fn rma_step(prev: Option<f64>, val: f64, len: usize) -> f64 {
        let k = 1.0 / len as f64;
        prev.map_or(val, |p| val * k + p * (1.0 - k))
    }

    fn update_rsi(&mut self, close: f64) -> f64 {
        let Some(prev) = self.rsi_prev_c else {
            self.rsi_prev_c = Some(close);
            return 50.0;
        };
        let delta = close - prev;
        self.rsi_prev_c = Some(close);
        self.rsi_gain = Some(Self::rma_step(self.rsi_gain, delta.max(0.0), self.rsi_len));
        self.rsi_loss = Some(Self::rma_step(
            self.rsi_loss,
            (-delta).max(0.0),
            self.rsi_len,
        ));
        let gain = self.rsi_gain.unwrap_or(0.0);
        let loss = self.rsi_loss.unwrap_or(1e-9).max(1e-9);
        100.0 - 100.0 / (1.0 + gain / loss)
    }

    fn update_adx(&mut self, high: f64, low: f64, close: f64) {
        let (Some(ph), Some(pl), Some(pc)) = (self.adx_prev_h, self.adx_prev_l, self.adx_prev_c)
        else {
            self.adx_prev_h = Some(high);
            self.adx_prev_l = Some(low);
            self.adx_prev_c = Some(close);
            return;
        };

        let tr = (high - low).max((high - pc).abs()).max((low - pc).abs());
        let up = high - ph;
        let down = pl - low;
        let dm_p = if up > down && up > 0.0 { up } else { 0.0 };
        let dm_m = if down > up && down > 0.0 { down } else { 0.0 };

        self.atr_adx = Some(Self::rma_step(self.atr_adx, tr, self.adx_len));
        let atr = self.atr_adx.unwrap_or(1e-9).max(1e-9);

        self.di_plus = Some(Self::rma_step(
            self.di_plus,
            dm_p / atr * 100.0,
            self.adx_len,
        ));
        self.di_minus = Some(Self::rma_step(
            self.di_minus,
            dm_m / atr * 100.0,
            self.adx_len,
        ));

        let dip = self.di_plus.unwrap_or(0.0);
        let dim = self.di_minus.unwrap_or(0.0);
        let di_sum = (dip + dim).max(1e-9);
        let dx = (dip - dim).abs() / di_sum * 100.0;
        self.adx_val = Some(Self::rma_step(self.adx_val, dx, self.adx_len));

        self.adx_prev_h = Some(high);
        self.adx_prev_l = Some(low);
        self.adx_prev_c = Some(close);
    }

    pub fn update(&mut self, candle: &Candle) {
        let (cl, vol, h, lo) = (candle.close, candle.volume, candle.high, candle.low);

        let cap = self.closes.capacity();
        if self.closes.len() == cap {
            self.closes.pop_front();
        }
        if self.volumes.len() == cap {
            self.volumes.pop_front();
        }
        if self.highs.len() == cap {
            self.highs.pop_front();
        }
        if self.lows.len() == cap {
            self.lows.pop_front();
        }
        self.closes.push_back(cl);
        self.volumes.push_back(vol);
        self.highs.push_back(h);
        self.lows.push_back(lo);

        self.ema_f = Some(Self::ema_step(self.ema_f, cl, self.fast_len));
        self.ema_s = Some(Self::ema_step(self.ema_s, cl, self.slow_len));
        self.ema_t = Some(Self::ema_step(self.ema_t, cl, self.trend_len));
        self.ema_fast = self.ema_f;
        self.ema_slow = self.ema_s;

        self.macd_ema12 = Some(Self::ema_step(self.macd_ema12, cl, 12));
        self.macd_ema26 = Some(Self::ema_step(self.macd_ema26, cl, 26));
        let macd_line = self.macd_ema12.unwrap_or(cl) - self.macd_ema26.unwrap_or(cl);
        self.macd_sig = Some(Self::ema_step(self.macd_sig, macd_line, 9));
        let macd_hist = macd_line - self.macd_sig.unwrap_or(0.0);

        let rsi_val = self.update_rsi(cl);
        self.update_adx(h, lo, cl);

        let adx = self.adx_val.unwrap_or(0.0);
        let dip = self.di_plus.unwrap_or(0.0);
        let dim = self.di_minus.unwrap_or(0.0);

        // Volume filter
        let vols: Vec<f64> = self.volumes.iter().copied().collect();
        let vol_sma = if vols.len() >= 20 {
            vols[vols.len() - 20..].iter().sum::<f64>() / 20.0
        } else {
            vol
        };
        let vol_ok = vol > vol_sma * 1.2;

        let ef = self.ema_f.unwrap_or(cl);
        let es = self.ema_s.unwrap_or(cl);
        let et = self.ema_t.unwrap_or(cl);
        let sig = self.macd_sig.unwrap_or(0.0);

        let mut b = 0.0_f64;
        b += if ef > es { 1.0 } else { 0.0 };
        b += if cl > et { 1.0 } else { 0.0 };
        b += if (50.0..75.0).contains(&rsi_val) {
            1.0
        } else {
            0.0
        };
        b += if macd_hist > 0.0 { 1.0 } else { 0.0 };
        b += if macd_line > sig { 1.0 } else { 0.0 };
        b += if vol_ok { 1.0 } else { 0.0 };
        b += if adx > 20.0 && dip > dim { 1.0 } else { 0.0 };
        b += if cl > ef { 0.5 } else { 0.0 };
        self.bull_score = b;

        let mut s = 0.0_f64;
        s += if ef < es { 1.0 } else { 0.0 };
        s += if cl < et { 1.0 } else { 0.0 };
        s += if (25.0..50.0).contains(&rsi_val) {
            1.0
        } else {
            0.0
        };
        s += if macd_hist < 0.0 { 1.0 } else { 0.0 };
        s += if macd_line < sig { 1.0 } else { 0.0 };
        s += if vol_ok { 1.0 } else { 0.0 };
        s += if adx > 20.0 && dim > dip { 1.0 } else { 0.0 };
        s += if cl < ef { 0.5 } else { 0.0 };
        self.bear_score = s;
    }

    pub fn grade(score: f64) -> &'static str {
        if score >= 8.0 {
            "A+"
        } else if score >= 6.5 {
            "A"
        } else if score >= 5.0 {
            "B"
        } else {
            "C"
        }
    }
}
