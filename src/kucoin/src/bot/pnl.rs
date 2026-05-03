//! Realised P&L bookkeeping for a single bot session.
//!
//! Every trade close and the final session summary are emitted with
//! `target: "pnl"` so the dedicated `logs/pnl.log` subscriber layer can
//! capture them independently of the main bot log.

/// Running totals accumulated across all trades in the current session.
#[derive(Debug, Default, Clone)]
pub struct PnlTracker {
    /// The futures symbol this tracker belongs to (e.g. `"XBTUSDTM"`).
    pub symbol: String,
    /// Gross realised PnL in USDT (before fees).
    pub realised_usdt: f64,
    /// Cumulative round-trip fees in USDT.
    pub total_fees: f64,
    pub trade_count: u32,
    pub win_count: u32,
    pub loss_count: u32,
    pub breakeven_count: u32,
    /// If set, halts trading for the rest of the session once net P&L drops
    /// to or below this threshold (USDT, should be negative, e.g. -50.0).
    pub session_loss_limit: Option<f64>,
    /// Set to true the first time `net_pnl()` crosses `session_loss_limit`.
    /// Once set it is never cleared within a session — use `reset_session`
    /// at the daily rollover to re-arm it for the new day.
    pub session_halted: bool,
}

impl PnlTracker {
    pub fn new(symbol: impl Into<String>) -> Self {
        Self {
            symbol: symbol.into(),
            ..Self::default()
        }
    }

    /// Attach a per-session net-loss ceiling (negative USDT value).
    ///
    /// Once `net_pnl()` drops to or below `limit_usdt` after any trade close,
    /// `is_session_halted()` returns `true` and `should_skip_entry` will
    /// block all further entries for the lifetime of this session.
    ///
    /// The limit is preserved across `reset_session` calls so it
    /// automatically re-arms itself at each daily rollover.
    ///
    /// Example: `PnlTracker::new("XBTUSDTM").with_session_limit(-50.0)`
    #[must_use]
    pub const fn with_session_limit(mut self, limit_usdt: f64) -> Self {
        self.session_loss_limit = Some(limit_usdt);
        self
    }

    /// Returns `true` when the session drawdown cap has been breached.
    /// Once tripped this never resets within a session — call `reset_session`
    /// at the daily 00:00 UTC rollover to re-arm it for the new day.
    pub const fn is_session_halted(&self) -> bool {
        self.session_halted
    }

    /// Update the per-session net-loss ceiling at runtime.
    ///
    /// Used by the hot-reload path so a change to `session_loss_limit_usdt`
    /// in `BotSettings` takes effect without a bot restart.  The new limit
    /// is evaluated on the next `record_close` call.
    ///
    /// Deliberately does NOT clear `session_halted` — if the session is
    /// already halted under the previous limit, it stays halted until the
    /// daily rollover.  This prevents a hot-reload from accidentally re-arming
    /// trading after a drawdown breach.
    pub const fn set_session_loss_limit(&mut self, limit_usdt: f64) {
        self.session_loss_limit = Some(limit_usdt);
    }

    /// Record the outcome of a closed trade and emit a PnL log line.
    ///
    /// * `pnl` — gross realised PnL in USDT (positive = profit, negative = loss).
    /// * `fee` — total round-trip taker/maker fee in USDT.
    pub fn record_close(&mut self, pnl: f64, fee: f64) {
        self.realised_usdt += pnl;
        self.total_fees += fee;
        self.trade_count += 1;

        // Classify on NET (after fee) so fee-flipped trades don't inflate win_count
        // or suppress the circuit breaker.  A gross win of $1 with a $3 fee is a
        // real loss and must be counted as one.
        let net = pnl - fee;
        #[allow(clippy::float_cmp)]
        if net > 0.0 {
            self.win_count += 1;
        } else if net < 0.0 {
            self.loss_count += 1;
        } else {
            self.breakeven_count += 1;
        }

        // Routed to logs/pnl.log by the `target: "pnl"` subscriber filter.
        tracing::info!(
            target: "pnl",
            symbol      = %self.symbol,
            trade       = self.trade_count,
            pnl_usdt    = format!("{:.4}", pnl),
            fee_usdt    = format!("{:.4}", fee),
            net_usdt    = format!("{:.4}", net),
            outcome     = if net > 0.0 { "WIN" } else if net < 0.0 { "LOSS" } else { "BREAKEVEN" },
            running_net = format!("{:.4}", self.net_pnl()),
            "trade closed",
        );

        // ── Session drawdown cap ──────────────────────────────────────────
        // Evaluated after updating totals so the trade that crosses the
        // threshold is the one that trips the halt, not the one after it.
        // Uses `<=` so reaching the limit exactly also trips the halt.
        if let Some(limit) = self.session_loss_limit
            && !self.session_halted
            && self.net_pnl() <= limit
        {
            self.session_halted = true;
            tracing::warn!(
                target: "pnl",
                symbol      = %self.symbol,
                net_pnl     = format!("{:.4} USDT", self.net_pnl()),
                limit       = format!("{:.4} USDT", limit),
                "session loss limit breached — trading halted for rest of session",
            );
        }
    }

    /// Net PnL after subtracting cumulative fees.
    pub fn net_pnl(&self) -> f64 {
        self.realised_usdt - self.total_fees
    }

    /// Win-rate is computed over decided trades only (wins + losses), excluding break-evens.
    pub fn win_rate(&self) -> f64 {
        let decided = self.win_count + self.loss_count;
        if decided == 0 {
            return 0.0;
        }
        f64::from(self.win_count) / f64::from(decided)
    }

    /// Emit a session-summary line to both the main log and `pnl.log`.
    pub fn log_summary(&self) {
        tracing::info!(
            target: "pnl",
            symbol     = %self.symbol,
            trades     = self.trade_count,
            wins       = self.win_count,
            losses     = self.loss_count,
            breakevens = self.breakeven_count,
            win_rate   = format!("{:.1}%", self.win_rate() * 100.0),
            gross      = format!("{:.4} USDT", self.realised_usdt),
            fees       = format!("{:.4} USDT", self.total_fees),
            net        = format!("{:.4} USDT", self.net_pnl()),
            "session P&L summary",
        );
    }

    /// Reset all session accumulators for a new calendar day.
    ///
    /// Called by the candle-poll task at 00:00 UTC so the drawdown cap and
    /// P&L totals are cleared exactly once per day without requiring a bot
    /// restart. The `session_loss_limit` is intentionally preserved so the
    /// cap automatically re-arms itself for the new session.
    pub fn reset_session(&mut self) {
        tracing::info!(
            target: "pnl",
            symbol     = %self.symbol,
            trades     = self.trade_count,
            wins       = self.win_count,
            losses     = self.loss_count,
            breakevens = self.breakeven_count,
            gross      = format!("{:.4} USDT", self.realised_usdt),
            fees       = format!("{:.4} USDT", self.total_fees),
            net        = format!("{:.4} USDT", self.net_pnl()),
            "daily session reset — rolling over to new session",
        );

        self.realised_usdt = 0.0;
        self.total_fees = 0.0;
        self.trade_count = 0;
        self.win_count = 0;
        self.loss_count = 0;
        self.breakeven_count = 0;
        self.session_halted = false;
        // session_loss_limit is deliberately kept — re-arms for the new day.
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record_close: outcome classification ─────────────────────────────────

    #[test]
    fn win_classified_on_net_not_gross() {
        let mut t = PnlTracker::new("TEST");
        // Gross profit but fee makes it a net loss — must count as a LOSS.
        t.record_close(1.0, 3.0); // net = -2.0
        assert_eq!(t.win_count, 0);
        assert_eq!(t.loss_count, 1);
    }

    #[test]
    fn clean_win_increments_win_count() {
        let mut t = PnlTracker::new("TEST");
        t.record_close(10.0, 1.0); // net = +9.0
        assert_eq!(t.win_count, 1);
        assert_eq!(t.loss_count, 0);
    }

    #[test]
    fn exact_breakeven_increments_breakeven_count() {
        let mut t = PnlTracker::new("TEST");
        t.record_close(5.0, 5.0); // net = 0.0
        assert_eq!(t.breakeven_count, 1);
        assert_eq!(t.win_count, 0);
        assert_eq!(t.loss_count, 0);
    }

    #[test]
    fn net_pnl_is_gross_minus_fees() {
        let mut t = PnlTracker::new("TEST");
        t.record_close(100.0, 3.0);
        t.record_close(-20.0, 2.0);
        // gross = 80.0, fees = 5.0, net = 75.0
        assert!((t.net_pnl() - 75.0).abs() < 1e-9);
    }

    #[test]
    fn trade_count_accumulates() {
        let mut t = PnlTracker::new("TEST");
        for _ in 0..5 {
            t.record_close(1.0, 0.1);
        }
        assert_eq!(t.trade_count, 5);
    }

    // ── win_rate ─────────────────────────────────────────────────────────────

    #[test]
    fn win_rate_zero_when_no_trades() {
        let t = PnlTracker::new("TEST");
        assert_eq!(t.win_rate(), 0.0);
    }

    #[test]
    fn win_rate_excludes_breakevens() {
        let mut t = PnlTracker::new("TEST");
        t.record_close(10.0, 1.0); // win
        t.record_close(-5.0, 1.0); // loss
        t.record_close(1.0, 1.0); // breakeven
        // decided = 2, wins = 1 → 50%
        assert!((t.win_rate() - 0.5).abs() < 1e-9);
    }

    // ── session_loss_limit ────────────────────────────────────────────────────

    #[test]
    fn session_halted_after_limit_breach() {
        let mut t = PnlTracker::new("TEST").with_session_limit(-10.0);
        assert!(!t.is_session_halted());
        t.record_close(-5.0, 1.0); // net = -6 → above limit
        assert!(!t.is_session_halted());
        t.record_close(-5.0, 1.0); // net = -12 → below -10 limit
        assert!(t.is_session_halted());
    }

    #[test]
    fn session_halt_is_permanent() {
        let mut t = PnlTracker::new("TEST").with_session_limit(-10.0);
        t.record_close(-20.0, 0.0); // trips the halt
        assert!(t.is_session_halted());
        t.record_close(100.0, 0.0); // large win can't un-halt
        assert!(t.is_session_halted());
    }

    #[test]
    fn session_not_halted_when_no_limit_set() {
        let mut t = PnlTracker::new("TEST");
        t.record_close(-999.0, 0.0);
        assert!(!t.is_session_halted());
    }

    #[test]
    fn session_halted_exactly_at_limit() {
        // The trade that lands exactly on the limit must trip the halt
        // (uses <= so the boundary itself is included).
        let mut t = PnlTracker::new("TEST").with_session_limit(-10.0);
        t.record_close(-10.0, 0.0); // net == limit exactly → should trip
        assert!(t.is_session_halted());
    }

    // ── reset_session ─────────────────────────────────────────────────────────

    #[test]
    fn reset_session_clears_all_accumulators() {
        let mut t = PnlTracker::new("TEST").with_session_limit(-50.0);
        t.record_close(10.0, 1.0); // win
        t.record_close(-5.0, 1.0); // loss
        t.record_close(3.0, 3.0); // breakeven

        t.reset_session();

        assert_eq!(t.trade_count, 0);
        assert_eq!(t.win_count, 0);
        assert_eq!(t.loss_count, 0);
        assert_eq!(t.breakeven_count, 0);
        assert!((t.realised_usdt).abs() < 1e-9);
        assert!((t.total_fees).abs() < 1e-9);
        assert!((t.net_pnl()).abs() < 1e-9);
    }

    #[test]
    fn reset_session_re_arms_halt() {
        let mut t = PnlTracker::new("TEST").with_session_limit(-10.0);
        t.record_close(-20.0, 0.0); // trips halt
        assert!(t.is_session_halted());

        t.reset_session(); // daily rollover

        assert!(
            !t.is_session_halted(),
            "halt should be re-armed after reset"
        );
        // limit is preserved — a new breach on the new day halts again
        t.record_close(-15.0, 0.0);
        assert!(t.is_session_halted());
    }

    #[test]
    fn reset_session_preserves_loss_limit() {
        let mut t = PnlTracker::new("TEST").with_session_limit(-25.0);
        t.reset_session();
        assert_eq!(t.session_loss_limit, Some(-25.0));
    }

    #[test]
    fn reset_session_accumulates_fresh_after_rollover() {
        let mut t = PnlTracker::new("TEST");
        t.record_close(100.0, 5.0); // session 1
        t.reset_session();

        t.record_close(20.0, 1.0); // session 2
        assert_eq!(t.trade_count, 1);
        assert!((t.net_pnl() - 19.0).abs() < 1e-9);
    }

    // ── set_session_loss_limit (hot-reload) ──────────────────────────────────

    #[test]
    fn set_session_loss_limit_takes_effect_on_next_close() {
        let mut t = PnlTracker::new("TEST").with_session_limit(-100.0);
        t.record_close(-30.0, 1.0); // net -31, well under -100 → no halt
        assert!(!t.is_session_halted());

        // Tighten the limit to -50. A close that brings net to -32 + -19 = -51
        // should now trip the halt under the new limit.
        t.set_session_loss_limit(-50.0);
        t.record_close(-18.0, 1.0); // net = -50 → trips at boundary (≤)
        assert!(
            t.is_session_halted(),
            "tightened limit must apply on next close"
        );
    }

    #[test]
    fn set_session_loss_limit_does_not_clear_active_halt() {
        let mut t = PnlTracker::new("TEST").with_session_limit(-10.0);
        t.record_close(-20.0, 0.0); // halted
        assert!(t.is_session_halted());

        // Loosen the limit dramatically. Halt must persist until reset_session.
        t.set_session_loss_limit(-1000.0);
        assert!(
            t.is_session_halted(),
            "loosening the limit must not un-halt an already-halted session"
        );
    }
}
