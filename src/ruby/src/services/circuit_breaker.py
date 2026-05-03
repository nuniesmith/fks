"""
Circuit breaker for consecutive trading losses.

After N consecutive losses on an asset, the breaker trips and blocks new
entries for a cooldown period. This prevents compounding losses when the
market regime has shifted against our signals.

Redis keys used:
    futures:consec_losses:{asset}     — current consecutive loss count
    futures:breaker_cooldown:{asset}  — TTL key, present = breaker is cooling down
"""

from __future__ import annotations

import time
from typing import Any

from utils.logging_config import get_logger

logger = get_logger("circuit_breaker")


class ConsecutiveLossBreaker:
    """Per-asset consecutive loss circuit breaker with Redis persistence.

    Parameters
    ----------
    store : RedisStore
        Redis store for persistent state.
    loss_limit : int
        Number of consecutive losses before the breaker trips (default 3).
    cooldown_sec : int
        Seconds to stay in cooldown after breaker trips (default 900 = 15 min).
    """

    def __init__(
        self,
        store: Any,
        loss_limit: int = 3,
        cooldown_sec: int = 900,
    ) -> None:
        self._store = store
        self._loss_limit = loss_limit
        self._cooldown_sec = cooldown_sec
        # In-memory cache to avoid Redis calls on every loop tick
        self._cache: dict[str, dict] = {}

    def _loss_key(self, asset: str) -> str:
        return f"consec_losses:{asset}"

    def _cooldown_key(self, asset: str) -> str:
        return f"breaker_cooldown:{asset}"

    async def record_outcome(self, asset: str, is_win: bool) -> None:
        """Record a trade outcome. Resets on win, increments on loss.

        If the loss count reaches the limit, starts the cooldown timer.
        """
        if is_win:
            # Win resets the counter
            await self._store._set(self._store._key(self._loss_key(asset)), "0")
            self._cache.pop(asset, None)
            logger.debug("[%s] Circuit breaker: win recorded, counter reset", asset.upper())
        else:
            # Loss increments
            full_key = self._store._key(self._loss_key(asset))
            if self._store._connected:
                new_count = await self._store._redis.incr(full_key)
            else:
                val = await self._store._get(full_key)
                new_count = int(val or 0) + 1
                await self._store._set(full_key, str(new_count))

            logger.info(
                "[%s] Circuit breaker: loss recorded, consecutive=%d/%d",
                asset.upper(),
                new_count,
                self._loss_limit,
            )

            # Trip the breaker if limit reached
            if int(new_count) >= self._loss_limit:
                cooldown_key = self._store._key(self._cooldown_key(asset))
                await self._store._set(cooldown_key, str(time.time()), ex=self._cooldown_sec)
                logger.warning(
                    "[%s] Circuit breaker TRIPPED — %d consecutive losses, cooling down for %ds",
                    asset.upper(),
                    new_count,
                    self._cooldown_sec,
                )
                self._cache[asset] = {
                    "tripped_at": time.time(),
                    "count": int(new_count),
                }

    async def is_breaker_open(self, asset: str) -> bool:
        """Check if the circuit breaker is currently open (blocking trades).

        The breaker is open when there's an active cooldown key in Redis.
        Once the TTL expires, Redis auto-deletes it and the breaker closes.
        """
        cooldown_key = self._store._key(self._cooldown_key(asset))
        val = await self._store._get(cooldown_key)
        return val is not None

    async def cooldown_remaining(self, asset: str) -> int:
        """Seconds until the breaker auto-resets. Returns 0 if not tripped."""
        cooldown_key = self._store._key(self._cooldown_key(asset))
        if self._store._connected:
            ttl = await self._store._redis.ttl(cooldown_key)
            return max(0, ttl) if ttl and ttl > 0 else 0
        else:
            val = self._store._mem_strings.get(cooldown_key)
            if val is None:
                return 0
            _, expire_ts = val
            if expire_ts is None:
                return 0
            remaining = expire_ts - time.time()
            return max(0, int(remaining))

    async def get_loss_count(self, asset: str) -> int:
        """Get current consecutive loss count for an asset."""
        val = await self._store._get(self._store._key(self._loss_key(asset)))
        return int(val) if val else 0

    async def status(self, asset: str) -> dict:
        """Get full breaker status for dashboard/heartbeat."""
        is_open = await self.is_breaker_open(asset)
        count = await self.get_loss_count(asset)
        remaining = await self.cooldown_remaining(asset) if is_open else 0
        return {
            "open": is_open,
            "consecutive_losses": count,
            "loss_limit": self._loss_limit,
            "cooldown_remaining_sec": remaining,
            "cooldown_total_sec": self._cooldown_sec,
        }
