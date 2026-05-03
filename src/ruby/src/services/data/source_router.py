"""
Data Source Router — Routes market data requests to the active data source
===========================================================================
Centralizes the logic for determining which data source (Kraken, Rithmic,
or both) should serve data for a given request. Used by DOM, charts,
signals, and the simulation engine.

The active source is stored in Redis at ``settings:data_source`` and can
be changed via the settings API.

Rithmic auto-preference:
    When ``RITHMIC_LIVE_DATA=1`` and the ``RithmicStreamManager`` reports
    ``is_live() == True``, futures symbols are automatically routed to
    Rithmic regardless of the ``settings:data_source`` value.  This means
    the system follows the actual connection state rather than a manually
    toggled setting.

    Fallback chain for futures (when Rithmic is disconnected):
        Rithmic → Massive → yfinance

    Source switches are logged at INFO level so ops can trace data origin
    changes in the service logs.
"""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Request

from core.logging_config import get_logger

# Tracks the last resolved source per symbol so we can log transitions.
_last_source_per_symbol: dict[str, str] = {}

logger = get_logger(__name__)

__all__ = [
    "get_active_source",
    "is_crypto_symbol",
    "is_futures_symbol",
    "should_use_source",
    "is_rithmic_live",
    "get_available_symbols",
    "source_api_router",
]

# ---------------------------------------------------------------------------
# Redis key for the active data source setting
# ---------------------------------------------------------------------------
_REDIS_DATA_SOURCE_KEY = "settings:data_source"

_VALID_SOURCES = ("kraken", "rithmic", "both", "tradingview")

# ---------------------------------------------------------------------------
# Futures symbol map — the 9 focus futures contracts
# ---------------------------------------------------------------------------
FUTURES_SYMBOLS: dict[str, dict[str, str]] = {
    "MGC": {"name": "Micro Gold", "data_ticker": "MGC=F"},
    "SIL": {"name": "Micro Silver", "data_ticker": "SIL=F"},
    "MES": {"name": "Micro E-mini S&P 500", "data_ticker": "MES=F"},
    "MNQ": {"name": "Micro E-mini Nasdaq", "data_ticker": "MNQ=F"},
    "M2K": {"name": "Micro E-mini Russell", "data_ticker": "M2K=F"},
    "MYM": {"name": "Micro E-mini Dow", "data_ticker": "MYM=F"},
    "ZN": {"name": "10-Year T-Note", "data_ticker": "ZN=F"},
    "ZB": {"name": "30-Year T-Bond", "data_ticker": "ZB=F"},
    "ZW": {"name": "Wheat", "data_ticker": "ZW=F"},
}

# Shorthand crypto names that should route to Kraken
_CRYPTO_SHORTHANDS = frozenset(
    {
        "BTC",
        "ETH",
        "SOL",
        "LINK",
        "AVAX",
        "DOT",
        "ADA",
        "POL",
        "XRP",
    }
)


# ---------------------------------------------------------------------------
# Redis helpers (same pattern as the rest of the project)
# ---------------------------------------------------------------------------


def _redis_client():
    """Return ``(client, available)`` — ``(None, False)`` if unavailable."""
    try:
        from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

        return _r, REDIS_AVAILABLE
    except ImportError:
        return None, False


# ---------------------------------------------------------------------------
# Rithmic live-connection check
# ---------------------------------------------------------------------------


def is_rithmic_live() -> bool:
    """Return True when Rithmic is enabled *and* the stream is actively connected.

    Checks ``RITHMIC_LIVE_DATA=1`` (env) **and** the ``RithmicStreamManager``
    singleton's ``is_live()`` flag, which requires the TICKER_PLANT WebSocket
    to be in the connected state.

    This is the authoritative check used by ``should_use_source`` to decide
    whether to auto-route futures to Rithmic regardless of the
    ``settings:data_source`` Redis key.
    """
    if os.getenv("RITHMIC_LIVE_DATA", "0") != "1":
        return False
    try:
        from integrations.rithmic_client import get_stream_manager  # type: ignore[import-unresolved]

        return get_stream_manager().is_live()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Core routing functions
# ---------------------------------------------------------------------------


def get_active_source() -> str:
    """Read the active data source from Redis.

    Returns one of ``"kraken"``, ``"rithmic"``, or ``"both"``.
    Defaults to ``"kraken"`` if the key is not set or Redis is unavailable.

    Note: this reflects the *operator-configured* preference.  Use
    ``should_use_source(symbol)`` to get the *effective* source for a symbol,
    which accounts for whether Rithmic is actually live.
    """
    r, available = _redis_client()
    if not available or r is None:
        return "kraken"
    try:
        raw = r.get(_REDIS_DATA_SOURCE_KEY)
        if raw is None:
            return "kraken"
        value = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        return value if value in _VALID_SOURCES else "kraken"
    except Exception:
        return "kraken"


def is_crypto_symbol(symbol: str) -> bool:
    """Return ``True`` if *symbol* looks like a crypto / Kraken symbol.

    Matches:
    - Symbols starting with ``"KRAKEN:"``
    - Shorthand names like ``"BTC"``, ``"ETH"``, ``"SOL"``, etc.
    """
    if symbol.upper().startswith("KRAKEN:"):
        return True
    return symbol.upper() in _CRYPTO_SHORTHANDS


def is_futures_symbol(symbol: str) -> bool:
    """Return ``True`` if *symbol* is a recognised CME futures symbol.

    Checks the symbol (case-insensitive) against the ``FUTURES_SYMBOLS`` map
    and common ticker suffixes like ``"MES=F"``.
    """
    sym = symbol.upper()
    if sym in FUTURES_SYMBOLS:
        return True
    # Also check if the symbol matches a data_ticker (e.g. "MES=F")
    return any(sym == info["data_ticker"].upper() for info in FUTURES_SYMBOLS.values())


def _log_source_switch(symbol: str, new_source: str) -> None:
    """Log a data source transition for *symbol* if it changed since last call."""
    prev = _last_source_per_symbol.get(symbol)
    if prev != new_source:
        if prev is not None:
            logger.info(
                "source_router: %s data source changed %s → %s",
                symbol,
                prev,
                new_source,
            )
        _last_source_per_symbol[symbol] = new_source


def should_use_source(symbol: str) -> str:
    """Determine which data source to use for *symbol*.

    Resolution order
    ----------------
    1. **Rithmic auto-preference** (futures only): when ``RITHMIC_LIVE_DATA=1``
       *and* the ``RithmicStreamManager`` is actively connected, futures symbols
       are routed to ``"rithmic"`` regardless of the ``settings:data_source``
       setting.  This ensures live data takes priority over the operator toggle.

    2. **Operator setting** (``settings:data_source`` Redis key):
       - ``"both"``    → crypto → ``"kraken"``, futures → ``"rithmic"``, else ``"mock"``
       - ``"kraken"``  → futures → ``"massive"`` (fallback), crypto → ``"kraken"``
       - ``"rithmic"`` → crypto → ``"mock"``, futures → ``"rithmic"``

    3. **Fallback chain** for futures when Rithmic is configured but
       disconnected: ``rithmic`` → ``"massive"`` → ``"yfinance"`` (the downstream
       data provider resolves the final step; this function returns ``"massive"``
       as the explicit fallback signal rather than ``"mock"``).

    Source switches are logged at INFO level so ops can trace transitions.

    Returns:
        One of ``"kraken"``, ``"rithmic"``, ``"massive"``, or ``"mock"``.
    """
    active = get_active_source()
    crypto = is_crypto_symbol(symbol)
    futures = is_futures_symbol(symbol)
    rithmic_live = is_rithmic_live()

    # ── Rithmic auto-preference for futures ──────────────────────────────────
    # When the stream is actually connected, prefer it for all futures symbols
    # even if the operator setting says "kraken" or "both".  This is the live-
    # trading fast path and takes priority over any manual toggle.
    if futures and rithmic_live:
        source = "rithmic"
        _log_source_switch(symbol, source)
        return source

    # ── Operator setting ─────────────────────────────────────────────────────
    if active == "tradingview":
        # TradingView covers all asset classes — route everything through it
        # when explicitly selected.  Falls back to symbol-appropriate source
        # if TV is not connected (treats futures → massive, crypto → kraken).
        tv_status = _get_tv_status()
        if tv_status == "connected":
            source = "tradingview"
        elif crypto:
            source = "kraken"
        elif futures:
            source = "massive"
        else:
            source = "mock"
        _log_source_switch(symbol, source)
        return source

    if active == "both":
        if crypto:
            source = "kraken"
        elif futures:
            # Rithmic configured but not live → fall back to Massive
            source = "massive"
        else:
            source = "mock"
        _log_source_switch(symbol, source)
        return source

    if active == "kraken":
        source = "massive" if futures else "kraken"
        _log_source_switch(symbol, source)
        return source

    if active == "rithmic":
        if crypto:
            source = "mock"
        elif futures:
            # Rithmic configured but stream is down → fall back to Massive
            source = "massive"
        else:
            source = "mock"
        _log_source_switch(symbol, source)
        return source

    _log_source_switch(symbol, "mock")
    return "mock"


def _get_kraken_status() -> str:
    """Check Kraken feed connectivity status."""
    try:
        from integrations.kraken_client import get_kraken_feed  # type: ignore[import-unresolved]

        feed = get_kraken_feed()
        if feed is not None:
            if getattr(feed, "is_connected", False):
                return "connected"
            if getattr(feed, "is_running", False):
                return "connecting"
            return "disconnected"
        return "disconnected"
    except Exception:
        return "disconnected"


def _get_rithmic_status() -> str:
    """Check Rithmic connectivity status.

    Prefers the ``RithmicStreamManager.is_live()`` flag (TICKER_PLANT stream)
    over account-level polling so the status reflects the actual live-data
    connection rather than whether a short-lived account refresh succeeded.
    """
    # Fast path: check the persistent stream first
    try:
        from integrations.rithmic_client import get_stream_manager  # type: ignore[import-unresolved]

        sm = get_stream_manager()
        if sm.is_live():
            return "connected"
        if sm._connected:
            # Connected but env var not set — treat as "connecting"
            return "connecting"
    except Exception:
        pass

    # Fallback: check account-level manager
    try:
        from integrations.rithmic_client import get_manager  # type: ignore[import-unresolved]

        mgr = get_manager()
        all_status = mgr.get_all_status()
        if not all_status:
            return "not_configured"
        for _key, st in all_status.items():
            if isinstance(st, dict) and st.get("connected"):
                return "connected"
        return "disconnected"
    except Exception:
        return "not_configured"


def _get_tv_status() -> str:
    """Check TradingView client connectivity status.

    Returns ``"connected"``, ``"disconnected"``, or ``"not_configured"``.
    The client is considered configured when ``TV_SESSION_ID`` is set in
    the environment **or** the singleton has been successfully connected.
    """
    try:
        from integrations.tradingview_client import get_tv_client  # type: ignore[import-unresolved]

        client = get_tv_client()
        if client.is_connected:
            return "connected"
        # Client exists but not yet connected — counts as configured but idle
        session_id = os.getenv("TV_SESSION_ID", "")
        return "disconnected" if session_id else "not_configured"
    except Exception:
        session_id = os.getenv("TV_SESSION_ID", "")
        return "not_configured" if not session_id else "disconnected"


def get_available_symbols() -> dict[str, Any]:
    """Return categorised symbol lists with source and liveness info.

    Returns a dict with ``"crypto"``, ``"futures"``, and ``"active_source"`` keys.
    """
    active = get_active_source()
    kraken_status = _get_kraken_status()
    rithmic_status = _get_rithmic_status()

    # --- Crypto symbols from Kraken ---
    crypto_symbols: list[dict[str, Any]] = []
    try:
        from integrations.kraken_client import KRAKEN_PAIRS  # type: ignore[import-unresolved]

        kraken_live = kraken_status == "connected" and active in ("kraken", "both")
        for name, info in KRAKEN_PAIRS.items():
            crypto_symbols.append(
                {
                    "symbol": info["internal_ticker"],
                    "name": name,
                    "source": "kraken",
                    "base": info.get("base", ""),
                    "live": kraken_live,
                }
            )
    except Exception:
        # Kraken client not available — provide minimal list
        for shorthand in sorted(_CRYPTO_SHORTHANDS):
            crypto_symbols.append(
                {
                    "symbol": f"KRAKEN:{shorthand}USD",
                    "name": shorthand,
                    "source": "kraken",
                    "base": shorthand,
                    "live": False,
                }
            )

    # --- Futures symbols ---
    # Live when Rithmic stream is actually connected (auto-preference logic),
    # not just when the operator setting says "rithmic".
    rithmic_stream_live = is_rithmic_live()
    rithmic_live = rithmic_stream_live or (rithmic_status == "connected" and active in ("rithmic", "both"))
    futures_symbols: list[dict[str, Any]] = []
    for sym, info in FUTURES_SYMBOLS.items():
        futures_symbols.append(
            {
                "symbol": sym,
                "name": info["name"],
                "data_ticker": info["data_ticker"],
                "source": "rithmic",
                "live": rithmic_live,
            }
        )

    return {
        "crypto": crypto_symbols,
        "futures": futures_symbols,
        "active_source": active,
        "rithmic_live": rithmic_live,
        "tv_status": _get_tv_status(),
        "tv_configured": bool(os.getenv("TV_SESSION_ID", "")),
    }


# ---------------------------------------------------------------------------
# FastAPI router — /api/sources/*
# ---------------------------------------------------------------------------

source_api_router = APIRouter(prefix="/api/sources", tags=["Data Sources"])


@source_api_router.get("/symbols")
def api_available_symbols() -> dict:
    """Return all available symbols grouped by asset class.

    Includes crypto (Kraken) and futures (Rithmic) symbols with their
    current liveness status based on the active data source configuration.
    """
    return get_available_symbols()


@source_api_router.get("/status")
def api_source_status() -> dict:
    """Return status of all data sources.

    Includes connectivity state for Kraken and Rithmic, the currently
    active source, whether simulation mode is enabled, and whether the
    Rithmic stream is actively live (which triggers auto-preference for
    futures regardless of the operator setting).
    """
    active = get_active_source()
    kraken_status = _get_kraken_status()
    rithmic_status = _get_rithmic_status()
    rithmic_stream_live = is_rithmic_live()
    sim_enabled = os.getenv("SIM_ENABLED", "0") == "1"
    tv_status = _get_tv_status()
    tv_configured = bool(os.getenv("TV_SESSION_ID", ""))

    return {
        "active_source": active,
        "kraken_status": kraken_status,
        "rithmic_status": rithmic_status,
        "rithmic_stream_live": rithmic_stream_live,
        "available_sources": list(_VALID_SOURCES),
        "sim_enabled": sim_enabled,
        "sim_data_source": active if active != "both" else "kraken",
        "tv_status": tv_status,
        "tv_configured": tv_configured,
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# GET /data-source — HTML partial with radio buttons for HTMX settings panel
# POST /data-source — save selected data source to Redis
# ---------------------------------------------------------------------------

# All data sources the operator can choose from in the settings UI.
_ALL_SOURCES: list[tuple[str, str, str]] = [
    ("massive", "Massive", "Primary futures data provider (historical + live bars)"),
    ("kraken", "Kraken", "Live crypto WebSocket feed"),
    ("yfinance", "yfinance", "Yahoo Finance fallback (delayed, free)"),
    ("rithmic", "Rithmic", "CME direct market data (requires credentials)"),
    ("tradingview", "TradingView", "Multi-asset via TradingView session bridge"),
]


@source_api_router.get("/data-source")
def get_data_source_html():
    """Return an HTML partial with radio buttons for each data source.

    The currently active source is pre-selected.  Designed to be swapped
    into ``#data-source-form`` in the settings workspace via HTMX.
    """
    from fastapi.responses import HTMLResponse

    active = get_active_source()
    # Also check env var as ultimate fallback
    if active == "kraken":
        env_src = os.getenv("DATA_SOURCE", "").lower().strip()
        if env_src in {s[0] for s in _ALL_SOURCES}:
            active = env_src

    r, available = _redis_client()
    if available and r is not None:
        try:
            raw = r.get("fks:config:data_source")
            if raw is not None:
                val = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                if val in {s[0] for s in _ALL_SOURCES}:
                    active = val
        except Exception:
            pass

    rows: list[str] = []
    for src_id, label, desc in _ALL_SOURCES:
        checked = "checked" if src_id == active else ""
        dot_color = "var(--green)" if src_id == active else "var(--t3)"
        rows.append(
            f'<label style="display:flex; align-items:center; gap:8px; padding:4px 0; cursor:pointer;">'
            f'  <input type="radio" name="data-source" value="{src_id}" {checked}'
            f'         style="accent-color:var(--accent);" />'
            f'  <span style="color:{dot_color}; font-size:8px;">●</span>'
            f'  <span class="mono" style="font-size:11px; color:var(--fg);">{label}</span>'
            f'  <span class="dim" style="font-size:9px; margin-left:4px;">{desc}</span>'
            f"</label>"
        )

    html = "\n".join(rows)
    return HTMLResponse(content=(f'<div style="display:flex; flex-direction:column; gap:2px;">  {html}</div>'))


@source_api_router.post("/data-source")
async def save_data_source_endpoint(request: Request):
    """Save the selected data source to Redis.

    Accepts either JSON ``{"source": "..."}`` or form-urlencoded ``source=...``.
    Writes to both ``settings:data_source`` (existing convention) and
    ``fks:config:data_source`` (new convention used by the settings workspace).
    Returns an HTML confirmation snippet suitable for HTMX swap.
    """
    from fastapi.responses import HTMLResponse

    # ------------------------------------------------------------------
    # Parse the source value from the request body
    # ------------------------------------------------------------------
    source: str | None = None

    content_type = request.headers.get("content-type", "")
    try:
        if "json" in content_type:
            body = await request.json()
            source = body.get("source") if isinstance(body, dict) else None
        else:
            form = await request.form()
            source = form.get("source")
    except Exception as exc:
        logger.warning("save_data_source: failed to parse body: %s", exc)

    if not source or source not in {s[0] for s in _ALL_SOURCES}:
        valid = ", ".join(s[0] for s in _ALL_SOURCES)
        return HTMLResponse(
            content=f'<div class="neg mono" style="font-size:10px;">Invalid source. Valid: {valid}</div>',
            status_code=400,
        )

    # ------------------------------------------------------------------
    # Persist to Redis
    # ------------------------------------------------------------------
    r, available = _redis_client()
    if available and r is not None:
        try:
            r.set(_REDIS_DATA_SOURCE_KEY, source)
            r.set("fks:config:data_source", source)
            logger.info("save_data_source: set active source → %s", source)
        except Exception as exc:
            logger.error("save_data_source: Redis write failed: %s", exc)
            return HTMLResponse(
                content=f'<div class="neg mono" style="font-size:10px;">Redis error: {exc}</div>',
                status_code=500,
            )
    else:
        logger.warning("save_data_source: Redis unavailable — source not persisted")
        return HTMLResponse(
            content='<div class="warn mono" style="font-size:10px;">⚠ Redis unavailable — setting not saved</div>',
            status_code=503,
        )

    label = next((s[1] for s in _ALL_SOURCES if s[0] == source), source)
    return HTMLResponse(
        content=(f'<div class="pos mono" style="font-size:10px;">  ✓ Data source set to <strong>{label}</strong></div>')
    )
