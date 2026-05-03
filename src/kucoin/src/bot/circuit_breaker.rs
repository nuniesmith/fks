//! Sliding-window circuit breaker.
//!
//! Trips when `breaker_loss_limit` losses occur within a rolling
//! `breaker_window_sec` window. Once tripped, entries are blocked for
//! `breaker_cooldown_sec` seconds before auto-resetting.
//!
//! The sliding-window design replaces the older consecutive-loss approach,
//! which was defeated by losses spaced hours apart resetting the count
//! before the threshold was hit. See review notes for Apr 20–21 2026.

use crate::BotSettings;
use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};

fn now_unix_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock is before UNIX epoch")
        .as_secs()
}

#[derive(Clone)]
pub struct CircuitBreaker {
    /// Timestamps (Unix seconds) of recent LOSS trades.
    /// Wins are not stored — they don't contribute to tripping the breaker,
    /// and keeping the buffer loss-only makes the count O(1) (== len()).
    recent_losses: VecDeque<u64>,

    /// Number of losses within `window_secs` that trips the breaker.
    limit: u32,

    /// Rolling lookback window in seconds (e.g. 14400 = 4h).
    window_secs: u64,

    /// How long the breaker stays tripped once fired.
    cooldown_secs: u64,

    /// Unix timestamp (seconds) when the breaker was last tripped, or `None`.
    /// Using wall-clock seconds (not `Instant`) is suspend-safe and serialisable.
    tripped_at_unix_secs: Option<u64>,
}

// `missing_const_for_fn` is a nursery lint. None of these can be const:
// `new` reads runtime settings, the `&mut self` methods mutate heap state
// and the `&self` methods call `SystemTime::now()`.
#[allow(clippy::missing_const_for_fn)]
impl CircuitBreaker {
    pub fn new(s: &BotSettings) -> Self {
        Self {
            recent_losses: VecDeque::with_capacity(16),
            limit: s.breaker_loss_limit as u32,
            window_secs: s.breaker_window_sec,
            cooldown_secs: s.breaker_cooldown_sec,
            tripped_at_unix_secs: None,
        }
    }

    /// Auto-reset the breaker if the cooldown window has elapsed,
    /// and evict stale loss timestamps so memory stays bounded.
    /// Call once at the start of every candle cycle.
    pub fn tick(&mut self) {
        let now = now_unix_secs();
        if let Some(t) = self.tripped_at_unix_secs
            && now.saturating_sub(t) >= self.cooldown_secs
        {
            self.reset();
        }
        self.evict_old(now);
    }

    /// Record a losing trade. Trips the breaker if the rolling count
    /// within `window_secs` reaches `limit`.
    pub fn record_loss(&mut self) {
        let now = now_unix_secs();
        self.recent_losses.push_back(now);
        self.evict_old(now);

        let loss_count = self.recent_losses.len() as u32;
        if loss_count >= self.limit {
            self.tripped_at_unix_secs = Some(now);
        }
    }

    /// Record a winning trade.
    ///
    /// # Important: does NOT clear `tripped_at_unix_secs`
    ///
    /// Once tripped, only elapsed cooldown can un-trip the breaker.
    /// A single win is not evidence that market conditions have recovered.
    ///
    /// In the sliding-window design a win is not stored at all — only
    /// loss timestamps live in the buffer — because a win does not help
    /// the strategy survive the next loss burst. If you later want wins
    /// to offset losses (e.g. "3 losses minus 1 win = 2 effective losses"),
    /// store wins as well and subtract from the count in `record_loss`.
    pub fn record_win(&mut self) {
        // Cooldown-window maintenance only.
        self.evict_old(now_unix_secs());
    }

    /// Returns `true` while the breaker is tripped AND cooldown has not yet elapsed.
    pub fn is_tripped(&self) -> bool {
        self.tripped_at_unix_secs
            .is_some_and(|t| now_unix_secs().saturating_sub(t) < self.cooldown_secs)
    }

    /// Clear the tripped state and the recent-loss buffer.
    pub fn reset(&mut self) {
        self.recent_losses.clear();
        self.tripped_at_unix_secs = None;
    }

    /// Number of losses currently within the rolling window.
    /// Exposed for observability (heartbeat / Redis).
    pub fn recent_loss_count(&self) -> usize {
        self.recent_losses.len()
    }

    /// Drop loss timestamps that have fallen out of the rolling window.
    fn evict_old(&mut self, now: u64) {
        let cutoff = now.saturating_sub(self.window_secs);
        while let Some(&ts) = self.recent_losses.front() {
            if ts < cutoff {
                self.recent_losses.pop_front();
            } else {
                break;
            }
        }
    }

    /// Update the breaker's configuration from a refreshed `BotSettings`.
    ///
    /// Used by the hot-reload path so a change to `breaker_loss_limit`,
    /// `breaker_window_sec`, or `breaker_cooldown_sec` takes effect on the
    /// running bot without a restart.
    ///
    /// Deliberately preserves `recent_losses` and `tripped_at_unix_secs` —
    /// loss history and any active trip should survive a parameter change so
    /// the breaker doesn't lose its safety net mid-session.
    pub fn update_params(&mut self, s: &BotSettings) {
        self.limit = s.breaker_loss_limit as u32;
        self.window_secs = s.breaker_window_sec;
        self.cooldown_secs = s.breaker_cooldown_sec;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::BotSettings;

    fn settings_with(loss_limit: usize, window_sec: u64, cooldown_sec: u64) -> BotSettings {
        BotSettings {
            breaker_loss_limit: loss_limit,
            breaker_window_sec: window_sec,
            breaker_cooldown_sec: cooldown_sec,
            ..BotSettings::base()
        }
    }

    #[test]
    fn starts_untripped() {
        let s = settings_with(4, 14400, 3600);
        let b = CircuitBreaker::new(&s);
        assert!(!b.is_tripped());
        assert_eq!(b.recent_loss_count(), 0);
    }

    #[test]
    fn trips_when_limit_reached() {
        let s = settings_with(3, 14400, 3600);
        let mut b = CircuitBreaker::new(&s);
        b.record_loss();
        assert!(!b.is_tripped());
        b.record_loss();
        assert!(!b.is_tripped());
        b.record_loss();
        assert!(b.is_tripped(), "3rd loss should trip breaker at limit=3");
    }

    #[test]
    fn win_does_not_untrip() {
        let s = settings_with(2, 14400, 3600);
        let mut b = CircuitBreaker::new(&s);
        b.record_loss();
        b.record_loss();
        assert!(b.is_tripped());
        b.record_win();
        assert!(b.is_tripped(), "a win must not bypass the cooldown");
    }

    #[test]
    fn reset_clears_state() {
        let s = settings_with(2, 14400, 3600);
        let mut b = CircuitBreaker::new(&s);
        b.record_loss();
        b.record_loss();
        assert!(b.is_tripped());
        b.reset();
        assert!(!b.is_tripped());
        assert_eq!(b.recent_loss_count(), 0);
    }

    #[test]
    fn loss_count_reflects_recent_buffer() {
        let s = settings_with(5, 14400, 3600);
        let mut b = CircuitBreaker::new(&s);
        for _ in 0..3 {
            b.record_loss();
        }
        assert_eq!(b.recent_loss_count(), 3);
        assert!(!b.is_tripped(), "under limit → not tripped");
    }

    #[test]
    fn update_params_changes_limit_without_clearing_history() {
        // Start with a permissive limit (5) and accumulate 3 losses.
        let s_loose = settings_with(5, 14400, 3600);
        let mut b = CircuitBreaker::new(&s_loose);
        for _ in 0..3 {
            b.record_loss();
        }
        assert!(!b.is_tripped(), "3 losses under limit=5 should not trip");
        assert_eq!(b.recent_loss_count(), 3);

        // Hot-reload to a tighter limit (3). The new param applies on the
        // *next* recorded loss — existing buffer is preserved so a tightened
        // limit doesn't retroactively trip on stale history.
        let s_tight = settings_with(3, 14400, 3600);
        b.update_params(&s_tight);
        assert_eq!(
            b.recent_loss_count(),
            3,
            "loss history must survive a param update"
        );

        // Next loss = 4 in buffer ≥ new limit of 3 → trip.
        b.record_loss();
        assert!(
            b.is_tripped(),
            "tightened limit must apply to subsequent losses"
        );
    }

    #[test]
    fn update_params_preserves_active_trip() {
        let s_orig = settings_with(2, 14400, 3600);
        let mut b = CircuitBreaker::new(&s_orig);
        b.record_loss();
        b.record_loss();
        assert!(b.is_tripped(), "should be tripped after 2 losses");

        // Hot-reload — must not un-trip the breaker.
        let s_new = settings_with(10, 14400, 7200);
        b.update_params(&s_new);
        assert!(
            b.is_tripped(),
            "param update must preserve an active trip — only cooldown can clear it"
        );
    }
}
