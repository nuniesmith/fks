# src/core/database/__init__.py
"""
Core database module.

Provides database models, session management, and utility functions
for interacting with TimescaleDB.
"""

from .models import (
    Base,
    engine,
    Session,
    Account,
    OHLCVData,
    Position,
    Trade,
    BalanceHistory,
    SyncStatus,
    IndicatorsCache,
    StrategyParameters,
    Document,
    DocumentChunk,
    QueryHistory,
    TradingInsight,
    init_db,
)

from .utils import (
    # OHLCV functions
    bulk_insert_ohlcv,
    get_ohlcv_data,
    get_latest_ohlcv_time,
    get_oldest_ohlcv_time,
    get_ohlcv_count,
    # Sync status functions
    update_sync_status,
    get_sync_status,
    # Account functions
    create_account,
    get_accounts,
    get_account_by_id,
    # Position functions
    update_position,
    get_positions,
    close_position,
    # Trade functions
    record_trade,
    get_trades,
    # Balance functions
    record_balance_snapshot,
    get_balance_history,
    # Strategy functions
    save_strategy_parameters,
    get_active_strategy_parameters,
)

__all__ = [
    # Models
    'Base',
    'engine',
    'Session',
    'Account',
    'OHLCVData',
    'Position',
    'Trade',
    'BalanceHistory',
    'SyncStatus',
    'IndicatorsCache',
    'StrategyParameters',
    'Document',
    'DocumentChunk',
    'QueryHistory',
    'TradingInsight',
    'init_db',
    # Utils
    'bulk_insert_ohlcv',
    'get_ohlcv_data',
    'get_latest_ohlcv_time',
    'get_oldest_ohlcv_time',
    'get_ohlcv_count',
    'update_sync_status',
    'get_sync_status',
    'create_account',
    'get_accounts',
    'get_account_by_id',
    'update_position',
    'get_positions',
    'close_position',
    'record_trade',
    'get_trades',
    'record_balance_snapshot',
    'get_balance_history',
    'save_strategy_parameters',
    'get_active_strategy_parameters',
]
