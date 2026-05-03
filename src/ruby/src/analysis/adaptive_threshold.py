"""
Adaptive confidence threshold for CNN signal gating.

Instead of a fixed min_confidence threshold, this module adjusts the
threshold up or down based on recent trade outcomes:
  - Consecutive wins → lower threshold (trust the model more)
  - Consecutive losses → raise threshold (require higher confidence)

The threshold is bounded between base * (1 - max_adjustment) and
base * (1 + max_adjustment) to prevent extreme drift.

Redis keys used:
    futures:adaptive_thresh:{asset}  — current threshold value
    futures:thresh_outcomes:{asset}  — recent outcome history
"""

from __future__ import annotations

import json
from typing import Any

from utils.logging_config import get_logger

logger = get_logger("adaptive_threshold")


class AdaptiveThreshold:
    """Per-asset adaptive confidence threshold.

    Parameters
    ----------
    store : RedisStore
        Redis store for persistent state.
    base_threshold : float
        Starting / center threshold (default 0.60).
    learning_rate : float
        How much to adjust per outcome (default 0.02).
    max_adjustment : float
        Maximum deviation from base as a fraction (default 0.25).
        With base=0.60, range would be [0.45, 0.75].
    target_win_rate : float
        Target win rate; threshold adjusts to try to achieve this (default 0.55).
    """

    def __init__(
        self,
        store: Any,
        base_threshold: float = 0.60,
        learning_rate: float = 0.02,
        max_adjustment: float = 0.25,
        target_win_rate: float = 0.55,
    ) -> None:
        self._store = store
        self._base = base_threshold
        self._lr = learning_rate
        self._max_adj = max_adjustment
        self._target_wr = target_win_rate

        # Bounds
        self._min_thresh = base_threshold * (1.0 - max_adjustment)
        self._max_thresh = base_threshold * (1.0 + max_adjustment)

        # In-memory cache (loaded from Redis on first access)
        self._cached: dict[str, float] = {}

    def _thresh_key(self, asset: str) -> str:
        return f"adaptive_thresh:{asset}"

    async def get_threshold(self, asset: str) -> float:
        """Get the current adaptive threshold for an asset.

        Returns the base threshold if no history exists.
        """
        if asset in self._cached:
            return self._cached[asset]

        val = await self._store._get(self._store._key(self._thresh_key(asset)))
        if val is not None:
            threshold = float(val)
            self._cached[asset] = threshold
            return threshold

        # No stored value — use base
        self._cached[asset] = self._base
        return self._base

    async def record_outcome(self, asset: str, is_win: bool) -> float:
        """Record a trade outcome and adjust the threshold.

        - Win → lower threshold (trust model more, take more signals)
        - Loss → raise threshold (require higher confidence)

        Returns the new threshold value.
        """
        current = await self.get_threshold(asset)

        if is_win:
            # Win: decrease threshold (be more aggressive)
            delta = -self._lr
        else:
            # Loss: increase threshold (be more conservative)
            delta = self._lr

        new_thresh = max(self._min_thresh, min(self._max_thresh, current + delta))

        # Persist to Redis
        await self._store._set(
            self._store._key(self._thresh_key(asset)),
            f"{new_thresh:.4f}",
        )
        self._cached[asset] = new_thresh

        logger.info(
            "[%s] Adaptive threshold: %s → %.4f (was %.4f, delta=%+.4f)",
            asset.upper(),
            "win" if is_win else "loss",
            new_thresh,
            current,
            delta,
        )

        return new_thresh

    async def reset(self, asset: str) -> None:
        """Reset threshold to base (e.g. after retraining)."""
        await self._store._set(
            self._store._key(self._thresh_key(asset)),
            f"{self._base:.4f}",
        )
        self._cached[asset] = self._base
        logger.info("[%s] Adaptive threshold reset to base %.4f", asset.upper(), self._base)
