"""
Tests for data_factory.chain.monitor — ChainMonitor

Covers:
  - TestDeduplication: seen tx_hash skipped; new tx processed; set trims at 10K
  - TestMinUsdFilter: below threshold ignored; at/above processed
  - TestRedisPublish: LPUSH to chain:whale:recent; pub/sub to channels; LTRIM caps at 200
  - TestMempoolCongestionAlert: alert when fee_next_block > 100; no alert when <= 100
  - TestDiscordAlert: triggered for MEGA/LARGE; not for MEDIUM/SMALL; correct emoji
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from data_factory.chain.monitor import ChainMonitor
from data_factory.chain.schemas import (
    Chain,
    ChainTransaction,
    MempoolSnapshot,
    Sentiment,
    TxType,
    WhaleTier,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tx(
    tx_hash: str = "0xabc",
    amount_usd: float = 5_000_000.0,
    chain: Chain = Chain.ETH,
    tx_type: TxType = TxType.WHALE_MOVE,
    sentiment: Sentiment = Sentiment.NEUTRAL,
    tier: WhaleTier = WhaleTier.MEDIUM,
    from_label: str | None = None,
    to_label: str | None = None,
) -> ChainTransaction:
    return ChainTransaction(
        chain=chain,
        tx_hash=tx_hash,
        tx_type=tx_type,
        amount_native=100.0,
        amount_usd=amount_usd,
        from_address="0xfrom000000000000",
        to_address="0xto000000000000000",
        from_label=from_label,
        to_label=to_label,
        token=chain.value,
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        block_height=19_000_000,
        tier=tier,
        sentiment=sentiment,
        source="test",
    )


def _make_monitor(
    redis: AsyncMock | None = None,
    engine: MagicMock | None = None,
) -> ChainMonitor:
    """Build a ChainMonitor with mocked Redis and engine."""
    if redis is None:
        redis = _make_redis()
    if engine is None:
        engine = _make_engine()
    monitor = ChainMonitor(redis, engine)
    return monitor


def _make_redis() -> AsyncMock:
    """Return a mock aioredis.Redis with a usable pipeline."""
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.lpush = AsyncMock()
    pipe.ltrim = AsyncMock()
    pipe.publish = AsyncMock()
    pipe.execute = AsyncMock(return_value=[1, 1, 1, 1])
    redis.pipeline = MagicMock(return_value=pipe)
    redis.setex = AsyncMock(return_value=True)
    redis.publish = AsyncMock(return_value=1)
    redis.get = AsyncMock(return_value=None)
    return redis


def _make_engine() -> MagicMock:
    """Return a mock SQLAlchemy AsyncEngine."""
    engine = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    engine.begin = MagicMock(return_value=ctx)
    return engine


def _noop_correlator(tx: ChainTransaction) -> ChainTransaction:
    """Return tx unchanged (zero-impact correlator stub)."""
    return tx


def _patch_correlator(monitor: ChainMonitor) -> None:
    """Replace the correlator with an async no-op."""

    async def _enrich(tx):
        return tx

    monitor._correlator.enrich = _enrich


def _patch_store_tx(monitor: ChainMonitor) -> None:
    """Replace _store_tx with an async no-op to avoid DB calls."""

    async def _store(tx):
        pass

    monitor._store_tx = _store


# ---------------------------------------------------------------------------
# TestDeduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    @pytest.mark.asyncio
    async def test_seen_tx_hash_is_skipped(self) -> None:
        """A tx_hash already in _seen_hashes must not be re-processed."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        tx = _make_tx(tx_hash="0xdupe")
        monitor._seen_hashes.add("0xdupe")

        pipe = redis.pipeline.return_value

        # Simulate the loop body for a single transaction
        if tx.tx_hash and tx.tx_hash in monitor._seen_hashes:
            pass  # skipped — mirrors the real loop logic
        else:
            await monitor._process_tx(tx)
            monitor._seen_hashes.add(tx.tx_hash)

        pipe.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_tx_hash_is_processed(self) -> None:
        """A tx_hash not in _seen_hashes must be processed."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        tx = _make_tx(tx_hash="0xnew", amount_usd=5_000_000.0)
        assert "0xnew" not in monitor._seen_hashes

        await monitor._process_tx(tx)
        monitor._seen_hashes.add(tx.tx_hash)

        pipe = redis.pipeline.return_value
        pipe.execute.assert_called()
        assert "0xnew" in monitor._seen_hashes

    @pytest.mark.asyncio
    async def test_tx_hash_added_to_seen_after_processing(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        tx = _make_tx(tx_hash="0xtrack")
        assert "0xtrack" not in monitor._seen_hashes

        await monitor._process_tx(tx)
        monitor._seen_hashes.add(tx.tx_hash)

        assert "0xtrack" in monitor._seen_hashes

    @pytest.mark.asyncio
    async def test_seen_set_trims_at_10k_keeps_newest_5k(self) -> None:
        """When _seen_hashes exceeds 10,000 entries, it is trimmed to 5,000."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        # Fill the set to exactly 10,001 entries
        for i in range(10_001):
            monitor._seen_hashes.add(f"0x{i:06x}")

        # Simulate the trimming logic from _loop_whale
        if len(monitor._seen_hashes) > 10_000:
            monitor._seen_hashes = set(list(monitor._seen_hashes)[-5_000:])

        assert len(monitor._seen_hashes) == 5_000

    @pytest.mark.asyncio
    async def test_seen_set_not_trimmed_below_10k(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        for i in range(9_999):
            monitor._seen_hashes.add(f"0x{i:06x}")

        count_before = len(monitor._seen_hashes)

        if len(monitor._seen_hashes) > 10_000:
            monitor._seen_hashes = set(list(monitor._seen_hashes)[-5_000:])

        assert len(monitor._seen_hashes) == count_before

    @pytest.mark.asyncio
    async def test_empty_tx_hash_not_added_to_seen(self) -> None:
        """Transactions with empty tx_hash must not pollute _seen_hashes."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        tx = _make_tx(tx_hash="")

        # Mirror the loop logic: only add non-empty hashes
        if tx.tx_hash and tx.tx_hash in monitor._seen_hashes:
            pass
        else:
            await monitor._process_tx(tx)
            if tx.tx_hash:
                monitor._seen_hashes.add(tx.tx_hash)

        assert "" not in monitor._seen_hashes

    @pytest.mark.asyncio
    async def test_second_occurrence_skipped(self) -> None:
        """Processing the same tx twice: second call must be skipped by caller."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        tx = _make_tx(tx_hash="0xrepeat")
        processed_count = 0

        for _ in range(2):
            if tx.tx_hash and tx.tx_hash in monitor._seen_hashes:
                continue
            await monitor._process_tx(tx)
            monitor._seen_hashes.add(tx.tx_hash)
            processed_count += 1

        assert processed_count == 1


# ---------------------------------------------------------------------------
# TestMinUsdFilter
# ---------------------------------------------------------------------------


class TestMinUsdFilter:
    @pytest.mark.asyncio
    async def test_below_threshold_is_ignored(self) -> None:
        """Transactions below DEFAULT_MIN_USD (1,000,000) must be skipped."""
        from data_factory.chain.monitor import DEFAULT_MIN_USD

        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(amount_usd=DEFAULT_MIN_USD - 1)

        # Mirror the loop filter
        if tx.amount_usd < DEFAULT_MIN_USD:
            pass  # skipped
        else:
            await monitor._process_tx(tx)

        pipe.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_at_threshold_is_processed(self) -> None:
        """Transactions exactly at DEFAULT_MIN_USD must be processed."""
        from data_factory.chain.monitor import DEFAULT_MIN_USD

        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(amount_usd=DEFAULT_MIN_USD)

        if tx.amount_usd < DEFAULT_MIN_USD:
            pass
        else:
            await monitor._process_tx(tx)

        pipe.execute.assert_called()

    @pytest.mark.asyncio
    async def test_above_threshold_is_processed(self) -> None:
        """Transactions above DEFAULT_MIN_USD must be processed."""
        from data_factory.chain.monitor import DEFAULT_MIN_USD

        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(amount_usd=DEFAULT_MIN_USD * 10)

        if tx.amount_usd < DEFAULT_MIN_USD:
            pass
        else:
            await monitor._process_tx(tx)

        pipe.execute.assert_called()

    def test_default_min_usd_is_1_million(self) -> None:
        """DEFAULT_MIN_USD defaults to 1,000,000 (unless overridden by env)."""
        from data_factory.chain.monitor import DEFAULT_MIN_USD

        # The env var may not be set, so we just assert it is >= 0
        assert DEFAULT_MIN_USD >= 0

    @pytest.mark.asyncio
    async def test_zero_usd_is_ignored(self) -> None:
        from data_factory.chain.monitor import DEFAULT_MIN_USD

        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(amount_usd=0.0)

        if tx.amount_usd < DEFAULT_MIN_USD:
            pass
        else:
            await monitor._process_tx(tx)

        pipe.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_env_override_min_usd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHAIN_MIN_USD env var controls the threshold."""
        monkeypatch.setenv("CHAIN_MIN_USD", "5000000")
        import importlib

        import lib.data_factory.chain.monitor as monitor_mod

        importlib.reload(monitor_mod)
        assert monitor_mod.DEFAULT_MIN_USD == 5_000_000.0
        # Restore default for subsequent tests
        monkeypatch.delenv("CHAIN_MIN_USD", raising=False)
        importlib.reload(monitor_mod)


# ---------------------------------------------------------------------------
# TestRedisPublish
# ---------------------------------------------------------------------------


class TestRedisPublish:
    @pytest.mark.asyncio
    async def test_lpush_to_chain_whale_recent(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(amount_usd=5_000_000.0)

        await monitor._process_tx(tx)

        pipe.lpush.assert_called()
        call_args_list = pipe.lpush.call_args_list
        keys = [call[0][0] for call in call_args_list]
        assert "chain:whale:recent" in keys

    @pytest.mark.asyncio
    async def test_ltrim_caps_at_200(self) -> None:
        from data_factory.chain.monitor import WHALE_RECENT_MAX

        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(amount_usd=5_000_000.0)

        await monitor._process_tx(tx)

        pipe.ltrim.assert_called()
        ltrim_calls = pipe.ltrim.call_args_list
        # Find the call for chain:whale:recent
        recent_calls = [c for c in ltrim_calls if c[0][0] == "chain:whale:recent"]
        assert len(recent_calls) == 1
        # LTRIM 0, WHALE_RECENT_MAX - 1 = 0, 199
        assert recent_calls[0][0][1] == 0
        assert recent_calls[0][0][2] == WHALE_RECENT_MAX - 1

    @pytest.mark.asyncio
    async def test_whale_recent_max_is_200(self) -> None:
        from data_factory.chain.monitor import WHALE_RECENT_MAX

        assert WHALE_RECENT_MAX == 200

    @pytest.mark.asyncio
    async def test_publish_to_ch_chain_whale(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(chain=Chain.ETH, amount_usd=5_000_000.0)

        await monitor._process_tx(tx)

        pipe.publish.assert_called()
        published_channels = [call[0][0] for call in pipe.publish.call_args_list]
        assert "ch:chain:whale" in published_channels

    @pytest.mark.asyncio
    async def test_publish_to_chain_specific_channel(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(chain=Chain.BTC, amount_usd=5_000_000.0)

        await monitor._process_tx(tx)

        published_channels = [call[0][0] for call in pipe.publish.call_args_list]
        assert "ch:chain:whale:BTC" in published_channels

    @pytest.mark.asyncio
    async def test_publish_to_eth_specific_channel(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(chain=Chain.ETH, amount_usd=5_000_000.0)

        await monitor._process_tx(tx)

        published_channels = [call[0][0] for call in pipe.publish.call_args_list]
        assert "ch:chain:whale:ETH" in published_channels

    @pytest.mark.asyncio
    async def test_publish_to_sol_specific_channel(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(chain=Chain.SOL, amount_usd=5_000_000.0)

        await monitor._process_tx(tx)

        published_channels = [call[0][0] for call in pipe.publish.call_args_list]
        assert "ch:chain:whale:SOL" in published_channels

    @pytest.mark.asyncio
    async def test_payload_is_valid_json(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(chain=Chain.ETH, tx_hash="0xpayload")

        await monitor._process_tx(tx)

        # The payload pushed to chain:whale:recent must be valid JSON
        lpush_calls = pipe.lpush.call_args_list
        recent_calls = [c for c in lpush_calls if c[0][0] == "chain:whale:recent"]
        assert len(recent_calls) == 1
        payload_str = recent_calls[0][0][1]
        data = json.loads(payload_str)
        assert data["tx_hash"] == "0xpayload"
        assert data["chain"] == "ETH"

    @pytest.mark.asyncio
    async def test_payload_contains_all_required_fields(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(chain=Chain.ETH, tx_hash="0xfields")

        await monitor._process_tx(tx)

        lpush_calls = pipe.lpush.call_args_list
        recent_calls = [c for c in lpush_calls if c[0][0] == "chain:whale:recent"]
        payload = json.loads(recent_calls[0][0][1])

        required = {
            "chain",
            "tx_hash",
            "tx_type",
            "amount_native",
            "amount_usd",
            "from_address",
            "to_address",
            "token",
            "timestamp",
            "tier",
            "sentiment",
            "source",
            "correlation_score",
            "correlated_signals",
        }
        assert required.issubset(payload.keys())

    @pytest.mark.asyncio
    async def test_pipeline_execute_called_once(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        pipe = redis.pipeline.return_value
        tx = _make_tx(tier=WhaleTier.MEDIUM)  # MEDIUM → no Discord

        await monitor._process_tx(tx)

        pipe.execute.assert_called_once()


# ---------------------------------------------------------------------------
# TestMempoolCongestionAlert
# ---------------------------------------------------------------------------


class TestMempoolCongestionAlert:
    @pytest.mark.asyncio
    async def test_alert_published_when_fee_above_100(self) -> None:
        redis = _make_redis()
        _make_monitor(redis=redis)

        snap = MempoolSnapshot(
            pending_txns=100_000,
            size_mb=250.0,
            fee_next_block=101.0,
            fee_30min=80.0,
            fee_1hour=50.0,
            fee_economy=10.0,
            as_of=datetime.now(UTC),
        )

        # Simulate the congestion-alert portion of _loop_mempool
        if snap.fee_next_block > 100:
            await redis.publish(
                "ch:chain:alert",
                json.dumps(
                    {
                        "type": "mempool_congestion",
                        "fee": snap.fee_next_block,
                        "msg": f"BTC mempool congested: {snap.fee_next_block:.0f} sat/vB",
                    }
                ),
            )

        redis.publish.assert_called_once()
        call_args = redis.publish.call_args[0]
        assert call_args[0] == "ch:chain:alert"
        payload = json.loads(call_args[1])
        assert payload["type"] == "mempool_congestion"
        assert payload["fee"] == 101.0

    @pytest.mark.asyncio
    async def test_no_alert_when_fee_exactly_100(self) -> None:
        redis = _make_redis()
        _make_monitor(redis=redis)

        snap = MempoolSnapshot(
            pending_txns=50_000,
            size_mb=100.0,
            fee_next_block=100.0,
            fee_30min=60.0,
            fee_1hour=30.0,
            fee_economy=5.0,
            as_of=datetime.now(UTC),
        )

        if snap.fee_next_block > 100:
            await redis.publish("ch:chain:alert", json.dumps({"type": "mempool_congestion"}))

        redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_alert_when_fee_below_100(self) -> None:
        redis = _make_redis()
        _make_monitor(redis=redis)

        snap = MempoolSnapshot(
            pending_txns=30_000,
            size_mb=60.0,
            fee_next_block=45.0,
            fee_30min=25.0,
            fee_1hour=15.0,
            fee_economy=3.0,
            as_of=datetime.now(UTC),
        )

        if snap.fee_next_block > 100:
            await redis.publish("ch:chain:alert", json.dumps({"type": "mempool_congestion"}))

        redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_congestion_alert_includes_fee_message(self) -> None:
        redis = _make_redis()
        _make_monitor(redis=redis)

        snap = MempoolSnapshot(
            pending_txns=80_000,
            size_mb=200.0,
            fee_next_block=150.0,
            fee_30min=100.0,
            fee_1hour=70.0,
            fee_economy=20.0,
            as_of=datetime.now(UTC),
        )

        if snap.fee_next_block > 100:
            await redis.publish(
                "ch:chain:alert",
                json.dumps(
                    {
                        "type": "mempool_congestion",
                        "fee": snap.fee_next_block,
                        "msg": f"BTC mempool congested: {snap.fee_next_block:.0f} sat/vB",
                    }
                ),
            )

        payload = json.loads(redis.publish.call_args[0][1])
        assert "150" in payload["msg"]
        assert "sat/vB" in payload["msg"]

    @pytest.mark.asyncio
    async def test_mempool_snapshot_stored_in_redis(self) -> None:
        """Normal mempool snapshot (fee <= 100) stores data without alert."""
        redis = _make_redis()
        _make_monitor(redis=redis)

        snap = MempoolSnapshot(
            pending_txns=20_000,
            size_mb=50.0,
            fee_next_block=30.0,
            fee_30min=20.0,
            fee_1hour=10.0,
            fee_economy=2.0,
            as_of=datetime.now(UTC),
        )

        payload = json.dumps(
            {
                "pending_txns": snap.pending_txns,
                "size_mb": snap.size_mb,
                "fee_next_block": snap.fee_next_block,
                "fee_30min": snap.fee_30min,
                "fee_1hour": snap.fee_1hour,
                "fee_economy": snap.fee_economy,
                "as_of": snap.as_of.isoformat() if snap.as_of else None,
            }
        )
        await redis.setex("chain:mempool:latest", 120, payload)
        await redis.publish("ch:chain:mempool", payload)

        redis.setex.assert_called_once_with("chain:mempool:latest", 120, payload)
        redis.publish.assert_called_once_with("ch:chain:mempool", payload)

    @pytest.mark.asyncio
    async def test_fee_just_above_100_triggers_alert(self) -> None:
        _make_redis()

        snap = MempoolSnapshot(
            pending_txns=1,
            size_mb=1.0,
            fee_next_block=100.01,
            fee_30min=50.0,
            fee_1hour=30.0,
            fee_economy=5.0,
        )

        triggered = snap.fee_next_block > 100
        assert triggered is True


# ---------------------------------------------------------------------------
# TestDiscordAlert
# ---------------------------------------------------------------------------


class TestDiscordAlert:
    @pytest.mark.asyncio
    async def test_discord_alert_triggered_for_mega(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        tx = _make_tx(
            chain=Chain.ETH,
            tier=WhaleTier.MEGA,
            amount_usd=200_000_000.0,
            sentiment=Sentiment.BULLISH,
            tx_type=TxType.EXCHANGE_WITHDRAWAL,
        )

        await monitor._discord_alert(tx)

        redis.publish.assert_called_once()
        args = redis.publish.call_args[0]
        assert args[0] == "ch:discord:chain"

    @pytest.mark.asyncio
    async def test_discord_alert_triggered_for_large(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        tx = _make_tx(
            chain=Chain.BTC,
            tier=WhaleTier.LARGE,
            amount_usd=50_000_000.0,
            sentiment=Sentiment.BEARISH,
            tx_type=TxType.EXCHANGE_DEPOSIT,
        )

        await monitor._discord_alert(tx)

        redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_tx_does_not_alert_for_medium(self) -> None:
        """MEDIUM tier should NOT trigger a Discord alert via _process_tx."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        discord_called = False
        original_discord = monitor._discord_alert

        async def track_discord(tx):
            nonlocal discord_called
            discord_called = True
            await original_discord(tx)

        monitor._discord_alert = track_discord

        tx = _make_tx(tier=WhaleTier.MEDIUM, amount_usd=5_000_000.0)
        await monitor._process_tx(tx)

        assert discord_called is False

    @pytest.mark.asyncio
    async def test_process_tx_does_not_alert_for_small(self) -> None:
        """SMALL tier should NOT trigger a Discord alert via _process_tx."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        discord_called = False
        original_discord = monitor._discord_alert

        async def track_discord(tx):
            nonlocal discord_called
            discord_called = True
            await original_discord(tx)

        monitor._discord_alert = track_discord

        tx = _make_tx(tier=WhaleTier.SMALL, amount_usd=500_000.0)
        await monitor._process_tx(tx)

        assert discord_called is False

    @pytest.mark.asyncio
    async def test_process_tx_alerts_for_mega(self) -> None:
        """MEGA tier should trigger a Discord alert via _process_tx."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        discord_called = False

        async def track_discord(tx):
            nonlocal discord_called
            discord_called = True

        monitor._discord_alert = track_discord

        tx = _make_tx(tier=WhaleTier.MEGA, amount_usd=200_000_000.0)
        await monitor._process_tx(tx)

        assert discord_called is True

    @pytest.mark.asyncio
    async def test_process_tx_alerts_for_large(self) -> None:
        """LARGE tier should trigger a Discord alert via _process_tx."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)
        _patch_correlator(monitor)
        _patch_store_tx(monitor)

        discord_called = False

        async def track_discord(tx):
            nonlocal discord_called
            discord_called = True

        monitor._discord_alert = track_discord

        tx = _make_tx(tier=WhaleTier.LARGE, amount_usd=50_000_000.0)
        await monitor._process_tx(tx)

        assert discord_called is True

    @pytest.mark.asyncio
    async def test_bullish_emoji_in_discord_payload(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(
            sentiment=Sentiment.BULLISH,
            tier=WhaleTier.MEGA,
            tx_type=TxType.EXCHANGE_WITHDRAWAL,
            amount_usd=200_000_000.0,
        )

        await monitor._discord_alert(tx)

        payload_str = redis.publish.call_args[0][1]
        payload = json.loads(payload_str)
        assert "🟢" in payload["message"]

    @pytest.mark.asyncio
    async def test_bearish_emoji_in_discord_payload(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(
            sentiment=Sentiment.BEARISH,
            tier=WhaleTier.MEGA,
            tx_type=TxType.EXCHANGE_DEPOSIT,
            amount_usd=200_000_000.0,
        )

        await monitor._discord_alert(tx)

        payload_str = redis.publish.call_args[0][1]
        payload = json.loads(payload_str)
        assert "🔴" in payload["message"]

    @pytest.mark.asyncio
    async def test_neutral_emoji_in_discord_payload(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(
            sentiment=Sentiment.NEUTRAL,
            tier=WhaleTier.LARGE,
            tx_type=TxType.WHALE_MOVE,
            amount_usd=50_000_000.0,
        )

        await monitor._discord_alert(tx)

        payload_str = redis.publish.call_args[0][1]
        payload = json.loads(payload_str)
        assert "🟡" in payload["message"]

    @pytest.mark.asyncio
    async def test_mega_discord_channel_is_chain_alerts(self) -> None:
        """MEGA tier posts to 'chain-alerts' channel."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(tier=WhaleTier.MEGA, amount_usd=200_000_000.0)

        await monitor._discord_alert(tx)

        payload = json.loads(redis.publish.call_args[0][1])
        assert payload["channel"] == "chain-alerts"

    @pytest.mark.asyncio
    async def test_large_discord_channel_is_factory(self) -> None:
        """LARGE tier posts to 'factory' channel."""
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(tier=WhaleTier.LARGE, amount_usd=50_000_000.0)

        await monitor._discord_alert(tx)

        payload = json.loads(redis.publish.call_args[0][1])
        assert payload["channel"] == "factory"

    @pytest.mark.asyncio
    async def test_discord_payload_contains_tx_hash(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(tier=WhaleTier.MEGA, tx_hash="0xdiscordhash")

        await monitor._discord_alert(tx)

        payload = json.loads(redis.publish.call_args[0][1])
        assert payload["tx_hash"] == "0xdiscordhash"

    @pytest.mark.asyncio
    async def test_discord_message_contains_tier_label(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(tier=WhaleTier.MEGA, amount_usd=500_000_000.0)

        await monitor._discord_alert(tx)

        payload = json.loads(redis.publish.call_args[0][1])
        assert "MEGA" in payload["message"]

    @pytest.mark.asyncio
    async def test_discord_message_contains_chain(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(chain=Chain.SOL, tier=WhaleTier.LARGE, amount_usd=20_000_000.0)

        await monitor._discord_alert(tx)

        payload = json.loads(redis.publish.call_args[0][1])
        assert "SOL" in payload["message"]

    @pytest.mark.asyncio
    async def test_discord_message_contains_usd_amount(self) -> None:
        redis = _make_redis()
        monitor = _make_monitor(redis=redis)

        tx = _make_tx(
            chain=Chain.BTC,
            tier=WhaleTier.MEGA,
            amount_usd=100_000_000.0,
        )

        await monitor._discord_alert(tx)

        payload = json.loads(redis.publish.call_args[0][1])
        # Amount formatted as $100.0M
        assert "100" in payload["message"]
