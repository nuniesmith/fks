"""
lib.trading — Trading engine, strategies, and cost models.

Re-exports the public API from each sub-module so callers can do:

    from trading import get_engine, DashboardEngine, STRATEGY_CLASSES
"""

from trading.engine import (
    DashboardEngine,
    get_engine,
    run_backtest,
    run_optimization,
)

__all__ = [
    # engine
    "DashboardEngine",
    "get_engine",
    "run_backtest",
    "run_optimization",
]
