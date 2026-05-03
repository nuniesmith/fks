"""Gap scanner — detects missing bar ranges and publishes fill jobs.

Runs on a configurable schedule, detects missing bar ranges by comparing
the ``bars`` table against an ideal ``generate_series``, writes a gap
manifest to Redis, and publishes fill jobs for the backfill manager.

Redis keys
----------
- ``ruby:gaps:{symbol}:{interval}`` — JSON-serialised list of
  :class:`GapWindow` dicts describing detected gaps (2 h TTL).
- ``ruby:gaps:last_scan`` — ISO-8601 timestamp of the most recent
  completed scan cycle.

Fill jobs are pushed onto ``ruby:factory:fill_queue`` so that the
:class:`~.backfill_manager.BackfillManager` can pick them up.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from core.logging_config import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncEngine

    from .registry.asset_registry import AssetRegistry

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FILL_QUEUE_KEY: str = "ruby:factory:fill_queue"
"""Redis list where backfill job payloads are pushed."""

GAP_KEY_PREFIX: str = "ruby:gaps"
"""Redis key prefix for per-symbol, per-interval gap manifests."""

_GAP_TTL: int = 7200
"""Time-to-live in seconds for gap manifest keys (2 hours)."""

_INTERVAL_TO_PG: dict[str, str] = {
    "1m": "1 minute",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "1h": "1 hour",
    "4h": "4 hours",
    "1d": "1 day",
}
"""Mapping from :class:`~.registry.schemas.DataInterval` values to
Postgres ``INTERVAL`` literals used inside ``generate_series``."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class GapWindow:
    """A contiguous range of missing bars for a single symbol × interval."""

    symbol: str
    interval: str
    start: str  # ISO-8601
    end: str  # ISO-8601
    missing_bars: int


# ---------------------------------------------------------------------------
# GapScanner
# ---------------------------------------------------------------------------


class GapScanner:
    """Scheduled worker that scans for missing bar ranges and enqueues fills.

    Parameters
    ----------
    redis:
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    db_engine:
        An async SQLAlchemy engine connected to the Postgres database that
        holds the ``bars`` table.
    intervals:
        Bar intervals to scan.  Defaults to ``["1m", "5m", "1d"]``.
    days_back:
        How many calendar days back from *now* each scan should look.
    scan_interval_secs:
        Seconds to sleep between scan cycles.
    """

    def __init__(
        self,
        redis: aioredis.Redis,  # type: ignore[name-defined]
        db_engine: AsyncEngine,
        intervals: list[str] | None = None,
        days_back: int = 14,
        scan_interval_secs: int = 3600,
    ) -> None:
        self._redis = redis
        self._engine = db_engine
        self._intervals = intervals or ["1m", "5m", "1d"]
        self._days_back = days_back
        self._scan_interval_secs = scan_interval_secs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, registry: AssetRegistry) -> None:
        """Main loop — scan for gaps, publish manifests, enqueue fills.

        Runs indefinitely, sleeping *scan_interval_secs* between cycles.
        """
        log.info(
            "gap_scanner.starting",
            intervals=self._intervals,
            days_back=self._days_back,
            scan_interval_secs=self._scan_interval_secs,
        )

        while True:
            try:
                assets = await registry.enabled_assets()
                symbols = [a.symbol for a in assets]

                if not symbols:
                    log.debug("gap_scanner.no_enabled_assets")
                    await asyncio.sleep(self._scan_interval_secs)
                    continue

                gaps = await self._scan_all(symbols)
                await self._publish_gaps(gaps)
                await self._enqueue_fills(gaps)

                log.info(
                    "gap_scanner.cycle_complete",
                    symbols=len(symbols),
                    gaps_found=len(gaps),
                    total_missing=sum(g.missing_bars for g in gaps),
                )
            except Exception:
                log.exception("gap_scanner.cycle_failed")

            await asyncio.sleep(self._scan_interval_secs)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    async def _scan_all(self, symbols: list[str]) -> list[GapWindow]:
        """Scan every *symbol* × *interval* pair and return all detected gaps."""
        since = datetime.now(UTC) - timedelta(days=self._days_back)
        gaps: list[GapWindow] = []

        for symbol in symbols:
            for interval in self._intervals:
                try:
                    found = await self._scan_symbol_interval(symbol, interval, since)
                    gaps.extend(found)
                except Exception:
                    log.warning(
                        "gap_scanner.scan_failed",
                        symbol=symbol,
                        interval=interval,
                        exc_info=True,
                    )

        return gaps

    async def _scan_symbol_interval(
        self,
        symbol: str,
        interval: str,
        since: datetime,
    ) -> list[GapWindow]:
        """Detect missing bars for a single *symbol* × *interval* pair.

        Uses ``generate_series`` to build the ideal set of timestamps and
        ``LEFT JOIN`` against the ``historical_bars`` table to find holes.  Adjacent
        missing timestamps are grouped into hourly windows so that the
        resulting :class:`GapWindow` list is compact.
        """
        from sqlalchemy import text

        pg_interval = _INTERVAL_TO_PG.get(interval)
        if pg_interval is None:
            log.warning("gap_scanner.unsupported_interval", interval=interval)
            return []

        now = datetime.now(UTC)

        query = text(
            """
            WITH expected AS (
                SELECT gs AS expected_time
                  FROM generate_series(
                           :since ::timestamptz,
                           :until ::timestamptz,
                           :step  ::interval
                       ) AS gs
            ),
            missing AS (
                SELECT e.expected_time
                  FROM expected e
                  LEFT JOIN historical_bars b
                    ON b.symbol   = :symbol
                   AND b.interval = :interval
                   AND b.timestamp = e.expected_time
                 WHERE b.timestamp IS NULL
            )
            SELECT
                date_trunc('hour', expected_time) AS window_start,
                MIN(expected_time)                AS first_missing,
                MAX(expected_time)                AS last_missing,
                COUNT(*)                          AS cnt
              FROM missing
             GROUP BY date_trunc('hour', expected_time)
             ORDER BY window_start;
            """
        )

        gaps: list[GapWindow] = []

        async with self._engine.connect() as conn:
            result = await conn.execute(
                query,
                {
                    "since": since.isoformat(),
                    "until": now.isoformat(),
                    "step": pg_interval,
                    "symbol": symbol,
                    "interval": interval,
                },
            )
            rows = result.fetchall()

        for row in rows:
            _window_start, first_missing, last_missing, cnt = row
            gaps.append(
                GapWindow(
                    symbol=symbol,
                    interval=interval,
                    start=first_missing.isoformat() if hasattr(first_missing, "isoformat") else str(first_missing),
                    end=last_missing.isoformat() if hasattr(last_missing, "isoformat") else str(last_missing),
                    missing_bars=int(cnt),
                )
            )

        return gaps

    # ------------------------------------------------------------------
    # Redis publishing
    # ------------------------------------------------------------------

    async def _publish_gaps(self, gaps: list[GapWindow]) -> None:
        """Write per-symbol/interval gap manifests to Redis.

        Each key ``ruby:gaps:{symbol}:{interval}`` stores the JSON list of
        gap windows for that pair.  The ``ruby:gaps:last_scan`` key is
        updated with the current UTC timestamp.
        """
        # Group gaps by (symbol, interval)
        grouped: dict[tuple[str, str], list[dict]] = {}
        for gap in gaps:
            key = (gap.symbol, gap.interval)
            grouped.setdefault(key, []).append(asdict(gap))

        pipe = self._redis.pipeline()

        for (symbol, interval), windows in grouped.items():
            redis_key = f"{GAP_KEY_PREFIX}:{symbol}:{interval}"
            pipe.setex(redis_key, _GAP_TTL, json.dumps(windows))

        # Record scan timestamp
        pipe.set(
            f"{GAP_KEY_PREFIX}:last_scan",
            datetime.now(UTC).isoformat(),
        )

        await pipe.execute()

    async def _enqueue_fills(self, gaps: list[GapWindow]) -> None:
        """Push fill jobs onto :data:`FILL_QUEUE_KEY` for the backfill manager.

        Each gap window becomes a single fill job containing the symbol,
        interval, and the start/end range.
        """
        if not gaps:
            return

        pipe = self._redis.pipeline()
        for gap in gaps:
            job = json.dumps(
                {
                    "symbol": gap.symbol,
                    "interval": gap.interval,
                    "start": gap.start,
                    "end": gap.end,
                    "reason": f"gap_scanner:missing_{gap.missing_bars}_bars",
                }
            )
            pipe.lpush(FILL_QUEUE_KEY, job)
        await pipe.execute()

        log.info("gap_scanner.enqueued_fills", count=len(gaps))
