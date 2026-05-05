//! `BotSettings` — typed replacement for Python's `DEFAULT_SETTINGS_*` dicts.
//!
//! Every field maps 1-to-1 to a key in the Python `SETTINGS` dict so
//! Optuna-tuned JSON files can be loaded with zero field renaming.

use indicators::IndicatorConfig;
use serde::{Deserialize, Serialize};

// 1. Define the struct with all the fields matching your base() method
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BotSettings {
    pub symbol: String,
    pub leverage: u32,
    pub use_market_orders: bool,
    pub taker_fee: f64,
    pub maker_fee: f64,
    /// Dollar amount of margin (collateral) committed per trade.
    /// Actual notional = trade_size_usd × leverage.
    pub trade_size_usd: f64,
    /// Hard cap: never open more than this many contracts regardless of sizing.
    pub max_contracts: u32,
    pub sim_balance: f64,
    pub kline_interval: String,
    pub rest_kline_type: String,
    pub history_candles: usize,
    pub backtest_candles: usize,
    pub ema_len: usize,
    pub atr_len: usize,
    pub st_factor: f64,
    pub training_period: usize,
    pub highvol_pct: f64,
    pub midvol_pct: f64,
    pub lowvol_pct: f64,
    pub ts_max_length: usize,
    pub ts_accel_mult: f64,
    pub ts_rma_len: usize,
    pub ts_hma_len: usize,
    pub ts_collen: usize,
    pub ts_lookback: usize,
    pub ts_speed_exit_threshold: Option<f64>,
    pub liq_period: usize,
    pub liq_bins: usize,
    pub conf_ema_fast: usize,
    pub conf_ema_slow: usize,
    pub conf_ema_trend: usize,
    pub conf_rsi_len: usize,
    pub conf_adx_len: usize,
    pub conf_min_score: f64,
    pub struct_swing_len: usize,
    pub struct_atr_mult: f64,
    pub fib_zone_enabled: bool,
    pub signal_mode: String,
    /// Number of consecutive identical raw signals required to confirm an
    /// **entry** (i.e., transition flat → long/short, or flip the position
    /// direction).  Larger values trade signal latency for noise rejection.
    pub signal_confirm_bars: usize,
    /// Number of consecutive opposite signals required to **exit** an open
    /// position via SAR-flip.  When `None` the entry value is used (legacy
    /// behavior).  Decoupling lets you require, e.g., 4 bars of agreement
    /// before entering but only 2 before flipping out — useful when the
    /// strategy systematically catches the tail end of moves and needs
    /// faster exits than entries.
    ///
    /// Tuning note (Apr 2026): the 7-day live sample showed zero SAR-flip
    /// wins across all symbols — every winning trade was forced out by
    /// `max_hold_candles`.  Setting this to roughly half of
    /// `signal_confirm_bars` is a reasonable starting point for sim testing.
    pub exit_confirm_bars: Option<usize>,
    pub cvd_slope_bars: usize,
    pub cvd_div_lookback: usize,
    pub wave_pct_l: f64,
    pub wave_pct_s: f64,
    pub mom_pct_min: f64,
    pub vol_pct_window: usize,
    pub hurst_threshold: f64,
    pub hurst_lookback: usize,
    pub stop_atr_mult: f64,
    pub min_vol_pct: f64,
    pub min_hold_candles: usize,
    /// Maximum bars a position may be held before it is forcibly closed at
    /// market price.  Acts as a time-based stop: prevents a position drifting
    /// indefinitely when neither the software stop-loss nor a signal reversal
    /// fires (most likely to happen in SIM mode where there is no exchange-side
    /// hard stop).
    ///
    /// Set to `0` to disable (no time-based exit).  A value of `120` caps any
    /// hold at 2 hours on 1-minute bars — a reasonable starting point.
    pub max_hold_candles: usize,
    // ── Rolling-window indicators (ChoppinessIndex / VZO / STC / ElderRay) ───
    pub chop_period: usize,
    pub vzo_period: usize,
    pub stc_long_ema: usize,
    pub stc_short_ema: usize,
    pub stc_stoch_period: usize,
    pub elder_period: usize,
    /// Choppiness Index threshold above which entries are suppressed (0–100).
    /// Classic level is 61.8; raise to be more permissive, lower to be stricter.
    pub chop_max: f64,
    pub breaker_loss_limit: usize,
    pub breaker_cooldown_sec: u64,
    /// Rolling lookback window (seconds) for the sliding-window circuit breaker.
    /// The breaker trips when `breaker_loss_limit` losses occur within this window.
    /// Default 14400 (4 hours) — covers a typical bad session without letting
    /// morning losses "age out" before an afternoon loss burst.
    pub breaker_window_sec: u64,
    /// STC overbought threshold above which fresh LONG entries are blocked.
    /// Default 85.0 blocks the top 15% of STC readings. Set to 100.0 to disable.
    /// Defence against the mean-reversion whipsaw pattern where long signals fire
    /// at local peaks (STC > 85) and immediately stop out on the pullback.
    /// Tightened from 90 → 85 (Apr 22 review: 92/18 overbought/oversold skew
    /// showed the loss tail extends well below the 90 threshold).
    pub stc_long_max: f64,
    /// STC oversold threshold below which fresh SHORT entries are blocked.
    /// Default 15.0 blocks the bottom 15%. Set to 0.0 to disable.
    /// Tightened from 10 → 15 symmetrically with `stc_long_max`.
    pub stc_short_min: f64,
    pub heartbeat_interval_sec: u64,
    /// Minimum-EV gate multiplier.
    ///
    /// Before opening a position the bot estimates how much a 1-ATR move would
    /// earn at the current contract size (`atr × contracts × contract_value`).
    /// If that expected profit is less than `est_fee × min_profit_mult` the
    /// trade is skipped — it cannot pay for itself even in the best case.
    ///
    /// Set to `0.0` to disable the gate entirely.
    /// A value of `2.5` means the expected profit must cover round-trip fees 2.5×.
    /// Raised from 1.5 → 2.5 (Apr 22 review: at 1.5 the gate let through trades
    /// where fees were 88–93% of gross loss magnitude; 2.5 forces the expected
    /// move to comfortably exceed round-trip fees without cutting winning exits).
    pub min_profit_mult: f64,
    /// How often (in seconds) to poll `data/best_params_<symbol>.json` for changes
    /// and hot-reload strategy parameters + rebuild indicators without a restart.
    ///
    /// The background `param_watch_task` reads this value once at startup.
    /// Set to `0` to disable hot-reload (the task will default to 300 s).
    ///
    /// A params file is considered changed when its filesystem `mtime` differs
    /// from the last-seen value. Only files with a `score` ≥ 0.0 are applied.
    pub param_watch_interval_sec: u64,
    /// Per-session net loss ceiling in USDT (must be negative, e.g. -50.0).
    ///
    /// Once `net_pnl()` drops below this threshold after any trade, the
    /// session is considered done and no new entries are opened. Set to
    /// `f64::NEG_INFINITY` (or any large negative) to disable.
    pub session_loss_limit_usdt: f64,
}

impl BotSettings {
    pub fn base() -> Self {
        Self {
            symbol: String::new(),
            leverage: 5,
            // Switched to limit (maker) entries — 2 bps vs 6 bps taker, ~60%
            // fee reduction.  The existing plumbing handles fill confirmation
            // via WS + REST poll with a 30 s market-order fallback so entries
            // are never silently missed.  (Apr 22 review: fees were 88–93% of
            // gross loss on SOL/ETH; XBT fees flipped a gross win into a net
            // loss.)
            use_market_orders: false,
            taker_fee: 0.0006,
            maker_fee: 0.0002,
            trade_size_usd: 500.0,
            max_contracts: 50,
            sim_balance: 10_000.0,
            kline_interval: "1min".into(),
            rest_kline_type: "1".into(),
            history_candles: 190,
            backtest_candles: 8000,
            ema_len: 9,
            atr_len: 10,
            st_factor: 3.0,
            training_period: 100,
            highvol_pct: 0.75,
            midvol_pct: 0.50,
            lowvol_pct: 0.25,
            ts_max_length: 50,
            ts_accel_mult: 5.0,
            ts_rma_len: 10,
            ts_hma_len: 5,
            ts_collen: 100,
            ts_lookback: 50,
            ts_speed_exit_threshold: None,
            liq_period: 100,
            liq_bins: 31,
            conf_ema_fast: 9,
            conf_ema_slow: 21,
            conf_ema_trend: 55,
            conf_rsi_len: 13,
            conf_adx_len: 14,
            conf_min_score: 5.0,
            struct_swing_len: 10,
            struct_atr_mult: 0.5,
            fib_zone_enabled: true,
            signal_mode: "majority".into(),
            signal_confirm_bars: 2,
            exit_confirm_bars: None,
            cvd_slope_bars: 10,
            cvd_div_lookback: 30,
            wave_pct_l: 0.25,
            wave_pct_s: 0.75,
            mom_pct_min: 0.30,
            vol_pct_window: 200,
            hurst_threshold: 0.52,
            hurst_lookback: 20,
            stop_atr_mult: 1.5,
            min_vol_pct: 0.20,
            min_hold_candles: 2,
            // 2 hours on 1-minute bars — forces a time-based exit so no
            // position can drift for hours without a reversal signal (Apr 21
            // logs showed a 23h XBT hold with `0` here). Set to 0 to disable.
            max_hold_candles: 120,
            chop_period: 14,
            vzo_period: 14,
            stc_long_ema: 26,
            stc_short_ema: 12,
            stc_stoch_period: 10,
            elder_period: 14,
            chop_max: 61.8,
            breaker_loss_limit: 4,
            // Cooldown bumped from 1200s → 3600s (1h).  A 20-minute cooldown
            // is effectively non-binding when losses arrive ~1h apart, which
            // is the actual live pattern observed on Apr 20–21.
            breaker_cooldown_sec: 3600,
            // Sliding-window lookback: 4h.  Combined with loss_limit=4 this
            // means "4 losses in any rolling 4h window → trip".
            breaker_window_sec: 14400,
            // STC extreme-entry guards — tightened from 90/10 → 85/15.
            // Apr 22 review: gate blocked 110 entries (92 overbought / 18
            // oversold) at the 90/10 thresholds; the 5:1 overbought skew
            // confirms the loss tail extends well below STC=90, so tightening
            // to 85/15 catches more of that tail.  Back off if trade count
            // drops below ~3/day across all symbols.
            stc_long_max: 85.0,
            stc_short_min: 15.0,
            heartbeat_interval_sec: 30,
            param_watch_interval_sec: 300,
            // Raised from 1.5 → 2.5 (Apr 22 review: at 1.5 the gate let
            // through trades where fees were 88–93% of gross loss; 2.5
            // requires the expected move to cover fees 2.5× and would have
            // blocked several of the day's small losers without touching wins).
            min_profit_mult: 2.5,
            session_loss_limit_usdt: -50.0,
        }
    }

    /// XBTUSDTM — Optuna best params (score=0.465, 540 trials, 2026-04-11)
    pub fn btc() -> Self {
        Self {
            symbol: "XBTUSDTM".into(),
            ema_len: 19,
            atr_len: 16,
            st_factor: 1.732_500_961_094_518,
            training_period: 100,
            ts_max_length: 61,
            ts_accel_mult: 7.947_699_447_181_174,
            ts_rma_len: 12,
            ts_hma_len: 10,
            ts_collen: 136,
            ts_lookback: 22,
            liq_period: 253,
            liq_bins: 36,
            conf_ema_fast: 7,
            conf_ema_slow: 25,
            conf_ema_trend: 101,
            conf_rsi_len: 18,
            conf_adx_len: 10,
            conf_min_score: 5.882_501_300_215_462,
            struct_swing_len: 10,
            struct_atr_mult: 1.418_522_513_036_211,
            signal_confirm_bars: 4,
            cvd_slope_bars: 18,
            cvd_div_lookback: 31,
            wave_pct_l: 0.324_932_803_654_824_5,
            wave_pct_s: 0.759_301_949_944_997,
            mom_pct_min: 0.315_407_983_258_626_35,
            hurst_threshold: 0.470_700_903_590_050_1,
            stop_atr_mult: 3.323_871_669_995_278,
            ..Self::base()
        }
    }

    /// ETHUSDTM — Optuna best params (score=0.337, 499 trials, 2026-04-11)
    /// NOTE: signal_confirm_bars bumped from Optuna's 1 → 3 manually.
    /// Optuna overfit to a trending session; 1 bar produced 27 trades at 11%
    /// win rate in live trading vs 16–17 trades at higher win rates for BTC/SOL.
    /// Re-run Optuna with the search space floored at 2 before reverting.
    pub fn eth() -> Self {
        Self {
            symbol: "ETHUSDTM".into(),
            ema_len: 23,
            atr_len: 14,
            st_factor: 2.800_930_946_445_57,
            training_period: 178,
            ts_max_length: 64,
            ts_accel_mult: 9.128_835_816_318_796,
            ts_rma_len: 8,
            ts_hma_len: 7,
            ts_collen: 147,
            ts_lookback: 118,
            liq_period: 169,
            liq_bins: 15,
            conf_ema_fast: 11,
            conf_ema_slow: 35,
            conf_ema_trend: 82,
            conf_rsi_len: 15,
            conf_adx_len: 13,
            conf_min_score: 6.060_279_558_202_47,
            struct_swing_len: 24,
            struct_atr_mult: 0.307_111_783_849_352_06,
            signal_confirm_bars: 3,
            cvd_slope_bars: 14,
            cvd_div_lookback: 34,
            wave_pct_l: 0.313_336_256_248_191_4,
            wave_pct_s: 0.803_847_300_878_296_9,
            mom_pct_min: 0.222_335_936_492_782_88,
            hurst_threshold: 0.449_458_831_918_266_1,
            stop_atr_mult: 3.527_876_796_765_249_3,
            ..Self::base()
        }
    }

    /// BNBUSDTM — starter params for sim experimentation, derived from
    /// `eth()` because BNB has a similar large-cap profile (similar 1m
    /// volatility, similar liquidity) to ETH and the strategy's tuning
    /// for ETH is the closest sensible cold-start prior.
    ///
    /// Replace with Optuna-tuned params once a backtest run has produced
    /// them; this function exists so `--symbols BNBUSDTM` can run in sim
    /// mode without an external params file.
    pub fn bnb() -> Self {
        Self {
            symbol: "BNBUSDTM".into(),
            ..Self::eth()
        }
    }

    /// SOLUSDTM — Optuna best params (score=0.373, 499 trials, 2026-04-11)
    pub fn sol() -> Self {
        Self {
            symbol: "SOLUSDTM".into(),
            ema_len: 16,
            atr_len: 16,
            st_factor: 3.249_845_525_526_999_3,
            training_period: 71,
            ts_max_length: 37,
            ts_accel_mult: 10.188_546_287_832_6,
            ts_rma_len: 27,
            ts_hma_len: 4,
            ts_collen: 247,
            ts_lookback: 114,
            liq_period: 108,
            liq_bins: 20,
            conf_ema_fast: 11,
            conf_ema_slow: 41,
            conf_ema_trend: 86,
            conf_rsi_len: 21,
            conf_adx_len: 9,
            conf_min_score: 6.361_409_517_615_795,
            struct_swing_len: 16,
            struct_atr_mult: 0.689_189_825_542_350_5,
            signal_confirm_bars: 4,
            cvd_slope_bars: 12,
            cvd_div_lookback: 48,
            wave_pct_l: 0.370_253_875_728_419_06,
            wave_pct_s: 0.639_030_671_212_053,
            mom_pct_min: 0.549_653_847_768_326_5,
            hurst_threshold: 0.448_802_179_358_898_66,
            stop_atr_mult: 3.695_385_547_309_862_2,
            ..Self::base()
        }
    }

    pub fn by_symbol(symbol: &str) -> Self {
        match symbol {
            "XBTUSDTM" => Self::btc(),
            "ETHUSDTM" => Self::eth(),
            "SOLUSDTM" => Self::sol(),
            "BNBUSDTM" => Self::bnb(),
            _ => Self {
                symbol: symbol.into(),
                ..Self::base()
            },
        }
    }

    /// Converts the relevant bot settings into the config required by the indicators crate
    pub fn as_indicator_config(&self) -> IndicatorConfig {
        IndicatorConfig {
            ema_len: self.ema_len,
            atr_len: self.atr_len,
            st_factor: self.st_factor,
            history_candles: self.history_candles,
            training_period: self.training_period,
            highvol_pct: self.highvol_pct,
            midvol_pct: self.midvol_pct,
            lowvol_pct: self.lowvol_pct,
            ts_max_length: self.ts_max_length,
            ts_accel_mult: self.ts_accel_mult,
            ts_rma_len: self.ts_rma_len,
            ts_hma_len: self.ts_hma_len,
            ts_collen: self.ts_collen,
            ts_lookback: self.ts_lookback,
            ts_speed_exit_threshold: self.ts_speed_exit_threshold,
            liq_period: self.liq_period,
            liq_bins: self.liq_bins,
            conf_ema_fast: self.conf_ema_fast,
            conf_ema_slow: self.conf_ema_slow,
            conf_ema_trend: self.conf_ema_trend,
            conf_rsi_len: self.conf_rsi_len,
            conf_adx_len: self.conf_adx_len,
            conf_min_score: self.conf_min_score,
            struct_swing_len: self.struct_swing_len,
            struct_atr_mult: self.struct_atr_mult,
            fib_zone_enabled: self.fib_zone_enabled,
            signal_mode: self.signal_mode.clone(),
            signal_confirm_bars: self.signal_confirm_bars,
            cvd_slope_bars: self.cvd_slope_bars,
            cvd_div_lookback: self.cvd_div_lookback,
            wave_pct_l: self.wave_pct_l,
            wave_pct_s: self.wave_pct_s,
            mom_pct_min: self.mom_pct_min,
            vol_pct_window: self.vol_pct_window,
            hurst_threshold: self.hurst_threshold,
            hurst_lookback: self.hurst_lookback,
            stop_atr_mult: self.stop_atr_mult,
            min_vol_pct: self.min_vol_pct,
            min_hold_candles: self.min_hold_candles,
        }
    }
}

// ── Optuna param override helpers ─────────────────────────────────────────────

/// All tunable fields from `BotSettings` as `Option<T>` for JSON hot-reload.
///
/// Deserialised from the `"params"` sub-object of the Optuna output file.
/// Only `Some` fields are applied; `None` fields leave the existing value
/// in `BotSettings` unchanged.  This replaces the old hand-written
/// `apply_param_field` match and gets compile-time field-name checking for free.
#[derive(Debug, Default, Deserialize)]
pub struct ParamOverrides {
    pub liq_period: Option<usize>,
    pub liq_bins: Option<usize>,
    pub conf_ema_fast: Option<usize>,
    pub conf_ema_slow: Option<usize>,
    pub conf_ema_trend: Option<usize>,
    pub conf_rsi_len: Option<usize>,
    pub conf_adx_len: Option<usize>,
    pub struct_swing_len: Option<usize>,
    pub struct_atr_mult: Option<f64>,
    pub cvd_slope_bars: Option<usize>,
    pub cvd_div_lookback: Option<usize>,
    pub vol_pct_window: Option<usize>,
    pub min_vol_pct: Option<f64>,
    pub signal_confirm_bars: Option<usize>,
    /// Optional override for `BotSettings::exit_confirm_bars`.
    ///
    /// Present in JSON → applies the value; absent → leaves whatever the
    /// running config has unchanged.  To revert from a configured value back
    /// to the legacy "exit gate mirrors entry gate" behavior, edit the
    /// `BotSettings` constructor or remove the bot's persisted state — JSON
    /// can only set, not clear.  Acceptable for now since we expect this
    /// field to be tuned per symbol and rarely cleared.
    pub exit_confirm_bars: Option<usize>,
    pub min_hold_candles: Option<usize>,
    pub max_hold_candles: Option<usize>,
    pub breaker_loss_limit: Option<usize>,
    pub breaker_cooldown_sec: Option<u64>,
    pub breaker_window_sec: Option<u64>,
    pub stc_long_max: Option<f64>,
    pub stc_short_min: Option<f64>,
    pub taker_fee: Option<f64>,
    pub maker_fee: Option<f64>,
    pub trade_size_usd: Option<f64>,
    pub max_contracts: Option<u32>,
    pub history_candles: Option<usize>,
    pub sim_balance: Option<f64>,
    pub leverage: Option<u32>,
    pub stop_atr_mult: Option<f64>,
    pub min_profit_mult: Option<f64>,
    pub session_loss_limit_usdt: Option<f64>,
    pub chop_period: Option<usize>,
    pub vzo_period: Option<usize>,
    pub stc_long_ema: Option<usize>,
    pub stc_short_ema: Option<usize>,
    pub stc_stoch_period: Option<usize>,
    pub elder_period: Option<usize>,
    pub chop_max: Option<f64>,
    pub ema_len: Option<usize>,
    pub atr_len: Option<usize>,
    pub st_factor: Option<f64>,
}

impl BotSettings {
    /// Apply non-`None` fields from `overrides` onto `self`.
    ///
    /// Called after loading a best-params JSON file.  The pattern
    /// `if let Some(v) = overrides.field { self.field = v; }` is
    /// intentionally mechanical — each arm is trivially correct and any
    /// new tunable field added to both structs is caught by the compiler.
    // Long by necessity (one branch per tunable field) — splitting it would
    // make maintenance harder, not easier.
    #[allow(clippy::too_many_lines, clippy::missing_const_for_fn)]
    pub fn apply_overrides(&mut self, o: &ParamOverrides) {
        if let Some(v) = o.liq_period {
            self.liq_period = v;
        }
        if let Some(v) = o.liq_bins {
            self.liq_bins = v;
        }
        if let Some(v) = o.conf_ema_fast {
            self.conf_ema_fast = v;
        }
        if let Some(v) = o.conf_ema_slow {
            self.conf_ema_slow = v;
        }
        if let Some(v) = o.conf_ema_trend {
            self.conf_ema_trend = v;
        }
        if let Some(v) = o.conf_rsi_len {
            self.conf_rsi_len = v;
        }
        if let Some(v) = o.conf_adx_len {
            self.conf_adx_len = v;
        }
        if let Some(v) = o.struct_swing_len {
            self.struct_swing_len = v;
        }
        if let Some(v) = o.struct_atr_mult {
            self.struct_atr_mult = v;
        }
        if let Some(v) = o.cvd_slope_bars {
            self.cvd_slope_bars = v;
        }
        if let Some(v) = o.cvd_div_lookback {
            self.cvd_div_lookback = v;
        }
        if let Some(v) = o.vol_pct_window {
            self.vol_pct_window = v;
        }
        if let Some(v) = o.min_vol_pct {
            self.min_vol_pct = v;
        }
        if let Some(v) = o.signal_confirm_bars {
            self.signal_confirm_bars = v;
        }
        if let Some(v) = o.exit_confirm_bars {
            self.exit_confirm_bars = Some(v);
        }
        if let Some(v) = o.min_hold_candles {
            self.min_hold_candles = v;
        }
        if let Some(v) = o.max_hold_candles {
            self.max_hold_candles = v;
        }
        if let Some(v) = o.breaker_loss_limit {
            self.breaker_loss_limit = v;
        }
        if let Some(v) = o.breaker_cooldown_sec {
            self.breaker_cooldown_sec = v;
        }
        if let Some(v) = o.breaker_window_sec {
            self.breaker_window_sec = v;
        }
        if let Some(v) = o.stc_long_max {
            self.stc_long_max = v;
        }
        if let Some(v) = o.stc_short_min {
            self.stc_short_min = v;
        }
        if let Some(v) = o.taker_fee {
            self.taker_fee = v;
        }
        if let Some(v) = o.maker_fee {
            self.maker_fee = v;
        }
        if let Some(v) = o.trade_size_usd {
            self.trade_size_usd = v;
        }
        if let Some(v) = o.max_contracts {
            self.max_contracts = v;
        }
        if let Some(v) = o.history_candles {
            self.history_candles = v;
        }
        if let Some(v) = o.sim_balance {
            self.sim_balance = v;
        }
        if let Some(v) = o.leverage {
            self.leverage = v;
        }
        if let Some(v) = o.stop_atr_mult {
            self.stop_atr_mult = v;
        }
        if let Some(v) = o.min_profit_mult {
            self.min_profit_mult = v;
        }
        if let Some(v) = o.session_loss_limit_usdt {
            self.session_loss_limit_usdt = v;
        }
        if let Some(v) = o.chop_period {
            self.chop_period = v;
        }
        if let Some(v) = o.vzo_period {
            self.vzo_period = v;
        }
        if let Some(v) = o.stc_long_ema {
            self.stc_long_ema = v;
        }
        if let Some(v) = o.stc_short_ema {
            self.stc_short_ema = v;
        }
        if let Some(v) = o.stc_stoch_period {
            self.stc_stoch_period = v;
        }
        if let Some(v) = o.elder_period {
            self.elder_period = v;
        }
        if let Some(v) = o.chop_max {
            self.chop_max = v;
        }
        if let Some(v) = o.ema_len {
            self.ema_len = v;
        }
        if let Some(v) = o.atr_len {
            self.atr_len = v;
        }
        if let Some(v) = o.st_factor {
            self.st_factor = v;
        }
    }
}

/// Contract multiplier — base asset units per 1 contract.
///
/// KuCoin futures contract specs (as of 2026):
///   XBTUSDTM  — 0.001 BTC per contract
///   ETHUSDTM  — 0.01  ETH per contract
///   ETHUSDM   — 0.01  ETH per contract (coin-margined)
///   SOLUSDTM  — 1.0   SOL per contract
///   BNBUSDTM  — 0.01  BNB per contract
///
/// This is the single source of truth used by both the sizing and PnL modules.
pub fn contract_value(symbol: &str) -> f64 {
    match symbol {
        "ETHUSDTM" | "ETHUSDM" | "BNBUSDTM" => 0.01,
        "SOLUSDTM" => 1.0,
        _ => 0.001, // XBTUSDTM and all other BTC-denominated contracts
    }
}
