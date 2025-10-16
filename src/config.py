# src/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# Constants
MAINS = ['BTCUSDT', 'ETHUSDT']  # Main fkss to hold long term
ALTS = ['SOLUSDT', 'AVAXUSDT', 'SUIUSDT']  # Alt coins
SYMBOLS = MAINS + ALTS

# Timeframes to track
TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M']

# Binance API timeframe mapping
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

# Historical data settings
HISTORICAL_DAYS = 730  # 2 years of data
MAX_CANDLES_PER_REQUEST = 1000  # Binance API limit

# Trading settings
FEE_RATE = 0.001  # 0.1% transaction fee
RISK_PER_TRADE = 0.01  # 1% risk per trade

# External services
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# Database config
DB_USER = os.getenv('DB_USER', 'user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'fks_db')
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Redis config
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# WebSocket config
WS_RECONNECT_DELAY = 5  # seconds
WS_PING_INTERVAL = 20  # seconds
WS_PING_TIMEOUT = 10  # seconds