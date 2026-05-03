"""
Tests for RithmicPositionEngine — live Rithmic connection wrapper
=================================================================
Tests cover:

Offline mode (RITHMIC_LIVE_DATA unset / "0"):
  - connect() returns False and sets _connected=False
  - is_connected() always returns False
  - All getters return graceful mock / zero data with _mock / _live flags

Live mode, no account configured (RITHMIC_LIVE_DATA=1, no configs):
  - connect() returns False gracefully without crashing

Live mode with a mock RithmicStreamManager:
  - connect() wires through start() + connect_pnl_plant() + subscribe_symbols()
  - already-live guard skips reconnect
  - get_l1() delegates to get_l1_snapshot() when connected
  - get_l1() falls back to mock when snapshot returns None
  - get_recent_trades() delegates to get_recent_ticks() when connected
  - get_recent_trades() falls back to mock on stream error
  - get_pnl() reads from Redis pnl:live:{account_key}
  - get_positions() reads from Redis account-status cache
  - disconnect() calls stop() and publishes health=false

Helper functions:
  - _get_default_symbols() respects RITHMIC_SYMBOLS env var
  - _ticks_to_trades() side heuristic (buy ≥ ask, sell ≤ bid, default buy)
  - _read_pnl_from_redis() decodes Redis hash correctly
  - _read_positions_from_redis() maps positions including zero-qty filter
  - _publish_health() writes correct hash with TTL

Status / repr:
  - get_status() keys present
  - __repr__ reflects connected state
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.engine.rithmic_position_engine import (
    _DEFAULT_SYMBOLS,
    RithmicPositionEngine,
    _get_default_symbols,
    _publish_health,
    _read_pnl_from_redis,
    _read_positions_from_redis,
    _ticks_to_trades,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stream_manager(
    *,
    is_live: bool = True,
    connected: bool = True,
    l1_snapshot: dict | None = None,
    recent_ticks: list | None = None,
    already_live: bool = False,
) -> MagicMock:
    """Return a MagicMock that looks like a RithmicStreamManager.

    Args:
        is_live: What ``is_live()`` returns once a connection is established.
            Defaults to ``True`` so connect() succeeds and _connected is set.
        already_live: When ``True``, the very first ``is_live()`` call returns
            ``True``, triggering the early-exit "already live" guard.  Use
            this only for the specific test that exercises that guard.
        connected: The ``_connected`` attribute value.
    """
    sm = MagicMock()

    if already_live:
        # Always return True — simulates an already-live stream manager.
        sm.is_live.return_value = True
    else:
        # First call → False (not already live, proceed with connect path).
        # All subsequent calls → the ``is_live`` value (post-connect state).
        _calls: list[int] = [0]

        def _is_live_fn():
            _calls[0] += 1
            if _calls[0] == 1:
                return False  # "already live?" guard → False → proceed
            return is_live

        sm.is_live.side_effect = _is_live_fn

    sm._connected = connected
    sm._subscribed_symbols = set()
    sm.get_plant_states.return_value = {}
    sm.is_pnl_connected = True
    sm.is_order_connected = False
    sm.is_history_connected = False

    # Async methods
    sm.start = AsyncMock(return_value=True)
    sm.connect_pnl_plant = AsyncMock(return_value=True)
    sm.subscribe_symbols = AsyncMock()
    sm.stop = AsyncMock()

    sm.get_l1_snapshot = AsyncMock(return_value=l1_snapshot)
    sm.get_recent_ticks = AsyncMock(return_value=recent_ticks or [])

    return sm


def _make_config(key: str = "acc1", enabled: bool = True) -> MagicMock:
    cfg = MagicMock()
    cfg.key = key
    cfg.enabled = enabled
    cfg.gateway = "Chicago"
    return cfg


def _make_manager(*configs) -> MagicMock:
    """Return a mock RithmicAccountManager with the given configs."""
    mgr = MagicMock()
    mgr._configs = {c.key: c for c in configs}
    mgr.reload_configs.return_value = None
    mgr.get_all_ui.return_value = []
    return mgr


# ---------------------------------------------------------------------------
# Offline mode (RITHMIC_LIVE_DATA not set / "0")
# ---------------------------------------------------------------------------


class TestOfflineMode:
    """All methods must return graceful mock / zero data when live data is disabled."""

    @pytest.fixture(autouse=True)
    def no_live_data(self, monkeypatch):
        monkeypatch.delenv("RITHMIC_LIVE_DATA", raising=False)

    # -- connect / is_connected --

    def test_connect_returns_false(self):
        engine = RithmicPositionEngine()
        result = asyncio.run(engine.connect())
        assert result is False

    def test_connect_sets_connected_false(self):
        engine = RithmicPositionEngine()
        asyncio.run(engine.connect())
        assert engine._connected is False

    def test_is_connected_false_when_offline(self):
        engine = RithmicPositionEngine()
        assert engine.is_connected() is False

    def test_is_connected_false_even_if_internal_flag_set(self):
        """_connected flag is ignored when RITHMIC_LIVE_DATA is not set."""
        engine = RithmicPositionEngine()
        engine._connected = True  # force internal state
        assert engine.is_connected() is False

    # -- get_positions --

    def test_get_positions_returns_mock_list(self):
        engine = RithmicPositionEngine()
        positions = asyncio.run(engine.get_positions())
        assert isinstance(positions, list)
        assert len(positions) > 0
        assert positions[0].get("_mock") is True

    def test_get_positions_mock_has_required_keys(self):
        engine = RithmicPositionEngine()
        pos = asyncio.run(engine.get_positions())[0]
        for key in ("symbol", "qty", "avg_price", "side", "unrealized_pnl", "account"):
            assert key in pos, f"missing key: {key}"

    def test_get_positions_account_key_propagated(self):
        engine = RithmicPositionEngine()
        pos = asyncio.run(engine.get_positions(account_key="MY_ACCT"))
        assert pos[0]["account"] == "MY_ACCT"

    # -- get_l1 --

    def test_get_l1_returns_mock_dict(self):
        engine = RithmicPositionEngine()
        l1 = asyncio.run(engine.get_l1("MES"))
        assert isinstance(l1, dict)
        assert l1.get("_mock") is True
        for key in ("bid", "ask", "last", "volume"):
            assert key in l1, f"missing key: {key}"

    def test_get_l1_symbol_in_result(self):
        engine = RithmicPositionEngine()
        l1 = asyncio.run(engine.get_l1("NQ"))
        assert l1.get("symbol") == "NQ"

    # -- get_l2 --

    def test_get_l2_returns_mock(self):
        engine = RithmicPositionEngine()
        l2 = asyncio.run(engine.get_l2("MES", levels=5))
        assert l2.get("_mock") is True
        assert len(l2["bids"]) == 5
        assert len(l2["asks"]) == 5

    def test_get_l2_level_clamping(self):
        engine = RithmicPositionEngine()
        l2 = asyncio.run(engine.get_l2("MES", levels=100))  # clamped to 20
        assert len(l2["bids"]) == 20
        l2_min = asyncio.run(engine.get_l2("MES", levels=0))  # clamped to 1
        assert len(l2_min["bids"]) == 1

    def test_get_l2_bid_ask_structure(self):
        engine = RithmicPositionEngine()
        l2 = asyncio.run(engine.get_l2("MES", levels=3))
        for lvl in l2["bids"] + l2["asks"]:
            assert "price" in lvl
            assert "size" in lvl
            assert lvl["size"] >= 1

    # -- get_recent_trades --

    def test_get_recent_trades_returns_mock_list(self):
        engine = RithmicPositionEngine()
        trades = asyncio.run(engine.get_recent_trades("MES", n=5))
        assert isinstance(trades, list)
        assert len(trades) == 5
        assert all(t.get("_mock") for t in trades)

    def test_get_recent_trades_keys(self):
        engine = RithmicPositionEngine()
        trade = asyncio.run(engine.get_recent_trades("MES", n=1))[0]
        for key in ("price", "size", "side", "timestamp"):
            assert key in trade

    def test_get_recent_trades_sides(self):
        engine = RithmicPositionEngine()
        trades = asyncio.run(engine.get_recent_trades("MES", n=20))
        sides = {t["side"] for t in trades}
        assert sides <= {"buy", "sell"}

    # -- get_pnl --

    def test_get_pnl_returns_zero_dict(self):
        engine = RithmicPositionEngine()
        pnl = asyncio.run(engine.get_pnl("acc1"))
        assert pnl["daily_pnl"] == 0.0
        assert pnl["unrealized_pnl"] == 0.0
        assert pnl["realized_pnl"] == 0.0

    def test_get_pnl_no_live_flag(self):
        engine = RithmicPositionEngine()
        pnl = asyncio.run(engine.get_pnl("acc1"))
        assert "_live" not in pnl

    # -- get_status --

    def test_get_status_offline(self):
        engine = RithmicPositionEngine()
        status = engine.get_status()
        assert status["connected"] is False
        assert status["live_data_enabled"] is False
        assert isinstance(status["subscribed_symbols"], list)

    # -- disconnect (no-op when not connected) --

    def test_disconnect_no_op_without_stream_manager(self):
        engine = RithmicPositionEngine()
        # Should not raise
        asyncio.run(engine.disconnect())
        assert engine._connected is False


# ---------------------------------------------------------------------------
# Live mode — RITHMIC_LIVE_DATA=1 but no account configured
# ---------------------------------------------------------------------------


class TestLiveModeNoAccount:
    @pytest.fixture(autouse=True)
    def live_env(self, monkeypatch):
        monkeypatch.setenv("RITHMIC_LIVE_DATA", "1")

    def test_connect_returns_false_with_no_config(self):
        """When no enabled account exists, connect() must return False without crashing."""
        # Mock the account manager to return no configs
        empty_mgr = _make_manager()

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: empty_mgr,
        ):
            engine = RithmicPositionEngine()
            result = asyncio.run(engine.connect())

        assert result is False
        assert engine._connected is False
        assert engine._account_key == ""

    def test_is_connected_false_when_not_connected(self):
        empty_mgr = _make_manager()

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: empty_mgr,
        ):
            engine = RithmicPositionEngine()
            asyncio.run(engine.connect())
            assert engine.is_connected() is False

    def test_getters_still_return_mock_when_not_connected(self):
        empty_mgr = _make_manager()

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: empty_mgr,
        ):
            engine = RithmicPositionEngine()
            asyncio.run(engine.connect())

        l1 = asyncio.run(engine.get_l1("MES"))
        assert l1.get("_mock") is True


# ---------------------------------------------------------------------------
# Live mode with a mock RithmicStreamManager
# ---------------------------------------------------------------------------


class TestLiveModeWithStreamManager:
    @pytest.fixture(autouse=True)
    def live_env(self, monkeypatch):
        monkeypatch.setenv("RITHMIC_LIVE_DATA", "1")

    @pytest.fixture
    def config(self):
        return _make_config(key="acc1", enabled=True)

    @pytest.fixture
    def manager(self, config):
        return _make_manager(config)

    @pytest.fixture
    def stream_manager(self):
        return _make_stream_manager(is_live=True, connected=True)

    # -- connect() --

    def test_connect_calls_start(self, stream_manager, manager, config):
        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            result = asyncio.run(engine.connect())

        assert result is True
        stream_manager.start.assert_awaited_once_with(config)

    def test_connect_calls_pnl_plant(self, stream_manager, manager, config):
        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())

        stream_manager.connect_pnl_plant.assert_awaited_once_with(config)

    def test_connect_subscribes_to_default_symbols(self, stream_manager, manager, monkeypatch):
        monkeypatch.delenv("RITHMIC_SYMBOLS", raising=False)

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())

        stream_manager.subscribe_symbols.assert_awaited_once()
        subscribed = stream_manager.subscribe_symbols.await_args[0][0]
        assert set(subscribed) == set(_DEFAULT_SYMBOLS)

    def test_connect_subscribes_to_env_symbols(self, stream_manager, manager, monkeypatch):
        monkeypatch.setenv("RITHMIC_SYMBOLS", "MES,NQ,MGC")

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())

        subscribed = stream_manager.subscribe_symbols.await_args[0][0]
        assert set(subscribed) == {"MES", "NQ", "MGC"}

    def test_connect_sets_account_key(self, stream_manager, manager, config):
        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())

        assert engine._account_key == config.key

    def test_connect_already_live_skips_reconnect(self, manager):
        """When is_live() returns True on the first call, connect() skips start()."""
        sm = _make_stream_manager(is_live=True, already_live=True)

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=sm)
            result = asyncio.run(engine.connect())

        assert result is True
        sm.start.assert_not_awaited()

    def test_connect_returns_false_when_start_fails(self, manager):
        sm = _make_stream_manager(is_live=False)
        sm.start = AsyncMock(return_value=False)  # TICKER_PLANT fails

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=sm)
            result = asyncio.run(engine.connect())

        assert result is False

    # -- is_connected() --

    def test_is_connected_delegates_to_is_live(self, stream_manager, manager):
        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())

        # After connect, override side_effect to control is_live directly
        stream_manager.is_live.side_effect = None
        stream_manager.is_live.return_value = True
        assert engine.is_connected() is True

        stream_manager.is_live.return_value = False
        assert engine.is_connected() is False

    # -- get_l1() --

    def test_get_l1_uses_snapshot_when_connected(self, stream_manager, manager, monkeypatch):
        live_l1 = {"bid": 5100.0, "ask": 5100.25, "last": 5100.0, "volume": 500, "ts": 1700000000}
        stream_manager.get_l1_snapshot = AsyncMock(return_value=live_l1)

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())
            # After connect, override side_effect so is_live() returns True for get_l1
            stream_manager.is_live.side_effect = None
            stream_manager.is_live.return_value = True
            l1 = asyncio.run(engine.get_l1("MES"))

        assert l1.get("_live") is True
        assert l1["bid"] == 5100.0
        assert l1["ask"] == 5100.25

    def test_get_l1_falls_back_to_mock_when_snapshot_is_none(self, manager):
        sm = _make_stream_manager(is_live=True, l1_snapshot=None)

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=sm)
            asyncio.run(engine.connect())
            # After connect, override so get_l1 sees is_live=True and tries live path
            sm.is_live.side_effect = None
            sm.is_live.return_value = True
            l1 = asyncio.run(engine.get_l1("MES"))

        assert l1.get("_mock") is True

    def test_get_l1_snapshot_called_with_correct_symbol(self, stream_manager, manager):
        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())
            # Override so get_l1 sees is_live=True
            stream_manager.is_live.side_effect = None
            stream_manager.is_live.return_value = True
            asyncio.run(engine.get_l1("NQ"))

        stream_manager.get_l1_snapshot.assert_awaited_once_with("NQ")

    # -- get_recent_trades() --

    def test_get_recent_trades_from_ticks(self, manager):
        ticks = [
            {"symbol": "MES", "bid": 5419.75, "ask": 5420.0, "last": 5420.0, "volume": 2, "ts": 1700000010},
            {"symbol": "MES", "bid": 5419.75, "ask": 5420.0, "last": 5419.75, "volume": 1, "ts": 1700000005},
        ]
        sm = _make_stream_manager(is_live=True, recent_ticks=ticks)

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=sm)
            asyncio.run(engine.connect())
            # Override so get_recent_trades sees is_live=True
            sm.is_live.side_effect = None
            sm.is_live.return_value = True
            trades = asyncio.run(engine.get_recent_trades("MES", n=5))

        assert len(trades) == 2
        assert all("_mock" not in t for t in trades)
        assert trades[0]["price"] == 5420.0  # last = ask → buy
        assert trades[0]["side"] == "buy"
        assert trades[1]["side"] == "sell"  # last = bid → sell

    def test_get_recent_trades_empty_list_when_no_ticks(self, manager):
        """When connected but no ticks yet, should return [] not mock."""
        sm = _make_stream_manager(is_live=True, recent_ticks=[])

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=sm)
            asyncio.run(engine.connect())
            sm.is_live.side_effect = None
            sm.is_live.return_value = True
            trades = asyncio.run(engine.get_recent_trades("MES", n=10))

        assert trades == []

    def test_get_recent_trades_falls_back_to_mock_on_error(self, manager):
        sm = _make_stream_manager(is_live=True)
        sm.get_recent_ticks = AsyncMock(side_effect=RuntimeError("connection dropped"))

        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=sm)
            asyncio.run(engine.connect())
            sm.is_live.side_effect = None
            sm.is_live.return_value = True
            trades = asyncio.run(engine.get_recent_trades("MES", n=5))

        assert len(trades) > 0
        assert trades[0].get("_mock") is True

    def test_get_recent_trades_n_clamped(self):
        engine = RithmicPositionEngine()
        trades = asyncio.run(engine.get_recent_trades("MES", n=999))
        # Offline mock caps at 20
        assert len(trades) == 20

    # -- get_pnl() --

    def test_get_pnl_reads_from_redis(self, stream_manager, manager):
        pnl_data = {
            b"unrealized": b"12.50",
            b"realized": b"5.00",
            b"total": b"17.50",
            b"ts": b"2024-01-01T10:00:00",
        }
        mock_r = MagicMock()
        mock_r.hgetall.return_value = pnl_data

        with (
            patch(
                "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
                return_value=lambda: manager,
            ),
            patch("lib.services.engine.rithmic_position_engine._read_pnl_from_redis") as mock_pnl,
        ):
            mock_pnl.return_value = {
                "unrealized": 12.50,
                "realized": 5.00,
                "total": 17.50,
                "ts": "2024-01-01T10:00:00",
            }
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())
            stream_manager.is_live.side_effect = None
            stream_manager.is_live.return_value = True
            pnl = asyncio.run(engine.get_pnl("acc1"))

        assert pnl["unrealized_pnl"] == 12.50
        assert pnl["realized_pnl"] == 5.00
        assert pnl["_live"] is True

    def test_get_pnl_returns_zeros_when_redis_empty(self, stream_manager, manager):
        with (
            patch(
                "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
                return_value=lambda: manager,
            ),
            patch(
                "lib.services.engine.rithmic_position_engine._read_pnl_from_redis",
                return_value=None,
            ),
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())
            stream_manager.is_live.side_effect = None
            stream_manager.is_live.return_value = True
            pnl = asyncio.run(engine.get_pnl("acc1"))

        assert pnl["daily_pnl"] == 0.0
        assert pnl["unrealized_pnl"] == 0.0
        assert pnl["realized_pnl"] == 0.0

    # -- get_positions() --

    def test_get_positions_reads_from_redis(self, stream_manager, manager, config):
        with (
            patch(
                "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
                return_value=lambda: manager,
            ),
            patch(
                "lib.services.engine.rithmic_position_engine._read_positions_from_redis",
                return_value=[
                    {
                        "symbol": "MES",
                        "qty": 2,
                        "avg_price": 5400.0,
                        "side": "long",
                        "unrealized_pnl": 25.0,
                        "account": config.key,
                    }
                ],
            ),
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())
            stream_manager.is_live.side_effect = None
            stream_manager.is_live.return_value = True
            positions = asyncio.run(engine.get_positions())

        assert len(positions) == 1
        assert positions[0]["symbol"] == "MES"
        assert positions[0]["qty"] == 2
        assert "_mock" not in positions[0]

    def test_get_positions_empty_when_cache_empty(self, stream_manager, manager):
        with (
            patch(
                "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
                return_value=lambda: manager,
            ),
            patch(
                "lib.services.engine.rithmic_position_engine._read_positions_from_redis",
                return_value=[],
            ),
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())
            stream_manager.is_live.side_effect = None
            stream_manager.is_live.return_value = True
            positions = asyncio.run(engine.get_positions())

        assert positions == []

    # -- disconnect() --

    def test_disconnect_calls_stop(self, stream_manager, manager):
        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())
            asyncio.run(engine.disconnect())

        stream_manager.stop.assert_awaited_once()

    def test_disconnect_sets_connected_false(self, stream_manager, manager):
        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            stream_manager.is_live.side_effect = None
            stream_manager.is_live.return_value = False
            asyncio.run(engine.connect())

        asyncio.run(engine.disconnect())
        assert engine._connected is False

    def test_disconnect_handles_stop_error_gracefully(self):
        sm = _make_stream_manager()
        sm.stop = AsyncMock(side_effect=RuntimeError("network error"))
        engine = RithmicPositionEngine(stream_manager=sm)
        engine._connected = True

        # Should not raise
        asyncio.run(engine.disconnect())
        assert engine._connected is False

    # -- subscribe_symbols() --

    def test_subscribe_symbols_when_connected(self, stream_manager, manager):
        with patch(
            "lib.services.engine.rithmic_position_engine._import_account_manager_factory",
            return_value=lambda: manager,
        ):
            engine = RithmicPositionEngine(stream_manager=stream_manager)
            asyncio.run(engine.connect())
            # Now live so subscribe_symbols is active
            stream_manager.is_live.return_value = True

        stream_manager.subscribe_symbols.reset_mock()
        asyncio.run(engine.subscribe_symbols(["6E", "GC"]))

        stream_manager.subscribe_symbols.assert_awaited_once_with(["6E", "GC"])
        assert "6E" in engine._subscribed_symbols
        assert "GC" in engine._subscribed_symbols

    def test_subscribe_symbols_noop_when_not_connected(self):
        sm = _make_stream_manager(is_live=False)
        engine = RithmicPositionEngine(stream_manager=sm)
        engine._connected = False

        asyncio.run(engine.subscribe_symbols(["MES"]))
        sm.subscribe_symbols.assert_not_awaited()


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestGetDefaultSymbols:
    def test_returns_default_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("RITHMIC_SYMBOLS", raising=False)
        symbols = _get_default_symbols()
        assert symbols == list(_DEFAULT_SYMBOLS)

    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("RITHMIC_SYMBOLS", "MGC,MES,6E")
        symbols = _get_default_symbols()
        assert symbols == ["MGC", "MES", "6E"]

    def test_uppercases_symbols(self, monkeypatch):
        monkeypatch.setenv("RITHMIC_SYMBOLS", "mes,nq")
        symbols = _get_default_symbols()
        assert symbols == ["MES", "NQ"]

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("RITHMIC_SYMBOLS", " MES , NQ , ES ")
        symbols = _get_default_symbols()
        assert symbols == ["MES", "NQ", "ES"]

    def test_empty_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("RITHMIC_SYMBOLS", "")
        symbols = _get_default_symbols()
        assert symbols == list(_DEFAULT_SYMBOLS)

    def test_env_with_only_commas_falls_back(self, monkeypatch):
        monkeypatch.setenv("RITHMIC_SYMBOLS", ",,,")
        symbols = _get_default_symbols()
        assert symbols == list(_DEFAULT_SYMBOLS)


class TestTicksToTrades:
    def test_last_at_ask_is_buy(self):
        ticks = [{"bid": 100.0, "ask": 100.25, "last": 100.25, "volume": 3, "ts": 1700000000}]
        trades = _ticks_to_trades(ticks)
        assert trades[0]["side"] == "buy"

    def test_last_above_ask_is_buy(self):
        ticks = [{"bid": 100.0, "ask": 100.25, "last": 100.50, "volume": 1, "ts": 1700000000}]
        trades = _ticks_to_trades(ticks)
        assert trades[0]["side"] == "buy"

    def test_last_at_bid_is_sell(self):
        ticks = [{"bid": 100.0, "ask": 100.25, "last": 100.0, "volume": 2, "ts": 1700000000}]
        trades = _ticks_to_trades(ticks)
        assert trades[0]["side"] == "sell"

    def test_last_below_bid_is_sell(self):
        ticks = [{"bid": 100.0, "ask": 100.25, "last": 99.75, "volume": 2, "ts": 1700000000}]
        trades = _ticks_to_trades(ticks)
        assert trades[0]["side"] == "sell"

    def test_last_between_bid_ask_defaults_to_buy(self):
        ticks = [{"bid": 100.0, "ask": 100.50, "last": 100.25, "volume": 1, "ts": 1700000000}]
        trades = _ticks_to_trades(ticks)
        assert trades[0]["side"] == "buy"

    def test_missing_last_skips_tick(self):
        ticks = [{"bid": 100.0, "ask": 100.25, "last": None, "volume": 1, "ts": 1700000000}]
        trades = _ticks_to_trades(ticks)
        assert trades == []

    def test_volume_zero_defaults_to_one(self):
        ticks = [{"bid": 100.0, "ask": 100.25, "last": 100.25, "volume": 0, "ts": 1700000000}]
        trades = _ticks_to_trades(ticks)
        assert trades[0]["size"] == 1

    def test_nanosecond_ts_converted(self):
        ts_ns = 1_700_000_000 * 1_000_000_000  # nanoseconds
        ticks = [{"bid": 100.0, "ask": 100.25, "last": 100.25, "volume": 1, "ts": ts_ns}]
        trades = _ticks_to_trades(ticks)
        # Should be converted to seconds
        assert trades[0]["timestamp"] == pytest.approx(1_700_000_000.0, rel=1e-3)

    def test_empty_input_returns_empty(self):
        assert _ticks_to_trades([]) == []

    def test_multiple_ticks(self):
        ticks = [
            {"bid": 100.0, "ask": 100.25, "last": 100.25, "volume": 2, "ts": 1700000010},
            {"bid": 100.0, "ask": 100.25, "last": 100.0, "volume": 1, "ts": 1700000005},
        ]
        trades = _ticks_to_trades(ticks)
        assert len(trades) == 2
        assert trades[0]["side"] == "buy"
        assert trades[1]["side"] == "sell"


class TestReadPnlFromRedis:
    def _patch_redis(self, raw: dict | None):
        mock_r = MagicMock()
        mock_r.hgetall.return_value = raw if raw is not None else {}
        return patch(
            "lib.services.engine.rithmic_position_engine._r",
            mock_r,
        ), patch(
            "lib.services.engine.rithmic_position_engine.REDIS_AVAILABLE",
            True,
        )

    def test_returns_none_when_key_missing(self):
        mock_r = MagicMock()
        mock_r.hgetall.return_value = {}

        with (
            patch("lib.core.cache.REDIS_AVAILABLE", True),
            patch("lib.core.cache._r", mock_r),
        ):
            result = _read_pnl_from_redis("acc1")

        assert result is None

    def test_decodes_bytes_values(self):
        raw = {
            b"unrealized": b"12.50",
            b"realized": b"5.00",
            b"total": b"17.50",
            b"ts": b"2024-01-01T10:00:00",
        }
        mock_r = MagicMock()
        mock_r.hgetall.return_value = raw

        with (
            patch("lib.core.cache.REDIS_AVAILABLE", True),
            patch("lib.core.cache._r", mock_r),
        ):
            result = _read_pnl_from_redis("acc1")

        assert result is not None
        assert result["unrealized"] == 12.50
        assert result["realized"] == 5.00
        assert result["total"] == 17.50
        assert result["ts"] == "2024-01-01T10:00:00"

    def test_returns_none_on_redis_unavailable(self):
        with patch("lib.core.cache.REDIS_AVAILABLE", False):
            result = _read_pnl_from_redis("acc1")
        assert result is None


class TestReadPositionsFromRedis:
    def test_returns_empty_when_no_cache(self):
        with patch("lib.core.cache.cache_get", return_value=None):
            result = _read_positions_from_redis("acc1")
        assert result == []

    def test_parses_positions_correctly(self):
        status_data = {
            "positions": [
                {"symbol": "MES", "size": 2, "avg_price": 5400.0, "open_pnl": 25.0},
                {"symbol": "MNQ", "size": -1, "avg_price": 18000.0, "open_pnl": -10.0},
            ]
        }
        raw = json.dumps(status_data).encode()

        with patch("lib.core.cache.cache_get", return_value=raw):
            result = _read_positions_from_redis("acc1")

        assert len(result) == 2

        long_pos = next(p for p in result if p["symbol"] == "MES")
        assert long_pos["qty"] == 2
        assert long_pos["side"] == "long"
        assert long_pos["avg_price"] == 5400.0

        short_pos = next(p for p in result if p["symbol"] == "MNQ")
        assert short_pos["qty"] == 1
        assert short_pos["side"] == "short"

    def test_zero_size_positions_filtered_out(self):
        status_data = {
            "positions": [
                {"symbol": "MES", "size": 0, "avg_price": 5400.0, "open_pnl": 0.0},
            ]
        }
        raw = json.dumps(status_data).encode()

        with patch("lib.core.cache.cache_get", return_value=raw):
            result = _read_positions_from_redis("acc1")

        assert result == []

    def test_handles_legacy_field_names(self):
        """Supports qty/unrealized_pnl aliases in addition to size/open_pnl."""
        status_data = {
            "positions": [
                {"symbol": "ES", "qty": 3, "avg_price": 5500.0, "unrealized_pnl": 75.0},
            ]
        }
        raw = json.dumps(status_data).encode()

        with patch("lib.core.cache.cache_get", return_value=raw):
            result = _read_positions_from_redis("acc1")

        assert len(result) == 1
        assert result[0]["qty"] == 3
        assert result[0]["unrealized_pnl"] == 75.0

    def test_returns_empty_on_malformed_json(self):
        with patch("lib.core.cache.cache_get", return_value=b"not-json"):
            result = _read_positions_from_redis("acc1")
        assert result == []

    def test_account_key_in_result(self):
        status_data = {
            "positions": [
                {"symbol": "MES", "size": 1, "avg_price": 5400.0, "open_pnl": 0.0},
            ]
        }
        raw = json.dumps(status_data).encode()

        with patch("lib.core.cache.cache_get", return_value=raw):
            result = _read_positions_from_redis("my_account")

        assert result[0]["account"] == "my_account"


class TestPublishHealth:
    def test_writes_to_redis(self):
        mock_r = MagicMock()

        with (
            patch("lib.core.cache.REDIS_AVAILABLE", True),
            patch("lib.core.cache._r", mock_r),
        ):
            _publish_health(True, account_key="acc1")

        mock_r.hset.assert_called_once()
        call_kwargs = mock_r.hset.call_args
        key = call_kwargs[0][0]
        mapping = call_kwargs[1]["mapping"]
        assert "rithmic:health" in key
        assert mapping["connected"] == "true"
        assert mapping["account_key"] == "acc1"

    def test_sets_ttl(self):
        mock_r = MagicMock()

        with (
            patch("lib.core.cache.REDIS_AVAILABLE", True),
            patch("lib.core.cache._r", mock_r),
        ):
            _publish_health(False, error="connection failed")

        mock_r.expire.assert_called_once()
        assert mock_r.expire.call_args[0][1] == 30  # 30 s TTL

    def test_connected_false_written_correctly(self):
        mock_r = MagicMock()

        with (
            patch("lib.core.cache.REDIS_AVAILABLE", True),
            patch("lib.core.cache._r", mock_r),
        ):
            _publish_health(False, error="oops")

        mapping = mock_r.hset.call_args[1]["mapping"]
        assert mapping["connected"] == "false"
        assert mapping["error"] == "oops"

    def test_no_op_when_redis_unavailable(self):
        mock_r = MagicMock()

        with (
            patch("lib.core.cache.REDIS_AVAILABLE", False),
            patch("lib.core.cache._r", mock_r),
        ):
            _publish_health(True)

        mock_r.hset.assert_not_called()


# ---------------------------------------------------------------------------
# Status / repr
# ---------------------------------------------------------------------------


class TestGetStatus:
    def test_get_status_keys(self):
        engine = RithmicPositionEngine()
        status = engine.get_status()
        expected_keys = {
            "connected",
            "account_key",
            "subscribed_symbols",
            "connect_ts",
            "live_data_enabled",
        }
        assert expected_keys.issubset(set(status.keys()))

    def test_get_status_connected_false_when_offline(self, monkeypatch):
        monkeypatch.delenv("RITHMIC_LIVE_DATA", raising=False)
        engine = RithmicPositionEngine()
        status = engine.get_status()
        assert status["connected"] is False
        assert status["live_data_enabled"] is False

    def test_get_status_subscribed_symbols_from_engine(self, monkeypatch):
        monkeypatch.delenv("RITHMIC_LIVE_DATA", raising=False)
        engine = RithmicPositionEngine()
        engine._subscribed_symbols = ["MES", "NQ"]
        status = engine.get_status()
        assert status["subscribed_symbols"] == ["MES", "NQ"]

    def test_get_status_includes_plant_states_when_stream_manager_present(self):
        sm = _make_stream_manager()
        sm.get_plant_states.return_value = {"TICKER_PLANT": {"state": "connected"}}
        engine = RithmicPositionEngine(stream_manager=sm)
        status = engine.get_status()
        assert "plant_states" in status
        assert status["plant_states"]["TICKER_PLANT"]["state"] == "connected"


class TestRepr:
    def test_repr_offline(self, monkeypatch):
        monkeypatch.delenv("RITHMIC_LIVE_DATA", raising=False)
        engine = RithmicPositionEngine()
        r = repr(engine)
        assert "connected=False" in r
        assert "stream_manager=no" in r

    def test_repr_with_stream_manager(self):
        sm = _make_stream_manager()
        engine = RithmicPositionEngine(stream_manager=sm)
        r = repr(engine)
        assert "stream_manager=yes" in r
