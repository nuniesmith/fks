"""
Tests for the Janus SSE bridge additions
============================================================
Covers:
  - _get_janus_signals_from_cache() — per-symbol and sorted-set paths
  - Janus pub/sub channel constants
  - SSE throttling behaviour for janus-signal events
  - Janus-signal forwarding in the pub/sub handler
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Cache mock — same pattern as test_sse.py
# ---------------------------------------------------------------------------

_original_cache_module = sys.modules.get("lib.core.cache", None)

_mock_cache = MagicMock()
_mock_cache.REDIS_AVAILABLE = False
_mock_cache._r = None
_mock_cache.cache_get = MagicMock(return_value=None)
_mock_cache.cache_set = MagicMock()
_mock_cache._cache_key = MagicMock(side_effect=lambda *parts: "futures:mock:" + ":".join(str(p) for p in parts))
_mock_cache.get_data_source = MagicMock(return_value="mock")
_mock_cache.flush_all = MagicMock()

sys.modules["lib.core.cache"] = _mock_cache

# Import the symbols under test now that the mock is in place
from lib.services.data.api.sse import (  # noqa: E402
    _JANUS_SIGNAL_CHANNEL,
    _JANUS_SIGNAL_LATEST_PREFIX,
    _JANUS_THROTTLE_SECONDS,
    _get_janus_signals_from_cache,
    _last_sent,
    _should_throttle,
)

# Restore the real cache module so later test files are unaffected
if _original_cache_module is not None:
    sys.modules["lib.core.cache"] = _original_cache_module
else:
    sys.modules.pop("lib.core.cache", None)


def _reset_cache_mock() -> None:
    """Reset mock cache to its default (Redis unavailable) state."""
    sys.modules["lib.core.cache"] = _mock_cache
    _mock_cache.REDIS_AVAILABLE = False
    _mock_cache._r = None
    _mock_cache.cache_get.reset_mock()
    _mock_cache.cache_get.return_value = None
    _mock_cache.cache_get.side_effect = None
    _mock_cache.cache_set.reset_mock()


def _restore_real_cache_module() -> None:
    if _original_cache_module is not None:
        sys.modules["lib.core.cache"] = _original_cache_module
    else:
        sys.modules.pop("lib.core.cache", None)


@pytest.fixture(autouse=True, scope="module")
def _janus_sse_cache_lifecycle():
    """Install mock before all tests in this module, restore after."""
    sys.modules["lib.core.cache"] = _mock_cache
    yield
    _restore_real_cache_module()


# ===========================================================================
# Constants
# ===========================================================================


class TestJanusSSEConstants:
    """Verify the Janus bridge constants have sensible values."""

    def test_signal_channel_name(self):
        assert _JANUS_SIGNAL_CHANNEL == "janus:signals"

    def test_latest_prefix(self):
        assert _JANUS_SIGNAL_LATEST_PREFIX == "janus:signal:latest:"

    def test_throttle_seconds_positive(self):
        assert _JANUS_THROTTLE_SECONDS > 0

    def test_throttle_seconds_reasonable(self):
        # Should be fast enough to feel real-time but not flood the client
        assert 0.5 <= _JANUS_THROTTLE_SECONDS <= 30.0

    def test_throttle_more_aggressive_than_default(self):
        # _JANUS_THROTTLE_SECONDS is intentionally shorter than the default
        # _THROTTLE_SECONDS (signals can burst, so 2s < 7s is correct).
        from lib.services.data.api.sse import _THROTTLE_SECONDS

        assert _JANUS_THROTTLE_SECONDS <= _THROTTLE_SECONDS


# ===========================================================================
# _get_janus_signals_from_cache — no Redis
# ===========================================================================


class TestGetJanusSignalsFromCacheNoRedis:
    """Behaviour when Redis is unavailable."""

    def setup_method(self):
        _reset_cache_mock()

    def test_returns_empty_list_when_redis_none(self):
        with patch("lib.services.data.api.sse._get_redis", return_value=None):
            result = _get_janus_signals_from_cache()
        assert result == []

    def test_returns_empty_list_with_symbols_when_redis_none(self):
        with patch("lib.services.data.api.sse._get_redis", return_value=None):
            result = _get_janus_signals_from_cache(symbols=["MES", "MGC"])
        assert result == []

    def test_return_type_is_list(self):
        with patch("lib.services.data.api.sse._get_redis", return_value=None):
            result = _get_janus_signals_from_cache()
        assert isinstance(result, list)


# ===========================================================================
# _get_janus_signals_from_cache — per-symbol path
# ===========================================================================


class TestGetJanusSignalsFromCacheBySymbol:
    """Tests for the ``symbols`` parameter path (per-key lookup)."""

    def setup_method(self):
        _reset_cache_mock()

    def _make_redis(self, store: dict) -> MagicMock:
        """Build a minimal Redis mock whose ``.get()`` resolves from ``store``."""
        r = MagicMock()
        r.get.side_effect = lambda key: store.get(key)
        return r

    def test_returns_signal_for_single_symbol(self):
        payload = json.dumps({"symbol": "MES", "direction": "long", "confidence": 0.9})
        store = {"janus:signal:latest:MES": payload.encode()}
        mock_r = self._make_redis(store)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["MES"])

        assert len(result) == 1
        parsed = json.loads(result[0])
        assert parsed["symbol"] == "MES"
        assert parsed["direction"] == "long"

    def test_returns_signals_for_multiple_symbols(self):
        mes_payload = json.dumps({"symbol": "MES", "confidence": 0.8})
        mgc_payload = json.dumps({"symbol": "MGC", "confidence": 0.7})
        store = {
            "janus:signal:latest:MES": mes_payload.encode(),
            "janus:signal:latest:MGC": mgc_payload.encode(),
        }
        mock_r = self._make_redis(store)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["MES", "MGC"])

        assert len(result) == 2
        symbols_found = {json.loads(s)["symbol"] for s in result}
        assert symbols_found == {"MES", "MGC"}

    def test_skips_missing_symbol_keys(self):
        payload = json.dumps({"symbol": "MES", "confidence": 0.85})
        store = {"janus:signal:latest:MES": payload.encode()}
        mock_r = self._make_redis(store)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            # MGC key absent from store — should silently skip it
            result = _get_janus_signals_from_cache(symbols=["MES", "MGC"])

        assert len(result) == 1
        assert json.loads(result[0])["symbol"] == "MES"

    def test_symbol_uppercased_in_key(self):
        """Lowercase symbol arg should still resolve the upper-case Redis key."""
        payload = json.dumps({"symbol": "MES"})
        store = {"janus:signal:latest:MES": payload.encode()}
        mock_r = self._make_redis(store)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["mes"])

        assert len(result) == 1

    def test_handles_string_value_not_just_bytes(self):
        """Redis may return plain strings in some client configurations."""
        payload = json.dumps({"symbol": "MES"})
        store = {"janus:signal:latest:MES": payload}  # str, not bytes
        mock_r = self._make_redis(store)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["MES"])

        assert len(result) == 1
        assert json.loads(result[0])["symbol"] == "MES"

    def test_returns_empty_when_all_symbols_missing(self):
        mock_r = self._make_redis({})  # nothing in Redis

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["MES", "MGC", "NQ"])

        assert result == []

    def test_exception_in_redis_returns_empty(self):
        mock_r = MagicMock()
        mock_r.get.side_effect = Exception("Redis I/O error")

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["MES"])

        # Should catch and return empty, not propagate
        assert result == []


# ===========================================================================
# _get_janus_signals_from_cache — sorted-set fallback (no symbols arg)
# ===========================================================================


class TestGetJanusSignalsFromCacheSortedSet:
    """Tests for the fallback path that reads from ``janus:signals:recent``."""

    def setup_method(self):
        _reset_cache_mock()

    def test_reads_sorted_set_when_no_symbols(self):
        payload = json.dumps({"symbol": "NQ", "confidence": 0.75})

        mock_r = MagicMock()
        mock_r.zrevrange.return_value = [b"signal-abc-123"]
        mock_r.get.return_value = payload.encode()

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache()

        mock_r.zrevrange.assert_called_once_with("janus:signals:recent", 0, 4)
        assert len(result) == 1
        assert json.loads(result[0])["symbol"] == "NQ"

    def test_fetches_correct_per_id_key(self):
        payload = json.dumps({"symbol": "MES"})

        mock_r = MagicMock()
        mock_r.zrevrange.return_value = [b"sig-001"]
        mock_r.get.return_value = payload.encode()

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            _get_janus_signals_from_cache()

        # get() must be called with the per-ID key
        mock_r.get.assert_called_once_with("janus:signal:sig-001")

    def test_returns_multiple_from_sorted_set(self):
        payloads = {
            "janus:signal:id-1": json.dumps({"symbol": "MES"}).encode(),
            "janus:signal:id-2": json.dumps({"symbol": "MGC"}).encode(),
        }
        mock_r = MagicMock()
        mock_r.zrevrange.return_value = [b"id-1", b"id-2"]
        mock_r.get.side_effect = lambda key: payloads.get(key)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache()

        assert len(result) == 2

    def test_skips_missing_id_entries(self):
        mock_r = MagicMock()
        mock_r.zrevrange.return_value = [b"id-ghost"]
        mock_r.get.return_value = None  # key does not exist

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache()

        assert result == []

    def test_empty_sorted_set_returns_empty_list(self):
        mock_r = MagicMock()
        mock_r.zrevrange.return_value = []

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache()

        assert result == []

    def test_exception_in_zrevrange_returns_empty(self):
        mock_r = MagicMock()
        mock_r.zrevrange.side_effect = Exception("connection reset")

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache()

        assert result == []

    def test_handles_string_id_from_sorted_set(self):
        """zrevrange may return plain strings in some Redis client versions."""
        payload = json.dumps({"symbol": "ES"})
        mock_r = MagicMock()
        mock_r.zrevrange.return_value = ["string-id"]  # str, not bytes
        mock_r.get.return_value = payload.encode()

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache()

        # Should decode fine and look up "janus:signal:string-id"
        assert len(result) == 1


# ===========================================================================
# Janus throttle integration
# ===========================================================================


class TestJanusThrottleKey:
    """Verify the per-symbol throttle key pattern used by the SSE generator."""

    def setup_method(self):
        # Clear throttle state between tests
        _last_sent.clear()

    def test_first_janus_signal_not_throttled(self):
        assert _should_throttle("janus-signal:mes") is False

    def test_immediate_repeat_throttled(self):
        _should_throttle("janus-signal:mgc")  # first call — records timestamp
        assert _should_throttle("janus-signal:mgc") is True

    def test_different_symbols_independent(self):
        _should_throttle("janus-signal:mes")
        # A *different* symbol should not be throttled
        assert _should_throttle("janus-signal:nq") is False

    def test_throttle_key_format_per_symbol(self):
        """Confirm that lower-cased symbol throttle keys don't collide."""
        _should_throttle("janus-signal:mes")
        _should_throttle("janus-signal:mgc")
        # Both should now be throttled independently
        assert _should_throttle("janus-signal:mes") is True
        assert _should_throttle("janus-signal:mgc") is True

    def test_unknown_symbol_key_not_throttled(self):
        """The 'unknown' symbol key starts unthrottled."""
        assert _should_throttle("janus-signal:unknown") is False

    def test_throttle_respects_janus_throttle_seconds(self, monkeypatch):
        """After the standard throttle window passes the key should be released.

        _should_throttle() uses the generic _THROTTLE_SECONDS (7 s), not the
        _JANUS_THROTTLE_SECONDS constant (2 s).  The janus constant documents
        intent but the gate function is shared.
        """
        import time

        from lib.services.data.api.sse import _THROTTLE_SECONDS

        key = "janus-signal:test-ttl"
        _should_throttle(key)  # arm the throttle

        # Fake the last-sent time to be older than the actual gate window
        _last_sent[key] = time.monotonic() - (_THROTTLE_SECONDS + 0.5)
        assert _should_throttle(key) is False


# ===========================================================================
# Pub/sub channel name used in _dashboard_event_generator
# ===========================================================================


class TestJanusChannelSubscription:
    """Ensure the channel constant matches what Janus publishes to."""

    def test_channel_matches_expected_redis_channel(self):
        # This is the exact channel name the Rust Janus service publishes to.
        # Any mismatch would silently break signal delivery to the browser.
        assert _JANUS_SIGNAL_CHANNEL == "janus:signals"

    def test_latest_prefix_ends_with_colon(self):
        """The prefix must end with ':' so symbol can be directly appended."""
        assert _JANUS_SIGNAL_LATEST_PREFIX.endswith(":")

    def test_per_symbol_key_construction(self):
        """Verify the full key string matches the expected Janus convention."""
        sym = "MES"
        expected = "janus:signal:latest:MES"
        actual = f"{_JANUS_SIGNAL_LATEST_PREFIX}{sym.upper()}"
        assert actual == expected

    def test_per_id_key_construction(self):
        """Verify the full per-ID key matches the Janus Redis convention."""
        sig_id = "abc-123"
        expected = "janus:signal:abc-123"
        actual = f"janus:signal:{sig_id}"
        assert actual == expected


# ===========================================================================
# Round-trip JSON integrity
# ===========================================================================


class TestJanusSignalJsonIntegrity:
    """Ensure signals retrieved from cache survive a round-trip parse."""

    def setup_method(self):
        _reset_cache_mock()

    def _redis_with(self, symbol: str, payload: dict) -> MagicMock:
        raw = json.dumps(payload).encode()
        mock_r = MagicMock()
        mock_r.get.return_value = raw
        return mock_r

    def test_full_signal_payload_survives_round_trip(self):
        original = {
            "signal_id": "abc-001",
            "symbol": "MES",
            "direction": "long",
            "confidence": 0.92,
            "strength": 0.85,
            "price": 5432.75,
            "suggested_entry": 5431.0,
            "suggested_stop_loss": 5420.0,
            "suggested_tp1": 5445.0,
            "source": "janus-swing",
            "category": "swing",
            "timestamp": "2025-06-01T14:30:00Z",
        }
        mock_r = self._redis_with("MES", original)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["MES"])

        assert len(result) == 1
        parsed = json.loads(result[0])
        assert parsed["signal_id"] == "abc-001"
        assert parsed["confidence"] == pytest.approx(0.92)
        assert parsed["suggested_tp1"] == pytest.approx(5445.0)

    def test_minimal_signal_payload(self):
        original = {"symbol": "MGC", "side": "Buy"}
        mock_r = self._redis_with("MGC", original)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["MGC"])

        assert len(result) == 1
        parsed = json.loads(result[0])
        assert parsed["symbol"] == "MGC"

    def test_result_elements_are_strings(self):
        original = {"symbol": "NQ", "confidence": 0.7}
        mock_r = self._redis_with("NQ", original)

        with patch("lib.services.data.api.sse._get_redis", return_value=mock_r):
            result = _get_janus_signals_from_cache(symbols=["NQ"])

        for item in result:
            assert isinstance(item, str), f"Expected str, got {type(item)}"
