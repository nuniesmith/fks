"""
ml/kline_cache.py — Two-level synchronous Redis cache for OHLCV training data.

Why two levels?
---------------
Page cache (200-bar chunks)
    KuCoin hard-caps every fetch_ohlcv call at 200 bars.  Collecting 15 000
    bars requires 75 round-trips per asset.  The page cache stores each
    individual 200-bar response so that a crashed or re-run training session
    can skip every page it already fetched without touching the exchange API.

    Key  : train:klines:page:{symbol}:{timeframe}:{since_ms}
    TTL  : 6 hours  (old pages are immutable; only the trailing edge changes)

Full-dataset cache
    After all pages are assembled and deduplicated, the complete DataFrame
    rows are stored in a single key.  Subsequent runs that request the same
    symbol / timeframe / bar-count on the same UTC day return immediately
    from this key, skipping all 75 API calls.

    Key  : train:klines:full:{symbol}:{timeframe}:{limit}:{date_utc}
    TTL  : 12 hours  (refreshes at the next UTC-day boundary)

Both levels degrade silently to no-op when Redis is unavailable.

Usage
-----
    from ml.kline_cache import KlineCache

    cache = KlineCache.connect("redis://localhost:6379/0")
    # or: cache = KlineCache()   # disabled — all ops are no-ops

    # Inside fetch_klines —
    rows = cache.get_page(symbol, timeframe, since_ms)
    if rows is None:
        rows = exchange.fetch_ohlcv(...)
        cache.set_page(symbol, timeframe, since_ms, rows)

    # After assembling the full dataset —
    cache.set_dataset(symbol, timeframe, limit, all_rows)

    print(cache.stats_line())   # "cache  hits=72  misses=3  ratio=96.0%  stored=3 keys"
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Key prefixes (separate from the live bot's "futures:" namespace) ──────────
_PAGE_NS = "train:klines:page"
_FULL_NS = "train:klines:full"

# ── TTLs ──────────────────────────────────────────────────────────────────────
PAGE_TTL_SEC: int = 6 * 3600  # 6 h  — individual 200-bar pages
FULL_TTL_SEC: int = 12 * 3600  # 12 h — assembled full dataset


class KlineCache:
    """Two-level synchronous Redis cache for OHLCV kline data.

    All public methods are safe to call even when Redis is unavailable:
    they simply return None (reads) or do nothing (writes).

    Parameters
    ----------
    client : redis.Redis | None
        A connected synchronous Redis client.  Pass None to run with
        caching disabled (useful for ``--no-cache`` flag).
    """

    def __init__(self, client: Any | None = None) -> None:
        self._r = client
        # Counters — reset per fetch_klines call via reset_stats()
        self._page_hits: int = 0
        self._page_misses: int = 0
        self._full_hits: int = 0
        self._full_misses: int = 0
        self._keys_written: int = 0
        self._bytes_written: int = 0

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def connect(
        cls,
        redis_url: str = "redis://localhost:6379/0",
        password: str | None = None,
    ) -> KlineCache:
        """Try to connect to Redis and return a live KlineCache.

        Returns a disabled (no-op) KlineCache if the connection fails so
        training can continue without caching.
        """
        try:
            import redis as redis_lib  # synchronous client

            kwargs: dict[str, Any] = {"decode_responses": True}
            if password:
                kwargs["password"] = password

            client = redis_lib.from_url(redis_url, **kwargs)
            client.ping()  # raises if Redis is not reachable

            logger.info("[cache] Connected to Redis at %s", redis_url)
            return cls(client=client)

        except ImportError:
            logger.warning("[cache] redis package not installed — caching disabled")
            return cls(client=None)

        except Exception as exc:
            logger.warning(
                "[cache] Redis unavailable (%s) — training will fetch all data from exchange",
                exc,
            )
            return cls(client=None)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        """True when a live Redis connection is available."""
        return self._r is not None

    # ── Key builders ──────────────────────────────────────────────────────────

    @staticmethod
    def _page_key(symbol: str, timeframe: str, since_ms: int) -> str:
        return f"{_PAGE_NS}:{symbol}:{timeframe}:{since_ms}"

    @staticmethod
    def _full_key(symbol: str, timeframe: str, limit: int) -> str:
        date_utc = time.strftime("%Y-%m-%d", time.gmtime())
        return f"{_FULL_NS}:{symbol}:{timeframe}:{limit}:{date_utc}"

    # ── Full-dataset cache ────────────────────────────────────────────────────

    def get_dataset(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[list] | None:
        """Return the full assembled OHLCV row list if cached, else None.

        A cache hit means fetch_klines can skip all paginated API calls
        and return immediately.
        """
        if not self.enabled:
            return None
        try:
            key = self._full_key(symbol, timeframe, limit)
            raw = self._r.get(key)
            if raw:
                self._full_hits += 1
                data: list[list] = json.loads(raw)
                logger.info(
                    "[cache] ✓ Full dataset hit  %s %s  %d bars  (key=%s)",
                    symbol,
                    timeframe,
                    len(data),
                    key,
                )
                return data
            self._full_misses += 1
            return None
        except Exception as exc:
            logger.debug("[cache] get_dataset error: %s", exc)
            self._full_misses += 1
            return None

    def set_dataset(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        rows: list[list],
    ) -> None:
        """Cache the full assembled OHLCV row list with a 12-hour TTL."""
        if not self.enabled or not rows:
            return
        try:
            key = self._full_key(symbol, timeframe, limit)
            payload = json.dumps(rows)
            self._r.setex(key, FULL_TTL_SEC, payload)
            self._keys_written += 1
            self._bytes_written += len(payload)
            logger.debug(
                "[cache] Stored full dataset  %s %s  %d bars  %.1f KB  TTL=%dh",
                symbol,
                timeframe,
                len(rows),
                len(payload) / 1024,
                FULL_TTL_SEC // 3600,
            )
        except Exception as exc:
            logger.debug("[cache] set_dataset error: %s", exc)

    # ── Page cache ────────────────────────────────────────────────────────────

    def get_page(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int,
    ) -> list[list] | None:
        """Return cached 200-bar page if available, else None."""
        if not self.enabled:
            return None
        try:
            raw = self._r.get(self._page_key(symbol, timeframe, since_ms))
            if raw:
                self._page_hits += 1
                return json.loads(raw)
            self._page_misses += 1
            return None
        except Exception as exc:
            logger.debug("[cache] get_page error: %s", exc)
            self._page_misses += 1
            return None

    def set_page(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int,
        rows: list[list],
    ) -> None:
        """Cache a 200-bar page with a 6-hour TTL."""
        if not self.enabled or not rows:
            return
        try:
            key = self._page_key(symbol, timeframe, since_ms)
            payload = json.dumps(rows)
            self._r.setex(key, PAGE_TTL_SEC, payload)
            self._keys_written += 1
            self._bytes_written += len(payload)
        except Exception as exc:
            logger.debug("[cache] set_page error: %s", exc)

    # ── Bulk operations ───────────────────────────────────────────────────────

    def flush_training_keys(self) -> int:
        """Delete all training cache keys.  Returns the number removed.

        Useful for a ``--no-cache`` / cache-busting flag without restarting Redis.
        """
        if not self.enabled:
            return 0
        removed = 0
        try:
            for pattern in (f"{_PAGE_NS}:*", f"{_FULL_NS}:*"):
                keys = self._r.keys(pattern)
                if keys:
                    removed += self._r.delete(*keys)
        except Exception as exc:
            logger.debug("[cache] flush error: %s", exc)
        return removed

    def ttl(self, symbol: str, timeframe: str, limit: int) -> int:
        """Remaining TTL in seconds for a full-dataset key (-2 = not found)."""
        if not self.enabled:
            return -2
        try:
            return int(self._r.ttl(self._full_key(symbol, timeframe, limit)))
        except Exception:
            return -2

    # ── Statistics ────────────────────────────────────────────────────────────

    def reset_stats(self) -> None:
        """Reset counters — call before each symbol's fetch to get per-asset stats."""
        self._page_hits = 0
        self._page_misses = 0
        self._full_hits = 0
        self._full_misses = 0
        self._keys_written = 0
        self._bytes_written = 0

    def stats(self) -> dict[str, Any]:
        """Return a snapshot of cache counters."""
        total = self._page_hits + self._page_misses
        ratio = self._page_hits / total if total else 0.0
        return {
            "enabled": self.enabled,
            "full_hits": self._full_hits,
            "full_misses": self._full_misses,
            "page_hits": self._page_hits,
            "page_misses": self._page_misses,
            "page_total": total,
            "page_hit_ratio": round(ratio, 3),
            "keys_written": self._keys_written,
            "bytes_written": self._bytes_written,
        }

    def stats_line(self) -> str:
        """Single-line summary suitable for a log message.

        Example output:
            cache  page hits=72/75 (96.0%)  full hits=1  stored=1 keys  12.4 KB written
            cache  DISABLED
        """
        if not self.enabled:
            return "cache  DISABLED"

        s = self.stats()
        total = s["page_total"]
        ratio_pct = s["page_hit_ratio"] * 100

        parts: list[str] = []

        if s["full_hits"]:
            parts.append("full-hit (skipped all API calls)")
        else:
            parts.append(f"page hits={s['page_hits']}/{total} ({ratio_pct:.0f}%)")

        if s["keys_written"]:
            kb = s["bytes_written"] / 1024
            parts.append(f"stored={s['keys_written']} keys  {kb:.1f} KB")

        return "cache  " + "  |  ".join(parts)
