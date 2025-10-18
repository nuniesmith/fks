# src/config.py
"""
Legacy config module - Re-exports from framework.config.constants for backward compatibility.

MIGRATION NOTE: This module is deprecated. Import directly from framework.config.constants instead:
    from framework.config.constants import SYMBOLS, MAINS, ALTS, FEE_RATE, etc.
"""

import os
from dotenv import load_dotenv

# Import core trading constants from framework
from framework.config.constants import (
    SYMBOLS,
    MAINS, 
    ALTS,
    FEE_RATE,
    RISK_PER_TRADE,
    DATABASE_URL,
    TIMEFRAMES,
)

load_dotenv()

# Binance API timeframe mapping (legacy compatibility)
BINANCE_INTERVALS = {
    '1m': '1m',
    '5m': '5m',
    '15m': '15m',
    '30m': '30m',
    '1h': '1h',
    '4h': '4h',
    '1d': '1d',
    '1w': '1w',
    '1M': '1M'
}

# Historical data settings (legacy compatibility)
HISTORICAL_DAYS = 730  # 2 years of data
MAX_CANDLES_PER_REQUEST = 1000  # Binance API limit

# External services
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# OpenAI API for RAG
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Database config (legacy - use DATABASE_URL from framework.config.constants instead)
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'trading_db')

# Redis config
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# WebSocket config
WS_RECONNECT_DELAY = 5  # seconds
WS_PING_INTERVAL = 20  # seconds
WS_PING_TIMEOUT = 10  # seconds

# Asset Management
# Import asset registry for centralized asset management
try:
    from core.registry import (
        SPOT_ASSETS, FUTURES_ASSETS, 
        get_assets_by_category, get_assets_by_type,
        AssetCategory, AssetType
    )
    ASSET_REGISTRY_AVAILABLE = True
except ImportError:
    ASSET_REGISTRY_AVAILABLE = False
    SPOT_ASSETS = []
    FUTURES_ASSETS = []

# Oanda API Configuration
OANDA_API_TOKEN = os.getenv('OANDA_API_TOKEN', '')
OANDA_ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID', '')
OANDA_ENVIRONMENT = os.getenv('OANDA_ENVIRONMENT', 'practice')  # 'practice' or 'live'

# Asset type preferences for different trading strategies
PERSONAL_TRADING_ASSET_TYPE = 'spot'  # Spot for personal profits
PROP_FIRM_ASSET_TYPE = 'futures'  # Futures for prop firms

# Portfolio allocation settings
PORTFOLIO_SPOT_ALLOCATION = 0.5  # 50% to spot assets (personal)
PORTFOLIO_FUTURES_ALLOCATION = 0.5  # 50% to futures assets (prop firms)
