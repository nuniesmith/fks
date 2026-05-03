"""
Futures Perpetual Contract Registry
====================================
Hardcoded registry of available USDTM perpetual contracts.

This serves as the source of truth for:
- Symbol mapping (human name -> exchange symbol)
- CCXT unified symbol mapping for exchange-agnostic lookups
- Max leverage per contract
- Market category (crypto, metals, commodities, stocks, etc.)
- Contract specifications

Workers look up contract details from this registry.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractSpec:
    """Specification for a perpetual contract."""

    symbol: str  # Exchange symbol e.g. "XBTUSDTM" (default for KuCoin)
    base: str  # Human-readable base e.g. "BTC"
    max_leverage: int  # Exchange maximum leverage
    category: str  # "crypto" | "metals" | "commodities" | "stocks" | "meme"
    tick_size: float  # Price tick size
    multiplier: float  # Contract multiplier
    description: str  # Short description
    base_symbol: str = ""  # Generic base pair e.g. "BTC/USDT:USDT" for CCXT unified lookup


# ═══════════════════════════════════════════════════════════════════
# Complete Asset Registry
# ═══════════════════════════════════════════════════════════════════
# Organized by category. All confirmed active perpetual contracts.
# Key = short name used in config and Redis

ASSET_REGISTRY: dict[str, ContractSpec] = {
    # ─── Blue Chip Crypto ────────────────────────────────────────
    "btc": ContractSpec(
        "XBTUSDTM", "BTC", 125, "crypto", 0.1, 0.001, "Bitcoin", base_symbol="BTC/USDT:USDT"
    ),
    "eth": ContractSpec(
        "ETHUSDTM", "ETH", 100, "crypto", 0.01, 0.01, "Ethereum", base_symbol="ETH/USDT:USDT"
    ),
    "sol": ContractSpec(
        "SOLUSDTM", "SOL", 75, "crypto", 0.001, 0.1, "Solana", base_symbol="SOL/USDT:USDT"
    ),
    "xrp": ContractSpec(
        "XRPUSDTM", "XRP", 75, "crypto", 0.00001, 10.0, "XRP/Ripple", base_symbol="XRP/USDT:USDT"
    ),
    "bnb": ContractSpec(
        "BNBUSDTM", "BNB", 75, "crypto", 0.01, 0.01, "BNB", base_symbol="BNB/USDT:USDT"
    ),
    "doge": ContractSpec(
        "DOGEUSDTM", "DOGE", 75, "crypto", 0.00001, 100.0, "Dogecoin", base_symbol="DOGE/USDT:USDT"
    ),
    "avax": ContractSpec(
        "AVAXUSDTM", "AVAX", 75, "crypto", 0.01, 0.1, "Avalanche", base_symbol="AVAX/USDT:USDT"
    ),
    "sui": ContractSpec(
        "SUIUSDTM", "SUI", 75, "crypto", 0.0001, 1.0, "Sui", base_symbol="SUI/USDT:USDT"
    ),
    "link": ContractSpec(
        "LINKUSDTM", "LINK", 75, "crypto", 0.001, 0.1, "Chainlink", base_symbol="LINK/USDT:USDT"
    ),
    "ltc": ContractSpec(
        "LTCUSDTM", "LTC", 75, "crypto", 0.01, 0.1, "Litecoin", base_symbol="LTC/USDT:USDT"
    ),
    "dot": ContractSpec(
        "DOTUSDTM", "DOT", 75, "crypto", 0.001, 1.0, "Polkadot", base_symbol="DOT/USDT:USDT"
    ),
    "near": ContractSpec(
        "NEARUSDTM", "NEAR", 75, "crypto", 0.001, 0.1, "Near Protocol", base_symbol="NEAR/USDT:USDT"
    ),
    "hbar": ContractSpec(
        "HBARUSDTM", "HBAR", 75, "crypto", 0.00001, 10.0, "Hedera", base_symbol="HBAR/USDT:USDT"
    ),
    # ─── AI / DePIN ──────────────────────────────────────────────
    "tao": ContractSpec(
        "TAOUSDTM", "TAO", 75, "crypto", 0.1, 0.01, "Bittensor TAO", base_symbol="TAO/USDT:USDT"
    ),
    "render": ContractSpec(
        "RENDERUSDTM", "RENDER", 50, "crypto", 0.001, 0.1, "Render", base_symbol="RENDER/USDT:USDT"
    ),
    # ─── Layer 1 / DeFi ──────────────────────────────────────────
    "ada": ContractSpec(
        "ADAUSDTM", "ADA", 75, "crypto", 0.00001, 10.0, "Cardano", base_symbol="ADA/USDT:USDT"
    ),
    "ton": ContractSpec(
        "TONUSDTM", "TON", 75, "crypto", 0.0001, 1.0, "Toncoin", base_symbol="TON/USDT:USDT"
    ),
    "trx": ContractSpec(
        "TRXUSDTM", "TRX", 75, "crypto", 0.00001, 100.0, "Tron", base_symbol="TRX/USDT:USDT"
    ),
    "atom": ContractSpec(
        "ATOMUSDTM", "ATOM", 50, "crypto", 0.001, 0.1, "Cosmos", base_symbol="ATOM/USDT:USDT"
    ),
    "inj": ContractSpec(
        "INJUSDTM", "INJ", 50, "crypto", 0.001, 1.0, "Injective", base_symbol="INJ/USDT:USDT"
    ),
    "sei": ContractSpec(
        "SEIUSDTM", "SEI", 75, "crypto", 0.0001, 10.0, "Sei", base_symbol="SEI/USDT:USDT"
    ),
    "op": ContractSpec(
        "OPUSDTM", "OP", 75, "crypto", 0.0001, 1.0, "Optimism", base_symbol="OP/USDT:USDT"
    ),
    "arb": ContractSpec(
        "ARBUSDTM", "ARB", 75, "crypto", 0.0001, 1.0, "Arbitrum", base_symbol="ARB/USDT:USDT"
    ),
    "ip": ContractSpec(
        "IPUSDTM", "IP", 75, "crypto", 0.00001, 1.0, "Story Protocol", base_symbol="IP/USDT:USDT"
    ),
    # ─── Meme Coins ──────────────────────────────────────────────
    "pepe": ContractSpec(
        "PEPEUSDTM", "PEPE", 75, "meme", 1e-10, 520000.0, "Pepe", base_symbol="PEPE/USDT:USDT"
    ),
    "wif": ContractSpec(
        "WIFUSDTM", "WIF", 75, "meme", 0.0001, 10.0, "dogwifhat", base_symbol="WIF/USDT:USDT"
    ),
    "fartcoin": ContractSpec(
        "FARTCOINUSDTM",
        "FARTCOIN",
        50,
        "meme",
        0.0001,
        1.0,
        "Fartcoin",
        base_symbol="FARTCOIN/USDT:USDT",
    ),
    "shib": ContractSpec(
        "SHIBUSDTM", "SHIB", 75, "meme", 1e-9, 100000.0, "Shiba Inu", base_symbol="SHIB/USDT:USDT"
    ),
    "floki": ContractSpec(
        "FLOKIUSDTM", "FLOKI", 75, "meme", 1e-9, 100000.0, "Floki", base_symbol="FLOKI/USDT:USDT"
    ),
    "bonk": ContractSpec(
        "1000BONKUSDTM",
        "1000BONK",
        75,
        "meme",
        1e-6,
        1000.0,
        "Bonk (1000x)",
        base_symbol="1000BONK/USDT:USDT",
    ),
    "trump": ContractSpec(
        "TRUMPUSDTM", "TRUMP", 50, "meme", 0.001, 0.1, "Trump Meme", base_symbol="TRUMP/USDT:USDT"
    ),
    "popcat": ContractSpec(
        "POPCATUSDTM", "POPCAT", 50, "meme", 0.0001, 1.0, "Popcat", base_symbol="POPCAT/USDT:USDT"
    ),
    "moodeng": ContractSpec(
        "MOODENGUSDTM",
        "MOODENG",
        50,
        "meme",
        0.00001,
        10.0,
        "Moo Deng",
        base_symbol="MOODENG/USDT:USDT",
    ),
    # ─── Hyperliquid / DeFi Tokens ───────────────────────────────
    "hype": ContractSpec(
        "HYPEUSDTM", "HYPE", 75, "crypto", 0.001, 0.1, "Hyperliquid", base_symbol="HYPE/USDT:USDT"
    ),
    "siren": ContractSpec(
        "SIRENUSDTM", "SIREN", 20, "crypto", 0.00001, 10.0, "Siren", base_symbol="SIREN/USDT:USDT"
    ),
    "river": ContractSpec(
        "RIVERUSDTM", "RIVER", 50, "crypto", 0.001, 1.0, "River", base_symbol="RIVER/USDT:USDT"
    ),
    # ─── Precious Metals (Tokenized) ─────────────────────────────
    "gold": ContractSpec(
        "PAXGUSDTM",
        "PAXG",
        30,
        "metals",
        0.01,
        0.001,
        "Gold (PAXG tokenized)",
        base_symbol="PAXG/USDT:USDT",
    ),
    "xaut": ContractSpec(
        "XAUTUSDTM",
        "XAUT",
        75,
        "metals",
        0.01,
        0.001,
        "Gold (Tether Gold)",
        base_symbol="XAUT/USDT:USDT",
    ),
    "silver": ContractSpec(
        "XAGUSDTM", "XAG", 75, "metals", 0.01, 0.01, "Silver", base_symbol="XAG/USDT:USDT"
    ),
    "platinum": ContractSpec(
        "XPTUSDTM", "XPT", 75, "metals", 0.01, 0.001, "Platinum", base_symbol="XPT/USDT:USDT"
    ),
    "palladium": ContractSpec(
        "XPDUSDTM", "XPD", 75, "metals", 0.01, 0.001, "Palladium", base_symbol="XPD/USDT:USDT"
    ),
    # ─── Commodities ─────────────────────────────────────────────
    "oil": ContractSpec(
        "CLUSDTM",
        "CL",
        50,
        "commodities",
        0.001,
        0.01,
        "Crude Oil (WTI)",
        base_symbol="CL/USDT:USDT",
    ),
    "copper": ContractSpec(
        "COPPERUSDTM",
        "COPPER",
        50,
        "commodities",
        0.001,
        1.0,
        "Copper",
        base_symbol="COPPER/USDT:USDT",
    ),
    # ─── Stocks (Tokenized) ──────────────────────────────────────
    "tsla": ContractSpec(
        "TSLAUSDTM", "TSLA", 10, "stocks", 0.01, 0.01, "Tesla", base_symbol="TSLA/USDT:USDT"
    ),
    "nvda": ContractSpec(
        "NVDAUSDTM", "NVDA", 10, "stocks", 0.01, 0.01, "NVIDIA", base_symbol="NVDA/USDT:USDT"
    ),
    "amzn": ContractSpec(
        "AMZNUSDTM", "AMZN", 10, "stocks", 0.01, 0.01, "Amazon", base_symbol="AMZN/USDT:USDT"
    ),
    "googl": ContractSpec(
        "GOOGLUSDTM", "GOOGL", 10, "stocks", 0.01, 0.01, "Google", base_symbol="GOOGL/USDT:USDT"
    ),
    "meta": ContractSpec(
        "METAUSDTM", "META", 10, "stocks", 0.01, 0.01, "Meta", base_symbol="META/USDT:USDT"
    ),
    "mstr": ContractSpec(
        "MSTRUSDTM", "MSTR", 10, "stocks", 0.01, 0.01, "MicroStrategy", base_symbol="MSTR/USDT:USDT"
    ),
    "coin": ContractSpec(
        "COINUSDTM", "COIN", 10, "stocks", 0.01, 0.01, "Coinbase", base_symbol="COIN/USDT:USDT"
    ),
    "pltr": ContractSpec(
        "PLTRUSDTM", "PLTR", 10, "stocks", 0.01, 0.01, "Palantir", base_symbol="PLTR/USDT:USDT"
    ),
    "hood": ContractSpec(
        "HOODUSDTM", "HOOD", 10, "stocks", 0.01, 0.01, "Robinhood", base_symbol="HOOD/USDT:USDT"
    ),
    "intc": ContractSpec(
        "INTCUSDTM", "INTC", 10, "stocks", 0.01, 0.01, "Intel", base_symbol="INTC/USDT:USDT"
    ),
    # ─── More Crypto (Popular) ───────────────────────────────────
    "ondo": ContractSpec(
        "ONDOUSDTM",
        "ONDO",
        50,
        "crypto",
        0.0001,
        10.0,
        "Ondo Finance",
        base_symbol="ONDO/USDT:USDT",
    ),
    "pendle": ContractSpec(
        "PENDLEUSDTM", "PENDLE", 50, "crypto", 0.0001, 1.0, "Pendle", base_symbol="PENDLE/USDT:USDT"
    ),
    "jup": ContractSpec(
        "JUPUSDTM", "JUP", 50, "crypto", 0.0001, 1.0, "Jupiter", base_symbol="JUP/USDT:USDT"
    ),
    "ray": ContractSpec(
        "RAYUSDTM", "RAY", 50, "crypto", 0.0001, 1.0, "Raydium", base_symbol="RAY/USDT:USDT"
    ),
    "ena": ContractSpec(
        "ENAUSDTM", "ENA", 75, "crypto", 0.0001, 1.0, "Ethena", base_symbol="ENA/USDT:USDT"
    ),
    "kas": ContractSpec(
        "KASUSDTM", "KAS", 50, "crypto", 1e-6, 100.0, "Kaspa", base_symbol="KAS/USDT:USDT"
    ),
    "virtual": ContractSpec(
        "VIRTUALUSDTM",
        "VIRTUAL",
        50,
        "crypto",
        0.0001,
        1.0,
        "Virtuals Protocol",
        base_symbol="VIRTUAL/USDT:USDT",
    ),
    "pengu": ContractSpec(
        "PENGUUSDTM",
        "PENGU",
        75,
        "crypto",
        1e-6,
        10.0,
        "Pudgy Penguins",
        base_symbol="PENGU/USDT:USDT",
    ),
}


def get_contract(key: str) -> ContractSpec | None:
    """Look up a contract by its short key name."""
    return ASSET_REGISTRY.get(key.lower())


def get_by_symbol(symbol: str) -> tuple[str, ContractSpec] | None:
    """Look up a contract by its exchange symbol. Returns (key, spec) or None."""
    for key, spec in ASSET_REGISTRY.items():
        if spec.symbol == symbol:
            return key, spec
    return None


def get_by_base_symbol(base_symbol: str) -> tuple[str, ContractSpec] | None:
    """Look up a contract by its CCXT unified symbol. Returns (key, spec) or None."""
    for key, spec in ASSET_REGISTRY.items():
        if spec.base_symbol == base_symbol:
            return key, spec
    return None


def list_by_category(category: str) -> dict[str, ContractSpec]:
    """Return all contracts in a given category."""
    return {k: v for k, v in ASSET_REGISTRY.items() if v.category == category}


def get_categories() -> list[str]:
    """Return all unique categories."""
    return sorted(set(spec.category for spec in ASSET_REGISTRY.values()))


# Convenience: default recommended assets for new users
DEFAULT_ENABLED = [
    "btc",
    "eth",
    "sol",
    "doge",
    "sui",
    "pepe",
    "avax",
    "wif",
    "fartcoin",
]
