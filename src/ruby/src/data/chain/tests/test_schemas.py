"""
Tests for data_factory.chain.schemas

Covers:
  - WhaleTier enum values and string representation
  - classify_tier() boundary conditions
  - classify_sentiment() heuristic mapping
  - ChainTransaction dataclass defaults
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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
# TestWhaleTier
# ---------------------------------------------------------------------------


class TestWhaleTier:
    def test_enum_values(self) -> None:
        assert WhaleTier.MEGA.value == "mega"
        assert WhaleTier.LARGE.value == "large"
        assert WhaleTier.MEDIUM.value == "medium"
        assert WhaleTier.SMALL.value == "small"

    def test_string_representation(self) -> None:
        # WhaleTier is a str-enum; the .value always gives the raw string.
        # Python 3.11+ StrEnum str() may return "WhaleTier.MEGA" vs "mega"
        # depending on the exact mixin order, so we test .value directly.
        assert WhaleTier.MEGA.value == "mega"
        assert WhaleTier.LARGE.value == "large"
        assert WhaleTier.MEDIUM.value == "medium"
        assert WhaleTier.SMALL.value == "small"
        # The enum compares equal to its string value via __eq__
        assert WhaleTier.MEGA == "mega"

    def test_membership(self) -> None:
        members = list(WhaleTier)
        assert WhaleTier.MEGA in members
        assert WhaleTier.LARGE in members
        assert WhaleTier.MEDIUM in members
        assert WhaleTier.SMALL in members
        assert len(members) == 4

    def test_str_equality(self) -> None:
        # As a str enum the value should compare equal to its raw string
        assert WhaleTier.MEGA == "mega"
        assert WhaleTier.LARGE == "large"


# ---------------------------------------------------------------------------
# TestClassifyTier
# ---------------------------------------------------------------------------


class TestClassifyTier:
    # --- MEGA ($100M+) ------------------------------------------------------

    def test_exactly_100m_is_mega(self) -> None:
        assert classify_tier(100_000_000) == WhaleTier.MEGA

    def test_above_100m_is_mega(self) -> None:
        assert classify_tier(500_000_000) == WhaleTier.MEGA

    def test_one_billion_is_mega(self) -> None:
        assert classify_tier(1_000_000_000) == WhaleTier.MEGA

    # --- LARGE ($10M–$100M) ------------------------------------------------

    def test_exactly_10m_is_large(self) -> None:
        assert classify_tier(10_000_000) == WhaleTier.LARGE

    def test_50m_is_large(self) -> None:
        assert classify_tier(50_000_000) == WhaleTier.LARGE

    def test_just_below_100m_is_large(self) -> None:
        assert classify_tier(99_999_999) == WhaleTier.LARGE

    # --- MEDIUM ($1M–$10M) -------------------------------------------------

    def test_exactly_1m_is_medium(self) -> None:
        assert classify_tier(1_000_000) == WhaleTier.MEDIUM

    def test_5m_is_medium(self) -> None:
        assert classify_tier(5_000_000) == WhaleTier.MEDIUM

    def test_just_below_10m_is_medium(self) -> None:
        assert classify_tier(9_999_999) == WhaleTier.MEDIUM

    # --- SMALL (<$1M) ------------------------------------------------------

    def test_100k_is_small(self) -> None:
        assert classify_tier(100_000) == WhaleTier.SMALL

    def test_500k_is_small(self) -> None:
        assert classify_tier(500_000) == WhaleTier.SMALL

    def test_just_below_1m_is_small(self) -> None:
        assert classify_tier(999_999) == WhaleTier.SMALL

    def test_zero_is_small(self) -> None:
        assert classify_tier(0) == WhaleTier.SMALL

    def test_one_dollar_is_small(self) -> None:
        assert classify_tier(1) == WhaleTier.SMALL

    # --- Boundary precision ------------------------------------------------

    def test_boundary_10m_not_mega(self) -> None:
        assert classify_tier(10_000_000) != WhaleTier.MEGA

    def test_boundary_1m_not_large(self) -> None:
        assert classify_tier(1_000_000) != WhaleTier.LARGE


# ---------------------------------------------------------------------------
# TestClassifySentiment
# ---------------------------------------------------------------------------


class TestClassifySentiment:
    # --- Bearish -----------------------------------------------------------

    def test_exchange_deposit_is_bearish(self) -> None:
        assert classify_sentiment(TxType.EXCHANGE_DEPOSIT) == Sentiment.BEARISH

    def test_stablecoin_burn_is_bearish(self) -> None:
        assert classify_sentiment(TxType.STABLECOIN_BURN) == Sentiment.BEARISH

    # --- Bullish -----------------------------------------------------------

    def test_exchange_withdrawal_is_bullish(self) -> None:
        assert classify_sentiment(TxType.EXCHANGE_WITHDRAWAL) == Sentiment.BULLISH

    def test_stablecoin_mint_is_bullish(self) -> None:
        assert classify_sentiment(TxType.STABLECOIN_MINT) == Sentiment.BULLISH

    # --- Neutral -----------------------------------------------------------

    def test_whale_move_is_neutral(self) -> None:
        assert classify_sentiment(TxType.WHALE_MOVE) == Sentiment.NEUTRAL

    def test_bridge_is_neutral(self) -> None:
        assert classify_sentiment(TxType.BRIDGE) == Sentiment.NEUTRAL

    def test_unknown_is_neutral(self) -> None:
        assert classify_sentiment(TxType.UNKNOWN) == Sentiment.NEUTRAL

    def test_unstake_is_neutral(self) -> None:
        assert classify_sentiment(TxType.UNSTAKE) == Sentiment.NEUTRAL

    def test_wallet_watched_is_neutral(self) -> None:
        assert classify_sentiment(TxType.WALLET_WATCHED) == Sentiment.NEUTRAL

    # --- Sentiment enum values ---------------------------------------------

    def test_sentiment_values(self) -> None:
        assert Sentiment.BULLISH.value == "bullish"
        assert Sentiment.BEARISH.value == "bearish"
        assert Sentiment.NEUTRAL.value == "neutral"


# ---------------------------------------------------------------------------
# TestChainTransaction
# ---------------------------------------------------------------------------


def _make_tx(**overrides) -> ChainTransaction:
    """Helper — create a minimal valid ChainTransaction."""
    defaults = dict(
        chain=Chain.ETH,
        tx_hash="0xdeadbeef",
        tx_type=TxType.WHALE_MOVE,
        amount_native=100.0,
        amount_usd=314_800.0,
        from_address="0xabc",
        to_address="0xdef",
        from_label=None,
        to_label=None,
        token="ETH",
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        block_height=19_000_000,
        tier=WhaleTier.SMALL,
        sentiment=Sentiment.NEUTRAL,
        source="test",
    )
    defaults.update(overrides)
    return ChainTransaction(**defaults)


class TestChainTransaction:
    def test_basic_instantiation(self) -> None:
        tx = _make_tx()
        assert tx.chain == Chain.ETH
        assert tx.tx_hash == "0xdeadbeef"
        assert tx.token == "ETH"
        assert tx.source == "test"

    def test_default_correlation_score_is_zero(self) -> None:
        tx = _make_tx()
        assert tx.correlation_score == 0.0

    def test_default_correlated_signals_is_empty_list(self) -> None:
        tx = _make_tx()
        assert tx.correlated_signals == []

    def test_correlated_signals_are_independent_per_instance(self) -> None:
        """Mutable default must not be shared between instances."""
        tx1 = _make_tx()
        tx2 = _make_tx()
        tx1.correlated_signals.append("signal_a")
        assert tx2.correlated_signals == []

    def test_default_id_is_none(self) -> None:
        tx = _make_tx()
        assert tx.id is None

    def test_default_raw_is_empty_dict(self) -> None:
        tx = _make_tx()
        assert tx.raw == {}

    def test_raw_dicts_are_independent_per_instance(self) -> None:
        tx1 = _make_tx()
        tx2 = _make_tx()
        tx1.raw["key"] = "value"
        assert tx2.raw == {}

    def test_explicit_correlation_score(self) -> None:
        tx = _make_tx()
        tx.correlation_score = 0.75
        assert tx.correlation_score == 0.75

    def test_explicit_correlated_signals(self) -> None:
        tx = _make_tx()
        tx.correlated_signals.append("LONG MES + bullish")
        assert len(tx.correlated_signals) == 1
        assert "LONG MES + bullish" in tx.correlated_signals

    def test_block_height_none(self) -> None:
        tx = _make_tx(block_height=None)
        assert tx.block_height is None

    def test_from_label_none(self) -> None:
        tx = _make_tx(from_label=None)
        assert tx.from_label is None

    def test_to_label_set(self) -> None:
        tx = _make_tx(to_label="Binance")
        assert tx.to_label == "Binance"

    def test_chains(self) -> None:
        for chain in Chain:
            tx = _make_tx(chain=chain)
            assert tx.chain == chain

    def test_tier_and_sentiment_roundtrip(self) -> None:
        tx = _make_tx(tier=WhaleTier.MEGA, sentiment=Sentiment.BEARISH)
        assert tx.tier == WhaleTier.MEGA
        assert tx.sentiment == Sentiment.BEARISH

    def test_amount_usd_float(self) -> None:
        tx = _make_tx(amount_usd=1_234_567.89)
        assert pytest.approx(tx.amount_usd) == 1_234_567.89

    def test_timestamp_preserved(self) -> None:
        ts = datetime(2025, 6, 15, 8, 30, 0, tzinfo=UTC)
        tx = _make_tx(timestamp=ts)
        assert tx.timestamp == ts
