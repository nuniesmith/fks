"""
On-chain data models.

ChainTransaction is the canonical record for every whale move,
exchange flow, and stablecoin event. Everything normalises to this
before hitting Postgres.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class Chain(StrEnum):
    BTC = "BTC"
    ETH = "ETH"
    SOL = "SOL"


class TxType(StrEnum):
    WHALE_MOVE = "whale_move"
    EXCHANGE_DEPOSIT = "exchange_deposit"
    EXCHANGE_WITHDRAWAL = "exchange_withdrawal"
    STABLECOIN_MINT = "stablecoin_mint"
    STABLECOIN_BURN = "stablecoin_burn"
    BRIDGE = "bridge"
    UNSTAKE = "unstake"
    WALLET_WATCHED = "wallet_watched"
    UNKNOWN = "unknown"


class Sentiment(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class WhaleTier(StrEnum):
    MEGA = "mega"  # $100M+
    LARGE = "large"  # $10M-$100M
    MEDIUM = "medium"  # $1M-$10M
    SMALL = "small"  # $100K-$1M


def classify_tier(usd_value: float) -> WhaleTier:
    if usd_value >= 100_000_000:
        return WhaleTier.MEGA
    if usd_value >= 10_000_000:
        return WhaleTier.LARGE
    if usd_value >= 1_000_000:
        return WhaleTier.MEDIUM
    return WhaleTier.SMALL


def classify_sentiment(tx_type: TxType) -> Sentiment:
    """Heuristic sentiment from transaction type."""
    bearish = {TxType.EXCHANGE_DEPOSIT, TxType.STABLECOIN_BURN}
    bullish = {TxType.EXCHANGE_WITHDRAWAL, TxType.STABLECOIN_MINT}
    if tx_type in bearish:
        return Sentiment.BEARISH
    if tx_type in bullish:
        return Sentiment.BULLISH
    return Sentiment.NEUTRAL


@dataclass
class ChainTransaction:
    chain: Chain
    tx_hash: str
    tx_type: TxType
    amount_native: float  # in native units (BTC, ETH, SOL)
    amount_usd: float
    from_address: str
    to_address: str
    from_label: str | None  # "Binance", "MicroStrategy", etc.
    to_label: str | None
    token: str  # "BTC", "ETH", "USDT", etc.
    timestamp: datetime
    block_height: int | None
    tier: WhaleTier  # computed
    sentiment: Sentiment  # computed
    source: str  # "whale_alert", "etherscan", etc.
    raw: dict = field(default_factory=dict)

    # Added after storage
    id: int | None = None
    # Correlation fields - filled by ChainSignalCorrelator
    correlated_signals: list[str] = field(default_factory=list)
    correlation_score: float = 0.0


@dataclass
class WalletWatch:
    """A wallet the user is actively monitoring."""

    address: str
    chain: Chain
    label: str  # human name e.g. "MicroStrategy"
    alert_on_any: bool = True  # alert on any movement
    min_usd: float = 0.0  # minimum USD value to alert on
    enabled: bool = True


@dataclass
class ExchangeFlow:
    """Aggregated 24h exchange flow for a chain."""

    chain: Chain
    exchange: str
    inflow_native: float
    outflow_native: float
    inflow_usd: float
    outflow_usd: float
    net_native: float  # positive = net outflow (bullish)
    sentiment: Sentiment
    period_hours: int = 24
    as_of: datetime | None = None


@dataclass
class MempoolSnapshot:
    """Bitcoin mempool state."""

    pending_txns: int
    size_mb: float
    fee_next_block: float  # sat/vB
    fee_30min: float
    fee_1hour: float
    fee_economy: float
    as_of: datetime | None = None


@dataclass
class OnChainMetrics:
    """Key on-chain health metrics per chain."""

    chain: Chain
    active_addresses: int | None
    exchange_supply_pct: float | None  # % of supply on exchanges
    sopr: float | None  # Spent Output Profit Ratio (BTC)
    nvt_signal: float | None
    mvrv_z: float | None
    hash_rate_eh: float | None  # BTC only
    gas_price_gwei: float | None  # ETH only
    tps: float | None  # SOL only
    as_of: datetime | None = None
