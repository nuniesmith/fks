"""Data models for the asset registry and provider system.

This module defines the core types that everything else in the data factory
is built around: asset classes, data-provider names, interval definitions,
window targets, news configuration, and per-asset configuration.  A
pre-populated ``ASSET_CATALOG`` list and a convenience ``CATALOG_BY_SYMBOL``
dictionary are exported for downstream consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from core.logging_config import get_logger

if TYPE_CHECKING:
    from datetime import datetime

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AssetClass(StrEnum):
    """Broad classification of a tradeable asset."""

    FUTURES_CME = "futures_cme"
    CRYPTO = "crypto"
    FOREX = "forex"
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    COMMODITY = "commodity"


class ProviderName(StrEnum):
    """Canonical names for market-data providers."""

    MASSIVE = "massive"
    YFINANCE = "yfinance"
    KRAKEN = "kraken"
    BINANCE = "binance"
    TRADINGVIEW = "tradingview"
    RITHMIC = "rithmic"
    FINNHUB = "finnhub"
    SCRAPER = "scraper"


class DataInterval(StrEnum):
    """Supported OHLCV bar intervals."""

    ONE_MIN = "1m"
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class WindowTarget:
    """Defines how much history to keep for a given bar interval.

    Attributes:
        interval:  The bar interval this target applies to.
        days:      Target rolling-window size in calendar days.
        min_days:  Minimum days before an alert is raised.
    """

    interval: DataInterval
    days: int
    min_days: int


@dataclass
class NewsConfig:
    """Per-asset news / sentiment configuration."""

    enabled: bool = True
    primary_keywords: list[str] = field(default_factory=list)
    secondary_keywords: list[str] = field(default_factory=list)
    subreddits: list[str] = field(default_factory=list)
    min_sentiment_threshold: float = -1.0
    history_days: int = 365


@dataclass
class AssetConfig:
    """Complete configuration for a single tradeable asset.

    Every asset tracked by the data factory is represented by one of these
    records.  The ``ASSET_CATALOG`` list below is the canonical source for
    all pre-configured assets.
    """

    symbol: str
    name: str
    asset_class: AssetClass
    exchange: str
    enabled: bool = False

    providers: list[ProviderName] = field(default_factory=list)
    window_targets: list[WindowTarget] = field(default_factory=list)
    news: NewsConfig = field(default_factory=NewsConfig)
    correlated: list[str] = field(default_factory=list)
    provider_symbol_map: dict[str, str] = field(default_factory=dict)

    point_value: float | None = None
    tick_size: float | None = None
    currency: str = "USD"

    created_at: datetime | None = None
    updated_at: datetime | None = None

    # -- helpers -------------------------------------------------------------

    def provider_symbol(self, provider: ProviderName) -> str:
        """Return the provider-specific symbol, falling back to *self.symbol*."""
        return self.provider_symbol_map.get(provider.value, self.symbol)

    def target_for(self, interval: DataInterval) -> WindowTarget | None:
        """Return the first :class:`WindowTarget` matching *interval*, or ``None``."""
        for wt in self.window_targets:
            if wt.interval is interval:
                return wt
        return None


# ---------------------------------------------------------------------------
# ASSET_CATALOG — pre-configured assets (all disabled by default)
# ---------------------------------------------------------------------------

_CME_PROVIDERS: list[ProviderName] = [
    ProviderName.MASSIVE,
    ProviderName.RITHMIC,
    ProviderName.YFINANCE,
]

_CME_WINDOWS: list[WindowTarget] = [
    WindowTarget(interval=DataInterval.ONE_MIN, days=90, min_days=30),
    WindowTarget(interval=DataInterval.FIVE_MIN, days=180, min_days=60),
    WindowTarget(interval=DataInterval.ONE_DAY, days=1825, min_days=365),
]

_CRYPTO_PROVIDERS: list[ProviderName] = [
    ProviderName.KRAKEN,
    ProviderName.BINANCE,
    ProviderName.TRADINGVIEW,
]

_CRYPTO_WINDOWS: list[WindowTarget] = [
    WindowTarget(interval=DataInterval.ONE_MIN, days=30, min_days=7),
    WindowTarget(interval=DataInterval.FIVE_MIN, days=90, min_days=30),
    # 15m added for crypto-4h ORB session training (step_size=15, window=240 bars).
    # Provides intermediate granularity between 5m scalping and 1h trend data.
    WindowTarget(interval=DataInterval.FIFTEEN_MIN, days=180, min_days=60),
    WindowTarget(interval=DataInterval.ONE_HOUR, days=365, min_days=90),
    WindowTarget(interval=DataInterval.ONE_DAY, days=1825, min_days=365),
]

_ETF_PROVIDERS: list[ProviderName] = [
    ProviderName.TRADINGVIEW,
    ProviderName.YFINANCE,
]

ASSET_CATALOG: list[AssetConfig] = [
    # ------------------------------------------------------------------
    # CME Micro Futures
    # ------------------------------------------------------------------
    AssetConfig(
        symbol="MGC",
        name="Micro Gold",
        asset_class=AssetClass.FUTURES_CME,
        exchange="CME",
        providers=list(_CME_PROVIDERS),
        window_targets=list(_CME_WINDOWS),
        provider_symbol_map={
            "yfinance": "GC=F",
            "tradingview": "COMEX:MGC1!",
        },
        point_value=10.0,
        tick_size=0.10,
        correlated=["SIL", "GLD", "DXY"],
        news=NewsConfig(
            primary_keywords=["MGC", "micro gold", "gold futures", "COMEX gold"],
            secondary_keywords=[
                "gold",
                "XAU",
                "precious metals",
                "inflation",
                "FOMC",
                "Fed rates",
                "dollar weakness",
                "safe haven",
            ],
            subreddits=["Gold", "investing", "Economics", "wallstreetbets"],
            history_days=730,
        ),
    ),
    AssetConfig(
        symbol="MES",
        name="Micro E-mini S&P 500",
        asset_class=AssetClass.FUTURES_CME,
        exchange="CME",
        providers=list(_CME_PROVIDERS),
        window_targets=list(_CME_WINDOWS),
        provider_symbol_map={
            "yfinance": "ES=F",
            "tradingview": "CME:MES1!",
        },
        point_value=5.0,
        tick_size=0.25,
        correlated=["MNQ", "M2K", "MYM", "SPY"],
        news=NewsConfig(
            primary_keywords=["MES", "micro S&P", "E-mini S&P", "ES futures"],
            secondary_keywords=[
                "S&P 500",
                "SPX",
                "equities",
                "stocks",
                "Fed",
                "earnings",
                "GDP",
                "recession",
                "bull market",
            ],
            subreddits=[
                "stocks",
                "investing",
                "stockmarket",
                "wallstreetbets",
                "SecurityAnalysis",
            ],
            history_days=1825,
        ),
    ),
    AssetConfig(
        symbol="MNQ",
        name="Micro E-mini Nasdaq",
        asset_class=AssetClass.FUTURES_CME,
        exchange="CME",
        providers=list(_CME_PROVIDERS),
        window_targets=list(_CME_WINDOWS),
        provider_symbol_map={
            "yfinance": "NQ=F",
            "tradingview": "CME:MNQ1!",
        },
        point_value=2.0,
        tick_size=0.25,
        correlated=["MES", "M2K", "QQQ"],
        news=NewsConfig(
            primary_keywords=["MNQ", "micro Nasdaq", "E-mini Nasdaq", "NQ futures"],
            secondary_keywords=[
                "Nasdaq",
                "tech stocks",
                "technology",
                "QQQ",
                "FAANG",
                "semiconductor",
                "growth stocks",
                "Fed",
                "earnings",
            ],
            subreddits=[
                "stocks",
                "investing",
                "stockmarket",
                "wallstreetbets",
                "technology",
            ],
            history_days=1825,
        ),
    ),
    AssetConfig(
        symbol="M2K",
        name="Micro E-mini Russell 2000",
        asset_class=AssetClass.FUTURES_CME,
        exchange="CME",
        providers=list(_CME_PROVIDERS),
        window_targets=list(_CME_WINDOWS),
        provider_symbol_map={
            "yfinance": "RTY=F",
            "tradingview": "CME:M2K1!",
        },
        point_value=5.0,
        tick_size=0.10,
        correlated=["MES", "IWM"],
        news=NewsConfig(
            primary_keywords=[
                "M2K",
                "micro Russell",
                "Russell 2000",
                "small cap futures",
            ],
            secondary_keywords=[
                "small cap",
                "Russell 2000",
                "IWM",
                "regional banks",
                "domestic economy",
                "risk on",
                "risk off",
                "Fed",
            ],
            subreddits=[
                "stocks",
                "investing",
                "smallcapstocks",
                "wallstreetbets",
            ],
            history_days=1825,
        ),
    ),
    AssetConfig(
        symbol="MYM",
        name="Micro E-mini Dow",
        asset_class=AssetClass.FUTURES_CME,
        exchange="CME",
        providers=list(_CME_PROVIDERS),
        window_targets=list(_CME_WINDOWS),
        provider_symbol_map={
            "yfinance": "YM=F",
            "tradingview": "CME:MYM1!",
        },
        point_value=0.50,
        tick_size=1.0,
        correlated=["MES", "DIA"],
        news=NewsConfig(
            primary_keywords=[
                "MYM",
                "micro Dow",
                "E-mini Dow",
                "YM futures",
            ],
            secondary_keywords=[
                "Dow Jones",
                "DJIA",
                "industrials",
                "blue chip",
                "DIA",
                "Fed",
                "earnings",
                "manufacturing",
            ],
            subreddits=[
                "stocks",
                "investing",
                "stockmarket",
                "wallstreetbets",
            ],
            history_days=1825,
        ),
    ),
    AssetConfig(
        symbol="SIL",
        name="Micro Silver",
        asset_class=AssetClass.FUTURES_CME,
        exchange="CME",
        providers=list(_CME_PROVIDERS),
        window_targets=list(_CME_WINDOWS),
        provider_symbol_map={
            "yfinance": "SI=F",
            "tradingview": "COMEX:SIL1!",
        },
        point_value=1000.0,
        tick_size=0.005,
        correlated=["MGC", "SLV"],
        news=NewsConfig(
            primary_keywords=[
                "SIL",
                "micro silver",
                "silver futures",
                "COMEX silver",
            ],
            secondary_keywords=[
                "silver",
                "XAG",
                "precious metals",
                "industrial metals",
                "inflation",
                "FOMC",
                "solar",
                "green energy",
            ],
            subreddits=[
                "Silverbugs",
                "Gold",
                "investing",
                "wallstreetbets",
            ],
            history_days=730,
        ),
    ),
    # ------------------------------------------------------------------
    # Crypto
    # ------------------------------------------------------------------
    AssetConfig(
        symbol="BTC/USD",
        name="Bitcoin",
        asset_class=AssetClass.CRYPTO,
        exchange="Kraken",
        providers=list(_CRYPTO_PROVIDERS),
        window_targets=list(_CRYPTO_WINDOWS),
        provider_symbol_map={
            "kraken": "XXBTZUSD",
            "binance": "BTCUSDT",
            "yfinance": "BTC-USD",
            "tradingview": "KRAKEN:BTCUSD",
        },
        correlated=["ETH/USD", "SOL/USD"],
        news=NewsConfig(
            primary_keywords=[
                "BTC",
                "Bitcoin",
                "BTCUSD",
                "XBT",
            ],
            secondary_keywords=[
                "crypto",
                "cryptocurrency",
                "blockchain",
                "halving",
                "mining",
                "digital gold",
                "Satoshi",
                "Lightning Network",
                "SEC crypto",
                "ETF Bitcoin",
            ],
            subreddits=[
                "Bitcoin",
                "CryptoCurrency",
                "BitcoinMarkets",
                "CryptoMarkets",
            ],
            history_days=1825,
        ),
    ),
    AssetConfig(
        symbol="ETH/USD",
        name="Ethereum",
        asset_class=AssetClass.CRYPTO,
        exchange="Kraken",
        providers=list(_CRYPTO_PROVIDERS),
        window_targets=list(_CRYPTO_WINDOWS),
        provider_symbol_map={
            "kraken": "XETHZUSD",
            "binance": "ETHUSDT",
            "yfinance": "ETH-USD",
            "tradingview": "KRAKEN:ETHUSD",
        },
        correlated=["BTC/USD"],
        news=NewsConfig(
            primary_keywords=[
                "ETH",
                "Ethereum",
                "ETHUSD",
                "Ether",
            ],
            secondary_keywords=[
                "crypto",
                "cryptocurrency",
                "DeFi",
                "smart contracts",
                "staking",
                "Layer 2",
                "gas fees",
                "Vitalik",
                "EIP",
                "merge",
            ],
            subreddits=[
                "ethereum",
                "CryptoCurrency",
                "ethfinance",
                "CryptoMarkets",
            ],
            history_days=1825,
        ),
    ),
    AssetConfig(
        symbol="SOL/USD",
        name="Solana",
        asset_class=AssetClass.CRYPTO,
        exchange="Kraken",
        providers=list(_CRYPTO_PROVIDERS),
        window_targets=list(_CRYPTO_WINDOWS),
        provider_symbol_map={
            # Kraken public REST pair name (no X/Z prefix — newer listing).
            # Verify with: GET https://api.kraken.com/0/public/AssetPairs?pair=SOLUSD
            "kraken": "SOLUSD",
            "binance": "SOLUSDT",
            "yfinance": "SOL-USD",
            "tradingview": "KRAKEN:SOLUSD",
        },
        correlated=["BTC/USD", "ETH/USD"],
        news=NewsConfig(
            primary_keywords=[
                "SOL",
                "Solana",
                "SOLUSD",
            ],
            secondary_keywords=[
                "crypto",
                "cryptocurrency",
                "DeFi",
                "NFT",
                "blockchain",
                "validator",
                "Phantom wallet",
                "Anatoly Yakovenko",
                "Firedancer",
                "Solana ETF",
            ],
            subreddits=[
                "solana",
                "CryptoCurrency",
                "CryptoMarkets",
                "ethfinance",
            ],
            history_days=1825,
        ),
    ),
    # ------------------------------------------------------------------
    # ETFs (correlation context)
    # ------------------------------------------------------------------
    AssetConfig(
        symbol="SPY",
        name="SPDR S&P 500 ETF",
        asset_class=AssetClass.ETF,
        exchange="NYSE",
        providers=list(_ETF_PROVIDERS),
        window_targets=[
            WindowTarget(interval=DataInterval.FIVE_MIN, days=90, min_days=60),
            WindowTarget(interval=DataInterval.ONE_DAY, days=1825, min_days=365),
        ],
        provider_symbol_map={
            "yfinance": "SPY",
            "tradingview": "AMEX:SPY",
        },
        correlated=["MES", "QQQ"],
        news=NewsConfig(enabled=False),
    ),
    AssetConfig(
        symbol="GLD",
        name="SPDR Gold Shares",
        asset_class=AssetClass.ETF,
        exchange="NYSE",
        providers=list(_ETF_PROVIDERS),
        window_targets=[
            WindowTarget(interval=DataInterval.ONE_DAY, days=1825, min_days=365),
        ],
        provider_symbol_map={
            "yfinance": "GLD",
            "tradingview": "AMEX:GLD",
        },
        correlated=["MGC", "SIL"],
        news=NewsConfig(enabled=False),
    ),
]


# ---------------------------------------------------------------------------
# Convenience lookup
# ---------------------------------------------------------------------------

CATALOG_BY_SYMBOL: dict[str, AssetConfig] = {a.symbol: a for a in ASSET_CATALOG}
