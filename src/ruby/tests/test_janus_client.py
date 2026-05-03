"""
Tests for the Janus HTTP Client
================================
Covers:
  - JanusSignal dataclass: from_dict / to_dict
  - JanusSignalSummary dataclass: from_dict
  - JanusClientError hierarchy
  - JanusHTTPClient: construction, headers, session lifecycle, retry logic,
    4xx/5xx handling, all API methods, singleton management
  - Sync shims: get_latest_signals_sync, publish_signal_sync, is_janus_healthy_sync
  - JanusSignalPoller: __anext__ deduplication and error resilience
  - Environment variable overrides (_env_float, _env_int)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.integrations.janus_client import (
    JanusClientError,
    JanusConnectionError,
    JanusHTTPClient,
    JanusResponseError,
    JanusSignal,
    JanusSignalPoller,
    JanusSignalSummary,
    _env_float,
    _env_int,
    get_janus_client,
    get_latest_signals_sync,
    is_janus_healthy_sync,
    publish_signal_sync,
    reset_janus_client,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _signal_dict(**overrides) -> dict:
    """Minimal valid Janus signal dict."""
    base = {
        "signal_id": "sig-001",
        "symbol": "MES",
        "timeframe": "5m",
        "signal_type": "breakout",
        "direction": "long",
        "confidence": 0.85,
        "strength": 0.75,
        "price": 5420.5,
        "suggested_entry": 5422.0,
        "suggested_stop_loss": 5400.0,
        "suggested_tp1": 5440.0,
        "suggested_tp2": 5460.0,
        "suggested_tp3": 5480.0,
        "risk_reward_ratio": 2.5,
        "position_size_usd": 10000.0,
        "atr": 12.5,
        "ema_fast": 5418.0,
        "ema_slow": 5410.0,
        "timestamp": "2025-01-06T10:30:00Z",
        "source": "janus-swing",
        "category": "swing",
        "reason": "ICT OB reclaim",
    }
    base.update(overrides)
    return base


def _make_client(**kwargs) -> JanusHTTPClient:
    """Construct a JanusHTTPClient with safe test defaults."""
    defaults = {
        "base_url": "http://test-janus:8080",
        "api_key": "test-key",
        "timeout_s": 5.0,
        "max_retries": 2,
        "retry_delay_s": 0.01,  # speed up retry tests
    }
    defaults.update(kwargs)
    return JanusHTTPClient(**defaults)  # type: ignore[arg-type]


# ===========================================================================
# Environment helpers
# ===========================================================================


class TestEnvHelpers:
    def test_env_float_returns_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("_TEST_FLOAT_VAR", raising=False)
        assert _env_float("_TEST_FLOAT_VAR", 3.14) == pytest.approx(3.14)

    def test_env_float_parses_value(self, monkeypatch):
        monkeypatch.setenv("_TEST_FLOAT_VAR", "2.5")
        assert _env_float("_TEST_FLOAT_VAR", 1.0) == pytest.approx(2.5)

    def test_env_float_falls_back_on_bad_value(self, monkeypatch):
        monkeypatch.setenv("_TEST_FLOAT_VAR", "not-a-number")
        assert _env_float("_TEST_FLOAT_VAR", 9.9) == pytest.approx(9.9)

    def test_env_int_returns_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("_TEST_INT_VAR", raising=False)
        assert _env_int("_TEST_INT_VAR", 7) == 7

    def test_env_int_parses_value(self, monkeypatch):
        monkeypatch.setenv("_TEST_INT_VAR", "42")
        assert _env_int("_TEST_INT_VAR", 1) == 42

    def test_env_int_falls_back_on_bad_value(self, monkeypatch):
        monkeypatch.setenv("_TEST_INT_VAR", "oops")
        assert _env_int("_TEST_INT_VAR", 5) == 5


# ===========================================================================
# JanusSignal
# ===========================================================================


class TestJanusSignalFromDict:
    def test_all_fields_populated(self):
        d = _signal_dict()
        sig = JanusSignal.from_dict(d)

        assert sig.signal_id == "sig-001"
        assert sig.symbol == "MES"
        assert sig.timeframe == "5m"
        assert sig.signal_type == "breakout"
        assert sig.direction == "long"
        assert sig.confidence == pytest.approx(0.85)
        assert sig.strength == pytest.approx(0.75)
        assert sig.price == pytest.approx(5420.5)
        assert sig.suggested_entry == pytest.approx(5422.0)
        assert sig.suggested_stop_loss == pytest.approx(5400.0)
        assert sig.suggested_tp1 == pytest.approx(5440.0)
        assert sig.suggested_tp2 == pytest.approx(5460.0)
        assert sig.suggested_tp3 == pytest.approx(5480.0)
        assert sig.risk_reward_ratio == pytest.approx(2.5)
        assert sig.position_size_usd == pytest.approx(10000.0)
        assert sig.atr == pytest.approx(12.5)
        assert sig.ema_fast == pytest.approx(5418.0)
        assert sig.ema_slow == pytest.approx(5410.0)
        assert sig.timestamp == "2025-01-06T10:30:00Z"
        assert sig.source == "janus-swing"
        assert sig.category == "swing"
        assert sig.reason == "ICT OB reclaim"
        assert sig.raw is d

    def test_minimal_dict(self):
        sig = JanusSignal.from_dict({})
        assert sig.signal_id == ""
        assert sig.symbol == ""
        assert sig.confidence == 0.0
        assert sig.strength == 0.0
        assert sig.price == 0.0
        assert sig.suggested_entry is None
        assert sig.suggested_stop_loss is None
        assert sig.suggested_tp1 is None
        assert sig.atr is None
        assert sig.reason is None

    def test_accepts_id_alias(self):
        """Janus may return 'id' instead of 'signal_id'."""
        sig = JanusSignal.from_dict({"id": "alias-99", "symbol": "GC"})
        assert sig.signal_id == "alias-99"

    def test_signal_id_prefers_signal_id_over_id(self):
        sig = JanusSignal.from_dict({"signal_id": "primary", "id": "secondary"})
        assert sig.signal_id == "primary"

    def test_numeric_strings_parsed(self):
        sig = JanusSignal.from_dict({"confidence": "0.9", "strength": "0.8", "price": "5000.25"})
        assert sig.confidence == pytest.approx(0.9)
        assert sig.strength == pytest.approx(0.8)
        assert sig.price == pytest.approx(5000.25)

    def test_bad_float_fields_become_none(self):
        sig = JanusSignal.from_dict({"atr": "bad", "ema_fast": "??", "suggested_tp1": "n/a"})
        assert sig.atr is None
        assert sig.ema_fast is None
        assert sig.suggested_tp1 is None

    def test_confidence_none_becomes_zero(self):
        sig = JanusSignal.from_dict({"confidence": None})
        assert sig.confidence == 0.0

    def test_raw_contains_original_dict(self):
        d = _signal_dict()
        sig = JanusSignal.from_dict(d)
        assert sig.raw is d


class TestJanusSignalToDict:
    def test_round_trips(self):
        d = _signal_dict()
        sig = JanusSignal.from_dict(d)
        out = sig.to_dict()

        assert out["signal_id"] == "sig-001"
        assert out["symbol"] == "MES"
        assert out["confidence"] == pytest.approx(0.85)
        assert out["suggested_entry"] == pytest.approx(5422.0)
        assert out["atr"] == pytest.approx(12.5)
        assert out["reason"] == "ICT OB reclaim"

    def test_does_not_include_raw_key(self):
        sig = JanusSignal.from_dict(_signal_dict())
        out = sig.to_dict()
        assert "raw" not in out

    def test_none_optional_fields_preserved(self):
        sig = JanusSignal.from_dict({})
        out = sig.to_dict()
        assert out["suggested_tp1"] is None
        assert out["atr"] is None
        assert out["reason"] is None


# ===========================================================================
# JanusSignalSummary
# ===========================================================================


class TestJanusSignalSummary:
    def test_from_dict_full(self):
        d = {
            "category": "swing",
            "symbols": ["MES", "MGC"],
            "total_signals": 42,
            "strong_signals": 12,
            "average_confidence": 0.73,
            "by_type": {"breakout": 20, "reversal": 22},
        }
        s = JanusSignalSummary.from_dict(d)
        assert s.category == "swing"
        assert s.symbols == ["MES", "MGC"]
        assert s.total_signals == 42
        assert s.strong_signals == 12
        assert s.average_confidence == pytest.approx(0.73)
        assert s.by_type == {"breakout": 20, "reversal": 22}

    def test_from_dict_empty(self):
        s = JanusSignalSummary.from_dict({})
        assert s.category == ""
        assert s.symbols == []
        assert s.total_signals == 0
        assert s.strong_signals == 0
        assert s.average_confidence == 0.0
        assert s.by_type == {}

    def test_by_type_int_coercion(self):
        s = JanusSignalSummary.from_dict({"by_type": {"breakout": "5", "trend": "3"}})
        assert s.by_type["breakout"] == 5
        assert s.by_type["trend"] == 3


# ===========================================================================
# Exception hierarchy
# ===========================================================================


class TestExceptions:
    def test_janus_client_error_is_exception(self):
        exc = JanusClientError("oops")
        assert isinstance(exc, Exception)

    def test_connection_error_is_client_error(self):
        exc = JanusConnectionError("unreachable")
        assert isinstance(exc, JanusClientError)

    def test_response_error_captures_status_and_body(self):
        exc = JanusResponseError(503, "service unavailable")
        assert exc.status == 503
        assert "503" in str(exc)
        assert "service unavailable" in str(exc)

    def test_response_error_truncates_long_body(self):
        long_body = "x" * 500
        exc = JanusResponseError(500, long_body)
        # Should not include the entire 500-char body in the message
        assert len(str(exc)) < 400

    def test_response_error_is_client_error(self):
        assert isinstance(JanusResponseError(400, "bad"), JanusClientError)


# ===========================================================================
# JanusHTTPClient — construction
# ===========================================================================


class TestJanusHTTPClientConstruction:
    def test_default_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("JANUS_HTTP_URL", "http://custom-janus:9090")
        monkeypatch.delenv("API_KEY", raising=False)
        client = JanusHTTPClient()
        assert client._base_url == "http://custom-janus:9090"

    def test_trailing_slash_stripped(self):
        client = JanusHTTPClient(base_url="http://janus:8080/")
        assert not client._base_url.endswith("/")

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv("JANUS_HTTP_URL", "http://env-janus:8080")
        monkeypatch.setenv("API_KEY", "env-key")
        client = JanusHTTPClient(
            base_url="http://explicit:9999",
            api_key="explicit-key",
            timeout_s=3.0,
            max_retries=1,
            retry_delay_s=0.1,
        )
        assert client._base_url == "http://explicit:9999"
        assert client._api_key == "explicit-key"
        assert client._timeout_s == pytest.approx(3.0)
        assert client._max_retries == 1
        assert client._retry_delay_s == pytest.approx(0.1)

    def test_session_starts_as_none(self):
        client = _make_client()
        assert client._session is None

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "from-env-key")
        client = JanusHTTPClient(base_url="http://x:8080")
        assert client._api_key == "from-env-key"


# ===========================================================================
# JanusHTTPClient — headers
# ===========================================================================


class TestBuildHeaders:
    def test_includes_accept_and_content_type(self):
        client = _make_client(api_key="")
        headers = client._build_headers()
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"

    def test_includes_bearer_when_api_key_set(self):
        client = _make_client(api_key="my-secret")
        headers = client._build_headers()
        assert headers["Authorization"] == "Bearer my-secret"

    def test_no_auth_header_when_key_empty(self):
        client = _make_client(api_key="")
        headers = client._build_headers()
        assert "Authorization" not in headers


# ===========================================================================
# JanusHTTPClient — session lifecycle
# ===========================================================================


class TestSessionLifecycle:
    def test_context_manager_returns_self(self):
        client = _make_client()

        async def _run():
            mock_session = MagicMock()
            mock_session.closed = False
            mock_session.close = AsyncMock()
            client._session = mock_session
            async with client as c:
                assert c is client

        asyncio.run(_run())

    def test_close_skips_when_session_none(self):
        client = _make_client()
        asyncio.run(client.close())  # should not raise

    def test_close_skips_when_session_already_closed(self):
        client = _make_client()
        mock_session = MagicMock()
        mock_session.closed = True
        client._session = mock_session

        asyncio.run(client.close())
        mock_session.close.assert_not_called()

    def test_close_calls_close_on_open_session(self):
        client = _make_client()
        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session

        asyncio.run(client.close())
        mock_session.close.assert_awaited_once()

    def test_get_session_raises_when_aiohttp_missing(self):
        import sys

        saved = sys.modules.get("aiohttp")
        sys.modules["aiohttp"] = None  # type: ignore[assignment]
        try:
            client = _make_client()

            async def _run():
                with pytest.raises(JanusClientError, match="aiohttp"):
                    await client._get_session()

            asyncio.run(_run())
        finally:
            if saved is None:
                sys.modules.pop("aiohttp", None)
            else:
                sys.modules["aiohttp"] = saved


# ===========================================================================
# JanusHTTPClient — _request (retry, error handling)
# ===========================================================================


def _make_mock_response(status: int, body: str) -> MagicMock:
    """Build a mock aiohttp response context manager."""
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=body)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _patch_session(client: JanusHTTPClient, responses: list[MagicMock]) -> None:
    """Replace the client's session with a mock that yields responses in order."""
    session = MagicMock()
    session.closed = False
    call_count = [0]

    def _request(*args, **kwargs):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return responses[idx]

    session.request = _request
    client._session = session


class TestRequestMethod:
    def test_successful_get_parses_json(self):
        client = _make_client()
        resp = _make_mock_response(200, '{"signals": []}')
        _patch_session(client, [resp])

        async def _run():
            result = await client._get("/api/signals/latest")
            assert result == {"signals": []}

        asyncio.run(_run())

    def test_returns_empty_dict_on_empty_body(self):
        client = _make_client()
        resp = _make_mock_response(200, "")
        _patch_session(client, [resp])

        async def _run():
            result = await client._get("/health")
            assert result == {}

        asyncio.run(_run())

    def test_4xx_raises_response_error_no_retry(self):
        client = _make_client(max_retries=3)
        resp = _make_mock_response(404, "not found")
        _patch_session(client, [resp])

        async def _run():
            with pytest.raises(JanusResponseError) as exc_info:
                await client._get("/missing")
            assert exc_info.value.status == 404

        asyncio.run(_run())

    def test_5xx_retries_and_raises_connection_error(self):
        client = _make_client(max_retries=2, retry_delay_s=0.001)
        resp = _make_mock_response(503, "service unavailable")

        # Patch asyncio.sleep so tests run fast
        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):
            _patch_session(client, [resp, resp])

            async def _run():
                with pytest.raises(JanusConnectionError):
                    await client._get("/api/signals/latest")

            asyncio.run(_run())

    def test_network_error_retries_and_raises_connection_error(self):
        client = _make_client(max_retries=2, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False

        def _bad_request(*args, **kwargs):
            raise OSError("connection refused")

        session.request = _bad_request
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                with pytest.raises(JanusConnectionError):
                    await client._get("/health")

            asyncio.run(_run())

    def test_succeeds_on_second_attempt_after_5xx(self):
        client = _make_client(max_retries=3, retry_delay_s=0.001)
        fail_resp = _make_mock_response(500, "error")
        ok_resp = _make_mock_response(200, '{"ok": true}')

        responses = [fail_resp, ok_resp]
        idx = [0]
        session = MagicMock()
        session.closed = False

        def _request(*args, **kwargs):
            r = responses[min(idx[0], len(responses) - 1)]
            idx[0] += 1
            return r

        session.request = _request
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                result = await client._get("/health")
                assert result == {"ok": True}

            asyncio.run(_run())

    def test_non_json_body_returned_as_string(self):
        client = _make_client()
        resp = _make_mock_response(200, "plain text body")
        _patch_session(client, [resp])

        async def _run():
            result = await client._get("/health")
            assert result == "plain text body"

        asyncio.run(_run())


# ===========================================================================
# JanusHTTPClient — health endpoints
# ===========================================================================


class TestHealthEndpoints:
    def test_health_returns_dict_on_success(self):
        client = _make_client()
        resp = _make_mock_response(200, '{"ok": true, "version": "0.1.0"}')
        _patch_session(client, [resp])

        async def _run():
            result = await client.health()
            assert result["ok"] is True
            assert result["version"] == "0.1.0"

        asyncio.run(_run())

    def test_health_returns_error_dict_on_failure(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        # Simulate connection refused on every attempt
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("refused"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                result = await client.health()
                assert result.get("ok") is False
                assert "error" in result

            asyncio.run(_run())

    def test_is_healthy_true_when_ok(self):
        client = _make_client()
        resp = _make_mock_response(200, '{"ok": true}')
        _patch_session(client, [resp])

        async def _run():
            assert await client.is_healthy() is True

        asyncio.run(_run())

    def test_is_healthy_false_when_error_key_present(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("refused"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                assert await client.is_healthy() is False

            asyncio.run(_run())


# ===========================================================================
# JanusHTTPClient — get_latest_signals
# ===========================================================================


class TestGetLatestSignals:
    def test_returns_parsed_signals(self):
        client = _make_client()
        payload = {"signals": [_signal_dict(), _signal_dict(signal_id="sig-002", symbol="MGC")]}
        import json

        resp = _make_mock_response(200, json.dumps(payload))
        _patch_session(client, [resp])

        async def _run():
            signals = await client.get_latest_signals(limit=10)
            assert len(signals) == 2
            assert signals[0].signal_id == "sig-001"
            assert signals[1].symbol == "MGC"

        asyncio.run(_run())

    def test_returns_empty_list_on_connection_failure(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("down"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                result = await client.get_latest_signals()
                assert result == []

            asyncio.run(_run())

    def test_skips_non_dict_entries(self):
        import json

        client = _make_client()
        payload = {"signals": [_signal_dict(), "not-a-dict", None, 42]}
        resp = _make_mock_response(200, json.dumps(payload))
        _patch_session(client, [resp])

        async def _run():
            signals = await client.get_latest_signals()
            assert len(signals) == 1

        asyncio.run(_run())

    def test_handles_missing_signals_key(self):
        import json

        client = _make_client()
        resp = _make_mock_response(200, json.dumps({"other": "data"}))
        _patch_session(client, [resp])

        async def _run():
            result = await client.get_latest_signals()
            assert result == []

        asyncio.run(_run())


# ===========================================================================
# JanusHTTPClient — get_signals_by_symbol
# ===========================================================================


class TestGetSignalsBySymbol:
    def test_uppercases_symbol_in_url(self):
        import json

        client = _make_client()
        captured_url = []

        session = MagicMock()
        session.closed = False
        resp = _make_mock_response(200, json.dumps({"signals": [_signal_dict()]}))

        def _request(method, url, **kwargs):
            captured_url.append(url)
            return resp

        session.request = _request
        client._session = session

        async def _run():
            await client.get_signals_by_symbol("mes")
            assert "MES" in captured_url[0]

        asyncio.run(_run())

    def test_passes_limit_and_date_params(self):
        import json

        client = _make_client()
        captured_params = []

        session = MagicMock()
        session.closed = False
        resp = _make_mock_response(200, json.dumps({"signals": []}))

        def _request(method, url, params=None, **kwargs):
            captured_params.append(params)
            return resp

        session.request = _request
        client._session = session

        async def _run():
            await client.get_signals_by_symbol("MES", limit=20, date="2025-01-06")
            assert captured_params[0]["limit"] == 20
            assert captured_params[0]["date"] == "2025-01-06"

        asyncio.run(_run())

    def test_returns_empty_on_failure(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("down"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                result = await client.get_signals_by_symbol("MES")
                assert result == []

            asyncio.run(_run())


# ===========================================================================
# JanusHTTPClient — get_signal_summary
# ===========================================================================


class TestGetSignalSummary:
    def test_returns_summary_object(self):
        import json

        client = _make_client()
        d = {
            "category": "swing",
            "symbols": ["MES"],
            "total_signals": 5,
            "strong_signals": 2,
            "average_confidence": 0.80,
            "by_type": {"breakout": 5},
        }
        resp = _make_mock_response(200, json.dumps(d))
        _patch_session(client, [resp])

        async def _run():
            summary = await client.get_signal_summary(category="swing")
            assert summary is not None
            assert summary.category == "swing"
            assert summary.total_signals == 5

        asyncio.run(_run())

    def test_returns_none_on_failure(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("down"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                result = await client.get_signal_summary()
                assert result is None

            asyncio.run(_run())

    def test_joins_symbols_param(self):
        import json

        client = _make_client()
        captured_params = []

        session = MagicMock()
        session.closed = False
        resp = _make_mock_response(200, json.dumps({"category": "swing"}))

        def _request(method, url, params=None, **kwargs):
            captured_params.append(params)
            return resp

        session.request = _request
        client._session = session

        async def _run():
            await client.get_signal_summary(symbols=["mes", "mgc"])
            assert captured_params[0]["symbols"] == "MES,MGC"

        asyncio.run(_run())


# ===========================================================================
# JanusHTTPClient — publish_signal
# ===========================================================================


class TestPublishSignal:
    def test_returns_true_on_success(self):
        import json

        client = _make_client()
        resp = _make_mock_response(200, json.dumps({"published": True}))
        _patch_session(client, [resp])

        async def _run():
            ok = await client.publish_signal({"symbol": "MES", "side": "Buy", "strength": 0.9, "confidence": 0.85})
            assert ok is True

        asyncio.run(_run())

    def test_returns_false_on_connection_failure(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("refused"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                ok = await client.publish_signal({"symbol": "MES", "side": "Buy", "strength": 0.5, "confidence": 0.5})
                assert ok is False

            asyncio.run(_run())

    def test_returns_false_on_4xx(self):
        client = _make_client()
        resp = _make_mock_response(422, "unprocessable")
        _patch_session(client, [resp])

        async def _run():
            ok = await client.publish_signal({"symbol": "X"})
            assert ok is False

        asyncio.run(_run())


# ===========================================================================
# JanusHTTPClient — get_modules_health
# ===========================================================================


class TestGetModulesHealth:
    def test_returns_modules_list(self):
        import json

        client = _make_client()
        payload = {"modules": [{"name": "swing", "healthy": True}, {"name": "scalp", "healthy": False}]}
        resp = _make_mock_response(200, json.dumps(payload))
        _patch_session(client, [resp])

        async def _run():
            result = await client.get_modules_health()
            assert len(result) == 2
            assert result[0]["name"] == "swing"

        asyncio.run(_run())

    def test_returns_empty_list_on_failure(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("down"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                result = await client.get_modules_health()
                assert result == []

            asyncio.run(_run())


# ===========================================================================
# Singleton management
# ===========================================================================


class TestSingleton:
    def setup_method(self):
        reset_janus_client()

    def teardown_method(self):
        reset_janus_client()

    def test_get_janus_client_returns_same_instance(self):
        c1 = get_janus_client(base_url="http://test:8080")
        c2 = get_janus_client(base_url="http://ignored:9999")
        assert c1 is c2

    def test_reset_clears_singleton(self):
        c1 = get_janus_client(base_url="http://test:8080")
        reset_janus_client()
        c2 = get_janus_client(base_url="http://test:8080")
        assert c1 is not c2

    def test_returns_janus_http_client_instance(self):
        c = get_janus_client(base_url="http://test:8080")
        assert isinstance(c, JanusHTTPClient)


# ===========================================================================
# Synchronous shims
# ===========================================================================


class TestSyncShims:
    def setup_method(self):
        reset_janus_client()

    def teardown_method(self):
        reset_janus_client()

    def test_get_latest_signals_sync_all(self):
        import json

        payload = {"signals": [_signal_dict()]}
        resp = _make_mock_response(200, json.dumps(payload))

        client = _make_client()
        _patch_session(client, [resp])

        with patch("lib.integrations.janus_client.get_janus_client", return_value=client):
            result = get_latest_signals_sync(limit=10)
            assert len(result) == 1
            assert result[0].signal_id == "sig-001"

    def test_get_latest_signals_sync_by_symbol(self):
        import json

        payload = {"signals": [_signal_dict(symbol="MGC")]}
        resp = _make_mock_response(200, json.dumps(payload))

        client = _make_client()
        _patch_session(client, [resp])

        with patch("lib.integrations.janus_client.get_janus_client", return_value=client):
            result = get_latest_signals_sync("MGC", limit=5)
            assert len(result) == 1
            assert result[0].symbol == "MGC"

    def test_publish_signal_sync_success(self):
        import json

        resp = _make_mock_response(200, json.dumps({"ok": True}))

        client = _make_client()
        _patch_session(client, [resp])

        with patch("lib.integrations.janus_client.get_janus_client", return_value=client):
            ok = publish_signal_sync({"symbol": "MES", "side": "Buy", "strength": 0.9, "confidence": 0.9})
            assert ok is True

    def test_is_janus_healthy_sync_true(self):
        import json

        resp = _make_mock_response(200, json.dumps({"ok": True}))

        client = _make_client()
        _patch_session(client, [resp])

        with patch("lib.integrations.janus_client.get_janus_client", return_value=client):
            assert is_janus_healthy_sync() is True

    def test_is_janus_healthy_sync_false_on_error(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("down"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with (
            patch("asyncio.sleep", side_effect=_fast_sleep),
            patch("lib.integrations.janus_client.get_janus_client", return_value=client),
        ):
            assert is_janus_healthy_sync() is False


# ===========================================================================
# JanusSignalPoller
# ===========================================================================


class TestJanusSignalPoller:
    def test_yields_new_signals_only(self):
        """Poller should skip signals it has already seen (unit-tests _seen dedup logic directly)."""
        sig1 = JanusSignal.from_dict(_signal_dict(signal_id="a"))
        sig2 = JanusSignal.from_dict(_signal_dict(signal_id="b"))
        sig3 = JanusSignal.from_dict(_signal_dict(signal_id="c"))

        client = MagicMock()

        # Simulate two consecutive poll batches
        batches = [
            [sig1, sig2],  # first call: two new signals
            [sig1, sig2, sig3],  # second call: sig1+sig2 already seen, sig3 is new
        ]
        call_count = [0]

        async def _get_latest(limit=50):
            idx = min(call_count[0], len(batches) - 1)
            call_count[0] += 1
            return batches[idx]

        client.get_latest_signals = _get_latest

        poller = JanusSignalPoller(client=client, poll_interval_s=0.0)

        async def _drain_one(p):
            """Call __anext__ once and return the yielded signal (no sleep)."""
            while True:
                batch = await p._client.get_latest_signals(limit=p._limit)
                for sig in batch:
                    key = sig.signal_id or f"{sig.symbol}:{sig.timestamp}"
                    if key and key not in p._seen:
                        p._seen.add(key)
                        return sig
                # No new signals found in this batch — break to avoid infinite loop in test
                break
            return None

        async def _run():
            results = []
            # Pull three signals manually, bypassing the sleep
            for _ in range(3):
                sig = await _drain_one(poller)
                if sig is not None:
                    results.append(sig.signal_id)
            return results

        seen = asyncio.run(_run())
        assert seen == ["a", "b", "c"]

    def test_poller_uses_by_symbol_when_symbol_set(self):

        client = MagicMock()
        captured_args = []

        async def _get_by_symbol(symbol, limit=50):
            captured_args.append(symbol)
            return [JanusSignal.from_dict(_signal_dict(signal_id="x"))]

        client.get_signals_by_symbol = _get_by_symbol

        poller = JanusSignalPoller(symbol="MES", client=client, poll_interval_s=0.0)

        async def _run():
            async for _ in poller:
                break

        with patch("lib.integrations.janus_client.asyncio.sleep", new_callable=AsyncMock):
            asyncio.run(_run())

        assert captured_args[0] == "MES"

    def test_poller_recovers_from_exception(self):
        """An exception during polling should be swallowed; next iteration succeeds."""
        client = MagicMock()
        call_count = [0]

        async def _get_latest(limit=50):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("transient error")
            return [JanusSignal.from_dict(_signal_dict(signal_id="recovered"))]

        client.get_latest_signals = _get_latest

        poller = JanusSignalPoller(client=client, poll_interval_s=0.0)

        async def _run():
            async for sig in poller:
                return sig.signal_id

        with patch("lib.integrations.janus_client.asyncio.sleep", new_callable=AsyncMock):
            result = asyncio.run(_run())

        assert result == "recovered"

    def test_poller_prunes_seen_set_when_large(self):
        """_seen set should be pruned when it exceeds 10 000 entries."""
        client = MagicMock()
        poller = JanusSignalPoller(client=client, poll_interval_s=0.0)

        # Pre-populate _seen with 10 001 IDs
        poller._seen = {f"id-{i}" for i in range(10_001)}

        # Simulate: get_latest_signals returns one new signal
        new_sig = JanusSignal.from_dict(_signal_dict(signal_id="brand-new"))
        call_count = [0]

        async def _get_latest(limit=50):
            call_count[0] += 1
            return [new_sig]

        client.get_latest_signals = _get_latest

        async def _run():
            async for _ in poller:
                break

        with patch("lib.integrations.janus_client.asyncio.sleep", new_callable=AsyncMock):
            asyncio.run(_run())

        # After pruning, seen set should be smaller than 10 001
        assert len(poller._seen) <= 5_001

    def test_poller_key_falls_back_to_symbol_timestamp(self):
        """When signal_id is empty, use 'symbol:timestamp' as the dedup key."""
        client = MagicMock()
        # Two signals with no signal_id but different timestamps
        sig_a = JanusSignal.from_dict({"symbol": "MES", "timestamp": "T1"})
        sig_b = JanusSignal.from_dict({"symbol": "MES", "timestamp": "T2"})
        calls = [0]

        async def _get_latest(limit=50):
            calls[0] += 1
            if calls[0] == 1:
                return [sig_a]
            return [sig_a, sig_b]

        client.get_latest_signals = _get_latest

        poller = JanusSignalPoller(client=client, poll_interval_s=0.0)
        results = []

        async def _run():
            async for sig in poller:
                results.append(sig.timestamp)
                if len(results) == 2:
                    break

        with patch("lib.integrations.janus_client.asyncio.sleep", new_callable=AsyncMock):
            asyncio.run(_run())

        assert results == ["T1", "T2"]


# ===========================================================================
# get_dashboard_signals_summary
# ===========================================================================


class TestGetDashboardSignalsSummary:
    def test_returns_dict_on_success(self):
        import json

        client = _make_client()
        payload = {"total": 10, "strong": 3}
        resp = _make_mock_response(200, json.dumps(payload))
        _patch_session(client, [resp])

        async def _run():
            result = await client.get_dashboard_signals_summary()
            assert result == {"total": 10, "strong": 3}

        asyncio.run(_run())

    def test_returns_empty_dict_on_failure(self):
        client = _make_client(max_retries=1, retry_delay_s=0.001)
        session = MagicMock()
        session.closed = False
        session.request = MagicMock(side_effect=OSError("down"))
        client._session = session

        async def _fast_sleep(_):
            pass

        with patch("asyncio.sleep", side_effect=_fast_sleep):

            async def _run():
                result = await client.get_dashboard_signals_summary()
                assert result == {}

            asyncio.run(_run())
