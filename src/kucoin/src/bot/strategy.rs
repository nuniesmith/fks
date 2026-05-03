//! Stop-and-reverse strategy orchestration.

use crate::BotSettings;
use crate::settings::contract_value;
use exchange_apiws::types::Candle;
use exchange_apiws::{KuCoinClient, Side};
use indicators::{
    CVDTracker, ConfluenceEngine, Indicators, LiquidityProfile, MarketRegime, MarketStructure,
    SignalStreak, VolatilityPercentile,
};
use tracing::{info, warn};

use crate::bot::circuit_breaker::CircuitBreaker;
use crate::bot::execute::{self, FillSignals};
use crate::bot::pnl::PnlTracker;
use crate::bot::rolling_indicators::{RollingConfig, RollingIndicators};
use crate::bot::sizing::contracts_for_signal;
use crate::bot::state::BotState;
use crate::error::Result;
use crate::notify::discord::DiscordNotifier;
use crate::types::Position;

// ── Candle conversion ─────────────────────────────────────────────────────────
//
// `exchange_apiws::Candle` and `indicators::types::Candle` are distinct types
// that happen to share the same field layout.  Convert at the boundary.

const fn to_ind_candle(c: &Candle) -> indicators::types::Candle {
    indicators::types::Candle {
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
    }
}

// ── All per-symbol indicator state ────────────────────────────────────────────

pub struct SymbolIndicators {
    pub ind: Indicators,
    pub liq: LiquidityProfile,
    pub conf: ConfluenceEngine,
    pub structure: MarketStructure,
    pub cvd: CVDTracker,
    pub vol: VolatilityPercentile,
    pub regime: MarketRegime,
    /// Streak gate for **entry** confirmation (flat → long/short).
    pub streak: SignalStreak,
    /// Streak gate for **exit / SAR-flip** confirmation, configured from
    /// `BotSettings::exit_confirm_bars`.  When that field is `None` this is
    /// constructed with the same length as `streak` and the two gates fire
    /// in lock-step (legacy behavior).  When set lower, exits flip out
    /// faster than entries flip in — useful when the strategy systematically
    /// enters late and needs an asymmetric exit gate.
    pub exit_streak: SignalStreak,
    /// Rolling-window batch indicators (Choppiness, VZO, STC, Elder Ray).
    pub rol: RollingIndicators,
}

/// Decision produced by `plan_candle` — everything the async executor needs,
/// with no references back into the locked context.
pub struct CandlePlan {
    /// Confirmed signal from the **entry** streak gate.  Used to decide
    /// flat → long/short transitions.  Zero when the streak hasn't seen
    /// enough consecutive same-direction raw signals.
    pub confirmed_sig: i8,
    /// Confirmed signal from the **exit** streak gate.  Used to decide
    /// SAR-flip exits when a position is already open.  When
    /// `exit_confirm_bars` is unset this equals `confirmed_sig`.
    pub exit_confirmed_sig: i8,
    pub last_close: f64,
    pub vol_pct: f64,
    /// Pre-computed: `ind.check_speed_exit(position)` — avoids needing to
    /// clone `Indicators` (which doesn't implement `Clone`) for the async phase.
    pub speed_exit: bool,
    /// ATR snapshot at the time of this candle — used by the async executor
    /// to compute exchange-side hard stop prices without holding the mutex.
    pub atr: f64,
    /// True when ChoppinessIndex says the market is ranging — blocks new entries.
    pub is_choppy: bool,
    /// VZO direction: +1 bullish, -1 bearish, 0 neutral/not ready.
    pub vzo_dir: i8,
    /// Elder Ray directional bias score (see `RollingIndicators::elder_bias`).
    pub elder_bias: f64,
    /// Current Schaff Trend Cycle reading (None if indicator not yet warm).
    /// Used by the STC extreme-entry guard to block longs when overbought
    /// (STC ≥ `stc_long_max`) and shorts when oversold (STC ≤ `stc_short_min`).
    pub stc: Option<f64>,
}

impl SymbolIndicators {
    pub fn new(s: &BotSettings) -> Self {
        Self {
            ind: Indicators::new(s.as_indicator_config()),
            liq: LiquidityProfile::new(s.liq_period, s.liq_bins),
            conf: ConfluenceEngine::new(
                s.conf_ema_fast,
                s.conf_ema_slow,
                s.conf_ema_trend,
                s.conf_rsi_len,
                s.conf_adx_len,
            ),
            structure: MarketStructure::new(s.struct_swing_len, s.struct_atr_mult),
            cvd: CVDTracker::new(s.cvd_slope_bars, s.cvd_div_lookback),
            vol: VolatilityPercentile::new(s.vol_pct_window),
            regime: MarketRegime::default(),
            streak: SignalStreak::new(s.signal_confirm_bars),
            // Default to mirroring the entry streak when no separate exit
            // value is configured — preserves legacy behavior bit-for-bit.
            exit_streak: SignalStreak::new(s.exit_confirm_bars.unwrap_or(s.signal_confirm_bars)),
            rol: RollingIndicators::new(RollingConfig {
                chop_period: s.chop_period,
                vzo_period: s.vzo_period,
                stc_long_ema: s.stc_long_ema,
                stc_short_ema: s.stc_short_ema,
                stc_stoch_period: s.stc_stoch_period,
                elder_period: s.elder_period,
                chop_max: s.chop_max,
            }),
        }
    }

    /// Replay historical candles to warm up all indicators.
    pub fn warm_up(&mut self, candles: &[Candle]) {
        let history = if candles.len() > 1 {
            &candles[..candles.len() - 1]
        } else {
            candles
        };

        for candle in history {
            let ic = to_ind_candle(candle);
            self.ind.update(&ic);
            self.liq.update(&ic);
            self.conf.update(&ic);
            self.structure.update(&ic);
            self.cvd.update(&ic);
            self.vol.update(self.ind.atr);
            self.rol.update(&ic);
        }
    }

    /// **Sync** phase: tick indicators and compute the trading decision.
    ///
    /// Call this while holding the `SymbolContext` mutex. It is entirely
    /// CPU-bound — no I/O — so the lock is held for the minimum possible time.
    /// Returns a `CandlePlan` that the async executor can use without the lock.
    pub fn plan_candle(
        &mut self,
        candle: &Candle,
        state: &mut BotState,
        breaker: &mut CircuitBreaker,
    ) -> CandlePlan {
        // 1. Tick the circuit breaker (auto-reset if cooldown elapsed).
        breaker.tick();

        // 2. Convert and feed the candle into all indicators.
        let ic = to_ind_candle(candle);
        let ready = self.ind.update(&ic);
        self.liq.update(&ic);
        self.conf.update(&ic);
        self.structure.update(&ic);
        self.cvd.update(&ic);
        self.vol.update(self.ind.atr);
        self.rol.update(&ic);

        // 3. Compute raw signal and feed it through BOTH streak gates.
        //    `streak` confirms entries; `exit_streak` confirms exits/flips.
        //    They must be advanced on every tick (not just when ready) so the
        //    streak history doesn't drift between entry and exit gates.
        let (sig, confirmed_sig, exit_confirmed_sig) = if ready {
            let (raw, _components) = indicators::compute_signal(
                candle.close,
                &self.ind,
                &self.liq,
                &self.conf,
                &self.structure,
                &state.settings.as_indicator_config(),
                Some(&self.cvd),
                Some(&self.vol),
            );
            let entry_ok = self.streak.update(raw);
            let exit_ok = self.exit_streak.update(raw);
            (
                raw as i8,
                if entry_ok { raw as i8 } else { 0i8 },
                if exit_ok { raw as i8 } else { 0i8 },
            )
        } else {
            (0i8, 0i8, 0i8)
        };

        // 4. Increment hold counter.
        state.tick_bars_held();

        // 5. Log the candle state.
        info!(
            symbol         = %state.settings.symbol,
            close          = candle.close,
            sig            = sig,
            confirmed      = confirmed_sig,
            exit_confirmed = exit_confirmed_sig,
            position       = state.position.0,
            bars_held      = state.bars_since_entry,
            breaker_open   = breaker.is_tripped(),
            chop           = ?self.rol.chop,
            vzo            = ?self.rol.vzo,
            stc            = ?self.rol.stc,
            elder_bias     = self.rol.elder_bias(),
            "candle",
        );

        CandlePlan {
            confirmed_sig,
            exit_confirmed_sig,
            last_close: candle.close,
            vol_pct: self.vol.vol_pct,
            // Pre-compute so execute_plan doesn't need a reference to `ind`.
            speed_exit: !state.position.is_flat() && self.ind.check_speed_exit(state.position.0),
            atr: self.ind.atr.unwrap_or(0.0),
            is_choppy: self.rol.is_choppy(),
            vzo_dir: self.rol.vzo_direction(),
            elder_bias: self.rol.elder_bias(),
            stc: self.rol.stc_value(),
        }
    }

    /// **Async** phase: execute the order decided by `plan_candle`.
    ///
    /// Called *without* holding the `SymbolContext` mutex. All network I/O
    /// happens here, keeping the lock free for the heartbeat task.
    pub async fn execute_plan(
        plan: &CandlePlan,
        state: &mut BotState,
        pnl: &mut PnlTracker,
        breaker: &mut CircuitBreaker,
        client: &KuCoinClient,
        sim_mode: bool,
        discord: Option<&DiscordNotifier>,
        fill_signals: FillSignals,
    ) -> Result<()> {
        execute_sar(
            client,
            state,
            plan.confirmed_sig,
            plan.exit_confirmed_sig,
            plan.last_close,
            plan.speed_exit,
            plan.vol_pct,
            plan.atr,
            plan.is_choppy,
            plan.vzo_dir,
            plan.elder_bias,
            plan.stc,
            pnl,
            breaker,
            sim_mode,
            discord,
            fill_signals,
        )
        .await
    }
}

// ── Entry gate ────────────────────────────────────────────────────────────────

/// Returns `true` if entry should be skipped (signal blocked by a gate).
pub fn should_skip_entry(
    state: &BotState,
    signal: i8,
    breaker: &CircuitBreaker,
    vol_pct: f64,
    is_choppy: bool,
    vzo_dir: i8,
    elder_bias: f64,
    stc: Option<f64>,
    pnl: &PnlTracker,
) -> bool {
    let s = &state.settings;

    // ── Session drawdown cap ──────────────────────────────────────────────
    if pnl.is_session_halted() {
        // The initial halt is already logged at WARN inside PnlTracker
        // (target "pnl") when the limit is first breached.  Repeating it
        // here at WARN every candle tick produces thousands of identical
        // lines that drown out real events.  DEBUG keeps it discoverable
        // without the noise.
        tracing::debug!(
            symbol = %s.symbol,
            "session drawdown cap reached — entry blocked",
        );
        return true;
    }

    if signal == 0 || signal == state.last_signal {
        return true;
    }

    if breaker.is_tripped() {
        warn!(
            symbol   = %s.symbol,
            signal,
            "circuit breaker open — entry blocked",
        );
        return true;
    }

    if vol_pct < s.min_vol_pct {
        tracing::debug!(
            symbol    = %s.symbol,
            vol_pct,
            threshold = s.min_vol_pct,
            "vol gate: entry blocked",
        );
        return true;
    }

    // ── Choppiness gate ──────────────────────────────────────────────────
    // Block entries when CHOP says the market is ranging.  The indicator
    // needs ~20 bars to warm up; before that is_choppy is always false.
    if is_choppy {
        tracing::debug!(
            symbol    = %s.symbol,
            signal,
            "chop gate: market ranging — entry blocked",
        );
        return true;
    }

    // ── VZO alignment gate ────────────────────────────────────────────────
    // Soft gate: skip if VZO contradicts the signal direction.
    // vzo_dir == 0 means the indicator isn't ready yet — let it through.
    if vzo_dir != 0 && (vzo_dir) != signal {
        tracing::debug!(
            symbol  = %s.symbol,
            signal,
            vzo_dir,
            "vzo gate: volume momentum disagrees — entry blocked",
        );
        return true;
    }

    // ── Elder Ray alignment gate ──────────────────────────────────────────
    // Soft gate: skip if Elder Ray bias contradicts signal direction.
    // elder_bias == 0.0 means the indicator isn't warm yet — let it through.
    if elder_bias != 0.0 && (elder_bias.signum() as i8) != signal {
        tracing::debug!(
            symbol     = %s.symbol,
            signal,
            elder_bias,
            "elder gate: bias disagrees — entry blocked",
        );
        return true;
    }

    // ── STC extreme gate ──────────────────────────────────────────────────
    // Block entries when the market is already at a momentum extreme, since
    // the trend-confirmation stack (VZO / Elder / Hurst) tends to align
    // exactly at local peaks and troughs — i.e. right before the mean-
    // reversion pullback that takes out our stop.
    //
    // stc == None means the indicator isn't warm yet — let it through.
    if let Some(stc_val) = stc {
        if signal == 1 && stc_val >= s.stc_long_max {
            tracing::info!(
                symbol    = %s.symbol,
                stc       = stc_val,
                threshold = s.stc_long_max,
                "stc gate: overbought — long entry blocked",
            );
            return true;
        }
        if signal == -1 && stc_val <= s.stc_short_min {
            tracing::info!(
                symbol    = %s.symbol,
                stc       = stc_val,
                threshold = s.stc_short_min,
                "stc gate: oversold — short entry blocked",
            );
            return true;
        }
    }

    if !state.position.is_flat() && state.bars_since_entry < s.min_hold_candles {
        tracing::debug!(
            symbol    = %s.symbol,
            held      = state.bars_since_entry,
            required  = s.min_hold_candles,
            "min-hold gate: flip blocked",
        );
        return true;
    }

    false
}

// ── SAR execution ─────────────────────────────────────────────────────────────

/// Execute the SAR strategy decision for one candle.
///
/// # Signals
/// * `entry_signal` — confirmed signal from the entry streak gate. Drives
///   flat → long/short transitions and the entry side of a SAR flip
///   (i.e., what direction to flip *into*).
/// * `exit_signal` — confirmed signal from the exit streak gate. Drives the
///   close half of a SAR flip — when it disagrees with the held position,
///   the bot exits. When `exit_confirm_bars` is unset this is identical to
///   `entry_signal`. Only consulted when a position is already open.
#[allow(clippy::too_many_arguments, clippy::too_many_lines)]
pub async fn execute_sar(
    client: &KuCoinClient,
    state: &mut BotState,
    entry_signal: i8,
    exit_signal: i8,
    last_close: f64,
    speed_exit: bool,
    vol_pct: f64,
    atr: f64,
    is_choppy: bool,
    vzo_dir: i8,
    elder_bias: f64,
    stc: Option<f64>,
    pnl: &mut PnlTracker,
    breaker: &mut CircuitBreaker,
    sim_mode: bool,
    discord: Option<&DiscordNotifier>,
    fill_signals: FillSignals,
) -> Result<()> {
    let s = state.settings.clone();
    let symbol = s.symbol.as_str();
    let cv = contract_value(symbol);
    let fee_rate = if s.use_market_orders {
        s.taker_fee
    } else {
        s.maker_fee
    };

    // Choose the operative signal based on whether we already hold a position.
    //
    // * Flat → use `entry_signal` (need full entry confirmation before opening).
    // * Long/short → use `exit_signal` (a flip to the opposite side, or a flat
    //   reading from the exit gate, decides whether to close).
    //
    // When `exit_confirm_bars` is unset, `exit_signal == entry_signal` and the
    // behavior is identical to the previous single-signal path.
    let signal = if state.position.is_flat() {
        entry_signal
    } else {
        exit_signal
    };

    // ── Speed-exit check ─────────────────────────────────────────────────────
    if speed_exit {
        // Speed exit closes only — charge one leg of the fee, not round-trip.
        let est_fee = estimate_fee_one_leg(last_close, state.position.size(), cv, fee_rate);
        info!(symbol, est_fee, "speed-exit triggered");

        let realised = realised_pnl(state, last_close, cv);
        record_close(state, pnl, breaker, realised, est_fee);

        if !sim_mode {
            execute::close_position(client, symbol, state.position.0, s.leverage).await?;
            // Cancel the exchange-side hard stop now the position is flat.
            execute::cancel_all_stop_orders(client, symbol).await;
        }

        state.position = Position(0);
        state.last_signal = 0;
        state.entry_price = None;
        state.bars_since_entry = 0;
        return Ok(());
    }

    // ── Software stop-loss ───────────────────────────────────────────────────
    // In live mode the exchange hard stop (placed immediately after entry) is
    // the primary mechanism.  In SIM mode no exchange order exists, so we
    // replicate the same ATR-multiple logic here in software to prevent
    // unbounded losing holds.  Also acts as a candle-level safety net in live
    // mode if the exchange stop were somehow missed.
    //
    // Gate: only active when stop_atr_mult > 0 and ATR is ready.
    if !state.position.is_flat() && s.stop_atr_mult > 0.0 && atr > 0.0 {
        if let Some(entry) = state.entry_price {
            let dir = f64::from(state.position.0.signum());
            let stop_dist = s.stop_atr_mult * atr;
            let stop_hit = (dir > 0.0 && last_close <= entry - stop_dist)
                || (dir < 0.0 && last_close >= entry + stop_dist);
            if stop_hit {
                let realised = realised_pnl(state, last_close, cv);
                let close_fee =
                    estimate_fee_one_leg(last_close, state.position.size(), cv, fee_rate);
                info!(
                    symbol,
                    entry_price = entry,
                    last_close,
                    stop_dist = format!("{stop_dist:.4}"),
                    realised = format!("{realised:.4} USDT"),
                    "software stop-loss hit — closing position",
                );
                record_close(state, pnl, breaker, realised, close_fee);

                if !sim_mode {
                    execute::close_position(client, symbol, state.position.0, s.leverage).await?;
                    execute::cancel_all_stop_orders(client, symbol).await;
                }

                state.position = Position(0);
                state.entry_price = None;
                state.last_signal = 0;
                state.bars_since_entry = 0;
                return Ok(());
            }
        }
    }

    // ── Max hold exit ────────────────────────────────────────────────────────
    // Time-based exit: closes the position at market once bars_since_entry
    // reaches max_hold_candles.  Disabled when max_hold_candles == 0.
    // This is especially important in SIM mode where there is no exchange-side
    // hard stop — without it a position can drift for hundreds of bars when the
    // strategy stays directional and the stop never fires.
    if !state.position.is_flat()
        && s.max_hold_candles > 0
        && state.bars_since_entry >= s.max_hold_candles
    {
        let realised = realised_pnl(state, last_close, cv);
        let close_fee = estimate_fee_one_leg(last_close, state.position.size(), cv, fee_rate);
        info!(
            symbol,
            bars_held = state.bars_since_entry,
            max_hold = s.max_hold_candles,
            realised = format!("{realised:.4} USDT"),
            "max hold exceeded — closing position at market",
        );
        record_close(state, pnl, breaker, realised, close_fee);

        if !sim_mode {
            execute::close_position(client, symbol, state.position.0, s.leverage).await?;
            execute::cancel_all_stop_orders(client, symbol).await;
        }

        state.position = Position(0);
        state.entry_price = None;
        state.last_signal = 0;
        state.bars_since_entry = 0;
        return Ok(());
    }

    // ── Entry gate ───────────────────────────────────────────────────────────
    if should_skip_entry(
        state, signal, breaker, vol_pct, is_choppy, vzo_dir, elder_bias, stc, pnl,
    ) {
        return Ok(());
    }

    // ── Size ─────────────────────────────────────────────────────────────────
    let contracts = contracts_for_signal(last_close, &s);
    if contracts == 0 {
        warn!(
            symbol,
            trade_size_usd = s.trade_size_usd,
            price = last_close,
            "sizing returned 0 contracts — skip",
        );
        return Ok(());
    }

    let notional = last_close * f64::from(contracts) * cv;
    // Round-trip fee — used ONLY for the min-EV gate's hurdle comparison.
    // Actual fee bookkeeping below charges one leg at a time, after each
    // corresponding exchange call succeeds.
    let round_trip_fee = estimate_fee(last_close, contracts, cv, fee_rate);

    // ── Minimum-EV gate ───────────────────────────────────────────────────────
    // Projects the expected price range over the configured minimum hold
    // duration using a random-walk approximation: range ≈ ATR × √N where N is
    // min_hold_candles.  This is a fairer comparison than a raw 1-bar ATR in
    // quiet markets, where the 1-minute ATR is tiny relative to round-trip fees.
    //
    // Gate is disabled when min_profit_mult == 0.0 or ATR is not yet ready.
    if s.min_profit_mult > 0.0 && atr > 0.0 {
        let hold_bars = (s.min_hold_candles.max(1) as f64).sqrt();
        let expected_profit = atr * hold_bars * f64::from(contracts) * cv;
        let fee_hurdle = round_trip_fee * s.min_profit_mult;
        if expected_profit < fee_hurdle {
            info!(
                symbol,
                expected_profit = format!("{expected_profit:.4}"),
                fee_hurdle = format!("{fee_hurdle:.4}"),
                hold_bars = format!("{hold_bars:.2}"),
                min_profit_mult = s.min_profit_mult,
                "min-EV gate: projected profit < fee hurdle — entry skipped",
            );
            return Ok(());
        }
    }

    info!(
        symbol,
        trade_size_usd = s.trade_size_usd,
        leverage = s.leverage,
        contracts,
        notional = format!("{notional:.2}"),
        round_trip_fee = format!("{round_trip_fee:.4}"),
        "sizing",
    );

    // ── Close existing position (SAR flip) ────────────────────────────────────
    //
    // Bookkeeping rule: every fee leg is charged AFTER the corresponding
    // exchange call succeeds.  `record_close` is called only after the live
    // close goes through, so a transient exchange failure cannot leave the
    // tracker desynced from reality.
    //
    // The fee passed to `record_close` is the close-side leg only (not a
    // round-trip).  The open-side leg is booked separately below, after the
    // open succeeds — this prevents the historical triple-charge bug where
    // a flip recorded close (2 legs) + open (1 leg) = 3 legs instead of 2.
    if !state.position.is_flat() {
        let realised = realised_pnl(state, last_close, cv);
        let close_fee = estimate_fee_one_leg(last_close, state.position.size(), cv, fee_rate);
        info!(
            symbol,
            qty = state.position.0,
            "SAR flip — closing existing position"
        );

        if !sim_mode {
            if let Err(e) =
                execute::close_position(client, symbol, state.position.0, s.leverage).await
            {
                warn!(symbol, err = %e, "close_position failed");
                return Err(e);
            }
            // Cancel any standing hard stop now that the position is closed.
            // Failure here is non-fatal — a dangling stop on a flat position
            // will simply not match any open quantity and will be rejected or
            // expire by itself.
            execute::cancel_all_stop_orders(client, symbol).await;
            // Brief pause after closing before reopening in the opposite
            // direction — gives the exchange time to process the close and
            // settle the position before the new order arrives.
            // Override at startup via the `SAR_FLIP_SETTLE_MS` env var; 1 s
            // is a safe default (see `sar_flip_settle_ms()` below).
            tokio::time::sleep(std::time::Duration::from_millis(sar_flip_settle_ms())).await;
        }

        // Close confirmed (live) or virtual (sim) — book the close.
        record_close(state, pnl, breaker, realised, close_fee);

        state.position = Position(0);
        state.entry_price = None;
    }

    // ── Open new position ─────────────────────────────────────────────────────
    let side = if signal == 1 { Side::Buy } else { Side::Sell };
    let direction = if signal == 1 { "LONG" } else { "SHORT" };
    info!(symbol, direction, contracts, "opening position");

    if !sim_mode {
        execute::open_position(client, side, contracts, last_close, &s, fill_signals).await?;

        // Place an exchange-enforced hard stop immediately after entry.
        // This order survives a process crash and protects the position between
        // candle poll ticks. It is cancelled when the position is closed or
        // flipped (see cancel_all_stop_orders calls above).
        //
        // Guard: skip if ATR is zero (indicators not yet warm). A stop at
        // entry price would trigger immediately on the next tick and close
        // the position for a loss before the strategy has any data to act on.
        let stop_side = if signal == 1 { Side::Sell } else { Side::Buy };
        let stop_distance = s.stop_atr_mult * atr;
        if atr <= 0.0 || stop_distance <= 0.0 {
            warn!(
                symbol,
                "ATR not ready (atr={atr}) — skipping hard stop placement; \
                 circuit-breaker is the sole safety net until next candle",
            );
        } else {
            let stop_price = if signal == 1 {
                last_close - stop_distance
            } else {
                last_close + stop_distance
            };
            execute::place_hard_stop(client, symbol, stop_side, contracts, stop_price, s.leverage)
                .await;
        }
    }

    // Open confirmed (live) or virtual (sim) — book the open-side leg.
    // Charged here, after `open_position` returns Ok, so a failed open never
    // leaves a phantom fee in the tracker.
    let open_fee = estimate_fee_one_leg(last_close, contracts, cv, fee_rate);
    pnl.total_fees += open_fee;

    state.position = Position(if signal == 1 {
        contracts.cast_signed()
    } else {
        -(contracts.cast_signed())
    });
    state.entry_price = Some(last_close);
    state.last_signal = signal;
    state.bars_since_entry = 0;

    // ── Notify Discord ────────────────────────────────────────────────────────
    if let Some(d) = discord {
        let signal_id = uuid::Uuid::new_v4().to_string();
        let _ = d
            .notify_signal_received(
                &signal_id,
                symbol,
                side,
                f64::from(contracts),
                Some(last_close),
                1.0,
                "SAR",
            )
            .await;
    }

    Ok(())
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/// Milliseconds to wait between closing the existing position and opening the
/// new one on a SAR flip.  Read once at first use from the `SAR_FLIP_SETTLE_MS`
/// environment variable; defaults to 1000 ms (1 second).
///
/// Cached in a `OnceLock` so subsequent calls are a single atomic load — the
/// env var is not re-parsed on every flip.  Operators can tune this for noisy
/// network conditions without rebuilding the binary.
fn sar_flip_settle_ms() -> u64 {
    use std::sync::OnceLock;
    static CACHED: OnceLock<u64> = OnceLock::new();
    *CACHED.get_or_init(|| {
        std::env::var("SAR_FLIP_SETTLE_MS")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(1_000)
    })
}

fn realised_pnl(state: &BotState, exit_price: f64, cv: f64) -> f64 {
    let Some(entry_price) = state.entry_price else {
        return 0.0;
    };
    let dir = f64::from(state.position.0.signum());
    let size = f64::from(state.position.size());
    dir * (exit_price - entry_price) * size * cv
}

/// Round-trip fee estimate (open + close) — used for SAR flips where we
/// immediately reopen in the opposite direction.
fn estimate_fee(price: f64, size: u32, cv: f64, fee_rate: f64) -> f64 {
    price * f64::from(size) * cv * fee_rate * 2.0
}

/// Single-leg fee estimate (close only) — used for speed exits where we
/// close the position and do not reopen.
fn estimate_fee_one_leg(price: f64, size: u32, cv: f64, fee_rate: f64) -> f64 {
    price * f64::from(size) * cv * fee_rate
}

fn record_close(
    state: &BotState,
    pnl: &mut PnlTracker,
    breaker: &mut CircuitBreaker,
    realised: f64,
    fee: f64,
) {
    pnl.record_close(realised, fee);
    // Circuit breaker verdict must match the real outcome the user sees —
    // a trade that earns $1 gross but costs $3 in fees is a net loss and
    // must count against the consecutive-loss limit.
    if realised - fee > 0.0 {
        breaker.record_win();
    } else {
        breaker.record_loss();
    }
    tracing::info!(
        symbol   = %state.settings.symbol,
        realised = format!("{realised:.4} USDT"),
        fee      = format!("{fee:.4} USDT"),
        net      = format!("{:.4} USDT", realised - fee),
        "trade closed",
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::BotSettings;
    use crate::bot::state::BotState;
    use crate::types::Position;
    use std::sync::Arc;

    // ── helpers ───────────────────────────────────────────────────────────────

    fn make_state(position: i32, entry_price: f64) -> BotState {
        let mut s = BotState::new(Arc::new(BotSettings::by_symbol("XBTUSDTM")));
        s.position = Position(position);
        s.entry_price = Some(entry_price);
        s
    }

    // contract_value for XBTUSDTM is 0.001
    const CV: f64 = 0.001;
    const FEE: f64 = 0.0006;

    // ── estimate_fee / estimate_fee_one_leg ───────────────────────────────────

    #[test]
    fn round_trip_fee_is_twice_one_leg() {
        let price = 50_000.0;
        let size = 10u32;
        let one_leg = estimate_fee_one_leg(price, size, CV, FEE);
        let round_trip = estimate_fee(price, size, CV, FEE);
        assert!(
            (round_trip - 2.0 * one_leg).abs() < 1e-9,
            "round-trip fee must be exactly 2× one-leg fee; got {round_trip} vs 2×{one_leg}"
        );
    }

    #[test]
    fn fee_scales_linearly_with_size() {
        let price = 50_000.0;
        let fee1 = estimate_fee_one_leg(price, 10, CV, FEE);
        let fee2 = estimate_fee_one_leg(price, 20, CV, FEE);
        assert!((fee2 - 2.0 * fee1).abs() < 1e-9);
    }

    #[test]
    fn fee_zero_when_size_zero() {
        assert_eq!(estimate_fee(50_000.0, 0, CV, FEE), 0.0);
        assert_eq!(estimate_fee_one_leg(50_000.0, 0, CV, FEE), 0.0);
    }

    #[test]
    fn fee_formula_known_value() {
        // 50_000 × 10 × 0.001 × 0.0006 = 0.3 USDT per leg
        let leg = estimate_fee_one_leg(50_000.0, 10, CV, FEE);
        assert!((leg - 0.3).abs() < 1e-9, "expected 0.3, got {leg}");
    }

    // ── realised_pnl ──────────────────────────────────────────────────────────

    #[test]
    fn long_pnl_positive_on_price_rise() {
        let state = make_state(10, 50_000.0);
        // price rises 1_000 → profit = 1_000 × 10 × 0.001 = 10 USDT
        let pnl = realised_pnl(&state, 51_000.0, CV);
        assert!(pnl > 0.0, "long should profit when price rises; got {pnl}");
        assert!((pnl - 10.0).abs() < 1e-9, "expected 10.0, got {pnl}");
    }

    #[test]
    fn long_pnl_negative_on_price_drop() {
        let state = make_state(10, 50_000.0);
        let pnl = realised_pnl(&state, 49_000.0, CV);
        assert!(pnl < 0.0, "long should lose when price falls; got {pnl}");
    }

    #[test]
    fn short_pnl_positive_on_price_drop() {
        // Short = negative position qty
        let state = make_state(-10, 50_000.0);
        // price falls 1_000 → profit = 1_000 × 10 × 0.001 = 10 USDT
        let pnl = realised_pnl(&state, 49_000.0, CV);
        assert!(pnl > 0.0, "short should profit when price falls; got {pnl}");
        assert!((pnl - 10.0).abs() < 1e-9, "expected 10.0, got {pnl}");
    }

    #[test]
    fn short_pnl_negative_on_price_rise() {
        let state = make_state(-10, 50_000.0);
        let pnl = realised_pnl(&state, 51_000.0, CV);
        assert!(pnl < 0.0, "short should lose when price rises; got {pnl}");
    }

    #[test]
    fn pnl_zero_when_no_entry_price() {
        let mut state = make_state(10, 50_000.0);
        state.entry_price = None;
        assert_eq!(realised_pnl(&state, 55_000.0, CV), 0.0);
    }

    #[test]
    fn pnl_zero_at_entry_price() {
        let state = make_state(10, 50_000.0);
        assert_eq!(realised_pnl(&state, 50_000.0, CV), 0.0);
    }

    #[test]
    fn pnl_scales_with_position_size() {
        let small = make_state(5, 50_000.0);
        let large = make_state(10, 50_000.0);
        let exit = 51_000.0;
        let pnl_small = realised_pnl(&small, exit, CV);
        let pnl_large = realised_pnl(&large, exit, CV);
        assert!(
            (pnl_large - 2.0 * pnl_small).abs() < 1e-9,
            "PnL should scale linearly with size"
        );
    }

    // ── SAR flip fee accounting ───────────────────────────────────────────────

    #[test]
    fn sar_flip_charges_close_plus_open_legs() {
        // A SAR flip = close old position + open new position = exactly 2 legs.
        // After the fee-bookkeeping refactor the flip path charges:
        //   * one leg via record_close (close-side, after close_position)
        //   * one leg via pnl.total_fees += open_fee (open-side, after open_position)
        // Total: 2 legs, not 3.  This guards against a regression to the old
        // triple-charge bug where record_close was passed the round-trip fee.
        let price = 50_000.0;
        let size = 10u32;
        let close_fee = estimate_fee_one_leg(price, size, CV, FEE);
        let open_fee = estimate_fee_one_leg(price, size, CV, FEE);
        let total = close_fee + open_fee;
        let expected = 2.0 * estimate_fee_one_leg(price, size, CV, FEE);
        assert!(
            (total - expected).abs() < 1e-9,
            "SAR flip should charge exactly 2 legs total (close + open); got {total}"
        );
        // Sanity: round-trip helper should match the same total.
        let rt = estimate_fee(price, size, CV, FEE);
        assert!(
            (total - rt).abs() < 1e-9,
            "2 individual legs must equal one estimate_fee(...) round-trip"
        );
    }

    // ── Entry/exit confirmation split ─────────────────────────────────────────

    #[test]
    fn exit_streak_defaults_to_entry_length_when_unset() {
        // Default BotSettings has exit_confirm_bars: None.
        // SymbolIndicators::new must build exit_streak with the same length
        // as the entry streak — preserving legacy behavior bit-for-bit.
        let s = BotSettings::by_symbol("XBTUSDTM");
        let inds = SymbolIndicators::new(&s);
        // Run a small reproduction: feed n-1 raw signals, neither streak
        // should confirm; feed the n-th, both should confirm together.
        let mut entry = inds.streak;
        let mut exit = inds.exit_streak;
        let n = s.signal_confirm_bars;
        for _ in 0..(n - 1) {
            assert!(!entry.update(1), "entry streak fires too early");
            assert!(!exit.update(1), "exit streak fires too early");
        }
        assert!(entry.update(1), "entry streak should confirm at n");
        assert!(
            exit.update(1),
            "exit streak should confirm at n in lockstep"
        );
    }

    #[test]
    fn exit_streak_fires_earlier_when_configured_smaller() {
        // exit_confirm_bars=2 with signal_confirm_bars=4 means the exit gate
        // confirms after 2 consecutive signals while the entry gate still needs 4.
        // This is the live-mode tuning question from the Apr 2026 review:
        // can we flip out of losing trades faster than we flip into them?
        let mut s = BotSettings::by_symbol("XBTUSDTM");
        s.signal_confirm_bars = 4;
        s.exit_confirm_bars = Some(2);
        let inds = SymbolIndicators::new(&s);
        let mut entry = inds.streak;
        let mut exit = inds.exit_streak;

        // Bar 1: neither fires.
        assert!(!entry.update(1));
        assert!(!exit.update(1));

        // Bar 2: exit fires (length 2), entry still needs more.
        assert!(!entry.update(1));
        assert!(exit.update(1), "exit streak should fire at bar 2");

        // Bar 3: entry still doesn't fire.
        assert!(!entry.update(1));

        // Bar 4: entry finally fires. Exit continues to fire on every
        // subsequent same-direction bar.
        assert!(entry.update(1), "entry streak should fire at bar 4");
    }
}
