"""
portfolio_rebalancer.py — Integration shim for the Kraken Spot Portfolio Rebalancer
=====================================================================================

Re-exports the canonical ``PortfolioConfig``, ``PortfolioRebalancer``, and
``DEFAULT_ALLOCATIONS`` from the engine module so that route files and other
integration consumers can import from a stable ``lib.integrations`` path without
coupling directly to the internal engine layout.

Usage::

    from integrations.portfolio_rebalancer import (
        PortfolioConfig,
        PortfolioRebalancer,
        DEFAULT_ALLOCATIONS,
    )
"""

from services.engine.crypto_portfolio import (
    DEFAULT_ALLOCATIONS,
    PORTFOLIO_ASSET_TO_REST,
    STABLECOIN_ASSETS,
    DepositMonitor,
    PortfolioConfig,
    PortfolioRebalancer,
    get_deposit_monitor,
)

__all__ = [
    "PortfolioConfig",
    "PortfolioRebalancer",
    "DEFAULT_ALLOCATIONS",
    "PORTFOLIO_ASSET_TO_REST",
    "STABLECOIN_ASSETS",
    "DepositMonitor",
    "get_deposit_monitor",
]
