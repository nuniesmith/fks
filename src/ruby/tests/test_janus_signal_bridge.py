"""
Tests for JanusSignalBridge
============================
Covers:
  - Valid signal bridging from ``janus:signals`` → ``fks:signals:incoming``
  - Deduplication within the 60s window
  - Rejection of malformed / incomplete payloads (no crash, no republish)
  - Per-symbol latest-signal caching in ``janus:signal:latest:{symbol}``
  - ``get_status()`` correctness after bridging activity
"""

import json
import time

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal(
    *,
    signal_id: str = "sig-001",
    symbol: str = "BTCUSD",
    side: str = "LONG",
    strength: float = 0.85,
    confidence: float = 0.92,
    entry_price: float = 67500.0,
    stop_loss: float = 66000.0,
    take_profit: float = 70000.0,
    **overrides,
) -> dict:
    """Build a valid Janus signal payload matching the Rust ``SignalMessage`` struct."""
    sig = {
        "signal_id": signal_id,
        "symbol": symbol,
        "side": side,
        "strength": strength,
        "confidence": confidence,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
    }
    sig.update(overrides)
    return sig


class FakeRedis:
    """Minimal async Redis mock that tracks publish and set calls.

    Provides just enough surface area for ``JanusSignalBridge`` to function
    without a real Redis server.
    """

    def __init__(self):
        self.published: list[tuple[str, str]] = []
        self.store: dict[str, tuple[str, int | None]] = {}

    async def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = (value, ex)

    async def aclose(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBridgeProcessesValidSignal:
    """A well-formed signal on ``janus:signals`` should be republished to
    ``fks:signals:incoming`` with normalisation fields added."""

    @pytest.fixture()
    def redis(self):
        return FakeRedis()

    @pytest.fixture()
    def bridge(self, redis):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        return JanusSignalBridge(redis=redis)

    @pytest.mark.asyncio
    async def test_bridge_publishes_to_dest_channel(self, bridge, redis):
        signal = _make_signal()
        await bridge._process_signal(signal)

        assert len(redis.published) == 1
        channel, raw = redis.published[0]
        assert channel == "fks:signals:incoming"

        payload = json.loads(raw)
        assert payload["signal_id"] == "sig-001"
        assert payload["symbol"] == "BTCUSD"

    @pytest.mark.asyncio
    async def test_bridge_adds_normalisation_fields(self, bridge, redis):
        signal = _make_signal()
        await bridge._process_signal(signal)

        payload = json.loads(redis.published[0][1])
        assert payload["source"] == "janus_bridge"
        assert "bridge_timestamp" in payload
        assert isinstance(payload["bridge_timestamp"], float)

    @pytest.mark.asyncio
    async def test_bridge_maps_side_to_direction(self, bridge, redis):
        signal = _make_signal(side="SHORT")
        await bridge._process_signal(signal)

        payload = json.loads(redis.published[0][1])
        assert payload["direction"] == "SHORT"
        # Original ``side`` field preserved
        assert payload["side"] == "SHORT"

    @pytest.mark.asyncio
    async def test_bridge_uppercases_symbol(self, bridge, redis):
        signal = _make_signal(symbol="ethusd")
        await bridge._process_signal(signal)

        payload = json.loads(redis.published[0][1])
        assert payload["symbol"] == "ETHUSD"


class TestBridgeDeduplicates:
    """Publishing the same ``signal_id`` twice within the dedup window
    should result in only one republish."""

    @pytest.fixture()
    def redis(self):
        return FakeRedis()

    @pytest.fixture()
    def bridge(self, redis):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        return JanusSignalBridge(redis=redis)

    @pytest.mark.asyncio
    async def test_duplicate_signal_not_republished(self, bridge, redis):
        signal = _make_signal(signal_id="dup-001")

        await bridge._process_signal(signal)
        await bridge._process_signal(signal)

        assert len(redis.published) == 1

    @pytest.mark.asyncio
    async def test_dedup_counter_incremented(self, bridge, redis):
        signal = _make_signal(signal_id="dup-002")

        await bridge._process_signal(signal)
        await bridge._process_signal(signal)
        await bridge._process_signal(signal)

        assert bridge._signals_deduplicated == 2
        assert bridge._signals_bridged == 1

    @pytest.mark.asyncio
    async def test_different_signal_ids_not_deduplicated(self, bridge, redis):
        await bridge._process_signal(_make_signal(signal_id="a"))
        await bridge._process_signal(_make_signal(signal_id="b"))

        assert len(redis.published) == 2
        assert bridge._signals_deduplicated == 0

    @pytest.mark.asyncio
    async def test_expired_dedup_allows_reprocess(self, bridge, redis):
        """After the dedup window expires, the same signal_id is accepted."""
        signal = _make_signal(signal_id="expire-001")

        await bridge._process_signal(signal)
        assert len(redis.published) == 1

        # Manually expire the entry
        bridge._seen["expire-001"] = time.monotonic() - 1

        await bridge._process_signal(signal)
        assert len(redis.published) == 2


class TestBridgeRejectsInvalid:
    """Malformed or incomplete payloads must not crash the bridge or
    result in any publish to ``fks:signals:incoming``."""

    @pytest.fixture()
    def redis(self):
        return FakeRedis()

    @pytest.fixture()
    def bridge(self, redis):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        return JanusSignalBridge(redis=redis)

    @pytest.mark.asyncio
    async def test_missing_signal_id(self, bridge, redis):
        signal = _make_signal()
        del signal["signal_id"]
        await bridge._process_signal(signal)

        assert len(redis.published) == 0
        assert bridge._signals_invalid == 1

    @pytest.mark.asyncio
    async def test_missing_symbol(self, bridge, redis):
        signal = _make_signal()
        del signal["symbol"]
        await bridge._process_signal(signal)

        assert len(redis.published) == 0

    @pytest.mark.asyncio
    async def test_missing_side(self, bridge, redis):
        signal = _make_signal()
        del signal["side"]
        await bridge._process_signal(signal)

        assert len(redis.published) == 0

    @pytest.mark.asyncio
    async def test_missing_confidence(self, bridge, redis):
        signal = _make_signal()
        del signal["confidence"]
        await bridge._process_signal(signal)

        assert len(redis.published) == 0

    @pytest.mark.asyncio
    async def test_empty_dict(self, bridge, redis):
        await bridge._process_signal({})
        assert len(redis.published) == 0
        assert bridge._signals_invalid == 1

    @pytest.mark.asyncio
    async def test_completely_wrong_keys(self, bridge, redis):
        await bridge._process_signal({"foo": "bar", "baz": 42})
        assert len(redis.published) == 0


class TestBridgeCachesLatest:
    """Each bridged signal should update ``janus:signal:latest:{SYMBOL}``."""

    @pytest.fixture()
    def redis(self):
        return FakeRedis()

    @pytest.fixture()
    def bridge(self, redis):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        return JanusSignalBridge(redis=redis)

    @pytest.mark.asyncio
    async def test_cache_key_written(self, bridge, redis):
        await bridge._process_signal(_make_signal(symbol="SOLUSD"))

        key = "janus:signal:latest:SOLUSD"
        assert key in redis.store

        value_json, ttl = redis.store[key]
        cached = json.loads(value_json)
        assert cached["symbol"] == "SOLUSD"
        assert cached["source"] == "janus_bridge"

    @pytest.mark.asyncio
    async def test_cache_has_ttl(self, bridge, redis):
        from lib.services.engine.janus_signal_bridge import _CACHE_TTL

        await bridge._process_signal(_make_signal(symbol="XBTUSD"))

        _, ttl = redis.store["janus:signal:latest:XBTUSD"]
        assert ttl == _CACHE_TTL

    @pytest.mark.asyncio
    async def test_cache_updated_on_new_signal(self, bridge, redis):
        await bridge._process_signal(_make_signal(signal_id="c1", symbol="ETHUSD", confidence=0.5))
        await bridge._process_signal(_make_signal(signal_id="c2", symbol="ETHUSD", confidence=0.9))

        cached = json.loads(redis.store["janus:signal:latest:ETHUSD"][0])
        assert cached["confidence"] == 0.9
        assert cached["signal_id"] == "c2"


class TestBridgeStatus:
    """``get_status()`` should reflect correct counters and state."""

    @pytest.fixture()
    def redis(self):
        return FakeRedis()

    @pytest.fixture()
    def bridge(self, redis):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        return JanusSignalBridge(redis=redis)

    def test_initial_status(self, bridge):
        status = bridge.get_status()

        assert status["running"] is False
        assert status["signals_bridged"] == 0
        assert status["signals_deduplicated"] == 0
        assert status["signals_invalid"] == 0
        assert status["last_signal_at"] is None
        assert status["last_symbol"] is None
        assert status["uptime_secs"] == 0.0

    @pytest.mark.asyncio
    async def test_status_after_bridging(self, bridge, redis):
        # Simulate that bridge has started
        bridge._running = True
        bridge._started_at = time.monotonic() - 10.0

        await bridge._process_signal(_make_signal(signal_id="s1", symbol="BTCUSD"))
        await bridge._process_signal(_make_signal(signal_id="s1", symbol="BTCUSD"))  # dup
        await bridge._process_signal(_make_signal(signal_id="s2", symbol="ETHUSD"))
        await bridge._process_signal({})  # invalid

        status = bridge.get_status()
        assert status["running"] is True
        assert status["signals_bridged"] == 2
        assert status["signals_deduplicated"] == 1
        assert status["signals_invalid"] == 1
        assert status["last_symbol"] == "ETHUSD"
        assert status["last_signal_at"] is not None
        assert status["uptime_secs"] >= 10.0

    @pytest.mark.asyncio
    async def test_status_uptime_before_start(self, bridge):
        status = bridge.get_status()
        assert status["uptime_secs"] == 0.0


class TestBridgePruneSeen:
    """The internal ``_prune_seen`` helper should remove expired entries."""

    @pytest.fixture()
    def redis(self):
        return FakeRedis()

    @pytest.fixture()
    def bridge(self, redis):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        return JanusSignalBridge(redis=redis)

    def test_prune_removes_expired(self, bridge):
        now = time.monotonic()
        bridge._seen["old"] = now - 10  # expired
        bridge._seen["fresh"] = now + 60  # still valid

        pruned = bridge._prune_seen()

        assert pruned == 1
        assert "old" not in bridge._seen
        assert "fresh" in bridge._seen

    def test_prune_empty(self, bridge):
        assert bridge._prune_seen() == 0

    def test_is_duplicate_returns_false_for_unseen(self, bridge):
        assert bridge._is_duplicate("never-seen") is False

    def test_is_duplicate_returns_true_for_recent(self, bridge):
        bridge._seen["recent"] = time.monotonic() + 60
        assert bridge._is_duplicate("recent") is True

    def test_is_duplicate_returns_false_for_expired(self, bridge):
        bridge._seen["old"] = time.monotonic() - 1
        assert bridge._is_duplicate("old") is False
        # Also cleans up the entry
        assert "old" not in bridge._seen


class TestBridgePublishError:
    """If the Redis publish fails, the bridge should log and continue
    without crashing or updating counters."""

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_crash(self):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        redis = FakeRedis()

        async def _fail_publish(channel, message):
            raise ConnectionError("Redis gone")

        redis.publish = _fail_publish

        bridge = JanusSignalBridge(redis=redis)
        signal = _make_signal(signal_id="fail-001")

        # Should not raise
        await bridge._process_signal(signal)

        # Signal was NOT successfully bridged
        assert bridge._signals_bridged == 0

    @pytest.mark.asyncio
    async def test_cache_failure_does_not_crash(self):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        redis = FakeRedis()

        async def _fail_set(key, value, ex=None):
            raise ConnectionError("Redis gone")

        redis.set = _fail_set

        bridge = JanusSignalBridge(redis=redis)
        signal = _make_signal(signal_id="cache-fail-001")

        # Should not raise — cache failure is non-fatal
        await bridge._process_signal(signal)

        # Signal was still bridged (publish succeeded)
        assert bridge._signals_bridged == 1
        assert len(redis.published) == 1


class TestBridgeDirectionPreservation:
    """If the signal already has a ``direction`` field, the bridge should
    not overwrite it with ``side``."""

    @pytest.mark.asyncio
    async def test_existing_direction_preserved(self):
        from lib.services.engine.janus_signal_bridge import JanusSignalBridge

        redis = FakeRedis()
        bridge = JanusSignalBridge(redis=redis)

        signal = _make_signal(side="LONG", direction="EXIT")
        await bridge._process_signal(signal)

        payload = json.loads(redis.published[0][1])
        # Pre-existing direction should not be overwritten
        assert payload["direction"] == "EXIT"
        assert payload["side"] == "LONG"
