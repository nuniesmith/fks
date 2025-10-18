# src/core/database/__init__.py
"""
Core database module.

Provides database models, session management, and utility functions
for interacting with TimescaleDB.
"""

from .models import (
                     Account,
                     BalanceHistory,
                     Base,
                     Document,
                     DocumentChunk,
                     IndicatorsCache,
                     OHLCVData,
                     Position,
                     QueryHistory,
                     Session,
                     StrategyParameters,
                     SyncStatus,
                     Trade,
                     TradingInsight,
                     engine,
                     init_db,
)
from .utils import (  # OHLCV functions; Account functions; Balance functions; Trade functions; Strategy functions; Position functions; Sync status functions
                     bulk_insert_ohlcv,
                     close_position,
                     create_account,
                     get_account_by_id,
                     get_accounts,
                     get_active_strategy_parameters,
                     get_balance_history,
                     get_latest_ohlcv_time,
                     get_ohlcv_count,
                     get_ohlcv_data,
                     get_oldest_ohlcv_time,
                     get_positions,
                     get_sync_status,
                     get_trades,
                     record_balance_snapshot,
                     record_trade,
                     save_strategy_parameters,
                     update_position,
                     update_sync_status,
)

__all__ = [
    # Models
    "Base",
    "engine",
    "Session",
    "Account",
    "OHLCVData",
    "Position",
    "Trade",
    "BalanceHistory",
    "SyncStatus",
    "IndicatorsCache",
    "StrategyParameters",
    "Document",
    "DocumentChunk",
    "QueryHistory",
    "TradingInsight",
    "init_db",
    # Utils
    "bulk_insert_ohlcv",
    "get_ohlcv_data",
    "get_latest_ohlcv_time",
    "get_oldest_ohlcv_time",
    "get_ohlcv_count",
    "update_sync_status",
    "get_sync_status",
    "create_account",
    "get_accounts",
    "get_account_by_id",
    "update_position",
    "get_positions",
    "close_position",
    "record_trade",
    "get_trades",
    "record_balance_snapshot",
    "get_balance_history",
    "save_strategy_parameters",
    "get_active_strategy_parameters",
]
