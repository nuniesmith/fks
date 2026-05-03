"""
utils/state.py
===============
Shared dataclasses and constants for per-worker runtime state.

Extracted from main.py so they can be imported by workers, indicators,
the optimizer, and tests without pulling in the full trading stack.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

# ── Signal confirmation ────────────────────────────────────────────
# How many consecutive loop ticks the entry signal must hold before
# we place an order.  Increase to filter noise at the cost of
# slightly later entries.
SIGNAL_CONFIRM_BARS: int = 2


# ═══════════════════════════════════════════════════════════════════
# Wave analysis state
# ═══════════════════════════════════════════════════════════════════


@dataclass
class WaveState:
    """Persistent wave-analysis state, held per AssetWorker.

    Fields are updated by utils.indicators.update_wave_state() on
    each candle tick.

    Attributes:
        bull_waves:  Ring buffer of peak speeds from completed bull waves.
        bear_waves:  Ring buffer of trough speeds from completed bear waves.
        wr_history:  History of wave_ratio values (for percentile ranking).
        mom_history: History of |cur_ratio| values (for percentile ranking).
        wave_ratio:  bull_avg / |bear_avg| — > 1.0 means bulls stronger.
        wr_pct:      Percentile rank of wave_ratio in wr_history.
        cur_ratio:   Current speed relative to the active wave's average.
        mom_pct:     Percentile rank of |cur_ratio| in mom_history.
        last_above:  Whether close was above EMA on the previous bar.
        bias:        "Bullish" | "Bearish" | "Neutral".
        rma_speed:   Latest RMA speed value (c_rma - o_rma).
    """

    bull_waves: deque = field(default_factory=lambda: deque(maxlen=200))
    bear_waves: deque = field(default_factory=lambda: deque(maxlen=200))
    wr_history: deque = field(default_factory=lambda: deque(maxlen=200))
    mom_history: deque = field(default_factory=lambda: deque(maxlen=200))
    wave_ratio: float = 1.0
    wr_pct: float = 0.5
    cur_ratio: float = 0.0
    mom_pct: float = 0.5
    last_above: bool = False
    bias: str = "Neutral"
    rma_speed: float = 0.0

    def reset(self) -> None:
        """Clear accumulated history without replacing the object reference."""
        self.bull_waves.clear()
        self.bear_waves.clear()
        self.wr_history.clear()
        self.mom_history.clear()
        self.wave_ratio = 1.0
        self.wr_pct = 0.5
        self.cur_ratio = 0.0
        self.mom_pct = 0.5
        self.last_above = False
        self.bias = "Neutral"
        self.rma_speed = 0.0


# ═══════════════════════════════════════════════════════════════════
# Signal streak tracker
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SignalStreak:
    """Track how many consecutive ticks the current signal has held.

    Used to require SIGNAL_CONFIRM_BARS of agreement before acting
    on an entry signal.  Prevents acting on single-bar noise spikes.

    Usage:
        streak = SignalStreak()
        streak.update("buy")
        if streak.confirmed():
            ...place order...
    """

    direction: str | None = None
    count: int = 0

    def update(self, signal: str | None) -> None:
        """Record the signal for the current tick.

        If the signal is the same as the previous tick the streak
        count increments.  Any change (including to None) resets it.

        Args:
            signal: "buy", "sell", or None (no signal this tick).
        """
        if signal == self.direction:
            self.count += 1
        else:
            self.direction = signal
            self.count = 1 if signal is not None else 0

    def confirmed(self, required: int = SIGNAL_CONFIRM_BARS) -> bool:
        """Return True when the current direction has held for *required* ticks.

        Args:
            required: Number of consecutive ticks required (default
                      SIGNAL_CONFIRM_BARS = 2).

        Returns:
            True → signal is confirmed; False → still building streak.
        """
        return self.count >= required

    def reset(self) -> None:
        """Reset the streak to a neutral state."""
        self.direction = None
        self.count = 0
