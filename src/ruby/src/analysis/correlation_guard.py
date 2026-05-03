"""
Cross-asset correlation guard.

Tracks per-asset log returns in a rolling window and blocks new entries
when too many open positions are already highly correlated with the candidate
asset. Prevents concentrating risk in a cluster of co-moving assets (e.g.
going long BTC, ETH, and SOL when all three are at 0.9+ correlation).

All operations are synchronous and in-memory — no Redis I/O. The guard is
a shared singleton passed to all AssetWorker instances that run in the same
asyncio event loop (single-threaded, no locking needed).

Usage::
    guard = CorrelationGuard(window=50, max_correlated=3, corr_threshold=0.7)

    # Each trading loop tick — feed a new log return for this asset
    guard.update("btc", log_return)

    # Before entering a new position
    open_assets = ["eth", "sol"]  # assets with positions currently open
    if guard.would_exceed_limit("btc", open_assets):
        skip_entry()

    # Periodic visibility
    matrix = guard.correlation_matrix()  # {asset: {other: corr}}
    status = guard.status()
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any

from utils.logging_config import get_logger

logger = get_logger("correlation_guard")


class CorrelationGuard:
    """In-memory rolling-window correlation guard.

    Parameters
    ----------
    window : int
        Number of recent log-return observations to keep per asset.
        50 ≈ 50 heartbeat intervals; at 5-min heartbeat that is ~4 hours.
    max_correlated : int
        Maximum number of open positions that may be highly correlated
        with a new candidate before the entry is blocked.
    corr_threshold : float
        Pearson correlation coefficient above which two assets are
        considered "highly correlated".
    """

    def __init__(
        self,
        window: int = 50,
        max_correlated: int = 3,
        corr_threshold: float = 0.7,
    ) -> None:
        self.window = window
        self.max_correlated = max_correlated
        self.corr_threshold = corr_threshold
        self._returns: dict[str, deque[float]] = {}

    # ── Data ingestion ──────────────────────────────────────────────────

    def update(self, asset: str, log_return: float) -> None:
        """Feed a new log-return observation for *asset*.

        Call this once per trading-loop tick (or heartbeat interval).
        NaN / Inf values are silently ignored.
        """
        if not math.isfinite(log_return):
            return
        if asset not in self._returns:
            self._returns[asset] = deque(maxlen=self.window)
        self._returns[asset].append(log_return)

    # ── Correlation maths ────────────────────────────────────────────────

    def pairwise_correlation(self, a: str, b: str) -> float | None:
        """Pearson correlation between assets *a* and *b*.

        Returns ``None`` when there is insufficient shared history
        (fewer than 10 observations in common).
        """
        ra = self._returns.get(a)
        rb = self._returns.get(b)
        if ra is None or rb is None:
            return None

        # Use the shorter series length as the window
        n = min(len(ra), len(rb))
        if n < 10:
            return None

        # Take the last n elements from each
        xs = list(ra)[-n:]
        ys = list(rb)[-n:]

        mean_x = sum(xs) / n
        mean_y = sum(ys) / n

        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        var_x = sum((x - mean_x) ** 2 for x in xs)
        var_y = sum((y - mean_y) ** 2 for y in ys)

        denom = math.sqrt(var_x * var_y)
        if denom < 1e-12:
            return None

        return cov / denom

    def get_correlated_count(self, new_asset: str, open_assets: list[str]) -> int:
        """Count how many assets in *open_assets* are highly correlated
        with *new_asset* (correlation >= threshold)."""
        count = 0
        for other in open_assets:
            if other == new_asset:
                continue
            corr = self.pairwise_correlation(new_asset, other)
            if corr is not None and abs(corr) >= self.corr_threshold:
                count += 1
        return count

    def would_exceed_limit(self, new_asset: str, open_assets: list[str]) -> bool:
        """Return True if entering *new_asset* would result in too many
        correlated open positions.

        A result of True means the entry should be blocked.
        Only triggers when there are enough open positions AND enough
        return history to compute a meaningful correlation.
        """
        if not open_assets:
            return False
        count = self.get_correlated_count(new_asset, open_assets)
        return count >= self.max_correlated

    # ── Introspection ────────────────────────────────────────────────────

    def correlation_matrix(self) -> dict[str, dict[str, float]]:
        """Return full pairwise correlation matrix for all tracked assets.

        Values are rounded to 3 d.p.  Missing pairs are omitted.
        """
        assets = list(self._returns.keys())
        matrix: dict[str, dict[str, float]] = {}
        for i, a in enumerate(assets):
            for b in assets[i + 1 :]:
                corr = self.pairwise_correlation(a, b)
                if corr is not None:
                    matrix.setdefault(a, {})[b] = round(corr, 3)
                    matrix.setdefault(b, {})[a] = round(corr, 3)
        return matrix

    def obs_count(self) -> dict[str, int]:
        """Return {asset: n_observations} for all tracked assets."""
        return {a: len(q) for a, q in self._returns.items()}

    def status(self) -> dict[str, Any]:
        """Summary dict for logging / heartbeat."""
        obs = self.obs_count()
        matrix = self.correlation_matrix()
        # Find highest correlation pair
        top_pair: tuple[str, str, float] | None = None
        for a, row in matrix.items():
            for b, corr in row.items():
                if a < b:  # deduplicate
                    if top_pair is None or abs(corr) > abs(top_pair[2]):
                        top_pair = (a, b, corr)
        return {
            "enabled": True,
            "window": self.window,
            "max_correlated": self.max_correlated,
            "corr_threshold": self.corr_threshold,
            "assets_tracked": len(self._returns),
            "obs_counts": obs,
            "top_pair": {
                "a": top_pair[0],
                "b": top_pair[1],
                "corr": round(top_pair[2], 3),
            }
            if top_pair
            else None,
        }

    def log_matrix(self) -> None:
        """Log the full correlation matrix at INFO level."""
        matrix = self.correlation_matrix()
        if not matrix:
            logger.info("[CorrelationGuard] No correlation data yet (insufficient history)")
            return
        assets = sorted(set(list(matrix.keys()) + [b for row in matrix.values() for b in row]))
        logger.info("[CorrelationGuard] Pairwise correlation matrix:")
        for a in assets:
            row_parts = []
            for b in assets:
                if a == b:
                    row_parts.append(f"{b:>6}: 1.000")
                else:
                    corr = matrix.get(a, {}).get(b)
                    if corr is not None:
                        flag = " *" if abs(corr) >= self.corr_threshold else "  "
                        row_parts.append(f"{b:>6}: {corr:+.3f}{flag}")
            if row_parts:
                logger.info("  %s → %s", a.upper(), "  ".join(row_parts))
