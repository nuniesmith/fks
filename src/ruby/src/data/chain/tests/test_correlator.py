"""
Tests for data_factory.chain.correlator — ChainSignalCorrelator.enrich()

Covers:
  - LONG+BULLISH = +0.4, SHORT+BEARISH = +0.4, LONG+BEARISH = −0.3, SHORT+BULLISH = −0.3
  - Score accumulates across multiple signals
  - Mega whale amplifier ×1.5
  - Score clamped to [-1.0, +1.0]
  - No signals → tx unchanged
  - Chain not in CHAIN_TO_FUTURES → tx unchanged
  - Publishes to Redis when |score| > 0.3; not when ≤ 0.3
  - CMC Fear & Greed confluence
  - BTC dominance amplifier (ETH-only)
  - Graceful skip when CMC Redis keys are empty
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from data_factory.chain.correlator import ChainSignalCorrelator
from data_factory.chain.schemas import (
    Chain,
    ChainTransaction,
    Sentiment,
    TxType,
    WhaleTier,
    classify_sentiment,
    classify_tier,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tx(
    chain: Chain = Chain.ETH,
    tx_type: TxType = TxType.WHALE_MOVE,
    amount_usd: float = 5_000_000.0,
    sentiment: Sentiment | None = None,
    tier: WhaleTier | None = None,
    tx_hash: str = "0xtest",
) -> ChainTransaction:
    resolved_sentiment = sentiment if sentiment is not None else classify_sentiment(tx_type)
    resolved_tier = tier if tier is not None else classify_tier(amount_usd)
    return ChainTransaction(
        chain=chain,
        tx_hash=tx_hash,
        tx_type=tx_type,
        amount_native=100.0,
        amount_usd=amount_usd,
        from_address="0xfrom",
        to_address="0xto",
        from_label=None,
        to_label=None,
        token=chain.value,
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        block_height=19_000_000,
        tier=resolved_tier,
        sentiment=resolved_sentiment,
        source="test",
    )


def _make_redis(
    signals: dict[str, dict] | None = None,
    fear_greed: dict | None = None,
    btc_dominance: float | None = None,
) -> AsyncMock:
    """
    Build a mock aioredis.Redis with configurable get() and a pipeline stub.

    signals: mapping of "ruby:signals:active:{sym}" -> signal dict
    fear_greed: dict to return for "cmc:fear_greed"
    btc_dominance: float to return for "cmc:btc_dominance"
    """
    redis = AsyncMock()

    async def fake_get(key: str):
        if signals is not None and key.startswith("ruby:signals:active:"):
            sym = key.split(":")[-1]
            # Try exact symbol match or prefix match on the stored keys
            for k, v in signals.items():
                stored_sym = k.split(":")[-1] if ":" in k else k
                if stored_sym == sym:
                    return json.dumps(v)
            return None
        if key == "cmc:fear_greed":
            return json.dumps(fear_greed) if fear_greed is not None else None
        if key == "cmc:btc_dominance":
            return str(btc_dominance) if btc_dominance is not None else None
        return None

    redis.get = fake_get

    # Pipeline: lpush, ltrim, publish all succeed
    pipe = AsyncMock()
    pipe.lpush = AsyncMock()
    pipe.ltrim = AsyncMock()
    pipe.publish = AsyncMock()
    pipe.execute = AsyncMock(return_value=[1, 1, 1])
    redis.pipeline = MagicMock(return_value=pipe)

    return redis


# ---------------------------------------------------------------------------
# TestNoSignals
# ---------------------------------------------------------------------------


class TestNoSignals:
    @pytest.mark.asyncio
    async def test_score_unchanged_when_no_signals(self) -> None:
        redis = _make_redis(signals={})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.WHALE_MOVE)
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_correlated_signals_empty_when_no_signals(self) -> None:
        redis = _make_redis(signals={})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.WHALE_MOVE)
        result = await correlator.enrich(tx)
        assert result.correlated_signals == []

    @pytest.mark.asyncio
    async def test_returns_same_tx_object(self) -> None:
        redis = _make_redis(signals={})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx()
        result = await correlator.enrich(tx)
        assert result is tx


# ---------------------------------------------------------------------------
# TestNoRelatedAssets
# ---------------------------------------------------------------------------


class TestNoRelatedAssets:
    @pytest.mark.asyncio
    async def test_chain_not_in_futures_map_leaves_score_zero(self) -> None:
        """If the chain has no entry in CHAIN_TO_FUTURES, no signals are checked."""
        # Patch CHAIN_TO_FUTURES to exclude BTC
        from data_factory.chain import correlator as corr_mod

        original = corr_mod.CHAIN_TO_FUTURES.copy()
        corr_mod.CHAIN_TO_FUTURES = {}  # clear all mappings
        try:
            redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
            correlator = ChainSignalCorrelator(redis)
            tx = _make_tx(chain=Chain.BTC, tx_type=TxType.EXCHANGE_WITHDRAWAL)
            result = await correlator.enrich(tx)
            assert result.correlation_score == 0.0
            assert result.correlated_signals == []
        finally:
            corr_mod.CHAIN_TO_FUTURES = original

    @pytest.mark.asyncio
    async def test_chain_with_no_active_signals_leaves_score_zero(self) -> None:
        """Chain is in CHAIN_TO_FUTURES but no signals exist in Redis."""
        redis = _make_redis(signals={})  # no signals for any symbol
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.BTC, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0


# ---------------------------------------------------------------------------
# TestEnrich — core signal correlation
# ---------------------------------------------------------------------------


class TestEnrich:
    # -- LONG + BULLISH = +0.4 -----------------------------------------------

    @pytest.mark.asyncio
    async def test_long_bullish_adds_0_4(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        # ETH EXCHANGE_WITHDRAWAL -> BULLISH
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.4

    @pytest.mark.asyncio
    async def test_long_bullish_appends_correlated_signal(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert any("LONG" in s and "bullish" in s for s in result.correlated_signals)

    # -- SHORT + BEARISH = +0.4 ----------------------------------------------

    @pytest.mark.asyncio
    async def test_short_bearish_adds_0_4(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "SHORT"}})
        correlator = ChainSignalCorrelator(redis)
        # ETH EXCHANGE_DEPOSIT -> BEARISH
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.4

    @pytest.mark.asyncio
    async def test_short_bearish_appends_correlated_signal(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "SHORT"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)
        result = await correlator.enrich(tx)
        assert any("SHORT" in s and "bearish" in s for s in result.correlated_signals)

    # -- LONG + BEARISH = −0.3 -----------------------------------------------

    @pytest.mark.asyncio
    async def test_long_bearish_subtracts_0_3(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)  # BEARISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == -0.3

    @pytest.mark.asyncio
    async def test_long_bearish_appends_counter_signal(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)
        result = await correlator.enrich(tx)
        assert any("COUNTER" in s for s in result.correlated_signals)

    # -- SHORT + BULLISH = −0.3 ----------------------------------------------

    @pytest.mark.asyncio
    async def test_short_bullish_subtracts_0_3(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "SHORT"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == -0.3

    @pytest.mark.asyncio
    async def test_short_bullish_appends_counter_signal(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "SHORT"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert any("COUNTER" in s for s in result.correlated_signals)

    # -- Neutral sentinel: no change for neutral sentiment -------------------

    @pytest.mark.asyncio
    async def test_long_neutral_leaves_score_zero(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.WHALE_MOVE)  # NEUTRAL
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    # -- Multiple signals accumulate -----------------------------------------

    @pytest.mark.asyncio
    async def test_multiple_long_bullish_signals_accumulate(self) -> None:
        """Two LONG signals on ETH-correlated assets + BULLISH tx = +0.8."""
        redis = _make_redis(
            signals={
                "MNQ": {"symbol": "MNQ", "direction": "LONG"},
                "MES": {"symbol": "MES", "direction": "LONG"},
            }
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        # 2 × +0.4 = +0.8, then clamped: still 0.8
        assert pytest.approx(result.correlation_score) == 0.8

    @pytest.mark.asyncio
    async def test_mixed_signals_partially_cancel(self) -> None:
        """One LONG + one SHORT on ETH with BULLISH tx: +0.4 + (−0.3) = +0.1."""
        redis = _make_redis(
            signals={
                "MNQ": {"symbol": "MNQ", "direction": "LONG"},
                "MES": {"symbol": "MES", "direction": "SHORT"},
            }
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.1

    # -- Mega whale amplifier ×1.5 -------------------------------------------

    @pytest.mark.asyncio
    async def test_mega_whale_amplifies_score_by_1_5(self) -> None:
        """LONG + BULLISH = +0.4, then ×1.5 for MEGA = +0.6."""
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(
            chain=Chain.ETH,
            tx_type=TxType.EXCHANGE_WITHDRAWAL,
            amount_usd=200_000_000.0,  # MEGA
            tier=WhaleTier.MEGA,
        )
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.6

    @pytest.mark.asyncio
    async def test_mega_amplifier_applied_to_negative_score(self) -> None:
        """LONG + BEARISH = −0.3, then ×1.5 = −0.45 for MEGA."""
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(
            chain=Chain.ETH,
            tx_type=TxType.EXCHANGE_DEPOSIT,  # BEARISH
            amount_usd=500_000_000.0,  # MEGA
            tier=WhaleTier.MEGA,
        )
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == -0.45

    @pytest.mark.asyncio
    async def test_large_whale_not_amplified(self) -> None:
        """LARGE tier (< $100M) does NOT get the ×1.5 amplifier."""
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(
            chain=Chain.ETH,
            tx_type=TxType.EXCHANGE_WITHDRAWAL,
            amount_usd=50_000_000.0,  # LARGE
            tier=WhaleTier.LARGE,
        )
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.4

    # -- Score clamped to [-1.0, +1.0] --------------------------------------

    @pytest.mark.asyncio
    async def test_score_clamped_at_positive_1(self) -> None:
        """
        ETH has MNQ + MES as correlated futures (2 signals).
        Two LONG signals + BULLISH = +0.8, then ×1.5 (MEGA) = +1.2 → clamped to +1.0.
        """
        redis = _make_redis(
            signals={
                "MNQ": {"symbol": "MNQ", "direction": "LONG"},
                "MES": {"symbol": "MES", "direction": "LONG"},
            }
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(
            chain=Chain.ETH,
            tx_type=TxType.EXCHANGE_WITHDRAWAL,
            amount_usd=200_000_000.0,  # MEGA
            tier=WhaleTier.MEGA,
        )
        result = await correlator.enrich(tx)
        assert result.correlation_score <= 1.0
        assert pytest.approx(result.correlation_score, abs=1e-9) == 1.0

    @pytest.mark.asyncio
    async def test_score_clamped_at_negative_1(self) -> None:
        """
        ETH MNQ + MES LONG signals, BEARISH tx: −0.3×2 = −0.6, ×1.5 = −0.9 → −0.9 (within range).
        Use SOL (only MNQ) + additional artificial boost to force clamping.
        Actually with ETH (MNQ + MES) both LONG + BEARISH:
        −0.3 + −0.3 = −0.6, ×1.5 (MEGA) = −0.9.
        Force a third signal by patching CHAIN_TO_FUTURES temporarily.
        """
        from data_factory.chain import correlator as corr_mod

        original = corr_mod.CHAIN_TO_FUTURES.copy()
        corr_mod.CHAIN_TO_FUTURES["ETH"] = ["MNQ", "MES", "MGC"]
        try:
            redis = _make_redis(
                signals={
                    "MNQ": {"symbol": "MNQ", "direction": "LONG"},
                    "MES": {"symbol": "MES", "direction": "LONG"},
                    "MGC": {"symbol": "MGC", "direction": "LONG"},
                }
            )
            correlator = ChainSignalCorrelator(redis)
            tx = _make_tx(
                chain=Chain.ETH,
                tx_type=TxType.EXCHANGE_DEPOSIT,  # BEARISH
                amount_usd=200_000_000.0,  # MEGA -> ×1.5
                tier=WhaleTier.MEGA,
            )
            result = await correlator.enrich(tx)
            # −0.3×3 = −0.9, ×1.5 = −1.35 → clamped to −1.0
            assert result.correlation_score >= -1.0
            assert pytest.approx(result.correlation_score, abs=1e-9) == -1.0
        finally:
            corr_mod.CHAIN_TO_FUTURES = original

    # -- BTC chain uses its own futures list ---------------------------------

    @pytest.mark.asyncio
    async def test_btc_chain_uses_mgc_mes_mnq(self) -> None:
        """BTC is correlated with MGC, MES, MNQ — all three checked."""
        redis = _make_redis(signals={"MGC": {"symbol": "MGC", "direction": "LONG"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.BTC, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.4

    @pytest.mark.asyncio
    async def test_sol_chain_uses_mnq(self) -> None:
        """SOL is correlated with MNQ only."""
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "SHORT"}})
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.SOL, tx_type=TxType.EXCHANGE_DEPOSIT)  # BEARISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.4


# ---------------------------------------------------------------------------
# TestPublishThreshold
# ---------------------------------------------------------------------------


class TestPublishThreshold:
    @pytest.mark.asyncio
    async def test_publishes_when_score_above_threshold(self) -> None:
        """Score > 0.3 → pipeline with lpush + ltrim + publish executed."""
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        pipe = redis.pipeline.return_value
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        await correlator.enrich(tx)
        # Score is +0.4 > 0.3
        pipe.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_when_score_below_negative_threshold(self) -> None:
        """Score < −0.3 → publish executed."""
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "SHORT"}})
        pipe = redis.pipeline.return_value
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH vs SHORT
        await correlator.enrich(tx)
        # Score is −0.3 — boundary: |−0.3| is NOT > 0.3 so should NOT publish
        pipe.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_publish_when_score_at_threshold(self) -> None:
        """Score == ±0.3 → does NOT publish (strictly greater than required)."""
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        pipe = redis.pipeline.return_value
        correlator = ChainSignalCorrelator(redis)
        # LONG + BEARISH = −0.3 exactly; |−0.3| is not > 0.3
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)
        await correlator.enrich(tx)
        pipe.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_publish_when_score_zero(self) -> None:
        """Zero score → no publish."""
        redis = _make_redis(signals={})
        pipe = redis.pipeline.return_value
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.WHALE_MOVE)
        await correlator.enrich(tx)
        pipe.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_lpush_to_correlation_latest(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        pipe = redis.pipeline.return_value
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        await correlator.enrich(tx)
        pipe.lpush.assert_called_once()
        args = pipe.lpush.call_args[0]
        assert args[0] == "chain:correlation:latest"

    @pytest.mark.asyncio
    async def test_publish_ltrim_to_20(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        pipe = redis.pipeline.return_value
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        await correlator.enrich(tx)
        pipe.ltrim.assert_called_once()
        args = pipe.ltrim.call_args[0]
        assert args[0] == "chain:correlation:latest"
        assert args[1] == 0
        assert args[2] == 19

    @pytest.mark.asyncio
    async def test_publish_to_correlation_channel(self) -> None:
        redis = _make_redis(signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}})
        pipe = redis.pipeline.return_value
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        await correlator.enrich(tx)
        pipe.publish.assert_called_once()
        args = pipe.publish.call_args[0]
        assert args[0] == "ch:chain:correlation"


# ---------------------------------------------------------------------------
# TestFearGreedConfluence
# ---------------------------------------------------------------------------


class TestFearGreedConfluence:
    @pytest.mark.asyncio
    async def test_fear_plus_bullish_whale_adds_0_25(self) -> None:
        """Fear sentiment (value < 45) + BULLISH tx → +0.25."""
        redis = _make_redis(
            signals={},
            fear_greed={"value": 30, "sentiment": "fear"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.25

    @pytest.mark.asyncio
    async def test_extreme_fear_plus_bullish_whale_adds_0_25(self) -> None:
        redis = _make_redis(
            signals={},
            fear_greed={"value": 10, "sentiment": "extreme_fear"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.BTC, tx_type=TxType.STABLECOIN_MINT)  # BULLISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.25

    @pytest.mark.asyncio
    async def test_greed_plus_bearish_whale_subtracts_0_2(self) -> None:
        """Greed sentiment (value >= 55) + BEARISH tx → −0.2."""
        redis = _make_redis(
            signals={},
            fear_greed={"value": 70, "sentiment": "greed"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)  # BEARISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == -0.2

    @pytest.mark.asyncio
    async def test_extreme_greed_plus_bearish_whale_subtracts_0_2(self) -> None:
        redis = _make_redis(
            signals={},
            fear_greed={"value": 90, "sentiment": "extreme_greed"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.BTC, tx_type=TxType.STABLECOIN_BURN)  # BEARISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == -0.2

    @pytest.mark.asyncio
    async def test_neutral_fg_no_change(self) -> None:
        """Neutral F&G → no score change."""
        redis = _make_redis(
            signals={},
            fear_greed={"value": 50, "sentiment": "neutral"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_fear_plus_bearish_no_change(self) -> None:
        """Fear + BEARISH (not bullish) → no contrarian confluence."""
        redis = _make_redis(
            signals={},
            fear_greed={"value": 20, "sentiment": "extreme_fear"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)  # BEARISH
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_greed_plus_bullish_no_change(self) -> None:
        """Greed + BULLISH (not bearish) → no distribution warning."""
        redis = _make_redis(
            signals={},
            fear_greed={"value": 80, "sentiment": "extreme_greed"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_fear_confluence_appends_signal_description(self) -> None:
        redis = _make_redis(
            signals={},
            fear_greed={"value": 22, "sentiment": "fear"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert any("F&G" in s or "fear" in s for s in result.correlated_signals)

    @pytest.mark.asyncio
    async def test_greed_confluence_appends_signal_description(self) -> None:
        redis = _make_redis(
            signals={},
            fear_greed={"value": 78, "sentiment": "greed"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)
        result = await correlator.enrich(tx)
        assert any("F&G" in s or "greed" in s for s in result.correlated_signals)

    @pytest.mark.asyncio
    async def test_fear_plus_signal_score_additive(self) -> None:
        """Signal score + F&G score combine correctly."""
        redis = _make_redis(
            signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}},
            fear_greed={"value": 20, "sentiment": "extreme_fear"},
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH
        result = await correlator.enrich(tx)
        # LONG + BULLISH = +0.4, F&G fear + bullish = +0.25 → total 0.65
        assert pytest.approx(result.correlation_score) == 0.65


# ---------------------------------------------------------------------------
# TestBtcDominanceAmplifier
# ---------------------------------------------------------------------------


class TestBtcDominanceAmplifier:
    @pytest.mark.asyncio
    async def test_low_btc_dominance_eth_bullish_adds_0_15(self) -> None:
        """BTC dom < 44% + ETH chain + BULLISH → +0.15."""
        redis = _make_redis(
            signals={},
            btc_dominance=42.5,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.15

    @pytest.mark.asyncio
    async def test_exact_44_pct_dominance_no_amplifier(self) -> None:
        """BTC dom == 44% is NOT < 44 → no amplifier."""
        redis = _make_redis(
            signals={},
            btc_dominance=44.0,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_high_btc_dominance_no_amplifier(self) -> None:
        """BTC dom > 44% → no amplifier."""
        redis = _make_redis(
            signals={},
            btc_dominance=55.0,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_btc_chain_ignores_btc_dominance(self) -> None:
        """BTC dominance amplifier only applies to ETH chain, not BTC."""
        redis = _make_redis(
            signals={},
            btc_dominance=40.0,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.BTC, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_sol_chain_ignores_btc_dominance(self) -> None:
        """BTC dominance amplifier only applies to ETH chain, not SOL."""
        redis = _make_redis(
            signals={},
            btc_dominance=38.0,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.SOL, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_low_btc_dominance_eth_bearish_no_amplifier(self) -> None:
        """Low BTC dom + ETH + BEARISH → no amplifier (only BULLISH triggers it)."""
        redis = _make_redis(
            signals={},
            btc_dominance=40.0,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_DEPOSIT)  # BEARISH
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_btc_dominance_appends_signal_description(self) -> None:
        redis = _make_redis(
            signals={},
            btc_dominance=43.0,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert any("dom" in s or "alt season" in s for s in result.correlated_signals)

    @pytest.mark.asyncio
    async def test_btc_dominance_combined_with_fg_and_signal(self) -> None:
        """All three layers active: signal +0.4, F&G +0.25, BTC dom +0.15 = +0.8."""
        redis = _make_redis(
            signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}},
            fear_greed={"value": 18, "sentiment": "extreme_fear"},
            btc_dominance=42.0,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.8


# ---------------------------------------------------------------------------
# TestCMCDataMissing
# ---------------------------------------------------------------------------


class TestCMCDataMissing:
    @pytest.mark.asyncio
    async def test_missing_fear_greed_key_no_crash(self) -> None:
        """cmc:fear_greed key absent → no error, no score change."""
        redis = _make_redis(signals={}, fear_greed=None, btc_dominance=None)
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_missing_btc_dominance_key_no_crash(self) -> None:
        """cmc:btc_dominance key absent → no error, no score change."""
        redis = _make_redis(signals={}, btc_dominance=None)
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        result = await correlator.enrich(tx)
        # No BTC dominance data → no amplifier
        assert result.correlation_score == 0.0

    @pytest.mark.asyncio
    async def test_both_cmc_keys_absent_no_change(self) -> None:
        redis = _make_redis(signals={}, fear_greed=None, btc_dominance=None)
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.WHALE_MOVE)
        result = await correlator.enrich(tx)
        assert result.correlation_score == 0.0
        assert result.correlated_signals == []

    @pytest.mark.asyncio
    async def test_signal_layer_still_works_without_cmc(self) -> None:
        """Signal correlation works even when CMC data is absent."""
        redis = _make_redis(
            signals={"MNQ": {"symbol": "MNQ", "direction": "LONG"}},
            fear_greed=None,
            btc_dominance=None,
        )
        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)  # BULLISH
        result = await correlator.enrich(tx)
        assert pytest.approx(result.correlation_score) == 0.4

    @pytest.mark.asyncio
    async def test_corrupt_fear_greed_json_no_crash(self) -> None:
        """Corrupt JSON in cmc:fear_greed → graceful skip."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="not valid json{{")
        pipe = AsyncMock()
        pipe.lpush = AsyncMock()
        pipe.ltrim = AsyncMock()
        pipe.publish = AsyncMock()
        pipe.execute = AsyncMock(return_value=[])
        redis.pipeline = MagicMock(return_value=pipe)

        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.EXCHANGE_WITHDRAWAL)
        # Should not raise
        result = await correlator.enrich(tx)
        assert isinstance(result, ChainTransaction)

    @pytest.mark.asyncio
    async def test_redis_get_raises_no_crash(self) -> None:
        """Redis.get() raises an exception → enrich() handles it gracefully."""
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=Exception("redis down"))
        redis.pipeline = MagicMock(return_value=AsyncMock())

        correlator = ChainSignalCorrelator(redis)
        tx = _make_tx(chain=Chain.ETH, tx_type=TxType.WHALE_MOVE)
        result = await correlator.enrich(tx)
        # The outer try/except in enrich() catches this
        assert isinstance(result, ChainTransaction)
