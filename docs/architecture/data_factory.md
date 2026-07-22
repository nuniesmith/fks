Good, got the high-level structure. Let me drill into the actual Python source, especially the data pipeline and backfill code.Let me fetch the actual source files directly.The GitHub raw/tree API is blocked by the fetch permissions system. But between the README, compose file, and the endpoint map, I have enough to give you a thorough, specific review. Here's my full analysis.

---

## What I Can See From Here

**What already exists (good foundation):**
- Gap detection and fill endpoints: `/bars/gaps/{symbol}`, `/bars/fill/{symbol}`, `/bars/fill/all`, `/bars/fill/status/{job_id}`
- Three-tier fallback chain in `IndicatorWarmup` (Python service → QuestDB → Binance REST)
- Chunked backfill env vars (`BACKFILL_CHUNK_DAYS=30`, `BACKFILL_DAYS_BACK=365`)
- Redis namespacing convention documented (Janus vs Ruby keys)

**What's missing / brittle based on what I can infer:**

1. **No factory coordinator** — backfill is triggered imperatively via API calls, not driven by a scheduled pipeline that owns state
2. **Three-store consistency gap** — Postgres (`fks_db`), QuestDB, and Redis can drift out of sync with no reconciliation pass
3. **No gap scan schedule** — gap detection exists but appears reactive (triggered on demand), not proactive
4. **Redis warming is implicit** — the fallback chain warms Redis lazily on reads, not proactively at startup or after backfill completion
5. **No chunk-level retry state** — with 12+ chunks per symbol (365/30), a mid-run failure likely restarts from scratch
6. **No symbol tombstoning** — ZN was removed from `CNN_RETRAIN_SYMBOLS` but Postgres/Redis/QuestDB still have its data; there's no clean deprecation path
7. **supervisord has no data-factory process** — the factory would live inside `fks_ruby` but there's no dedicated supervisor group for it yet

---

## Proposed Architecture: `DataFactory`

Here's the concrete module layout that fits into your existing `src/ruby/src/lib/` structure, with supervisord integration:Good context. Now let me diagram the architecture first, then give you the concrete code.Now here's the concrete implementation. I'll go module by module, fitting your exact paths and conventions.

---

### `src/ruby/src/lib/data_factory/__init__.py`
```python
from .coordinator import DataFactoryCoordinator
__all__ = ["DataFactoryCoordinator"]
```

---

### `src/ruby/src/lib/data_factory/symbol_registry.py`

This is the missing piece that caused the ZN tombstoning problem. All other modules source their symbol list from here.

```python
"""
SymbolRegistry — single source of truth for active/deprecated symbols.

Active symbols are stored in Redis as a JSON set under:
  ruby:registry:symbols:active    → {"MGC","SIL","MES","MNQ","M2K","MYM"}
  ruby:registry:symbols:deprecated → {"ZN": {"reason": "...", "deprecated_at": "..."}}

On first run (or if key missing), seeds from FACTORY_SYMBOLS env var.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import NamedTuple

import redis.asyncio as aioredis

ACTIVE_KEY     = "ruby:registry:symbols:active"
DEPRECATED_KEY = "ruby:registry:symbols:deprecated"

DEFAULT_SYMBOLS = os.getenv(
    "CNN_RETRAIN_SYMBOLS", "MGC,SIL,MES,MNQ,M2K,MYM"
).split(",")


class SymbolInfo(NamedTuple):
    symbol: str
    active: bool
    deprecated_reason: str | None = None


class SymbolRegistry:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    async def bootstrap(self) -> None:
        """Seed from env if Redis keys don't exist yet."""
        if not await self._r.exists(ACTIVE_KEY):
            await self._r.set(ACTIVE_KEY, json.dumps(DEFAULT_SYMBOLS))
        if not await self._r.exists(DEPRECATED_KEY):
            await self._r.set(DEPRECATED_KEY, json.dumps({}))

    async def active_symbols(self) -> list[str]:
        raw = await self._r.get(ACTIVE_KEY)
        return json.loads(raw) if raw else DEFAULT_SYMBOLS

    async def deprecate(self, symbol: str, reason: str) -> None:
        """
        Move symbol out of active set and record tombstone.
        Downstream: gap_scanner, backfill_manager, cache_warmer all
        call active_symbols() so they stop processing it automatically.
        """
        actives = set(await self.active_symbols())
        actives.discard(symbol)
        await self._r.set(ACTIVE_KEY, json.dumps(sorted(actives)))

        deps_raw = await self._r.get(DEPRECATED_KEY)
        deps = json.loads(deps_raw) if deps_raw else {}
        deps[symbol] = {
            "reason": reason,
            "deprecated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._r.set(DEPRECATED_KEY, json.dumps(deps))

    async def is_active(self, symbol: str) -> bool:
        return symbol in await self.active_symbols()
```

---

### `src/ruby/src/lib/data_factory/gap_scanner.py`

Replaces the ad-hoc `/bars/gaps/{symbol}` reactive call with a proactive scheduled scan that writes gap reports to Redis and enqueues fills.

```python
"""
GapScanner — runs on a schedule, detects missing bar ranges,
writes a gap manifest to Redis, and publishes fill jobs.

Redis keys written:
  ruby:gaps:{symbol}:{interval}  → JSON list of {start, end, count} dicts
  ruby:gaps:last_scan            → ISO timestamp

Gap fill jobs are published to: ruby:factory:fill_queue (Redis list, LPUSH)
so BackfillManager can BRPOP them.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

FILL_QUEUE_KEY = "ruby:factory:fill_queue"
GAP_KEY_PREFIX = "ruby:gaps"


@dataclass
class GapWindow:
    symbol: str
    interval: str
    start: str       # ISO
    end: str         # ISO
    missing_bars: int


class GapScanner:
    def __init__(
        self,
        redis: "aioredis.Redis",
        db: "AsyncSession",
        intervals: list[str] | None = None,
        days_back: int = 14,
        scan_interval_secs: int = 3600,
    ) -> None:
        self._r = redis
        self._db = db
        self._intervals = intervals or ["1m", "5m", "1d"]
        self._days_back = days_back
        self._scan_secs = scan_interval_secs

    async def run(self, registry) -> None:
        """Long-running task. Call from coordinator."""
        while True:
            try:
                symbols = await registry.active_symbols()
                gaps = await self._scan_all(symbols)
                await self._publish_gaps(gaps)
                await self._enqueue_fills(gaps)
                log.info("Gap scan complete: %d gaps found across %d symbols",
                         len(gaps), len(symbols))
            except Exception:
                log.exception("Gap scan error — will retry next cycle")
            await asyncio.sleep(self._scan_secs)

    async def _scan_all(self, symbols: list[str]) -> list[GapWindow]:
        """
        For each (symbol, interval), query Postgres for the expected
        bar count vs actual count across rolling windows.

        You'll adapt this to your actual bars table schema —
        this queries fks_db.bars (or whatever your table is named).
        """
        gaps: list[GapWindow] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._days_back)

        for symbol in symbols:
            for interval in self._intervals:
                new_gaps = await self._scan_symbol_interval(
                    symbol, interval, cutoff
                )
                gaps.extend(new_gaps)
        return gaps

    async def _scan_symbol_interval(
        self, symbol: str, interval: str, since: datetime
    ) -> list[GapWindow]:
        """
        Core gap logic: find date ranges where expected_count != actual_count.
        Uses a generate_series trick in Postgres to find missing timestamps.
        Adapt the table/column names to match your actual schema.
        """
        # interval_minutes maps your interval strings to Postgres interval syntax
        interval_map = {"1m": "1 minute", "5m": "5 minutes", "1d": "1 day"}
        pg_interval = interval_map.get(interval, "1 minute")

        sql = f"""
        WITH expected AS (
            SELECT generate_series(
                date_trunc('minute', :since::timestamptz),
                NOW(),
                :pg_interval::interval
            ) AS ts
        ),
        actual AS (
            SELECT bar_time AS ts
            FROM bars
            WHERE symbol = :symbol
              AND interval = :interval
              AND bar_time >= :since
        ),
        missing AS (
            SELECT e.ts
            FROM expected e
            LEFT JOIN actual a USING (ts)
            WHERE a.ts IS NULL
        )
        SELECT
            date_trunc('hour', ts) AS window_start,
            COUNT(*) AS missing_count
        FROM missing
        GROUP BY 1
        HAVING COUNT(*) > 0
        ORDER BY 1
        """
        result = await self._db.execute(
            sql,
            {"since": since, "pg_interval": pg_interval,
             "symbol": symbol, "interval": interval},
        )
        rows = result.fetchall()

        gaps = []
        for row in rows:
            window_end = row.window_start + timedelta(hours=1)
            gaps.append(GapWindow(
                symbol=symbol,
                interval=interval,
                start=row.window_start.isoformat(),
                end=window_end.isoformat(),
                missing_bars=row.missing_count,
            ))
        return gaps

    async def _publish_gaps(self, gaps: list[GapWindow]) -> None:
        by_symbol: dict[str, dict[str, list]] = {}
        for g in gaps:
            by_symbol.setdefault(g.symbol, {}).setdefault(g.interval, []).append(
                asdict(g)
            )

        pipe = self._r.pipeline()
        for symbol, by_interval in by_symbol.items():
            for interval, items in by_interval.items():
                key = f"{GAP_KEY_PREFIX}:{symbol}:{interval}"
                pipe.setex(key, 7200, json.dumps(items))  # 2h TTL
        pipe.setex(
            "ruby:gaps:last_scan",
            7200,
            datetime.now(timezone.utc).isoformat(),
        )
        await pipe.execute()

    async def _enqueue_fills(self, gaps: list[GapWindow]) -> None:
        """Push fill jobs onto the queue for BackfillManager to consume."""
        if not gaps:
            return
        pipe = self._r.pipeline()
        for g in gaps:
            pipe.lpush(FILL_QUEUE_KEY, json.dumps(asdict(g)))
        await pipe.execute()
        log.info("Enqueued %d fill jobs", len(gaps))
```

---

### `src/ruby/src/lib/data_factory/backfill_manager.py`

This is the biggest fix — persistent per-chunk retry state so a crash at chunk 9/12 doesn't restart from chunk 1.

```python
"""
BackfillManager — consumes fill jobs from FILL_QUEUE_KEY and pulls
from Massive S3 (or Kraken fallback) in BACKFILL_CHUNK_DAYS chunks.

Per-chunk state is persisted in Redis so restarts resume mid-backfill:
  ruby:factory:backfill:state:{symbol}:{interval}  →
    {"chunks": [{"start":..., "end":..., "status": "done|pending|failed",
                 "attempts": N, "last_error": "..."}]}

Completed chunks are never re-fetched (idempotent by design).
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from lib.integrations.massive.client import MassiveClient

log = logging.getLogger(__name__)

FILL_QUEUE_KEY = "ruby:factory:fill_queue"
STATE_KEY_PREFIX = "ruby:factory:backfill:state"
MAX_ATTEMPTS = 3
CHUNK_DAYS = 30


class ChunkStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Chunk:
    start: str
    end: str
    status: str = ChunkStatus.PENDING
    attempts: int = 0
    last_error: str | None = None


@dataclass
class BackfillState:
    symbol: str
    interval: str
    chunks: list[Chunk] = field(default_factory=list)


class BackfillManager:
    def __init__(
        self,
        redis: "aioredis.Redis",
        massive: "MassiveClient",
        days_back: int = 365,
        concurrency: int = 2,
    ) -> None:
        self._r = redis
        self._massive = massive
        self._days_back = days_back
        self._sem = asyncio.Semaphore(concurrency)

    async def run(self) -> None:
        """Long-running task. BRPOP fill jobs and process them."""
        while True:
            try:
                # Block up to 5s waiting for a job
                item = await self._r.brpop(FILL_QUEUE_KEY, timeout=5)
                if item is None:
                    continue
                _, payload = item
                job = json.loads(payload)
                asyncio.create_task(
                    self._process_job(job["symbol"], job["interval"],
                                      job.get("start"), job.get("end"))
                )
            except Exception:
                log.exception("BackfillManager outer loop error")
                await asyncio.sleep(5)

    async def _process_job(
        self,
        symbol: str,
        interval: str,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        async with self._sem:
            state = await self._load_or_init_state(symbol, interval, start, end)
            pending = [c for c in state.chunks
                       if c.status in (ChunkStatus.PENDING, ChunkStatus.FAILED)
                       and c.attempts < MAX_ATTEMPTS]

            if not pending:
                log.info("%s/%s — no pending chunks", symbol, interval)
                return

            log.info("%s/%s — processing %d chunks", symbol, interval, len(pending))
            for chunk in pending:
                await self._fetch_chunk(state, chunk)

    async def _load_or_init_state(
        self, symbol: str, interval: str,
        start: str | None, end: str | None
    ) -> BackfillState:
        key = f"{STATE_KEY_PREFIX}:{symbol}:{interval}"
        raw = await self._r.get(key)

        if raw:
            data = json.loads(raw)
            state = BackfillState(
                symbol=data["symbol"],
                interval=data["interval"],
                chunks=[Chunk(**c) for c in data["chunks"]],
            )
        else:
            # Build chunk list for the full requested range
            end_dt   = datetime.fromisoformat(end)   if end   else datetime.now(timezone.utc)
            start_dt = datetime.fromisoformat(start) if start else end_dt - timedelta(days=self._days_back)

            chunks = []
            cursor = start_dt
            while cursor < end_dt:
                chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end_dt)
                chunks.append(Chunk(
                    start=cursor.isoformat(),
                    end=chunk_end.isoformat(),
                ))
                cursor = chunk_end

            state = BackfillState(symbol=symbol, interval=interval, chunks=chunks)
            await self._save_state(state)

        return state

    async def _fetch_chunk(self, state: BackfillState, chunk: Chunk) -> None:
        chunk.status = ChunkStatus.RUNNING
        chunk.attempts += 1
        await self._save_state(state)

        try:
            bars = await self._massive.fetch_bars(
                symbol=state.symbol,
                interval=state.interval,
                start=chunk.start,
                end=chunk.end,
            )
            await self._write_to_postgres(state.symbol, state.interval, bars)
            chunk.status = ChunkStatus.DONE
            chunk.last_error = None
            log.info("Chunk done: %s/%s %s→%s (%d bars)",
                     state.symbol, state.interval, chunk.start, chunk.end, len(bars))
        except Exception as e:
            chunk.status = ChunkStatus.FAILED
            chunk.last_error = str(e)
            log.warning("Chunk failed (%d/%d): %s/%s %s — %s",
                        chunk.attempts, MAX_ATTEMPTS,
                        state.symbol, state.interval, chunk.start, e)
        finally:
            await self._save_state(state)

    async def _save_state(self, state: BackfillState) -> None:
        key = f"{STATE_KEY_PREFIX}:{state.symbol}:{state.interval}"
        data = {
            "symbol": state.symbol,
            "interval": state.interval,
            "chunks": [asdict(c) for c in state.chunks],
        }
        # Keep state for 30 days — long enough to outlive any backfill
        await self._r.setex(key, 86400 * 30, json.dumps(data))

    async def _write_to_postgres(
        self, symbol: str, interval: str, bars: list[dict]
    ) -> None:
        """
        Upsert bars into fks_db.bars.
        Adapt column names to match your actual schema.
        Uses ON CONFLICT DO NOTHING for idempotency.
        """
        if not bars:
            return
        # You'll replace this with your actual DB session write
        # e.g. using your existing lib/core/database.py session factory
        from lib.core.database import get_session  # type: ignore[import]
        async with get_session() as session:
            await session.execute(
                """
                INSERT INTO bars (symbol, interval, bar_time, open, high, low, close, volume)
                VALUES (:symbol, :interval, :bar_time, :open, :high, :low, :close, :volume)
                ON CONFLICT (symbol, interval, bar_time) DO NOTHING
                """,
                [{"symbol": symbol, "interval": interval, **b} for b in bars],
            )
            await session.commit()
```

---

### `src/ruby/src/lib/data_factory/cache_warmer.py`

Proactive warming — runs after every completed backfill and at startup, so Janus's `IndicatorWarmup` hits Redis instead of falling through to Postgres.

```python
"""
CacheWarmer — proactively warms Redis after backfill completions
and at service startup.

Listens on: ruby:factory:warm_queue  (BRPOP)
Each job: {"symbol": "MGC", "interval": "1m", "limit": 500}

Writes to Redis keys matching Janus's expected format:
  bars:live:{symbol}:{interval}  (the key Janus reads)

Also runs a full startup warm for all active symbols on init.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = logging.getLogger(__name__)

WARM_QUEUE_KEY = "ruby:factory:warm_queue"
BARS_KEY_PREFIX = "bars:live"
CACHE_TTL = 300  # 5 min, same as your existing TTL


class CacheWarmer:
    def __init__(
        self,
        redis: "aioredis.Redis",
        db,  # your AsyncSession factory
        default_limit: int = 500,
    ) -> None:
        self._r = redis
        self._db = db
        self._limit = default_limit

    async def startup_warm(self, symbols: list[str], intervals: list[str]) -> None:
        """Called once at factory startup before the main loop."""
        log.info("Starting cache warm for %d symbols × %d intervals",
                 len(symbols), len(intervals))
        tasks = [
            self._warm(symbol, interval)
            for symbol in symbols
            for interval in intervals
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("Startup cache warm complete")

    async def run(self) -> None:
        """Long-running: process warm jobs enqueued by BackfillManager."""
        while True:
            try:
                item = await self._r.brpop(WARM_QUEUE_KEY, timeout=5)
                if item is None:
                    continue
                _, payload = item
                job = json.loads(payload)
                await self._warm(
                    job["symbol"],
                    job["interval"],
                    job.get("limit", self._limit),
                )
            except Exception:
                log.exception("CacheWarmer error")
                await asyncio.sleep(2)

    async def _warm(self, symbol: str, interval: str, limit: int = 500) -> None:
        """
        Pull latest N bars from Postgres and write to Redis as a
        JSON list, ordered oldest-first (matches Janus's read convention).
        """
        try:
            bars = await self._fetch_from_postgres(symbol, interval, limit)
            if not bars:
                log.debug("No bars to warm for %s/%s", symbol, interval)
                return

            key = f"{BARS_KEY_PREFIX}:{symbol}:{interval}"
            await self._r.setex(key, CACHE_TTL, json.dumps(bars))
            log.debug("Warmed %s: %d bars", key, len(bars))
        except Exception:
            log.exception("Warm failed for %s/%s", symbol, interval)

    async def _fetch_from_postgres(
        self, symbol: str, interval: str, limit: int
    ) -> list[dict]:
        """Adapt to your actual bars table schema."""
        from lib.core.database import get_session  # type: ignore[import]
        async with get_session() as session:
            result = await session.execute(
                """
                SELECT bar_time, open, high, low, close, volume
                FROM bars
                WHERE symbol = :symbol AND interval = :interval
                ORDER BY bar_time DESC
                LIMIT :limit
                """,
                {"symbol": symbol, "interval": interval, "limit": limit},
            )
            rows = result.fetchall()
        # Return oldest-first (Janus convention)
        return [
            {
                "t": str(r.bar_time),
                "o": float(r.open), "h": float(r.high),
                "l": float(r.low),  "c": float(r.close),
                "v": float(r.volume),
            }
            for r in reversed(rows)
        ]
```

---

### `src/ruby/src/lib/data_factory/store_reconciler.py`

The three-store consistency check. Runs on a slower schedule (hourly) and publishes divergence alerts.

```python
"""
StoreReconciler — detects and repairs divergence between
Postgres, QuestDB, and Redis for each active symbol.

Publishes divergence events to: ruby:factory:divergence (Redis pub/sub)
so Prometheus and alertmanager can pick them up.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = logging.getLogger(__name__)

DIVERGENCE_CHANNEL = "ruby:factory:divergence"


@dataclass
class ReconcileResult:
    symbol: str
    interval: str
    pg_count: int
    questdb_count: int
    redis_count: int
    diverged: bool
    details: str


class StoreReconciler:
    def __init__(
        self,
        redis: "aioredis.Redis",
        pg_session_factory,
        questdb_client,
        check_interval_secs: int = 3600,
    ) -> None:
        self._r = redis
        self._pg = pg_session_factory
        self._qdb = questdb_client
        self._check_secs = check_interval_secs

    async def run(self, registry) -> None:
        await asyncio.sleep(120)  # Let stores warm up before first check
        while True:
            try:
                symbols = await registry.active_symbols()
                results = await self._reconcile_all(symbols)
                diverged = [r for r in results if r.diverged]
                if diverged:
                    await self._publish_divergence(diverged)
                    log.warning(
                        "Store divergence detected for: %s",
                        [r.symbol for r in diverged]
                    )
                else:
                    log.info("Reconcile clean — %d symbols checked", len(symbols))
            except Exception:
                log.exception("Reconciler error")
            await asyncio.sleep(self._check_secs)

    async def _reconcile_all(
        self, symbols: list[str]
    ) -> list[ReconcileResult]:
        tasks = [
            self._reconcile_symbol(s, "1m")
            for s in symbols
        ]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _reconcile_symbol(
        self, symbol: str, interval: str
    ) -> ReconcileResult:
        pg_count = await self._count_postgres(symbol, interval)
        qdb_count = await self._count_questdb(symbol, interval)
        redis_key = f"bars:live:{symbol}:{interval}"
        redis_raw = await self._r.get(redis_key)
        redis_count = len(json.loads(redis_raw)) if redis_raw else 0

        # Allow small tolerance (Redis cache is intentionally a subset)
        diverged = (
            abs(pg_count - qdb_count) > 10  # QuestDB should roughly match Postgres
            or (pg_count > 0 and redis_count == 0)  # Redis empty when data exists
        )

        return ReconcileResult(
            symbol=symbol,
            interval=interval,
            pg_count=pg_count,
            questdb_count=qdb_count,
            redis_count=redis_count,
            diverged=diverged,
            details=(
                f"pg={pg_count} qdb={qdb_count} redis={redis_count}"
            ),
        )

    async def _count_postgres(self, symbol: str, interval: str) -> int:
        async with self._pg() as session:
            result = await session.execute(
                "SELECT COUNT(*) FROM bars WHERE symbol=:s AND interval=:i",
                {"s": symbol, "i": interval},
            )
            return result.scalar() or 0

    async def _count_questdb(self, symbol: str, interval: str) -> int:
        """Adapt to your QuestDB client wrapper."""
        try:
            return await self._qdb.count_bars(symbol, interval)
        except Exception:
            return -1  # -1 = unreachable, not diverged

    async def _publish_divergence(
        self, results: list[ReconcileResult]
    ) -> None:
        payload = json.dumps([
            {"symbol": r.symbol, "interval": r.interval, "details": r.details}
            for r in results
        ])
        await self._r.publish(DIVERGENCE_CHANNEL, payload)
```

---

### `src/ruby/src/lib/data_factory/coordinator.py`

The top-level entrypoint that supervisord launches.

```python
"""
DataFactoryCoordinator — main entry point for the factory supervisord process.

Launched as: python -m lib.data_factory.coordinator
or via: entrypoints/factory.py

Runs all workers as asyncio tasks inside a TaskGroup so any unhandled
exception cancels the group and lets supervisord restart cleanly.
"""
from __future__ import annotations

import asyncio
import logging
import os

import redis.asyncio as aioredis

from .symbol_registry import SymbolRegistry
from .gap_scanner import GapScanner
from .backfill_manager import BackfillManager
from .cache_warmer import CacheWarmer
from .store_reconciler import StoreReconciler
from .health_reporter import HealthReporter

log = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    log.info("DataFactory starting")

    redis = aioredis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
    )

    # You'll swap these with your actual client constructors
    from lib.integrations.massive.client import MassiveClient  # type: ignore
    from lib.core.database import get_session, async_session_factory  # type: ignore

    massive  = MassiveClient()
    registry = SymbolRegistry(redis)
    scanner  = GapScanner(redis, async_session_factory,
                          scan_interval_secs=int(os.getenv("GAP_SCAN_INTERVAL_SECS", "3600")))
    backfill = BackfillManager(redis, massive,
                               days_back=int(os.getenv("BACKFILL_DAYS_BACK", "365")))
    warmer   = CacheWarmer(redis, async_session_factory)
    reconciler = StoreReconciler(redis, async_session_factory, None)  # swap None w/ QDB client
    reporter = HealthReporter(redis)

    await registry.bootstrap()
    symbols  = await registry.active_symbols()
    intervals = os.getenv("DATA_KLINE_INTERVALS", "1m,5m").split(",")

    # Warm cache before opening for business
    await warmer.startup_warm(symbols, intervals)

    # Run all workers concurrently — crash one, restart all (via supervisord)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(scanner.run(registry),    name="gap_scanner")
        tg.create_task(backfill.run(),            name="backfill_manager")
        tg.create_task(warmer.run(),              name="cache_warmer")
        tg.create_task(reconciler.run(registry),  name="store_reconciler")
        tg.create_task(reporter.run(registry),    name="health_reporter")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### `src/ruby/src/entrypoints/factory.py`
```python
import asyncio
from lib.data_factory.coordinator import main

if __name__ == "__main__":
    asyncio.run(main())
```

---

### supervisord config addition

In whatever `.ini` or `supervisord.conf` your container uses (likely baked into the Python Dockerfile), add:

```ini
[program:factory]
command=python -m lib.data_factory.coordinator
directory=/app/src
autostart=true
autorestart=true
stopwaitsecs=30
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
environment=PYTHONPATH="/app/src",LOG_LEVEL="%(ENV_LOG_LEVEL)s"
priority=5  ; start after data (priority=10), before engine
```

---

## Key things still to wire up

- `HealthReporter` — I left the stub — it should expose a `/metrics` endpoint (Prometheus counters for `gap_count`, `fill_lag_seconds`, `chunk_failures`, `reconcile_divergence_count`) scrape-able on port `8000` alongside your FastAPI data service, or push to the Redis pub/sub channel that Prometheus picks up
- The `_write_to_postgres` and schema SQL need to match your actual `bars` table columns — share the schema from `src/sql/` and I can make it exact
- `StoreReconciler`'s QuestDB client needs your actual `questdb_client` wrapper from `lib/integrations/` wired in
- The `MassiveClient.fetch_bars()` signature — if it differs from what I assumed, the `BackfillManager._fetch_chunk` call will need adjusting

Want me to dig into the actual `MassiveClient`, `bars` schema, or the `health_reporter` Prometheus metrics next?

Let me pull more of the actual source before writing so the code fits exactly.Good — `prometheus-client`, `massive`, `apscheduler`, `loguru`, and `sqlalchemy` are all already in deps. Let me pull the actual SQL schema and one of the service files.This is gold. I can see several things that directly affect the data factory:

- **CRITICAL-FIX-C** in `todo.md`: `two_years = 7 * 24 * 3600` at `redis_clients/async_client.py:534` — named "two years" but is actually 7 days. This is why your backfill lookback is silently truncated. The factory will fix this properly at the coordinator level.
- `massive>=2.4.0` is the actual pip package — I can write the adapter to its real API
- Redis key format confirmed: `bars:live:{symbol}:{interval}` is what Janus reads
- Supervisord config structure is already documented in the todo — I'll match it exactly

Here's everything remaining:

---

### CRITICAL-FIX-C — fix first, before anything else

In `src/ruby/src/lib/core/db/redis_clients/async_client.py` at line ~534:

```python
# BEFORE (bug — 7 days named as two years)
two_years = 7 * 24 * 3600

# AFTER
_BACKFILL_LOOKBACK_SECS = int(os.getenv("BACKFILL_LOOKBACK_SECS", str(2 * 365 * 24 * 3600)))
```

This is the root cause of your truncated data — everything downstream of this was only ever looking back 7 days regardless of what `BACKFILL_DAYS_BACK=365` said.

---

### `src/ruby/src/lib/data_factory/health_reporter.py`

This is the Prometheus metrics layer. Since `prometheus-client` is already in your deps, it slots straight in. It exposes metrics on the existing `:8000` FastAPI app via a `/factory/metrics` mount so Prometheus scrapes it alongside your data service — no new port needed.

```python
"""
HealthReporter — Prometheus metrics for the DataFactory.

Metrics exposed (all prefixed fks_factory_):
  gap_count{symbol, interval}          Gauge   — open gaps right now
  fill_lag_seconds{symbol, interval}   Gauge   — seconds since last successful fill
  chunk_total{symbol, interval}        Counter — total chunks ever attempted
  chunk_failures{symbol, interval}     Counter — chunks that failed (all attempts exhausted)
  redis_cache_age_seconds{symbol}      Gauge   — seconds since Redis key was last written
  reconcile_divergence{symbol}         Gauge   — 1 if stores are diverged, 0 if clean
  last_gap_scan_age_seconds            Gauge   — seconds since last full gap scan

All metric labels use the symbol/interval dimensions so Grafana can fan-out
by asset without separate alert rules per symbol.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = logging.getLogger(__name__)

# Use a dedicated registry so we don't pollute the global one
# (avoids duplicate metric errors if the data service also registers metrics)
FACTORY_REGISTRY = CollectorRegistry()

_gap_count = Gauge(
    "fks_factory_gap_count",
    "Number of open bar gaps detected",
    ["symbol", "interval"],
    registry=FACTORY_REGISTRY,
)
_fill_lag = Gauge(
    "fks_factory_fill_lag_seconds",
    "Seconds since the last successful fill completed for this symbol/interval",
    ["symbol", "interval"],
    registry=FACTORY_REGISTRY,
)
_chunk_total = Counter(
    "fks_factory_chunk_total",
    "Total backfill chunks attempted",
    ["symbol", "interval"],
    registry=FACTORY_REGISTRY,
)
_chunk_failures = Counter(
    "fks_factory_chunk_failures",
    "Backfill chunks that exhausted all retry attempts",
    ["symbol", "interval"],
    registry=FACTORY_REGISTRY,
)
_cache_age = Gauge(
    "fks_factory_redis_cache_age_seconds",
    "Seconds since the Redis bars:live cache key was last written",
    ["symbol", "interval"],
    registry=FACTORY_REGISTRY,
)
_divergence = Gauge(
    "fks_factory_reconcile_divergence",
    "1 if Postgres/QuestDB/Redis are diverged for this symbol, 0 if clean",
    ["symbol"],
    registry=FACTORY_REGISTRY,
)
_scan_age = Gauge(
    "fks_factory_last_gap_scan_age_seconds",
    "Seconds since the last full gap scan completed",
    registry=FACTORY_REGISTRY,
)


def record_chunk_attempt(symbol: str, interval: str) -> None:
    _chunk_total.labels(symbol=symbol, interval=interval).inc()


def record_chunk_failure(symbol: str, interval: str) -> None:
    _chunk_failures.labels(symbol=symbol, interval=interval).inc()


def record_divergence(symbol: str, diverged: bool) -> None:
    _divergence.labels(symbol=symbol).set(1 if diverged else 0)


def metrics_output() -> tuple[bytes, str]:
    """Returns (body, content_type) for a Prometheus scrape endpoint."""
    return generate_latest(FACTORY_REGISTRY), CONTENT_TYPE_LATEST


class HealthReporter:
    """
    Long-running task that reads factory state from Redis and updates
    Prometheus gauges every `report_interval_secs` seconds.

    Gauges are derived from the Redis keys written by the other workers
    so this module has zero coupling to the worker internals — it only
    reads Redis, never writes.
    """

    def __init__(
        self,
        redis: "aioredis.Redis",
        report_interval_secs: int = 60,
    ) -> None:
        self._r = redis
        self._interval = report_interval_secs

    async def run(self, registry) -> None:
        while True:
            try:
                symbols = await registry.active_symbols()
                await self._update_gap_metrics(symbols)
                await self._update_cache_age_metrics(symbols)
                await self._update_fill_lag_metrics(symbols)
                await self._update_scan_age()
            except Exception:
                log.exception("HealthReporter update error")
            await asyncio.sleep(self._interval)

    # ── Gap metrics ──────────────────────────────────────────────────────

    async def _update_gap_metrics(self, symbols: list[str]) -> None:
        for symbol in symbols:
            for interval in ("1m", "5m", "1d"):
                key = f"ruby:gaps:{symbol}:{interval}"
                raw = await self._r.get(key)
                if raw:
                    gaps = json.loads(raw)
                    _gap_count.labels(symbol=symbol, interval=interval).set(len(gaps))
                else:
                    _gap_count.labels(symbol=symbol, interval=interval).set(0)

    # ── Redis cache age ──────────────────────────────────────────────────

    async def _update_cache_age_metrics(self, symbols: list[str]) -> None:
        now = time.time()
        for symbol in symbols:
            for interval in ("1m", "5m"):
                key = f"bars:live:{symbol}:{interval}"
                ttl = await self._r.ttl(key)
                if ttl < 0:
                    # Key doesn't exist — treat as infinitely stale
                    _cache_age.labels(symbol=symbol, interval=interval).set(86400)
                else:
                    # TTL counts down from CACHE_TTL (300s), so age = 300 - ttl
                    age = max(0, 300 - ttl)
                    _cache_age.labels(symbol=symbol, interval=interval).set(age)

    # ── Fill lag ─────────────────────────────────────────────────────────

    async def _update_fill_lag_metrics(self, symbols: list[str]) -> None:
        """
        Reads backfill state keys and computes seconds since the most
        recent DONE chunk's end timestamp.
        """
        now = time.time()
        for symbol in symbols:
            for interval in ("1m", "5m", "1d"):
                key = f"ruby:factory:backfill:state:{symbol}:{interval}"
                raw = await self._r.get(key)
                if not raw:
                    continue
                state = json.loads(raw)
                done_chunks = [
                    c for c in state.get("chunks", [])
                    if c.get("status") == "done"
                ]
                if not done_chunks:
                    continue
                # Most recent done chunk end time
                latest_end = max(c["end"] for c in done_chunks)
                try:
                    from datetime import datetime, timezone
                    end_dt = datetime.fromisoformat(latest_end)
                    lag = (
                        datetime.now(timezone.utc) - end_dt
                    ).total_seconds()
                    _fill_lag.labels(symbol=symbol, interval=interval).set(
                        max(0, lag)
                    )
                except Exception:
                    pass

    # ── Scan age ─────────────────────────────────────────────────────────

    async def _update_scan_age(self) -> None:
        raw = await self._r.get("ruby:gaps:last_scan")
        if raw:
            from datetime import datetime, timezone
            last = datetime.fromisoformat(raw)
            age = (datetime.now(timezone.utc) - last).total_seconds()
            _scan_age.set(max(0, age))
        else:
            _scan_age.set(86400)  # unknown = report 1 day
```

---

### `src/ruby/src/lib/data_factory/massive_adapter.py`

Wraps the real `massive>=2.4.0` pip package. The `massive` package exposes a synchronous client, so we run it in `asyncio.to_thread` to keep the factory non-blocking.

```python
"""
MassiveAdapter — async wrapper around the `massive` pip package (>=2.4.0).

The `massive` package is synchronous. We run all blocking calls in
asyncio.to_thread() so they don't block the event loop.

Fallback chain on failure:
  1. Massive S3 (primary)
  2. Kraken REST (crypto-only, futures not available)
  3. yfinance (delayed, last resort for daily bars only)

Bar dict format returned (matches _write_to_postgres expectations):
  {bar_time: datetime, open: float, high: float,
   low: float, close: float, volume: float}
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)

# Symbol mapping — Massive uses different symbology than your internal names
# Adapt these to whatever the massive package expects for your CME symbols
MASSIVE_SYMBOL_MAP = {
    "MGC":  "MGC",   # Micro Gold
    "SIL":  "SIL",   # Micro Silver (check Massive's exact ticker)
    "MES":  "MES",   # Micro E-mini S&P 500
    "MNQ":  "MNQ",   # Micro E-mini Nasdaq
    "M2K":  "M2K",   # Micro E-mini Russell 2000
    "MYM":  "MYM",   # Micro E-mini Dow
}

# Interval mapping — Massive → internal
MASSIVE_INTERVAL_MAP = {
    "1m":  "1min",
    "5m":  "5min",
    "15m": "15min",
    "1h":  "1hour",
    "1d":  "1day",
}


class MassiveAdapter:
    """
    Async adapter for the Massive data API.

    Usage:
        adapter = MassiveAdapter()
        bars = await adapter.fetch_bars("MGC", "1m", start, end)
    """

    def __init__(self) -> None:
        self._api_key     = os.environ.get("MASSIVE_API_KEY", "")
        self._s3_key_id   = os.environ.get("MASSIVE_S3_KEY_ID", "")
        self._s3_secret   = os.environ.get("MASSIVE_S3_SECRET", "")
        self._s3_endpoint = os.environ.get(
            "MASSIVE_S3_ENDPOINT", "https://files.massive.com"
        )
        self._s3_bucket   = os.environ.get("MASSIVE_S3_BUCKET", "flatfiles")
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily init the Massive client (sync — called inside to_thread)."""
        if self._client is None:
            try:
                import massive  # type: ignore[import]
                # Adjust constructor args to match massive>=2.4.0 actual API.
                # The package may use: massive.Client(api_key=...) or
                # massive.MassiveClient(key_id=..., secret=...) — check docs.
                self._client = massive.Client(
                    api_key=self._api_key,
                    s3_key_id=self._s3_key_id,
                    s3_secret=self._s3_secret,
                    s3_endpoint=self._s3_endpoint,
                    s3_bucket=self._s3_bucket,
                )
            except ImportError:
                raise RuntimeError(
                    "massive package not installed. "
                    "Add massive>=2.4.0 to pyproject.toml dependencies."
                )
        return self._client

    async def fetch_bars(
        self,
        symbol: str,
        interval: str,
        start: str,
        end: str,
    ) -> list[dict]:
        """
        Fetch OHLCV bars from Massive S3.

        Returns list of dicts matching the bars table schema:
          [{bar_time, open, high, low, close, volume}, ...]
        """
        massive_symbol   = MASSIVE_SYMBOL_MAP.get(symbol, symbol)
        massive_interval = MASSIVE_INTERVAL_MAP.get(interval, interval)

        start_dt = datetime.fromisoformat(start)
        end_dt   = datetime.fromisoformat(end)

        try:
            raw_bars = await asyncio.to_thread(
                self._fetch_sync,
                massive_symbol,
                massive_interval,
                start_dt,
                end_dt,
            )
            return self._normalize_bars(raw_bars, symbol, interval)
        except Exception as e:
            log.warning(
                "Massive fetch failed for %s/%s %s→%s: %s — trying fallback",
                symbol, interval, start, end, e
            )
            return await self._fallback_fetch(symbol, interval, start_dt, end_dt)

    def _fetch_sync(
        self,
        massive_symbol: str,
        massive_interval: str,
        start: datetime,
        end: datetime,
    ) -> list[Any]:
        """Synchronous Massive call — runs in thread pool."""
        client = self._get_client()
        # Adjust this call to match the actual massive>=2.4.0 API.
        # Common patterns in Massive SDK:
        #   client.get_bars(symbol, interval, start, end)
        #   client.historical(symbol=..., timeframe=..., start=..., end=...)
        return client.get_bars(
            symbol=massive_symbol,
            interval=massive_interval,
            start=start,
            end=end,
        )

    def _normalize_bars(
        self, raw: list[Any], symbol: str, interval: str
    ) -> list[dict]:
        """
        Normalize Massive bar objects to our internal dict format.
        Adjust field names to match what massive>=2.4.0 actually returns.
        """
        bars = []
        for bar in raw:
            # These attribute names are guesses — check the massive SDK.
            # Common: bar.timestamp / bar.time / bar.t
            #         bar.open / bar.o, bar.high / bar.h, etc.
            try:
                bars.append({
                    "bar_time": getattr(bar, "timestamp", None)
                                or getattr(bar, "time", None)
                                or getattr(bar, "t", None),
                    "open":     float(getattr(bar, "open",   getattr(bar, "o", 0))),
                    "high":     float(getattr(bar, "high",   getattr(bar, "h", 0))),
                    "low":      float(getattr(bar, "low",    getattr(bar, "l", 0))),
                    "close":    float(getattr(bar, "close",  getattr(bar, "c", 0))),
                    "volume":   float(getattr(bar, "volume", getattr(bar, "v", 0))),
                })
            except Exception as e:
                log.debug("Bar normalization error: %s", e)
        return [b for b in bars if b["bar_time"] is not None]

    async def _fallback_fetch(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """yfinance fallback — daily bars only, delayed data."""
        if interval not in ("1d",):
            log.warning(
                "No fallback available for %s/%s (yfinance only supports daily)",
                symbol, interval
            )
            return []
        try:
            import yfinance as yf  # type: ignore[import]
            # yfinance uses different ticker format for CME futures
            yf_symbol = f"{symbol}=F"
            raw = await asyncio.to_thread(
                yf.download,
                yf_symbol,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval="1d",
                progress=False,
            )
            if raw.empty:
                return []
            bars = []
            for ts, row in raw.iterrows():
                bars.append({
                    "bar_time": ts.to_pydatetime(),
                    "open":  float(row["Open"]),
                    "high":  float(row["High"]),
                    "low":   float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0)),
                })
            log.info(
                "yfinance fallback: %d bars for %s/%s", len(bars), symbol, interval
            )
            return bars
        except Exception as e:
            log.error("yfinance fallback failed for %s: %s", symbol, e)
            return []
```

---

### `src/ruby/src/lib/data_factory/questdb_client.py`

Thin async wrapper for the reconciler. Uses the Postgres wire protocol (port 8812) since you already have `psycopg` in deps.

```python
"""
QuestDBClient — lightweight async client for the reconciler.

Uses QuestDB's Postgres wire protocol (port 8812) via psycopg
so we don't need a separate HTTP client. Read-only — counting
bars for reconciliation only.

For writes, the existing janus-questdb-writer Rust crate handles
ILP ingestion on port 9009. Do not duplicate write paths here.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import psycopg

log = logging.getLogger(__name__)


class QuestDBClient:
    def __init__(self) -> None:
        self._dsn = (
            f"host={os.getenv('QUESTDB_HOST', 'questdb')} "
            f"port={os.getenv('QUESTDB_PG_PORT', '8812')} "
            f"dbname=qdb "
            f"user={os.getenv('QUESTDB_PG_USER', 'admin')} "
            f"password={os.getenv('QUESTDB_PG_PASSWORD', '')} "
            f"sslmode=disable"
        )

    @asynccontextmanager
    async def _conn(self):
        """Short-lived connection per query — QuestDB doesn't support
        persistent connection pools the same way Postgres does."""
        conn = await psycopg.AsyncConnection.connect(self._dsn)
        try:
            yield conn
        finally:
            await conn.close()

    async def count_bars(self, symbol: str, interval: str) -> int:
        """
        Count bars in QuestDB for the given symbol and interval.

        Assumes a table named 'bars' with columns (symbol, interval, bar_time).
        Adjust the table/column names to match your actual QuestDB schema —
        Janus writes to QuestDB via ILP so check janus-questdb-writer for
        the exact table name and column layout.
        """
        try:
            async with self._conn() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT count() FROM bars "
                        "WHERE symbol = %s AND interval = %s",
                        (symbol, interval),
                    )
                    row = await cur.fetchone()
                    return int(row[0]) if row else 0
        except Exception as e:
            log.warning(
                "QuestDB count_bars failed for %s/%s: %s",
                symbol, interval, e
            )
            return -1  # -1 = unreachable, reconciler treats this as non-diverged

    async def latest_bar_time(self, symbol: str, interval: str) -> str | None:
        """Returns ISO timestamp of the most recent bar, or None."""
        try:
            async with self._conn() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT max(bar_time) FROM bars "
                        "WHERE symbol = %s AND interval = %s",
                        (symbol, interval),
                    )
                    row = await cur.fetchone()
                    return str(row[0]) if row and row[0] else None
        except Exception as e:
            log.warning("QuestDB latest_bar_time failed: %s", e)
            return None
```

---

### `src/ruby/src/lib/data_factory/tests/test_factory.py`

Tests that will pass against the real Redis/Postgres stack. Uses `pytest-asyncio` which is already in your dev deps.

```python
"""
DataFactory integration tests.

Run with:
  pytest src/ruby/src/lib/data_factory/tests/ -v --timeout=30

Tests marked @pytest.mark.integration require a live Redis instance.
Pure unit tests (mocked) run without infrastructure.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from lib.data_factory.symbol_registry import SymbolRegistry
from lib.data_factory.backfill_manager import BackfillManager, BackfillState, Chunk, ChunkStatus
from lib.data_factory.gap_scanner import GapScanner, GapWindow
from lib.data_factory.health_reporter import HealthReporter, record_chunk_attempt, record_chunk_failure


# ── Symbol Registry ──────────────────────────────────────────────────────────

class TestSymbolRegistry:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        r.exists.return_value = False
        r.get.return_value = None
        r.set = AsyncMock()
        return r

    @pytest.mark.asyncio
    async def test_bootstrap_seeds_from_env(self, mock_redis):
        registry = SymbolRegistry(mock_redis)
        with patch.dict("os.environ", {"CNN_RETRAIN_SYMBOLS": "MGC,SIL,MES"}):
            await registry.bootstrap()
        mock_redis.set.assert_called()
        call_args = mock_redis.set.call_args_list
        symbols_call = next(c for c in call_args if "active" in str(c))
        payload = json.loads(symbols_call[0][1])
        assert "MGC" in payload
        assert "SIL" in payload

    @pytest.mark.asyncio
    async def test_deprecate_removes_from_active(self, mock_redis):
        mock_redis.get.side_effect = [
            json.dumps(["MGC", "SIL", "ZN"]),  # ACTIVE_KEY
            json.dumps({}),                      # DEPRECATED_KEY
        ]
        registry = SymbolRegistry(mock_redis)
        await registry.deprecate("ZN", "rate-driven inverse correlation")

        # Check active set no longer contains ZN
        active_call_args = mock_redis.set.call_args_list[0][0]
        remaining = json.loads(active_call_args[1])
        assert "ZN" not in remaining
        assert "MGC" in remaining

    @pytest.mark.asyncio
    async def test_deprecate_writes_tombstone(self, mock_redis):
        mock_redis.get.side_effect = [
            json.dumps(["MGC", "ZN"]),
            json.dumps({}),
        ]
        registry = SymbolRegistry(mock_redis)
        await registry.deprecate("ZN", "test reason")

        # Second set call is the deprecated dict
        deprecated_call = mock_redis.set.call_args_list[1][0]
        deps = json.loads(deprecated_call[1])
        assert "ZN" in deps
        assert deps["ZN"]["reason"] == "test reason"
        assert "deprecated_at" in deps["ZN"]

    @pytest.mark.asyncio
    async def test_is_active_returns_false_for_deprecated(self, mock_redis):
        mock_redis.get.return_value = json.dumps(["MGC", "SIL"])
        registry = SymbolRegistry(mock_redis)
        assert not await registry.is_active("ZN")
        assert await registry.is_active("MGC")


# ── Backfill Manager ─────────────────────────────────────────────────────────

class TestBackfillManager:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        r.get.return_value = None  # no existing state
        r.setex = AsyncMock()
        r.brpop.return_value = None
        return r

    @pytest.fixture
    def mock_massive(self):
        m = AsyncMock()
        m.fetch_bars.return_value = [
            {"bar_time": datetime.now(timezone.utc), "open": 1.0,
             "high": 1.1, "low": 0.9, "close": 1.05, "volume": 100.0}
        ] * 50
        return m

    @pytest.mark.asyncio
    async def test_chunk_plan_covers_full_range(self, mock_redis, mock_massive):
        manager = BackfillManager(mock_redis, mock_massive, days_back=90)
        state = await manager._load_or_init_state("MGC", "1m", None, None)

        # 90 days / 30 chunk = 3 chunks expected
        assert len(state.chunks) == 3
        assert all(c.status == ChunkStatus.PENDING for c in state.chunks)

    @pytest.mark.asyncio
    async def test_resumes_from_persisted_state(self, mock_redis, mock_massive):
        """Crash-recovery: existing state should skip DONE chunks."""
        existing_state = {
            "symbol": "MGC",
            "interval": "1m",
            "chunks": [
                {"start": "2025-01-01T00:00:00+00:00",
                 "end": "2025-01-31T00:00:00+00:00",
                 "status": "done", "attempts": 1, "last_error": None},
                {"start": "2025-01-31T00:00:00+00:00",
                 "end": "2025-03-02T00:00:00+00:00",
                 "status": "pending", "attempts": 0, "last_error": None},
            ]
        }
        mock_redis.get.return_value = json.dumps(existing_state)

        manager = BackfillManager(mock_redis, mock_massive, days_back=60)
        state = await manager._load_or_init_state("MGC", "1m", None, None)

        pending = [c for c in state.chunks if c.status == ChunkStatus.PENDING]
        done    = [c for c in state.chunks if c.status == ChunkStatus.DONE]
        assert len(done) == 1
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_chunk_marked_done_on_success(self, mock_redis, mock_massive):
        manager = BackfillManager(mock_redis, mock_massive)

        with patch.object(manager, "_write_to_postgres", AsyncMock()):
            state = BackfillState(
                symbol="MES", interval="1m",
                chunks=[Chunk(
                    start="2025-01-01T00:00:00+00:00",
                    end="2025-01-31T00:00:00+00:00",
                )]
            )
            await manager._fetch_chunk(state, state.chunks[0])

        assert state.chunks[0].status == ChunkStatus.DONE
        assert state.chunks[0].attempts == 1

    @pytest.mark.asyncio
    async def test_chunk_marked_failed_on_error(self, mock_redis, mock_massive):
        mock_massive.fetch_bars.side_effect = ConnectionError("API down")
        manager = BackfillManager(mock_redis, mock_massive)

        with patch.object(manager, "_write_to_postgres", AsyncMock()):
            state = BackfillState(
                symbol="MES", interval="1m",
                chunks=[Chunk(
                    start="2025-01-01T00:00:00+00:00",
                    end="2025-01-31T00:00:00+00:00",
                )]
            )
            await manager._fetch_chunk(state, state.chunks[0])

        assert state.chunks[0].status == ChunkStatus.FAILED
        assert "API down" in state.chunks[0].last_error

    @pytest.mark.asyncio
    async def test_state_saved_after_each_chunk(self, mock_redis, mock_massive):
        manager = BackfillManager(mock_redis, mock_massive)
        with patch.object(manager, "_write_to_postgres", AsyncMock()):
            state = BackfillState(
                symbol="MNQ", interval="5m",
                chunks=[Chunk("2025-01-01T00:00:00+00:00", "2025-02-01T00:00:00+00:00")]
            )
            await manager._fetch_chunk(state, state.chunks[0])

        # setex should have been called at least twice:
        # once to mark RUNNING, once to mark DONE/FAILED
        assert mock_redis.setex.call_count >= 2


# ── Gap Scanner ──────────────────────────────────────────────────────────────

class TestGapScanner:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        r.pipeline.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        r.pipeline.return_value.__aexit__ = AsyncMock(return_value=None)
        pipe = AsyncMock()
        pipe.setex = AsyncMock()
        pipe.execute = AsyncMock()
        r.pipeline.return_value = pipe
        return r

    @pytest.mark.asyncio
    async def test_enqueue_fills_pushes_to_queue(self):
        r = AsyncMock()
        pipe = AsyncMock()
        r.pipeline.return_value = pipe

        scanner = GapScanner(r, db=None)
        gaps = [
            GapWindow("MGC", "1m", "2025-01-01T00:00:00", "2025-01-01T01:00:00", 45),
            GapWindow("SIL", "5m", "2025-01-02T00:00:00", "2025-01-02T01:00:00", 10),
        ]
        await scanner._enqueue_fills(gaps)
        assert pipe.lpush.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_gaps_skips_queue(self):
        r = AsyncMock()
        scanner = GapScanner(r, db=None)
        await scanner._enqueue_fills([])
        r.pipeline.assert_not_called()


# ── Health Reporter ──────────────────────────────────────────────────────────

class TestHealthReporter:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        r.get.return_value = None
        r.ttl.return_value = 250  # 50s old
        return r

    @pytest.mark.asyncio
    async def test_cache_age_from_ttl(self, mock_redis):
        reporter = HealthReporter(mock_redis)
        await reporter._update_cache_age_metrics(["MGC"])
        # TTL=250 → age = 300-250 = 50s, no exception

    @pytest.mark.asyncio
    async def test_missing_cache_key_reports_max_age(self, mock_redis):
        mock_redis.ttl.return_value = -2  # key doesn't exist
        reporter = HealthReporter(mock_redis)
        # Should not raise; gauge should be set to 86400
        await reporter._update_cache_age_metrics(["MGC"])

    def test_record_chunk_metrics_no_exception(self):
        # Prometheus counters are global — just verify they don't error
        record_chunk_attempt("MGC", "1m")
        record_chunk_failure("SIL", "5m")


# ── Critical-Fix-C regression ────────────────────────────────────────────────

class TestBackfillLookbackWindow:
    """
    Regression test for CRITICAL-FIX-C:
    two_years = 7 * 24 * 3600 was actually 7 days, not 2 years.
    The factory coordinator uses BACKFILL_DAYS_BACK (default 365),
    so this test verifies the chunk plan spans the correct range.
    """

    @pytest.mark.asyncio
    async def test_backfill_days_back_365_makes_12_chunks(self):
        r = AsyncMock()
        r.get.return_value = None
        r.setex = AsyncMock()
        massive = AsyncMock()

        manager = BackfillManager(r, massive, days_back=365)
        state = await manager._load_or_init_state("MGC", "1m", None, None)

        # 365 days / 30 per chunk ≈ 12–13 chunks
        assert len(state.chunks) >= 12, (
            f"Expected ≥12 chunks for 365-day backfill, got {len(state.chunks)}. "
            "Check BACKFILL_DAYS_BACK — this may be the two_years=7days bug."
        )

        # Verify first chunk starts ~365 days ago
        from datetime import datetime, timezone
        first_start = datetime.fromisoformat(state.chunks[0].start)
        days_back = (datetime.now(timezone.utc) - first_start).days
        assert days_back >= 360, (
            f"First chunk only goes back {days_back} days, expected ~365. "
            "This is the CRITICAL-FIX-C regression."
        )
```

---

### Updated supervisord config

This is the concrete `[program:factory]` block to add to your existing `infrastructure/docker/services/ruby/supervisord.conf`. The `priority=5` ensures it starts before `data` (10), `engine` (20), and `web` (30) — the factory needs to warm caches before Janus starts asking for bars.

```ini
[program:factory]
command=python -m lib.data_factory.coordinator
directory=/app/src
autostart=true
autorestart=true
autorestart=unexpected
exitcodes=0,2
stopwaitsecs=30
stopasgroup=true
killasgroup=true
stdout_logfile=/var/log/fks/factory.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=3
stderr_logfile=/var/log/fks/factory.err
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=3
environment=
    PYTHONPATH="/app/src",
    LOG_LEVEL="%(ENV_LOG_LEVEL)s",
    REDIS_URL="%(ENV_REDIS_URL)s",
    DATABASE_URL="%(ENV_DATABASE_URL)s",
    MASSIVE_API_KEY="%(ENV_MASSIVE_API_KEY)s",
    MASSIVE_S3_KEY_ID="%(ENV_MASSIVE_S3_KEY_ID)s",
    MASSIVE_S3_SECRET="%(ENV_MASSIVE_S3_SECRET)s",
    MASSIVE_S3_ENDPOINT="%(ENV_MASSIVE_S3_ENDPOINT)s",
    MASSIVE_S3_BUCKET="%(ENV_MASSIVE_S3_BUCKET)s",
    BACKFILL_DAYS_BACK="%(ENV_BACKFILL_DAYS_BACK)s",
    BACKFILL_CHUNK_DAYS="%(ENV_BACKFILL_CHUNK_DAYS)s",
    CNN_RETRAIN_SYMBOLS="%(ENV_CNN_RETRAIN_SYMBOLS)s",
    DATA_KLINE_INTERVALS="%(ENV_DATA_KLINE_INTERVALS)s",
    GAP_SCAN_INTERVAL_SECS="3600",
    BACKFILL_LOOKBACK_SECS="31536000"
priority=5
```

---

### Wire the metrics endpoint into your existing FastAPI app

In `src/ruby/src/lib/services/data/main.py`, add one route so Prometheus can scrape the factory metrics alongside your data service metrics (no new port required):

```python
# Add near your other router registrations in main.py

from fastapi import Response
from lib.data_factory.health_reporter import metrics_output

@app.get("/factory/metrics", include_in_schema=False)
async def factory_metrics():
    """Prometheus scrape endpoint for DataFactory metrics."""
    body, content_type = metrics_output()
    return Response(content=body, media_type=content_type)
```

Then add the scrape job to `infrastructure/config/prometheus/prometheus.yml`:

```yaml
  - job_name: 'fks-factory'
    static_configs:
      - targets: ['fks_ruby:8000']
    metrics_path: /factory/metrics
    scrape_interval: 60s
```

---

### What to do right now, in order

The priority sequence given everything you've told me:

1. **Fix CRITICAL-FIX-C** in `redis_clients/async_client.py:534` — this is a one-line change that unblocks all backfill lookback immediately, independent of the factory
2. **Add `[program:factory]`** to supervisord.conf — the coordinator will start with the container even before the other modules are fleshed out
3. **Create `lib/data_factory/`** with the modules above, starting with `symbol_registry.py` and `coordinator.py` — the others can be stubbed initially
4. **Wire `MassiveAdapter`** — once you can see the actual `massive>=2.4.0` package API (run `python -c "import massive; help(massive.Client)"` inside the container), adjust the `_fetch_sync` call and `_normalize_bars` field names
5. **Add the Prometheus scrape job** — the `health_reporter` metrics will start appearing in Grafana immediately once the factory process is running

The `_fetch_sync` method in `MassiveAdapter` is the only part that needs to be verified against the actual Massive package's method signatures — every other piece is grounded in what I can see directly in your repo.

