"""
Contract specifications, account profiles, and derived lookups.

This module owns all contract-related constants and the runtime
``set_contract_mode()`` toggle.  Everything that was previously in
``models.py`` related to tickers, watchlists, point values, and
tick sizes now lives here.
"""

import os
from typing import Any

# ---------------------------------------------------------------------------
# Contract mode: "micro" (default) or "full"
# Set via environment variable CONTRACT_MODE or toggle at runtime.
# ---------------------------------------------------------------------------
CONTRACT_MODE = os.getenv("CONTRACT_MODE", "micro").lower()

# ---------------------------------------------------------------------------
# Account profiles – 50k is 1/3 of 150k, 100k is 2/3
# ---------------------------------------------------------------------------
ACCOUNT_PROFILES: dict[str, dict[str, Any]] = {
    "50k": {
        "size": 50_000,
        "risk_pct": 0.01,
        "risk_dollars": 500,
        "max_contracts": 2,
        "max_contracts_micro": 10,
        "soft_stop": -500,
        "hard_stop": -750,
        "eod_dd": 1_500,
        "label": "$50k TakeProfit Trader",
        "playbook_note": (
            "TPT PLAYBOOK: Max 1-2 full / 10 micro contracts on $50k (25% rule). Daily Loss Removed: $1,500."
        ),
    },
    "100k": {
        "size": 100_000,
        "risk_pct": 0.01,
        "risk_dollars": 1_000,
        "max_contracts": 3,
        "max_contracts_micro": 20,
        "soft_stop": -1_000,
        "hard_stop": -1_500,
        "eod_dd": 3_000,
        "label": "$100k TakeProfit Trader",
        "playbook_note": (
            "TPT PLAYBOOK: Max 2-3 full / 20 micro contracts on $100k (25% rule). Daily Loss Removed: $3,000."
        ),
    },
    "150k": {
        "size": 150_000,
        "risk_pct": 0.01,
        "risk_dollars": 1_500,
        "max_contracts": 4,
        "max_contracts_micro": 30,
        "soft_stop": -1_500,
        "hard_stop": -2_250,
        "eod_dd": 4_500,
        "label": "$150k TakeProfit Trader",
        "playbook_note": (
            "TPT PLAYBOOK: Max 3-4 full / 30 micro contracts on $150k (25% rule). Daily Loss Removed: $4,500."
        ),
    },
}

# ---------------------------------------------------------------------------
# Contract specifications — Full-size CME contracts
# ---------------------------------------------------------------------------
FULL_CONTRACT_SPECS: dict[str, dict[str, Any]] = {
    "Gold": {"ticker": "GC=F", "point": 100, "tick": 0.10, "margin": 11_000},
    "Silver": {"ticker": "SI=F", "point": 5_000, "tick": 0.005, "margin": 9_000},
    "Copper": {"ticker": "HG=F", "point": 25_000, "tick": 0.0005, "margin": 6_000},
    "Crude Oil": {"ticker": "CL=F", "point": 1_000, "tick": 0.01, "margin": 7_000},
    "Natural Gas": {"ticker": "NG=F", "point": 10_000, "tick": 0.001, "margin": 3_500},
    "S&P": {"ticker": "ES=F", "point": 50, "tick": 0.25, "margin": 12_000},
    "Nasdaq": {"ticker": "NQ=F", "point": 20, "tick": 0.25, "margin": 17_000},
    "Russell 2000": {"ticker": "RTY=F", "point": 50, "tick": 0.10, "margin": 8_000},
    "Dow Jones": {"ticker": "YM=F", "point": 5, "tick": 1.0, "margin": 9_000},
    # FX futures (full-size CME)
    "Euro FX": {"ticker": "6E=F", "point": 125_000, "tick": 0.00005, "margin": 2_800},
    "British Pound": {"ticker": "6B=F", "point": 62_500, "tick": 0.0001, "margin": 2_600},
    "Japanese Yen": {"ticker": "6J=F", "point": 12_500_000, "tick": 0.0000005, "margin": 2_400},
    "Australian Dollar": {"ticker": "6A=F", "point": 100_000, "tick": 0.0001, "margin": 1_800},
    "Canadian Dollar": {"ticker": "6C=F", "point": 100_000, "tick": 0.0001, "margin": 1_600},
    "Swiss Franc": {"ticker": "6S=F", "point": 125_000, "tick": 0.0001, "margin": 3_000},
    # Interest rate futures (CBOT)
    "10Y T-Note": {"ticker": "ZN=F", "point": 1_000, "tick": 0.015625, "margin": 1_800},
    # Crypto (full-size CME)
    "Bitcoin": {"ticker": "BTC=F", "point": 5, "tick": 5.0, "margin": 80_000},
    "Ether": {"ticker": "ETH=F", "point": 50, "tick": 0.25, "margin": 6_500},
}

# ---------------------------------------------------------------------------
# Contract specifications — Micro CME contracts
# Micro contracts are 1/10 of full size (except Silver 1/5, FX 1/10).
# These give more granularity for position sizing and scaling.
# ---------------------------------------------------------------------------
MICRO_CONTRACT_SPECS: dict[str, dict[str, Any]] = {
    # ── Metals ──────────────────────────────────────────────────────────────
    "Gold": {
        "ticker": "MGC=F",
        "data_ticker": "MGC=F",
        "point": 10,
        "tick": 0.10,
        "margin": 1_100,
    },
    "Silver": {
        "ticker": "SIL=F",
        "data_ticker": "SI=F",
        "point": 1_000,
        "tick": 0.005,
        "margin": 1_800,
    },
    "Copper": {
        "ticker": "MHG=F",
        "data_ticker": "HG=F",
        "point": 2_500,
        "tick": 0.0005,
        "margin": 600,
    },
    # ── Energy ──────────────────────────────────────────────────────────────
    "Crude Oil": {
        "ticker": "MCL=F",
        "data_ticker": "CL=F",
        "point": 100,
        "tick": 0.01,
        "margin": 700,
    },
    "Natural Gas": {
        # CME Micro Natural Gas (MNG) — 1/10 of the standard NG contract
        "ticker": "MNG=F",
        "data_ticker": "NG=F",
        "point": 1_000,
        "tick": 0.001,
        "margin": 350,
    },
    # ── Equity index ────────────────────────────────────────────────────────
    "S&P": {
        "ticker": "MES=F",
        "data_ticker": "ES=F",
        "point": 5,
        "tick": 0.25,
        "margin": 1_500,
    },
    "Nasdaq": {
        "ticker": "MNQ=F",
        "data_ticker": "NQ=F",
        "point": 2,
        "tick": 0.25,
        "margin": 2_100,
    },
    "Russell 2000": {
        "ticker": "M2K=F",
        "data_ticker": "RTY=F",
        "point": 5,
        "tick": 0.10,
        "margin": 1_200,
    },
    "Dow Jones": {
        "ticker": "MYM=F",
        "data_ticker": "YM=F",
        "point": 0.5,
        "tick": 1.0,
        "margin": 1_100,
    },
    # ── FX futures ──────────────────────────────────────────────────────────
    # M6E / M6B are genuine CME Micro FX contracts (1/10 of standard size).
    # The remaining pairs use the standard contract size alongside micros for
    # session-based ORB scanning.
    "Euro FX": {
        "ticker": "M6E=F",
        "data_ticker": "6E=F",
        "point": 12_500,
        "tick": 0.0001,
        "margin": 280,
    },
    "British Pound": {
        "ticker": "M6B=F",
        "data_ticker": "6B=F",
        "point": 6_250,
        "tick": 0.0001,
        "margin": 260,
    },
    "Japanese Yen": {
        "ticker": "6J=F",
        "data_ticker": "6J=F",
        "point": 12_500_000,
        "tick": 0.0000005,
        "margin": 2_400,
    },
    "Australian Dollar": {
        "ticker": "6A=F",
        "data_ticker": "6A=F",
        "point": 100_000,
        "tick": 0.0001,
        "margin": 1_800,
    },
    "Canadian Dollar": {
        "ticker": "6C=F",
        "data_ticker": "6C=F",
        "point": 100_000,
        "tick": 0.0001,
        "margin": 1_600,
    },
    "Swiss Franc": {
        "ticker": "6S=F",
        "data_ticker": "6S=F",
        "point": 125_000,
        "tick": 0.0001,
        "margin": 3_000,
    },
    # ── Interest rate futures (CBOT) ─────────────────────────────────────────
    # No standard CME micro exists for ZN/ZB; we use full-size contracts
    # here since margins are already relatively small and they're important
    # for macro regime context.
    "10Y T-Note": {
        "ticker": "ZN=F",
        "data_ticker": "ZN=F",
        "point": 1_000,
        "tick": 0.015625,
        "margin": 1_800,
    },
    "30Y T-Bond": {
        "ticker": "ZB=F",
        "data_ticker": "ZB=F",
        "point": 1_000,
        "tick": 0.03125,
        "margin": 3_200,
    },
    "Corn": {
        "ticker": "ZC=F",
        "data_ticker": "ZC=F",
        "point": 50,
        "tick": 0.25,
        "margin": 1_200,
    },
    "Soybeans": {
        "ticker": "ZS=F",
        "data_ticker": "ZS=F",
        "point": 50,
        "tick": 0.25,
        "margin": 2_200,
    },
    "Wheat": {
        "ticker": "ZW=F",
        "data_ticker": "ZW=F",
        "point": 50,
        "tick": 0.25,
        "margin": 1_700,
    },
    # ── Crypto ──────────────────────────────────────────────────────────────
    "Micro Bitcoin": {
        "ticker": "MBT=F",
        "data_ticker": "MBT=F",
        "point": 0.1,
        "tick": 5.0,
        "margin": 8_000,
    },
    "Micro Ether": {
        "ticker": "MET=F",
        "data_ticker": "MET=F",
        "point": 0.1,
        "tick": 0.25,
        "margin": 700,
    },
}

# ---------------------------------------------------------------------------
# Kraken Crypto Contract Specifications
# ---------------------------------------------------------------------------
# Spot crypto pairs sourced from Kraken exchange via REST + WebSocket.
# These use a KRAKEN: prefix internally so the cache layer and engine can
# distinguish them from CME futures tickers.
#
# "point" = value of a $1 move per 1 unit (spot crypto = 1.0).
# "tick"  = minimum price increment on Kraken.
# "margin"= notional margin to risk-size 1 unit (informal, for dashboard display).
#
# Enable/disable Kraken crypto in the pipeline via ENABLE_KRAKEN_CRYPTO env var.
# ---------------------------------------------------------------------------
ENABLE_KRAKEN_CRYPTO = os.getenv("ENABLE_KRAKEN_CRYPTO", "1").strip().lower() in ("1", "true", "yes")

KRAKEN_CONTRACT_SPECS: dict[str, dict[str, Any]] = {
    "BTC/USD": {
        "ticker": "KRAKEN:XBTUSD",
        "data_ticker": "KRAKEN:XBTUSD",
        "point": 1.0,
        "tick": 0.1,
        "margin": 5_000,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
    "ETH/USD": {
        "ticker": "KRAKEN:ETHUSD",
        "data_ticker": "KRAKEN:ETHUSD",
        "point": 1.0,
        "tick": 0.01,
        "margin": 500,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
    "SOL/USD": {
        "ticker": "KRAKEN:SOLUSD",
        "data_ticker": "KRAKEN:SOLUSD",
        "point": 1.0,
        "tick": 0.001,
        "margin": 50,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
    "LINK/USD": {
        "ticker": "KRAKEN:LINKUSD",
        "data_ticker": "KRAKEN:LINKUSD",
        "point": 1.0,
        "tick": 0.001,
        "margin": 25,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
    "AVAX/USD": {
        "ticker": "KRAKEN:AVAXUSD",
        "data_ticker": "KRAKEN:AVAXUSD",
        "point": 1.0,
        "tick": 0.001,
        "margin": 30,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
    "DOT/USD": {
        "ticker": "KRAKEN:DOTUSD",
        "data_ticker": "KRAKEN:DOTUSD",
        "point": 1.0,
        "tick": 0.0001,
        "margin": 15,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
    "ADA/USD": {
        "ticker": "KRAKEN:ADAUSD",
        "data_ticker": "KRAKEN:ADAUSD",
        "point": 1.0,
        "tick": 0.00001,
        "margin": 10,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
    "POL/USD": {
        "ticker": "KRAKEN:POLUSD",
        "data_ticker": "KRAKEN:POLUSD",
        "point": 1.0,
        "tick": 0.0001,
        "margin": 10,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
    "XRP/USD": {
        "ticker": "KRAKEN:XRPUSD",
        "data_ticker": "KRAKEN:XRPUSD",
        "point": 1.0,
        "tick": 0.0001,
        "margin": 10,
        "exchange": "kraken",
        "asset_class": "crypto",
    },
}

# ---------------------------------------------------------------------------
# Active contract specs — selected by CONTRACT_MODE env var
# ---------------------------------------------------------------------------
CONTRACT_SPECS = MICRO_CONTRACT_SPECS if CONTRACT_MODE == "micro" else FULL_CONTRACT_SPECS

# Convenience: name → data ticker (for data fetching).
# When data_ticker differs from ticker, data is fetched using data_ticker.
# Gold uses MGC=F directly to avoid front-month mismatch between GC and MGC.
ASSETS: dict[str, str] = {name: str(spec.get("data_ticker", spec["ticker"])) for name, spec in CONTRACT_SPECS.items()}

# Merge in Kraken crypto pairs when enabled
if ENABLE_KRAKEN_CRYPTO:
    ASSETS.update({name: str(spec["data_ticker"]) for name, spec in KRAKEN_CONTRACT_SPECS.items()})

# Reverse lookup: data ticker → name
TICKER_TO_NAME: dict[str, str] = {
    str(spec.get("data_ticker", spec["ticker"])): name for name, spec in CONTRACT_SPECS.items()
}
if ENABLE_KRAKEN_CRYPTO:
    TICKER_TO_NAME.update({str(spec["data_ticker"]): name for name, spec in KRAKEN_CONTRACT_SPECS.items()})

# ---------------------------------------------------------------------------
# Flat ticker sets — useful for quick membership checks
# ---------------------------------------------------------------------------
# All micro-contract tickers (for filtering signals to tradeable instruments)
MICRO_TICKERS: frozenset[str] = frozenset(
    str(spec.get("data_ticker", spec["ticker"])) for spec in MICRO_CONTRACT_SPECS.values()
)

# FX futures tickers subset (data tickers)
FX_TICKERS: frozenset[str] = frozenset({"6E=F", "6B=F", "6J=F", "6A=F", "6C=F", "6S=F"})

# Interest rate futures tickers subset
RATES_TICKERS: frozenset[str] = frozenset({"ZN=F", "ZB=F"})

# Kraken crypto tickers subset (data tickers)
CRYPTO_TICKERS: frozenset[str] = frozenset(str(spec["data_ticker"]) for spec in KRAKEN_CONTRACT_SPECS.values())

# Overnight-session relevant tickers (traded when US equity markets are closed)
OVERNIGHT_TICKERS: frozenset[str] = frozenset(
    {
        # Metals
        "MGC=F",
        "SIL=F",
        "MHG=F",
        # Energy
        "CL=F",
        "NG=F",
        # FX
        "6E=F",
        "6B=F",
        "6J=F",
        "6A=F",
        "6C=F",
        "6S=F",
        # CME Crypto futures
        "MBT=F",
        "MET=F",
        # Kraken spot crypto (24/7 markets — always "overnight")
        *(str(spec["data_ticker"]) for spec in KRAKEN_CONTRACT_SPECS.values()),
    }
)

# ---------------------------------------------------------------------------
# Watchlists — curated asset tiers for strategy & scanning
# ---------------------------------------------------------------------------
# CORE_WATCHLIST: 5 assets actively traded with 1-lot micro stop-and-reverse.
#   Selected for: tight spreads, deep liquidity, clean breakout patterns,
#   sufficient ATR for meaningful R-multiples, low margin requirement.
#   Total margin for 5 positions ≈ $5,680 (11.4% of $50K account).
CORE_WATCHLIST: dict[str, str] = {
    "Gold": "MGC=F",  # Best breakout patterns, 23h trading, $10/pt, $1,100 margin
    "Crude Oil": "MCL=F",  # Clean ORB setups, strong session opens, $100/pt, $700 margin
    "S&P": "MES=F",  # Highest liquidity micro, trends cleanly intraday, $5/pt, $1,500 margin
    "Nasdaq": "MNQ=F",  # Highest ATR index micro, big moves = big R, $2/pt, $2,100 margin
    "Euro FX": "M6E=F",  # Best FX micro for breakouts, London open textbook ORB, $280 margin
}

# EXTENDED_WATCHLIST: 5 additional assets for signal scanning & CNN predictions.
#   Not actively traded with stop-and-reverse unless core assets aren't setting up.
#   Still generate breakout signals, CNN inferences, and dashboard alerts.
EXTENDED_WATCHLIST: dict[str, str] = {
    "Silver": "SIL=F",  # Correlated with Gold; trade when MGC is choppy but SIL trends
    "Russell 2000": "M2K=F",  # Small-cap divergence plays; trade when MES/MNQ are range-bound
    "British Pound": "M6B=F",  # Trade during London session when 6E is flat
    "Micro Bitcoin": "MBT=F",  # 24/7 market; weekend breakout setups when futures are closed
    "10Y T-Note": "ZN=F",  # Macro context + flight-to-safety; trade on FOMC/CPI days
}

# ACTIVE_WATCHLIST: Union of core + extended — all assets the engine should
# actively monitor for breakout signals, CNN inference, and dashboard display.
ACTIVE_WATCHLIST: dict[str, str] = {**CORE_WATCHLIST, **EXTENDED_WATCHLIST}

# CORE_TICKERS / EXTENDED_TICKERS / ACTIVE_TICKERS: frozenset variants for
# quick membership checks (keyed by data_ticker, e.g. "MGC=F").
CORE_TICKERS: frozenset[str] = frozenset(CORE_WATCHLIST.values())
EXTENDED_TICKERS: frozenset[str] = frozenset(EXTENDED_WATCHLIST.values())
ACTIVE_TICKERS: frozenset[str] = frozenset(ACTIVE_WATCHLIST.values())

# Point values for quick P&L calculation (per contract, per full point move)
# Keyed by data_ticker so callers can look up by the ticker they actually trade.
POINT_VALUE: dict[str, float] = {
    str(spec.get("data_ticker", spec["ticker"])): float(spec["point"]) for spec in MICRO_CONTRACT_SPECS.values()
}
# Add Kraken crypto point values
if ENABLE_KRAKEN_CRYPTO:
    POINT_VALUE.update({str(spec["data_ticker"]): float(spec["point"]) for spec in KRAKEN_CONTRACT_SPECS.values()})

# Tick sizes keyed by data_ticker
TICK_SIZE: dict[str, float] = {
    str(spec.get("data_ticker", spec["ticker"])): float(spec["tick"]) for spec in MICRO_CONTRACT_SPECS.values()
}
# Add Kraken crypto tick sizes
if ENABLE_KRAKEN_CRYPTO:
    TICK_SIZE.update({str(spec["data_ticker"]): float(spec["tick"]) for spec in KRAKEN_CONTRACT_SPECS.values()})


def set_contract_mode(mode: str) -> dict:
    """Switch between 'micro' and 'full' contract specs at runtime.

    Updates the module-level CONTRACT_SPECS, ASSETS, and TICKER_TO_NAME dicts
    in place so all importers see the change.

    Returns the newly active CONTRACT_SPECS.
    """
    global CONTRACT_MODE
    mode = mode.lower()
    if mode not in ("micro", "full"):
        raise ValueError(f"Invalid contract mode '{mode}'. Use 'micro' or 'full'.")

    CONTRACT_MODE = mode
    source = MICRO_CONTRACT_SPECS if mode == "micro" else FULL_CONTRACT_SPECS

    CONTRACT_SPECS.clear()
    CONTRACT_SPECS.update(source)

    ASSETS.clear()
    ASSETS.update({name: str(spec.get("data_ticker", spec["ticker"])) for name, spec in CONTRACT_SPECS.items()})

    TICKER_TO_NAME.clear()
    TICKER_TO_NAME.update({str(spec.get("data_ticker", spec["ticker"])): name for name, spec in CONTRACT_SPECS.items()})

    return CONTRACT_SPECS


# ---------------------------------------------------------------------------
# __all__ — public API for wildcard imports
# ---------------------------------------------------------------------------
__all__ = [
    "CONTRACT_MODE",
    "ACCOUNT_PROFILES",
    "FULL_CONTRACT_SPECS",
    "MICRO_CONTRACT_SPECS",
    "ENABLE_KRAKEN_CRYPTO",
    "KRAKEN_CONTRACT_SPECS",
    "CONTRACT_SPECS",
    "ASSETS",
    "TICKER_TO_NAME",
    "MICRO_TICKERS",
    "FX_TICKERS",
    "RATES_TICKERS",
    "CRYPTO_TICKERS",
    "OVERNIGHT_TICKERS",
    "CORE_WATCHLIST",
    "EXTENDED_WATCHLIST",
    "ACTIVE_WATCHLIST",
    "CORE_TICKERS",
    "EXTENDED_TICKERS",
    "ACTIVE_TICKERS",
    "POINT_VALUE",
    "TICK_SIZE",
    "set_contract_mode",
]
