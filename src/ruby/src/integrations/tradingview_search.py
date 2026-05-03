"""
TradingView Symbol Search
===========================
Search and discovery module for TradingView symbols, built on the
``TradingView-API`` package's ``SymbolSearch`` facility.  Results are
normalised into a standard FKS dictionary format and optionally filtered
by asset type.

This module is intentionally **stateless** — it does not require a live
WebSocket connection and can be used independently of
:mod:`~lib.integrations.tradingview_client`.

Result format
-------------
Every symbol returned by :func:`search_symbols` is a dict with the
following keys::

    {
        "symbol":      "BTCUSDT",          # base symbol name
        "exchange":    "BINANCE",           # exchange / data source
        "description": "Bitcoin / TetherUS",
        "asset_type":  "crypto",            # one of ASSET_TYPES
        "currency":    "USDT",              # quote / settlement currency
    }

Asset type classification
-------------------------
:func:`classify_asset_type` maps the raw exchange and type metadata
returned by TradingView into one of five canonical FKS categories:

- ``futures``  — CME, NYMEX, COMEX, CBOT, ICE, SGX, Eurex, etc.
- ``forex``    — FX / FOREX / OANDA / FXCM pairs
- ``crypto``   — BINANCE, COINBASE, KRAKEN, BYBIT, BITSTAMP, etc.
- ``stocks``   — NASDAQ, NYSE, AMEX, LSE, TSX, ASX, etc.
- ``indices``  — index-type symbols (SPX, NDX, DJI, VIX, etc.)

When the type cannot be determined the fallback is ``"stocks"``.

Environment variables
---------------------
This module reads no environment variables directly.  The underlying
``TradingView-API`` import is guarded so the module can be imported
safely even when the package is not installed.

Usage
-----
::

    from integrations.tradingview_search import search_symbols

    results = await search_symbols("BTCUSD", asset_type="crypto")
    for r in results:
        print(f"{r['exchange']}:{r['symbol']}  ({r['asset_type']})")

    # Without filtering
    all_results = await search_symbols("AAPL")

    # Classify a raw result dict
    from integrations.tradingview_search import classify_asset_type
    atype = classify_asset_type({"exchange": "BINANCE", "type": "crypto"})
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# Lazy TradingView-API import guard
# ---------------------------------------------------------------------------
# The ``TradingView-API`` pip package may not be installed in every
# environment (e.g. CI, lightweight dev containers).  We defer the import
# and surface a clear error only when search is actually invoked.

_TV_AVAILABLE = False
_TV_IMPORT_ERROR: str | None = None

try:
    from TradingView import SymbolSearch  # type: ignore[import-untyped]

    _TV_AVAILABLE = True
except ImportError as _exc:
    _TV_IMPORT_ERROR = (
        f"TradingView-API package is not installed ({_exc}). Install it with:  pip install TradingView-API==1.0.1"
    )
    SymbolSearch = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Logger (structlog — project convention)
# ---------------------------------------------------------------------------

logger = structlog.get_logger("integrations.tradingview_search")

# ---------------------------------------------------------------------------
# Constants — asset type classification
# ---------------------------------------------------------------------------

#: Canonical FKS asset types.
ASSET_TYPES: frozenset[str] = frozenset(
    {
        "futures",
        "forex",
        "crypto",
        "stocks",
        "indices",
    }
)

#: Exchanges / data sources that are unambiguously futures venues.
_FUTURES_EXCHANGES: frozenset[str] = frozenset(
    {
        "CME",
        "CME_MINI",
        "CME_MICRO",
        "COMEX",
        "NYMEX",
        "CBOT",
        "ICE",
        "SGX",
        "EUREX",
        "OSE",
        "TOCOM",
        "HKEX_F",
        "BMF",
        "MCX",
        "NCDEX",
        "DGCX",
        "LME",
        "MGEX",
        "KCBT",
    }
)

#: Exchanges / data sources that are unambiguously crypto venues.
_CRYPTO_EXCHANGES: frozenset[str] = frozenset(
    {
        "BINANCE",
        "BINANCEUS",
        "COINBASE",
        "KRAKEN",
        "BITSTAMP",
        "BYBIT",
        "OKX",
        "BITFINEX",
        "HUOBI",
        "KUCOIN",
        "GATEIO",
        "GEMINI",
        "POLONIEX",
        "BITMEX",
        "DERIBIT",
        "FTX",
        "CRYPTO",
        "CRYPTOCAP",
        "PHEMEX",
        "MEXC",
        "BITGET",
    }
)

#: Exchanges / data sources that are unambiguously forex venues.
_FOREX_EXCHANGES: frozenset[str] = frozenset(
    {
        "FX",
        "FOREX",
        "OANDA",
        "FXCM",
        "FX_IDC",
        "SAXO",
        "PEPPERSTONE",
        "FOREXCOM",
        "CAPITALCOM",
    }
)

#: Exchanges / data sources that are unambiguously stock exchanges.
_STOCK_EXCHANGES: frozenset[str] = frozenset(
    {
        "NASDAQ",
        "NYSE",
        "AMEX",
        "ARCA",
        "BATS",
        "LSE",
        "TSX",
        "TSXV",
        "ASX",
        "NSE",
        "BSE",
        "SSE",
        "SZSE",
        "HKEX",
        "TSE",
        "JPX",
        "KRX",
        "MOEX",
        "BMV",
        "BOVESPA",
        "B3",
        "JSE",
        "NZX",
        "SGX",
        "XETR",
        "SWX",
        "MIL",
        "EURONEXT",
        "OMXSTO",
        "OMXHEX",
        "OMXCOP",
        "OMXICE",
        "OMXTAL",
        "OMXVIL",
        "OMXRIG",
        "ATHEX",
        "WBAG",
        "BET",
        "PSE",
        "SET",
        "HOSE",
        "IDX",
    }
)

#: TradingView ``type`` field values that map directly to an FKS type.
_TYPE_MAP: dict[str, str] = {
    "futures": "futures",
    "future": "futures",
    "forex": "forex",
    "cfd": "forex",
    "crypto": "crypto",
    "bitcoin": "crypto",
    "stock": "stocks",
    "dr": "stocks",
    "fund": "stocks",
    "etf": "stocks",
    "index": "indices",
    "economic": "indices",
    "bond": "indices",
}


# ---------------------------------------------------------------------------
# Classification helper
# ---------------------------------------------------------------------------


def classify_asset_type(symbol_data: dict[str, Any]) -> str:
    """Classify a TradingView symbol into an FKS asset type.

    Uses the ``exchange`` and ``type`` fields from TradingView's search
    response to determine the canonical FKS category.

    Classification priority:
    1. Exact ``type`` match in ``_TYPE_MAP``
    2. Exchange name match against known venue sets
    3. Heuristic: symbol suffix or naming conventions
    4. Fallback: ``"stocks"``

    Args:
        symbol_data: A dict containing at least ``exchange`` and/or ``type``
            keys (as returned by ``SymbolSearch``).

    Returns:
        One of ``"futures"``, ``"forex"``, ``"crypto"``, ``"stocks"``,
        or ``"indices"``.
    """
    raw_type = str(symbol_data.get("type", "")).strip().lower()
    exchange = str(symbol_data.get("exchange", "")).strip().upper()
    symbol = str(symbol_data.get("symbol", "")).strip().upper()

    # 1. Direct type mapping
    if raw_type in _TYPE_MAP:
        return _TYPE_MAP[raw_type]

    # 2. Exchange-based classification
    # Strip trailing qualifiers like "_DL" or numbers that some TV feeds add
    exchange_base = exchange.split("_")[0] if "_" in exchange else exchange

    if exchange in _FUTURES_EXCHANGES or exchange_base in _FUTURES_EXCHANGES:
        return "futures"
    if exchange in _CRYPTO_EXCHANGES or exchange_base in _CRYPTO_EXCHANGES:
        return "crypto"
    if exchange in _FOREX_EXCHANGES or exchange_base in _FOREX_EXCHANGES:
        return "forex"
    if exchange in _STOCK_EXCHANGES or exchange_base in _STOCK_EXCHANGES:
        return "stocks"

    # 3. Heuristic: common patterns
    # Futures often have "!" suffix (ES1!, NQ1!, GC1!) or "=F"
    if symbol.endswith("!") or symbol.endswith("=F"):
        return "futures"

    # Forex pairs are typically 6 chars (EURUSD, GBPJPY) or have "/" separator
    if "/" in symbol and len(symbol) <= 10:
        parts = symbol.split("/")
        if len(parts) == 2 and all(2 <= len(p) <= 4 for p in parts):
            return "forex"
    if len(symbol) == 6 and symbol.isalpha():
        # Could be forex — but also could be a stock ticker, so don't classify
        pass

    # Crypto pairs often end in USDT, USD, BTC, ETH
    crypto_suffixes = ("USDT", "BUSD", "USDC", "PERP", "1000")
    if any(symbol.endswith(s) for s in crypto_suffixes):
        return "crypto"

    # Index heuristics
    index_symbols = {"SPX", "NDX", "DJI", "VIX", "RUT", "IXIC", "GSPC", "DXY"}
    if symbol in index_symbols:
        return "indices"

    # 4. Fallback
    logger.debug(
        "classify_fallback",
        symbol=symbol,
        exchange=exchange,
        raw_type=raw_type,
        fallback="stocks",
    )
    return "stocks"


# ---------------------------------------------------------------------------
# Result normalisation
# ---------------------------------------------------------------------------


def _normalise_result(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise a single TradingView search result into FKS format.

    Args:
        raw: A raw result dict as returned by ``SymbolSearch``.

    Returns:
        A dict with keys: ``symbol``, ``exchange``, ``description``,
        ``asset_type``, ``currency``.
    """
    symbol = str(raw.get("symbol", raw.get("name", ""))).strip()
    exchange = str(raw.get("exchange", "")).strip()
    description = str(raw.get("description", raw.get("full_name", ""))).strip()
    currency = str(raw.get("currency_code", raw.get("currency", ""))).strip()

    # Sometimes the symbol comes as "EXCHANGE:SYMBOL" — split it
    if ":" in symbol and not exchange:
        parts = symbol.split(":", 1)
        exchange = parts[0]
        symbol = parts[1]

    asset_type = classify_asset_type(raw)

    return {
        "symbol": symbol,
        "exchange": exchange.upper(),
        "description": description,
        "asset_type": asset_type,
        "currency": currency.upper() if currency else "",
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _search_sync(query: str) -> list[dict[str, Any]]:
    """Blocking symbol search — called via ``asyncio.to_thread()``.

    Args:
        query: Free-text search query (e.g. ``"BTCUSD"``, ``"Apple"``).

    Returns:
        List of raw result dicts from ``SymbolSearch``.

    Raises:
        RuntimeError: If the TradingView-API package is not installed.
    """
    if not _TV_AVAILABLE or SymbolSearch is None:
        raise RuntimeError(_TV_IMPORT_ERROR or "TradingView-API package is not available.")

    try:
        results = SymbolSearch(query)  # type: ignore[misc]
    except Exception as exc:
        logger.error("SymbolSearch call failed", query=query, error=str(exc))
        raise

    # SymbolSearch may return a list of dicts, a custom result object, or
    # similar iterable.  Normalise to a plain list[dict].
    if results is None:
        return []

    if isinstance(results, dict):
        # Single result wrapped in a dict
        return [results]

    parsed: list[dict[str, Any]] = []
    try:
        for item in results:
            if isinstance(item, dict):
                parsed.append(item)
            elif hasattr(item, "__dict__"):
                parsed.append(vars(item))
            elif hasattr(item, "to_dict"):
                parsed.append(item.to_dict())
            else:
                # Last resort — try treating it as a mapping
                parsed.append(dict(item))  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        logger.warning(
            "Could not iterate search results",
            query=query,
            result_type=type(results).__name__,
            error=str(exc),
        )
        # If the whole object looks dict-like, wrap it
        if hasattr(results, "__dict__"):
            parsed.append(vars(results))

    return parsed


async def search_symbols(
    query: str,
    asset_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search TradingView symbols and return normalised FKS-format results.

    The blocking ``SymbolSearch`` call is dispatched to a thread via
    ``asyncio.to_thread()`` so the event loop is never blocked.

    Args:
        query: Free-text search string (symbol, company name, etc.).
        asset_type: Optional filter — only return results matching this
            FKS asset type (``"futures"``, ``"forex"``, ``"crypto"``,
            ``"stocks"``, ``"indices"``).  ``None`` returns all types.

    Returns:
        List of normalised result dicts.  Empty list on error or no matches.

    Examples:
        >>> results = await search_symbols("AAPL")
        >>> results[0]["exchange"]
        'NASDAQ'

        >>> crypto = await search_symbols("BTC", asset_type="crypto")
    """
    if not _TV_AVAILABLE:
        logger.warning(
            "search_symbols called but TradingView-API not installed",
            error=_TV_IMPORT_ERROR,
        )
        return []

    if not query or not query.strip():
        return []

    # Validate asset_type filter if provided
    if asset_type is not None:
        asset_type = asset_type.strip().lower()
        if asset_type not in ASSET_TYPES:
            logger.warning(
                "Invalid asset_type filter, ignoring",
                asset_type=asset_type,
                valid=sorted(ASSET_TYPES),
            )
            asset_type = None

    logger.debug("search_symbols", query=query, asset_type=asset_type)

    try:
        raw_results = await asyncio.to_thread(_search_sync, query.strip())
    except RuntimeError:
        # Package not installed — already logged
        return []
    except Exception as exc:
        logger.error(
            "Symbol search failed",
            query=query,
            error=str(exc),
        )
        return []

    # Normalise all results
    normalised: list[dict[str, Any]] = []
    for raw in raw_results:
        try:
            result = _normalise_result(raw)
            normalised.append(result)
        except Exception as exc:
            logger.debug(
                "Failed to normalise search result",
                raw=raw,
                error=str(exc),
            )
            continue

    # Apply asset_type filter if requested
    if asset_type is not None:
        normalised = [r for r in normalised if r["asset_type"] == asset_type]

    logger.info(
        "search_complete",
        query=query,
        total_raw=len(raw_results),
        returned=len(normalised),
        asset_type_filter=asset_type,
    )

    return normalised


# ---------------------------------------------------------------------------
# Public API summary
# ---------------------------------------------------------------------------

__all__ = [
    "ASSET_TYPES",
    "classify_asset_type",
    "search_symbols",
]
