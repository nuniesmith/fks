"""Rolling data-coverage manager.

This module proactively ensures rolling data coverage for all enabled
assets.  It runs on a configurable schedule and, for each enabled asset
crossed with each :class:`~..registry.schemas.WindowTarget`:

1. Queries Postgres for the actual coverage (oldest bar, newest bar, count).
2. Compares against the target window defined in the asset configuration.
3. Emits backfill jobs for any uncovered date ranges.
4. Publishes per-symbol, per-interval coverage metrics to Redis.

Coverage is tracked in Redis under keys of the form
``ruby:coverage:{symbol}:{interval}``.  Each key stores a JSON-serialised
:class:`CoverageReport` with a status of **ok**, **partial**, **critical**,
or **empty**.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from core.logging_config import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncEngine

    from ..registry.asset_registry import AssetRegistry

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COVERAGE_KEY_PREFIX: str = "ruby:coverage"
"""Redis key prefix for per-symbol, per-interval coverage reports."""

FILL_QUEUE_KEY: str = "ruby:factory:fill_queue"
"""Redis list where backfill job payloads are pushed."""

COVERAGE_TTL: int = 7200
"""Time-to-live in seconds for cached coverage reports (2 hours)."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CoverageStatus(StrEnum):
    """Health status of data coverage for a single symbol × interval."""

    OK = "ok"
    """≥ 95 % of the target window is covered."""

    PARTIAL = "partial"
    """≥ min_days but < 95 % of the target window."""

    CRITICAL = "critical"
    """Below min_days of coverage."""

    EMPTY = "empty"
    """No data at all for this symbol × interval."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CoverageReport:
    """Snapshot of coverage health for a single symbol × interval pair."""

    symbol: str
    interval: str
    oldest_bar: str | None
    newest_bar: str | None
    actual_days: int
    target_days: int
    min_days: int
    pct: float
    status: str
    gap_start: str | None
    gap_end: str | None


# ---------------------------------------------------------------------------
# WindowManager
# ---------------------------------------------------------------------------


class WindowManager:
    """Periodically audits rolling-window coverage and enqueues backfills.

    Parameters
    ----------
    redis:
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    engine:
        An async SQLAlchemy engine connected to the Postgres database that
        holds the ``historical_bars`` table.
    check_interval_secs:
        How often (in seconds) to re-check coverage.  Defaults to one hour.
    """

    def __init__(
        self,
        redis: aioredis.Redis,  # type: ignore[name-defined]
        engine: AsyncEngine,
        check_interval_secs: int = 3600,
    ) -> None:
        self._redis = redis
        self._engine = engine
        self._check_interval_secs = check_interval_secs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, registry: AssetRegistry) -> None:
        """Main loop — run forever, auditing coverage on each tick.

        An initial 60-second sleep gives the backfill manager time to
        start before this manager begins emitting fill jobs.
        """
        log.info("window_manager.starting", check_interval=self._check_interval_secs)
        await asyncio.sleep(60)

        while True:
            try:
                assets = await registry.enabled_assets()
                reports = await self._check_all(assets)
                await self._publish_coverage(reports)
                await self._enqueue_fills(reports)

                critical = sum(1 for r in reports if r.status == CoverageStatus.CRITICAL.value)
                empty = sum(1 for r in reports if r.status == CoverageStatus.EMPTY.value)
                log.info(
                    "window_manager.cycle_complete",
                    assets=len(assets),
                    reports=len(reports),
                    critical=critical,
                    empty=empty,
                )
            except Exception:
                log.exception("window_manager.cycle_failed")

            await asyncio.sleep(self._check_interval_secs)

    async def coverage_for(self, symbol: str, interval: str) -> CoverageReport | None:
        """Return the cached :class:`CoverageReport` for *symbol* × *interval*.

        Returns ``None`` when the key does not exist or cannot be decoded.
        """
        key = f"{COVERAGE_KEY_PREFIX}:{symbol}:{interval}"
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            data: dict[str, Any] = json.loads(raw)
            return CoverageReport(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            log.warning("window_manager.coverage_decode_failed", key=key)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_all(self, assets: list[Any]) -> list[CoverageReport]:
        """Check every enabled asset × window-target pair concurrently."""
        tasks: list[asyncio.Task[CoverageReport]] = []
        for asset in assets:
            for wt in asset.window_targets:
                tasks.append(
                    asyncio.ensure_future(
                        self._check_symbol_interval(
                            symbol=asset.symbol,
                            interval=wt.interval.value,
                            target_days=wt.days,
                            min_days=wt.min_days,
                        )
                    )
                )

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        reports: list[CoverageReport] = []
        for result in results:
            if isinstance(result, CoverageReport):
                reports.append(result)
            elif isinstance(result, BaseException):
                log.warning("window_manager.check_failed", error=str(result))

        return reports

    async def _check_symbol_interval(
        self,
        symbol: str,
        interval: str,
        target_days: int,
        min_days: int,
    ) -> CoverageReport:
        """Query Postgres for actual coverage and build a report."""
        from sqlalchemy import text

        now = datetime.now(UTC)
        target_start = now - timedelta(days=target_days)

        async with self._engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT MIN(timestamp), MAX(timestamp), COUNT(*) "
                    "FROM historical_bars "
                    "WHERE symbol = :symbol AND interval = :interval"
                ),
                {"symbol": symbol, "interval": interval},
            )
            row = result.fetchone()

        if row is None or row[2] == 0:
            return CoverageReport(
                symbol=symbol,
                interval=interval,
                oldest_bar=None,
                newest_bar=None,
                actual_days=0,
                target_days=target_days,
                min_days=min_days,
                pct=0.0,
                status=CoverageStatus.EMPTY.value,
                gap_start=target_start.isoformat(),
                gap_end=now.isoformat(),
            )

        oldest: datetime = row[0]
        newest: datetime = row[1]

        # Postgres may return timezone-naive datetimes; normalise to UTC.
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=UTC)
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=UTC)

        actual_days = (newest - oldest).days
        pct = (actual_days / target_days * 100) if target_days > 0 else 0.0

        # Determine status
        if pct >= 95.0:
            status = CoverageStatus.OK.value
        elif actual_days >= min_days:
            status = CoverageStatus.PARTIAL.value
        else:
            status = CoverageStatus.CRITICAL.value

        # Detect leading gap (data starts after the target window start)
        gap_start: str | None = None
        gap_end: str | None = None
        if oldest > target_start:
            gap_start = target_start.isoformat()
            gap_end = oldest.isoformat()

        return CoverageReport(
            symbol=symbol,
            interval=interval,
            oldest_bar=oldest.isoformat(),
            newest_bar=newest.isoformat(),
            actual_days=actual_days,
            target_days=target_days,
            min_days=min_days,
            pct=round(pct, 2),
            status=status,
            gap_start=gap_start,
            gap_end=gap_end,
        )

    async def _publish_coverage(self, reports: list[CoverageReport]) -> None:
        """Cache every report in Redis with :data:`COVERAGE_TTL`."""
        if not reports:
            return

        pipe = self._redis.pipeline()
        for report in reports:
            key = f"{COVERAGE_KEY_PREFIX}:{report.symbol}:{report.interval}"
            pipe.setex(key, COVERAGE_TTL, json.dumps(asdict(report)))
        await pipe.execute()

    async def _enqueue_fills(self, reports: list[CoverageReport]) -> None:
        """Push backfill jobs for any reports that have coverage gaps."""
        actionable = [
            r
            for r in reports
            if r.gap_start is not None
            and r.status
            in (
                CoverageStatus.EMPTY.value,
                CoverageStatus.CRITICAL.value,
                CoverageStatus.PARTIAL.value,
            )
        ]

        if not actionable:
            return

        pipe = self._redis.pipeline()
        for report in actionable:
            job = json.dumps(
                {
                    "symbol": report.symbol,
                    "interval": report.interval,
                    "start": report.gap_start,
                    "end": report.gap_end,
                    "reason": f"window_manager:{report.status}",
                }
            )
            pipe.lpush(FILL_QUEUE_KEY, job)
        await pipe.execute()

        log.info("window_manager.enqueued_fills", count=len(actionable))
