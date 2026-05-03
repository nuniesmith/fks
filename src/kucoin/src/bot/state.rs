//! `BotState` — all mutable runtime state for one trading symbol.

use std::sync::Arc;

use crate::BotSettings;
use exchange_apiws::rest::account::PositionInfo;

use crate::types::Position;

/// All mutable state for one trading symbol.
#[derive(Clone)]
pub struct BotState {
    /// Strategy parameters. Wrapped in `Arc` so cloning `BotState` (which
    /// happens every candle in the Phase 1 snapshot) is O(1) — no heap
    /// allocation — instead of a deep copy of dozens of fields.
    pub settings: Arc<BotSettings>,

    // ── Position ──────────────────────────────────────────────────────────────
    /// Current signed contract count from the exchange.
    pub position: Position,
    pub entry_price: Option<f64>,
    pub unrealised_pnl: f64,

    // ── Account ───────────────────────────────────────────────────────────────
    pub balance: f64,

    // ── Signal tracking ───────────────────────────────────────────────────────
    /// Last confirmed signal: +1 long, -1 short, 0 flat.
    pub last_signal: i8,
    /// Candles held since the current position was opened.
    pub bars_since_entry: usize,
}

// `missing_const_for_fn` nursery lint: `new` takes `Arc<BotSettings>` (Arc
// is not const-constructible), and `tick_bars_held` mutates runtime state.
#[allow(clippy::missing_const_for_fn)]
impl BotState {
    pub fn new(settings: Arc<BotSettings>) -> Self {
        Self {
            settings,
            position: Position(0),
            entry_price: None,
            unrealised_pnl: 0.0,
            balance: 0.0,
            last_signal: 0,
            bars_since_entry: 0,
        }
    }

    /// Sync position and balance from a REST `PositionInfo` response.
    ///
    /// On a non-flat sync (e.g. startup adoption of a pre-existing position
    /// after a crash) `bars_since_entry` is set to the configured
    /// `min_hold_candles`. We don't actually know how long the position has
    /// been open — the exchange position blob doesn't carry an open time we
    /// can rely on — so we pick the conservative default that:
    ///
    /// * lets the next valid signal flip immediately (the min-hold gate is
    ///   already satisfied), so we don't artificially trap the position in
    ///   place after a restart, AND
    /// * starts the `max_hold_candles` countdown from baseline rather than
    ///   from a guessed elapsed value, so we won't fire max-hold prematurely
    ///   on a position that has already been held for hours.
    ///
    /// This is intentionally a one-shot heuristic — once trading resumes and
    /// the next flip occurs, the counter resumes its normal lifecycle.
    pub fn sync_position(&mut self, info: &PositionInfo) {
        self.position = Position(info.current_qty);
        self.entry_price = info.avg_entry_price;
        self.unrealised_pnl = info.unrealised_pnl.unwrap_or(0.0);
        if !info.is_flat() {
            self.bars_since_entry = self.settings.min_hold_candles;
        }
    }

    /// Increment the open-position bar counter, or reset when flat.
    pub fn tick_bars_held(&mut self) {
        if self.position.is_flat() {
            self.bars_since_entry = 0;
        } else {
            self.bars_since_entry += 1;
        }
    }
}
