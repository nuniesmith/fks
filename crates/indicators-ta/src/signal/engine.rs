//! Core Indicators Engine — Layers 1–4, 9–11.
//!
//! Faithful port of the Python `Indicators` class from `indicators.py`.
//!
//! Layers:
//! - **L1** VWAP (daily reset)
//! - **L2** EMA (configurable period)
//! - **L3** ML SuperTrend — KMeans-adaptive ATR multiplier
//! - **L4** Trend Speed — dynamic EMA + RMA wave tracking + HMA
//! - **L9** Awesome Oscillator + wave/momentum percentile gates
//! - **L10** Hurst exponent (R/S analysis, recomputed every 10 bars)
//! - **L11** Price acceleration (2nd derivative, normalised)

use std::collections::{HashMap, VecDeque};

use chrono::{NaiveDate, TimeZone, Utc};

// Safely importing from your unified config file
use crate::error::IndicatorError;
use crate::indicator::{Indicator, IndicatorOutput};
use crate::indicator_config::IndicatorConfig;
use crate::registry::param_usize;
use crate::signal::vol_regime::PercentileTracker;
use crate::types::Candle;

// ── Indicator wrapper ─────────────────────────────────────────────────────────

/// Batch `Indicator` adapter for [`Indicators`].
///
/// Replays candles through the full engine (L1–L4, L9–L11) and emits per-bar
/// columns for every published field.
#[derive(Debug, Clone)]
pub struct EngineIndicator {
    pub config: IndicatorConfig,
}

impl EngineIndicator {
    pub fn new(config: IndicatorConfig) -> Self {
        Self { config }
    }
    pub fn with_defaults() -> Self {
        Self::new(IndicatorConfig::default())
    }
}

impl Indicator for EngineIndicator {
    fn name(&self) -> &'static str {
        "Engine"
    }
    fn required_len(&self) -> usize {
        self.config.training_period
    }
    fn required_columns(&self) -> &[&'static str] {
        &["open", "high", "low", "close", "volume"]
    }

    fn calculate(&self, candles: &[Candle]) -> Result<IndicatorOutput, IndicatorError> {
        self.check_len(candles)?;
        let mut ind = Indicators::new(self.config.clone());
        let n = candles.len();
        let mut vwap_out = vec![f64::NAN; n];
        let mut ema_out = vec![f64::NAN; n];
        let mut st_out = vec![f64::NAN; n];
        let mut st_dir_out = vec![f64::NAN; n];
        let mut ts_norm_out = vec![f64::NAN; n];
        let mut ts_bullish_out = vec![f64::NAN; n];
        let mut hurst_out = vec![f64::NAN; n];
        let mut accel_out = vec![f64::NAN; n];
        let mut ao_out = vec![f64::NAN; n];
        let mut dominance_out = vec![f64::NAN; n];
        for (i, c) in candles.iter().enumerate() {
            ind.update(c);
            vwap_out[i] = ind.vwap.unwrap_or(f64::NAN);
            ema_out[i] = ind.ema.unwrap_or(f64::NAN);
            st_out[i] = ind.st.unwrap_or(f64::NAN);
            st_dir_out[i] = ind.st_dir_pub as f64;
            ts_norm_out[i] = ind.ts_norm;
            ts_bullish_out[i] = if ind.ts_bullish { 1.0 } else { 0.0 };
            hurst_out[i] = ind.hurst;
            accel_out[i] = ind.price_accel;
            ao_out[i] = ind.ao;
            dominance_out[i] = ind.dominance;
        }
        Ok(IndicatorOutput::from_pairs([
            ("engine_vwap", vwap_out),
            ("engine_ema", ema_out),
            ("engine_st", st_out),
            ("engine_st_dir", st_dir_out),
            ("engine_ts_norm", ts_norm_out),
            ("engine_ts_bullish", ts_bullish_out),
            ("engine_hurst", hurst_out),
            ("engine_accel", accel_out),
            ("engine_ao", ao_out),
            ("engine_dominance", dominance_out),
        ]))
    }
}

// ── Registry factory ──────────────────────────────────────────────────────────

pub fn factory<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
) -> Result<Box<dyn Indicator>, IndicatorError> {
    let training_period = param_usize(params, "training_period", 100)?;
    let ema_len = param_usize(params, "ema_len", 9)?;
    let atr_len = param_usize(params, "atr_len", 10)?;
    let config = IndicatorConfig {
        ema_len,
        atr_len,
        training_period,
        ..IndicatorConfig::default()
    };
    Ok(Box::new(EngineIndicator::new(config)))
}

// ── Helpers ───────────────────────────────────────────────────────────────────

#[inline]
fn rma_step(prev: Option<f64>, val: f64, len: usize) -> f64 {
    let k = 1.0 / len as f64;
    prev.map_or(val, |p| val * k + p * (1.0 - k))
}

fn wma(arr: &[f64]) -> f64 {
    if arr.is_empty() {
        return 0.0;
    }
    let n = arr.len() as f64;
    let weights_sum = n * (n + 1.0) / 2.0;
    arr.iter()
        .enumerate()
        .map(|(i, &v)| v * (i as f64 + 1.0))
        .sum::<f64>()
        / weights_sum
}

/// R/S Hurst exponent for a single window of closes.
fn hurst_scalar(closes: &[f64], max_lag: usize) -> f64 {
    let n = closes.len();
    if n < max_lag * 2 + 1 {
        return 0.5;
    }
    let mut log_lags: Vec<f64> = Vec::new();
    let mut log_rs: Vec<f64> = Vec::new();

    for lag in 2..=max_lag {
        let chunks = n / lag;
        if chunks < 1 {
            continue;
        }
        let mut rs_vals: Vec<f64> = Vec::new();
        for ci in 0..chunks {
            let chunk = &closes[ci * lag..(ci + 1) * lag];
            if chunk.len() < 2 {
                continue;
            }
            let _mean = chunk.iter().sum::<f64>() / chunk.len() as f64;
            let rets: Vec<f64> = chunk.windows(2).map(|w| w[1] - w[0]).collect();
            let ret_mean = rets.iter().sum::<f64>() / rets.len() as f64;
            let devs: Vec<f64> = {
                let mut cum = 0.0;
                rets.iter()
                    .map(|&r| {
                        cum += r - ret_mean;
                        cum
                    })
                    .collect()
            };
            let r = devs.iter().copied().fold(f64::NEG_INFINITY, f64::max)
                - devs.iter().copied().fold(f64::INFINITY, f64::min);
            let ddof = rets.len() as f64 - 1.0;
            let s = if ddof > 0.0 {
                let var = rets.iter().map(|&x| (x - ret_mean).powi(2)).sum::<f64>() / ddof;
                var.sqrt()
            } else {
                0.0
            };
            if s > 1e-12 {
                rs_vals.push(r / s);
            }
        }
        if !rs_vals.is_empty() {
            log_lags.push((lag as f64).ln());
            log_rs.push(rs_vals.iter().sum::<f64>().ln() - (rs_vals.len() as f64).ln());
        }
    }

    if log_lags.len() < 3 {
        return 0.5;
    }
    let n = log_lags.len() as f64;
    let mx = log_lags.iter().sum::<f64>() / n;
    let my = log_rs.iter().sum::<f64>() / n;
    let num: f64 = log_lags
        .iter()
        .zip(log_rs.iter())
        .map(|(&x, &y)| (x - mx) * (y - my))
        .sum();
    let den: f64 = log_lags.iter().map(|&x| (x - mx).powi(2)).sum();
    if den < 1e-12 {
        return 0.5;
    }
    (num / den).clamp(0.0, 1.0)
}

// ── Indicators ────────────────────────────────────────────────────────────────

/// Full indicator engine (Layers 1–4, 9–11).
///
/// Call [`Indicators::update`] once per closed candle.
/// After `training_period` candles, [`Indicators::st`] and related fields become `Some`.
pub struct Indicators {
    cfg: IndicatorConfig,
    maxlen: usize,

    pub opens: VecDeque<f64>,
    pub highs: VecDeque<f64>,
    pub lows: VecDeque<f64>,
    pub closes: VecDeque<f64>,
    pub volumes: VecDeque<f64>,
    pub times: VecDeque<i64>,
    bar: usize,

    // L1 VWAP
    vwap_vol: f64,
    vwap_tpv: f64,
    vwap_date: Option<NaiveDate>,

    // L2 EMA
    ema9: Option<f64>,

    // L3 SuperTrend
    rma_atr: Option<f64>,
    st_upper: Option<f64>,
    st_lower: Option<f64>,
    st_dir: i8,
    st_value: Option<f64>,
    kmeans_centroids: Option<[f64; 3]>,
    kmeans_last_bar: usize,

    // L4 TrendSpeed
    dyn_ema: Option<f64>,
    prev_close: Option<f64>,
    max_abs_buf: VecDeque<f64>,
    delta_buf: VecDeque<f64>,
    rma_c: Option<f64>,
    rma_o: Option<f64>,
    wave_speed: f64,
    wave_pos: i8,
    speed_norm: VecDeque<f64>,
    hma_buf: VecDeque<f64>,
    bull_waves: VecDeque<f64>,
    bear_waves: VecDeque<f64>,
    wr_tracker: PercentileTracker,
    mom_tracker: PercentileTracker,
    cur_ratio: f64,

    // L10 Hurst
    hurst_last_bar: usize,
    /// Close price at the last Hurst recompute — used to skip redundant R/S runs.
    hurst_last_close: f64,

    // L11 Price acceleration
    vel_buf: VecDeque<f64>,

    // ── Published fields ─────────────────────────────────────────────────────
    /// Layer 1 — intraday VWAP, resets at UTC midnight.
    pub vwap: Option<f64>,
    /// Layer 2 — EMA of configurable period.
    pub ema: Option<f64>,
    /// Layer 3 — SuperTrend line value.
    pub st: Option<f64>,
    /// Layer 3 — SuperTrend direction: `-1` = bullish (price above ST), `+1` = bearish.
    pub st_dir_pub: i8,
    /// Layer 3 — RMA ATR used for SuperTrend.
    pub atr: Option<f64>,
    /// Layer 3 — KMeans cluster index (0 = high vol, 1 = mid, 2 = low vol).
    pub cluster: usize,
    /// Layer 4 — dynamic EMA.
    pub dyn_ema_pub: Option<f64>,
    /// Layer 4 — HMA-smoothed wave speed.
    pub ts_speed: f64,
    /// Layer 4 — wave speed normalised 0–1.
    pub ts_norm: f64,
    /// Layer 4 — true when wave speed is positive.
    pub ts_bullish: bool,
    /// Layer 4 — average bull wave magnitude.
    pub bull_avg: f64,
    /// Layer 4 — average bear wave magnitude.
    pub bear_avg: f64,
    /// Layer 4 — bull_avg - |bear_avg|.
    pub dominance: f64,
    /// Layer 9 — Awesome Oscillator value.
    pub ao: f64,
    /// Layer 9 — true when AO is rising.
    pub ao_rising: bool,
    /// Layer 9 — wave ratio percentile.
    pub wr_pct: f64,
    /// Layer 9 — momentum percentile.
    pub mom_pct: f64,
    pub wave_ok_long: bool,
    pub wave_ok_short: bool,
    pub mom_ok_long: bool,
    pub mom_ok_short: bool,
    /// Layer 10 — Hurst exponent (0.5 = random, >0.52 = trending).
    pub hurst: f64,
    /// Layer 11 — normalised price acceleration (−1 to +1).
    pub price_accel: f64,
}

impl Indicators {
    pub fn new(cfg: IndicatorConfig) -> Self {
        let maxlen = cfg.history_candles.max(cfg.training_period + 50).max(300);
        let ts_collen = cfg.ts_collen;
        let ts_lookback = cfg.ts_lookback;

        let mut wr_tracker = PercentileTracker::new(200);
        for i in 0..100 {
            wr_tracker.push(if i % 2 == 0 { 0.5 } else { 2.0 });
        }

        Self {
            cfg,
            maxlen,
            opens: VecDeque::with_capacity(maxlen),
            highs: VecDeque::with_capacity(maxlen),
            lows: VecDeque::with_capacity(maxlen),
            closes: VecDeque::with_capacity(maxlen),
            volumes: VecDeque::with_capacity(maxlen),
            times: VecDeque::with_capacity(maxlen),
            bar: 0,
            vwap_vol: 0.0,
            vwap_tpv: 0.0,
            vwap_date: None,
            ema9: None,
            rma_atr: None,
            st_upper: None,
            st_lower: None,
            st_dir: 1,
            st_value: None,
            kmeans_centroids: None,
            kmeans_last_bar: 0,
            dyn_ema: None,
            prev_close: None,
            max_abs_buf: VecDeque::with_capacity(200),
            delta_buf: VecDeque::with_capacity(200),
            rma_c: None,
            rma_o: None,
            wave_speed: 0.0,
            wave_pos: 0,
            speed_norm: VecDeque::with_capacity(ts_collen),
            hma_buf: VecDeque::new(),
            bull_waves: VecDeque::with_capacity(ts_lookback * 4),
            bear_waves: VecDeque::with_capacity(ts_lookback * 4),
            wr_tracker,
            mom_tracker: PercentileTracker::seeded(200, 0.5, 0.5),
            cur_ratio: 0.0,
            hurst_last_bar: 0,
            hurst_last_close: f64::NAN,
            vel_buf: VecDeque::with_capacity(110),
            vwap: None,
            ema: None,
            st: None,
            st_dir_pub: 1,
            atr: None,
            cluster: 1,
            dyn_ema_pub: None,
            ts_speed: 0.0,
            ts_norm: 0.5,
            ts_bullish: false,
            bull_avg: 0.0,
            bear_avg: 0.0,
            dominance: 0.0,
            ao: 0.0,
            ao_rising: false,
            wr_pct: 0.5,
            mom_pct: 0.5,
            wave_ok_long: true,
            wave_ok_short: true,
            mom_ok_long: true,
            mom_ok_short: true,
            hurst: 0.5,
            price_accel: 0.0,
        }
    }

    // ── L1 VWAP ───────────────────────────────────────────────────────────────

    fn upd_vwap(&mut self, candle: &Candle) -> f64 {
        let dt = Utc
            .timestamp_millis_opt(candle.time)
            .single()
            .unwrap_or_else(Utc::now)
            .date_naive();
        if Some(dt) != self.vwap_date {
            self.vwap_vol = 0.0;
            self.vwap_tpv = 0.0;
            self.vwap_date = Some(dt);
        }
        let tp = candle.typical_price();
        self.vwap_vol += candle.volume;
        self.vwap_tpv += tp * candle.volume;
        if self.vwap_vol > 0.0 {
            self.vwap_tpv / self.vwap_vol
        } else {
            candle.close
        }
    }

    // ── L3 RMA ATR ────────────────────────────────────────────────────────────

    fn upd_atr(&mut self, candle: &Candle) -> f64 {
        let prev_c = self
            .closes
            .iter()
            .rev()
            .nth(1)
            .copied()
            .unwrap_or(candle.close);
        let tr = (candle.high - candle.low)
            .max((candle.high - prev_c).abs())
            .max((candle.low - prev_c).abs());
        self.rma_atr = Some(rma_step(self.rma_atr, tr, self.cfg.atr_len));
        self.rma_atr.unwrap()
    }

    // ── L3 KMeans ─────────────────────────────────────────────────────────────

    fn kmeans_atr(&mut self, atr_val: f64) -> f64 {
        if self.kmeans_centroids.is_none() || (self.bar - self.kmeans_last_bar) >= 10 {
            self.kmeans_centroids = Some(self.compute_kmeans_centroids());
            self.kmeans_last_bar = self.bar;
        }
        let [c_h, c_m, c_l] = self.kmeans_centroids.unwrap();
        let dists = [
            (c_h - atr_val).abs(),
            (c_m - atr_val).abs(),
            (c_l - atr_val).abs(),
        ];
        self.cluster = dists
            .iter()
            .enumerate()
            .min_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map_or(1, |(i, _)| i);
        [c_h, c_m, c_l][self.cluster]
    }

    fn compute_kmeans_centroids(&self) -> [f64; 3] {
        let n = self.cfg.training_period.min(self.closes.len());
        let ha: Vec<f64> = self.highs.iter().rev().take(n).copied().collect();
        let la: Vec<f64> = self.lows.iter().rev().take(n).copied().collect();
        let ca: Vec<f64> = self.closes.iter().rev().take(n).copied().collect();

        let mut trs = vec![ha[0] - la[0]];
        for i in 1..n {
            trs.push(
                (ha[i] - la[i])
                    .max((ha[i] - ca[i - 1]).abs())
                    .max((la[i] - ca[i - 1]).abs()),
            );
        }
        let alpha = 1.0 / self.cfg.atr_len as f64;
        let mut atr_w = vec![trs[0]];
        for i in 1..trs.len() {
            atr_w.push(alpha * trs[i] + (1.0 - alpha) * atr_w[i - 1]);
        }

        let lo = atr_w.iter().copied().fold(f64::INFINITY, f64::min);
        let hi = atr_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let rng = if (hi - lo).abs() > 1e-9 {
            hi - lo
        } else {
            1e-9
        };

        let mut c_h = lo + rng * self.cfg.highvol_pct;
        let mut c_m = lo + rng * self.cfg.midvol_pct;
        let mut c_l = lo + rng * self.cfg.lowvol_pct;

        for _ in 0..100 {
            let mut g: [Vec<f64>; 3] = [Vec::new(), Vec::new(), Vec::new()];
            for &v in &atr_w {
                let dists = [(v - c_h).abs(), (v - c_m).abs(), (v - c_l).abs()];
                let idx = dists
                    .iter()
                    .enumerate()
                    .min_by(|a, b| a.1.partial_cmp(b.1).unwrap())
                    .map_or(1, |(i, _)| i);
                g[idx].push(v);
            }
            let nh = if g[0].is_empty() {
                c_h
            } else {
                g[0].iter().sum::<f64>() / g[0].len() as f64
            };
            let nm = if g[1].is_empty() {
                c_m
            } else {
                g[1].iter().sum::<f64>() / g[1].len() as f64
            };
            let nl = if g[2].is_empty() {
                c_l
            } else {
                g[2].iter().sum::<f64>() / g[2].len() as f64
            };
            if (nh - c_h).abs() < 1e-9 && (nm - c_m).abs() < 1e-9 && (nl - c_l).abs() < 1e-9 {
                break;
            }
            c_h = nh;
            c_m = nm;
            c_l = nl;
        }
        [c_h, c_m, c_l]
    }

    // ── L3 SuperTrend ─────────────────────────────────────────────────────────

    fn upd_supertrend(&mut self, adaptive_atr: f64, close: f64) -> (f64, i8) {
        let hl2 = (self.highs.back().copied().unwrap_or(close)
            + self.lows.back().copied().unwrap_or(close))
            / 2.0;
        let factor = self.cfg.st_factor;
        let raw_upper = hl2 + factor * adaptive_atr;
        let raw_lower = hl2 - factor * adaptive_atr;

        let prev_u = self.st_upper.unwrap_or(raw_upper);
        let prev_l = self.st_lower.unwrap_or(raw_lower);
        let prev_st = self.st_value.unwrap_or(raw_upper);
        let prev_c = self.closes.iter().rev().nth(1).copied().unwrap_or(close);

        let lower = if raw_lower > prev_l || prev_c < prev_l {
            raw_lower
        } else {
            prev_l
        };
        let upper = if raw_upper < prev_u || prev_c > prev_u {
            raw_upper
        } else {
            prev_u
        };

        let direction = if prev_st == prev_u {
            if close > upper { -1 } else { 1 }
        } else {
            if close < lower { 1 } else { -1 }
        };

        let st_val = if direction == -1 { lower } else { upper };
        self.st_upper = Some(upper);
        self.st_lower = Some(lower);
        self.st_dir = direction;
        self.st_value = Some(st_val);
        (st_val, direction)
    }

    // ── L4 Trend Speed ────────────────────────────────────────────────────────

    fn upd_trend_speed(&mut self, candle: &Candle) {
        let cl = candle.close;
        let op = candle.open;

        let abs_cd = (cl - op).abs();
        if self.max_abs_buf.len() == 200 {
            self.max_abs_buf.pop_front();
        }
        self.max_abs_buf.push_back(abs_cd);
        let max_abs = self
            .max_abs_buf
            .iter()
            .copied()
            .fold(f64::NEG_INFINITY, f64::max)
            .max(1.0);
        let cd_norm = (abs_cd + max_abs) / (2.0 * max_abs);
        let dyn_len = 5.0 + cd_norm * (self.cfg.ts_max_length as f64 - 5.0);

        let prev_c = self.prev_close.unwrap_or(cl);
        let delta = (cl - prev_c).abs();
        if self.delta_buf.len() == 200 {
            self.delta_buf.pop_front();
        }
        self.delta_buf.push_back(delta);
        let max_d = self
            .delta_buf
            .iter()
            .copied()
            .fold(f64::NEG_INFINITY, f64::max)
            .max(1.0);
        let accel = delta / max_d;

        let alpha = (2.0 / (dyn_len + 1.0) * (1.0 + accel * self.cfg.ts_accel_mult)).min(1.0);
        self.dyn_ema = Some(match self.dyn_ema {
            None => cl,
            Some(prev) => alpha * cl + (1.0 - alpha) * prev,
        });
        self.dyn_ema_pub = self.dyn_ema;

        self.rma_c = Some(rma_step(self.rma_c, cl, self.cfg.ts_rma_len));
        self.rma_o = Some(rma_step(self.rma_o, op, self.cfg.ts_rma_len));

        let trend = self.dyn_ema.unwrap();
        let prev_cl = self.closes.iter().rev().nth(1).copied().unwrap_or(cl);
        let c_rma = self.rma_c.unwrap_or(0.0);
        let o_rma = self.rma_o.unwrap_or(0.0);
        let lookback_cap = self.cfg.ts_lookback * 4;

        if cl > trend && prev_cl <= trend {
            if self.wave_pos != 0 {
                if self.bear_waves.len() == lookback_cap {
                    self.bear_waves.pop_front();
                }
                self.bear_waves.push_back(self.wave_speed);
            }
            self.wave_pos = 1;
            self.wave_speed = c_rma - o_rma;
        } else if cl < trend && prev_cl >= trend {
            if self.wave_pos != 0 {
                if self.bull_waves.len() == lookback_cap {
                    self.bull_waves.pop_front();
                }
                self.bull_waves.push_back(self.wave_speed);
            }
            self.wave_pos = -1;
            self.wave_speed = c_rma - o_rma;
        } else {
            self.wave_speed += c_rma - o_rma;
        }

        if self.speed_norm.len() == self.cfg.ts_collen {
            self.speed_norm.pop_front();
        }
        self.speed_norm.push_back(self.wave_speed);

        self.ts_speed = self.hma_smooth(self.cfg.ts_hma_len);
        self.ts_bullish = self.ts_speed > 0.0;

        let sp_min = self
            .speed_norm
            .iter()
            .copied()
            .fold(f64::INFINITY, f64::min);
        let sp_max = self
            .speed_norm
            .iter()
            .copied()
            .fold(f64::NEG_INFINITY, f64::max);
        let sp_rng = if (sp_max - sp_min).abs() > 1e-9 {
            sp_max - sp_min
        } else {
            1.0
        };
        self.ts_norm = (self.wave_speed - sp_min) / sp_rng;

        let lb = self.cfg.ts_lookback;
        let bull_r: Vec<f64> = self.bull_waves.iter().rev().take(lb).copied().collect();
        let bear_r: Vec<f64> = self.bear_waves.iter().rev().take(lb).copied().collect();
        self.bull_avg = if bull_r.is_empty() {
            0.0
        } else {
            bull_r.iter().sum::<f64>() / bull_r.len() as f64
        };
        self.bear_avg = if bear_r.is_empty() {
            0.0
        } else {
            bear_r.iter().sum::<f64>() / bear_r.len() as f64
        };
        self.dominance = self.bull_avg - self.bear_avg.abs();
        self.prev_close = Some(cl);

        let bear_abs = self.bear_avg.abs().max(1e-9);
        let wave_ratio = if self.bull_avg > 0.0 {
            self.bull_avg / bear_abs
        } else {
            1.0 / bear_abs
        };
        self.wr_tracker.push(wave_ratio);
        self.wr_pct = self.wr_tracker.pct(wave_ratio);

        self.cur_ratio = if self.wave_speed > 0.0 && self.bull_avg > 0.0 {
            self.wave_speed / self.bull_avg
        } else if self.wave_speed < 0.0 && bear_abs > 0.0 {
            -self.wave_speed.abs() / bear_abs
        } else {
            0.0
        };
        self.mom_tracker.push(self.cur_ratio.abs());
        self.mom_pct = self.mom_tracker.pct(self.cur_ratio.abs());

        let wl = self.cfg.wave_pct_l.clamp(0.01, 0.99);
        let ws = (1.0 - self.cfg.wave_pct_s).clamp(0.01, 0.99);
        let ml = self.cfg.mom_pct_min.clamp(0.01, 0.99);

        self.wave_ok_long = self.wr_pct >= wl;
        self.wave_ok_short = self.wr_pct <= ws;
        self.mom_ok_long = self.mom_pct >= ml && self.cur_ratio > 0.0;
        self.mom_ok_short = self.mom_pct >= ml && self.cur_ratio < 0.0;
    }

    /// HMA: 2*WMA(n/2) - WMA(n), then WMA(√n) of that.
    fn hma_smooth(&mut self, length: usize) -> f64 {
        let sn: Vec<f64> = self.speed_norm.iter().copied().collect();
        if sn.len() < 2 {
            return *sn.last().unwrap_or(&0.0);
        }
        let half = (length / 2).max(1);
        let sqrt_n = (length as f64).sqrt().round() as usize;
        let raw = 2.0 * wma(&sn[sn.len().saturating_sub(half)..])
            - wma(&sn[sn.len().saturating_sub(length)..]);
        if self.hma_buf.len() == sqrt_n {
            self.hma_buf.pop_front();
        }
        self.hma_buf.push_back(raw);
        let hma_arr: Vec<f64> = self.hma_buf.iter().copied().collect();
        wma(&hma_arr)
    }

    // ── L9 Awesome Oscillator ─────────────────────────────────────────────────

    fn upd_ao(&mut self) {
        if self.highs.len() < 34 {
            return;
        }
        let hs: Vec<f64> = self.highs.iter().copied().collect();
        let ls: Vec<f64> = self.lows.iter().copied().collect();
        let hl2: Vec<f64> = hs
            .iter()
            .zip(ls.iter())
            .map(|(h, l)| (h + l) / 2.0)
            .collect();
        let n = hl2.len();
        let ao_new =
            hl2[n - 5..].iter().sum::<f64>() / 5.0 - hl2[n - 34..].iter().sum::<f64>() / 34.0;
        self.ao_rising = ao_new > self.ao;
        self.ao = ao_new;
    }

    // ── L10 Hurst ─────────────────────────────────────────────────────────────

    fn upd_hurst(&mut self) {
        let lb = self.cfg.hurst_lookback;
        let min_bars = lb * 2 + 1;
        if self.closes.len() < min_bars || (self.bar - self.hurst_last_bar) < 10 {
            return;
        }
        // Skip the O(N log N) R/S loop when the close has barely moved since
        // the last recompute (< 0.01 % change).  The Hurst exponent is stable
        // over such tiny price moves, so the cached value remains valid.
        let cur_close = *self.closes.back().unwrap_or(&0.0);
        let pct_move = if self.hurst_last_close.is_nan() || self.hurst_last_close.abs() < 1e-10 {
            f64::INFINITY // force first compute
        } else {
            (cur_close - self.hurst_last_close).abs() / self.hurst_last_close
        };
        if pct_move < 1e-4 {
            // Price hasn't moved enough to shift the Hurst estimate — reuse cache.
            self.hurst_last_bar = self.bar;
            return;
        }
        let cl_arr: Vec<f64> = self.closes.iter().rev().take(min_bars).copied().collect();
        self.hurst = hurst_scalar(&cl_arr, lb);
        self.hurst_last_bar = self.bar;
        self.hurst_last_close = cur_close;
    }

    // ── L11 Price acceleration ────────────────────────────────────────────────

    fn upd_accel(&mut self) {
        let k = 3usize;
        let n = self.closes.len();
        if n <= k * 2 {
            return;
        }
        let cl: Vec<f64> = self.closes.iter().copied().collect();
        let vel_now = (cl[n - 1] - cl[n - 1 - k]) / (cl[n - 1 - k] + 1e-10);
        let vel_prev = (cl[n - 1 - k] - cl[n - 1 - k * 2]) / (cl[n - 1 - k * 2] + 1e-10);
        if self.vel_buf.len() == 110 {
            self.vel_buf.pop_front();
        }
        self.vel_buf.push_back(vel_now);
        let accel = vel_now - vel_prev;
        let vel_std = if self.vel_buf.len() > 1 {
            let vv: Vec<f64> = self.vel_buf.iter().copied().collect();
            let mean = vv.iter().sum::<f64>() / vv.len() as f64;
            let var = vv.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / vv.len() as f64;
            var.sqrt()
        } else {
            1.0
        };
        self.price_accel = (accel / (vel_std + 1e-10) / 3.0).clamp(-1.0, 1.0);
    }

    // ── Main update ───────────────────────────────────────────────────────────

    /// Feed one closed candle. Returns `true` once SuperTrend is ready.
    pub fn update(&mut self, candle: &Candle) -> bool {
        let cap = self.maxlen;
        macro_rules! push {
            ($buf:expr, $val:expr) => {
                if $buf.len() == cap {
                    $buf.pop_front();
                }
                $buf.push_back($val);
            };
        }
        push!(self.opens, candle.open);
        push!(self.highs, candle.high);
        push!(self.lows, candle.low);
        push!(self.closes, candle.close);
        push!(self.volumes, candle.volume);
        push!(self.times, candle.time);
        self.bar += 1;

        self.vwap = Some(self.upd_vwap(candle));

        let k = 2.0 / (self.cfg.ema_len as f64 + 1.0);
        self.ema9 = Some(match self.ema9 {
            None => candle.close,
            Some(e) => candle.close * k + e * (1.0 - k),
        });
        self.ema = self.ema9;

        let atr_val = self.upd_atr(candle);
        self.atr = Some(atr_val);

        self.upd_trend_speed(candle);
        self.upd_ao();
        self.upd_hurst();
        self.upd_accel();

        if self.closes.len() < self.cfg.training_period {
            return false;
        }

        let adaptive_atr = self.kmeans_atr(atr_val);
        let (st, dir) = self.upd_supertrend(adaptive_atr, candle.close);
        self.st = Some(st);
        self.st_dir_pub = dir;

        true
    }

    /// Returns `true` if a speed-exit condition is triggered for the given position.
    ///
    /// `position`: `+1` = long, `-1` = short.
    /// Returns `false` when `ts_speed_exit_threshold` is `None`.
    pub fn check_speed_exit(&self, position: i32) -> bool {
        let Some(thr) = self.cfg.ts_speed_exit_threshold else {
            return false;
        };
        if position > 0 && self.ts_speed < -thr.abs() {
            return true;
        }
        position < 0 && self.ts_speed > thr.abs()
    }
}
