"""
Core constants for FKS trading system.

Centralized location for all system-wide constants.
"""

# Time intervals
INTERVALS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
    "1w": 604800,
}

# Trading constants
DEFAULT_LOOKBACK_PERIODS = 100
DEFAULT_RISK_PERCENTAGE = 0.02  # 2% risk per trade
MAX_POSITION_SIZE = 0.1  # 10% of portfolio max per position
MIN_CONFIDENCE_THRESHOLD = 0.6  # 60% minimum confidence for signals

# API rate limits
DEFAULT_RATE_LIMIT = 10  # requests per second
BINANCE_RATE_LIMIT = 20
POLYGON_RATE_LIMIT = 5
OANDA_RATE_LIMIT = 10

# Cache settings
DEFAULT_CACHE_TTL = 300  # 5 minutes
MARKET_DATA_CACHE_TTL = 60  # 1 minute
CONFIG_CACHE_TTL = 3600  # 1 hour

# Database settings
DEFAULT_BATCH_SIZE = 1000
MAX_QUERY_SIZE = 10000

# Backtesting defaults
DEFAULT_INITIAL_CAPITAL = 10000
DEFAULT_COMMISSION = 0.001  # 0.1%
DEFAULT_SLIPPAGE = 0.0005  # 0.05%

# Signal thresholds
STRONG_BUY_THRESHOLD = 0.8
BUY_THRESHOLD = 0.6
NEUTRAL_THRESHOLD = 0.4
SELL_THRESHOLD = 0.2
STRONG_SELL_THRESHOLD = 0.0

# Indicator parameters
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

BB_PERIOD = 20
BB_STD = 2

ATR_PERIOD = 14

# ML model defaults
DEFAULT_TRAIN_TEST_SPLIT = 0.8
DEFAULT_RANDOM_STATE = 42
DEFAULT_N_ESTIMATORS = 100
DEFAULT_MAX_DEPTH = 10

# Logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# File paths (relative to project root)
DATA_DIR = "data"
LOGS_DIR = "logs"
MODELS_DIR = "models"
REPORTS_DIR = "reports"

# Environment variables
ENV_PREFIX = "FKS_"

# Status codes
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

__all__ = [
    "INTERVALS",
    "DEFAULT_LOOKBACK_PERIODS",
    "DEFAULT_RISK_PERCENTAGE",
    "MAX_POSITION_SIZE",
    "MIN_CONFIDENCE_THRESHOLD",
    "DEFAULT_RATE_LIMIT",
    "BINANCE_RATE_LIMIT",
    "POLYGON_RATE_LIMIT",
    "OANDA_RATE_LIMIT",
    "DEFAULT_CACHE_TTL",
    "MARKET_DATA_CACHE_TTL",
    "CONFIG_CACHE_TTL",
    "DEFAULT_BATCH_SIZE",
    "MAX_QUERY_SIZE",
    "DEFAULT_INITIAL_CAPITAL",
    "DEFAULT_COMMISSION",
    "DEFAULT_SLIPPAGE",
    "STRONG_BUY_THRESHOLD",
    "BUY_THRESHOLD",
    "NEUTRAL_THRESHOLD",
    "SELL_THRESHOLD",
    "STRONG_SELL_THRESHOLD",
    "RSI_PERIOD",
    "RSI_OVERBOUGHT",
    "RSI_OVERSOLD",
    "MACD_FAST",
    "MACD_SLOW",
    "MACD_SIGNAL",
    "BB_PERIOD",
    "BB_STD",
    "ATR_PERIOD",
    "DEFAULT_TRAIN_TEST_SPLIT",
    "DEFAULT_RANDOM_STATE",
    "DEFAULT_N_ESTIMATORS",
    "DEFAULT_MAX_DEPTH",
    "LOG_FORMAT",
    "LOG_DATE_FORMAT",
    "DATA_DIR",
    "LOGS_DIR",
    "MODELS_DIR",
    "REPORTS_DIR",
    "ENV_PREFIX",
    "STATUS_SUCCESS",
    "STATUS_ERROR",
    "STATUS_PENDING",
    "STATUS_RUNNING",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
]
