"""Backfill manager — consumes fill jobs and pulls data in resumable chunks.

Consumes fill jobs from ``ruby:factory:fill_queue``, pulls historical bar
data via the :class:`~.providers.router.ProviderRouter` in configurable
chunks, and writes the results to Postgres.  Per-chunk state is persisted
in Redis so that a crash mid-backfill can be resumed without re-fetching
already-completed chunks.

Redis keys
----------
- ``ruby:factory:fill_queue`` — BRPOP source for incoming fill jobs
  (shared with :mod:`.gap_scanner` and :mod:`.windows.window_manager`).
- ``ruby:factory:backfill:state:{symbol}:{interval}`` — JSON-serialised
  :class:`BackfillState` with per-chunk progress (30-day TTL).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from core.logging_config import get_logger

from .registry.schemas import DataInterval

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncEngine

    from .providers.base import OHLCVBar
    from .providers.router import ProviderRouter
    from .registry.asset_registry import AssetRegistry
    from .registry.schemas import AssetConfig

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FILL_QUEUE_KEY: str = "ruby:factory:fill_queue"
"""Redis list where backfill job payloads are consumed from."""

STATE_KEY_PREFIX: str = "ruby:factory:backfill:state"
"""Redis key prefix for per-symbol, per-interval backfill state."""

MAX_ATTEMPTS: int = 3
"""Maximum number of fetch attempts per chunk before marking it FAILED."""

CHUNK_DAYS: int = 30
"""Number of calendar days per backfill chunk."""

_STATE_TTL: int = 60 * 60 * 24 * 30
"""Time-to-live in seconds for persisted backfill state (30 days)."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ChunkStatus(StrEnum):
    """Processing status of a single backfill chunk."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A single time-range chunk within a backfill job."""

    start: str  # ISO-8601
    end: str  # ISO-8601
    status: str = ChunkStatus.PENDING.value
    attempts: int = 0
    last_error: str | None = None


@dataclass
class BackfillState:
    """Full state for one symbol × interval backfill job."""

    symbol: str
    interval: str
    chunks: list[Chunk] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _state_to_dict(state: BackfillState) -> dict:
    """Serialise a :class:`BackfillState` to a JSON-safe dict."""
    return {
        "symbol": state.symbol,
        "interval": state.interval,
        "chunks": [asdict(c) for c in state.chunks],
    }


def _dict_to_state(data: dict) -> BackfillState:
    """Deserialise a plain dict back into a :class:`BackfillState`."""
    chunks = [
        Chunk(
            start=c["start"],
            end=c["end"],
            status=c.get("status", ChunkStatus.PENDING.value),
            attempts=c.get("attempts", 0),
            last_error=c.get("last_error"),
        )
        for c in data.get("chunks", [])
    ]
    return BackfillState(
        symbol=data["symbol"],
        interval=data["interval"],
        chunks=chunks,
    )


# ---------------------------------------------------------------------------
# BackfillManager
# ---------------------------------------------------------------------------


class BackfillManager:
    """Chunked backfill worker with crash-resumable state in Redis.

    Parameters
    ----------
    redis:
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    provider_router:
        A :class:`~.providers.router.ProviderRouter` used to fetch bars
        from the best available upstream provider.
    db_engine:
        An async SQLAlchemy engine connected to the Postgres database that
        holds the ``bars`` table.
    registry:
        The :class:`~.registry.asset_registry.AssetRegistry` used to
        look up :class:`~.registry.schemas.AssetConfig` for each symbol.
    days_back:
        Default look-back depth (in calendar days) when a fill job does
        not specify an explicit start date.
    concurrency:
        Maximum number of backfill jobs processed in parallel.
    """

    def __init__(
        self,
        redis: aioredis.Redis,  # type: ignore[name-defined]
        provider_router: ProviderRouter,
        db_engine: AsyncEngine,
        registry: AssetRegistry,
        days_back: int = 365,
        concurrency: int = 2,
    ) -> None:
        self._redis = redis
        self._router = provider_router
        self._engine = db_engine
        self._registry = registry
        self._days_back = days_back
        self._semaphore = asyncio.Semaphore(concurrency)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main loop — consume fill jobs from Redis and process them.

        Uses ``BRPOP`` with a 5-second timeout so the loop remains
        responsive to cancellation.
        """
        log.info(
            "backfill_manager.starting",
            days_back=self._days_back,
            concurrency=self._semaphore._value,
        )

        await self._ensure_table()

        while True:
            try:
                result = await self._redis.brpop(FILL_QUEUE_KEY, timeout=5)
                if result is None:
                    continue

                _key, raw = result
                payload = json.loads(raw if isinstance(raw, str) else raw.decode())

                symbol = payload["symbol"]
                interval = payload["interval"]
                start = payload.get("start")
                end = payload.get("end")

                log.info(
                    "backfill_manager.job_received",
                    symbol=symbol,
                    interval=interval,
                    start=start,
                    end=end,
                    reason=payload.get("reason", "unknown"),
                )

                asyncio.create_task(self._process_job(symbol, interval, start=start, end=end))
            except json.JSONDecodeError:
                log.warning("backfill_manager.invalid_job_payload", exc_info=True)
            except Exception:
                log.exception("backfill_manager.run_error")
                await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    async def _ensure_table(self) -> None:
        """Create the ``historical_bars`` table if it does not already exist.

        Delegates to :func:`~lib.services.engine.backfill.init_backfill_table`
        (a synchronous function) via :func:`asyncio.to_thread` so that the
        event loop is not blocked during the DDL operation.
        """
        from services.engine.backfill import init_backfill_table

        await asyncio.to_thread(init_backfill_table)
        log.debug("backfill_manager.table_ensured")

    # ------------------------------------------------------------------
    # Job processing
    # ------------------------------------------------------------------

    async def _process_job(
        self,
        symbol: str,
        interval: str,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        """Process a single backfill job under the concurrency semaphore."""
        async with self._semaphore:
            config = await self._registry.get(symbol)
            if config is None:
                log.warning(
                    "backfill_manager.symbol_not_found",
                    symbol=symbol,
                )
                return

            state = await self._load_or_init_state(symbol, interval, start, end)

            actionable = [
                c
                for c in state.chunks
                if c.status in (ChunkStatus.PENDING.value, ChunkStatus.FAILED.value) and c.attempts < MAX_ATTEMPTS
            ]

            if not actionable:
                log.info(
                    "backfill_manager.nothing_to_do",
                    symbol=symbol,
                    interval=interval,
                    total_chunks=len(state.chunks),
                )
                return

            log.info(
                "backfill_manager.processing",
                symbol=symbol,
                interval=interval,
                actionable_chunks=len(actionable),
                total_chunks=len(state.chunks),
            )

            for chunk in actionable:
                await self._fetch_chunk(state, chunk, config)

            done = sum(1 for c in state.chunks if c.status == ChunkStatus.DONE.value)
            failed = sum(1 for c in state.chunks if c.status == ChunkStatus.FAILED.value)
            log.info(
                "backfill_manager.job_complete",
                symbol=symbol,
                interval=interval,
                done=done,
                failed=failed,
                total=len(state.chunks),
            )

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    async def _load_or_init_state(
        self,
        symbol: str,
        interval: str,
        start: str | None,
        end: str | None,
    ) -> BackfillState:
        """Load existing state from Redis or initialise a fresh chunk list.

        If persisted state exists it is returned as-is so that a crashed
        backfill resumes where it left off.  Otherwise a new chunk list is
        built from *start* to *end* in :data:`CHUNK_DAYS` increments.
        """
        state_key = f"{STATE_KEY_PREFIX}:{symbol}:{interval}"
        raw = await self._redis.get(state_key)

        if raw is not None:
            try:
                data = json.loads(raw if isinstance(raw, str) else raw.decode())
                state = _dict_to_state(data)
                log.debug(
                    "backfill_manager.state_loaded",
                    symbol=symbol,
                    interval=interval,
                    chunks=len(state.chunks),
                )
                return state
            except (json.JSONDecodeError, KeyError, TypeError):
                log.warning(
                    "backfill_manager.state_decode_failed",
                    symbol=symbol,
                    interval=interval,
                )

        # Build fresh state
        now = datetime.now(UTC)

        if end is not None:
            end_dt = datetime.fromisoformat(end)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=UTC)
        else:
            end_dt = now

        if start is not None:
            start_dt = datetime.fromisoformat(start)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
        else:
            start_dt = now - timedelta(days=self._days_back)

        # Slice into chunks
        chunks: list[Chunk] = []
        cursor = start_dt
        while cursor < end_dt:
            chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end_dt)
            chunks.append(
                Chunk(
                    start=cursor.isoformat(),
                    end=chunk_end.isoformat(),
                )
            )
            cursor = chunk_end

        state = BackfillState(symbol=symbol, interval=interval, chunks=chunks)
        await self._save_state(state)

        log.info(
            "backfill_manager.state_initialised",
            symbol=symbol,
            interval=interval,
            chunks=len(chunks),
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
        )
        return state

    async def _save_state(self, state: BackfillState) -> None:
        """Persist *state* to Redis with a 30-day TTL."""
        state_key = f"{STATE_KEY_PREFIX}:{state.symbol}:{state.interval}"
        payload = json.dumps(_state_to_dict(state))
        await self._redis.setex(state_key, _STATE_TTL, payload)

    # ------------------------------------------------------------------
    # Chunk fetching
    # ------------------------------------------------------------------

    async def _fetch_chunk(
        self,
        state: BackfillState,
        chunk: Chunk,
        config: AssetConfig,
    ) -> None:
        """Fetch a single chunk from the provider router and write to Postgres.

        Updates the chunk status to RUNNING before the fetch, DONE on
        success, or FAILED (with ``last_error``) on failure.  State is
        saved after every transition so that progress is never lost.
        """
        chunk.status = ChunkStatus.RUNNING.value
        chunk.attempts += 1
        await self._save_state(state)

        try:
            start_dt = datetime.fromisoformat(chunk.start)
            end_dt = datetime.fromisoformat(chunk.end)

            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=UTC)

            bars, provider = await self._router.fetch_bars(
                state.symbol,
                DataInterval(state.interval),
                start_dt,
                end_dt,
                config,
            )

            if bars:
                await self._write_to_postgres(state.symbol, state.interval, bars)

            chunk.status = ChunkStatus.DONE.value
            chunk.last_error = None

            log.info(
                "backfill_manager.chunk_done",
                symbol=state.symbol,
                interval=state.interval,
                chunk_start=chunk.start,
                chunk_end=chunk.end,
                bars=len(bars),
                provider=provider.value if provider else None,
                attempt=chunk.attempts,
            )
        except Exception as exc:
            chunk.status = ChunkStatus.FAILED.value
            chunk.last_error = f"{type(exc).__name__}: {exc}"

            log.warning(
                "backfill_manager.chunk_failed",
                symbol=state.symbol,
                interval=state.interval,
                chunk_start=chunk.start,
                chunk_end=chunk.end,
                attempt=chunk.attempts,
                error=chunk.last_error,
            )
        finally:
            await self._save_state(state)

    # ------------------------------------------------------------------
    # Postgres writer
    # ------------------------------------------------------------------

    async def _write_to_postgres(
        self,
        symbol: str,
        interval: str,
        bars: list[OHLCVBar],
    ) -> None:
        """Bulk-insert bars into Postgres, skipping duplicates.

        Uses ``INSERT … ON CONFLICT DO NOTHING`` on the
        ``(symbol, interval, bar_time)`` natural key so that overlapping
        fetches are idempotent.
        """
        from sqlalchemy import text

        if not bars:
            return

        insert_stmt = text(
            """
            INSERT INTO historical_bars (symbol, timestamp, open, high, low, close, volume, interval)
            VALUES (:symbol, :timestamp, :open, :high, :low, :close, :volume, :interval)
            ON CONFLICT (symbol, timestamp, interval) DO NOTHING;
            """
        )

        async with self._engine.begin() as conn:
            for bar in bars:
                await conn.execute(
                    insert_stmt,
                    {
                        "symbol": symbol,
                        "timestamp": bar.bar_time.isoformat(),
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                        "interval": interval,
                    },
                )

        log.debug(
            "backfill_manager.wrote_bars",
            symbol=symbol,
            interval=interval,
            count=len(bars),
        )
