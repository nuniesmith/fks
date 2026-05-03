"""Unit tests for DataFactory core modules.

Covers:

BackfillManager
    - chunk plan covers the full requested date range
    - crash-resume: DONE chunks are skipped on reload
    - chunk is marked DONE on a successful fetch
    - chunk is marked FAILED (with error) when the provider raises
    - state is persisted to Redis after every chunk transition

GapScanner
    - _enqueue_fills pushes one job per gap to FILL_QUEUE_KEY
    - _enqueue_fills is a no-op when the gap list is empty

HealthReporter
    - cache age is derived from TTL (300 - remaining_ttl)
    - a missing cache key is reported as maximally stale (86400 s)
    - record_chunk_attempt / record_chunk_failure do not raise

Lookback regression (CRITICAL-FIX-C)
    - a 365-day lookback produces ≥12 chunks (≥1 per 30-day chunk)
    - the first chunk's start is approximately 365 days ago
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_factory.backfill_manager import (
    BackfillManager,
    BackfillState,
    Chunk,
    ChunkStatus,
    _dict_to_state,
    _state_to_dict,
)
from data_factory.gap_scanner import GapScanner, GapWindow
from data_factory.health_reporter import (
    record_chunk_attempt,
    record_chunk_failure,
    record_divergence,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _make_fake_redis(
    *,
    brpop_payload: tuple[str, str] | None = None,
    get_returns: str | None = None,
    ttl_returns: int = 200,
) -> AsyncMock:
    """Build a minimal async-Redis mock."""
    redis = AsyncMock()
    # BRPOP: first call returns payload, subsequent calls block (return None)
    if brpop_payload is not None:
        redis.brpop.side_effect = [brpop_payload, None, None, None, None]
    else:
        redis.brpop.return_value = None

    redis.get.return_value = get_returns
    redis.setex.return_value = True
    redis.set.return_value = True
    redis.lpush.return_value = 1
    redis.pipeline.return_value.__aenter__ = AsyncMock(
        return_value=MagicMock(
            setex=MagicMock(),
            set=MagicMock(),
            lpush=MagicMock(),
            execute=AsyncMock(return_value=[True]),
        )
    )
    redis.pipeline.return_value.__aexit__ = AsyncMock(return_value=False)
    redis.ttl.return_value = ttl_returns
    return redis


def _make_fake_engine() -> AsyncMock:
    """Build a minimal async SQLAlchemy engine mock."""
    engine = AsyncMock()
    conn = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    engine.connect.return_value = conn
    engine.begin.return_value = conn
    return engine


def _make_fake_registry(symbol: str = "MGC") -> AsyncMock:
    """Return an AssetRegistry mock with one enabled asset."""
    config = MagicMock()
    config.symbol = symbol
    config.providers = []
    config.news = MagicMock(enabled=True)
    config.window_targets = []

    registry = AsyncMock()
    registry.get.return_value = config
    registry.enabled_assets.return_value = [config]
    return registry


def _make_fake_router(bars: list | None = None) -> AsyncMock:
    """Return a ProviderRouter mock that returns a fixed bar list."""
    router = AsyncMock()
    router.fetch_bars.return_value = (bars or [], None)
    return router


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


class TestBackfillStateSerialization:
    """BackfillState serialises to dict and back without data loss."""

    def test_round_trip(self) -> None:
        state = BackfillState(
            symbol="MGC",
            interval="1m",
            chunks=[
                Chunk(
                    start="2024-01-01T00:00:00+00:00",
                    end="2024-01-31T00:00:00+00:00",
                    status=ChunkStatus.DONE.value,
                    attempts=1,
                    last_error=None,
                ),
                Chunk(
                    start="2024-01-31T00:00:00+00:00",
                    end="2024-03-01T00:00:00+00:00",
                    status=ChunkStatus.PENDING.value,
                    attempts=0,
                    last_error=None,
                ),
            ],
        )
        restored = _dict_to_state(_state_to_dict(state))

        assert restored.symbol == state.symbol
        assert restored.interval == state.interval
        assert len(restored.chunks) == 2
        assert restored.chunks[0].status == ChunkStatus.DONE.value
        assert restored.chunks[1].status == ChunkStatus.PENDING.value


# ---------------------------------------------------------------------------
# Chunk plan coverage
# ---------------------------------------------------------------------------


class TestBackfillChunkPlan:
    """BackfillManager._load_or_init_state builds a complete chunk plan."""

    @pytest.mark.asyncio
    async def test_chunk_plan_covers_full_range(self) -> None:
        """A 90-day range with 30-day chunks should produce exactly 3 chunks."""
        redis = _make_fake_redis(get_returns=None)  # no persisted state
        engine = _make_fake_engine()
        router = _make_fake_router()
        registry = _make_fake_registry()

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=90,
        )

        now = _utcnow()
        start = now - timedelta(days=90)
        end = now

        state = await manager._load_or_init_state(
            "MGC",
            "1m",
            start=start.isoformat(),
            end=end.isoformat(),
        )

        assert len(state.chunks) == 3
        # First chunk starts at start
        first_start = datetime.fromisoformat(state.chunks[0].start)
        assert abs((first_start - start).total_seconds()) < 60
        # Last chunk ends at or near end
        last_end = datetime.fromisoformat(state.chunks[-1].end)
        assert abs((last_end - end).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_all_chunks_initially_pending(self) -> None:
        """Fresh state: every chunk should start as PENDING."""
        redis = _make_fake_redis(get_returns=None)
        engine = _make_fake_engine()
        router = _make_fake_router()
        registry = _make_fake_registry()

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=60,
        )

        now = _utcnow()
        state = await manager._load_or_init_state(
            "MGC",
            "5m",
            start=(now - timedelta(days=60)).isoformat(),
            end=now.isoformat(),
        )

        for chunk in state.chunks:
            assert chunk.status == ChunkStatus.PENDING.value
            assert chunk.attempts == 0
            assert chunk.last_error is None

    @pytest.mark.asyncio
    async def test_chunk_boundaries_are_contiguous(self) -> None:
        """Adjacent chunks must share a boundary (no gaps, no overlaps)."""
        redis = _make_fake_redis(get_returns=None)
        engine = _make_fake_engine()
        router = _make_fake_router()
        registry = _make_fake_registry()

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=90,
        )

        now = _utcnow()
        state = await manager._load_or_init_state(
            "MGC",
            "1m",
            start=(now - timedelta(days=90)).isoformat(),
            end=now.isoformat(),
        )

        for i in range(len(state.chunks) - 1):
            end_i = datetime.fromisoformat(state.chunks[i].end)
            start_next = datetime.fromisoformat(state.chunks[i + 1].start)
            assert end_i == start_next, f"Chunk {i} ends at {end_i} but chunk {i + 1} starts at {start_next}"


# ---------------------------------------------------------------------------
# Crash-resume (DONE chunks are skipped)
# ---------------------------------------------------------------------------


class TestBackfillResume:
    """BackfillManager resumes correctly when persisted state exists."""

    @pytest.mark.asyncio
    async def test_resumes_from_persisted_state(self) -> None:
        """When Redis holds a BackfillState, it is loaded and DONE chunks are skipped."""
        existing_state = BackfillState(
            symbol="MES",
            interval="1m",
            chunks=[
                Chunk(
                    start="2024-01-01T00:00:00+00:00",
                    end="2024-01-31T00:00:00+00:00",
                    status=ChunkStatus.DONE.value,
                    attempts=1,
                ),
                Chunk(
                    start="2024-01-31T00:00:00+00:00",
                    end="2024-03-01T00:00:00+00:00",
                    status=ChunkStatus.PENDING.value,
                    attempts=0,
                ),
            ],
        )
        serialised = json.dumps(_state_to_dict(existing_state))
        redis = _make_fake_redis(get_returns=serialised)
        engine = _make_fake_engine()
        router = _make_fake_router()
        registry = _make_fake_registry("MES")

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
        )

        loaded = await manager._load_or_init_state("MES", "1m", start=None, end=None)

        assert len(loaded.chunks) == 2
        assert loaded.chunks[0].status == ChunkStatus.DONE.value
        # Should not have built fresh chunks (still 2 chunks from persisted state)
        assert loaded.chunks[1].status == ChunkStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_done_chunks_are_not_actionable(self) -> None:
        """_process_job skips DONE chunks so they are never re-fetched."""
        done_state = BackfillState(
            symbol="MNQ",
            interval="5m",
            chunks=[
                Chunk(
                    start="2024-01-01T00:00:00+00:00",
                    end="2024-01-31T00:00:00+00:00",
                    status=ChunkStatus.DONE.value,
                    attempts=1,
                ),
            ],
        )
        serialised = json.dumps(_state_to_dict(done_state))
        redis = _make_fake_redis(get_returns=serialised)
        engine = _make_fake_engine()
        router = _make_fake_router()
        registry = _make_fake_registry("MNQ")

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
        )

        await manager._process_job("MNQ", "5m")

        # Router should not have been called — all chunks were already DONE
        router.fetch_bars.assert_not_called()


# ---------------------------------------------------------------------------
# Chunk status transitions
# ---------------------------------------------------------------------------


class TestBackfillChunkStatus:
    """Chunk status transitions on success and failure."""

    @pytest.mark.asyncio
    async def test_chunk_marked_done_on_success(self) -> None:
        """A successful fetch transitions the chunk status to DONE."""
        from data_factory.providers.base import OHLCVBar

        fake_bar = OHLCVBar(
            symbol="MGC",
            interval="1m",
            bar_time=_utcnow(),
            open=2000.0,
            high=2010.0,
            low=1990.0,
            close=2005.0,
            volume=100.0,
            source="yfinance",
        )
        redis = _make_fake_redis(get_returns=None)
        engine = _make_fake_engine()
        router = _make_fake_router(bars=[fake_bar])
        registry = _make_fake_registry()

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=30,
        )

        now = _utcnow()
        state = BackfillState(
            symbol="MGC",
            interval="1m",
            chunks=[
                Chunk(
                    start=(now - timedelta(days=30)).isoformat(),
                    end=now.isoformat(),
                    status=ChunkStatus.PENDING.value,
                    attempts=0,
                )
            ],
        )
        config = registry.get.return_value

        with patch.object(manager, "_write_to_postgres", new_callable=AsyncMock):
            with patch.object(manager, "_save_state", new_callable=AsyncMock):
                await manager._fetch_chunk(state, state.chunks[0], config)

        assert state.chunks[0].status == ChunkStatus.DONE.value
        assert state.chunks[0].last_error is None
        assert state.chunks[0].attempts == 1

    @pytest.mark.asyncio
    async def test_chunk_marked_failed_on_error(self) -> None:
        """A provider exception transitions the chunk status to FAILED."""
        router = _make_fake_router()
        router.fetch_bars.side_effect = ConnectionError("Upstream unavailable")

        redis = _make_fake_redis(get_returns=None)
        engine = _make_fake_engine()
        registry = _make_fake_registry()

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=30,
        )

        now = _utcnow()
        state = BackfillState(
            symbol="MGC",
            interval="1m",
            chunks=[
                Chunk(
                    start=(now - timedelta(days=30)).isoformat(),
                    end=now.isoformat(),
                    status=ChunkStatus.PENDING.value,
                    attempts=0,
                )
            ],
        )
        config = registry.get.return_value

        with patch.object(manager, "_save_state", new_callable=AsyncMock):
            await manager._fetch_chunk(state, state.chunks[0], config)

        assert state.chunks[0].status == ChunkStatus.FAILED.value
        assert state.chunks[0].last_error is not None
        assert "ConnectionError" in state.chunks[0].last_error
        assert state.chunks[0].attempts == 1

    @pytest.mark.asyncio
    async def test_state_persisted_after_each_transition(self) -> None:
        """_save_state is called at least twice per chunk (RUNNING → final)."""
        from data_factory.providers.base import OHLCVBar

        fake_bar = OHLCVBar(
            symbol="MGC",
            interval="1m",
            bar_time=_utcnow(),
            open=2000.0,
            high=2010.0,
            low=1990.0,
            close=2005.0,
            volume=50.0,
            source="massive",
        )
        router = _make_fake_router(bars=[fake_bar])
        redis = _make_fake_redis(get_returns=None)
        engine = _make_fake_engine()
        registry = _make_fake_registry()

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=30,
        )

        now = _utcnow()
        state = BackfillState(
            symbol="MGC",
            interval="1m",
            chunks=[
                Chunk(
                    start=(now - timedelta(days=30)).isoformat(),
                    end=now.isoformat(),
                )
            ],
        )
        config = registry.get.return_value
        save_calls: list[BackfillState] = []

        async def _capture_save(s: BackfillState) -> None:
            save_calls.append(s)

        with patch.object(manager, "_save_state", side_effect=_capture_save):
            with patch.object(manager, "_write_to_postgres", new_callable=AsyncMock):
                await manager._fetch_chunk(state, state.chunks[0], config)

        # Must persist at least RUNNING (before fetch) and DONE/FAILED (after)
        assert len(save_calls) >= 2


# ---------------------------------------------------------------------------
# Lookback regression — CRITICAL-FIX-C
# ---------------------------------------------------------------------------


class TestBackfillLookbackWindow:
    """Regression guard for the 365-day lookback window bug (CRITICAL-FIX-C).

    Verifies that a 365-day backfill produces enough chunks to cover the
    full year and that the first chunk starts approximately 365 days ago.
    """

    @pytest.mark.asyncio
    async def test_365_day_lookback_produces_enough_chunks(self) -> None:
        """365 days / 30-day chunks → at least 12 chunks."""
        redis = _make_fake_redis(get_returns=None)
        engine = _make_fake_engine()
        router = _make_fake_router()
        registry = _make_fake_registry()

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=365,
        )

        now = _utcnow()
        state = await manager._load_or_init_state(
            "MGC",
            "1m",
            start=(now - timedelta(days=365)).isoformat(),
            end=now.isoformat(),
        )

        # 365 / 30 = 12.17 → at least 12 chunks, at most 13
        assert len(state.chunks) >= 12, f"Expected ≥12 chunks for 365-day backfill, got {len(state.chunks)}"

    @pytest.mark.asyncio
    async def test_first_chunk_starts_approximately_365_days_ago(self) -> None:
        """The first chunk must start close to 365 days before now."""
        redis = _make_fake_redis(get_returns=None)
        engine = _make_fake_engine()
        router = _make_fake_router()
        registry = _make_fake_registry()

        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=365,
        )

        now = _utcnow()
        expected_start = now - timedelta(days=365)

        state = await manager._load_or_init_state(
            "MGC",
            "1m",
            start=expected_start.isoformat(),
            end=now.isoformat(),
        )

        first_start = datetime.fromisoformat(state.chunks[0].start)
        if first_start.tzinfo is None:
            first_start = first_start.replace(tzinfo=UTC)

        delta_days = abs((first_start - expected_start).total_seconds()) / 86400
        assert delta_days < 1, (
            f"First chunk start {first_start} is {delta_days:.2f} days away from expected {expected_start}"
        )

    @pytest.mark.asyncio
    async def test_default_days_back_used_when_no_start_given(self) -> None:
        """When start=None, the manager uses days_back to compute the start date."""
        redis = _make_fake_redis(get_returns=None)
        engine = _make_fake_engine()
        router = _make_fake_router()
        registry = _make_fake_registry()

        days_back = 365
        manager = BackfillManager(
            redis=redis,
            provider_router=router,
            db_engine=engine,
            registry=registry,
            days_back=days_back,
        )

        before_call = _utcnow()
        state = await manager._load_or_init_state("MGC", "1m", start=None, end=None)
        after_call = _utcnow()

        first_start = datetime.fromisoformat(state.chunks[0].start)
        if first_start.tzinfo is None:
            first_start = first_start.replace(tzinfo=UTC)

        expected_earliest = before_call - timedelta(days=days_back)
        expected_latest = after_call - timedelta(days=days_back)

        assert expected_earliest <= first_start <= expected_latest + timedelta(seconds=5)


# ---------------------------------------------------------------------------
# GapScanner
# ---------------------------------------------------------------------------


class TestGapScanner:
    """GapScanner enqueues fill jobs for detected gaps."""

    @pytest.mark.asyncio
    async def test_enqueue_fills_pushes_one_job_per_gap(self) -> None:
        """_enqueue_fills should push one Redis job per GapWindow."""
        pushed: list[str] = []

        pipe_mock = MagicMock()
        pipe_mock.lpush = MagicMock(side_effect=lambda key, val: pushed.append(val))
        pipe_mock.execute = AsyncMock(return_value=[1, 1])
        pipe_mock.__aenter__ = AsyncMock(return_value=pipe_mock)
        pipe_mock.__aexit__ = AsyncMock(return_value=False)

        redis = AsyncMock()
        # pipeline() is called synchronously in gap_scanner (not awaited)
        redis.pipeline = MagicMock(return_value=pipe_mock)
        engine = _make_fake_engine()

        scanner = GapScanner(redis=redis, db_engine=engine)

        gaps = [
            GapWindow(
                symbol="MGC",
                interval="1m",
                start="2024-06-01T09:00:00+00:00",
                end="2024-06-01T10:00:00+00:00",
                missing_bars=60,
            ),
            GapWindow(
                symbol="MES",
                interval="5m",
                start="2024-06-02T14:00:00+00:00",
                end="2024-06-02T15:00:00+00:00",
                missing_bars=12,
            ),
        ]

        await scanner._enqueue_fills(gaps)

        assert len(pushed) == 2

        job_0 = json.loads(pushed[0])
        assert job_0["symbol"] == "MGC"
        assert job_0["interval"] == "1m"
        assert "gap_scanner" in job_0["reason"]

        job_1 = json.loads(pushed[1])
        assert job_1["symbol"] == "MES"
        assert job_1["interval"] == "5m"

    @pytest.mark.asyncio
    async def test_enqueue_fills_skips_when_no_gaps(self) -> None:
        """_enqueue_fills should be a no-op for an empty gap list."""
        redis = AsyncMock()
        engine = _make_fake_engine()

        scanner = GapScanner(redis=redis, db_engine=engine)

        await scanner._enqueue_fills([])

        # pipeline should not have been touched
        redis.pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_gaps_writes_per_symbol_interval_keys(self) -> None:
        """_publish_gaps should setex one key per unique symbol/interval pair."""
        set_keys: list[str] = []

        pipe_mock = MagicMock()
        pipe_mock.setex = MagicMock(side_effect=lambda k, ttl, v: set_keys.append(k))
        pipe_mock.set = MagicMock()
        pipe_mock.execute = AsyncMock(return_value=[True])
        pipe_mock.__aenter__ = AsyncMock(return_value=pipe_mock)
        pipe_mock.__aexit__ = AsyncMock(return_value=False)

        redis = AsyncMock()
        # pipeline() is called synchronously in gap_scanner (not awaited)
        redis.pipeline = MagicMock(return_value=pipe_mock)
        engine = _make_fake_engine()

        scanner = GapScanner(redis=redis, db_engine=engine)

        gaps = [
            GapWindow("MGC", "1m", "2024-01-01T09:00:00+00:00", "2024-01-01T10:00:00+00:00", 60),
            GapWindow("MGC", "5m", "2024-01-01T09:00:00+00:00", "2024-01-01T10:00:00+00:00", 12),
            GapWindow("MES", "1m", "2024-01-01T09:00:00+00:00", "2024-01-01T10:00:00+00:00", 60),
        ]

        await scanner._publish_gaps(gaps)

        # Expect three distinct keys — one per (symbol, interval) pair
        gap_keys = [k for k in set_keys if k.startswith("ruby:gaps:")]
        assert len(gap_keys) == 3
        assert "ruby:gaps:MGC:1m" in gap_keys
        assert "ruby:gaps:MGC:5m" in gap_keys
        assert "ruby:gaps:MES:1m" in gap_keys


# ---------------------------------------------------------------------------
# HealthReporter
# ---------------------------------------------------------------------------


class TestHealthReporter:
    """HealthReporter metrics helpers behave correctly."""

    def test_record_chunk_attempt_does_not_raise(self) -> None:
        """record_chunk_attempt must not raise for any symbol/interval."""
        record_chunk_attempt("MGC", "1m")
        record_chunk_attempt("BTC/USD", "5m")
        record_chunk_attempt("unknown_symbol", "1d")

    def test_record_chunk_failure_does_not_raise(self) -> None:
        """record_chunk_failure must not raise for any symbol/interval."""
        record_chunk_failure("MGC", "1m")
        record_chunk_failure("MES", "5m")

    def test_record_divergence_does_not_raise(self) -> None:
        """record_divergence must not raise for any symbol."""
        record_divergence("MGC", diverged=True)
        record_divergence("MGC", diverged=False)

    @pytest.mark.asyncio
    async def test_cache_age_derived_from_ttl(self) -> None:
        """Cache age should be 300 - remaining_ttl (e.g. ttl=200 → age=100)."""
        from data_factory.health_reporter import HealthReporter, _cache_age

        redis = _make_fake_redis(ttl_returns=200)
        reporter = HealthReporter(redis=redis)

        await reporter._update_cache_age_metrics(["MGC"])

        # Gauge should reflect 300 - 200 = 100 s
        gauge_value = _cache_age.labels(symbol="MGC", interval="1m")._value.get()
        assert gauge_value == 100.0

    @pytest.mark.asyncio
    async def test_missing_cache_key_reports_max_stale(self) -> None:
        """A missing cache key (ttl=-2) should be reported as 86400 s stale."""
        from data_factory.health_reporter import HealthReporter, _cache_age

        redis = _make_fake_redis(ttl_returns=-2)
        reporter = HealthReporter(redis=redis)

        await reporter._update_cache_age_metrics(["MES"])

        gauge_value = _cache_age.labels(symbol="MES", interval="1m")._value.get()
        assert gauge_value == 86400.0

    @pytest.mark.asyncio
    async def test_scan_age_set_from_redis_timestamp(self) -> None:
        """Scan age should equal seconds elapsed since ruby:gaps:last_scan."""
        from data_factory.health_reporter import HealthReporter, _scan_age

        # Simulate a last scan 5 minutes ago
        five_min_ago = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()

        redis = AsyncMock()
        redis.get.return_value = five_min_ago
        reporter = HealthReporter(redis=redis)

        await reporter._update_scan_age()

        age = _scan_age._value.get()
        # Should be approximately 300 s (±30 s tolerance)
        assert 270 <= age <= 330, f"Expected ~300 s scan age, got {age}"

    @pytest.mark.asyncio
    async def test_missing_scan_timestamp_reports_max_stale(self) -> None:
        """When ruby:gaps:last_scan is absent, scan age should be 86400 s."""
        from data_factory.health_reporter import HealthReporter, _scan_age

        redis = AsyncMock()
        redis.get.return_value = None
        reporter = HealthReporter(redis=redis)

        await reporter._update_scan_age()

        age = _scan_age._value.get()
        assert age == 86400.0


# ---------------------------------------------------------------------------
# Write-to-postgres schema guard
# ---------------------------------------------------------------------------


class TestWriteToPostgresSchema:
    """Ensure BackfillManager uses the correct historical_bars schema."""

    @pytest.mark.asyncio
    async def test_insert_uses_historical_bars_table(self) -> None:
        """The INSERT SQL must reference historical_bars, not bars."""
        import inspect
        import re

        from data_factory.backfill_manager import BackfillManager

        source = inspect.getsource(BackfillManager._write_to_postgres)
        assert "historical_bars" in source, "_write_to_postgres must INSERT into 'historical_bars', not 'bars'"
        # Extract the SQL string literal (inside triple-quotes) and verify it
        # uses historical_bars as the table name, not a bare 'bars' reference.
        sql_strings = re.findall(r'"""\s*(.*?)\s*"""', source, re.DOTALL)
        assert sql_strings, "Expected a triple-quoted SQL string in _write_to_postgres"
        for sql in sql_strings:
            after_strip = sql.replace("historical_bars", "")
            assert "INTO bars" not in after_strip, (
                f"Found bare 'INTO bars' table reference in SQL — must be 'historical_bars': {sql[:200]}"
            )

    @pytest.mark.asyncio
    async def test_insert_uses_timestamp_column(self) -> None:
        """The SQL bind parameter must be ':timestamp', not ':bar_time'.

        Note: ``bar.bar_time`` WILL appear in the source — that is the correct
        OHLCVBar attribute name.  What must NOT appear is ``:bar_time`` as a
        named bind parameter (which would indicate the wrong column name was
        passed to the DB).
        """
        import inspect

        from data_factory.backfill_manager import BackfillManager

        source = inspect.getsource(BackfillManager._write_to_postgres)
        # The bind parameter key in the params dict must be "timestamp"
        assert '"timestamp"' in source or "'timestamp'" in source, (
            "_write_to_postgres must bind the timestamp column via 'timestamp' key"
        )
        # The SQL column bind placeholder must be :timestamp
        assert ":timestamp" in source, "SQL must use :timestamp placeholder, not :bar_time"
        assert ":bar_time" not in source, (
            "Found ':bar_time' bind parameter — the DB column is 'timestamp', not 'bar_time'"
        )

    @pytest.mark.asyncio
    async def test_insert_excludes_source_column(self) -> None:
        """The INSERT SQL must not reference the 'source' column (doesn't exist)."""
        import inspect

        from data_factory.backfill_manager import BackfillManager

        source = inspect.getsource(BackfillManager._write_to_postgres)
        # ":source" as a bind parameter would mean we're trying to insert into
        # a column that does not exist in historical_bars.
        assert ":source" not in source, (
            "Found ':source' bind parameter in _write_to_postgres — 'source' column does not exist in historical_bars"
        )
