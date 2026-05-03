"""
Rithmic Integration Tests — RithmicStreamManager (TESTS-A)
============================================================
Tests the connection manager, reconnect lifecycle, bar aggregation,
and order event processing using mocked WebSocket connections.

``async_rithmic`` is NOT installed in the test environment, so we
mock it via ``sys.modules`` patching before any import of the client.
All tests are fully offline — no real WebSocket connections are made.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Environment setup — must happen before any project imports
# ---------------------------------------------------------------------------
os.environ.setdefault("DISABLE_REDIS", "1")
os.environ.setdefault("PROMETHEUS_DISABLE_CREATED_SERIES", "true")


# ---------------------------------------------------------------------------
# Fake async_rithmic module
# ---------------------------------------------------------------------------
# We inject a stub ``async_rithmic`` module into ``sys.modules`` before
# importing the client.  This means the real ``from async_rithmic import ...``
# inside ``start()`` will succeed (getting our stubs) instead of raising
# ImportError.
#
# IMPORTANT: We do NOT stub ``lib.core.cache`` — the real module loads fine
# with ``DISABLE_REDIS=1``.  Only ``async_rithmic`` needs a fake because it
# is a third-party package that is not installed in the test environment.


class _FakeGateway:
    """Simulates the async_rithmic.Gateway enum."""

    CHICAGO = "wss://fake-chicago.rithmic.com"
    SYDNEY = "wss://fake-sydney.rithmic.com"
    SAO_PAULO = "wss://fake-saopaulo.rithmic.com"
    TEST = "wss://fake-test.rithmic.com"


class _FakeSysInfraType:
    TICKER_PLANT = "TICKER_PLANT"
    ORDER_PLANT = "ORDER_PLANT"
    PNL_PLANT = "PNL_PLANT"
    HISTORY_PLANT = "HISTORY_PLANT"


class _FakeDataType:
    """Minimal stub for ``async_rithmic.DataType`` flag enum."""

    LAST_TRADE = 1
    BBO = 2
    ORDER_BOOK = 4

    def __init__(self, value: int = 0) -> None:
        self._value = value

    def __or__(self, other: Any) -> _FakeDataType:
        if isinstance(other, _FakeDataType):
            return _FakeDataType(self._value | other._value)
        if isinstance(other, int):
            return _FakeDataType(self._value | other)
        return NotImplemented

    def __ror__(self, other: Any) -> _FakeDataType:
        return self.__or__(other)


class _FakeEvent:
    """Minimal event stub that supports ``+=`` for registering callbacks."""

    def __init__(self) -> None:
        self._handlers: list[Any] = []

    def __iadd__(self, handler: Any) -> _FakeEvent:
        self._handlers.append(handler)
        return self

    def __isub__(self, handler: Any) -> _FakeEvent:
        with contextlib.suppress(ValueError):
            self._handlers.remove(handler)
        return self


def _build_fake_rithmic_module(
    connect_raises: Exception | None = None,
    subscribe_raises: Exception | None = None,
) -> types.ModuleType:
    """Build a fake ``async_rithmic`` module with controllable behaviour."""
    mod = types.ModuleType("async_rithmic")

    class FakeRithmicClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._connected = True
            self.on_tick = _FakeEvent()
            self.on_order_book = _FakeEvent()

        async def connect(self, infra_type=None, **kwargs):
            if connect_raises is not None:
                raise connect_raises

        async def disconnect(self, **kwargs):
            pass

        async def subscribe_to_market_data(self, symbol, exchange=None, data_type=None):
            if subscribe_raises is not None:
                raise subscribe_raises

        async def get_front_month_contract(self, symbol):
            return symbol

    mod.RithmicClient = FakeRithmicClient  # type: ignore[attr-defined]
    mod.SysInfraType = _FakeSysInfraType  # type: ignore[attr-defined]
    mod.Gateway = _FakeGateway  # type: ignore[attr-defined]
    mod.DataType = _FakeDataType  # type: ignore[attr-defined]
    return mod


def _install_fake_rithmic(
    connect_raises: Exception | None = None,
    subscribe_raises: Exception | None = None,
) -> types.ModuleType:
    """Install a fake async_rithmic into sys.modules and return it."""
    mod = _build_fake_rithmic_module(connect_raises, subscribe_raises)
    sys.modules["async_rithmic"] = mod
    return mod


# ---------------------------------------------------------------------------
# Install the default fake module on first load, then import the client
# ---------------------------------------------------------------------------
_install_fake_rithmic()

import lib.integrations.rithmic_client as _rc_mod  # noqa: E402

# Clear the gateway map cache so it picks up our fake Gateway enum
_rc_mod._GATEWAY_MAP = {}


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_manager():
    """Return a fresh RithmicStreamManager instance."""
    from lib.integrations.rithmic_client import RithmicStreamManager

    return RithmicStreamManager()


def _make_config(
    key: str = "test_key",
    label: str = "Test Account",
    username: str = "user1",
    password: str = "pass1",
    gateway: str = "Chicago",
) -> Any:
    """Build a RithmicAccountConfig with credentials set."""
    from lib.integrations.rithmic_client import RithmicAccountConfig

    cfg = RithmicAccountConfig(key=key, label=label, gateway=gateway)
    cfg.set_credentials(username, password)
    return cfg


def _make_order_event(
    order_id: str = "ORD001",
    status: str = "filled",
    fill_price: float | None = 5000.0,
    fill_qty: int | None = 2,
    symbol: str = "ESZ4",
    timestamp: str = "2025-01-01T10:00:00",
) -> MagicMock:
    """Build a mock order event object with getattr-compatible attributes."""
    e = MagicMock()
    e.order_id = order_id
    e.status = status
    e.fill_price = fill_price
    e.fill_qty = fill_qty
    e.symbol = symbol
    e.timestamp = timestamp
    # Fallback attributes that _process_order_event checks via getattr
    e.id = None
    e.order_status = None
    e.state = None
    e.avg_fill_price = None
    e.filled_qty = None
    e.security_code = None
    e.update_time = None
    return e


# ===========================================================================
# Tests: __init__ state
# ===========================================================================


class TestStreamManagerInit:
    """Verify the initial state of a freshly constructed RithmicStreamManager."""

    def test_initially_not_connected(self):
        mgr = _make_manager()
        assert mgr._connected is False

    def test_initially_no_client(self):
        mgr = _make_manager()
        assert mgr._client is None

    def test_initially_empty_subscriptions(self):
        mgr = _make_manager()
        assert len(mgr._subscribed_symbols) == 0

    def test_initially_no_reconnect_task(self):
        mgr = _make_manager()
        assert mgr._reconnect_task is None

    def test_initially_empty_bar_state(self):
        mgr = _make_manager()
        assert mgr._bar_state == {}

    def test_initially_empty_order_states(self):
        mgr = _make_manager()
        assert mgr._order_states == {}

    def test_initially_pnl_not_connected(self):
        mgr = _make_manager()
        assert mgr._pnl_connected is False

    def test_initially_order_not_connected(self):
        mgr = _make_manager()
        assert mgr._order_connected is False

    def test_initially_history_not_connected(self):
        mgr = _make_manager()
        assert mgr._history_connected is False

    def test_is_pnl_connected_false_initially(self):
        mgr = _make_manager()
        assert mgr.is_pnl_connected is False

    def test_is_order_connected_false_initially(self):
        mgr = _make_manager()
        assert mgr.is_order_connected is False

    def test_is_history_connected_false_initially(self):
        mgr = _make_manager()
        assert mgr.is_history_connected is False

    def test_is_live_false_when_env_not_set(self):
        """is_live() requires RITHMIC_LIVE_DATA=1 AND _connected."""
        mgr = _make_manager()
        # Even if connected, env var is not set
        mgr._connected = True
        with patch.dict(os.environ, {"RITHMIC_LIVE_DATA": "0"}):
            assert mgr.is_live() is False

    def test_is_live_false_when_not_connected(self):
        mgr = _make_manager()
        with patch.dict(os.environ, {"RITHMIC_LIVE_DATA": "1"}):
            assert mgr.is_live() is False

    def test_no_config_initially(self):
        mgr = _make_manager()
        assert mgr._config is None


# ===========================================================================
# Tests: start() — successful connection
# ===========================================================================


class TestStreamManagerStartSuccess:
    """Test start() when async_rithmic connects successfully."""

    @pytest.fixture(autouse=True)
    def _setup_fake_rithmic(self):
        """Ensure a working fake async_rithmic is installed for each test."""
        _install_fake_rithmic()
        _rc_mod._GATEWAY_MAP = {}
        yield

    @pytest.mark.asyncio
    async def test_start_returns_true_on_success(self):
        mgr = _make_manager()
        cfg = _make_config()
        result = await mgr.start(cfg)
        assert result is True

    @pytest.mark.asyncio
    async def test_start_sets_connected_flag(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        assert mgr._connected is True

    @pytest.mark.asyncio
    async def test_start_stores_client_instance(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        assert mgr._client is not None

    @pytest.mark.asyncio
    async def test_start_saves_config(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        assert mgr._config is cfg

    @pytest.mark.asyncio
    async def test_is_live_true_when_env_and_connected(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        with patch.dict(os.environ, {"RITHMIC_LIVE_DATA": "1"}):
            assert mgr.is_live() is True

    @pytest.mark.asyncio
    async def test_start_with_different_gateway(self):
        mgr = _make_manager()
        cfg = _make_config(gateway="Sydney")
        result = await mgr.start(cfg)
        assert result is True

    @pytest.mark.asyncio
    async def test_multiple_start_calls_safe(self):
        """Calling start() multiple times should not crash."""
        mgr = _make_manager()
        cfg = _make_config()
        ok1 = await mgr.start(cfg)
        ok2 = await mgr.start(cfg)
        assert ok1 is True
        assert ok2 is True
        assert mgr._connected is True


# ===========================================================================
# Tests: start() — failure cases
# ===========================================================================


class TestStreamManagerStartFailure:
    """Test start() when credentials are missing or connections fail."""

    @pytest.fixture(autouse=True)
    def _setup_fake_rithmic(self):
        _install_fake_rithmic()
        _rc_mod._GATEWAY_MAP = {}
        yield

    @pytest.mark.asyncio
    async def test_no_credentials_returns_false(self):
        mgr = _make_manager()
        from lib.integrations.rithmic_client import RithmicAccountConfig

        cfg = RithmicAccountConfig(key="k", label="L")
        # No credentials set
        result = await mgr.start(cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_credentials_stays_disconnected(self):
        mgr = _make_manager()
        from lib.integrations.rithmic_client import RithmicAccountConfig

        cfg = RithmicAccountConfig(key="k", label="L")
        await mgr.start(cfg)
        assert mgr._connected is False

    @pytest.mark.asyncio
    async def test_empty_username_returns_false(self):
        mgr = _make_manager()
        from lib.integrations.rithmic_client import RithmicAccountConfig

        cfg = RithmicAccountConfig(key="k", label="L")
        cfg.set_credentials("", "somepass")
        result = await mgr.start(cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_password_returns_false(self):
        mgr = _make_manager()
        from lib.integrations.rithmic_client import RithmicAccountConfig

        cfg = RithmicAccountConfig(key="k", label="L")
        cfg.set_credentials("someuser", "")
        result = await mgr.start(cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_import_error_returns_false(self):
        """If async_rithmic is not importable, start() returns False gracefully."""
        # Break the module
        broken = types.ModuleType("async_rithmic")
        # Don't set RithmicClient or SysInfraType → import will fail
        sys.modules["async_rithmic"] = broken
        _rc_mod._GATEWAY_MAP = {}

        mgr = _make_manager()
        cfg = _make_config()
        result = await mgr.start(cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_timeout_all_retries_returns_false(self):
        """If every connect attempt times out, start() eventually returns False."""
        _install_fake_rithmic(connect_raises=TimeoutError("timed out"))
        _rc_mod._GATEWAY_MAP = {}

        mgr = _make_manager()
        cfg = _make_config()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await mgr.start(cfg)
        assert result is False
        assert mgr._connected is False

    @pytest.mark.asyncio
    async def test_connect_exception_all_retries_returns_false(self):
        """If every attempt raises, start() returns False after retries."""
        _install_fake_rithmic(connect_raises=ConnectionRefusedError("refused"))
        _rc_mod._GATEWAY_MAP = {}

        mgr = _make_manager()
        cfg = _make_config()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await mgr.start(cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_exception_client_stays_none(self):
        _install_fake_rithmic(connect_raises=OSError("network error"))
        _rc_mod._GATEWAY_MAP = {}

        mgr = _make_manager()
        cfg = _make_config()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await mgr.start(cfg)
        assert mgr._client is None


# ===========================================================================
# Tests: stop()
# ===========================================================================


class TestStreamManagerStop:
    """Test graceful disconnection and cleanup."""

    @pytest.fixture(autouse=True)
    def _setup_fake_rithmic(self):
        _install_fake_rithmic()
        _rc_mod._GATEWAY_MAP = {}
        yield

    @pytest.mark.asyncio
    async def test_stop_clears_connected_flag(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        assert mgr._connected is True
        await mgr.stop()
        assert mgr._connected is False

    @pytest.mark.asyncio
    async def test_stop_clears_client(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.stop()
        assert mgr._client is None

    @pytest.mark.asyncio
    async def test_stop_when_never_connected_is_safe(self):
        """Calling stop() without ever connecting should not raise."""
        mgr = _make_manager()
        await mgr.stop()
        assert mgr._connected is False

    @pytest.mark.asyncio
    async def test_stop_multiple_times_is_safe(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.stop()
        await mgr.stop()
        await mgr.stop()
        assert mgr._connected is False

    @pytest.mark.asyncio
    async def test_stop_cancels_reconnect_task(self):
        """If a reconnect task is pending, stop() should cancel it."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)

        async def _long_task():
            await asyncio.sleep(3600)

        mgr._reconnect_task = asyncio.create_task(_long_task())
        await mgr.stop()
        assert mgr._reconnect_task is None or mgr._reconnect_task.done()

    @pytest.mark.asyncio
    async def test_stop_after_start_makes_is_live_false(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        with patch.dict(os.environ, {"RITHMIC_LIVE_DATA": "1"}):
            assert mgr.is_live() is True
        await mgr.stop()
        with patch.dict(os.environ, {"RITHMIC_LIVE_DATA": "1"}):
            assert mgr.is_live() is False


# ===========================================================================
# Tests: subscribe_symbols()
# ===========================================================================


class TestSubscribeSymbols:
    """Test market data subscription management."""

    @pytest.fixture(autouse=True)
    def _setup_fake_rithmic(self):
        _install_fake_rithmic()
        _rc_mod._GATEWAY_MAP = {}
        yield

    @pytest.mark.asyncio
    async def test_subscribe_adds_to_set(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.subscribe_symbols(["ESZ4", "NQZ4"])
        assert "ESZ4" in mgr._subscribed_symbols
        assert "NQZ4" in mgr._subscribed_symbols

    @pytest.mark.asyncio
    async def test_subscribe_not_connected_no_add(self):
        """Subscribing when not connected should not add symbols."""
        mgr = _make_manager()
        await mgr.subscribe_symbols(["ESZ4"])
        assert "ESZ4" not in mgr._subscribed_symbols

    @pytest.mark.asyncio
    async def test_subscribe_multiple_symbols(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        syms = ["ESZ4", "NQZ4", "GCMAIN", "CLMAIN", "6EZ4"]
        await mgr.subscribe_symbols(syms)
        for s in syms:
            assert s in mgr._subscribed_symbols

    @pytest.mark.asyncio
    async def test_subscribe_deduplicates(self):
        """Subscribing the same symbol multiple times should store it once."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.subscribe_symbols(["ESZ4", "ESZ4", "ESZ4"])
        assert list(mgr._subscribed_symbols).count("ESZ4") == 1

    @pytest.mark.asyncio
    async def test_subscribe_empty_list_is_safe(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.subscribe_symbols([])
        assert len(mgr._subscribed_symbols) == 0

    @pytest.mark.asyncio
    async def test_subscribe_error_on_symbol_does_not_raise(self):
        """If subscribing one symbol fails, the method completes without raising."""
        _install_fake_rithmic(subscribe_raises=RuntimeError("sub failed"))
        _rc_mod._GATEWAY_MAP = {}

        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        # Should not raise
        await mgr.subscribe_symbols(["ESZ4", "NQZ4"])
        # Symbols won't be in set because subscribe raised
        assert "ESZ4" not in mgr._subscribed_symbols

    @pytest.mark.asyncio
    async def test_subscribe_adds_incrementally(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.subscribe_symbols(["ESZ4"])
        await mgr.subscribe_symbols(["NQZ4"])
        assert "ESZ4" in mgr._subscribed_symbols
        assert "NQZ4" in mgr._subscribed_symbols
        assert len(mgr._subscribed_symbols) == 2


# ===========================================================================
# Tests: reconnect()
# ===========================================================================


class TestReconnect:
    """Test background reconnection with re-subscription."""

    @pytest.fixture(autouse=True)
    def _setup_fake_rithmic(self):
        _install_fake_rithmic()
        _rc_mod._GATEWAY_MAP = {}
        yield

    @pytest.mark.asyncio
    async def test_reconnect_re_establishes_connection(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.stop()
        assert mgr._connected is False
        await mgr.reconnect(cfg)
        assert mgr._connected is True

    @pytest.mark.asyncio
    async def test_reconnect_re_subscribes_symbols(self):
        """Reconnect should re-subscribe to previously subscribed symbols."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.subscribe_symbols(["ESZ4", "NQZ4"])

        # Simulate disconnect
        async with mgr._lock:
            mgr._connected = False
            mgr._client = None

        await mgr.reconnect(cfg)

        assert mgr._connected is True
        assert "ESZ4" in mgr._subscribed_symbols
        assert "NQZ4" in mgr._subscribed_symbols

    @pytest.mark.asyncio
    async def test_reconnect_with_no_prior_subscriptions(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.stop()
        # No subscriptions were made
        await mgr.reconnect(cfg)
        assert mgr._connected is True
        assert len(mgr._subscribed_symbols) == 0

    @pytest.mark.asyncio
    async def test_reconnect_handles_cancelled_error(self):
        """reconnect() should propagate CancelledError cleanly."""
        mgr = _make_manager()
        cfg = _make_config()

        with (
            patch.object(mgr, "start", new_callable=AsyncMock, side_effect=asyncio.CancelledError),
            pytest.raises(asyncio.CancelledError),
        ):
            await mgr.reconnect(cfg)

    @pytest.mark.asyncio
    async def test_reconnect_handles_start_failure(self):
        """If start() fails during reconnect, reconnect completes without raising."""
        mgr = _make_manager()
        cfg = _make_config()
        with patch.object(mgr, "start", new_callable=AsyncMock, return_value=False):
            await mgr.reconnect(cfg)  # should not raise
        assert mgr._connected is False

    @pytest.mark.asyncio
    async def test_reconnect_handles_generic_exception(self):
        """If start() raises something unexpected, reconnect does not propagate it."""
        mgr = _make_manager()
        cfg = _make_config()
        with patch.object(mgr, "start", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            # Should NOT raise (caught in reconnect)
            await mgr.reconnect(cfg)


# ===========================================================================
# Tests: trigger_reconnect()
# ===========================================================================


class TestTriggerReconnect:
    """Test the sync entry point for scheduling reconnect."""

    @pytest.fixture(autouse=True)
    def _setup_fake_rithmic(self):
        _install_fake_rithmic()
        _rc_mod._GATEWAY_MAP = {}
        yield

    def test_trigger_reconnect_no_config_no_crash(self):
        """trigger_reconnect with no config and no stored config is a no-op."""
        mgr = _make_manager()
        mgr._config = None
        mgr.trigger_reconnect()  # should not raise

    def test_trigger_reconnect_schedules_task(self):
        """trigger_reconnect should create an asyncio task on the running loop."""
        mgr = _make_manager()
        cfg = _make_config()

        async def _run():
            mgr._config = cfg
            mgr.trigger_reconnect(cfg)
            await asyncio.sleep(0.01)
            task = mgr._reconnect_task
            assert task is not None
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        asyncio.run(_run())

    def test_trigger_reconnect_uses_stored_config(self):
        """trigger_reconnect with no arg uses the stored self._config."""
        mgr = _make_manager()
        cfg = _make_config()
        mgr._config = cfg

        async def _run():
            mgr.trigger_reconnect()
            await asyncio.sleep(0.01)
            task = mgr._reconnect_task
            assert task is not None
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        asyncio.run(_run())

    def test_trigger_reconnect_dedup_when_task_running(self):
        """If a reconnect task is already running, a second call should not create another."""
        mgr = _make_manager()
        cfg = _make_config()

        async def _run():
            mgr._config = cfg

            # Create a long-running fake task so it's still pending when we check
            async def _slow_reconnect(_cfg):
                await asyncio.sleep(3600)

            with patch.object(mgr, "reconnect", _slow_reconnect):
                mgr.trigger_reconnect(cfg)
                await asyncio.sleep(0.01)
                first_task = mgr._reconnect_task
                assert first_task is not None and not first_task.done()
                # Trigger again while first is still running
                mgr.trigger_reconnect(cfg)
                assert mgr._reconnect_task is first_task  # same task, deduped
                first_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await first_task

        asyncio.run(_run())


# ===========================================================================
# Tests: _update_bar() — 1-minute bar aggregation
# ===========================================================================


class TestUpdateBar:
    """Test the in-memory 1-minute bar aggregation logic."""

    def test_first_tick_returns_none(self):
        mgr = _make_manager()
        result = mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=1700000060)
        assert result is None

    def test_first_tick_creates_bar_state(self):
        mgr = _make_manager()
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=1700000060)
        assert "ESZ4" in mgr._bar_state
        state = mgr._bar_state["ESZ4"]
        assert state["open"] == 5000.0
        assert state["high"] == 5000.0
        assert state["low"] == 5000.0
        assert state["close"] == 5000.0
        assert state["volume"] == 10

    def test_same_minute_updates_close(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=5050.0, volume=5, ts_epoch=ts + 30)
        state = mgr._bar_state["ESZ4"]
        assert state["close"] == 5050.0

    def test_same_minute_updates_high(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=5050.0, volume=5, ts_epoch=ts + 30)
        state = mgr._bar_state["ESZ4"]
        assert state["high"] == 5050.0

    def test_same_minute_updates_low(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=4980.0, volume=5, ts_epoch=ts + 15)
        state = mgr._bar_state["ESZ4"]
        assert state["low"] == 4980.0

    def test_same_minute_open_unchanged(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=5050.0, volume=5, ts_epoch=ts + 30)
        assert mgr._bar_state["ESZ4"]["open"] == 5000.0

    def test_same_minute_volume_accumulates(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=5050.0, volume=5, ts_epoch=ts + 30)
        assert mgr._bar_state["ESZ4"]["volume"] == 15

    def test_same_minute_returns_none(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        result = mgr._update_bar("ESZ4", price=5050.0, volume=5, ts_epoch=ts + 30)
        assert result is None

    def test_minute_rollover_returns_completed_bar(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        completed = mgr._update_bar("ESZ4", price=5100.0, volume=3, ts_epoch=ts + 60)
        assert completed is not None
        assert isinstance(completed, dict)

    def test_completed_bar_symbol(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        completed = mgr._update_bar("ESZ4", price=5100.0, volume=3, ts_epoch=ts + 60)
        assert completed["symbol"] == "ESZ4"

    def test_completed_bar_has_open(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        completed = mgr._update_bar("ESZ4", price=5100.0, volume=3, ts_epoch=ts + 60)
        assert completed["open"] == 5000.0

    def test_completed_bar_has_high_low(self):
        mgr = _make_manager()
        # Use a timestamp aligned to a minute boundary so all ticks fit in one minute
        ts = 1700000040 - (1700000040 % 60)  # align to minute start
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=5025.0, volume=5, ts_epoch=ts + 15)
        mgr._update_bar("ESZ4", price=4990.0, volume=5, ts_epoch=ts + 30)
        completed = mgr._update_bar("ESZ4", price=5200.0, volume=1, ts_epoch=ts + 60)
        assert completed is not None
        assert completed["high"] == 5025.0
        assert completed["low"] == 4990.0

    def test_completed_bar_close_is_last_price_in_minute(self):
        mgr = _make_manager()
        # Align to minute boundary so ts and ts+50 share the same minute
        ts = 1700000040 - (1700000040 % 60)  # minute start
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=5010.0, volume=3, ts_epoch=ts + 50)
        completed = mgr._update_bar("ESZ4", price=5200.0, volume=1, ts_epoch=ts + 60)
        assert completed is not None
        assert completed["close"] == 5010.0

    def test_completed_bar_volume_sum(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=5010.0, volume=5, ts_epoch=ts + 30)
        completed = mgr._update_bar("ESZ4", price=5100.0, volume=3, ts_epoch=ts + 60)
        assert completed["volume"] == 15  # 10 + 5 from the completed bar

    def test_completed_bar_has_ts_string(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        completed = mgr._update_bar("ESZ4", price=5100.0, volume=3, ts_epoch=ts + 60)
        assert "ts" in completed
        assert isinstance(completed["ts"], str)

    def test_rollover_opens_new_bar(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("ESZ4", price=5100.0, volume=3, ts_epoch=ts + 60)
        # New bar should be opened with the new minute's tick
        state = mgr._bar_state["ESZ4"]
        assert state["open"] == 5100.0
        assert state["close"] == 5100.0
        assert state["volume"] == 3

    def test_different_symbols_independent(self):
        mgr = _make_manager()
        ts = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=ts)
        mgr._update_bar("NQZ4", price=20000.0, volume=2, ts_epoch=ts)
        assert mgr._bar_state["ESZ4"]["close"] == 5000.0
        assert mgr._bar_state["NQZ4"]["close"] == 20000.0

    def test_many_ticks_high_is_maximum(self):
        mgr = _make_manager()
        ts = 1700000060
        prices = [5000.0, 5010.0, 5030.0, 5015.0, 5020.0, 5040.0, 5025.0]
        for i, p in enumerate(prices):
            mgr._update_bar("ESZ4", price=p, volume=1, ts_epoch=ts + i)
        assert mgr._bar_state["ESZ4"]["high"] == 5040.0

    def test_many_ticks_low_is_minimum(self):
        mgr = _make_manager()
        ts = 1700000060
        prices = [5000.0, 4990.0, 4980.0, 4995.0, 5000.0, 4970.0, 4985.0]
        for i, p in enumerate(prices):
            mgr._update_bar("ESZ4", price=p, volume=1, ts_epoch=ts + i)
        assert mgr._bar_state["ESZ4"]["low"] == 4970.0

    def test_volume_accumulates_across_many_ticks(self):
        mgr = _make_manager()
        ts = 1700000060
        for i in range(10):
            mgr._update_bar("ESZ4", price=5000.0 + i, volume=100, ts_epoch=ts + i)
        assert mgr._bar_state["ESZ4"]["volume"] == 1000

    def test_multiple_rollovers_sequence(self):
        """Multiple minute rollovers produce correct completed bars."""
        mgr = _make_manager()
        base = 1700000060  # minute 0

        # Minute 0
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=base)
        mgr._update_bar("ESZ4", price=5010.0, volume=5, ts_epoch=base + 30)

        # Minute 1 — triggers rollover of minute 0
        bar1 = mgr._update_bar("ESZ4", price=5100.0, volume=3, ts_epoch=base + 60)
        assert bar1 is not None
        assert bar1["open"] == 5000.0
        assert bar1["close"] == 5010.0

        # More ticks in minute 1
        mgr._update_bar("ESZ4", price=5120.0, volume=2, ts_epoch=base + 90)

        # Minute 2 — triggers rollover of minute 1
        bar2 = mgr._update_bar("ESZ4", price=5200.0, volume=1, ts_epoch=base + 120)
        assert bar2 is not None
        assert bar2["open"] == 5100.0
        assert bar2["close"] == 5120.0
        assert bar2["volume"] == 5  # 3 + 2

    def test_rollover_skipping_minutes(self):
        """If a tick arrives 2+ minutes later, the old bar is still completed."""
        mgr = _make_manager()
        base = 1700000060
        mgr._update_bar("ESZ4", price=5000.0, volume=10, ts_epoch=base)
        # Skip several minutes
        completed = mgr._update_bar("ESZ4", price=5100.0, volume=1, ts_epoch=base + 300)
        assert completed is not None
        assert completed["open"] == 5000.0


# ===========================================================================
# Tests: _process_order_event()
# ===========================================================================


class TestProcessOrderEvent:
    """Test ORDER_PLANT event handling and in-memory state tracking."""

    @pytest.mark.asyncio
    async def test_updates_order_states(self):
        mgr = _make_manager()
        event = _make_order_event(order_id="ORD001", status="filled")
        await mgr._process_order_event(event)
        assert "ORD001" in mgr._order_states

    @pytest.mark.asyncio
    async def test_order_state_has_correct_status(self):
        mgr = _make_manager()
        event = _make_order_event(order_id="ORD001", status="filled")
        await mgr._process_order_event(event)
        assert mgr._order_states["ORD001"]["status"] == "filled"

    @pytest.mark.asyncio
    async def test_order_state_fill_price(self):
        mgr = _make_manager()
        event = _make_order_event(order_id="ORD001", fill_price=5000.0)
        await mgr._process_order_event(event)
        assert mgr._order_states["ORD001"]["fill_price"] == 5000.0

    @pytest.mark.asyncio
    async def test_order_state_fill_qty(self):
        mgr = _make_manager()
        event = _make_order_event(order_id="ORD001", fill_qty=3)
        await mgr._process_order_event(event)
        assert mgr._order_states["ORD001"]["fill_qty"] == 3

    @pytest.mark.asyncio
    async def test_order_state_symbol(self):
        mgr = _make_manager()
        event = _make_order_event(order_id="ORD001", symbol="NQZ4")
        await mgr._process_order_event(event)
        assert mgr._order_states["ORD001"]["symbol"] == "NQZ4"

    @pytest.mark.asyncio
    async def test_status_lowercased(self):
        mgr = _make_manager()
        event = _make_order_event(status="FILLED")
        await mgr._process_order_event(event)
        state = mgr._order_states[event.order_id]
        assert state["status"] == "filled"

    @pytest.mark.asyncio
    async def test_status_transition_tracked(self):
        """Multiple events for the same order update the status."""
        mgr = _make_manager()
        event1 = _make_order_event(order_id="ORD002", status="pending")
        event2 = _make_order_event(order_id="ORD002", status="filled", fill_price=5010.0)
        await mgr._process_order_event(event1)
        assert mgr._order_states["ORD002"]["status"] == "pending"
        await mgr._process_order_event(event2)
        assert mgr._order_states["ORD002"]["status"] == "filled"
        assert mgr._order_states["ORD002"]["fill_price"] == 5010.0

    @pytest.mark.asyncio
    async def test_multiple_distinct_orders(self):
        mgr = _make_manager()
        for i in range(5):
            e = _make_order_event(order_id=f"ORD{i:03d}", status="pending")
            await mgr._process_order_event(e)
        assert len(mgr._order_states) == 5

    @pytest.mark.asyncio
    async def test_none_fill_fields_stored_as_none(self):
        mgr = _make_manager()
        e = _make_order_event(
            order_id="ORD_NOFILL",
            status="pending",
            fill_price=None,
            fill_qty=None,
        )
        await mgr._process_order_event(e)
        assert mgr._order_states["ORD_NOFILL"]["fill_price"] is None
        assert mgr._order_states["ORD_NOFILL"]["fill_qty"] is None

    @pytest.mark.asyncio
    async def test_unknown_order_id_handled(self):
        """Event with no order_id attribute should use 'unknown'."""
        mgr = _make_manager()
        e = _make_order_event(order_id=None, status="cancelled", symbol="")
        e.order_id = None
        e.id = None
        await mgr._process_order_event(e)
        assert "unknown" in mgr._order_states

    @pytest.mark.asyncio
    async def test_order_state_has_timestamp(self):
        mgr = _make_manager()
        event = _make_order_event(timestamp="2025-06-15T14:30:00")
        await mgr._process_order_event(event)
        state = mgr._order_states[event.order_id]
        assert state["ts"] == "2025-06-15T14:30:00"

    @pytest.mark.asyncio
    async def test_full_order_lifecycle(self):
        """Simulate a complete order lifecycle: new → open → partially_filled → filled."""
        mgr = _make_manager()
        oid = "ORD_LIFECYCLE"

        for status in ["new", "open", "partially_filled", "filled"]:
            e = _make_order_event(
                order_id=oid,
                status=status,
                fill_price=5000.0 if status == "filled" else None,
                fill_qty=2 if status in ("partially_filled", "filled") else None,
            )
            await mgr._process_order_event(e)

        final = mgr._order_states[oid]
        assert final["status"] == "filled"
        assert final["fill_price"] == 5000.0
        assert final["fill_qty"] == 2

    @pytest.mark.asyncio
    async def test_cancel_lifecycle(self):
        """Simulate: new → open → cancelled."""
        mgr = _make_manager()
        oid = "ORD_CANCEL"
        for status in ["new", "open", "cancelled"]:
            e = _make_order_event(order_id=oid, status=status)
            await mgr._process_order_event(e)
        assert mgr._order_states[oid]["status"] == "cancelled"


# ===========================================================================
# Tests: _set_plant_state() — non-Redis path
# ===========================================================================


class TestSetPlantState:
    """Verify _set_plant_state is a safe no-op when Redis is unavailable."""

    def test_set_plant_state_connected_no_crash(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        RithmicStreamManager._set_plant_state("ticker", "connected", gateway="Chicago")

    def test_set_plant_state_disconnected_no_crash(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        RithmicStreamManager._set_plant_state("ticker", "disconnected")

    def test_set_plant_state_connecting_no_crash(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        RithmicStreamManager._set_plant_state("ticker", "connecting", gateway="Chicago")

    def test_set_plant_state_error_no_crash(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        RithmicStreamManager._set_plant_state("pnl", "error", error="connection refused")

    def test_set_plant_state_all_plants(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        for plant in ["ticker", "pnl", "history", "order"]:
            RithmicStreamManager._set_plant_state(plant, "connected")

    def test_set_plant_state_empty_strings(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        RithmicStreamManager._set_plant_state("", "", gateway="", error="")


# ===========================================================================
# Tests: get_plant_states() — non-Redis path
# ===========================================================================


class TestGetPlantStates:
    """Verify get_plant_states returns a dict when Redis is unavailable."""

    def test_returns_dict(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        result = RithmicStreamManager.get_plant_states()
        assert isinstance(result, dict)

    def test_values_are_dicts(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        result = RithmicStreamManager.get_plant_states()
        for v in result.values():
            assert isinstance(v, dict)


# ===========================================================================
# Tests: Connection properties
# ===========================================================================


class TestConnectionProperties:
    """Test the is_*_connected property shortcuts."""

    def test_is_pnl_connected_reflects_flag(self):
        mgr = _make_manager()
        assert mgr.is_pnl_connected is False
        mgr._pnl_connected = True
        assert mgr.is_pnl_connected is True

    def test_is_order_connected_reflects_flag(self):
        mgr = _make_manager()
        assert mgr.is_order_connected is False
        mgr._order_connected = True
        assert mgr.is_order_connected is True

    def test_is_history_connected_reflects_flag(self):
        mgr = _make_manager()
        assert mgr.is_history_connected is False
        mgr._history_connected = True
        assert mgr.is_history_connected is True

    @pytest.fixture(autouse=True)
    def _setup_fake_rithmic(self):
        _install_fake_rithmic()
        _rc_mod._GATEWAY_MAP = {}
        yield

    @pytest.mark.asyncio
    async def test_is_live_after_connect_with_env(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        with patch.dict(os.environ, {"RITHMIC_LIVE_DATA": "1"}):
            assert mgr.is_live() is True

    @pytest.mark.asyncio
    async def test_is_live_after_connect_without_env(self):
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        with patch.dict(os.environ, {"RITHMIC_LIVE_DATA": "0"}):
            assert mgr.is_live() is False


# ===========================================================================
# Tests: Full connect → subscribe → disconnect → reconnect lifecycle
# ===========================================================================


class TestFullLifecycle:
    """End-to-end integration tests verifying the complete connection lifecycle."""

    @pytest.fixture(autouse=True)
    def _setup_fake_rithmic(self):
        _install_fake_rithmic()
        _rc_mod._GATEWAY_MAP = {}
        yield

    @pytest.mark.asyncio
    async def test_connect_subscribe_stop_reconnect(self):
        """Full lifecycle: connect → subscribe → stop → reconnect → verify."""
        mgr = _make_manager()
        cfg = _make_config()

        # Connect
        ok = await mgr.start(cfg)
        assert ok is True
        assert mgr._connected is True

        # Subscribe
        await mgr.subscribe_symbols(["ESZ4", "NQZ4"])
        assert "ESZ4" in mgr._subscribed_symbols

        # Stop
        await mgr.stop()
        assert mgr._connected is False

        # Reconnect
        await mgr.reconnect(cfg)
        assert mgr._connected is True
        assert "ESZ4" in mgr._subscribed_symbols
        assert "NQZ4" in mgr._subscribed_symbols

    @pytest.mark.asyncio
    async def test_bar_state_persists_across_reconnect(self):
        """Bar aggregation state should persist across connect/disconnect cycles."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)

        # Build some bar state
        mgr._update_bar("ESZ4", 5000.0, 10, 1700000060)
        mgr._update_bar("ESZ4", 5010.0, 5, 1700000080)

        await mgr.stop()
        await mgr.start(cfg)

        assert "ESZ4" in mgr._bar_state
        assert mgr._bar_state["ESZ4"]["high"] == 5010.0

    @pytest.mark.asyncio
    async def test_order_states_persist_across_reconnect(self):
        """Order states in memory should persist across reconnect."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)

        e = _make_order_event(order_id="ORD_PERSIST", status="pending")
        await mgr._process_order_event(e)

        await mgr.stop()
        await mgr.reconnect(cfg)

        assert "ORD_PERSIST" in mgr._order_states
        assert mgr._order_states["ORD_PERSIST"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_bar_aggregation_then_order_events(self):
        """Bar aggregation and order processing are independent systems."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)

        # Bar ticks
        mgr._update_bar("ESZ4", 5000.0, 10, 1700000060)
        mgr._update_bar("ESZ4", 5010.0, 5, 1700000080)

        # Order events
        e = _make_order_event(order_id="ORD_MIX", status="filled", fill_price=5005.0)
        await mgr._process_order_event(e)

        # Both systems have their data
        assert "ESZ4" in mgr._bar_state
        assert "ORD_MIX" in mgr._order_states
        assert mgr._bar_state["ESZ4"]["close"] == 5010.0
        assert mgr._order_states["ORD_MIX"]["fill_price"] == 5005.0

    @pytest.mark.asyncio
    async def test_subscribe_bar_rollover_order_fill(self):
        """Simulate realistic flow: subscribe, get ticks producing a bar, then an order fill."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.subscribe_symbols(["ESZ4"])

        # Align to minute boundary so all ticks within +0..+59 share one minute
        ts = 1700000040 - (1700000040 % 60)  # minute start
        # Ticks in minute 0
        mgr._update_bar("ESZ4", 5000.0, 100, ts)
        mgr._update_bar("ESZ4", 5005.0, 50, ts + 10)
        mgr._update_bar("ESZ4", 4995.0, 80, ts + 30)
        mgr._update_bar("ESZ4", 5002.0, 60, ts + 55)

        # Tick in minute 1 — completes minute 0 bar
        bar = mgr._update_bar("ESZ4", 5010.0, 20, ts + 60)
        assert bar is not None
        assert bar["open"] == 5000.0
        assert bar["high"] == 5005.0
        assert bar["low"] == 4995.0
        assert bar["close"] == 5002.0
        assert bar["volume"] == 290  # 100+50+80+60

        # Meanwhile an order fill comes through
        fill_event = _make_order_event(
            order_id="ORD_FILL",
            status="filled",
            fill_price=5010.0,
            fill_qty=1,
            symbol="ESZ4",
        )
        await mgr._process_order_event(fill_event)

        assert mgr._order_states["ORD_FILL"]["fill_price"] == 5010.0
        assert mgr._order_states["ORD_FILL"]["status"] == "filled"

    @pytest.mark.asyncio
    async def test_concurrent_symbols_bar_aggregation(self):
        """Multiple symbols aggregate bars independently."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)

        ts = 1700000060
        # ESZ4 and NQZ4 at different prices
        mgr._update_bar("ESZ4", 5000.0, 10, ts)
        mgr._update_bar("NQZ4", 20000.0, 3, ts)
        mgr._update_bar("ESZ4", 5050.0, 5, ts + 30)
        mgr._update_bar("NQZ4", 19950.0, 2, ts + 30)

        # Rollover both
        es_bar = mgr._update_bar("ESZ4", 5100.0, 1, ts + 60)
        nq_bar = mgr._update_bar("NQZ4", 20100.0, 1, ts + 60)

        assert es_bar is not None
        assert nq_bar is not None
        assert es_bar["high"] == 5050.0
        assert nq_bar["low"] == 19950.0

    @pytest.mark.asyncio
    async def test_connect_disconnect_repeated(self):
        """Rapid connect/disconnect cycles should be safe."""
        mgr = _make_manager()
        cfg = _make_config()
        for _ in range(5):
            ok = await mgr.start(cfg)
            assert ok is True
            await mgr.stop()
            assert mgr._connected is False

    @pytest.mark.asyncio
    async def test_subscribe_after_reconnect_adds_new_symbols(self):
        """After reconnect, subscribing to new symbols should work."""
        mgr = _make_manager()
        cfg = _make_config()
        await mgr.start(cfg)
        await mgr.subscribe_symbols(["ESZ4"])
        await mgr.stop()
        await mgr.reconnect(cfg)
        await mgr.subscribe_symbols(["NQZ4"])
        assert "ESZ4" in mgr._subscribed_symbols
        assert "NQZ4" in mgr._subscribed_symbols


# ===========================================================================
# Tests: RithmicAccountConfig credential round-trips (supplementary)
# ===========================================================================


class TestAccountConfigSupplemental:
    """Additional credential and config tests beyond test_rithmic_account.py."""

    def test_config_gateway_stored(self):
        cfg = _make_config(gateway="Sydney")
        assert cfg.gateway == "Sydney"

    def test_config_label_stored(self):
        cfg = _make_config(label="My Account")
        assert cfg.label == "My Account"

    def test_config_key_stored(self):
        cfg = _make_config(key="acct_123")
        assert cfg.key == "acct_123"

    def test_credential_round_trip(self):
        cfg = _make_config(username="myuser", password="mypass123!")
        assert cfg.get_username() == "myuser"
        assert cfg.get_password() == "mypass123!"

    def test_empty_credentials_return_empty(self):
        from lib.integrations.rithmic_client import RithmicAccountConfig

        cfg = RithmicAccountConfig(key="k", label="L")
        assert cfg.get_username() == ""
        assert cfg.get_password() == ""

    def test_ui_dict_has_no_plaintext_password(self):
        cfg = _make_config(username="myuser", password="secret123")
        ui = cfg.to_ui_dict()
        # The UI dict should not contain the actual password
        assert "secret123" not in str(ui)

    def test_storage_dict_round_trip(self):
        cfg = _make_config(key="k1", label="Test", username="u1", password="p1")
        d = cfg.to_storage_dict()
        from lib.integrations.rithmic_client import RithmicAccountConfig

        cfg2 = RithmicAccountConfig.from_storage_dict(d)
        assert cfg2.key == "k1"
        assert cfg2.label == "Test"
        assert cfg2.get_username() == "u1"
        assert cfg2.get_password() == "p1"


# ===========================================================================
# Tests: _publish_bar_to_redis / _write_bar_to_postgres stubs
# ===========================================================================


class TestBarPublishing:
    """Verify publish/write helpers don't crash when deps are unavailable."""

    def test_publish_bar_to_redis_with_mock(self):
        """_publish_bar_to_redis should call lpush + ltrim on the Redis client."""
        from lib.integrations.rithmic_client import RithmicStreamManager

        bar = {
            "symbol": "ESZ4",
            "ts": "2025-01-01T10:00:00",
            "open": 5000.0,
            "high": 5010.0,
            "low": 4990.0,
            "close": 5005.0,
            "volume": 100,
        }
        mock_r = MagicMock()
        RithmicStreamManager._publish_bar_to_redis(bar, mock_r)
        mock_r.lpush.assert_called_once()
        mock_r.ltrim.assert_called_once()

    def test_publish_bar_to_redis_key_format(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        bar = {"symbol": "NQZ4", "ts": "2025-01-01T10:00:00", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
        mock_r = MagicMock()
        RithmicStreamManager._publish_bar_to_redis(bar, mock_r)
        key_arg = mock_r.lpush.call_args[0][0]
        assert key_arg == "bars:live:NQZ4"

    def test_publish_bar_to_redis_json_serializable(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        bar = {
            "symbol": "ESZ4",
            "ts": "2025-01-01T10:00:00",
            "open": 5000.0,
            "high": 5010.0,
            "low": 4990.0,
            "close": 5005.0,
            "volume": 100,
        }
        mock_r = MagicMock()
        RithmicStreamManager._publish_bar_to_redis(bar, mock_r)
        json_arg = mock_r.lpush.call_args[0][1]
        # Should be valid JSON
        parsed = json.loads(json_arg)
        assert parsed["symbol"] == "ESZ4"
        assert parsed["volume"] == 100

    def test_publish_bar_ltrim_cap(self):
        from lib.integrations.rithmic_client import RithmicStreamManager

        bar = {"symbol": "ESZ4", "ts": "", "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0}
        mock_r = MagicMock()
        RithmicStreamManager._publish_bar_to_redis(bar, mock_r)
        # Should trim to 500 entries
        ltrim_args = mock_r.ltrim.call_args[0]
        assert ltrim_args == ("bars:live:ESZ4", 0, 499)
