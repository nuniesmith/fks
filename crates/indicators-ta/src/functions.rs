//! Standalone batch indicator functions and incremental structs.
//!
//! Ported from the original `indicators` crate lib. These work on slices
//! (batch mode) or as incremental O(1)-per-tick structs.

use std::collections::VecDeque;

use crate::error::IndicatorError;
use crate::types::MacdResult;

// ── Batch functions ───────────────────────────────────────────────────────────

/// Exponential Moving Average over a price slice.
/// Returns a Vec of the same length; leading values are `NaN` until warm-up.
pub fn ema(prices: &[f64], period: usize) -> Result<Vec<f64>, IndicatorError> {
    if period == 0 {
        return Err(IndicatorError::InvalidParameter {
            name: "period".into(),
            value: 0.0,
        });
    }
    if prices.len() < period {
        return Err(IndicatorError::InsufficientData {
            required: period,
            available: prices.len(),
        });
    }
    let mut result = vec![f64::NAN; prices.len()];
    let alpha = 2.0 / (period as f64 + 1.0);
    let first_sma: f64 = prices.iter().take(period).sum::<f64>() / period as f64;
    result[period - 1] = first_sma;
    for i in period..prices.len() {
        result[i] = prices[i] * alpha + result[i - 1] * (1.0 - alpha);
    }
    Ok(result)
}

/// EMA that handles leading NaN values, matching Python's `ewm(adjust=False)` behaviour.
///
/// Unlike [`ema`], which seeds from the arithmetic mean of the first `period`
/// values, this function seeds from the **first non-NaN value** and applies
/// the recursive formula from that point on.  All positions before the first
/// non-NaN value are left as `NaN`.
///
/// This is needed wherever EMA is applied to a derived series (e.g. the MACD
/// line) that already has a leading NaN warm-up period.  Using the standard
/// [`ema`] on such a series would propagate NaN through the SMA seed and
/// produce an all-NaN output.
pub fn ema_nan_aware(prices: &[f64], period: usize) -> Result<Vec<f64>, IndicatorError> {
    if period == 0 {
        return Err(IndicatorError::InvalidParameter {
            name: "period".into(),
            value: 0.0,
        });
    }
    let mut result = vec![f64::NAN; prices.len()];
    let alpha = 2.0 / (period as f64 + 1.0);

    // Seed from the first non-NaN value (adjust=False, no SMA warm-up).
    let Some(start) = prices.iter().position(|v| !v.is_nan()) else {
        return Ok(result); // all NaN — nothing to compute
    };

    result[start] = prices[start];
    for i in (start + 1)..prices.len() {
        result[i] = if prices[i].is_nan() {
            f64::NAN
        } else {
            prices[i] * alpha + result[i - 1] * (1.0 - alpha)
        };
    }
    Ok(result)
}

/// Simple Moving Average over a price slice.
pub fn sma(prices: &[f64], period: usize) -> Result<Vec<f64>, IndicatorError> {
    if period == 0 {
        return Err(IndicatorError::InvalidParameter {
            name: "period".into(),
            value: 0.0,
        });
    }
    if prices.len() < period {
        return Err(IndicatorError::InsufficientData {
            required: period,
            available: prices.len(),
        });
    }
    let mut result = vec![f64::NAN; prices.len()];
    for i in (period - 1)..prices.len() {
        let sum: f64 = prices[(i + 1 - period)..=i].iter().sum();
        result[i] = sum / period as f64;
    }
    Ok(result)
}

/// True Range = max(H-L, |H-prevC|, |L-prevC|).
pub fn true_range(high: &[f64], low: &[f64], close: &[f64]) -> Result<Vec<f64>, IndicatorError> {
    if high.len() != low.len() || high.len() != close.len() {
        return Err(IndicatorError::InsufficientData {
            required: high.len(),
            available: low.len().min(close.len()),
        });
    }
    let mut result = vec![f64::NAN; high.len()];
    if !high.is_empty() {
        result[0] = high[0] - low[0];
    }
    for i in 1..high.len() {
        let tr1 = high[i] - low[i];
        let tr2 = (high[i] - close[i - 1]).abs();
        let tr3 = (low[i] - close[i - 1]).abs();
        result[i] = tr1.max(tr2).max(tr3);
    }
    Ok(result)
}

/// Average True Range (EMA-smoothed).
pub fn atr(
    high: &[f64],
    low: &[f64],
    close: &[f64],
    period: usize,
) -> Result<Vec<f64>, IndicatorError> {
    let tr = true_range(high, low, close)?;
    ema(&tr, period)
}

/// Relative Strength Index.
pub fn rsi(prices: &[f64], period: usize) -> Result<Vec<f64>, IndicatorError> {
    if prices.len() < period + 1 {
        return Err(IndicatorError::InsufficientData {
            required: period + 1,
            available: prices.len(),
        });
    }
    let mut result = vec![f64::NAN; prices.len()];
    let mut gains = vec![0.0; prices.len()];
    let mut losses = vec![0.0; prices.len()];
    for i in 1..prices.len() {
        let change = prices[i] - prices[i - 1];
        if change > 0.0 {
            gains[i] = change;
        } else {
            losses[i] = -change;
        }
    }
    let avg_gains = ema(&gains, period)?;
    let avg_losses = ema(&losses, period)?;
    for i in period..prices.len() {
        if avg_losses[i] == 0.0 {
            result[i] = 100.0;
        } else {
            let rs = avg_gains[i] / avg_losses[i];
            result[i] = 100.0 - (100.0 / (1.0 + rs));
        }
    }
    Ok(result)
}

/// MACD — returns (macd_line, signal_line, histogram).
pub fn macd(
    prices: &[f64],
    fast_period: usize,
    slow_period: usize,
    signal_period: usize,
) -> MacdResult {
    // Use ema_nan_aware to match Python's ewm(span=X, adjust=False), which
    // seeds from the first value rather than an SMA of the first `period` bars.
    let fast_ema = ema_nan_aware(prices, fast_period)?;
    let slow_ema = ema_nan_aware(prices, slow_period)?;
    let mut macd_line = vec![f64::NAN; prices.len()];
    for i in 0..prices.len() {
        if !fast_ema[i].is_nan() && !slow_ema[i].is_nan() {
            macd_line[i] = fast_ema[i] - slow_ema[i];
        }
    }
    // The macd_line has leading NaN (warm-up from the slow EMA); use the
    // NaN-aware variant so the signal seeds from the first valid MACD value
    // rather than an all-NaN SMA, matching Python's ewm(adjust=False).
    let signal_line = ema_nan_aware(&macd_line, signal_period)?;
    let mut histogram = vec![f64::NAN; prices.len()];
    for i in 0..prices.len() {
        if !macd_line[i].is_nan() && !signal_line[i].is_nan() {
            histogram[i] = macd_line[i] - signal_line[i];
        }
    }
    Ok((macd_line, signal_line, histogram))
}

// ── Incremental structs ───────────────────────────────────────────────────────

/// Incremental EMA — O(1) update, SMA warm-up.
///
/// Unlike the batch [`ema`] function (which initialises from an SMA over the
/// first `period` prices), this struct emits its first value *after* it has
/// accumulated exactly `period` samples and seeds itself from their average.
/// Both approaches are correct; this one is more natural for streaming use.
#[derive(Debug, Clone)]
pub struct EMA {
    period: usize,
    alpha: f64,
    value: f64,
    initialized: bool,
    warmup: VecDeque<f64>,
}

impl EMA {
    pub fn new(period: usize) -> Self {
        Self {
            period,
            alpha: 2.0 / (period as f64 + 1.0),
            value: 0.0,
            initialized: false,
            warmup: VecDeque::with_capacity(period),
        }
    }

    pub fn update(&mut self, price: f64) {
        if !self.initialized {
            self.warmup.push_back(price);
            if self.warmup.len() >= self.period {
                self.value = self.warmup.iter().sum::<f64>() / self.period as f64;
                self.initialized = true;
                self.warmup.clear();
            }
        } else {
            self.value = price * self.alpha + self.value * (1.0 - self.alpha);
        }
    }

    pub fn value(&self) -> f64 {
        if self.initialized {
            self.value
        } else {
            f64::NAN
        }
    }

    pub fn is_ready(&self) -> bool {
        self.initialized
    }

    pub fn reset(&mut self) {
        self.value = 0.0;
        self.initialized = false;
        self.warmup.clear();
    }
}

/// Incremental Wilder ATR.
#[derive(Debug, Clone)]
pub struct ATR {
    #[allow(dead_code)]
    period: usize,
    ema: EMA,
    prev_close: Option<f64>,
}

impl ATR {
    pub fn new(period: usize) -> Self {
        Self {
            period,
            ema: EMA::new(period),
            prev_close: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) {
        let tr = if let Some(prev) = self.prev_close {
            (high - low)
                .max((high - prev).abs())
                .max((low - prev).abs())
        } else {
            high - low
        };
        self.ema.update(tr);
        self.prev_close = Some(close);
    }

    pub fn value(&self) -> f64 {
        self.ema.value()
    }

    pub fn is_ready(&self) -> bool {
        self.ema.is_ready()
    }
}

/// Bundle of per-strategy indicator series.
#[derive(Debug, Clone)]
pub struct StrategyIndicators {
    pub ema_fast: Vec<f64>,
    pub ema_slow: Vec<f64>,
    pub atr: Vec<f64>,
}

/// Multi-period indicator calculator (batch mode).
#[derive(Debug, Clone)]
pub struct IndicatorCalculator {
    pub fast_ema_period: usize,
    pub slow_ema_period: usize,
    pub atr_period: usize,
}

impl Default for IndicatorCalculator {
    fn default() -> Self {
        Self {
            fast_ema_period: 8,
            slow_ema_period: 21,
            atr_period: 14,
        }
    }
}

impl IndicatorCalculator {
    pub fn new(fast_ema: usize, slow_ema: usize, atr_period: usize) -> Self {
        Self {
            fast_ema_period: fast_ema,
            slow_ema_period: slow_ema,
            atr_period,
        }
    }

    pub fn calculate_all(
        &self,
        close: &[f64],
        high: &[f64],
        low: &[f64],
    ) -> Result<StrategyIndicators, IndicatorError> {
        Ok(StrategyIndicators {
            ema_fast: ema(close, self.fast_ema_period)?,
            ema_slow: ema(close, self.slow_ema_period)?,
            atr: atr(high, low, close, self.atr_period)?,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ema_sma_seed() {
        let prices = vec![22.27, 22.19, 22.08, 22.17, 22.18];
        let result = ema(&prices, 5).unwrap();
        let expected = (22.27 + 22.19 + 22.08 + 22.17 + 22.18) / 5.0;
        assert!((result[4] - expected).abs() < 1e-9);
    }

    #[test]
    fn test_true_range_first() {
        let h = vec![50.0, 52.0];
        let l = vec![48.0, 49.0];
        let c = vec![49.0, 51.0];
        let tr = true_range(&h, &l, &c).unwrap();
        assert_eq!(tr[0], 2.0);
        assert_eq!(tr[1], 3.0);
    }

    #[test]
    fn test_ema_incremental() {
        let mut e = EMA::new(3);
        e.update(10.0);
        assert!(!e.is_ready());
        e.update(20.0);
        assert!(!e.is_ready());
        e.update(30.0);
        assert!(e.is_ready());
        assert!((e.value() - 20.0).abs() < 1e-9);
    }
}
