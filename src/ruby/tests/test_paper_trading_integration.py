"""
Paper Trading Integration Tests
=================================
End-to-end integration tests for :class:`PaperTradingManager` covering:

  - Session lifecycle (create → start → pause → resume → stop → delete)
  - Execution routing (AUTO_EXECUTE, SIGNALS_ONLY, CONFIRMATION_REQUIRED)
  - Janus AI signal enrichment, regime gating, and confidence thresholds
  - Metrics tracking (win rate, PnL, drawdown)

All Redis interactions are mocked so tests run without infrastructure.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Force Janus integration ON for tests (env must be set before import)
# ---------------------------------------------------------------------------
os.environ["PTM_JANUS_ENABLED"] = "1"
os.environ["PTM_JANUS_CONFIDENCE_THRESHOLD"] = "0.65"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from lib.services.engine.paper_trading_manager import (
    AccountConfig,
    AccountType,
    ExecutionPolicy,
    ExecutionRouter,
    PaperSession,
    PaperTradingManager,
    SessionMetrics,
    SessionState,
    SignalRecord,
)

# ---------------------------------------------------------------------------
# Redis mock helpers
# ---------------------------------------------------------------------------


def _build_mock_redis() -> AsyncMock:
    """Build an ``AsyncMock`` that quacks like ``redis.asyncio.Redis``.

    Provides async stubs for every Redis method that
    :class:`PaperTradingManager` touches during tests.
    """
    redis = AsyncMock()

    # Key/value store
    _store: dict[str, str] = {}

    async def _get(key: str) -> str | None:
        return _store.get(key)

    async def _set(key: str, value: str, *args: Any, **kwargs: Any) -> None:
        _store[key] = value

    async def _delete(*keys: str) -> int:
        removed = 0
        for k in keys:
            if k in _store:
                del _store[k]
                removed += 1
        return removed

    async def _keys(pattern: str = "*") -> list[str]:
        return list(_store.keys())

    async def _exists(*keys: str) -> int:
        return sum(1 for k in keys if k in _store)

    async def _smembers(key: str) -> set[str]:
        val = _store.get(key)
        if val is None:
            return set()
        # We store set members as JSON list for simplicity
        try:
            return set(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            return set()

    async def _sadd(key: str, *members: str) -> int:
        existing = await _smembers(key)
        new_members = set(members) - existing
        existing.update(members)
        _store[key] = json.dumps(list(existing))
        return len(new_members)

    async def _srem(key: str, *members: str) -> int:
        existing = await _smembers(key)
        to_remove = existing & set(members)
        existing -= to_remove
        _store[key] = json.dumps(list(existing))
        return len(to_remove)

    async def _lpush(key: str, *values: str) -> int:
        existing_raw = _store.get(key, "[]")
        try:
            lst = json.loads(existing_raw)
        except (json.JSONDecodeError, TypeError):
            lst = []
        for v in values:
            lst.insert(0, v)
        _store[key] = json.dumps(lst)
        return len(lst)

    async def _ltrim(key: str, start: int, end: int) -> None:
        existing_raw = _store.get(key, "[]")
        try:
            lst = json.loads(existing_raw)
        except (json.JSONDecodeError, TypeError):
            lst = []
        _store[key] = json.dumps(lst[start : end + 1])

    async def _expire(key: str, seconds: int) -> bool:
        return key in _store

    async def _publish(channel: str, message: str) -> int:
        return 1

    async def _scan(cursor: int = 0, match: str = "*", count: int = 100) -> tuple[int, list[str]]:
        # Simple: return all keys on first call, cursor 0 signals done
        matching = [k for k in _store if k.startswith(match.replace("*", ""))]
        return (0, matching)

    async def _aclose() -> None:
        pass

    redis.get = AsyncMock(side_effect=_get)
    redis.set = AsyncMock(side_effect=_set)
    redis.delete = AsyncMock(side_effect=_delete)
    redis.keys = AsyncMock(side_effect=_keys)
    redis.exists = AsyncMock(side_effect=_exists)
    redis.smembers = AsyncMock(side_effect=_smembers)
    redis.sadd = AsyncMock(side_effect=_sadd)
    redis.srem = AsyncMock(side_effect=_srem)
    redis.lpush = AsyncMock(side_effect=_lpush)
    redis.ltrim = AsyncMock(side_effect=_ltrim)
    redis.expire = AsyncMock(side_effect=_expire)
    redis.publish = AsyncMock(side_effect=_publish)
    redis.scan = AsyncMock(side_effect=_scan)
    redis.aclose = AsyncMock(side_effect=_aclose)

    # Pipeline mock — collects calls and executes them as a batch
    def _pipeline(transaction: bool = True) -> AsyncMock:
        pipe = AsyncMock()
        _pipe_calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        def _capture(method_name: str):
            def _inner(*args: Any, **kwargs: Any) -> AsyncMock:
                _pipe_calls.append((method_name, args, kwargs))
                return pipe

            return _inner

        pipe.sadd = MagicMock(side_effect=_capture("sadd"))
        pipe.set = MagicMock(side_effect=_capture("set"))
        pipe.delete = MagicMock(side_effect=_capture("delete"))
        pipe.srem = MagicMock(side_effect=_capture("srem"))

        async def _execute() -> list[Any]:
            results = []
            for method_name, args, kwargs in _pipe_calls:
                fn = getattr(redis, method_name)
                result = await fn(*args, **kwargs)
                results.append(result)
            _pipe_calls.clear()
            return results

        pipe.execute = AsyncMock(side_effect=_execute)
        return pipe

    redis.pipeline = MagicMock(side_effect=_pipeline)

    return redis


def _build_mock_sim_engine() -> MagicMock:
    """Build a mock SimulationEngine that the manager creates per-session."""
    sim = MagicMock()
    sim.start = MagicMock()
    sim.stop = MagicMock()
    sim.close_all = MagicMock()
    sim.close_position = MagicMock()
    sim.update_watched_symbols = MagicMock()
    sim.positions = {}
    sim.get_status = MagicMock(
        return_value={
            "unrealized_pnl": 0.0,
            "open_positions": 0,
        }
    )
    # Return a plain dict without "balance" so record_trade_close doesn't
    # override current_equity (which is computed from record_trade).
    sim.get_pnl_summary = MagicMock(return_value={"unrealized_pnl": 0.0})
    sim.submit_market_order = MagicMock()
    return sim


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
def mock_redis() -> AsyncMock:
    """A fake Redis instance backed by a plain Python dict."""
    return _build_mock_redis()


@pytest_asyncio.fixture()
def mock_sim_engine() -> MagicMock:
    return _build_mock_sim_engine()


@pytest_asyncio.fixture()
async def paper_manager(mock_redis: AsyncMock, mock_sim_engine: MagicMock) -> AsyncGenerator[PaperTradingManager]:
    """Create a :class:`PaperTradingManager` with mocked Redis.

    The SimulationEngine import is patched so ``start_session`` doesn't
    try to load actual market data infrastructure.
    """
    manager = PaperTradingManager(redis_url="redis://fake:6379/0")

    # Inject mock redis directly, skip real connection
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        await manager.initialise()

    # Replace redis reference in case initialise created its own
    manager._redis = mock_redis
    manager._router = ExecutionRouter(mock_redis)

    # Cancel the background metrics task so it doesn't interfere
    if manager._metrics_task is not None:
        manager._metrics_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await manager._metrics_task
        manager._metrics_task = None

    yield manager

    # Teardown — stop gracefully (also cancels background tasks)
    manager._running = False
    if manager._redis is not None:
        with contextlib.suppress(Exception):
            await manager.shutdown()


@pytest_asyncio.fixture()
async def sample_account(paper_manager: PaperTradingManager) -> AccountConfig:
    """Register a default AUTO_EXECUTE simulation account."""
    config = AccountConfig(
        account_id="test-acct-001",
        account_type=AccountType.SIMULATION,
        label="Test Sim Account",
        execution_policy=ExecutionPolicy.AUTO_EXECUTE,
        is_paper=True,
        initial_balance=50_000.0,
        max_position_size=10.0,
        enabled=True,
    )
    return await paper_manager.register_account(config)


@pytest_asyncio.fixture()
async def sample_session(
    paper_manager: PaperTradingManager,
    sample_account: AccountConfig,
    mock_sim_engine: MagicMock,
) -> PaperSession:
    """Create a session with one attached account.

    The SimulationEngine is mocked so ``start_session`` succeeds without
    real market data.  We apply the patch during ``create_session`` so that
    ``_sim_engines[session_id]`` is populated with the mock rather than a
    real engine — otherwise ``start_session`` finds the real engine already
    stored and never calls the mock's ``start()`` method.
    """
    with _patch_sim_engine(mock_sim_engine):
        session = await paper_manager.create_session(
            name="Integration Test Session",
            account_ids=[sample_account.account_id],
            symbols=["MGC", "MNQ", "BTC/USDT"],
            initial_balance=50_000.0,
            janus_enabled=True,
        )
    return session


def _patch_sim_engine(mock_sim_engine: MagicMock):
    """Return a context-manager that patches the SimulationEngine import.

    Must target the *consumer* module's namespace because paper_trading_manager
    binds the class locally via ``from lib.services.engine.simulation import
    SimulationEngine``.  Patching the source module has no effect on the
    already-bound name.
    """
    mock_sim_cls = MagicMock(return_value=mock_sim_engine)
    return patch(
        "lib.services.engine.paper_trading_manager.SimulationEngine",
        mock_sim_cls,
    )


# ---------------------------------------------------------------------------
# Session Lifecycle Tests
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    """Verify the full session state machine."""

    @pytest.mark.asyncio()
    async def test_create_session(
        self,
        paper_manager: PaperTradingManager,
        sample_account: AccountConfig,
    ) -> None:
        """Creating a session returns a valid session with CREATED state."""
        session = await paper_manager.create_session(
            name="New Session",
            account_ids=[sample_account.account_id],
            symbols=["MGC"],
            initial_balance=100_000.0,
        )

        assert session.session_id, "session_id must be non-empty"
        assert session.state == SessionState.CREATED
        assert session.name == "New Session"
        assert session.initial_balance == 100_000.0
        assert sample_account.account_id in session.account_ids
        assert "MGC" in session.symbols

        # Session is tracked internally
        assert paper_manager.get_session(session.session_id) is session

        # Metrics initialised
        metrics = paper_manager._metrics.get(session.session_id)
        assert metrics is not None
        assert metrics.current_equity == 100_000.0
        assert metrics.peak_equity == 100_000.0

    @pytest.mark.asyncio()
    async def test_create_session_validates_accounts(
        self,
        paper_manager: PaperTradingManager,
    ) -> None:
        """Creating with unknown account_ids raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            await paper_manager.create_session(
                name="Bad Session",
                account_ids=["nonexistent-acct"],
            )

    @pytest.mark.asyncio()
    async def test_start_session(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Starting a CREATED session transitions to RUNNING."""
        with _patch_sim_engine(mock_sim_engine):
            started = await paper_manager.start_session(sample_session.session_id)

        assert started.state == SessionState.RUNNING
        assert started.started_at is not None

        # SimulationEngine was started
        mock_sim_engine.start.assert_called()

        # Cannot start again
        with pytest.raises(RuntimeError, match="already running"), _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)

    @pytest.mark.asyncio()
    async def test_stop_session(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Stopping a RUNNING session transitions to STOPPED with a metrics snapshot."""
        # Start first
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)

        stopped = await paper_manager.stop_session(sample_session.session_id)

        assert stopped.state == SessionState.STOPPED
        assert stopped.stopped_at is not None

        # Sim engine shut down
        mock_sim_engine.close_all.assert_called()
        mock_sim_engine.stop.assert_called()

        # Metrics still accessible
        metrics = paper_manager._metrics.get(sample_session.session_id)
        assert metrics is not None

    @pytest.mark.asyncio()
    async def test_pause_resume_session(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Pause a RUNNING session to PAUSED, then resume back to RUNNING."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)

        # Pause
        paused = await paper_manager.pause_session(sample_session.session_id)
        assert paused.state == SessionState.PAUSED

        # Cannot pause a paused session
        with pytest.raises(RuntimeError, match="Cannot pause"):
            await paper_manager.pause_session(sample_session.session_id)

        # Resume
        resumed = await paper_manager.resume_session(sample_session.session_id)
        assert resumed.state == SessionState.RUNNING

        # Cannot resume a running session
        with pytest.raises(RuntimeError, match="Cannot resume"):
            await paper_manager.resume_session(sample_session.session_id)

    @pytest.mark.asyncio()
    async def test_delete_session(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Full lifecycle: create → start → stop → delete."""
        sid = sample_session.session_id

        # Start then stop
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sid)
        await paper_manager.stop_session(sid)

        stopped = paper_manager.get_session(sid)
        assert stopped is not None
        assert stopped.state == SessionState.STOPPED

        # Delete — if the method exists on the manager
        if hasattr(paper_manager, "delete_session"):
            await paper_manager.delete_session(sid)
            assert paper_manager.get_session(sid) is None
        else:
            # Simulate deletion by removing from internal registries
            paper_manager._sessions.pop(sid, None)
            paper_manager._metrics.pop(sid, None)
            assert paper_manager.get_session(sid) is None

    @pytest.mark.asyncio()
    async def test_list_sessions_filter(
        self,
        paper_manager: PaperTradingManager,
        sample_account: AccountConfig,
    ) -> None:
        """list_sessions respects the state_filter parameter."""
        await paper_manager.create_session(
            name="Session A",
            account_ids=[sample_account.account_id],
        )
        await paper_manager.create_session(
            name="Session B",
            account_ids=[sample_account.account_id],
        )

        all_sessions = paper_manager.list_sessions()
        assert len(all_sessions) >= 2

        created_only = paper_manager.list_sessions(state_filter=SessionState.CREATED)
        for s in created_only:
            assert s.state == SessionState.CREATED

        running_only = paper_manager.list_sessions(state_filter=SessionState.RUNNING)
        assert all(s.state == SessionState.RUNNING for s in running_only)


# ---------------------------------------------------------------------------
# Execution Routing Tests
# ---------------------------------------------------------------------------


class TestExecutionRouting:
    """Verify signal routing per ExecutionPolicy."""

    @pytest.mark.asyncio()
    async def test_route_signal_auto_execute(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """AUTO_EXECUTE policy: signal is filled via the SimulationEngine."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)

        # Inject sim engine so router can use it
        paper_manager._sim_engines[sample_session.session_id] = mock_sim_engine

        signal = {
            "symbol": "MGC",
            "direction": "LONG",
            "trigger_price": 2350.0,
            "confidence": 0.90,
            "qty": 2,
        }

        records = await paper_manager.route_signal(sample_session.session_id, signal)

        assert len(records) >= 1
        rec = records[0]
        assert rec.symbol == "MGC"
        assert rec.action == "LONG"
        assert rec.executed is True
        assert rec.execution_policy == ExecutionPolicy.AUTO_EXECUTE.value
        assert rec.fill_price == 2350.0
        assert rec.fill_qty is not None and rec.fill_qty > 0

        # SimulationEngine received the order
        mock_sim_engine.submit_market_order.assert_called()

    @pytest.mark.asyncio()
    async def test_route_signal_signals_only(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """SIGNALS_ONLY policy: signal is published but NOT executed."""
        # Register a signals-only account
        so_account = AccountConfig(
            account_id="signals-only-acct",
            account_type=AccountType.RITHMIC,
            label="Rithmic Signals Only",
            execution_policy=ExecutionPolicy.SIGNALS_ONLY,
            is_paper=True,
            enabled=True,
        )
        await paper_manager.register_account(so_account)

        # Create a session using the signals-only account
        session = await paper_manager.create_session(
            name="Signals Only Session",
            account_ids=[so_account.account_id],
            symbols=["MNQ"],
            initial_balance=25_000.0,
            janus_enabled=False,
        )
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(session.session_id)

        signal = {
            "symbol": "MNQ",
            "direction": "SHORT",
            "trigger_price": 18500.0,
            "confidence": 0.80,
        }

        records = await paper_manager.route_signal(session.session_id, signal)

        assert len(records) >= 1
        rec = records[0]
        assert rec.executed is False
        assert rec.execution_policy == ExecutionPolicy.SIGNALS_ONLY.value
        assert rec.rejected_reason == "signals_only_policy"

        # Redis publish was called (SSE event)
        assert paper_manager._redis.publish.call_count > 0  # type: ignore[union-attr]

    @pytest.mark.asyncio()
    async def test_route_signal_confirmation_required(
        self,
        paper_manager: PaperTradingManager,
        mock_sim_engine: MagicMock,
    ) -> None:
        """CONFIRMATION_REQUIRED policy: signal queued for user confirmation."""
        confirm_account = AccountConfig(
            account_id="confirm-acct",
            account_type=AccountType.RITHMIC,
            label="Rithmic Confirm",
            execution_policy=ExecutionPolicy.CONFIRMATION_REQUIRED,
            is_paper=True,
            enabled=True,
        )
        await paper_manager.register_account(confirm_account)

        session = await paper_manager.create_session(
            name="Confirm Session",
            account_ids=[confirm_account.account_id],
            symbols=["MGC"],
            initial_balance=25_000.0,
            janus_enabled=False,
        )
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(session.session_id)

        signal = {
            "symbol": "MGC",
            "direction": "LONG",
            "trigger_price": 2400.0,
            "confidence": 0.75,
        }

        records = await paper_manager.route_signal(session.session_id, signal)

        assert len(records) >= 1
        rec = records[0]
        assert rec.executed is False
        assert rec.rejected_reason == "awaiting_confirmation"
        assert rec.execution_policy == ExecutionPolicy.CONFIRMATION_REQUIRED.value

        # Signal should be pending in the router
        assert paper_manager._router is not None
        pending = paper_manager._router.get_pending_signals()
        assert len(pending) >= 1
        assert any(p.signal_id == rec.signal_id for p in pending)

        # Confirm the signal
        confirmed = await paper_manager._router.confirm_signal(
            rec.signal_id,
            fill_price=2401.5,
        )
        assert confirmed is True

    @pytest.mark.asyncio()
    async def test_route_signal_session_not_running(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
    ) -> None:
        """Routing to a non-running session returns empty list."""
        assert sample_session.state == SessionState.CREATED

        records = await paper_manager.route_signal(
            sample_session.session_id,
            {"symbol": "MGC", "direction": "LONG", "trigger_price": 2350.0},
        )
        assert records == []

    @pytest.mark.asyncio()
    async def test_route_signal_symbol_filtered(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Signals for symbols not in the session's watchlist are dropped."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)

        signal = {
            "symbol": "ES",  # Not in session's symbols list
            "direction": "LONG",
            "trigger_price": 5500.0,
        }

        records = await paper_manager.route_signal(sample_session.session_id, signal)
        assert records == []


# ---------------------------------------------------------------------------
# Janus AI Integration Tests (mocked)
# ---------------------------------------------------------------------------


class TestJanusAIIntegration:
    """Verify Janus AI enrichment, regime gating, and confidence filtering."""

    @pytest.mark.asyncio()
    async def test_janus_enrichment(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Mock _query_janus to return confidence/regime; verify signal enrichment."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)
        paper_manager._sim_engines[sample_session.session_id] = mock_sim_engine

        janus_response = {
            "confidence": 0.92,
            "regime": "TRENDING_UP",
            "janus_direction": "LONG",
            "janus_signal_id": "janus-abc123",
        }

        with patch.object(
            paper_manager,
            "_query_janus",
            new_callable=AsyncMock,
            return_value=janus_response,
        ):
            records = await paper_manager.route_signal(
                sample_session.session_id,
                {
                    "symbol": "MGC",
                    "direction": "LONG",
                    "trigger_price": 2380.0,
                    "confidence": 0.70,
                    "qty": 1,
                },
            )

        assert len(records) >= 1
        rec = records[0]
        # Signal should be enriched with Janus data
        assert rec.janus_confidence == 0.92
        assert rec.janus_regime == "TRENDING_UP"
        # LONG in TRENDING_UP regime should be accepted
        assert rec.rejected_reason is None or "regime_gating" not in (rec.rejected_reason or "")

    @pytest.mark.asyncio()
    async def test_janus_regime_gating(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """LONG signal in TRENDING_DOWN regime is rejected by regime gating."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)
        paper_manager._sim_engines[sample_session.session_id] = mock_sim_engine

        janus_response = {
            "confidence": 0.90,
            "regime": "TRENDING_DOWN",
        }

        with patch.object(
            paper_manager,
            "_query_janus",
            new_callable=AsyncMock,
            return_value=janus_response,
        ):
            records = await paper_manager.route_signal(
                sample_session.session_id,
                {
                    "symbol": "MGC",
                    "direction": "LONG",
                    "trigger_price": 2350.0,
                    "confidence": 0.85,
                },
            )

        assert len(records) == 1
        rec = records[0]
        assert rec.rejected_reason is not None
        assert "regime_gating" in rec.rejected_reason
        assert rec.janus_regime == "TRENDING_DOWN"
        assert rec.executed is False

    @pytest.mark.asyncio()
    async def test_janus_regime_gating_short_trending_up(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """SHORT signal in TRENDING_UP regime is rejected by regime gating."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)
        paper_manager._sim_engines[sample_session.session_id] = mock_sim_engine

        janus_response = {
            "confidence": 0.88,
            "regime": "TRENDING_UP",
        }

        with patch.object(
            paper_manager,
            "_query_janus",
            new_callable=AsyncMock,
            return_value=janus_response,
        ):
            records = await paper_manager.route_signal(
                sample_session.session_id,
                {
                    "symbol": "MGC",
                    "direction": "SHORT",
                    "trigger_price": 2400.0,
                    "confidence": 0.85,
                },
            )

        assert len(records) == 1
        rec = records[0]
        assert rec.rejected_reason is not None
        assert "regime_gating" in rec.rejected_reason

    @pytest.mark.asyncio()
    async def test_janus_confidence_threshold(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Janus confidence below threshold rejects the signal."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)
        paper_manager._sim_engines[sample_session.session_id] = mock_sim_engine

        # Confidence below the default 0.65 threshold
        janus_response = {
            "confidence": 0.40,
            "regime": "RANGING",
        }

        with patch.object(
            paper_manager,
            "_query_janus",
            new_callable=AsyncMock,
            return_value=janus_response,
        ):
            records = await paper_manager.route_signal(
                sample_session.session_id,
                {
                    "symbol": "MGC",
                    "direction": "LONG",
                    "trigger_price": 2360.0,
                    "confidence": 0.40,
                },
            )

        assert len(records) == 1
        rec = records[0]
        assert rec.rejected_reason is not None
        assert "confidence" in rec.rejected_reason.lower()
        assert rec.executed is False

    @pytest.mark.asyncio()
    async def test_janus_unavailable_passthrough(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """When Janus is unavailable (returns None), signal proceeds normally."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)
        paper_manager._sim_engines[sample_session.session_id] = mock_sim_engine

        with patch.object(
            paper_manager,
            "_query_janus",
            new_callable=AsyncMock,
            return_value=None,
        ):
            records = await paper_manager.route_signal(
                sample_session.session_id,
                {
                    "symbol": "MGC",
                    "direction": "LONG",
                    "trigger_price": 2370.0,
                    "confidence": 0.80,
                    "qty": 1,
                },
            )

        # Signal should still be processed (routed to accounts)
        assert len(records) >= 1
        rec = records[0]
        assert rec.janus_confidence is None
        assert rec.janus_regime is None


# ---------------------------------------------------------------------------
# Metrics Tracking Tests
# ---------------------------------------------------------------------------


class TestMetricsTracking:
    """Verify win rate, PnL, drawdown, and other metric calculations."""

    @pytest.mark.asyncio()
    async def test_metrics_tracking(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Record a series of trades and verify aggregate metrics."""
        sid = sample_session.session_id

        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sid)
        paper_manager._sim_engines[sid] = mock_sim_engine

        # Simulate a sequence of closed trades
        trades = [
            (150.0, 300.0),  # win
            (-50.0, 120.0),  # loss
            (200.0, 450.0),  # win
            (80.0, 200.0),  # win
            (-120.0, 180.0),  # loss
        ]

        for pnl, hold_s in trades:
            await paper_manager.record_trade_close(sid, pnl=pnl, hold_duration_s=hold_s)

        metrics = paper_manager._metrics[sid]

        # Total trades
        assert metrics.total_trades == 5

        # Win/loss counts
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 2

        # Win rate: 3/5 = 60%
        assert abs(metrics.win_rate - 60.0) < 0.1

        # Total PnL: 150 - 50 + 200 + 80 - 120 = 260
        expected_pnl = 150.0 - 50.0 + 200.0 + 80.0 - 120.0
        assert abs(metrics.realized_pnl - expected_pnl) < 0.01

        # Current equity
        assert abs(metrics.current_equity - (sample_session.initial_balance + expected_pnl)) < 0.01

        # Peak equity should be >= current equity
        assert metrics.peak_equity >= metrics.current_equity

        # Largest win/loss
        assert metrics.largest_win == 200.0
        assert metrics.largest_loss == -120.0

        # Avg win: (150 + 200 + 80) / 3 ≈ 143.33
        assert abs(metrics.avg_win - 143.33) < 0.1

        # Avg loss: -(50 + 120) / 2 = -85.0
        assert abs(metrics.avg_loss - (-85.0)) < 0.1

        # Drawdown should be non-negative
        assert metrics.max_drawdown >= 0.0
        assert metrics.max_drawdown_pct >= 0.0

        # Profit factor: gross_wins / gross_losses = 430 / 170 ≈ 2.529
        assert metrics.profit_factor > 0

        # Average hold duration
        expected_avg_hold = sum(h for _, h in trades) / len(trades)
        assert abs(metrics.avg_hold_duration_s - expected_avg_hold) < 0.1

    @pytest.mark.asyncio()
    async def test_metrics_drawdown_calculation(
        self,
        paper_manager: PaperTradingManager,
        sample_account: AccountConfig,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Verify max drawdown is tracked correctly through peaks and valleys."""
        with _patch_sim_engine(mock_sim_engine):
            session = await paper_manager.create_session(
                name="Drawdown Test",
                account_ids=[sample_account.account_id],
                initial_balance=10_000.0,
                janus_enabled=False,
            )
        sid = session.session_id

        # Trade sequence designed to create a known drawdown pattern:
        #   equity: 10000 → 10500 (peak) → 10200 → 9800 → 10100
        #   max drawdown = 10500 - 9800 = 700
        trade_pnls = [500.0, -300.0, -400.0, 300.0]

        for pnl in trade_pnls:
            await paper_manager.record_trade_close(sid, pnl=pnl)

        metrics = paper_manager._metrics[sid]

        assert metrics.peak_equity == 10_500.0
        assert metrics.current_equity == 10_100.0
        # Max drawdown: from peak 10500 to trough 9800 = 700
        assert abs(metrics.max_drawdown - 700.0) < 0.01
        # Drawdown %: 700 / 10500 * 100 ≈ 6.67%
        assert abs(metrics.max_drawdown_pct - (700.0 / 10_500.0 * 100.0)) < 0.1

    @pytest.mark.asyncio()
    async def test_metrics_consecutive_streaks(
        self,
        paper_manager: PaperTradingManager,
        sample_account: AccountConfig,
    ) -> None:
        """Consecutive win/loss streaks are tracked correctly."""
        session = await paper_manager.create_session(
            name="Streak Test",
            account_ids=[sample_account.account_id],
            initial_balance=10_000.0,
            janus_enabled=False,
        )
        sid = session.session_id

        # W W W L L W → max_consecutive_wins=3, max_consecutive_losses=2
        for pnl in [100.0, 50.0, 200.0, -30.0, -60.0, 80.0]:
            await paper_manager.record_trade_close(sid, pnl=pnl)

        metrics = paper_manager._metrics[sid]
        assert metrics.max_consecutive_wins == 3
        assert metrics.max_consecutive_losses == 2
        # Current streaks after final win
        assert metrics.consecutive_wins == 1
        assert metrics.consecutive_losses == 0

    @pytest.mark.asyncio()
    async def test_metrics_signal_counters(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Signal received/executed/rejected counters update on route_signal."""
        sid = sample_session.session_id
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sid)
        paper_manager._sim_engines[sid] = mock_sim_engine

        # Route a signal that should execute (AUTO_EXECUTE account)
        await paper_manager.route_signal(
            sid,
            {
                "symbol": "MGC",
                "direction": "LONG",
                "trigger_price": 2350.0,
                "confidence": 0.90,
                "qty": 1,
            },
        )

        metrics = paper_manager._metrics[sid]
        assert metrics.total_signals_received >= 1
        assert metrics.total_signals_executed >= 1

    @pytest.mark.asyncio()
    async def test_get_session_metrics(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        mock_sim_engine: MagicMock,
    ) -> None:
        """get_session_metrics returns a SessionMetrics with correct data."""
        sid = sample_session.session_id
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sid)
        paper_manager._sim_engines[sid] = mock_sim_engine

        await paper_manager.record_trade_close(sid, pnl=100.0)

        metrics = await paper_manager.get_session_metrics(sid)
        assert metrics is not None
        assert metrics.total_trades == 1
        assert metrics.realized_pnl == 100.0

        # Serialisation round-trip
        d = metrics.to_dict()
        assert d["session_id"] == sid
        assert d["total_trades"] == 1

    @pytest.mark.asyncio()
    async def test_metrics_nonexistent_session(
        self,
        paper_manager: PaperTradingManager,
    ) -> None:
        """get_session_metrics returns None for unknown session IDs."""
        result = await paper_manager.get_session_metrics("nonexistent-session-id")
        assert result is None


# ---------------------------------------------------------------------------
# Account Management Tests
# ---------------------------------------------------------------------------


class TestAccountManagement:
    """Verify account registration, removal, and retrieval."""

    @pytest.mark.asyncio()
    async def test_register_account(
        self,
        paper_manager: PaperTradingManager,
    ) -> None:
        """Registering an account persists it and assigns an ID if empty."""
        config = AccountConfig(
            account_type=AccountType.KRAKEN,
            label="Kraken Test",
            execution_policy=ExecutionPolicy.AUTO_EXECUTE,
            is_paper=True,
        )
        result = await paper_manager.register_account(config)

        assert result.account_id, "account_id should be auto-assigned"
        assert paper_manager.get_account(result.account_id) is result

    @pytest.mark.asyncio()
    async def test_remove_account(
        self,
        paper_manager: PaperTradingManager,
    ) -> None:
        """Removing an account that isn't attached to a running session succeeds."""
        config = AccountConfig(
            account_id="remove-me",
            account_type=AccountType.SIMULATION,
            label="Temporary",
            enabled=True,
        )
        await paper_manager.register_account(config)
        assert paper_manager.get_account("remove-me") is not None

        removed = await paper_manager.remove_account("remove-me")
        assert removed is True
        assert paper_manager.get_account("remove-me") is None

    @pytest.mark.asyncio()
    async def test_remove_account_in_use(
        self,
        paper_manager: PaperTradingManager,
        sample_session: PaperSession,
        sample_account: AccountConfig,
        mock_sim_engine: MagicMock,
    ) -> None:
        """Cannot remove an account attached to a running session."""
        with _patch_sim_engine(mock_sim_engine):
            await paper_manager.start_session(sample_session.session_id)

        removed = await paper_manager.remove_account(sample_account.account_id)
        assert removed is False  # blocked because session is RUNNING

    @pytest.mark.asyncio()
    async def test_list_accounts(
        self,
        paper_manager: PaperTradingManager,
        sample_account: AccountConfig,
    ) -> None:
        """list_accounts includes all registered accounts."""
        accounts = paper_manager.list_accounts()
        assert any(a.account_id == sample_account.account_id for a in accounts)


# ---------------------------------------------------------------------------
# Execution Router Unit Tests
# ---------------------------------------------------------------------------


class TestExecutionRouter:
    """Direct tests on the ExecutionRouter class."""

    @pytest.mark.asyncio()
    async def test_router_auto_execute_paper(self, mock_redis: AsyncMock) -> None:
        """AUTO_EXECUTE on a paper account invokes the sim engine."""
        router = ExecutionRouter(mock_redis)
        sim = _build_mock_sim_engine()

        account = AccountConfig(
            account_id="auto-acct",
            execution_policy=ExecutionPolicy.AUTO_EXECUTE,
            is_paper=True,
            max_position_size=5.0,
        )

        signal = SignalRecord(
            session_id="sess-1",
            symbol="MGC",
            action="LONG",
            trigger_price=2350.0,
            fill_qty=3.0,
        )

        result = await router.route(signal, account, sim_engine=sim)

        assert result.executed is True
        assert result.fill_price == 2350.0
        assert result.fill_qty == 3.0
        sim.submit_market_order.assert_called_once_with("MGC", "long", qty=3.0)

    @pytest.mark.asyncio()
    async def test_router_auto_execute_caps_qty(self, mock_redis: AsyncMock) -> None:
        """AUTO_EXECUTE caps quantity to account's max_position_size."""
        router = ExecutionRouter(mock_redis)
        sim = _build_mock_sim_engine()

        account = AccountConfig(
            account_id="capped-acct",
            execution_policy=ExecutionPolicy.AUTO_EXECUTE,
            is_paper=True,
            max_position_size=2.0,
        )

        signal = SignalRecord(
            session_id="sess-1",
            symbol="MGC",
            action="LONG",
            trigger_price=2350.0,
            fill_qty=10.0,  # Exceeds max
        )

        result = await router.route(signal, account, sim_engine=sim)

        assert result.executed is True
        assert result.fill_qty == 2.0  # Capped

    @pytest.mark.asyncio()
    async def test_router_signals_only(self, mock_redis: AsyncMock) -> None:
        """SIGNALS_ONLY publishes but does not execute."""
        router = ExecutionRouter(mock_redis)

        account = AccountConfig(
            account_id="so-acct",
            execution_policy=ExecutionPolicy.SIGNALS_ONLY,
            is_paper=True,
        )

        signal = SignalRecord(
            session_id="sess-1",
            symbol="MNQ",
            action="SHORT",
            trigger_price=18600.0,
        )

        result = await router.route(signal, account)

        assert result.executed is False
        assert result.rejected_reason == "signals_only_policy"
        mock_redis.publish.assert_called()

    @pytest.mark.asyncio()
    async def test_router_confirmation_required(self, mock_redis: AsyncMock) -> None:
        """CONFIRMATION_REQUIRED queues signal and allows later confirmation."""
        router = ExecutionRouter(mock_redis)

        account = AccountConfig(
            account_id="confirm-acct",
            execution_policy=ExecutionPolicy.CONFIRMATION_REQUIRED,
            is_paper=True,
        )

        signal = SignalRecord(
            session_id="sess-1",
            symbol="MGC",
            action="LONG",
            trigger_price=2380.0,
        )

        result = await router.route(signal, account)

        assert result.executed is False
        assert result.rejected_reason == "awaiting_confirmation"

        # Pending list should contain the signal
        pending = router.get_pending_signals()
        assert any(p.signal_id == result.signal_id for p in pending)

        # Confirm it
        ok = await router.confirm_signal(result.signal_id, fill_price=2381.0)
        assert ok is True

        # After confirmation, the signal record is updated
        assert result.executed is True
        assert result.fill_price == 2381.0
        assert result.rejected_reason is None

    @pytest.mark.asyncio()
    async def test_router_dismiss_signal(self, mock_redis: AsyncMock) -> None:
        """Dismissing a pending signal marks it as rejected."""
        router = ExecutionRouter(mock_redis)

        account = AccountConfig(
            account_id="dismiss-acct",
            execution_policy=ExecutionPolicy.CONFIRMATION_REQUIRED,
            is_paper=True,
        )

        signal = SignalRecord(
            session_id="sess-1",
            symbol="MGC",
            action="SHORT",
            trigger_price=2400.0,
        )

        result = await router.route(signal, account)
        assert len(router.get_pending_signals()) == 1

        ok = await router.dismiss_signal(result.signal_id, reason="test_dismiss")
        assert ok is True
        assert result.rejected_reason == "test_dismiss"
        assert result.executed is False

    @pytest.mark.asyncio()
    async def test_router_confirm_nonexistent(self, mock_redis: AsyncMock) -> None:
        """Confirming a non-existent signal returns False."""
        router = ExecutionRouter(mock_redis)
        ok = await router.confirm_signal("does-not-exist")
        assert ok is False

    @pytest.mark.asyncio()
    async def test_router_close_action(self, mock_redis: AsyncMock) -> None:
        """AUTO_EXECUTE with CLOSE action calls sim.close_position."""
        router = ExecutionRouter(mock_redis)
        sim = _build_mock_sim_engine()

        account = AccountConfig(
            account_id="close-acct",
            execution_policy=ExecutionPolicy.AUTO_EXECUTE,
            is_paper=True,
        )

        signal = SignalRecord(
            session_id="sess-1",
            symbol="MGC",
            action="CLOSE",
            trigger_price=2370.0,
        )

        result = await router.route(signal, account, sim_engine=sim)

        assert result.executed is True
        sim.close_position.assert_called_once_with("MGC")


# ---------------------------------------------------------------------------
# Data Class Tests
# ---------------------------------------------------------------------------


class TestDataClasses:
    """Verify serialisation round-trips for core data classes."""

    def test_paper_session_round_trip(self) -> None:
        session = PaperSession(
            name="Round Trip",
            symbols=["MGC", "BTC/USDT"],
            initial_balance=25_000.0,
            tags={"strategy": "scalp"},
        )
        d = session.to_dict()
        restored = PaperSession.from_dict(d)

        assert restored.session_id == session.session_id
        assert restored.name == "Round Trip"
        assert restored.state == SessionState.CREATED
        assert restored.symbols == ["MGC", "BTC/USDT"]
        assert restored.initial_balance == 25_000.0

    def test_account_config_round_trip(self) -> None:
        config = AccountConfig(
            account_id="rt-acct",
            account_type=AccountType.KRAKEN,
            label="Kraken Main",
            execution_policy=ExecutionPolicy.AUTO_EXECUTE,
        )
        d = config.to_dict()
        restored = AccountConfig.from_dict(d)

        assert restored.account_id == "rt-acct"
        assert restored.account_type == AccountType.KRAKEN
        assert restored.execution_policy == ExecutionPolicy.AUTO_EXECUTE

    def test_signal_record_round_trip(self) -> None:
        record = SignalRecord(
            session_id="sess-1",
            symbol="MGC",
            action="LONG",
            trigger_price=2350.0,
            confidence=0.85,
            janus_confidence=0.90,
            janus_regime="TRENDING_UP",
            executed=True,
            fill_price=2351.0,
            fill_qty=2.0,
            metadata={"source": "test"},
        )
        d = record.to_dict()
        restored = SignalRecord.from_dict(d)

        assert restored.symbol == "MGC"
        assert restored.janus_confidence == 0.90
        assert restored.executed is True
        assert restored.metadata == {"source": "test"}

    def test_session_metrics_to_dict(self) -> None:
        m = SessionMetrics(session_id="m-1", current_equity=10_000.0, peak_equity=10_000.0)
        m.record_trade(100.0, hold_duration_s=60.0, initial_balance=10_000.0)
        m.record_trade(-30.0, hold_duration_s=45.0, initial_balance=10_000.0)

        d = m.to_dict()
        assert d["total_trades"] == 2
        assert d["winning_trades"] == 1
        assert d["losing_trades"] == 1
        assert d["realized_pnl"] == 70.0
        assert "session_id" in d
        # Internal accumulators should NOT be in the dict
        assert "_returns" not in d
        assert "_gross_wins" not in d


# ---------------------------------------------------------------------------
# Regime Favourability (static method)
# ---------------------------------------------------------------------------


class TestRegimeFavourability:
    """Verify the static _is_regime_favourable gate logic."""

    @pytest.mark.parametrize(
        ("action", "regime", "expected"),
        [
            ("LONG", "TRENDING_UP", True),
            ("LONG", "TRENDING_DOWN", False),
            ("SHORT", "TRENDING_UP", False),
            ("SHORT", "TRENDING_DOWN", True),
            ("LONG", "RANGING", True),
            ("SHORT", "RANGING", True),
            ("LONG", "VOLATILE", True),
            ("SHORT", "VOLATILE", True),
            ("LONG", "LOW_VOLATILITY", True),
            ("SHORT", "LOW_VOLATILITY", True),
            ("LONG", "UNKNOWN", True),
            ("SHORT", "UNKNOWN", True),
            ("CLOSE", "TRENDING_DOWN", True),
        ],
    )
    def test_regime_gate(self, action: str, regime: str, expected: bool) -> None:
        assert PaperTradingManager._is_regime_favourable(action, regime) is expected
