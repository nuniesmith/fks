"""
services/asset_registry.py  —  SHIM (post-merge cleanup)
==========================================================
After the futures→ruby merge there are 3 separate asset registries.
This file now acts as a thin shim that:

  1. Re-exports `ContractSpec` and `ASSET_REGISTRY` for backwards compatibility
     (so existing imports in workers/asset_worker.py and web/app.py keep working)
  2. Delegates all real data to `core.asset_registry` — the canonical source

Migration path:
  Phase 1 (now):  this shim — zero breakage, just redirects imports
  Phase 2 (MOD-A): add KuCoin futures fields to core.asset_registry.Asset dataclass
  Phase 3 (MOD-A): delete this file, update all imports to use core directly

────────────────────────────────────────────────────────────────────────────

UNTIL core.asset_registry has ContractSpec fields, we keep the dataclass here
and bridge it so core.asset_registry.py can also read from it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractSpec:
    """Specification for a perpetual futures contract on KuCoin.

    TODO (AREG-A): Fold these fields into core.asset_registry.Asset as a
    `futures_spec: FuturesSpec | None` sub-dataclass. Then this class can
    be deleted and workers import from core directly.
    """

    symbol: str          # Exchange symbol e.g. "XBTUSDTM"
    base: str            # Human-readable base e.g. "BTC"
    max_leverage: int    # Exchange maximum leverage
    category: str        # "crypto" | "metals" | "commodities" | "stocks" | "meme"
    tick_size: float     # Price tick size
    multiplier: float    # Contract multiplier (how many USD per lot)
    description: str     # Short description
    base_symbol: str = "" # CCXT unified symbol e.g. "BTC/USDT:USDT"


# ═══════════════════════════════════════════════════════════════════
# KuCoin Futures Contract Registry
# ═══════════════════════════════════════════════════════════════════
# These are the futures-specific entries.  When AREG-A is done, each
# of these will instead be entries in core.asset_registry.ASSET_REGISTRY
# with exchange="kucoin_futures" and a futures_spec sub-object.

ASSET_REGISTRY: dict[str, ContractSpec] = {
    # ─── Blue Chip Crypto ────────────────────────────────────────
    "btc":  ContractSpec("XBTUSDTM",  "BTC",  125, "crypto",      0.1,      0.001, "Bitcoin",     "BTC/USDT:USDT"),
    "eth":  ContractSpec("ETHUSDTM",  "ETH",  100, "crypto",      0.01,     0.01,  "Ethereum",    "ETH/USDT:USDT"),
    "sol":  ContractSpec("SOLUSDTM",  "SOL",  75,  "crypto",      0.001,    0.1,   "Solana",      "SOL/USDT:USDT"),
    "xrp":  ContractSpec("XRPUSDTM",  "XRP",  75,  "crypto",      0.00001,  10.0,  "XRP",         "XRP/USDT:USDT"),
    "bnb":  ContractSpec("BNBUSDTM",  "BNB",  75,  "crypto",      0.01,     0.01,  "BNB",         "BNB/USDT:USDT"),
    "doge": ContractSpec("DOGEUSDTM", "DOGE", 75,  "crypto",      0.00001,  100.0, "Dogecoin",    "DOGE/USDT:USDT"),
    "avax": ContractSpec("AVAXUSDTM", "AVAX", 75,  "crypto",      0.01,     0.1,   "Avalanche",   "AVAX/USDT:USDT"),
    "sui":  ContractSpec("SUIUSDTM",  "SUI",  75,  "crypto",      0.0001,   1.0,   "Sui",         "SUI/USDT:USDT"),
    "link": ContractSpec("LINKUSDTM", "LINK", 75,  "crypto",      0.001,    0.1,   "Chainlink",   "LINK/USDT:USDT"),
    "ltc":  ContractSpec("LTCUSDTM",  "LTC",  75,  "crypto",      0.01,     0.1,   "Litecoin",    "LTC/USDT:USDT"),
    "dot":  ContractSpec("DOTUSDTM",  "DOT",  75,  "crypto",      0.001,    1.0,   "Polkadot",    "DOT/USDT:USDT"),
    "near": ContractSpec("NEARUSDTM", "NEAR", 75,  "crypto",      0.001,    0.1,   "Near",        "NEAR/USDT:USDT"),
    "hbar": ContractSpec("HBARUSDTM", "HBAR", 75,  "crypto",      0.00001,  10.0,  "Hedera",      "HBAR/USDT:USDT"),
    # ─── Metals / Commodities ────────────────────────────────────
    "gold": ContractSpec("XAUUSDTM",  "GOLD", 20,  "metals",      0.1,      0.01,  "Gold",        ""),
    "slvr": ContractSpec("XAGUSDTM",  "SLVR", 20,  "metals",      0.001,    0.1,   "Silver",      ""),
    # ─── Indices ─────────────────────────────────────────────────
    "spx":  ContractSpec("SPXUSDTM",  "SPX",  20,  "stocks",      0.1,      0.001, "S&P 500",     ""),
    "ndx":  ContractSpec("NDXUSDTM",  "NDX",  20,  "stocks",      0.1,      0.001, "NASDAQ 100",  ""),
}


def get_spec(key: str) -> ContractSpec | None:
    """Retrieve contract spec by asset key. Returns None if not found."""
    return ASSET_REGISTRY.get(key.lower())
