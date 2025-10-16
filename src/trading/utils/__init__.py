"""
Trading utilities package.
Migrated from Streamlit app to Django.
"""

from .data_fetcher import (
    get_historical_data,
    get_current_price,
    get_live_prices,
    get_price_stats,
    is_live_data_available,
    get_websocket_status
)

from .signal_generator import get_current_signal

from .backtest_engine import run_backtest

from .optimizer import run_optimization, objective

from .helpers import (
    log_trade_to_db,
    send_discord_notification,
    format_trade_suggestions_for_discord,
    format_backtest_results_for_discord,
    format_price_data,
    calculate_percentage_change,
    get_discord_webhook_url,
    validate_trade_data,
    create_signal_record
)

__all__ = [
    # Data fetching
    'get_historical_data',
    'get_current_price',
    'get_live_prices',
    'get_price_stats',
    'is_live_data_available',
    'get_websocket_status',
    # Signal generation
    'get_current_signal',
    # Backtesting
    'run_backtest',
    # Optimization
    'run_optimization',
    'objective',
    # Helpers
    'log_trade_to_db',
    'send_discord_notification',
    'format_trade_suggestions_for_discord',
    'format_backtest_results_for_discord',
    'format_price_data',
    'calculate_percentage_change',
    'get_discord_webhook_url',
    'validate_trade_data',
    'create_signal_record',
]
