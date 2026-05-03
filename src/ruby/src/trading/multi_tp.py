"""
Multi-TP/SL with trailing stop tightening.

Instead of all-or-nothing exits, this module implements a ladder of
take-profit levels with partial closes. After each TP level is hit,
the trailing stop tightens to lock in more profit.

Default levels (configurable via YAML):
  TP1: 1.0R → close 25%, trail at 1.5×ATR
  TP2: 2.0R → close 50%, trail at 1.0×ATR
  TP3: 3.0R → close 75%, trail at 0.75×ATR
  TP4: 5.0R → close 100%, trail at 0.5×ATR

Where R = ATR at entry time (the "risk unit").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from utils.logging_config import get_logger

logger = get_logger("multi_tp")


@dataclass
class TPLevel:
    """One level in the take-profit ladder."""

    r_multiple: float  # how many R (ATR multiples) for this TP
    close_pct: float  # fraction of ORIGINAL position to close (cumulative)
    trail_atr_mult: float  # trailing stop distance as ATR multiple after this TP hits


@dataclass
class TPAction:
    """Action to take based on price movement."""

    action: str  # "partial_close", "full_close", "trailing_stop", "none"
    close_size: float = 0.0  # contracts to close (for partial/full)
    reason: str = ""
    new_trail_price: float = 0.0  # updated trailing stop price (0 = no change)
    level_hit: int = -1  # which TP level was hit (-1 = none)


class MultiTPManager:
    """Manages multi-TP state for a single position.

    Parameters
    ----------
    entry_price : float
        Average entry price.
    direction : str
        "buy" or "sell".
    total_size : float
        Total position size in contracts.
    atr : float
        ATR value at entry time (the "risk unit").
    sl_pct : float
        Stop loss percentage (used as fallback before any TP is hit).
    levels : list[TPLevel]
        TP ladder levels.
    """

    def __init__(
        self,
        entry_price: float,
        direction: str,
        total_size: float,
        atr: float,
        sl_pct: float,
        levels: list[TPLevel] | None = None,
    ) -> None:
        self.entry_price = entry_price
        self.direction = direction
        self.total_size = total_size
        self.remaining_size = total_size
        self.atr = max(atr, 1e-10)
        self.sl_pct = sl_pct

        # Default levels if not provided
        self.levels = levels or [
            TPLevel(r_multiple=1.0, close_pct=0.25, trail_atr_mult=1.5),
            TPLevel(r_multiple=2.0, close_pct=0.50, trail_atr_mult=1.0),
            TPLevel(r_multiple=3.0, close_pct=0.75, trail_atr_mult=0.75),
            TPLevel(r_multiple=5.0, close_pct=1.00, trail_atr_mult=0.50),
        ]

        self.current_level = 0  # index of next TP level to check
        self.highest_favorable = entry_price  # for trailing stop
        self.trailing_stop: float | None = None  # None = use SL, set after TP1

        # Initial stop loss based on sl_pct
        if direction == "buy":
            self.stop_loss = entry_price * (1 - sl_pct)
        else:
            self.stop_loss = entry_price * (1 + sl_pct)

    def _price_move_r(self, current_price: float) -> float:
        """How many R (ATR multiples) the price has moved in our favor."""
        if self.direction == "buy":
            return (current_price - self.entry_price) / self.atr
        else:
            return (self.entry_price - current_price) / self.atr

    def _update_trailing(self, current_price: float) -> None:
        """Update highest favorable price and trailing stop."""
        if self.direction == "buy":
            if current_price > self.highest_favorable:
                self.highest_favorable = current_price
        else:
            if current_price < self.highest_favorable:
                self.highest_favorable = current_price

        # Update trailing stop if we have one
        if self.trailing_stop is not None and self.current_level > 0:
            level = self.levels[self.current_level - 1]
            trail_dist = self.atr * level.trail_atr_mult
            if self.direction == "buy":
                new_trail = self.highest_favorable - trail_dist
                if new_trail > self.trailing_stop:
                    self.trailing_stop = new_trail
            else:
                new_trail = self.highest_favorable + trail_dist
                if new_trail < self.trailing_stop:
                    self.trailing_stop = new_trail

    def check(self, current_price: float) -> TPAction:
        """Check current price against TP levels and stops.

        Returns a TPAction describing what to do (if anything).
        Call this on every price tick.
        """
        if self.remaining_size <= 0:
            return TPAction(action="none")

        # Update trailing stop tracking
        self._update_trailing(current_price)

        # Check stop loss / trailing stop first
        effective_stop = self.trailing_stop if self.trailing_stop is not None else self.stop_loss
        if self.direction == "buy" and current_price <= effective_stop:
            stop_type = "trailing" if self.trailing_stop is not None else "initial"
            return TPAction(
                action="full_close",
                close_size=self.remaining_size,
                reason=f"Stop Loss ({stop_type}) at {effective_stop:.4f}",
            )
        if self.direction == "sell" and current_price >= effective_stop:
            stop_type = "trailing" if self.trailing_stop is not None else "initial"
            return TPAction(
                action="full_close",
                close_size=self.remaining_size,
                reason=f"Stop Loss ({stop_type}) at {effective_stop:.4f}",
            )

        # Check TP levels
        if self.current_level >= len(self.levels):
            return TPAction(action="none")  # all levels exhausted

        move_r = self._price_move_r(current_price)
        level = self.levels[self.current_level]

        if move_r >= level.r_multiple:
            # TP level hit!
            # Calculate how much to close at this level
            # close_pct is cumulative — subtract what we've already closed
            already_closed_pct = 0.0
            if self.current_level > 0:
                already_closed_pct = self.levels[self.current_level - 1].close_pct

            level_close_pct = level.close_pct - already_closed_pct
            close_size = self.total_size * level_close_pct

            # Don't close more than remaining
            close_size = min(close_size, self.remaining_size)

            # Set up trailing stop for next phase
            trail_dist = self.atr * level.trail_atr_mult
            if self.direction == "buy":
                self.trailing_stop = self.highest_favorable - trail_dist
            else:
                self.trailing_stop = self.highest_favorable + trail_dist

            level_idx = self.current_level
            self.current_level += 1
            self.remaining_size -= close_size

            is_full = self.remaining_size <= 0 or level.close_pct >= 1.0
            action = "full_close" if is_full else "partial_close"

            return TPAction(
                action=action,
                close_size=close_size,
                reason=(
                    f"TP{level_idx + 1} ({level.r_multiple:.1f}R) — "
                    f"close {level_close_pct:.0%}, trail at {level.trail_atr_mult:.1f}xATR"
                ),
                new_trail_price=self.trailing_stop,
                level_hit=level_idx,
            )

        return TPAction(action="none")

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for Redis persistence."""
        return {
            "entry_price": self.entry_price,
            "direction": self.direction,
            "total_size": self.total_size,
            "remaining_size": self.remaining_size,
            "atr": self.atr,
            "sl_pct": self.sl_pct,
            "current_level": self.current_level,
            "highest_favorable": self.highest_favorable,
            "trailing_stop": self.trailing_stop,
            "stop_loss": self.stop_loss,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], levels: list[TPLevel] | None = None) -> MultiTPManager:
        """Restore from serialized state."""
        mgr = cls(
            entry_price=data["entry_price"],
            direction=data["direction"],
            total_size=data["total_size"],
            atr=data["atr"],
            sl_pct=data["sl_pct"],
            levels=levels,
        )
        mgr.remaining_size = data.get("remaining_size", mgr.total_size)
        mgr.current_level = data.get("current_level", 0)
        mgr.highest_favorable = data.get("highest_favorable", mgr.entry_price)
        mgr.trailing_stop = data.get("trailing_stop")
        mgr.stop_loss = data.get("stop_loss", mgr.stop_loss)
        return mgr


def parse_tp_levels(config_levels: list[dict[str, Any]]) -> list[TPLevel]:
    """Parse TP levels from config YAML format.

    Each item in *config_levels* is a dict like::

        {"r_multiple": 1.0, "close_pct": 0.25, "trail_atr": 1.5}

    Returns a list of :class:`TPLevel` sorted by ``r_multiple`` ascending.
    """
    levels: list[TPLevel] = []
    for item in config_levels:
        levels.append(
            TPLevel(
                r_multiple=float(item.get("r_multiple", 1.0)),
                close_pct=float(item.get("close_pct", 1.0)),
                trail_atr_mult=float(item.get("trail_atr", 1.0)),
            )
        )
    # Sort by r_multiple ascending
    levels.sort(key=lambda lv: lv.r_multiple)
    return levels
