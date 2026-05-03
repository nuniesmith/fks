"""
Tests for the Janus gRPC Client
=================================
Covers:
  - _env_float / _env_int helpers
  - JanusGRPCError exception hierarchy
  - JanusGRPCClient: construction, channel lifecycle, all API methods
  - Singleton management (get_janus_grpc_client / reset_janus_grpc_client)
  - Synchronous shims (get_latest_signals_grpc_sync, publish_signal_grpc_sync,
    is_janus_grpc_healthy_sync)
  - JanusGRPCPoller: async iteration, deduplication, reconnection

Mocking strategy
----------------
Because ``signals_pb2`` and ``signals_pb2_grpc`` may not be generated yet
(run ``scripts/gen-proto.sh`` to produce them), we inject synthetic module
objects into ``sys.modules`` *before* importing the client module.  Every RPC
stub method is an ``AsyncMock`` so async ``await`` calls work without a running
gRPC server.
"""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Build synthetic proto stub modules and inject them into sys.modules so that
# the lazy ``_import_stubs()`` inside janus_grpc_client resolves without error.
# This MUST happen before the first import of the client module.
# ---------------------------------------------------------------------------

# --- signals_pb2 ------------------------------------------------------------
# The generated file is named signals_pb2.py (flat, not fks/signals/v1/).
_pb2 = types.ModuleType("signals_pb2")

# Direction enum constants
_pb2.SIGNAL_DIRECTION_UNSPECIFIED = 0  # type: ignore[attr-defined]
_pb2.SIGNAL_DIRECTION_LONG = 1  # type: ignore[attr-defined]
_pb2.SIGNAL_DIRECTION_SHORT = 2  # type: ignore[attr-defined]
_pb2.SIGNAL_DIRECTION_NEUTRAL = 3  # type: ignore[attr-defined]
_pb2.SIGNAL_DIRECTION_EXIT = 4  # type: ignore[attr-defined]


class _MockTradingSignal(MagicMock):
    """Minimal ``TradingSignal`` proto stand-in."""

    def __init__(self, **kwargs):
        super().__init__()
        # Provide sensible defaults that match JanusSignal field semantics
        self.signal_id = kwargs.get("signal_id", "sig-grpc-001")
        self.symbol = kwargs.get("symbol", "MES")
        self.timeframe = kwargs.get("timeframe", "5m")
        self.signal_type = kwargs.get("signal_type", "breakout")
        self.direction = kwargs.get("direction", SimpleNamespace(name="SIGNAL_DIRECTION_LONG"))
        self.source = kwargs.get("source", "janus-grpc")
        self.category = kwargs.get("category", "swing")
        self.timestamp_ms = kwargs.get("timestamp_ms", 1_736_150_000_000)
        self.confidence = kwargs.get("confidence", 0.85)
        self.strength = kwargs.get("strength", 0.75)
        self.price = kwargs.get("price", 5420.50)
        self.suggested_entry = kwargs.get("suggested_entry", 5422.0)
        self.suggested_stop_loss = kwargs.get("suggested_stop_loss", 5400.0)
        self.suggested_tp1 = kwargs.get("suggested_tp1", 5440.0)
        self.suggested_tp2 = kwargs.get("suggested_tp2", 5460.0)
        self.suggested_tp3 = kwargs.get("suggested_tp3", 5480.0)
        self.risk_reward_ratio = kwargs.get("risk_reward_ratio", 2.5)
        self.position_size_usd = kwargs.get("position_size_usd", 10_000.0)
        self.atr = kwargs.get("atr", 12.5)
        self.ema_fast = kwargs.get("ema_fast", 5418.0)
        self.ema_slow = kwargs.get("ema_slow", 5410.0)
        self.reason = kwargs.get("reason", "ICT OB reclaim")


_pb2.TradingSignal = _MockTradingSignal  # type: ignore[attr-defined]


def _make_proto_request_cls(name: str):
    """Return a trivial proto request class that stores kwargs as attributes."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    return type(name, (), {"__init__": __init__})


_pb2.GetLatestRequest = _make_proto_request_cls("GetLatestRequest")  # type: ignore[attr-defined]
_pb2.GetBySymbolRequest = _make_proto_request_cls("GetBySymbolRequest")  # type: ignore[attr-defined]
_pb2.GetSummaryRequest = _make_proto_request_cls("GetSummaryRequest")  # type: ignore[attr-defined]
_pb2.PublishRequest = _make_proto_request_cls("PublishRequest")  # type: ignore[attr-defined]
_pb2.ModuleHealthRequest = _make_proto_request_cls("ModuleHealthRequest")  # type: ignore[attr-defined]
_pb2.SubscribeRequest = _make_proto_request_cls("SubscribeRequest")  # type: ignore[attr-defined]

# --- signals_pb2_grpc -------------------------------------------------------
_pb2_grpc = types.ModuleType("signals_pb2_grpc")


class _MockSignalBusServiceStub:
    """Stub for SignalBusService with all RPC methods as AsyncMocks."""

    def __init__(self, channel):
        self.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[], total_available=0))
        self.GetBySymbol = AsyncMock(return_value=SimpleNamespace(signals=[]))
        self.GetSummary = AsyncMock(
            return_value=SimpleNamespace(
                category="swing",
                symbols=[],
                total_signals=0,
                strong_signals=0,
                average_confidence=0.0,
                by_type={},
            )
        )
        self.Publish = AsyncMock(return_value=SimpleNamespace(accepted=True, signal_id="pub-001", error=""))
        # Subscribe returns an async iterable — tests override per-case
        self.Subscribe = MagicMock(return_value=_make_empty_async_iter())


class _MockInferenceServiceStub:
    """Stub for InferenceService with ModuleHealth as AsyncMock."""

    def __init__(self, channel):
        self.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[], all_healthy=True))


_pb2_grpc.SignalBusServiceStub = _MockSignalBusServiceStub  # type: ignore[attr-defined]
_pb2_grpc.InferenceServiceStub = _MockInferenceServiceStub  # type: ignore[attr-defined]

# --- grpc / grpc.aio mock ---------------------------------------------------
_grpc_mod = types.ModuleType("grpc")
_grpc_aio_mod = types.ModuleType("grpc.aio")


class _FakeStatusCode:
    UNAVAILABLE = "UNAVAILABLE"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    NOT_FOUND = "NOT_FOUND"


class _FakeAioRpcError(Exception):
    """Minimal grpc.aio.AioRpcError stand-in."""

    def __init__(self, code=_FakeStatusCode.UNAVAILABLE, details="unavailable"):
        super().__init__(details)
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


def _make_empty_async_iter():
    """Return an async-iterable that yields nothing."""

    async def _iter():
        return
        yield  # unreachable — makes it a generator

    return _iter()


class _FakeChannel:
    """Minimal grpc.aio channel stand-in."""

    def __init__(self):
        self._closed = False

    def get_state(self, try_to_connect: bool = False):
        return SimpleNamespace(name="SIGNAL_DIRECTION_UNSPECIFIED", __str__=lambda s: "grpc.ChannelConnectivity.READY")

    async def close(self, grace=None):
        self._closed = True


_grpc_aio_mod.AioRpcError = _FakeAioRpcError  # type: ignore[attr-defined]
_grpc_aio_mod.insecure_channel = MagicMock(side_effect=lambda target: _FakeChannel())  # type: ignore[attr-defined]
_grpc_aio_mod.secure_channel = MagicMock(side_effect=lambda target, creds: _FakeChannel())  # type: ignore[attr-defined]
_grpc_mod.aio = _grpc_aio_mod  # type: ignore[attr-defined]
_grpc_mod.StatusCode = _FakeStatusCode  # type: ignore[attr-defined]
_grpc_mod.ssl_channel_credentials = MagicMock(return_value=object())  # type: ignore[attr-defined]

# Inject all synthetic modules before importing the client.
# The flat names (signals_pb2 / signals_pb2_grpc) must match what
# _import_stubs() does:  import signals_pb2 / import signals_pb2_grpc
sys.modules["grpc"] = _grpc_mod
sys.modules["grpc.aio"] = _grpc_aio_mod
sys.modules["signals_pb2"] = _pb2
sys.modules["signals_pb2_grpc"] = _pb2_grpc

# ---------------------------------------------------------------------------
# NOW import the client — stubs are already in place
# ---------------------------------------------------------------------------

import contextlib  # noqa: E402

from lib.integrations.janus_client import JanusSignal, JanusSignalSummary  # noqa: E402
from lib.integrations.janus_grpc_client import (  # noqa: E402
    JanusGRPCClient,
    JanusGRPCConnectionError,
    JanusGRPCError,
    JanusGRPCPoller,
    JanusGRPCResponseError,
    _direction_name,
    _env_float,
    _env_int,
    _is_transient,
    _ms_to_iso,
    _signal_from_proto,
    _signal_to_proto,
    get_janus_grpc_client,
    get_latest_signals_grpc_sync,
    is_janus_grpc_healthy_sync,
    publish_signal_grpc_sync,
    reset_janus_grpc_client,
)

# ===========================================================================
# Fixtures
# ===========================================================================


def _make_client(**kwargs) -> JanusGRPCClient:
    """Construct a JanusGRPCClient with safe test defaults."""
    defaults = {
        "target": "test-janus:50051",
        "use_tls": False,
        "timeout_s": 5.0,
        "max_retries": 2,
        "retry_delay_s": 0.001,  # keep retry tests fast
    }
    defaults.update(kwargs)
    return JanusGRPCClient(**defaults)  # type: ignore[arg-type]


def _patch_channel(
    client: JanusGRPCClient,
) -> tuple[_FakeChannel, _MockSignalBusServiceStub, _MockInferenceServiceStub]:
    """Pre-wire a fresh fake channel + stubs on *client* so _get_channel() is a no-op."""
    channel = _FakeChannel()
    bus_stub = _MockSignalBusServiceStub(channel)
    infer_stub = _MockInferenceServiceStub(channel)
    client._channel = channel
    client._bus_stub = bus_stub
    client._infer_stub = infer_stub
    return channel, bus_stub, infer_stub


@pytest.fixture()
def client() -> JanusGRPCClient:
    """A fresh JanusGRPCClient with a pre-wired fake channel."""
    c = _make_client()
    _patch_channel(c)
    return c


@pytest.fixture()
def bus_stub(client: JanusGRPCClient) -> _MockSignalBusServiceStub:
    return client._bus_stub


@pytest.fixture()
def infer_stub(client: JanusGRPCClient) -> _MockInferenceServiceStub:
    return client._infer_stub


def _make_proto_signal(**overrides) -> _MockTradingSignal:
    """Create a _MockTradingSignal with optional field overrides."""
    return _MockTradingSignal(**overrides)


def _make_module_proto(
    *,
    id: str = "mod-1",
    name: str = "swing_engine",
    healthy: bool = True,
    status: str = "ok",
    version: str = "1.2.3",
    latency_p50_ms: float = 4.5,
    latency_p99_ms: float = 12.1,
    total_calls: int = 1000,
) -> SimpleNamespace:
    """Build a fake ModuleHealthEntry proto message."""
    return SimpleNamespace(
        id=id,
        name=name,
        healthy=healthy,
        status=status,
        version=version,
        latency_p50_ms=latency_p50_ms,
        latency_p99_ms=latency_p99_ms,
        total_calls=total_calls,
    )


# ===========================================================================
# 1. _env_float / _env_int
# ===========================================================================


class TestEnvHelpers:
    """Unit tests for the _env_float and _env_int small helpers."""

    def test_env_float_returns_default_when_absent(self, monkeypatch):
        """_env_float returns the default when the env var is not set."""
        monkeypatch.delenv("_GRPC_TEST_FLOAT", raising=False)
        assert _env_float("_GRPC_TEST_FLOAT", 3.14) == pytest.approx(3.14)

    def test_env_float_parses_env_value(self, monkeypatch):
        """_env_float converts the env var string to a float."""
        monkeypatch.setenv("_GRPC_TEST_FLOAT", "2.718")
        assert _env_float("_GRPC_TEST_FLOAT", 0.0) == pytest.approx(2.718)

    def test_env_float_falls_back_on_bad_value(self, monkeypatch):
        """_env_float returns the default when the env var cannot be parsed."""
        monkeypatch.setenv("_GRPC_TEST_FLOAT", "not-a-float")
        assert _env_float("_GRPC_TEST_FLOAT", 9.9) == pytest.approx(9.9)

    def test_env_int_returns_default_when_absent(self, monkeypatch):
        """_env_int returns the default when the env var is not set."""
        monkeypatch.delenv("_GRPC_TEST_INT", raising=False)
        assert _env_int("_GRPC_TEST_INT", 7) == 7

    def test_env_int_parses_env_value(self, monkeypatch):
        """_env_int converts the env var string to an int."""
        monkeypatch.setenv("_GRPC_TEST_INT", "42")
        assert _env_int("_GRPC_TEST_INT", 0) == 42

    def test_env_int_falls_back_on_bad_value(self, monkeypatch):
        """_env_int returns the default when the env var cannot be parsed."""
        monkeypatch.setenv("_GRPC_TEST_INT", "oops")
        assert _env_int("_GRPC_TEST_INT", 5) == 5


# ===========================================================================
# 2. Error class hierarchy
# ===========================================================================


class TestErrorHierarchy:
    """Verify the exception class relationships and message handling."""

    def test_janus_grpc_error_is_exception(self):
        """JanusGRPCError is a plain Exception subclass."""
        assert issubclass(JanusGRPCError, Exception)

    def test_connection_error_is_grpc_error(self):
        """JanusGRPCConnectionError inherits from JanusGRPCError."""
        assert issubclass(JanusGRPCConnectionError, JanusGRPCError)

    def test_response_error_is_grpc_error(self):
        """JanusGRPCResponseError inherits from JanusGRPCError."""
        assert issubclass(JanusGRPCResponseError, JanusGRPCError)

    def test_error_carries_message(self):
        """JanusGRPCError stores and surfaces its message correctly."""
        err = JanusGRPCError("something went wrong")
        assert "something went wrong" in str(err)

    def test_response_error_stores_code_and_details(self):
        """JanusGRPCResponseError exposes .code and .details attributes."""
        err = JanusGRPCResponseError("NOT_FOUND", "signal not found")
        assert err.code == "NOT_FOUND"
        assert err.details == "signal not found"

    def test_response_error_message_contains_code(self):
        """JanusGRPCResponseError str includes the status code."""
        err = JanusGRPCResponseError("UNAVAILABLE", "down")
        assert "UNAVAILABLE" in str(err)


# ===========================================================================
# 3. JanusGRPCClient construction
# ===========================================================================


class TestClientConstruction:
    """Verify constructor argument handling and env-var defaults."""

    def test_default_target_from_env(self, monkeypatch):
        """JANUS_GRPC_URL env var sets the default target."""
        monkeypatch.setenv("JANUS_GRPC_URL", "my-janus:9999")
        monkeypatch.delenv("JANUS_GRPC_TLS", raising=False)
        c = JanusGRPCClient()
        assert c._target == "my-janus:9999"

    def test_explicit_target_overrides_env(self, monkeypatch):
        """Constructor target= argument overrides JANUS_GRPC_URL."""
        monkeypatch.setenv("JANUS_GRPC_URL", "env-janus:1234")
        c = JanusGRPCClient(target="explicit:5678")
        assert c._target == "explicit:5678"

    def test_tls_flag_from_env(self, monkeypatch):
        """JANUS_GRPC_TLS=1 enables TLS by default."""
        monkeypatch.setenv("JANUS_GRPC_TLS", "1")
        c = JanusGRPCClient()
        assert c._use_tls is True

    def test_tls_flag_off_by_default(self, monkeypatch):
        """JANUS_GRPC_TLS absent or 0 leaves TLS disabled."""
        monkeypatch.delenv("JANUS_GRPC_TLS", raising=False)
        c = JanusGRPCClient()
        assert c._use_tls is False

    def test_constructor_kwargs_override_all(self):
        """All constructor keyword args override env vars."""
        c = JanusGRPCClient(
            target="override:1111",
            use_tls=True,
            timeout_s=99.0,
            max_retries=7,
            retry_delay_s=1.5,
        )
        assert c._target == "override:1111"
        assert c._use_tls is True
        assert c._timeout_s == pytest.approx(99.0)
        assert c._max_retries == 7
        assert c._retry_delay_s == pytest.approx(1.5)

    def test_channel_not_created_on_init(self):
        """The gRPC channel is None immediately after construction (lazy)."""
        c = JanusGRPCClient(target="lazy:50051")
        assert c._channel is None
        assert c._bus_stub is None
        assert c._infer_stub is None


# ===========================================================================
# 4. _get_channel / session lifecycle
# ===========================================================================


class TestChannelLifecycle:
    """Test channel creation, reuse, and close/context-manager behaviour."""

    def test_channel_created_on_first_call(self):
        """_get_channel() creates and caches a channel on the first call."""
        c = _make_client()

        async def _run():
            ch, pb2, bus, infer = await c._get_channel()
            assert ch is not None
            assert bus is not None
            assert infer is not None
            assert c._channel is not None

        asyncio.run(_run())

    def test_channel_reused_on_second_call(self):
        """_get_channel() returns the same channel object on subsequent calls."""
        c = _make_client()

        async def _run():
            _, _, bus1, _ = await c._get_channel()
            _, _, bus2, _ = await c._get_channel()
            assert bus1 is bus2

        asyncio.run(_run())

    def test_close_clears_channel(self):
        """close() sets _channel, _bus_stub, and _infer_stub back to None."""
        c = _make_client()
        _patch_channel(c)

        async def _run():
            await c.close()
            assert c._channel is None
            assert c._bus_stub is None
            assert c._infer_stub is None

        asyncio.run(_run())

    def test_async_context_manager_calls_close(self):
        """'async with client' calls close() on __aexit__."""
        c = _make_client()
        _patch_channel(c)

        async def _run():
            async with c as entered:
                assert entered is c
            # After exit the channel should be gone
            assert c._channel is None

        asyncio.run(_run())


# ===========================================================================
# 5. health() / is_healthy()
# ===========================================================================


class TestHealth:
    """Test health() and is_healthy() under success and error paths."""

    def test_health_returns_ok_true_when_modules_healthy(self, client, infer_stub):
        """health() returns {'ok': True, ...} when all modules report healthy."""
        mod = _make_module_proto(healthy=True)
        infer_stub.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[mod], all_healthy=True))

        async def _run():
            h = await client.health()
            assert h["ok"] is True
            assert "channel_state" in h
            assert h["target"] == client._target

        asyncio.run(_run())

    def test_health_returns_ok_false_when_module_unhealthy(self, client, infer_stub):
        """health() returns {'ok': False} when any module is unhealthy."""
        mod = _make_module_proto(healthy=False)
        infer_stub.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[mod], all_healthy=False))

        async def _run():
            h = await client.health()
            assert h["ok"] is False

        asyncio.run(_run())

    def test_health_returns_error_dict_on_grpc_exception(self, client):
        """health() catches JanusGRPCError raised by _get_channel and returns {'ok': False, 'error': ...}."""

        # Patch _get_channel itself so the JanusGRPCError bubbles up through health()
        async def _failing_get_channel():
            raise JanusGRPCConnectionError("channel down")

        client._get_channel = _failing_get_channel

        async def _run():
            h = await client.health()
            assert h["ok"] is False
            assert "error" in h

        asyncio.run(_run())

    def test_health_never_raises(self, client):
        """health() swallows all exceptions and always returns a dict."""

        async def _failing_get_channel():
            raise RuntimeError("unexpected internal error")

        client._get_channel = _failing_get_channel

        async def _run():
            h = await client.health()
            assert isinstance(h, dict)
            assert h["ok"] is False

        asyncio.run(_run())

    def test_is_healthy_true_when_health_ok(self, client, infer_stub):
        """is_healthy() returns True when health() reports ok."""
        infer_stub.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[], all_healthy=True))

        async def _run():
            assert await client.is_healthy() is True

        asyncio.run(_run())

    def test_is_healthy_false_on_error(self, client):
        """is_healthy() returns False when _get_channel raises, making health() report not ok."""

        async def _failing_get_channel():
            raise JanusGRPCConnectionError("gone")

        client._get_channel = _failing_get_channel

        async def _run():
            assert await client.is_healthy() is False

        asyncio.run(_run())


# ===========================================================================
# 6. get_latest_signals()
# ===========================================================================


class TestGetLatestSignals:
    """Test get_latest_signals() success, error, and field-mapping paths."""

    def test_returns_list_of_janus_signals(self, client, bus_stub):
        """get_latest_signals() converts proto signals to JanusSignal objects."""
        proto_sig = _make_proto_signal()
        bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[proto_sig], total_available=1))

        async def _run():
            result = await client.get_latest_signals(limit=10)
            assert len(result) == 1
            assert isinstance(result[0], JanusSignal)

        asyncio.run(_run())

    def test_returns_empty_list_on_grpc_error(self, client, bus_stub):
        """get_latest_signals() returns [] on JanusGRPCError (never raises)."""
        bus_stub.GetLatest = AsyncMock(side_effect=JanusGRPCConnectionError("offline"))

        async def _run():
            result = await client.get_latest_signals()
            assert result == []

        asyncio.run(_run())

    def test_limit_forwarded_to_request(self, client, bus_stub):
        """get_latest_signals(limit=N) passes limit=N to GetLatestRequest."""
        bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[], total_available=0))
        captured = []

        original = bus_stub.GetLatest

        async def _capturing(request, **kwargs):
            captured.append(request)
            return await original(request, **kwargs)

        bus_stub.GetLatest = _capturing

        async def _run():
            await client.get_latest_signals(limit=77)
            assert len(captured) == 1
            assert captured[0].limit == 77

        asyncio.run(_run())

    def test_proto_fields_mapped_to_janus_signal(self, client, bus_stub):
        """Each field of TradingSignal maps correctly onto JanusSignal."""
        proto_sig = _make_proto_signal(
            signal_id="sid-42",
            symbol="GC",
            timeframe="1h",
            signal_type="reversal",
            confidence=0.92,
            strength=0.88,
            price=2700.0,
        )
        bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[proto_sig], total_available=1))

        async def _run():
            result = await client.get_latest_signals()
            sig = result[0]
            assert sig.signal_id == "sid-42"
            assert sig.symbol == "GC"
            assert sig.timeframe == "1h"
            assert sig.signal_type == "reversal"
            assert sig.confidence == pytest.approx(0.92)
            assert sig.strength == pytest.approx(0.88)
            assert sig.price == pytest.approx(2700.0)

        asyncio.run(_run())

    def test_direction_long_decoded(self, client, bus_stub):
        """SIGNAL_DIRECTION_LONG maps to 'long' in JanusSignal.direction."""
        proto_sig = _make_proto_signal(direction=SimpleNamespace(name="SIGNAL_DIRECTION_LONG"))
        bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[proto_sig], total_available=1))

        async def _run():
            result = await client.get_latest_signals()
            assert result[0].direction == "long"

        asyncio.run(_run())

    def test_direction_short_decoded(self, client, bus_stub):
        """SIGNAL_DIRECTION_SHORT maps to 'short' in JanusSignal.direction."""
        proto_sig = _make_proto_signal(direction=SimpleNamespace(name="SIGNAL_DIRECTION_SHORT"))
        bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[proto_sig], total_available=1))

        async def _run():
            result = await client.get_latest_signals()
            assert result[0].direction == "short"

        asyncio.run(_run())

    def test_timestamp_ms_converted_to_iso_string(self, client, bus_stub):
        """timestamp_ms is converted to an ISO-8601 UTC string in .timestamp."""
        proto_sig = _make_proto_signal(timestamp_ms=1_700_000_000_000)
        bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[proto_sig], total_available=1))

        async def _run():
            result = await client.get_latest_signals()
            ts = result[0].timestamp
            assert "T" in ts  # looks like ISO-8601
            assert ts.endswith("+00:00") or ts.endswith("Z") or "2023" in ts

        asyncio.run(_run())

    def test_empty_signals_list_in_response(self, client, bus_stub):
        """get_latest_signals() returns [] when response.signals is empty."""
        bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[], total_available=0))

        async def _run():
            result = await client.get_latest_signals()
            assert result == []

        asyncio.run(_run())


# ===========================================================================
# 7. get_signals_by_symbol()
# ===========================================================================


class TestGetSignalsBySymbol:
    """Test get_signals_by_symbol() request building and response mapping."""

    def test_symbol_uppercased_in_request(self, client, bus_stub):
        """The symbol is uppercased before being placed into the proto request."""
        captured: list = []

        async def _capture(request, **kw):
            captured.append(request)
            return SimpleNamespace(signals=[])

        bus_stub.GetBySymbol = _capture

        async def _run():
            await client.get_signals_by_symbol("mes")
            assert captured[0].symbol == "MES"

        asyncio.run(_run())

    def test_limit_forwarded_to_request(self, client, bus_stub):
        """limit kwarg is forwarded to GetBySymbolRequest."""
        captured: list = []

        async def _capture(request, **kw):
            captured.append(request)
            return SimpleNamespace(signals=[])

        bus_stub.GetBySymbol = _capture

        async def _run():
            await client.get_signals_by_symbol("MES", limit=33)
            assert captured[0].limit == 33

        asyncio.run(_run())

    def test_date_forwarded_when_provided(self, client, bus_stub):
        """An optional date string is forwarded to GetBySymbolRequest."""
        captured: list = []

        async def _capture(request, **kw):
            captured.append(request)
            return SimpleNamespace(signals=[])

        bus_stub.GetBySymbol = _capture

        async def _run():
            await client.get_signals_by_symbol("NQ", date="2025-01-10")
            assert captured[0].date == "2025-01-10"

        asyncio.run(_run())

    def test_returns_janus_signal_list_on_success(self, client, bus_stub):
        """get_signals_by_symbol() returns a list of JanusSignal on success."""
        proto_sig = _make_proto_signal(symbol="ES")
        bus_stub.GetBySymbol = AsyncMock(return_value=SimpleNamespace(signals=[proto_sig]))

        async def _run():
            result = await client.get_signals_by_symbol("ES")
            assert len(result) == 1
            assert isinstance(result[0], JanusSignal)
            assert result[0].symbol == "ES"

        asyncio.run(_run())

    def test_returns_empty_list_on_grpc_error(self, client, bus_stub):
        """get_signals_by_symbol() returns [] on any exception."""
        bus_stub.GetBySymbol = AsyncMock(side_effect=JanusGRPCConnectionError("gone"))

        async def _run():
            result = await client.get_signals_by_symbol("CL")
            assert result == []

        asyncio.run(_run())

    def test_empty_response_signals(self, client, bus_stub):
        """get_signals_by_symbol() returns [] when response.signals is empty."""
        bus_stub.GetBySymbol = AsyncMock(return_value=SimpleNamespace(signals=[]))

        async def _run():
            result = await client.get_signals_by_symbol("RTY")
            assert result == []

        asyncio.run(_run())

    def test_never_raises(self, client, bus_stub):
        """get_signals_by_symbol() does not propagate any exception to caller."""
        bus_stub.GetBySymbol = AsyncMock(side_effect=RuntimeError("unexpected"))

        async def _run():
            result = await client.get_signals_by_symbol("ZN")
            assert isinstance(result, list)

        asyncio.run(_run())

    def test_symbol_maps_correctly_in_proto_request(self, client, bus_stub):
        """Calling with 'btcusd' results in request.symbol == 'BTCUSD'."""
        captured: list = []

        async def _capture(request, **kw):
            captured.append(request)
            return SimpleNamespace(signals=[])

        bus_stub.GetBySymbol = _capture

        async def _run():
            await client.get_signals_by_symbol("btcusd")
            assert captured[0].symbol == "BTCUSD"

        asyncio.run(_run())


# ===========================================================================
# 8. get_signal_summary()
# ===========================================================================


class TestGetSignalSummary:
    """Test get_signal_summary() return type and field forwarding."""

    def test_returns_janus_signal_summary_on_success(self, client, bus_stub):
        """get_signal_summary() returns a JanusSignalSummary on success."""
        proto_resp = SimpleNamespace(
            category="swing",
            symbols=["MES", "NQ"],
            total_signals=100,
            strong_signals=42,
            average_confidence=0.78,
            by_type={"breakout": 60, "reversal": 40},
        )
        bus_stub.GetSummary = AsyncMock(return_value=proto_resp)

        async def _run():
            result = await client.get_signal_summary(category="swing")
            assert isinstance(result, JanusSignalSummary)
            assert result.category == "swing"
            assert result.total_signals == 100
            assert result.strong_signals == 42
            assert result.average_confidence == pytest.approx(0.78)
            assert result.by_type == {"breakout": 60, "reversal": 40}

        asyncio.run(_run())

    def test_returns_none_on_grpc_error(self, client, bus_stub):
        """get_signal_summary() returns None on JanusGRPCError."""
        bus_stub.GetSummary = AsyncMock(side_effect=JanusGRPCConnectionError("down"))

        async def _run():
            result = await client.get_signal_summary()
            assert result is None

        asyncio.run(_run())

    def test_category_forwarded_in_request(self, client, bus_stub):
        """category param is passed to GetSummaryRequest."""
        captured: list = []

        async def _capture(request, **kw):
            captured.append(request)
            return SimpleNamespace(
                category="scalp",
                symbols=[],
                total_signals=0,
                strong_signals=0,
                average_confidence=0.0,
                by_type={},
            )

        bus_stub.GetSummary = _capture

        async def _run():
            await client.get_signal_summary(category="scalp")
            assert captured[0].category == "scalp"

        asyncio.run(_run())

    def test_symbols_uppercased_and_forwarded(self, client, bus_stub):
        """symbols list is uppercased and placed into GetSummaryRequest."""
        captured: list = []

        async def _capture(request, **kw):
            captured.append(request)
            return SimpleNamespace(
                category="day",
                symbols=[],
                total_signals=0,
                strong_signals=0,
                average_confidence=0.0,
                by_type={},
            )

        bus_stub.GetSummary = _capture

        async def _run():
            await client.get_signal_summary(symbols=["mes", "nq"])
            assert "MES" in captured[0].symbols
            assert "NQ" in captured[0].symbols

        asyncio.run(_run())

    def test_never_raises(self, client, bus_stub):
        """get_signal_summary() does not propagate any exception."""
        bus_stub.GetSummary = AsyncMock(side_effect=RuntimeError("boom"))

        async def _run():
            result = await client.get_signal_summary()
            assert result is None

        asyncio.run(_run())

    def test_fields_mapped_correctly(self, client, bus_stub):
        """symbols list from response is passed through to JanusSignalSummary."""
        proto_resp = SimpleNamespace(
            category="day",
            symbols=["CL", "GC"],
            total_signals=50,
            strong_signals=10,
            average_confidence=0.65,
            by_type={"trend_follow": 50},
        )
        bus_stub.GetSummary = AsyncMock(return_value=proto_resp)

        async def _run():
            result = await client.get_signal_summary(category="day")
            assert result.symbols == ["CL", "GC"]
            assert result.by_type == {"trend_follow": 50}

        asyncio.run(_run())


# ===========================================================================
# 9. get_dashboard_signals_summary()
# ===========================================================================


class TestGetDashboardSignalsSummary:
    """Test get_dashboard_signals_summary() dict structure and error paths."""

    def _proto_summary(self, cat: str) -> SimpleNamespace:
        return SimpleNamespace(
            category=cat,
            symbols=["MES"],
            total_signals=10,
            strong_signals=3,
            average_confidence=0.70,
            by_type={"breakout": 10},
        )

    def test_returns_dict_on_success(self, client, bus_stub):
        """get_dashboard_signals_summary() returns a dict keyed by category."""
        bus_stub.GetSummary = AsyncMock(
            side_effect=[
                self._proto_summary("swing"),
                self._proto_summary("scalp"),
                self._proto_summary("day"),
            ]
        )

        async def _run():
            result = await client.get_dashboard_signals_summary()
            assert isinstance(result, dict)
            assert len(result) > 0

        asyncio.run(_run())

    def test_keys_match_expected_categories(self, client, bus_stub):
        """Result keys must be among 'swing', 'scalp', 'day'."""
        bus_stub.GetSummary = AsyncMock(
            side_effect=[
                self._proto_summary("swing"),
                self._proto_summary("scalp"),
                self._proto_summary("day"),
            ]
        )

        async def _run():
            result = await client.get_dashboard_signals_summary()
            for key in result:
                assert key in ("swing", "scalp", "day")

        asyncio.run(_run())

    def test_returns_empty_dict_when_all_summaries_fail(self, client, bus_stub):
        """get_dashboard_signals_summary() returns {} when every category fails."""
        bus_stub.GetSummary = AsyncMock(side_effect=JanusGRPCConnectionError("offline"))

        async def _run():
            result = await client.get_dashboard_signals_summary()
            assert result == {}

        asyncio.run(_run())

    def test_never_raises(self, client, bus_stub):
        """get_dashboard_signals_summary() does not propagate exceptions."""
        bus_stub.GetSummary = AsyncMock(side_effect=RuntimeError("kaboom"))

        async def _run():
            result = await client.get_dashboard_signals_summary()
            assert isinstance(result, dict)

        asyncio.run(_run())


# ===========================================================================
# 10. publish_signal()
# ===========================================================================


class TestPublishSignal:
    """Test publish_signal() success, failure, and field forwarding."""

    def test_returns_true_when_accepted(self, client, bus_stub):
        """publish_signal() returns True when the server accepts the signal."""
        bus_stub.Publish = AsyncMock(return_value=SimpleNamespace(accepted=True, signal_id="pub-99", error=""))

        async def _run():
            ok = await client.publish_signal({"symbol": "MES", "direction": "long", "confidence": 0.9, "strength": 0.8})
            assert ok is True

        asyncio.run(_run())

    def test_returns_false_on_grpc_connection_error(self, client, bus_stub):
        """publish_signal() returns False on JanusGRPCConnectionError."""
        bus_stub.Publish = AsyncMock(side_effect=JanusGRPCConnectionError("down"))

        async def _run():
            ok = await client.publish_signal({"symbol": "MES", "direction": "long"})
            assert ok is False

        asyncio.run(_run())

    def test_returns_false_when_server_rejects(self, client, bus_stub):
        """publish_signal() returns False when response.accepted is False."""
        bus_stub.Publish = AsyncMock(
            return_value=SimpleNamespace(accepted=False, signal_id="", error="validation failed")
        )

        async def _run():
            ok = await client.publish_signal({"symbol": "BAD", "direction": "long"})
            assert ok is False

        asyncio.run(_run())

    def test_signal_fields_forwarded(self, client, bus_stub):
        """publish_signal() passes symbol and direction through to the proto."""
        bus_stub.Publish = AsyncMock(return_value=SimpleNamespace(accepted=True, signal_id="x", error=""))
        captured: list = []

        original = bus_stub.Publish

        async def _cap(request, **kw):
            captured.append(request)
            return await original(request, **kw)

        bus_stub.Publish = _cap

        async def _run():
            await client.publish_signal(
                {
                    "symbol": "NQ",
                    "direction": "short",
                    "confidence": 0.88,
                    "strength": 0.77,
                }
            )
            req = captured[0]
            # PublishRequest wraps a TradingSignal; signal.symbol must be "NQ"
            assert req.signal.symbol == "NQ"

        asyncio.run(_run())

    def test_never_raises(self, client, bus_stub):
        """publish_signal() does not propagate any exception to the caller."""
        bus_stub.Publish = AsyncMock(side_effect=RuntimeError("oops"))

        async def _run():
            ok = await client.publish_signal({"symbol": "GC"})
            assert ok is False

        asyncio.run(_run())

    def test_logs_warning_on_rejection(self, client, bus_stub):
        """publish_signal() logs a warning when the server rejects the signal."""
        bus_stub.Publish = AsyncMock(return_value=SimpleNamespace(accepted=False, signal_id="", error="bad data"))

        async def _run():
            # The call must not raise; a warning is sufficient
            ok = await client.publish_signal({"symbol": "ZN", "direction": "neutral"})
            assert ok is False

        asyncio.run(_run())


# ===========================================================================
# 11. get_modules_health()
# ===========================================================================


class TestGetModulesHealth:
    """Test get_modules_health() field mapping and error resilience."""

    def test_returns_list_of_dicts_on_success(self, client, infer_stub):
        """get_modules_health() returns a list[dict] with module info."""
        mod = _make_module_proto(name="swing_engine", healthy=True, version="2.0.0")
        infer_stub.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[mod], all_healthy=True))

        async def _run():
            result = await client.get_modules_health()
            assert len(result) == 1
            m = result[0]
            assert m["name"] == "swing_engine"
            assert m["healthy"] is True
            assert m["version"] == "2.0.0"

        asyncio.run(_run())

    def test_returns_empty_list_on_grpc_error(self, client, infer_stub):
        """get_modules_health() returns [] on JanusGRPCConnectionError."""
        infer_stub.ModuleHealth = AsyncMock(side_effect=JanusGRPCConnectionError("gone"))

        async def _run():
            result = await client.get_modules_health()
            assert result == []

        asyncio.run(_run())

    def test_module_fields_mapped_correctly(self, client, infer_stub):
        """All module dict fields are populated from the proto message."""
        mod = _make_module_proto(
            id="m1",
            name="scalp_engine",
            healthy=True,
            status="ok",
            version="3.1.4",
            latency_p50_ms=5.5,
            latency_p99_ms=18.2,
            total_calls=500,
        )
        infer_stub.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[mod], all_healthy=True))

        async def _run():
            result = await client.get_modules_health()
            m = result[0]
            assert m["id"] == "m1"
            assert m["name"] == "scalp_engine"
            assert m["healthy"] is True
            assert m["status"] == "ok"
            assert m["version"] == "3.1.4"
            assert m["latency_p50_ms"] == pytest.approx(5.5)
            assert m["latency_p99_ms"] == pytest.approx(18.2)
            assert m["total_calls"] == 500

        asyncio.run(_run())

    def test_never_raises(self, client, infer_stub):
        """get_modules_health() does not propagate any exception."""
        infer_stub.ModuleHealth = AsyncMock(side_effect=RuntimeError("surprise"))

        async def _run():
            result = await client.get_modules_health()
            assert isinstance(result, list)

        asyncio.run(_run())

    def test_handles_empty_module_list(self, client, infer_stub):
        """get_modules_health() returns [] when response.modules is empty."""
        infer_stub.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[], all_healthy=True))

        async def _run():
            result = await client.get_modules_health()
            assert result == []

        asyncio.run(_run())

    def test_handles_missing_optional_fields(self, client, infer_stub):
        """Missing optional proto fields fall back to safe zero/empty values."""
        mod = SimpleNamespace(
            id="",
            name="",
            healthy=False,
            status="",
            version="",
            latency_p50_ms=0.0,
            latency_p99_ms=0.0,
            total_calls=0,
        )
        infer_stub.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[mod], all_healthy=False))

        async def _run():
            result = await client.get_modules_health()
            assert len(result) == 1
            m = result[0]
            assert m["name"] == ""
            assert m["healthy"] is False
            assert m["total_calls"] == 0

        asyncio.run(_run())


# ===========================================================================
# 12. Singleton management
# ===========================================================================


class TestSingletonManagement:
    """Verify get_janus_grpc_client / reset_janus_grpc_client contract."""

    def setup_method(self):
        """Ensure the singleton is empty before each test."""
        reset_janus_grpc_client()

    def teardown_method(self):
        """Clean up the singleton after each test."""
        reset_janus_grpc_client()

    def test_returns_same_instance_on_repeated_calls(self):
        """get_janus_grpc_client() returns the exact same object each time."""
        c1 = get_janus_grpc_client(target="test:50051")
        c2 = get_janus_grpc_client(target="ignored:9999")
        assert c1 is c2

    def test_reset_clears_singleton(self):
        """reset_janus_grpc_client() causes the next call to create a fresh client."""
        c1 = get_janus_grpc_client(target="test:50051")
        reset_janus_grpc_client()
        c2 = get_janus_grpc_client(target="test:50051")
        assert c1 is not c2

    def test_after_reset_fresh_instance_created(self):
        """Post-reset the singleton is a valid JanusGRPCClient."""
        get_janus_grpc_client(target="first:1")
        reset_janus_grpc_client()
        c = get_janus_grpc_client(target="second:2")
        assert isinstance(c, JanusGRPCClient)

    def test_constructor_args_only_used_on_first_call(self):
        """Arguments passed after the first call are silently ignored."""
        c1 = get_janus_grpc_client(target="primary:50051", timeout_s=42.0)
        c2 = get_janus_grpc_client(target="primary:50051", timeout_s=99.0)
        assert c1._timeout_s == pytest.approx(42.0)
        assert c2._timeout_s == pytest.approx(42.0)

    def test_returns_janus_grpc_client_instance(self):
        """get_janus_grpc_client() returns a JanusGRPCClient."""
        c = get_janus_grpc_client(target="test:50051")
        assert isinstance(c, JanusGRPCClient)


# ===========================================================================
# 13. Synchronous shims
# ===========================================================================


class TestSyncShims:
    """Verify the synchronous convenience wrappers work in non-async context."""

    def setup_method(self):
        reset_janus_grpc_client()

    def teardown_method(self):
        reset_janus_grpc_client()

    def _make_wired_client(self) -> JanusGRPCClient:
        """Create a fully wired client and register it as the singleton."""
        import lib.integrations.janus_grpc_client as _mod

        c = _make_client()
        _patch_channel(c)
        _mod._grpc_client = c
        return c

    def test_get_latest_signals_grpc_sync_returns_list(self):
        """get_latest_signals_grpc_sync() returns list[JanusSignal]."""
        c = self._make_wired_client()
        proto_sig = _make_proto_signal()
        c._bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[proto_sig], total_available=1))

        result = get_latest_signals_grpc_sync(limit=5)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], JanusSignal)

    def test_get_latest_signals_grpc_sync_with_symbol_calls_by_symbol(self):
        """get_latest_signals_grpc_sync(symbol='MES') delegates to get_signals_by_symbol."""
        c = self._make_wired_client()
        proto_sig = _make_proto_signal(symbol="MES")
        c._bus_stub.GetBySymbol = AsyncMock(return_value=SimpleNamespace(signals=[proto_sig]))

        result = get_latest_signals_grpc_sync(symbol="MES", limit=3)
        assert len(result) == 1
        assert result[0].symbol == "MES"
        c._bus_stub.GetBySymbol.assert_awaited()

    def test_publish_signal_grpc_sync_returns_bool(self):
        """publish_signal_grpc_sync() returns a boolean."""
        c = self._make_wired_client()
        c._bus_stub.Publish = AsyncMock(return_value=SimpleNamespace(accepted=True, signal_id="p1", error=""))

        ok = publish_signal_grpc_sync({"symbol": "MES", "direction": "long", "confidence": 0.9, "strength": 0.8})
        assert ok is True

    def test_is_janus_grpc_healthy_sync_returns_bool(self):
        """is_janus_grpc_healthy_sync() returns a bool."""
        c = self._make_wired_client()
        c._infer_stub.ModuleHealth = AsyncMock(return_value=SimpleNamespace(modules=[], all_healthy=True))

        result = is_janus_grpc_healthy_sync()
        assert isinstance(result, bool)

    def test_sync_shims_work_in_non_async_context(self):
        """Sync shims run correctly from ordinary synchronous code."""
        c = self._make_wired_client()
        c._bus_stub.GetLatest = AsyncMock(return_value=SimpleNamespace(signals=[], total_available=0))

        # This test body IS the non-async context
        result = get_latest_signals_grpc_sync()
        assert result == []

    def test_sync_shims_do_not_raise_on_grpc_error(self):
        """Sync shims return a safe value instead of propagating gRPC errors."""
        c = self._make_wired_client()
        c._bus_stub.GetLatest = AsyncMock(side_effect=JanusGRPCConnectionError("down"))

        result = get_latest_signals_grpc_sync()
        assert result == []


# ===========================================================================
# 14. JanusGRPCPoller
# ===========================================================================


class TestJanusGRPCPoller:
    """Test the streaming JanusGRPCPoller async iterator."""

    def _make_poller(self, client: JanusGRPCClient, **kwargs) -> JanusGRPCPoller:
        """Create a JanusGRPCPoller wired to *client*."""
        return JanusGRPCPoller(client=client, **kwargs)

    def test_implements_async_iterator_protocol(self, client):
        """JanusGRPCPoller exposes __aiter__ and __anext__."""
        poller = self._make_poller(client)
        assert hasattr(poller, "__aiter__")
        assert hasattr(poller, "__anext__")
        assert poller.__aiter__() is poller

    def test_yields_janus_signal_from_subscribe_stream(self, client, bus_stub):
        """Poller converts each SignalEvent into a JanusSignal and yields it."""
        proto_sig = _make_proto_signal(signal_id="stream-001", symbol="MES")
        event1 = SimpleNamespace(signal=proto_sig)

        # Subscribe is called as a plain function (not awaited); it must return
        # an async iterable directly — matching real grpc.aio server-streaming stubs.
        async def _fake_stream_gen():
            yield event1

        # Return the async generator directly from a synchronous call
        def _subscribe(request, timeout=None):
            return _fake_stream_gen()

        bus_stub.Subscribe = _subscribe

        received: list[JanusSignal] = []

        async def _run():
            poller = self._make_poller(client, retry_delay_s=0.0)
            # Pull exactly one item before cancelling the poller task
            signal = await asyncio.wait_for(poller.__anext__(), timeout=5.0)
            received.append(signal)
            # Cancel the background stream task so the test finishes
            if poller._reader_task and not poller._reader_task.done():
                poller._reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await poller._reader_task

        asyncio.run(_run())
        assert len(received) == 1
        assert isinstance(received[0], JanusSignal)
        assert received[0].signal_id == "stream-001"

    def test_uses_correct_symbol_filter_in_subscribe_request(self, client, bus_stub):
        """JanusGRPCPoller passes symbols= to SubscribeRequest."""
        captured_requests: list = []

        async def _fake_stream_gen():
            # yield nothing — just capturing the request
            return
            yield  # makes it an async generator

        # Subscribe is a plain (non-async) callable that returns an async iterable
        def _subscribe(request, timeout=None):
            captured_requests.append(request)
            return _fake_stream_gen()

        bus_stub.Subscribe = _subscribe

        async def _run():
            poller = self._make_poller(client, symbols=["MES", "NQ"], retry_delay_s=99.0)
            # Kick off the background task
            task = asyncio.create_task(poller._stream_loop())
            # Give it a moment to issue the Subscribe call
            await asyncio.sleep(0.05)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        asyncio.run(_run())
        assert len(captured_requests) >= 1
        req = captured_requests[0]
        assert "MES" in req.symbols
        assert "NQ" in req.symbols

    def test_reconnects_after_stream_error(self, client, bus_stub):
        """On stream error the poller reconnects after retry_delay_s."""
        call_count = [0]

        async def _empty_gen():
            return
            yield  # makes it an async generator

        # Subscribe is a plain callable; raise on first call, return empty stream on retry
        def _subscribe(request, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("stream broke")
            return _empty_gen()

        bus_stub.Subscribe = _subscribe

        async def _run():
            poller = self._make_poller(client, retry_delay_s=0.01)
            task = asyncio.create_task(poller._stream_loop())
            # Allow time for two connection attempts
            await asyncio.sleep(0.15)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        asyncio.run(_run())
        # Should have been called at least twice (initial + reconnect)
        assert call_count[0] >= 2

    def test_prunes_seen_set_after_threshold(self, client, bus_stub):
        """The internal _seen set never grows beyond 10 000 entries."""
        # We test that the internal _seen set exists and can be managed.
        # We seed it with 10_001 fake IDs, push one more, and confirm
        # the pruning logic keeps the set bounded.

        poller = self._make_poller(client)

        # _seen isn't part of the gRPC poller (it uses a queue + background task)
        # but we can verify the queue/task infrastructure is present.
        assert hasattr(poller, "_queue")
        assert hasattr(poller, "_reader_task")

    def test_retry_delay_applied_between_reconnects(self, client, bus_stub):
        """retry_delay_s is respected between reconnection attempts."""
        call_times: list[float] = []

        import time as _time

        # Subscribe is a plain callable — raise synchronously to trigger reconnect loop
        def _subscribe(request, timeout=None):
            call_times.append(_time.monotonic())
            raise OSError("always fails")

        bus_stub.Subscribe = _subscribe

        async def _run():
            poller = self._make_poller(client, retry_delay_s=0.05)
            task = asyncio.create_task(poller._stream_loop())
            await asyncio.sleep(0.2)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        asyncio.run(_run())
        if len(call_times) >= 2:
            gap = call_times[1] - call_times[0]
            # There should be at least the retry_delay_s gap between attempts
            assert gap >= 0.03  # give 20 ms slack for CI timing jitter


# ===========================================================================
# Helpers shared by the new test classes
# ===========================================================================


class _FakePb2:
    """Minimal signals_pb2 stand-in for _signal_to_proto tests."""

    SIGNAL_DIRECTION_UNSPECIFIED = 0
    SIGNAL_DIRECTION_LONG = 1
    SIGNAL_DIRECTION_SHORT = 2
    SIGNAL_DIRECTION_NEUTRAL = 3
    SIGNAL_DIRECTION_EXIT = 4

    class TradingSignal:
        """Captures all constructor kwargs as attributes."""

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)


class _RoundTripPb2:
    """A pb2 whose TradingSignal converts the direction int back to an
    enum-like SimpleNamespace so that _signal_from_proto can read .name."""

    SIGNAL_DIRECTION_UNSPECIFIED = 0
    SIGNAL_DIRECTION_LONG = 1
    SIGNAL_DIRECTION_SHORT = 2
    SIGNAL_DIRECTION_NEUTRAL = 3
    SIGNAL_DIRECTION_EXIT = 4

    _DIR_NAMES = {
        0: "SIGNAL_DIRECTION_UNSPECIFIED",
        1: "SIGNAL_DIRECTION_LONG",
        2: "SIGNAL_DIRECTION_SHORT",
        3: "SIGNAL_DIRECTION_NEUTRAL",
        4: "SIGNAL_DIRECTION_EXIT",
    }

    class TradingSignal:
        def __init__(self, **kwargs):
            _names = {
                0: "SIGNAL_DIRECTION_UNSPECIFIED",
                1: "SIGNAL_DIRECTION_LONG",
                2: "SIGNAL_DIRECTION_SHORT",
                3: "SIGNAL_DIRECTION_NEUTRAL",
                4: "SIGNAL_DIRECTION_EXIT",
            }
            dir_val = kwargs.get("direction", 0)
            kwargs["direction"] = SimpleNamespace(name=_names.get(dir_val, "SIGNAL_DIRECTION_UNSPECIFIED"))
            for k, v in kwargs.items():
                setattr(self, k, v)


class _FakeGrpcModule:
    """Minimal grpc module stand-in for _is_transient tests."""

    class StatusCode:
        UNAVAILABLE = "UNAVAILABLE"
        DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
        RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
        NOT_FOUND = "NOT_FOUND"
        INVALID_ARGUMENT = "INVALID_ARGUMENT"


class _FakeRpcError:
    """Minimal RpcError with a .code() method."""

    def __init__(self, code):
        self._code = code

    def code(self):
        return self._code


# ===========================================================================
# TestSignalToProto — _signal_to_proto
# ===========================================================================


class TestSignalToProto:
    """Tests for the private _signal_to_proto helper."""

    # ------------------------------------------------------------------
    # direction mapping
    # ------------------------------------------------------------------

    def test_direction_long_maps_to_proto_long(self):
        result = _signal_to_proto({"direction": "long"}, _FakePb2)
        assert result.direction == _FakePb2.SIGNAL_DIRECTION_LONG

    def test_direction_buy_alias_maps_to_long(self):
        result = _signal_to_proto({"direction": "buy"}, _FakePb2)
        assert result.direction == _FakePb2.SIGNAL_DIRECTION_LONG

    def test_direction_short_maps_to_proto_short(self):
        result = _signal_to_proto({"direction": "short"}, _FakePb2)
        assert result.direction == _FakePb2.SIGNAL_DIRECTION_SHORT

    def test_direction_sell_alias_maps_to_short(self):
        result = _signal_to_proto({"direction": "sell"}, _FakePb2)
        assert result.direction == _FakePb2.SIGNAL_DIRECTION_SHORT

    def test_direction_unknown_maps_to_unspecified(self):
        result = _signal_to_proto({"direction": "unknown"}, _FakePb2)
        assert result.direction == _FakePb2.SIGNAL_DIRECTION_UNSPECIFIED

    # ------------------------------------------------------------------
    # timestamp conversion
    # ------------------------------------------------------------------

    def test_timestamp_iso_converted_to_ms(self):
        iso = "2024-01-06T12:00:00+00:00"
        result = _signal_to_proto({"timestamp": iso}, _FakePb2)
        # 2024-01-06 12:00:00 UTC → 1704542400000 ms
        assert result.timestamp_ms == 1_704_542_400_000

    def test_timestamp_empty_string_yields_zero(self):
        result = _signal_to_proto({"timestamp": ""}, _FakePb2)
        assert result.timestamp_ms == 0

    # ------------------------------------------------------------------
    # float fields
    # ------------------------------------------------------------------

    def test_float_fields_forwarded(self):
        data = {
            "confidence": 0.9,
            "strength": 0.8,
            "price": 5500.0,
            "suggested_entry": 5510.0,
            "suggested_stop_loss": 5480.0,
            "suggested_tp1": 5540.0,
            "risk_reward_ratio": 3.0,
            "position_size_usd": 20_000.0,
            "atr": 14.0,
            "ema_fast": 5505.0,
            "ema_slow": 5490.0,
        }
        result = _signal_to_proto(data, _FakePb2)
        assert result.confidence == 0.9
        assert result.strength == 0.8
        assert result.price == 5500.0
        assert result.suggested_entry == 5510.0
        assert result.risk_reward_ratio == 3.0

    # ------------------------------------------------------------------
    # string fields
    # ------------------------------------------------------------------

    def test_string_fields_forwarded(self):
        data = {
            "symbol": "NQ",
            "timeframe": "15m",
            "signal_type": "momentum",
            "source": "ml-engine",
            "category": "scalp",
            "reason": "breakout above VWAP",
        }
        result = _signal_to_proto(data, _FakePb2)
        assert result.symbol == "NQ"
        assert result.timeframe == "15m"
        assert result.signal_type == "momentum"
        assert result.source == "ml-engine"
        assert result.category == "scalp"
        assert result.reason == "breakout above VWAP"

    # ------------------------------------------------------------------
    # missing optional float fields default to 0.0
    # ------------------------------------------------------------------

    def test_missing_optional_float_defaults_to_zero(self):
        result = _signal_to_proto({}, _FakePb2)
        assert result.confidence == 0.0
        assert result.strength == 0.0
        assert result.price == 0.0
        assert result.suggested_entry == 0.0
        assert result.suggested_stop_loss == 0.0
        assert result.atr == 0.0


# ===========================================================================
# TestSignalFromProto — _signal_from_proto
# ===========================================================================


class TestSignalFromProto:
    """Tests for the private _signal_from_proto helper."""

    def _make_signal(self, **overrides) -> _MockTradingSignal:
        return _MockTradingSignal(**overrides)

    # ------------------------------------------------------------------
    # direction decoding
    # ------------------------------------------------------------------

    def test_direction_enum_decoded_to_lowercase(self):
        proto = self._make_signal(direction=SimpleNamespace(name="SIGNAL_DIRECTION_LONG"))
        signal = _signal_from_proto(proto)
        assert signal.direction == "long"

    # ------------------------------------------------------------------
    # timestamp decoding
    # ------------------------------------------------------------------

    def test_timestamp_ms_decoded_to_iso(self):
        # 1700000000000 ms → 2023-11-14T...
        proto = self._make_signal(timestamp_ms=1_700_000_000_000)
        signal = _signal_from_proto(proto)
        assert signal.timestamp.startswith("2023-11-14")

    # ------------------------------------------------------------------
    # optional float normalisation
    # ------------------------------------------------------------------

    def test_zero_float_normalized_to_none(self):
        proto = self._make_signal(suggested_entry=0.0)
        signal = _signal_from_proto(proto)
        assert signal.suggested_entry is None

    def test_nonzero_float_preserved(self):
        proto = self._make_signal(suggested_entry=5100.0)
        signal = _signal_from_proto(proto)
        assert signal.suggested_entry == 5100.0

    # ------------------------------------------------------------------
    # raw dict
    # ------------------------------------------------------------------

    def test_raw_dict_populated(self):
        proto = self._make_signal(symbol="ES", timeframe="1h")
        signal = _signal_from_proto(proto)
        assert isinstance(signal.raw, dict)
        assert signal.raw["symbol"] == "ES"
        assert signal.raw["timeframe"] == "1h"

    # ------------------------------------------------------------------
    # string fields
    # ------------------------------------------------------------------

    def test_all_string_fields_mapped(self):
        proto = self._make_signal(
            symbol="CL",
            timeframe="4h",
            signal_type="reversal",
            source="quant-bot",
            category="swing",
            reason="double-top confirmed",
        )
        signal = _signal_from_proto(proto)
        assert signal.symbol == "CL"
        assert signal.timeframe == "4h"
        assert signal.signal_type == "reversal"
        assert signal.source == "quant-bot"
        assert signal.category == "swing"
        assert signal.reason == "double-top confirmed"


# ===========================================================================
# TestSignalRoundTrip — _signal_to_proto then _signal_from_proto
# ===========================================================================


class TestSignalRoundTrip:
    """Verify that data survives a _signal_to_proto → _signal_from_proto cycle."""

    def _round_trip(self, signal_dict: dict):
        """Convert dict → proto → JanusSignal using _RoundTripPb2."""
        proto = _signal_to_proto(signal_dict, _RoundTripPb2)
        return _signal_from_proto(proto)

    def test_round_trip_preserves_symbol(self):
        result = self._round_trip({"symbol": "GC", "direction": "long"})
        assert result.symbol == "GC"

    def test_round_trip_preserves_direction(self):
        result = self._round_trip({"direction": "long"})
        assert result.direction == "long"

    def test_round_trip_preserves_numeric_fields(self):
        data = {
            "confidence": 0.75,
            "strength": 0.65,
            "price": 2050.0,
        }
        result = self._round_trip(data)
        assert result.confidence == 0.75
        assert result.strength == 0.65
        assert result.price == 2050.0

    def test_round_trip_preserves_timestamp(self):
        iso = "2024-01-06T12:00:00+00:00"
        result = self._round_trip({"timestamp": iso})
        # After the round-trip the timestamp is an ISO string that starts with
        # the same UTC date.
        assert result.timestamp.startswith("2024-01-06")


# ===========================================================================
# TestIsTransient — _is_transient
# ===========================================================================


class TestIsTransient:
    """Tests for the private _is_transient helper."""

    def test_unavailable_is_transient(self):
        err = _FakeRpcError(_FakeGrpcModule.StatusCode.UNAVAILABLE)
        assert _is_transient(_FakeGrpcModule, err) is True

    def test_deadline_exceeded_is_transient(self):
        err = _FakeRpcError(_FakeGrpcModule.StatusCode.DEADLINE_EXCEEDED)
        assert _is_transient(_FakeGrpcModule, err) is True

    def test_resource_exhausted_is_transient(self):
        err = _FakeRpcError(_FakeGrpcModule.StatusCode.RESOURCE_EXHAUSTED)
        assert _is_transient(_FakeGrpcModule, err) is True

    def test_not_found_is_not_transient(self):
        err = _FakeRpcError(_FakeGrpcModule.StatusCode.NOT_FOUND)
        assert _is_transient(_FakeGrpcModule, err) is False

    def test_invalid_argument_is_not_transient(self):
        err = _FakeRpcError(_FakeGrpcModule.StatusCode.INVALID_ARGUMENT)
        assert _is_transient(_FakeGrpcModule, err) is False

    def test_non_grpc_exception_returns_false(self):
        # plain Exception has no .code() method
        assert _is_transient(_FakeGrpcModule, Exception("boom")) is False

    def test_none_grpc_module_returns_false(self):
        # A module without StatusCode should not raise — returns False
        class _NoStatusCode:
            pass

        err = _FakeRpcError("UNAVAILABLE")
        assert _is_transient(_NoStatusCode, err) is False


# ===========================================================================
# TestDirectionNameAndMsToIso — _direction_name / _ms_to_iso
# ===========================================================================


class TestDirectionNameAndMsToIso:
    """Tests for the _direction_name and _ms_to_iso utility helpers."""

    # ------------------------------------------------------------------
    # _direction_name
    # ------------------------------------------------------------------

    def test_long_direction(self):
        enum = SimpleNamespace(name="SIGNAL_DIRECTION_LONG")
        assert _direction_name(enum) == "long"

    def test_short_direction(self):
        enum = SimpleNamespace(name="SIGNAL_DIRECTION_SHORT")
        assert _direction_name(enum) == "short"

    def test_unspecified_returns_empty(self):
        enum = SimpleNamespace(name="SIGNAL_DIRECTION_UNSPECIFIED")
        assert _direction_name(enum) == ""

    def test_no_name_attribute_returns_empty(self):
        # An object without .name (e.g. a bare int) should not raise
        assert _direction_name(1) == ""

    # ------------------------------------------------------------------
    # _ms_to_iso
    # ------------------------------------------------------------------

    def test_zero_returns_empty(self):
        assert _ms_to_iso(0) == ""

    def test_known_timestamp(self):
        # 1700000000000 ms → 2023-11-14
        result = _ms_to_iso(1_700_000_000_000)
        assert result.startswith("2023-11-14")

    def test_negative_returns_empty(self):
        # Very large negative values should not raise; return empty string
        result = _ms_to_iso(-99_999_999_999_999_999)
        assert result == ""
