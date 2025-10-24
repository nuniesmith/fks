"""
Asset Registry - Centralized asset management for FKS trading system

This module provides a centralized registry for all tradeable assets organized by:
- Category: Crypto, Forex, Futures
- Type: Spot (personal trading) vs Futures (prop firms)
- Subcategories: For futures - Commodities, Indices, Forex
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class AssetCategory(Enum):
    """Asset category enumeration"""

    CRYPTO = "crypto"
    FOREX = "forex"
    FUTURES = "futures"


class AssetType(Enum):
    """Asset type enumeration for portfolio separation"""

    SPOT = "spot"  # Personal trading / profits
    FUTURES = "futures"  # Prop firms


class FuturesSubcategory(Enum):
    """Futures subcategory enumeration"""

    COMMODITIES = "commodities"
    INDICES = "indices"
    FOREX = "forex"


@dataclass
class Asset:
    """Asset data structure"""

    symbol: str
    name: str
    category: AssetCategory
    asset_type: AssetType
    exchange: str
    subcategory: FuturesSubcategory | None = None
    base_currency: str | None = None
    quote_currency: str | None = None
    tick_size: float | None = None
    lot_size: float | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# Crypto Assets (Spot and Futures)
CRYPTO_SPOT_ASSETS = [
    Asset(
        "BTCUSDT",
        "Bitcoin",
        AssetCategory.CRYPTO,
        AssetType.SPOT,
        "binance",
        base_currency="BTC",
        quote_currency="USDT",
    ),
    Asset(
        "ETHUSDT",
        "Ethereum",
        AssetCategory.CRYPTO,
        AssetType.SPOT,
        "binance",
        base_currency="ETH",
        quote_currency="USDT",
    ),
    Asset(
        "SOLUSDT",
        "Solana",
        AssetCategory.CRYPTO,
        AssetType.SPOT,
        "binance",
        base_currency="SOL",
        quote_currency="USDT",
    ),
    Asset(
        "AVAXUSDT",
        "Avalanche",
        AssetCategory.CRYPTO,
        AssetType.SPOT,
        "binance",
        base_currency="AVAX",
        quote_currency="USDT",
    ),
    Asset(
        "SUIUSDT",
        "Sui",
        AssetCategory.CRYPTO,
        AssetType.SPOT,
        "binance",
        base_currency="SUI",
        quote_currency="USDT",
    ),
    Asset(
        "ADAUSDT",
        "Cardano",
        AssetCategory.CRYPTO,
        AssetType.SPOT,
        "binance",
        base_currency="ADA",
        quote_currency="USDT",
    ),
    Asset(
        "DOTUSDT",
        "Polkadot",
        AssetCategory.CRYPTO,
        AssetType.SPOT,
        "binance",
        base_currency="DOT",
        quote_currency="USDT",
    ),
    Asset(
        "LINKUSDT",
        "Chainlink",
        AssetCategory.CRYPTO,
        AssetType.SPOT,
        "binance",
        base_currency="LINK",
        quote_currency="USDT",
    ),
]

CRYPTO_FUTURES_ASSETS = [
    Asset(
        "BTCUSDT",
        "Bitcoin Futures",
        AssetCategory.CRYPTO,
        AssetType.FUTURES,
        "binance",
        base_currency="BTC",
        quote_currency="USDT",
    ),
    Asset(
        "ETHUSDT",
        "Ethereum Futures",
        AssetCategory.CRYPTO,
        AssetType.FUTURES,
        "binance",
        base_currency="ETH",
        quote_currency="USDT",
    ),
    Asset(
        "SOLUSDT",
        "Solana Futures",
        AssetCategory.CRYPTO,
        AssetType.FUTURES,
        "binance",
        base_currency="SOL",
        quote_currency="USDT",
    ),
    Asset(
        "AVAXUSDT",
        "Avalanche Futures",
        AssetCategory.CRYPTO,
        AssetType.FUTURES,
        "binance",
        base_currency="AVAX",
        quote_currency="USDT",
    ),
    Asset(
        "SUIUSDT",
        "Sui Futures",
        AssetCategory.CRYPTO,
        AssetType.FUTURES,
        "binance",
        base_currency="SUI",
        quote_currency="USDT",
    ),
]

# Forex Assets (Spot and Futures)
FOREX_SPOT_ASSETS = [
    Asset(
        "EURUSD",
        "Euro/US Dollar",
        AssetCategory.FOREX,
        AssetType.SPOT,
        "oanda",
        base_currency="EUR",
        quote_currency="USD",
    ),
    Asset(
        "GBPUSD",
        "British Pound/US Dollar",
        AssetCategory.FOREX,
        AssetType.SPOT,
        "oanda",
        base_currency="GBP",
        quote_currency="USD",
    ),
    Asset(
        "USDJPY",
        "US Dollar/Japanese Yen",
        AssetCategory.FOREX,
        AssetType.SPOT,
        "oanda",
        base_currency="USD",
        quote_currency="JPY",
    ),
    Asset(
        "AUDUSD",
        "Australian Dollar/US Dollar",
        AssetCategory.FOREX,
        AssetType.SPOT,
        "oanda",
        base_currency="AUD",
        quote_currency="USD",
    ),
    Asset(
        "USDCAD",
        "US Dollar/Canadian Dollar",
        AssetCategory.FOREX,
        AssetType.SPOT,
        "oanda",
        base_currency="USD",
        quote_currency="CAD",
    ),
    Asset(
        "USDCHF",
        "US Dollar/Swiss Franc",
        AssetCategory.FOREX,
        AssetType.SPOT,
        "oanda",
        base_currency="USD",
        quote_currency="CHF",
    ),
    Asset(
        "NZDUSD",
        "New Zealand Dollar/US Dollar",
        AssetCategory.FOREX,
        AssetType.SPOT,
        "oanda",
        base_currency="NZD",
        quote_currency="USD",
    ),
]

FOREX_FUTURES_ASSETS = [
    Asset(
        "6E",
        "Euro Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.FOREX,
        base_currency="EUR",
        quote_currency="USD",
    ),
    Asset(
        "6B",
        "British Pound Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.FOREX,
        base_currency="GBP",
        quote_currency="USD",
    ),
    Asset(
        "6J",
        "Japanese Yen Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.FOREX,
        base_currency="JPY",
        quote_currency="USD",
    ),
    Asset(
        "6A",
        "Australian Dollar Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.FOREX,
        base_currency="AUD",
        quote_currency="USD",
    ),
]

# Commodities Futures
COMMODITIES_FUTURES_ASSETS = [
    Asset(
        "GC",
        "Gold Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.COMMODITIES,
    ),
    Asset(
        "SI",
        "Silver Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.COMMODITIES,
    ),
    Asset(
        "CL",
        "Crude Oil Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.COMMODITIES,
    ),
    Asset(
        "NG",
        "Natural Gas Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.COMMODITIES,
    ),
    Asset(
        "ZC",
        "Corn Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.COMMODITIES,
    ),
    Asset(
        "ZS",
        "Soybean Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.COMMODITIES,
    ),
    Asset(
        "ZW",
        "Wheat Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.COMMODITIES,
    ),
]

# Indices Futures
INDICES_FUTURES_ASSETS = [
    Asset(
        "ES",
        "E-mini S&P 500 Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.INDICES,
    ),
    Asset(
        "NQ",
        "E-mini NASDAQ 100 Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.INDICES,
    ),
    Asset(
        "YM",
        "E-mini Dow Jones Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.INDICES,
    ),
    Asset(
        "RTY",
        "E-mini Russell 2000 Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.INDICES,
    ),
    Asset(
        "DAX",
        "DAX Index Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.INDICES,
    ),
    Asset(
        "FTSE",
        "FTSE 100 Index Futures",
        AssetCategory.FUTURES,
        AssetType.FUTURES,
        "oanda",
        subcategory=FuturesSubcategory.INDICES,
    ),
]

# Master Registry organized by category
ASSET_REGISTRY: dict[AssetCategory, dict[AssetType, list[Asset]]] = {
    AssetCategory.CRYPTO: {
        AssetType.SPOT: CRYPTO_SPOT_ASSETS,
        AssetType.FUTURES: CRYPTO_FUTURES_ASSETS,
    },
    AssetCategory.FOREX: {
        AssetType.SPOT: FOREX_SPOT_ASSETS,
        AssetType.FUTURES: [],  # Forex futures are in FUTURES category
    },
    AssetCategory.FUTURES: {
        AssetType.FUTURES: (
            FOREX_FUTURES_ASSETS + COMMODITIES_FUTURES_ASSETS + INDICES_FUTURES_ASSETS
        ),
        AssetType.SPOT: [],  # No spot futures
    },
}

# Convenience dictionaries for quick lookup
ALL_ASSETS: list[Asset] = []
ASSETS_BY_SYMBOL: dict[str, Asset] = {}
ASSETS_BY_EXCHANGE: dict[str, list[Asset]] = {}
SPOT_ASSETS: list[Asset] = []
FUTURES_ASSETS: list[Asset] = []

# Build convenience lookups
for _category, types_dict in ASSET_REGISTRY.items():
    for _asset_type, assets in types_dict.items():
        for asset in assets:
            ALL_ASSETS.append(asset)
            ASSETS_BY_SYMBOL[asset.symbol] = asset

            # Group by exchange
            if asset.exchange not in ASSETS_BY_EXCHANGE:
                ASSETS_BY_EXCHANGE[asset.exchange] = []
            ASSETS_BY_EXCHANGE[asset.exchange].append(asset)

            # Group by type for portfolio separation
            if asset.asset_type == AssetType.SPOT:
                SPOT_ASSETS.append(asset)
            elif asset.asset_type == AssetType.FUTURES:
                FUTURES_ASSETS.append(asset)


def get_asset(symbol: str) -> Asset | None:
    """Get asset by symbol"""
    return ASSETS_BY_SYMBOL.get(symbol)


def get_assets_by_category(category: AssetCategory) -> list[Asset]:
    """Get all assets in a category"""
    assets = []
    for _asset_type, asset_list in ASSET_REGISTRY[category].items():
        assets.extend(asset_list)
    return assets


def get_assets_by_type(asset_type: AssetType) -> list[Asset]:
    """Get all assets of a specific type (spot/futures)"""
    return SPOT_ASSETS if asset_type == AssetType.SPOT else FUTURES_ASSETS


def get_assets_by_exchange(exchange: str) -> list[Asset]:
    """Get all assets for a specific exchange"""
    return ASSETS_BY_EXCHANGE.get(exchange, [])


def get_futures_by_subcategory(subcategory: FuturesSubcategory) -> list[Asset]:
    """Get futures assets by subcategory"""
    return [asset for asset in FUTURES_ASSETS if asset.subcategory == subcategory]


def get_symbol_list(
    category: AssetCategory | None = None, asset_type: AssetType | None = None
) -> list[str]:
    """Get list of symbols with optional filtering"""
    if category and asset_type:
        return [asset.symbol for asset in ASSET_REGISTRY[category][asset_type]]
    elif category:
        return [asset.symbol for asset in get_assets_by_category(category)]
    elif asset_type:
        return [asset.symbol for asset in get_assets_by_type(asset_type)]
    else:
        return [asset.symbol for asset in ALL_ASSETS]


# Legacy compatibility - maintain old SYMBOLS list from config
MAINS = ["BTCUSDT", "ETHUSDT"]  # Main cryptos to hold long term
ALTS = ["SOLUSDT", "AVAXUSDT", "SUIUSDT"]  # Alt coins
SYMBOLS = MAINS + ALTS  # For backward compatibility

__all__ = [
    "Asset",
    "AssetCategory",
    "AssetType",
    "FuturesSubcategory",
    "ASSET_REGISTRY",
    "ALL_ASSETS",
    "ASSETS_BY_SYMBOL",
    "ASSETS_BY_EXCHANGE",
    "SPOT_ASSETS",
    "FUTURES_ASSETS",
    "get_asset",
    "get_assets_by_category",
    "get_assets_by_type",
    "get_assets_by_exchange",
    "get_futures_by_subcategory",
    "get_symbol_list",
    "MAINS",
    "ALTS",
    "SYMBOLS",  # Legacy compatibility
]
