//! Layer 7 — Market Structure + Fibonacci Engine.
//!
//! Detects swing highs/lows, identifies Break of Structure (BOS) and
//! Change of Character (CHoCH), and computes Fibonacci retracement levels.

use std::collections::{HashMap, VecDeque};

use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::registry::{param_f64, param_usize};
use crate::types::Candle;

// ── Params ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct StructureParams {
    /// Half-width of the pivot detection window (bars on each side of pivot).
    pub swing_len: usize,
    /// Minimum ATR multiple required between swings to qualify.
    pub atr_mult: f64,
}

impl Default for StructureParams {
    fn default() -> Self {
        Self {
            swing_len: 5,
            atr_mult: 0.5,
        }
    }
}

// ── Indicator wrapper ─────────────────────────────────────────────────────────

/// Batch `Indicator` adapter for [`MarketStructure`].
///
/// Replays candles through the structure engine and emits per-bar:
/// `struct_bias`, `struct_fib618`, `struct_fib500`,
/// `struct_in_discount`, `struct_in_premium`,
/// `struct_bos`, `struct_choch`, `struct_confluence`.
#[derive(Debug, Clone)]
pub struct StructureIndicator {
    pub params: StructureParams,
}

impl StructureIndicator {
    pub fn new(params: StructureParams) -> Self {
        Self { params }
    }
    pub fn with_defaults() -> Self {
        Self::new(StructureParams::default())
    }
}

impl Indicator for StructureIndicator {
    fn name(&self) -> &'static str {
        "Structure"
    }
    /// `swing_len * 4 + 10` mirrors the internal `maxlen` in [`MarketStructure`].
    fn required_len(&self) -> usize {
        self.params.swing_len * 4 + 10
    }
    fn required_columns(&self) -> &[&'static str] {
        &["high", "low", "close"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;
        let p = &self.params;
        let mut ms = MarketStructure::new(p.swing_len, p.atr_mult);
        let n = candles.len();
        let mut bias = vec![f64::NAN; n];
        let mut fib618 = vec![f64::NAN; n];
        let mut fib500 = vec![f64::NAN; n];
        let mut in_discount = vec![f64::NAN; n];
        let mut in_premium = vec![f64::NAN; n];
        let mut bos = vec![f64::NAN; n];
        let mut choch = vec![f64::NAN; n];
        let mut confluence = vec![f64::NAN; n];
        for (i, c) in candles.iter().enumerate() {
            ms.update(c);
            bias[i] = ms.bias as f64;
            fib618[i] = ms.fib618.unwrap_or(f64::NAN);
            fib500[i] = ms.fib500.unwrap_or(f64::NAN);
            in_discount[i] = if ms.in_discount { 1.0 } else { 0.0 };
            in_premium[i] = if ms.in_premium { 1.0 } else { 0.0 };
            bos[i] = if ms.bos { 1.0 } else { 0.0 };
            choch[i] = if ms.choch { 1.0 } else { 0.0 };
            confluence[i] = ms.confluence;
        }
        Ok(IndicatorOutput::from_pairs([
            ("struct_bias", bias),
            ("struct_fib618", fib618),
            ("struct_fib500", fib500),
            ("struct_in_discount", in_discount),
            ("struct_in_premium", in_premium),
            ("struct_bos", bos),
            ("struct_choch", choch),
            ("struct_confluence", confluence),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let swing_len = param_usize(params, "swing_len", 5)?;
    let atr_mult = param_f64(params, "atr_mult", 0.5)?;
    Ok(Box::new(StructureIndicator::new(StructureParams {
        swing_len,
        atr_mult,
    })))
}

#[derive(Debug)]
pub struct MarketStructure {
    swing_len: usize,
    atr_mult: f64,
    maxlen: usize,

    highs: VecDeque<f64>,
    lows: VecDeque<f64>,
    closes: VecDeque<f64>,

    swing_hi: Option<f64>,
    swing_lo: Option<f64>,
    prev_swing_hi: Option<f64>,
    prev_swing_lo: Option<f64>,
    atr: Option<f64>,
    bias_internal: i8,
    fib_hi: Option<f64>,
    fib_lo: Option<f64>,
    fib_dir: i8,
    last_broken_hi: Option<f64>,
    last_broken_lo: Option<f64>,

    // Published state
    pub bias: i8,
    pub fib618: Option<f64>,
    pub fib500: Option<f64>,
    pub fib382: Option<f64>,
    pub fib786: Option<f64>,
    pub in_discount: bool,
    pub in_premium: bool,
    pub bos: bool,
    pub choch: bool,
    pub choch_dir: i8,
    /// 0–100 Fibonacci confluence score.
    pub confluence: f64,
}

impl MarketStructure {
    pub fn new(swing_len: usize, atr_mult_min: f64) -> Self {
        let maxlen = swing_len * 4 + 10;
        Self {
            swing_len,
            atr_mult: atr_mult_min,
            maxlen,
            highs: VecDeque::with_capacity(maxlen),
            lows: VecDeque::with_capacity(maxlen),
            closes: VecDeque::with_capacity(maxlen),
            swing_hi: None,
            swing_lo: None,
            prev_swing_hi: None,
            prev_swing_lo: None,
            atr: None,
            bias_internal: 0,
            fib_hi: None,
            fib_lo: None,
            fib_dir: 0,
            last_broken_hi: None,
            last_broken_lo: None,
            bias: 0,
            fib618: None,
            fib500: None,
            fib382: None,
            fib786: None,
            in_discount: false,
            in_premium: false,
            bos: false,
            choch: false,
            choch_dir: 0,
            confluence: 0.0,
        }
    }

    pub fn update(&mut self, candle: &Candle) {
        if self.highs.len() == self.maxlen {
            self.highs.pop_front();
        }
        if self.lows.len() == self.maxlen {
            self.lows.pop_front();
        }
        if self.closes.len() == self.maxlen {
            self.closes.pop_front();
        }
        self.highs.push_back(candle.high);
        self.lows.push_back(candle.low);
        self.closes.push_back(candle.close);

        // ATR (Wilder 1/14)
        let prev_c = if self.closes.len() >= 2 {
            *self.closes.iter().rev().nth(1).unwrap()
        } else {
            candle.close
        };
        let tr = (candle.high - candle.low)
            .max((candle.high - prev_c).abs())
            .max((candle.low - prev_c).abs());
        self.atr = Some(match self.atr {
            None => tr,
            Some(prev) => prev / 14.0 + tr * (1.0 - 1.0 / 14.0),
        });
        let atr = self.atr.unwrap_or(1e-9).max(1e-9);

        let ph = self.pivot_high();
        let pl = self.pivot_low();

        self.bos = false;
        self.choch = false;
        self.choch_dir = 0;

        if let Some(ph_val) = ph {
            let atr_ok = self
                .swing_lo
                .is_none_or(|slo| (ph_val - slo) >= atr * self.atr_mult);
            if atr_ok {
                self.prev_swing_hi = self.swing_hi;
                self.swing_hi = Some(ph_val);
            }
        }
        if let Some(pl_val) = pl {
            let atr_ok = self
                .swing_hi
                .is_none_or(|shi| (shi - pl_val) >= atr * self.atr_mult);
            if atr_ok {
                self.prev_swing_lo = self.swing_lo;
                self.swing_lo = Some(pl_val);
            }
        }

        let cl = candle.close;

        if let Some(shi) = self.swing_hi
            && cl > shi
            && self.last_broken_hi != Some(shi)
        {
            if self.bias_internal <= 0 {
                self.choch = true;
                self.choch_dir = 1;
                self.fib_dir = 1;
                self.fib_hi = Some(candle.high);
                self.fib_lo = self.swing_lo;
            } else {
                self.bos = true;
                self.fib_hi = Some(candle.high);
                self.fib_lo = self.swing_lo;
                self.fib_dir = 1;
            }
            self.bias_internal = 1;
            self.last_broken_hi = Some(shi);
        }
        if let Some(slo) = self.swing_lo
            && cl < slo
            && self.last_broken_lo != Some(slo)
        {
            if self.bias_internal >= 0 {
                self.choch = true;
                self.choch_dir = -1;
                self.fib_dir = -1;
                self.fib_lo = Some(candle.low);
                self.fib_hi = self.swing_hi;
            } else {
                self.bos = true;
                self.fib_lo = Some(candle.low);
                self.fib_hi = self.swing_hi;
                self.fib_dir = -1;
            }
            self.bias_internal = -1;
            self.last_broken_lo = Some(slo);
        }

        self.bias = self.bias_internal;

        if let (Some(fh), Some(fl)) = (self.fib_hi, self.fib_lo)
            && self.fib_dir != 0
        {
            self.compute_fibs(fh, fl, self.fib_dir);
        }

        if let (Some(f5), dir) = (self.fib500, self.fib_dir) {
            if dir != 0 {
                if dir == 1 {
                    self.in_discount = cl <= f5;
                    self.in_premium = cl > f5;
                } else {
                    self.in_premium = cl >= f5;
                    self.in_discount = cl < f5;
                }
            }
        } else {
            self.in_discount = false;
            self.in_premium = false;
        }

        // Fibonacci confluence score
        let tol = atr * 0.3;
        let mut score = 0.0_f64;
        if self.fib382.is_some_and(|f| (cl - f).abs() < tol) {
            score += 1.5;
        }
        if self.fib500.is_some_and(|f| (cl - f).abs() < tol) {
            score += 2.0;
        }
        if self.fib618.is_some_and(|f| (cl - f).abs() < tol) {
            score += 2.5;
        }
        if self.fib786.is_some_and(|f| (cl - f).abs() < tol) {
            score += 1.5;
        }
        self.confluence = (score * 10.0).min(100.0);
    }

    fn pivot_high(&self) -> Option<f64> {
        let arr: Vec<f64> = self.highs.iter().copied().collect();
        let n = self.swing_len;
        if arr.len() < 2 * n + 1 {
            return None;
        }
        let mid = arr[arr.len() - n - 1];
        let left_ok = (1..=n).all(|i| mid >= arr[arr.len() - n - 1 - i]);
        let right_ok = (1..=n).all(|i| mid >= arr[arr.len() - n - 1 + i]);
        if left_ok && right_ok { Some(mid) } else { None }
    }

    fn pivot_low(&self) -> Option<f64> {
        let arr: Vec<f64> = self.lows.iter().copied().collect();
        let n = self.swing_len;
        if arr.len() < 2 * n + 1 {
            return None;
        }
        let mid = arr[arr.len() - n - 1];
        let left_ok = (1..=n).all(|i| mid <= arr[arr.len() - n - 1 - i]);
        let right_ok = (1..=n).all(|i| mid <= arr[arr.len() - n - 1 + i]);
        if left_ok && right_ok { Some(mid) } else { None }
    }

    fn compute_fibs(&mut self, hi: f64, lo: f64, direction: i8) {
        let rng = hi - lo;
        if rng <= 0.0 {
            return;
        }
        if direction == 1 {
            self.fib382 = Some(hi - rng * 0.382);
            self.fib500 = Some(hi - rng * 0.500);
            self.fib618 = Some(hi - rng * 0.618);
            self.fib786 = Some(hi - rng * 0.786);
        } else {
            self.fib382 = Some(lo + rng * 0.382);
            self.fib500 = Some(lo + rng * 0.500);
            self.fib618 = Some(lo + rng * 0.618);
            self.fib786 = Some(lo + rng * 0.786);
        }
    }
}
