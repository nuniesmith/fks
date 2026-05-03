"""
Rithmic Prop Account Integration
==================================
Read-only account monitoring for Rithmic-connected prop firm accounts
(TPT, Apex, Topstep, etc.) using the ``async-rithmic`` library.

Architecture:
    - ``RithmicAccountConfig``  — per-account credentials + metadata
    - ``RithmicAccountManager`` — async lifecycle: connect/disconnect/refresh
    - ``RithmicStreamManager``  — persistent TICKER_PLANT streaming connection
    - ``router``               — FastAPI endpoints consumed by the dashboard

Endpoints:
    GET  /api/rithmic/accounts          — list configured accounts (no creds)
    GET  /api/rithmic/status            — live status JSON for all accounts
    GET  /api/rithmic/status/html       — HTMX fragment for Connections page
    GET  /api/rithmic/account/{key}     — single account detail JSON
    POST /api/rithmic/account/{key}/refresh — force-refresh a single account
    GET  /api/rithmic/config            — load saved account configs (UI)
    POST /api/rithmic/config            — save account configs from settings UI

    --- Streaming (RITHMIC-STREAM-A) ---
    GET  /api/rithmic/stream/status           — live/connected/subscribed state
    POST /api/rithmic/stream/subscribe        — subscribe to symbols
    GET  /api/rithmic/stream/l1/{symbol}      — L1 bid/ask/last snapshot
    GET  /api/rithmic/stream/ticks/{symbol}   — recent tick history

Credentials are stored in Redis (AES-256-encrypted via a server-side key
derived from the ``SECRET_KEY`` env var) and NEVER returned to the browser.
The UI only sends credentials on initial save; subsequent reads return
masked values.

Prop firm presets (system_name / gateway defaults):
    TPT          — "Rithmic Paper Trading", Chicago
    Apex         — "Apex Trader Funding",   Chicago
    Topstep      — "TopStep",               Chicago
    TradeDay     — "TradeDay",              Chicago
    MyFundedFutures — "My Funded Futures",  Chicago
    Custom       — user-supplied values
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Rithmic"])

_EST = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# Prop firm presets
# ---------------------------------------------------------------------------

PROP_FIRM_PRESETS: dict[str, dict[str, str]] = {
    "tpt": {
        "label": "Take Profit Trader (TPT)",
        "system_name": "Rithmic Paper Trading",
        "gateway": "Chicago",
    },
    "apex": {
        "label": "Apex Trader Funding",
        "system_name": "Apex Trader Funding",
        "gateway": "Chicago",
    },
    "topstep": {
        "label": "TopStep",
        "system_name": "TopStep",
        "gateway": "Chicago",
    },
    "tradeday": {
        "label": "TradeDay",
        "system_name": "TradeDay",
        "gateway": "Chicago",
    },
    "mff": {
        "label": "My Funded Futures",
        "system_name": "My Funded Futures",
        "gateway": "Chicago",
    },
    "custom": {
        "label": "Custom",
        "system_name": "",
        "gateway": "Chicago",
    },
}

# Ordered list for the UI dropdown
PROP_FIRM_OPTIONS: list[dict[str, str]] = [{"value": k, "label": v["label"]} for k, v in PROP_FIRM_PRESETS.items()]

# ---------------------------------------------------------------------------
# Credential encryption helpers
# ---------------------------------------------------------------------------

_SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("API_KEY", "ruby-futures-default"))


def _derive_fernet_key() -> bytes:
    """Derive a 32-byte Fernet-compatible key from the server SECRET_KEY."""
    digest = hashlib.sha256(_SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _encrypt(plaintext: str) -> str:
    """Encrypt plaintext using Fernet (AES-128-CBC + HMAC).

    Falls back to base64 obfuscation when cryptography is not installed —
    still prevents accidental browser exposure, but not cryptographically
    secure.  Log a warning so the operator knows to install the package.
    """
    if not plaintext:
        return ""
    try:
        from cryptography.fernet import Fernet  # type: ignore[import-untyped]

        f = Fernet(_derive_fernet_key())
        return f.encrypt(plaintext.encode()).decode()
    except ImportError:
        logger.warning(
            "cryptography package not installed — Rithmic credentials are "
            "stored with base64 obfuscation only.  Run: pip install cryptography"
        )
        return base64.b64encode(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    """Decrypt a value previously encrypted by ``_encrypt``."""
    if not ciphertext:
        return ""
    try:
        from cryptography.fernet import Fernet  # type: ignore[import-untyped]

        f = Fernet(_derive_fernet_key())
        return f.decrypt(ciphertext.encode()).decode()
    except ImportError:
        try:
            return base64.b64decode(ciphertext.encode()).decode()
        except Exception:
            return ""
    except Exception:
        # Fernet InvalidToken or corrupt data — may be plain base64 from a migration
        try:
            return base64.b64decode(ciphertext.encode()).decode()
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Account config model
# ---------------------------------------------------------------------------

_REDIS_CONFIG_KEY = "rithmic:account_configs"
_REDIS_STATUS_KEY = "rithmic:account_status:{key}"


class RithmicAccountConfig:
    """Per-account configuration (credentials + metadata).

    ``key``         — short stable identifier, e.g. "acc1", "tpt_eval"
    ``label``       — display name shown in the UI
    ``prop_firm``   — one of the PROP_FIRM_PRESETS keys
    ``system_name`` — Rithmic system_name override (empty = use preset)
    ``gateway``     — "Chicago" | "Sydney" | "Sao Paulo" | "custom"
    ``username``    — encrypted Rithmic username
    ``password``    — encrypted Rithmic password
    ``enabled``     — whether to connect on startup
    ``app_name``    — app identifier sent to Rithmic (default: ruby_futures)
    ``app_version`` — version string sent to Rithmic
    """

    def __init__(
        self,
        key: str,
        label: str,
        prop_firm: str = "tpt",
        system_name: str = "",
        gateway: str = "Chicago",
        username: str = "",
        password: str = "",
        enabled: bool = True,
        app_name: str = "ruby_futures",
        app_version: str = "1.0",
        account_size: int = 150_000,
    ) -> None:
        self.key = key
        self.label = label
        self.prop_firm = prop_firm
        self.gateway = gateway
        self.app_name = app_name
        self.app_version = app_version
        self.enabled = enabled
        self.account_size = account_size

        # Resolve system_name: explicit override > preset > empty
        preset = PROP_FIRM_PRESETS.get(prop_firm, {})
        self.system_name = system_name or preset.get("system_name", "")

        # Credentials are always stored encrypted
        self._username_enc = username  # may already be encrypted
        self._password_enc = password

    # ------------------------------------------------------------------
    # Credential accessors
    # ------------------------------------------------------------------

    def set_credentials(self, username: str, password: str) -> None:
        """Encrypt and store plaintext credentials."""
        self._username_enc = _encrypt(username)
        self._password_enc = _encrypt(password)

    def get_username(self) -> str:
        return _decrypt(self._username_enc)

    def get_password(self) -> str:
        return _decrypt(self._password_enc)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_storage_dict(self) -> dict[str, Any]:
        """Serialise to dict for Redis storage (encrypted creds included)."""
        return {
            "key": self.key,
            "label": self.label,
            "prop_firm": self.prop_firm,
            "system_name": self.system_name,
            "gateway": self.gateway,
            "username_enc": self._username_enc,
            "password_enc": self._password_enc,
            "enabled": self.enabled,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "account_size": self.account_size,
        }

    def to_ui_dict(self) -> dict[str, Any]:
        """Serialise for the browser — credentials masked, never returned."""
        return {
            "key": self.key,
            "label": self.label,
            "prop_firm": self.prop_firm,
            "prop_firm_label": PROP_FIRM_PRESETS.get(self.prop_firm, {}).get("label", self.prop_firm),
            "system_name": self.system_name,
            "gateway": self.gateway,
            "enabled": self.enabled,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "account_size": self.account_size,
            # Never expose plaintext — show only whether credentials are configured
            "username_set": bool(self._username_enc),
            "password_set": bool(self._password_enc),
            # Mask: show first 3 chars of decrypted username for UI recognition only
            "username_hint": self._username_hint(),
        }

    def _username_hint(self) -> str:
        u = self.get_username()
        if not u:
            return ""
        if len(u) <= 4:
            return u[0] + "***"
        return u[:3] + "***"

    @classmethod
    def from_storage_dict(cls, d: dict[str, Any]) -> RithmicAccountConfig:
        obj = cls(
            key=d["key"],
            label=d.get("label", d["key"]),
            prop_firm=d.get("prop_firm", "tpt"),
            system_name=d.get("system_name", ""),
            gateway=d.get("gateway", "Chicago"),
            username=d.get("username_enc", ""),
            password=d.get("password_enc", ""),
            enabled=d.get("enabled", True),
            app_name=d.get("app_name", "ruby_futures"),
            app_version=d.get("app_version", "1.0"),
            account_size=d.get("account_size", 150_000),
        )
        # Overwrite with pre-encrypted values from storage
        obj._username_enc = d.get("username_enc", "")
        obj._password_enc = d.get("password_enc", "")
        return obj


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _load_configs() -> list[RithmicAccountConfig]:
    """Load account configs from Redis."""
    try:
        from core.cache import cache_get

        raw = cache_get(_REDIS_CONFIG_KEY)
        if raw:
            items = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            return [RithmicAccountConfig.from_storage_dict(d) for d in items]
    except Exception as exc:
        logger.debug("rithmic: config load error: %s", exc)
    return []


def _save_configs(configs: list[RithmicAccountConfig]) -> None:
    """Persist account configs to Redis (no expiry)."""
    try:
        from core.cache import cache_set

        data = json.dumps([c.to_storage_dict() for c in configs])
        cache_set(_REDIS_CONFIG_KEY, data.encode(), 0)
    except Exception as exc:
        logger.warning("rithmic: config save error: %s", exc)


def _load_status(key: str) -> dict[str, Any]:
    """Load the last-known live status for an account from Redis."""
    try:
        from core.cache import cache_get

        raw = cache_get(_REDIS_STATUS_KEY.format(key=key))
        if raw:
            return json.loads(raw.decode() if isinstance(raw, bytes) else raw)
    except Exception:
        pass
    return {}


def _save_status(key: str, status: dict[str, Any]) -> None:
    """Cache account live status in Redis (TTL: 120 s)."""
    try:
        from core.cache import cache_set

        cache_set(_REDIS_STATUS_KEY.format(key=key), json.dumps(status, default=str).encode(), 120)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Account manager
# ---------------------------------------------------------------------------

# Map from gateway name → WebSocket URL for Rithmic Protocol Buffer API
_GATEWAY_URLS: dict[str, str] = {
    "Chicago": "rituz00100.rithmic.com:443",
    "Sydney": "rituz00200.rithmic.com:443",
    "Sao Paulo": "rituz00300.rithmic.com:443",
    "test": "rituz00100.rithmic.com:443",  # test uses same URL, different system_name
}


def _resolve_gateway(name: str) -> str | None:
    """Return the WebSocket URL for the given gateway name.

    The async_rithmic RithmicClient auto-prepends ``wss://`` when missing,
    so we return bare ``host:port`` strings.
    """
    return _GATEWAY_URLS.get(name, _GATEWAY_URLS.get("Chicago"))


# ---------------------------------------------------------------------------
# Symbol → Exchange resolution for CME-traded futures
# ---------------------------------------------------------------------------

_SYMBOL_EXCHANGE_MAP: dict[str, str] = {
    # E-mini & Micro indices (CME)
    "ES": "CME",
    "MES": "CME",
    "NQ": "CME",
    "MNQ": "CME",
    "RTY": "CME",
    "M2K": "CME",
    "YM": "CME",
    "MYM": "CME",
    # Energy (NYMEX)
    "CL": "NYMEX",
    "MCL": "NYMEX",
    "NG": "NYMEX",
    "QM": "NYMEX",
    # Metals (COMEX)
    "GC": "COMEX",
    "MGC": "COMEX",
    "SI": "COMEX",
    "SIL": "COMEX",
    "HG": "COMEX",
    # Currencies (CME)
    "6E": "CME",
    "6B": "CME",
    "6J": "CME",
    "6A": "CME",
    "6C": "CME",
    "M6E": "CME",
    # Bonds (CBOT)
    "ZB": "CBOT",
    "ZN": "CBOT",
    "ZF": "CBOT",
    "ZT": "CBOT",
    # Agriculture (CBOT)
    "ZC": "CBOT",
    "ZS": "CBOT",
    "ZW": "CBOT",
}


def _resolve_exchange(symbol: str) -> str:
    """Return the exchange name for a futures symbol.

    Strips any trailing month/year contract code (e.g. ``ESM5`` → ``ES``)
    and looks up the root symbol.  Falls back to ``"CME"`` for unknowns.
    """
    # Try exact match first
    upper = symbol.upper()
    if upper in _SYMBOL_EXCHANGE_MAP:
        return _SYMBOL_EXCHANGE_MAP[upper]
    # Strip trailing month code + year digits (e.g. ESM5, MESH25)
    import re

    root = re.sub(r"[FGHJKMNQUVXZ]\d{1,2}$", "", upper)
    if root and root in _SYMBOL_EXCHANGE_MAP:
        return _SYMBOL_EXCHANGE_MAP[root]
    return "CME"  # safe default for prop firm micro futures


class RithmicAccountManager:
    """Manages async Rithmic client connections for all configured accounts.

    Each account gets its own ``RithmicClient`` instance connected to the
    Order Plant + PnL Plant for read-only position/P&L data.

    The manager is intentionally lightweight: it does NOT hold a persistent
    connection between refreshes (Rithmic sessions can be flaky in eval
    environments).  Instead, ``refresh(key)`` opens → reads → closes a
    short-lived session and stores the result in Redis.

    Long-lived streaming will be added in a future phase once we have funded
    accounts and need real-time position updates.
    """

    def __init__(self) -> None:
        self._configs: dict[str, RithmicAccountConfig] = {}
        self._status: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._loaded = False

    def reload_configs(self) -> None:
        """Reload configs from Redis (call after settings save)."""
        configs = _load_configs()
        self._configs = {c.key: c for c in configs}
        # Restore cached status for each account
        for key in self._configs:
            cached = _load_status(key)
            if cached:
                self._status[key] = cached
        self._loaded = True
        logger.info("rithmic: loaded %d account config(s)", len(self._configs))

    def get_all_ui(self) -> list[dict[str, Any]]:
        """Return all account configs safe for browser consumption."""
        if not self._loaded:
            self.reload_configs()
        return [c.to_ui_dict() for c in self._configs.values()]

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Return the last-known live status for all accounts."""
        if not self._loaded:
            self.reload_configs()
        return dict(self._status)

    def get_status(self, key: str) -> dict[str, Any]:
        return self._status.get(key, {"key": key, "connected": False, "error": "not yet polled"})

    async def refresh_account(self, key: str) -> dict[str, Any]:
        """Open a short-lived Rithmic session, pull positions + P&L, close.

        Returns a status dict that is also cached in Redis.
        """
        if not self._loaded:
            self.reload_configs()

        config = self._configs.get(key)
        if config is None:
            return {"key": key, "connected": False, "error": "account not found"}

        if not config.enabled:
            return {"key": key, "connected": False, "error": "account disabled"}

        username = config.get_username()
        password = config.get_password()
        if not username or not password:
            return {"key": key, "connected": False, "error": "credentials not configured"}

        status: dict[str, Any] = {
            "key": key,
            "label": config.label,
            "prop_firm": config.prop_firm,
            "prop_firm_label": PROP_FIRM_PRESETS.get(config.prop_firm, {}).get("label", config.prop_firm),
            "connected": False,
            "error": "",
            "refreshed_at": datetime.now(tz=_EST).isoformat(),
            "accounts": [],
            "positions": [],
            "pnl": {},
        }

        try:
            from async_rithmic import RithmicClient  # type: ignore[import-untyped]
        except ImportError:
            status["error"] = "async-rithmic not installed (pip install async-rithmic)"
            _save_status(key, status)
            self._status[key] = status
            return status

        gateway = _resolve_gateway(config.gateway)
        if gateway is None:
            status["error"] = f"unknown gateway: {config.gateway}"
            _save_status(key, status)
            self._status[key] = status
            return status

        client: Any = None
        try:
            async with self._lock:
                client = RithmicClient(  # type: ignore[possibly-undefined]
                    user=username,
                    password=password,
                    system_name=config.system_name,
                    app_name=config.app_name,
                    app_version=config.app_version,
                    url=gateway,
                )
                from async_rithmic import SysInfraType as _SysInfraType  # type: ignore[import-untyped]

                await asyncio.wait_for(
                    client.connect(infra_type=_SysInfraType.PNL_PLANT),
                    timeout=15.0,
                )
                status["connected"] = True

                # List accounts
                try:
                    accounts = await asyncio.wait_for(client.list_accounts(), timeout=10.0)
                    status["accounts"] = [
                        {
                            "id": getattr(a, "account_id", str(a)),
                            "name": getattr(a, "account_name", getattr(a, "account_id", str(a))),
                            "fcm": getattr(a, "fcm_id", ""),
                        }
                        for a in (accounts or [])
                    ]
                except Exception as acc_exc:
                    logger.debug("rithmic[%s]: list_accounts error: %s", key, acc_exc)

                # Positions
                try:
                    positions = await asyncio.wait_for(client.list_positions(), timeout=10.0)
                    status["positions"] = [
                        {
                            "symbol": getattr(p, "symbol", ""),
                            "size": getattr(p, "size", getattr(p, "pos_size", 0)),
                            "avg_price": getattr(p, "avg_price", getattr(p, "open_price", 0.0)),
                            "open_pnl": getattr(p, "open_pnl", getattr(p, "unrealized_pnl", 0.0)),
                        }
                        for p in (positions or [])
                    ]
                except Exception as pos_exc:
                    logger.debug("rithmic[%s]: list_positions error: %s", key, pos_exc)

                # P&L
                try:
                    pnl = await asyncio.wait_for(client.get_pnl_info(), timeout=10.0)
                    if pnl:
                        status["pnl"] = {
                            "unrealized": getattr(pnl, "unrealized_pnl", getattr(pnl, "open_pnl", None)),
                            "realized": getattr(pnl, "realized_pnl", getattr(pnl, "closed_pnl", None)),
                            "total": getattr(pnl, "total_pnl", None),
                        }
                except Exception as pnl_exc:
                    logger.debug("rithmic[%s]: get_pnl_info error: %s", key, pnl_exc)

        except TimeoutError:
            status["error"] = "connection timed out (15 s) — check credentials and network"
        except Exception as exc:
            status["error"] = str(exc)[:200]
            logger.warning("rithmic[%s]: refresh error: %s", key, exc)
        finally:
            if client is not None:
                import contextlib

                with contextlib.suppress(Exception):
                    await asyncio.wait_for(client.disconnect(), timeout=5.0)

        _save_status(key, status)
        self._status[key] = status
        return status

    async def refresh_all(self) -> None:
        """Refresh all enabled accounts concurrently."""
        if not self._loaded:
            self.reload_configs()
        tasks = [self.refresh_account(k) for k, c in self._configs.items() if c.enabled]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def get_today_fills(self, account_key: str) -> list[dict]:
        """Open a short-lived Rithmic session and retrieve today's order/fill history.

        Maps each order to a normalised fill dict and caches the result in Redis
        under ``rithmic:fills:{account_key}:{today_date}`` with a 24 h TTL.

        Returns a list of fill dicts (may be empty if no fills or on error).
        """
        if not self._loaded:
            self.reload_configs()

        config = self._configs.get(account_key)
        if config is None:
            logger.warning("rithmic[%s]: get_today_fills — account not found", account_key)
            return []

        if not config.enabled:
            logger.debug("rithmic[%s]: get_today_fills — account disabled", account_key)
            return []

        username = config.get_username()
        password = config.get_password()
        if not username or not password:
            logger.warning("rithmic[%s]: get_today_fills — credentials not configured", account_key)
            return []

        try:
            from async_rithmic import RithmicClient  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("rithmic[%s]: async-rithmic not installed", account_key)
            return []

        gateway = _resolve_gateway(config.gateway)
        if gateway is None:
            logger.warning("rithmic[%s]: get_today_fills — unknown gateway: %s", account_key, config.gateway)
            return []

        fills: list[dict] = []
        client: Any = None
        try:
            async with self._lock:
                client = RithmicClient(  # type: ignore[call-arg]
                    user=username,
                    password=password,
                    system_name=config.system_name,
                    app_name=config.app_name,
                    app_version=config.app_version,
                    gateway=gateway,
                )
                await asyncio.wait_for(client.connect(), timeout=15.0)

                try:
                    orders = await asyncio.wait_for(client.show_order_history_summary(), timeout=20.0)
                    for order in orders or []:
                        fills.append(
                            {
                                "account_key": account_key,
                                "order_id": str(getattr(order, "order_id", "")),
                                "symbol": str(getattr(order, "symbol", "")),
                                "exchange": str(getattr(order, "exchange", "")),
                                "buy_sell": str(
                                    getattr(
                                        order,
                                        "buy_sell_type",
                                        getattr(order, "action", ""),
                                    )
                                ),
                                "qty": int(
                                    getattr(
                                        order,
                                        "qty",
                                        getattr(order, "quantity", 0),
                                    )
                                ),
                                "fill_price": float(
                                    getattr(
                                        order,
                                        "avg_fill_price",
                                        getattr(order, "fill_price", 0.0),
                                    )
                                ),
                                "fill_time": str(
                                    getattr(
                                        order,
                                        "update_time",
                                        getattr(order, "fill_time", ""),
                                    )
                                ),
                                "status": str(getattr(order, "status", "FILLED")),
                                "commission": float(getattr(order, "commission", 0.0)),
                            }
                        )
                    logger.info(
                        "rithmic[%s]: retrieved %d fill(s) from order history",
                        account_key,
                        len(fills),
                    )
                except Exception as hist_exc:
                    logger.warning(
                        "rithmic[%s]: show_order_history_summary error: %s",
                        account_key,
                        hist_exc,
                    )

        except TimeoutError:
            logger.warning("rithmic[%s]: get_today_fills — connection timed out", account_key)
        except Exception as exc:
            logger.warning("rithmic[%s]: get_today_fills — error: %s", account_key, exc)
        finally:
            if client is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(client.disconnect(), timeout=5.0)

        # Cache in Redis: rithmic:fills:{account_key}:{today_date}  TTL = 24 h
        try:
            from core.cache import cache_set

            today_date = datetime.now(tz=_EST).strftime("%Y-%m-%d")
            redis_key = f"rithmic:fills:{account_key}:{today_date}"
            cache_set(redis_key, json.dumps(fills, default=str).encode(), 86400)
        except Exception as cache_exc:
            logger.debug("rithmic[%s]: fills cache write failed (non-fatal): %s", account_key, cache_exc)

        return fills

    async def get_all_today_fills(self) -> list[dict]:
        """Retrieve today's fills for all enabled accounts and combine them.

        Calls ``get_today_fills`` concurrently for every enabled account and
        merges the results into a single flat list.
        """
        if not self._loaded:
            self.reload_configs()

        enabled_keys = [k for k, c in self._configs.items() if c.enabled]
        if not enabled_keys:
            return []

        results = await asyncio.gather(
            *[self.get_today_fills(k) for k in enabled_keys],
            return_exceptions=True,
        )

        combined: list[dict] = []
        for key, result in zip(enabled_keys, results, strict=False):
            if isinstance(result, Exception):
                logger.warning("rithmic[%s]: get_all_today_fills — error: %s", key, result)
            elif isinstance(result, list):
                combined.extend(result)

        logger.info(
            "rithmic: get_all_today_fills — total %d fill(s) across %d account(s)", len(combined), len(enabled_keys)
        )
        return combined

    async def eod_close_all_positions(
        self,
        *,
        dry_run: bool = False,
    ) -> list[dict[str, Any]]:
        """Cancel all working orders then flatten all open positions across every
        enabled account.

        This is the 16:00 ET hard-safety-net. It is intentionally separate from
        ``refresh_account`` so it can be called independently (scheduler, manual
        API call) without polluting the status cache.

        Sequence per account:
          1. ``cancel_all_orders(account_id=...)``   — kills every pending entry /
             stop / target on the account (template 346).
          2. Short asyncio.sleep(0.5) so the exchange has time to ack cancels.
          3. ``exit_position(account_id=...)``        — market-flattens whatever
             net position remains (template 3504, no symbol filter = flatten all).

        Args:
            dry_run: When *True* the method still connects and discovers accounts
                     but skips the cancel/exit calls.  Useful for staging checks.

        Returns:
            List of result dicts, one per account key, with keys:
                key, label, account_id, cancelled, flattened, error, dry_run.
        """
        if not self._loaded:
            self.reload_configs()

        results: list[dict[str, Any]] = []

        for key, config in self._configs.items():
            if not config.enabled:
                results.append({"key": key, "label": config.label, "skipped": "disabled"})
                continue

            username = config.get_username()
            password = config.get_password()
            if not username or not password:
                results.append(
                    {
                        "key": key,
                        "label": config.label,
                        "error": "credentials not configured",
                    }
                )
                continue

            result: dict[str, Any] = {
                "key": key,
                "label": config.label,
                "cancelled": False,
                "flattened": False,
                "error": "",
                "dry_run": dry_run,
                "timestamp": datetime.now(tz=_EST).isoformat(),
            }

            try:
                from async_rithmic import OrderPlacement, RithmicClient  # type: ignore[import-untyped]
            except ImportError:
                result["error"] = "async-rithmic not installed"
                results.append(result)
                continue

            gateway = _resolve_gateway(config.gateway)
            if gateway is None:
                result["error"] = f"unknown gateway: {config.gateway}"
                results.append(result)
                continue

            client: Any = None
            try:
                client = RithmicClient(
                    user=username,
                    password=password,
                    system_name=config.system_name,
                    app_name=config.app_name,
                    app_version=config.app_version,
                    url=gateway,
                    manual_or_auto=OrderPlacement.MANUAL,
                )
                await asyncio.wait_for(client.connect(), timeout=15.0)

                # Discover account IDs so we can target each one individually.
                account_ids: list[str] = []
                with contextlib.suppress(Exception):
                    accounts = await asyncio.wait_for(client.list_accounts(), timeout=10.0)
                    account_ids = [str(getattr(a, "account_id", None) or a) for a in (accounts or [])]

                # Fall back to config-level account_id if discovery fails.
                if not account_ids and hasattr(config, "account_id") and config.account_id:  # type: ignore[attr-defined]
                    account_ids = [config.account_id]  # type: ignore[attr-defined]

                result["account_ids"] = account_ids

                if not dry_run:
                    for account_id in account_ids:
                        # Step 1 — kill all working orders
                        try:
                            await asyncio.wait_for(
                                client.cancel_all_orders(account_id=account_id),
                                timeout=10.0,
                            )
                            result["cancelled"] = True
                        except Exception as exc:
                            logger.warning(
                                "rithmic[%s] cancel_all_orders(%s) failed: %s",
                                key,
                                account_id,
                                exc,
                            )

                    # Brief pause so exchange acks land before flatten
                    await asyncio.sleep(0.5)

                    for account_id in account_ids:
                        # Step 2 — flatten remaining net position at market
                        try:
                            await asyncio.wait_for(
                                client.exit_position(
                                    account_id=account_id,
                                    manual_or_auto=OrderPlacement.MANUAL,
                                ),
                                timeout=10.0,
                            )
                            result["flattened"] = True
                        except Exception as exc:
                            logger.warning(
                                "rithmic[%s] exit_position(%s) failed: %s",
                                key,
                                account_id,
                                exc,
                            )
                else:
                    logger.info(
                        "rithmic[%s] EOD dry-run — would cancel+flatten account_ids=%s",
                        key,
                        account_ids,
                    )

            except TimeoutError:
                result["error"] = "connection timed out (15 s)"
            except Exception as exc:
                result["error"] = str(exc)[:300]
                logger.error("rithmic[%s] EOD close error: %s", key, exc)
            finally:
                if client is not None:
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(client.disconnect(), timeout=5.0)

            logger.info(
                "rithmic[%s] EOD close: cancelled=%s flattened=%s dry_run=%s error=%r",
                key,
                result.get("cancelled"),
                result.get("flattened"),
                dry_run,
                result.get("error"),
            )
            results.append(result)

        return results


# ---------------------------------------------------------------------------
# Singleton manager
# ---------------------------------------------------------------------------

_manager: RithmicAccountManager | None = None


def get_manager() -> RithmicAccountManager:
    global _manager
    if _manager is None:
        _manager = RithmicAccountManager()
        _manager.reload_configs()
    return _manager


# ---------------------------------------------------------------------------
# Persistent stream manager (RITHMIC-STREAM-A)
# ---------------------------------------------------------------------------


class RithmicStreamManager:
    """Persistent Rithmic connection for live market data streaming.

    Manages long-lived connections to TICKER_PLANT (live ticks + time bars)
    and PNL_PLANT (real-time P&L). Unlike RithmicAccountManager which uses
    short-lived polling connections, this class maintains a persistent
    connection with automatic reconnection on failure.

    Gated by:
        RITHMIC_LIVE_DATA=1   — enables the streaming connection
        RITHMIC_DEBUG_LOGGING=1 — verbose connection logging

    Redis keys written:
        ticks:live:{symbol}            — rolling 300-tick window (list, LPUSH+LTRIM)
        rithmic:ticks:{symbol}         — legacy alias, same data (kept for back-compat)
        bars:live:{symbol}             — completed 1m bars (list, LPUSH+LTRIM, 500 bars)
        rithmic:l1:{symbol}            — best bid/ask/last (hash, 2s TTL)
        rithmic:connection:{plant}     — connection state per plant (hash, no TTL)
        rithmic:pnl:{account_key}      — real-time P&L per account (hash, no TTL)

    1-minute bar aggregation:
        Ticks are bucketed by floor(ts / 60).  When a new minute starts the
        completed bar is published to ``bars:live:{symbol}`` (Redis list,
        newest-first, capped at 500) and upserted into the ``historical_bars``
        Postgres table so the rolling dataset stays current without a separate
        backfill pass.
    """

    # Plant name constants — used for Redis state keys
    TICKER_PLANT = "TICKER_PLANT"
    PNL_PLANT = "PNL_PLANT"
    HISTORY_PLANT = "HISTORY_PLANT"
    ORDER_PLANT = "ORDER_PLANT"

    def __init__(self) -> None:
        self._client: Any = None
        self._connected: bool = False
        self._subscribed_symbols: set[str] = set()
        self._reconnect_task: asyncio.Task[None] | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._config: RithmicAccountConfig | None = None
        self._debug: bool = os.getenv("RITHMIC_DEBUG_LOGGING", "0") == "1"

        # 1-minute bar aggregation state, keyed by symbol
        # Each entry: {"minute": int, "open": float, "high": float,
        #              "low": float, "close": float, "volume": int}
        self._bar_state: dict[str, dict[str, Any]] = {}

        # L2 order book state, keyed by symbol
        # Each entry: {"bids": {price: size, ...}, "asks": {price: size, ...}}
        self._l2_state: dict[str, dict[str, dict[float, int]]] = {}

        # PNL_PLANT streaming state
        self._pnl_client: Any = None
        self._pnl_connected: bool = False
        self._pnl_task: asyncio.Task[None] | None = None

        # HISTORY_PLANT — historical bar retrieval
        self._history_client: Any = None
        self._history_connected: bool = False
        self._backfill_lock: asyncio.Lock = asyncio.Lock()
        self._active_backfills: set[str] = set()

        # ORDER_PLANT — order lifecycle tracking
        self._order_client: Any = None
        self._order_connected: bool = False
        self._order_task: asyncio.Task[None] | None = None
        self._order_states: dict[str, dict[str, Any]] = {}

        # Journal update throttle — update daily_journal from live P&L at most once per 60s
        self._last_journal_update: float = 0.0
        self._journal_update_interval: float = 60.0  # seconds between journal writes

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Redis connection state helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_plant_state(plant: str, state: str, *, gateway: str = "", error: str = "") -> None:
        """Write plant connection state to Redis ``rithmic:connection:{plant}``.

        Fields written:
            state    — "connecting" | "connected" | "disconnected" | "error"
            gateway  — gateway name (e.g. "Chicago")
            error    — last error message (empty on success)
            ts       — ISO timestamp of this state change
        """
        try:
            from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

            if not REDIS_AVAILABLE or _r is None:
                return

            _r.hset(
                f"rithmic:connection:{plant}",
                mapping={
                    "state": state,
                    "gateway": gateway,
                    "error": error,
                    "ts": datetime.now(tz=_EST).isoformat(),
                },
            )
        except Exception:
            pass  # non-fatal — connection state is informational

    @staticmethod
    def get_plant_states() -> dict[str, dict[str, str]]:
        """Read all known plant connection states from Redis.

        Returns a dict ``{plant_name: {state, gateway, error, ts}}``.
        Missing plants default to ``{"state": "unknown"}``.
        """
        plants = [
            RithmicStreamManager.TICKER_PLANT,
            RithmicStreamManager.PNL_PLANT,
            RithmicStreamManager.HISTORY_PLANT,
            RithmicStreamManager.ORDER_PLANT,
        ]
        result: dict[str, dict[str, str]] = {}
        try:
            from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

            if not REDIS_AVAILABLE or _r is None:
                return {p: {"state": "unknown"} for p in plants}

            for plant in plants:
                raw = _r.hgetall(f"rithmic:connection:{plant}")
                if raw:
                    result[plant] = {
                        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                        for k, v in raw.items()
                    }
                else:
                    result[plant] = {"state": "unknown"}
        except Exception:
            return {p: {"state": "unknown"} for p in plants}
        return result

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, config: RithmicAccountConfig) -> bool:
        """Connect to TICKER_PLANT.  Returns True on success.

        Uses exponential backoff on failure (max 5 retries, 2→4→8→16→32 s).
        The config is saved so that ``reconnect`` can re-use it later.
        """
        async with self._lock:
            self._config = config

        username = config.get_username()
        password = config.get_password()
        if not username or not password:
            logger.warning("rithmic-stream: credentials not configured — cannot start")
            return False

        max_retries = 5
        delay = 2.0

        self._set_plant_state(self.TICKER_PLANT, "connecting", gateway=config.gateway)

        for attempt in range(1, max_retries + 1):
            try:
                from async_rithmic import RithmicClient, SysInfraType  # type: ignore[import-untyped]

                gateway = _resolve_gateway(config.gateway)
                if gateway is None:
                    logger.error("rithmic-stream: unknown gateway %r", config.gateway)
                    self._set_plant_state(self.TICKER_PLANT, "error", error=f"unknown gateway: {config.gateway}")
                    return False

                if self._debug:
                    logger.debug(
                        "rithmic-stream: connecting (attempt %d/%d) user=%s gateway=%s",
                        attempt,
                        max_retries,
                        config.get_username(),
                        config.gateway,
                    )

                client = RithmicClient(
                    user=username,
                    password=password,
                    system_name=config.system_name,
                    app_name=config.app_name,
                    app_version=config.app_version,
                    url=gateway,
                )
                await asyncio.wait_for(
                    client.connect(infra_type=SysInfraType.TICKER_PLANT),
                    timeout=20.0,
                )

                async with self._lock:
                    self._client = client
                    self._connected = True

                # Register event callbacks on the client
                client.on_tick += self.on_tick
                client.on_order_book += self._on_order_book

                self._set_plant_state(self.TICKER_PLANT, "connected", gateway=config.gateway)
                logger.info(
                    "rithmic-stream: connected to TICKER_PLANT (gateway=%s user=%s)",
                    config.gateway,
                    config.get_username(),
                )
                return True

            except ImportError:
                logger.error("rithmic-stream: async-rithmic not installed — streaming unavailable")
                self._set_plant_state(self.TICKER_PLANT, "error", error="async-rithmic not installed")
                return False
            except TimeoutError:
                logger.warning("rithmic-stream: connect attempt %d timed out", attempt)
                self._set_plant_state(
                    self.TICKER_PLANT, "connecting", gateway=config.gateway, error=f"timeout on attempt {attempt}"
                )
            except Exception as exc:
                logger.warning("rithmic-stream: connect attempt %d failed: %s", attempt, exc)
                self._set_plant_state(self.TICKER_PLANT, "connecting", gateway=config.gateway, error=str(exc))

            if attempt < max_retries:
                if self._debug:
                    logger.debug("rithmic-stream: retrying in %.0f s", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 32.0)

        logger.error("rithmic-stream: exhausted %d connect attempts — giving up", max_retries)
        async with self._lock:
            self._connected = False
        self._set_plant_state(self.TICKER_PLANT, "disconnected", error=f"exhausted {max_retries} connect attempts")
        return False

    async def stop(self) -> None:
        """Disconnect gracefully and cancel any pending reconnect task."""
        # Cancel reconnect background task first
        if self._reconnect_task is not None and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None

        async with self._lock:
            client = self._client
            self._client = None
            self._connected = False

        self._set_plant_state(self.TICKER_PLANT, "disconnected")

        if client is not None:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5.0)
                logger.info("rithmic-stream: disconnected")
            except Exception as exc:
                logger.debug("rithmic-stream: disconnect error (non-fatal): %s", exc)

        # Also disconnect PNL_PLANT if connected
        if self._pnl_connected:
            await self.disconnect_pnl_plant()

        # Also disconnect HISTORY_PLANT if connected
        if self._history_connected:
            await self.disconnect_history_plant()

        # Also disconnect ORDER_PLANT if connected
        if self._order_connected:
            await self.disconnect_order_plant()

    # ------------------------------------------------------------------
    # HISTORY_PLANT — historical bar retrieval
    # ------------------------------------------------------------------

    async def connect_history_plant(self, config: RithmicAccountConfig) -> bool:
        """Connect to HISTORY_PLANT.  Returns True on success.

        Uses the same exponential backoff pattern as ``start()``
        (max 5 retries, 2→4→8→16→32 s).  Writes plant state to Redis
        via ``_set_plant_state``.
        """
        username = config.get_username()
        password = config.get_password()
        if not username or not password:
            logger.warning("rithmic-stream: credentials not configured — cannot connect HISTORY_PLANT")
            return False

        max_retries = 5
        delay = 2.0

        self._set_plant_state(self.HISTORY_PLANT, "connecting", gateway=config.gateway)

        for attempt in range(1, max_retries + 1):
            try:
                from async_rithmic import RithmicClient, SysInfraType  # type: ignore[import-untyped]

                gateway = _resolve_gateway(config.gateway)
                if gateway is None:
                    logger.error("rithmic-stream: unknown gateway %r", config.gateway)
                    self._set_plant_state(self.HISTORY_PLANT, "error", error=f"unknown gateway: {config.gateway}")
                    return False

                if self._debug:
                    logger.debug(
                        "rithmic-stream: HISTORY_PLANT connecting (attempt %d/%d) user=%s gateway=%s",
                        attempt,
                        max_retries,
                        config.get_username(),
                        config.gateway,
                    )

                client = RithmicClient(
                    user=username,
                    password=password,
                    system_name=config.system_name,
                    app_name=config.app_name,
                    app_version=config.app_version,
                    url=gateway,
                )
                await asyncio.wait_for(
                    client.connect(infra_type=SysInfraType.HISTORY_PLANT),
                    timeout=20.0,
                )

                self._history_client = client
                self._history_connected = True

                self._set_plant_state(self.HISTORY_PLANT, "connected", gateway=config.gateway)
                logger.info(
                    "rithmic-stream: connected to HISTORY_PLANT (gateway=%s user=%s)",
                    config.gateway,
                    config.get_username(),
                )
                return True

            except ImportError:
                logger.error("rithmic-stream: async-rithmic not installed — HISTORY_PLANT unavailable")
                self._set_plant_state(self.HISTORY_PLANT, "error", error="async-rithmic not installed")
                return False
            except TimeoutError:
                logger.warning("rithmic-stream: HISTORY_PLANT connect attempt %d timed out", attempt)
                self._set_plant_state(
                    self.HISTORY_PLANT, "connecting", gateway=config.gateway, error=f"timeout on attempt {attempt}"
                )
            except Exception as exc:
                logger.warning("rithmic-stream: HISTORY_PLANT connect attempt %d failed: %s", attempt, exc)
                self._set_plant_state(self.HISTORY_PLANT, "connecting", gateway=config.gateway, error=str(exc))

            if attempt < max_retries:
                if self._debug:
                    logger.debug("rithmic-stream: HISTORY_PLANT retrying in %.0f s", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 32.0)

        logger.error("rithmic-stream: HISTORY_PLANT exhausted %d connect attempts — giving up", max_retries)
        self._history_connected = False
        self._set_plant_state(self.HISTORY_PLANT, "disconnected", error=f"exhausted {max_retries} connect attempts")
        return False

    async def disconnect_history_plant(self) -> None:
        """Gracefully disconnect the HISTORY_PLANT client.

        Cancels any active backfills, disconnects the client, and writes
        "disconnected" state to Redis.
        """
        # Clear active backfills so any running backfill_bars sees it
        self._active_backfills.clear()

        client = self._history_client
        self._history_client = None
        self._history_connected = False

        self._set_plant_state(self.HISTORY_PLANT, "disconnected")

        if client is not None:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5.0)
                logger.info("rithmic-stream: HISTORY_PLANT disconnected")
            except Exception as exc:
                logger.debug("rithmic-stream: HISTORY_PLANT disconnect error (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # PNL_PLANT — real-time P&L streaming
    # ------------------------------------------------------------------

    async def connect_pnl_plant(self, config: RithmicAccountConfig) -> bool:
        """Connect to PNL_PLANT for real-time P&L streaming.  Returns True on success.

        Uses the same exponential backoff pattern as ``start()``
        (max 5 retries, 2→4→8→16→32 s).  Creates a separate
        ``RithmicClient`` instance dedicated to the PNL infrastructure.
        On success, spawns a background ``_pnl_poll_loop`` task that
        polls P&L every 5 seconds and publishes to Redis.
        """
        username = config.get_username()
        password = config.get_password()
        if not username or not password:
            logger.warning("rithmic-stream: credentials not configured — cannot connect PNL_PLANT")
            return False

        max_retries = 5
        delay = 2.0

        self._set_plant_state(self.PNL_PLANT, "connecting", gateway=config.gateway)

        for attempt in range(1, max_retries + 1):
            try:
                from async_rithmic import RithmicClient, SysInfraType  # type: ignore[import-untyped]

                gateway = _resolve_gateway(config.gateway)
                if gateway is None:
                    logger.error("rithmic-stream: unknown gateway %r", config.gateway)
                    self._set_plant_state(self.PNL_PLANT, "error", error=f"unknown gateway: {config.gateway}")
                    return False

                if self._debug:
                    logger.debug(
                        "rithmic-stream: PNL_PLANT connecting (attempt %d/%d) user=%s gateway=%s",
                        attempt,
                        max_retries,
                        config.get_username(),
                        config.gateway,
                    )

                client = RithmicClient(
                    user=username,
                    password=password,
                    system_name=config.system_name,
                    app_name=config.app_name,
                    app_version=config.app_version,
                    url=gateway,
                )
                await asyncio.wait_for(
                    client.connect(infra_type=SysInfraType.PNL_PLANT),
                    timeout=20.0,
                )

                self._pnl_client = client
                self._pnl_connected = True

                # Register PNL event callbacks
                client.on_instrument_pnl_update += self._on_instrument_pnl_update
                client.on_account_pnl_update += self._on_account_pnl_update

                # Subscribe to real-time PNL pushes
                try:
                    await client.subscribe_to_pnl_updates()
                    logger.info("rithmic-stream: subscribed to PNL updates")
                except Exception as sub_exc:
                    logger.warning("rithmic-stream: PNL subscription failed (will fall back to polling): %s", sub_exc)

                self._set_plant_state(self.PNL_PLANT, "connected", gateway=config.gateway)
                logger.info(
                    "rithmic-stream: connected to PNL_PLANT (gateway=%s user=%s)",
                    config.gateway,
                    config.get_username(),
                )

                # Spawn background polling task
                self._pnl_task = asyncio.get_event_loop().create_task(self._pnl_poll_loop())
                return True

            except ImportError:
                logger.error("rithmic-stream: async-rithmic not installed — PNL_PLANT unavailable")
                self._set_plant_state(self.PNL_PLANT, "error", error="async-rithmic not installed")
                return False
            except TimeoutError:
                logger.warning("rithmic-stream: PNL_PLANT connect attempt %d timed out", attempt)
                self._set_plant_state(
                    self.PNL_PLANT, "connecting", gateway=config.gateway, error=f"timeout on attempt {attempt}"
                )
            except Exception as exc:
                logger.warning("rithmic-stream: PNL_PLANT connect attempt %d failed: %s", attempt, exc)
                self._set_plant_state(self.PNL_PLANT, "connecting", gateway=config.gateway, error=str(exc))

            if attempt < max_retries:
                if self._debug:
                    logger.debug("rithmic-stream: PNL_PLANT retrying in %.0f s", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 32.0)

        logger.error("rithmic-stream: PNL_PLANT exhausted %d connect attempts — giving up", max_retries)
        self._pnl_connected = False
        self._set_plant_state(self.PNL_PLANT, "disconnected", error=f"exhausted {max_retries} connect attempts")
        return False

    async def disconnect_pnl_plant(self) -> None:
        """Gracefully disconnect the PNL_PLANT client and cancel the poll loop.

        Cancels ``_pnl_task``, disconnects the client, and writes
        "disconnected" state to Redis.
        """
        # Cancel the poll loop task
        if self._pnl_task is not None and not self._pnl_task.done():
            self._pnl_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pnl_task
            self._pnl_task = None

        client = self._pnl_client
        self._pnl_client = None
        self._pnl_connected = False

        self._set_plant_state(self.PNL_PLANT, "disconnected")

        if client is not None:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5.0)
                logger.info("rithmic-stream: PNL_PLANT disconnected")
            except Exception as exc:
                logger.debug("rithmic-stream: PNL_PLANT disconnect error (non-fatal): %s", exc)

    async def _pnl_poll_loop(self) -> None:
        """Background task: poll P&L from PNL_PLANT every 5 seconds.

        Publishes to Redis:
          - ``pnl:live:{account_id}`` — hash with unrealized, realized, total, ts
          - ``pnl:updates``           — pub/sub channel for SSE consumers

        Also feeds the circuit breaker via ``_feed_circuit_breaker`` when
        the realized P&L changes (indicating a trade has closed).
        """
        logger.info("rithmic-stream: PNL poll loop started")
        while self._pnl_connected:
            try:
                client = self._pnl_client
                if client is None:
                    break

                pnl = await asyncio.wait_for(client.get_pnl_info(), timeout=10.0)
                if pnl is None:
                    await asyncio.sleep(5)
                    continue

                unrealized = getattr(pnl, "unrealized_pnl", None) or getattr(pnl, "open_pnl", None)
                realized = getattr(pnl, "realized_pnl", None) or getattr(pnl, "closed_pnl", None)
                total = getattr(pnl, "total_pnl", None)

                # Resolve account_id — use config key or fall back to pnl object attr
                account_id = getattr(pnl, "account_id", None)
                if account_id is None and self._config is not None:
                    account_id = self._config.key
                account_id = str(account_id or "default")

                pnl_data: dict[str, Any] = {
                    "unrealized": float(unrealized) if unrealized is not None else 0.0,
                    "realized": float(realized) if realized is not None else 0.0,
                    "total": float(total) if total is not None else 0.0,
                    "ts": datetime.now(tz=_EST).isoformat(),
                }

                try:
                    from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

                    if REDIS_AVAILABLE and _r is not None:
                        # Write P&L snapshot to hash
                        _r.hset(
                            f"pnl:live:{account_id}",
                            mapping={
                                "unrealized": str(pnl_data["unrealized"]),
                                "realized": str(pnl_data["realized"]),
                                "total": str(pnl_data["total"]),
                                "ts": pnl_data["ts"],
                            },
                        )

                        # Publish to pub/sub channel for SSE consumers
                        pub_payload = json.dumps({"account_id": account_id, **pnl_data})
                        _r.publish("pnl:updates", pub_payload)

                except Exception as redis_exc:
                    logger.debug("rithmic-stream: PNL redis publish error: %s", redis_exc)

                # Feed the circuit breaker with realized P&L deltas
                self._feed_circuit_breaker(pnl_data)

                # Update daily journal with live P&L (throttled)
                self._update_journal_from_pnl(pnl_data, account_id)

                if self._debug:
                    logger.debug(
                        "rithmic-stream: PNL poll — unrealized=%.2f realized=%.2f total=%.2f",
                        pnl_data["unrealized"],
                        pnl_data["realized"],
                        pnl_data["total"],
                    )

            except asyncio.CancelledError:
                logger.debug("rithmic-stream: PNL poll loop cancelled")
                raise
            except Exception as exc:
                logger.warning("rithmic-stream: PNL poll error (will retry): %s", exc)

            await asyncio.sleep(5)

        logger.info("rithmic-stream: PNL poll loop stopped")

    async def _on_instrument_pnl_update(self, data: Any) -> None:
        """Callback for real-time instrument PNL updates from PNL_PLANT.

        Writes position data to Redis for immediate consumption by
        the Position Intelligence Engine.
        """
        try:
            from google.protobuf.json_format import MessageToDict  # type: ignore[import-untyped]

            d = MessageToDict(data, preserving_proto_field_name=True, use_integers_for_enums=True)

            account_id = d.get("account_id", "")
            if not account_id and self._config is not None:
                account_id = self._config.key

            symbol = d.get("symbol", "")
            if not symbol:
                return

            position_data = {
                "symbol": symbol,
                "size": d.get("quantity", d.get("buy_qty", 0)),
                "avg_price": d.get("avg_open_fill_price", d.get("open_price", 0.0)),
                "open_pnl": d.get("open_pnl", 0.0),
                "closed_pnl": d.get("closed_pnl", 0.0),
                "ts": datetime.now(tz=_EST).isoformat(),
            }

            try:
                from core.cache import REDIS_AVAILABLE, _r

                if REDIS_AVAILABLE and _r is not None:
                    key = f"rithmic:position:{account_id}:{symbol}"
                    _r.hset(key, mapping={k: str(v) for k, v in position_data.items()})
                    _r.expire(key, 30)
                    _r.publish(
                        "pnl:updates", json.dumps({"type": "instrument", "account_id": account_id, **position_data})
                    )
            except Exception as redis_exc:
                logger.debug("rithmic-stream: instrument PNL redis write error: %s", redis_exc)

            if self._debug:
                logger.debug(
                    "rithmic-stream: instrument PNL update %s %s pnl=%.2f",
                    account_id,
                    symbol,
                    position_data["open_pnl"],
                )

        except Exception as exc:
            logger.debug("rithmic-stream: _on_instrument_pnl_update error: %s", exc)

    async def _on_account_pnl_update(self, data: Any) -> None:
        """Callback for real-time account PNL updates from PNL_PLANT.

        Writes aggregate account PNL to Redis, complementing the poll loop.
        """
        try:
            from google.protobuf.json_format import MessageToDict  # type: ignore[import-untyped]

            d = MessageToDict(data, preserving_proto_field_name=True, use_integers_for_enums=True)

            account_id = d.get("account_id", "")
            if not account_id and self._config is not None:
                account_id = self._config.key
            account_id = str(account_id or "default")

            pnl_data = {
                "unrealized": str(d.get("open_pnl", d.get("unrealized_pnl", 0.0))),
                "realized": str(d.get("closed_pnl", d.get("realized_pnl", 0.0))),
                "total": str(d.get("total_pnl", 0.0)),
                "ts": datetime.now(tz=_EST).isoformat(),
            }

            try:
                from core.cache import REDIS_AVAILABLE, _r

                if REDIS_AVAILABLE and _r is not None:
                    _r.hset(f"pnl:live:{account_id}", mapping=pnl_data)
                    _r.publish("pnl:updates", json.dumps({"type": "account", "account_id": account_id, **pnl_data}))
            except Exception as redis_exc:
                logger.debug("rithmic-stream: account PNL redis write error: %s", redis_exc)

            if self._debug:
                logger.debug("rithmic-stream: account PNL update %s total=%s", account_id, pnl_data["total"])

        except Exception as exc:
            logger.debug("rithmic-stream: _on_account_pnl_update error: %s", exc)

    def _update_journal_from_pnl(self, pnl_data: dict[str, Any], account_id: str) -> None:
        """Update the daily_journal table with live P&L from the PNL_PLANT stream.

        Throttled to at most once per ``_journal_update_interval`` seconds
        (default 60 s) to avoid excessive DB writes from the 5 s poll loop.

        Uses the account's ``account_size`` from config (default 150,000).
        Writes realized P&L as ``net_pnl`` and total P&L (realized + unrealized)
        as ``gross_pnl`` so the journal reflects both closed and open position
        value.  The ``notes`` field is tagged to distinguish live-stream updates
        from fill-based sync updates.
        """
        import time as _time

        now = _time.monotonic()
        if (now - self._last_journal_update) < self._journal_update_interval:
            return

        try:
            from core.models import save_daily_journal

            today = datetime.now(tz=_EST).strftime("%Y-%m-%d")

            realized = pnl_data.get("realized", 0.0)
            total = pnl_data.get("total", 0.0)

            # Skip if there's nothing to record yet
            if realized == 0.0 and total == 0.0:
                self._last_journal_update = now
                return

            # Resolve account_size from config, default 150k
            account_size = 150_000
            if self._config is not None:
                account_size = getattr(self._config, "account_size", 150_000) or 150_000

            # gross_pnl = total (realized + unrealized), net_pnl = realized only
            # This gives the journal a view of both closed P&L and open-position
            # mark-to-market value.
            save_daily_journal(
                trade_date=today,
                account_size=account_size,
                gross_pnl=total,
                net_pnl=realized,
                num_contracts=0,  # not available from PNL_PLANT aggregate
                instruments="",  # not available from PNL_PLANT aggregate
                notes=f"live P&L stream ({account_id})",
            )

            self._last_journal_update = now

            if self._debug:
                logger.debug(
                    "rithmic-stream: journal updated from live P&L — date=%s gross=%.2f net=%.2f acct=%s",
                    today,
                    total,
                    realized,
                    account_id,
                )

        except Exception as exc:
            logger.debug("rithmic-stream: _update_journal_from_pnl error (non-fatal): %s", exc)
            # Still update timestamp to avoid retrying immediately on persistent errors
            self._last_journal_update = now

    @staticmethod
    def _feed_circuit_breaker(pnl_data: dict[str, Any]) -> None:
        """Detect realized P&L changes and write a delta to Redis for the circuit breaker.

        Compares the current realized value against the previously stored
        ``pnl:live:last_reported_realized``.  When the realized value
        changes (a trade has closed), writes a JSON payload to
        ``pnl:circuit_breaker_feed`` so the execution gate can pick it up
        without tight coupling between the stream manager and the
        execution gate module.
        """
        try:
            from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

            if not REDIS_AVAILABLE or _r is None:
                return

            new_realized = float(pnl_data.get("realized", 0.0))

            # Read previous realized value
            prev_raw = _r.get("pnl:live:last_reported_realized")
            prev_realized = float(prev_raw) if prev_raw is not None else None

            if prev_realized is not None:
                delta = new_realized - prev_realized
                if delta != 0.0:
                    feed_payload = json.dumps(
                        {
                            "pnl_delta": delta,
                            "is_loss": delta < 0,
                            "ts": datetime.now(tz=_EST).isoformat(),
                        }
                    )
                    _r.set("pnl:circuit_breaker_feed", feed_payload)
                    logger.info(
                        "rithmic-stream: circuit breaker feed — delta=%.2f is_loss=%s",
                        delta,
                        delta < 0,
                    )

            # Always store the latest realized value
            _r.set("pnl:live:last_reported_realized", str(new_realized))

        except Exception as exc:
            logger.debug("rithmic-stream: _feed_circuit_breaker error: %s", exc)

    @property
    def is_pnl_connected(self) -> bool:
        """Return True when the PNL_PLANT client is connected."""
        return self._pnl_connected

    # ------------------------------------------------------------------
    # ORDER_PLANT — order lifecycle tracking
    # ------------------------------------------------------------------

    async def connect_order_plant(self, config: RithmicAccountConfig) -> bool:
        """Connect to ORDER_PLANT for real-time order lifecycle tracking.

        Uses the same exponential backoff pattern as ``connect_pnl_plant()``
        (max 5 retries, 2→4→8→16→32 s).  Creates a separate
        ``RithmicClient`` instance dedicated to the ORDER infrastructure.
        On success, spawns a background ``_order_event_loop`` task that
        listens for order events and publishes state changes to Redis.
        """
        username = config.get_username()
        password = config.get_password()
        if not username or not password:
            logger.warning("rithmic-stream: credentials not configured — cannot connect ORDER_PLANT")
            return False

        max_retries = 5
        delay = 2.0

        self._set_plant_state(self.ORDER_PLANT, "connecting", gateway=config.gateway)

        for attempt in range(1, max_retries + 1):
            try:
                from async_rithmic import RithmicClient, SysInfraType  # type: ignore[import-untyped]

                gateway = _resolve_gateway(config.gateway)
                if gateway is None:
                    logger.error("rithmic-stream: unknown gateway %r", config.gateway)
                    self._set_plant_state(self.ORDER_PLANT, "error", error=f"unknown gateway: {config.gateway}")
                    return False

                if self._debug:
                    logger.debug(
                        "rithmic-stream: ORDER_PLANT connecting (attempt %d/%d) user=%s gateway=%s",
                        attempt,
                        max_retries,
                        config.get_username(),
                        config.gateway,
                    )

                client = RithmicClient(
                    user=username,
                    password=password,
                    system_name=config.system_name,
                    app_name=config.app_name,
                    app_version=config.app_version,
                    url=gateway,
                )
                await asyncio.wait_for(
                    client.connect(infra_type=SysInfraType.ORDER_PLANT),
                    timeout=20.0,
                )

                self._order_client = client
                self._order_connected = True

                self._set_plant_state(self.ORDER_PLANT, "connected", gateway=config.gateway)
                logger.info(
                    "rithmic-stream: connected to ORDER_PLANT (gateway=%s user=%s)",
                    config.gateway,
                    config.get_username(),
                )

                # Spawn background event loop task
                self._order_task = asyncio.get_event_loop().create_task(self._order_event_loop())
                return True

            except ImportError:
                logger.error("rithmic-stream: async-rithmic not installed — ORDER_PLANT unavailable")
                self._set_plant_state(self.ORDER_PLANT, "error", error="async-rithmic not installed")
                return False
            except TimeoutError:
                logger.warning("rithmic-stream: ORDER_PLANT connect attempt %d timed out", attempt)
                self._set_plant_state(
                    self.ORDER_PLANT, "connecting", gateway=config.gateway, error=f"timeout on attempt {attempt}"
                )
            except Exception as exc:
                logger.warning("rithmic-stream: ORDER_PLANT connect attempt %d failed: %s", attempt, exc)
                self._set_plant_state(self.ORDER_PLANT, "connecting", gateway=config.gateway, error=str(exc))

            if attempt < max_retries:
                if self._debug:
                    logger.debug("rithmic-stream: ORDER_PLANT retrying in %.0f s", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 32.0)

        logger.error("rithmic-stream: ORDER_PLANT exhausted %d connect attempts — giving up", max_retries)
        self._order_connected = False
        self._set_plant_state(self.ORDER_PLANT, "disconnected", error=f"exhausted {max_retries} connect attempts")
        return False

    async def disconnect_order_plant(self) -> None:
        """Gracefully disconnect the ORDER_PLANT client and cancel the event loop.

        Cancels ``_order_task``, disconnects the client, and writes
        "disconnected" state to Redis.
        """
        # Cancel the event loop task
        if self._order_task is not None and not self._order_task.done():
            self._order_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._order_task
            self._order_task = None

        client = self._order_client
        self._order_client = None
        self._order_connected = False

        self._set_plant_state(self.ORDER_PLANT, "disconnected")

        if client is not None:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5.0)
                logger.info("rithmic-stream: ORDER_PLANT disconnected")
            except Exception as exc:
                logger.debug("rithmic-stream: ORDER_PLANT disconnect error (non-fatal): %s", exc)

    async def _order_event_loop(self) -> None:
        """Background task: listen for order events from ORDER_PLANT.

        Tries ``get_order_events()`` or ``stream_orders()`` for a streaming
        interface first.  Falls back to polling ``list_orders()`` every 3 s
        if neither streaming method is available on the client.

        For each order event, delegates to ``_process_order_event(event)``.
        """
        logger.info("rithmic-stream: ORDER event loop started")

        while self._order_connected:
            try:
                client = self._order_client
                if client is None:
                    break

                # Try streaming interface first
                stream_fn = getattr(client, "get_order_events", None) or getattr(client, "stream_orders", None)

                if stream_fn is not None:
                    # Streaming mode — async iterator
                    try:
                        async for event in stream_fn():
                            if not self._order_connected:
                                break
                            await self._process_order_event(event)
                    except (StopAsyncIteration, GeneratorExit):
                        pass
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.warning("rithmic-stream: ORDER stream error (will retry): %s", exc)
                        await asyncio.sleep(3)
                else:
                    # Fallback: poll list_orders() every 3 seconds
                    list_fn = getattr(client, "list_orders", None)
                    if list_fn is not None:
                        try:
                            orders = await asyncio.wait_for(list_fn(), timeout=10.0)
                            if orders:
                                for event in orders:
                                    await self._process_order_event(event)
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            logger.warning("rithmic-stream: ORDER poll error (will retry): %s", exc)
                    else:
                        logger.debug("rithmic-stream: ORDER_PLANT client has no streaming or polling method — sleeping")

                    await asyncio.sleep(3)

            except asyncio.CancelledError:
                logger.debug("rithmic-stream: ORDER event loop cancelled")
                raise
            except Exception as exc:
                logger.warning("rithmic-stream: ORDER event loop error (will retry): %s", exc)
                await asyncio.sleep(3)

        logger.info("rithmic-stream: ORDER event loop stopped")

    async def _process_order_event(self, event: Any) -> None:
        """Process a single order event from the ORDER_PLANT.

        Extracts order fields defensively via ``getattr``, updates in-memory
        ``_order_states``, writes to a Redis hash, and publishes to the
        ``dashboard:order_event`` pub/sub channel for SSE consumers.
        """
        order_id = str(getattr(event, "order_id", None) or getattr(event, "id", None) or "unknown")
        new_status = str(
            getattr(event, "status", None)
            or getattr(event, "order_status", None)
            or getattr(event, "state", None)
            or "unknown"
        ).lower()
        fill_price = getattr(event, "fill_price", None) or getattr(event, "avg_fill_price", None)
        fill_qty = getattr(event, "fill_qty", None) or getattr(event, "filled_qty", None)
        symbol = str(getattr(event, "symbol", None) or getattr(event, "security_code", None) or "")
        ts = str(
            getattr(event, "timestamp", None)
            or getattr(event, "update_time", None)
            or datetime.now(tz=_EST).isoformat()
        )

        # Determine old status for transition logging
        old_state = self._order_states.get(order_id, {})
        old_status = old_state.get("status", "unknown")

        # Build new state dict
        state: dict[str, Any] = {
            "order_id": order_id,
            "status": new_status,
            "fill_price": float(fill_price) if fill_price is not None else None,
            "fill_qty": int(fill_qty) if fill_qty is not None else None,
            "symbol": symbol,
            "ts": ts,
        }

        # Update in-memory state
        self._order_states[order_id] = state

        # Log transition
        if old_status != new_status:
            logger.info("order %s: %s → %s", order_id, old_status, new_status)

        # Write to Redis
        try:
            from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

            if REDIS_AVAILABLE and _r is not None:
                # Persist order state hash
                redis_mapping: dict[str, str] = {
                    "order_id": order_id,
                    "status": new_status,
                    "fill_price": str(fill_price) if fill_price is not None else "",
                    "fill_qty": str(fill_qty) if fill_qty is not None else "",
                    "symbol": symbol,
                    "ts": ts,
                }
                _r.hset(f"rithmic:order:{order_id}", mapping=redis_mapping)

                # Publish for SSE consumers (dashboard:* psubscribe picks this up)
                pub_payload = json.dumps(state, default=str)
                _r.publish("dashboard:order_event", pub_payload)

        except Exception as redis_exc:
            logger.debug("rithmic-stream: ORDER redis publish error (non-fatal): %s", redis_exc)

    @property
    def is_order_connected(self) -> bool:
        """Return True when the ORDER_PLANT client is connected."""
        return self._order_connected

    async def backfill_bars(
        self,
        symbol: str,
        days_back: int = 365,
        interval: str = "1m",
    ) -> dict[str, Any]:
        """Fetch historical bars for *symbol* from HISTORY_PLANT and write to Postgres.

        Acquires ``_backfill_lock`` to check/update ``_active_backfills``.
        Returns early if the symbol is already being backfilled.

        Returns ``{"symbol": ..., "bars_written": ..., "error": ""}``.
        """
        symbol = symbol.upper()

        if not self._history_connected or self._history_client is None:
            return {"symbol": symbol, "bars_written": 0, "error": "HISTORY_PLANT not connected"}

        # Guard against duplicate concurrent backfills for the same symbol
        async with self._backfill_lock:
            if symbol in self._active_backfills:
                logger.info("rithmic-stream: backfill already in progress for %s — skipping", symbol)
                return {"symbol": symbol, "bars_written": 0, "error": "backfill already in progress"}
            self._active_backfills.add(symbol)

        bars_written = 0
        error = ""
        try:
            from datetime import timedelta

            end_time = datetime.now(tz=_EST)
            start_time = end_time - timedelta(days=days_back)

            # Defensively resolve the API method — the exact name varies across
            # async_rithmic versions (get_time_bars, replay_time_bars, etc.)
            get_bars_fn = getattr(self._history_client, "get_time_bars", None)
            if get_bars_fn is None:
                get_bars_fn = getattr(self._history_client, "replay_time_bars", None)
            if get_bars_fn is None:
                logger.warning("rithmic-stream: HISTORY_PLANT client has no get_time_bars or replay_time_bars method")
                return {
                    "symbol": symbol,
                    "bars_written": 0,
                    "error": "history client missing time-bar retrieval method",
                }

            logger.info(
                "rithmic-stream: starting backfill for %s (%d days back, interval=%s)",
                symbol,
                days_back,
                interval,
            )

            try:
                bars = await asyncio.wait_for(
                    get_bars_fn(
                        symbol=symbol,
                        start_time=start_time,
                        end_time=end_time,
                    ),
                    timeout=300.0,  # 5 min timeout for large requests
                )
            except Exception as fetch_exc:
                logger.warning("rithmic-stream: backfill fetch error for %s: %s", symbol, fetch_exc)
                return {"symbol": symbol, "bars_written": 0, "error": str(fetch_exc)[:300]}

            if not bars:
                logger.info("rithmic-stream: backfill for %s returned no bars", symbol)
                return {"symbol": symbol, "bars_written": 0, "error": ""}

            # Write bars to Postgres in chunks, with rate-limiting
            chunk_size = 100
            bar_list = list(bars) if not isinstance(bars, list) else bars

            for i, bar_data in enumerate(bar_list):
                # Check if we've been cancelled (disconnect_history_plant clears active set)
                if symbol not in self._active_backfills:
                    logger.info("rithmic-stream: backfill for %s cancelled", symbol)
                    error = "cancelled"
                    break

                try:
                    # Normalize bar data from the Rithmic response
                    bar_dict: dict[str, Any] = {
                        "symbol": symbol,
                        "ts": int(
                            getattr(bar_data, "timestamp", None)
                            or getattr(bar_data, "bar_end_time", None)
                            or getattr(bar_data, "ssboe", 0)
                            or 0
                        ),
                        "open": float(getattr(bar_data, "open", getattr(bar_data, "open_price", 0.0))),
                        "high": float(getattr(bar_data, "high", getattr(bar_data, "high_price", 0.0))),
                        "low": float(getattr(bar_data, "low", getattr(bar_data, "low_price", 0.0))),
                        "close": float(getattr(bar_data, "close", getattr(bar_data, "close_price", 0.0))),
                        "volume": int(getattr(bar_data, "volume", 0)),
                    }

                    # Write synchronously via thread pool (same as on_tick)
                    await asyncio.to_thread(self._write_bar_to_postgres, bar_dict)
                    bars_written += 1

                except Exception as bar_exc:
                    if self._debug:
                        logger.debug(
                            "rithmic-stream: backfill bar write error for %s: %s",
                            symbol,
                            bar_exc,
                        )

                # Rate-limit: sleep between chunks to respect Rithmic limits
                if (i + 1) % chunk_size == 0:
                    await asyncio.sleep(0.5)

            logger.info(
                "rithmic-stream: backfill complete for %s — %d bars written",
                symbol,
                bars_written,
            )

        except Exception as exc:
            error = str(exc)[:300]
            logger.error("rithmic-stream: backfill error for %s: %s", symbol, exc)
        finally:
            # Always remove from active set
            async with self._backfill_lock:
                self._active_backfills.discard(symbol)

        return {"symbol": symbol, "bars_written": bars_written, "error": error}

    async def backfill_all(
        self,
        symbols: list[str],
        days_back: int = 365,
    ) -> list[dict[str, Any]]:
        """Batch-backfill multiple symbols sequentially.

        Iterates symbols one at a time, calling ``backfill_bars()`` for each.
        Returns a list of result dicts.
        """
        results: list[dict[str, Any]] = []
        for symbol in symbols:
            result = await self.backfill_bars(symbol, days_back=days_back)
            results.append(result)
        return results

    @property
    def is_history_connected(self) -> bool:
        """Return True when the HISTORY_PLANT client is connected."""
        return self._history_connected

    # ------------------------------------------------------------------
    # Symbol subscription
    # ------------------------------------------------------------------

    async def subscribe_symbols(self, symbols: list[str]) -> None:
        """Subscribe to tick + L1 + order book data for each symbol.

        Calls ``client.subscribe_to_market_data(symbol, exchange, data_type)``
        and ``client.subscribe_to_market_data(symbol, exchange, DataType.ORDER_BOOK)``
        from the async_rithmic API.  Successfully subscribed symbols are stored
        in ``_subscribed_symbols`` so they can be re-subscribed on reconnect.
        """
        async with self._lock:
            client = self._client
            connected = self._connected

        if not connected or client is None:
            logger.warning("rithmic-stream: cannot subscribe — not connected")
            return

        try:
            from async_rithmic import DataType  # type: ignore[import-untyped]
        except ImportError:
            logger.error("rithmic-stream: cannot import DataType from async_rithmic")
            return

        for symbol in symbols:
            exchange = _resolve_exchange(symbol)
            try:
                # Subscribe to L1: last trade + best bid/offer
                data_type = DataType.LAST_TRADE | DataType.BBO
                await asyncio.wait_for(
                    client.subscribe_to_market_data(symbol, exchange, data_type),
                    timeout=10.0,
                )
                # Also subscribe to order book (L2) for DOM display
                await asyncio.wait_for(
                    client.subscribe_to_market_data(symbol, exchange, DataType.ORDER_BOOK),
                    timeout=10.0,
                )
                async with self._lock:
                    self._subscribed_symbols.add(symbol)
                if self._debug:
                    logger.debug("rithmic-stream: subscribed to %s on %s (L1+L2)", symbol, exchange)
            except Exception as exc:
                logger.warning("rithmic-stream: subscribe(%s) failed: %s", symbol, exc)

    # ------------------------------------------------------------------
    # Tick callback
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 1-minute bar aggregation helpers
    # ------------------------------------------------------------------

    def _update_bar(self, symbol: str, price: float, volume: int, ts_epoch: int) -> dict[str, Any] | None:
        """Update the in-memory 1m bar for *symbol* with a new trade tick.

        Returns the *completed* bar dict when the minute rolls over, or
        ``None`` when the current bar is still open.

        A bar dict has keys: symbol, ts (ISO minute string), open, high,
        low, close, volume.
        """
        minute = ts_epoch // 60  # floor to minute boundary

        state = self._bar_state.get(symbol)
        if state is None:
            # First tick for this symbol — open a new bar
            self._bar_state[symbol] = {
                "minute": minute,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }
            return None

        if minute == state["minute"]:
            # Same minute — update OHLCV
            state["high"] = max(state["high"], price)
            state["low"] = min(state["low"], price)
            state["close"] = price
            state["volume"] += volume
            return None

        # Minute rolled — emit the completed bar and open a new one
        bar_ts = datetime.fromtimestamp(state["minute"] * 60, tz=_EST)
        completed: dict[str, Any] = {
            "symbol": symbol,
            "ts": bar_ts.isoformat(),
            "open": state["open"],
            "high": state["high"],
            "low": state["low"],
            "close": state["close"],
            "volume": state["volume"],
        }
        self._bar_state[symbol] = {
            "minute": minute,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
        }
        return completed

    @staticmethod
    def _publish_bar_to_redis(bar: dict[str, Any], r: Any) -> None:
        """Push a completed 1m bar to ``bars:live:{symbol}`` (newest-first, 500 cap)."""
        key = f"bars:live:{bar['symbol']}"
        r.lpush(key, json.dumps(bar))
        r.ltrim(key, 0, 499)

    @staticmethod
    def _write_bar_to_postgres(bar: dict[str, Any]) -> None:
        """Upsert a completed 1m bar into the ``historical_bars`` table.

        Uses the same INSERT … ON CONFLICT DO NOTHING pattern as the
        existing backfill pipeline, so duplicate bars from reconnects are
        silently ignored.

        Runs synchronously — call via ``asyncio.to_thread`` if needed.
        """
        try:
            from services.engine.backfill import _get_conn, _is_postgres  # type: ignore[import-unresolved]

            conn = _get_conn()
            try:
                ph = "%s" if _is_postgres() else "?"
                if _is_postgres():
                    sql = (
                        f"INSERT INTO historical_bars "
                        f"(symbol, timestamp, open, high, low, close, volume, interval) "
                        f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph}) "
                        f"ON CONFLICT (symbol, timestamp, interval) DO NOTHING"
                    )
                else:
                    sql = (
                        f"INSERT OR IGNORE INTO historical_bars "
                        f"(symbol, timestamp, open, high, low, close, volume, interval) "
                        f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})"
                    )
                conn.execute(
                    sql,
                    (
                        bar["symbol"],
                        bar["ts"],
                        bar["open"],
                        bar["high"],
                        bar["low"],
                        bar["close"],
                        bar["volume"],
                        "1m",
                    ),
                )
                conn.commit()
            finally:
                with contextlib.suppress(Exception):
                    conn.close()
        except Exception as exc:
            logger.debug("rithmic-stream: bar Postgres write failed (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Tick callback
    # ------------------------------------------------------------------

    async def on_tick(self, tick_data: Any) -> None:
        """Callback for incoming tick events from TICKER_PLANT.

        Publishes to Redis:
          - ``ticks:live:{symbol}``  — rolling 300-tick list (LPUSH + LTRIM)
          - ``rithmic:ticks:{symbol}`` — legacy alias (same data, back-compat)
          - ``rithmic:l1:{symbol}``  — hash with bid/ask/last/volume (2 s TTL)
          - ``bars:live:{symbol}``   — completed 1m bars (list, 500 cap)

        Also upserts completed 1m bars into Postgres ``historical_bars``.

        ``tick_data`` is the raw object from async_rithmic; we read attributes
        defensively with ``getattr`` so schema changes don't crash the callback.
        """
        try:
            symbol: str = str(getattr(tick_data, "symbol", "") or getattr(tick_data, "ticker", ""))
            if not symbol:
                return

            bid = getattr(tick_data, "best_bid_price", None)
            ask = getattr(tick_data, "best_ask_price", None)
            last = getattr(tick_data, "last_trade_price", None) or getattr(tick_data, "trade_price", None)
            volume = getattr(tick_data, "last_trade_size", None) or getattr(tick_data, "trade_size", None)
            ts = getattr(tick_data, "trade_time", None) or getattr(tick_data, "ssboe", None)

            tick_dict: dict[str, Any] = {
                "symbol": symbol,
                "bid": float(bid) if bid is not None else None,
                "ask": float(ask) if ask is not None else None,
                "last": float(last) if last is not None else None,
                "volume": int(volume) if volume is not None else None,
                "ts": int(ts) if ts is not None else None,
            }

            from core.cache import REDIS_AVAILABLE, _r

            if not REDIS_AVAILABLE or _r is None:
                return

            tick_json = json.dumps(tick_dict)

            # Rolling 300-tick window — canonical key
            live_ticks_key = f"ticks:live:{symbol}"
            _r.lpush(live_ticks_key, tick_json)
            _r.ltrim(live_ticks_key, 0, 299)

            # Legacy alias — kept so existing consumers aren't broken
            legacy_ticks_key = f"rithmic:ticks:{symbol}"
            _r.lpush(legacy_ticks_key, tick_json)
            _r.ltrim(legacy_ticks_key, 0, 299)

            # L1 snapshot with 2-second TTL
            l1_key = f"rithmic:l1:{symbol}"
            l1_data: dict[str, str] = {}
            if tick_dict["bid"] is not None:
                l1_data["bid"] = str(tick_dict["bid"])
            if tick_dict["ask"] is not None:
                l1_data["ask"] = str(tick_dict["ask"])
            if tick_dict["last"] is not None:
                l1_data["last"] = str(tick_dict["last"])
            if tick_dict["volume"] is not None:
                l1_data["volume"] = str(tick_dict["volume"])
            if tick_dict["ts"] is not None:
                l1_data["ts"] = str(tick_dict["ts"])
            if l1_data:
                _r.hset(l1_key, mapping=l1_data)
                _r.expire(l1_key, 2)

            # 1-minute bar aggregation — only when we have a trade price and ts
            last_price = tick_dict["last"]
            trade_vol = tick_dict["volume"] or 0
            ts_epoch = tick_dict["ts"]
            if last_price is not None and ts_epoch is not None:
                completed_bar = self._update_bar(symbol, last_price, trade_vol, ts_epoch)
                if completed_bar is not None:
                    self._publish_bar_to_redis(completed_bar, _r)
                    if self._debug:
                        logger.debug(
                            "rithmic-stream: 1m bar closed %s o=%.4f h=%.4f l=%.4f c=%.4f v=%d",
                            symbol,
                            completed_bar["open"],
                            completed_bar["high"],
                            completed_bar["low"],
                            completed_bar["close"],
                            completed_bar["volume"],
                        )
                    # Write to Postgres in a thread so we don't block the event loop
                    asyncio.get_event_loop().run_in_executor(None, self._write_bar_to_postgres, completed_bar)

        except Exception as exc:
            logger.debug("rithmic-stream: on_tick error: %s", exc)

    async def _on_order_book(self, data: Any) -> None:
        """Callback for ORDER_BOOK updates from TICKER_PLANT.

        Maintains an in-memory L2 snapshot per symbol and caches to Redis
        under ``rithmic:l2:{symbol}`` (hash, 5 s TTL).

        ``data`` is the raw protobuf response from async_rithmic.  We read
        fields defensively with ``getattr``.
        """
        try:
            from google.protobuf.json_format import MessageToDict  # type: ignore[import-untyped]

            d = MessageToDict(data, preserving_proto_field_name=True, use_integers_for_enums=True)

            symbol = d.get("symbol", "")
            if not symbol:
                return

            # update_type values: CLEAR=0, BEGIN=1, MIDDLE=2, END=3, SOLO=4, SNAPSHOT_IMAGE=5, NO_BOOK=6
            update_type = d.get("update_type", 4)  # default SOLO

            if update_type == 0:  # CLEAR_ORDER_BOOK
                self._l2_state.pop(symbol, None)
                return
            if update_type == 6:  # NO_BOOK
                return

            if symbol not in self._l2_state:
                self._l2_state[symbol] = {"bids": {}, "asks": {}}

            book = self._l2_state[symbol]

            # Process bid/ask updates from the order book message
            price = d.get("price")
            size = d.get("size", d.get("order_size", 0))
            side = d.get("side", d.get("transaction_type", ""))

            if price is not None:
                price_f = float(price)
                size_i = int(size) if size else 0

                if str(side) in ("1", "BUY", "B"):
                    if size_i > 0:
                        book["bids"][price_f] = size_i
                    else:
                        book["bids"].pop(price_f, None)
                elif str(side) in ("2", "SELL", "S"):
                    if size_i > 0:
                        book["asks"][price_f] = size_i
                    else:
                        book["asks"].pop(price_f, None)

            # Publish to Redis on SOLO or END messages
            if update_type in (3, 4, 5):  # END, SOLO, SNAPSHOT_IMAGE
                try:
                    from core.cache import REDIS_AVAILABLE, _r

                    if REDIS_AVAILABLE and _r is not None:
                        l2_key = f"rithmic:l2:{symbol}"
                        # Store as JSON hash with bids and asks sorted
                        sorted_bids = sorted(book["bids"].items(), key=lambda x: -x[0])[:20]
                        sorted_asks = sorted(book["asks"].items(), key=lambda x: x[0])[:20]
                        _r.hset(
                            l2_key,
                            mapping={
                                "bids": json.dumps([[p, s] for p, s in sorted_bids]),
                                "asks": json.dumps([[p, s] for p, s in sorted_asks]),
                                "symbol": symbol,
                                "ts": str(int(time.time())),
                            },
                        )
                        _r.expire(l2_key, 5)  # 5-second TTL
                except Exception as redis_exc:
                    logger.debug("rithmic-stream: L2 redis publish error: %s", redis_exc)

        except Exception as exc:
            logger.debug("rithmic-stream: _on_order_book error: %s", exc)

    # ------------------------------------------------------------------
    # Reconnect background task
    # ------------------------------------------------------------------

    async def reconnect(self, config: RithmicAccountConfig) -> None:
        """Background task: re-connect and re-subscribe after a disconnect.

        Intended to be spawned as an ``asyncio.create_task`` when the stream
        drops.  Calls ``start()`` (which already does exponential backoff)
        and then re-subscribes all previously subscribed symbols.
        """
        logger.info("rithmic-stream: starting reconnect background task")
        try:
            success = await self.start(config)
            if success:
                async with self._lock:
                    symbols = list(self._subscribed_symbols)
                if symbols:
                    await self.subscribe_symbols(symbols)
                    logger.info("rithmic-stream: reconnected and re-subscribed %d symbols", len(symbols))
            else:
                logger.error("rithmic-stream: reconnect failed — stream is offline")
        except asyncio.CancelledError:
            logger.debug("rithmic-stream: reconnect task cancelled")
            raise
        except Exception as exc:
            logger.error("rithmic-stream: reconnect task error: %s", exc)

    def trigger_reconnect(self, config: RithmicAccountConfig | None = None) -> None:
        """Schedule a reconnect task on the running event loop (non-async entry point).

        Safe to call from a sync context or from a connection-dropped callback.
        Does nothing if a reconnect task is already running.
        """
        cfg = config or self._config
        if cfg is None:
            logger.warning("rithmic-stream: trigger_reconnect called with no config — ignoring")
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            logger.debug("rithmic-stream: reconnect already in progress — skipping")
            return
        try:
            loop = asyncio.get_event_loop()
            self._reconnect_task = loop.create_task(self.reconnect(cfg))
        except RuntimeError:
            logger.debug("rithmic-stream: no running event loop for reconnect task")

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def is_live(self) -> bool:
        """Return True when RITHMIC_LIVE_DATA=1 AND the stream is connected."""
        return os.getenv("RITHMIC_LIVE_DATA", "0") == "1" and self._connected

    @property
    def plant_states(self) -> dict[str, dict[str, str]]:
        """Return per-plant connection states from Redis (convenience property)."""
        return self.get_plant_states()

    # ------------------------------------------------------------------
    # Redis readers (async)
    # ------------------------------------------------------------------

    async def get_l1_snapshot(self, symbol: str) -> dict[str, Any] | None:
        """Read the latest L1 bid/ask/last from Redis ``rithmic:l1:{symbol}``.

        Returns None when the key is missing or Redis is unavailable.
        The key has a 2 s TTL so a None result means no recent tick arrived.
        """
        try:
            from core.cache import REDIS_AVAILABLE, _r

            if not REDIS_AVAILABLE or _r is None:
                return None

            raw = _r.hgetall(f"rithmic:l1:{symbol}")
            if not raw:
                return None

            # Decode bytes keys/values from Redis
            decoded: dict[str, Any] = {}
            for k, v in raw.items():
                key_str = k.decode() if isinstance(k, bytes) else str(k)
                val_str = v.decode() if isinstance(v, bytes) else str(v)
                # Coerce numeric fields
                try:
                    decoded[key_str] = float(val_str) if "." in val_str else int(val_str)
                except (ValueError, TypeError):
                    decoded[key_str] = val_str

            decoded["symbol"] = symbol
            return decoded

        except Exception as exc:
            logger.debug("rithmic-stream: get_l1_snapshot(%s) error: %s", symbol, exc)
            return None

    async def get_recent_ticks(self, symbol: str, n: int = 50) -> list[dict[str, Any]]:
        """Read the *n* most recent ticks from Redis ``ticks:live:{symbol}``.

        Falls back to the legacy ``rithmic:ticks:{symbol}`` key if the
        canonical key is empty (e.g. during a rolling deploy).

        Returns an empty list when both keys are absent or Redis is unavailable.
        Ticks are ordered newest-first (LPUSH inserts at head).
        """
        try:
            from core.cache import REDIS_AVAILABLE, _r

            if not REDIS_AVAILABLE or _r is None:
                return []

            n = max(1, min(n, 300))
            # Prefer the canonical live key; fall back to legacy alias
            raw_items = _r.lrange(f"ticks:live:{symbol}", 0, n - 1)
            if not raw_items:
                raw_items = _r.lrange(f"rithmic:ticks:{symbol}", 0, n - 1)

            ticks: list[dict[str, Any]] = []
            for item in raw_items:
                with contextlib.suppress(Exception):
                    ticks.append(json.loads(item.decode() if isinstance(item, bytes) else item))
            return ticks

        except Exception as exc:
            logger.debug("rithmic-stream: get_recent_ticks(%s) error: %s", symbol, exc)
            return []

    async def get_l2_snapshot(self, symbol: str, levels: int = 10) -> dict[str, Any] | None:
        """Read the latest L2 DOM snapshot from Redis ``rithmic:l2:{symbol}``.

        Returns a dict with ``bids`` and ``asks`` lists (each entry is
        ``{"price": float, "size": int}``), or ``None`` when the key is absent.
        """
        try:
            from core.cache import REDIS_AVAILABLE, _r

            if not REDIS_AVAILABLE or _r is None:
                return None

            raw = _r.hgetall(f"rithmic:l2:{symbol}")
            if not raw:
                return None

            bids_raw = raw.get(b"bids", raw.get("bids"))
            asks_raw = raw.get(b"asks", raw.get("asks"))
            if not bids_raw or not asks_raw:
                return None

            bids_data = json.loads(bids_raw.decode() if isinstance(bids_raw, bytes) else bids_raw)
            asks_data = json.loads(asks_raw.decode() if isinstance(asks_raw, bytes) else asks_raw)

            levels = max(1, min(levels, 20))
            return {
                "bids": [{"price": p, "size": s} for p, s in bids_data[:levels]],
                "asks": [{"price": p, "size": s} for p, s in asks_data[:levels]],
                "symbol": symbol,
            }
        except Exception as exc:
            logger.debug("get_l2_snapshot(%s): %s", symbol, exc)
            return None

    async def get_recent_bars(self, symbol: str, n: int = 50) -> list[dict[str, Any]]:
        """Read the *n* most recent completed 1m bars from ``bars:live:{symbol}``.

        Returns an empty list when no bars have been aggregated yet or Redis
        is unavailable.  Bars are ordered newest-first.
        """
        try:
            from core.cache import REDIS_AVAILABLE, _r

            if not REDIS_AVAILABLE or _r is None:
                return []

            n = max(1, min(n, 500))
            raw_items = _r.lrange(f"bars:live:{symbol}", 0, n - 1)
            bars: list[dict[str, Any]] = []
            for item in raw_items:
                with contextlib.suppress(Exception):
                    bars.append(json.loads(item.decode() if isinstance(item, bytes) else item))
            return bars

        except Exception as exc:
            logger.debug("rithmic-stream: get_recent_bars(%s) error: %s", symbol, exc)
            return []


# ---------------------------------------------------------------------------
# Stream manager singleton
# ---------------------------------------------------------------------------

_stream_manager: RithmicStreamManager | None = None


def get_stream_manager() -> RithmicStreamManager:
    """Return (or lazily create) the module-level RithmicStreamManager singleton."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = RithmicStreamManager()
    return _stream_manager


# ---------------------------------------------------------------------------
# HTML renderers
# ---------------------------------------------------------------------------


# UI-SPLIT-A AUDIT: inline HTML (~92 HTML/JS lines) — P1 extraction candidate
# Target template: src/ruby/static/templates/rithmic_status_panel.html
# Engine: Jinja2 (loop over configs_ui + early-return branch require real templating)
# See: docs/ui_split_inventory.md entry #1
def _render_status_html(all_status: dict[str, dict[str, Any]], configs_ui: list[dict[str, Any]]) -> str:
    """Render the Connections-page Rithmic panel fragment."""
    now_str = datetime.now(tz=_EST).strftime("%I:%M %p ET")

    if not configs_ui:
        return """
<div style="text-align:center;padding:1.5rem 0;color:var(--text-faint);font-size:12px">
    No Rithmic accounts configured.<br/>
    <a href="/settings" style="color:#818cf8;text-decoration:none;font-size:11px">
        ⚙️ Add an account in Settings → Prop Accounts
    </a>
</div>"""

    rows = ""
    for cfg in configs_ui:
        key = cfg["key"]
        st = all_status.get(key, {})
        connected = st.get("connected", False)
        error = st.get("error", "")
        refreshed = st.get("refreshed_at", "")

        # Connection dot
        dot_color = "#22c55e" if connected else "#ef4444"
        dot_title = "Connected" if connected else (error or "Not connected")

        # P&L summary
        pnl = st.get("pnl", {})
        unreal = pnl.get("unrealized")
        real = pnl.get("realized")

        pnl_html = ""
        if unreal is not None or real is not None:

            def _fmt(v: Any) -> str:
                if v is None:
                    return "n/a"
                try:
                    fv = float(v)
                    color = "#4ade80" if fv >= 0 else "#f87171"
                    return f'<span style="color:{color}">${fv:+,.2f}</span>'
                except (TypeError, ValueError):
                    return str(v)

            pnl_html = (
                f'<span style="font-size:10px;color:var(--text-muted)">Unreal: {_fmt(unreal)}'
                f"&nbsp;·&nbsp;Real: {_fmt(real)}</span>"
            )

        # Positions summary
        positions = st.get("positions", [])
        pos_summary = ""
        if positions:
            pos_items = ", ".join(
                f"{p['symbol']} {'+' if int(p.get('size', 0)) > 0 else ''}{p.get('size', 0)}" for p in positions[:4]
            )
            pos_summary = f'<div style="font-size:10px;color:var(--text-muted);margin-top:2px">Pos: {pos_items}</div>'

        age_str = ""
        if refreshed:
            try:
                dt = datetime.fromisoformat(refreshed)
                age_s = (datetime.now(tz=_EST) - dt).total_seconds()
                age_str = f"{int(age_s)}s ago" if age_s < 60 else f"{int(age_s / 60)}m ago"
            except Exception:
                pass

        rows += f"""
<div style="display:flex;align-items:flex-start;gap:8px;padding:8px 0;
            border-bottom:1px solid var(--border-subtle)">
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                 background:{dot_color};margin-top:3px;flex-shrink:0"
          title="{dot_title}"></span>
    <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;justify-content:space-between">
            <span style="font-size:12px;font-weight:600">{cfg["label"]}</span>
            <span style="font-size:10px;color:var(--text-faint)">{age_str}</span>
        </div>
        <div style="font-size:10px;color:var(--text-muted)">{cfg["prop_firm_label"]}</div>
        {pnl_html}
        {pos_summary}
        {f'<div style="font-size:10px;color:#f87171;margin-top:2px">{error}</div>' if not connected and error else ""}
    </div>
    <button onclick="refreshRithmicAccount('{key}')"
            style="background:none;border:1px solid var(--border-subtle);border-radius:4px;
                   padding:2px 7px;font-size:10px;color:var(--text-muted);cursor:pointer;
                   white-space:nowrap"
            title="Force refresh this account">↺</button>
</div>"""

    return f"""
<div style="font-size:11px">
    {rows}
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding-top:6px;margin-top:2px">
        <span style="color:var(--text-faint);font-size:10px">Updated {now_str}</span>
        <button onclick="refreshAllRithmic()"
                style="background:none;border:1px solid var(--border-subtle);border-radius:4px;
                       padding:2px 8px;font-size:10px;color:var(--text-muted);cursor:pointer">
            ↺ Refresh all
        </button>
    </div>
</div>
<script>
function refreshRithmicAccount(key) {{
    fetch('/api/rithmic/account/' + key + '/refresh', {{method:'POST'}})
        .then(function() {{
            if (typeof htmx !== 'undefined')
                htmx.ajax('GET', '/api/rithmic/status/html', {{target:'#conn-rithmic', swap:'innerHTML'}});
        }});
}}
function refreshAllRithmic() {{
    fetch('/api/rithmic/refresh-all', {{method:'POST'}})
        .then(function() {{
            setTimeout(function() {{
                if (typeof htmx !== 'undefined')
                    htmx.ajax('GET', '/api/rithmic/status/html', {{target:'#conn-rithmic', swap:'innerHTML'}});
            }}, 2000);
        }});
}}
</script>"""


# UI-SPLIT-A AUDIT: inline HTML (~220 HTML/JS lines) — P1 extraction candidate
# Target template: src/ruby/static/templates/rithmic_settings_panel.html
# Engine: Jinja2 (account loop + presets JSON injection + large <script> block)
# See: docs/ui_split_inventory.md entry #2
def _render_settings_panel(configs_ui: list[dict[str, Any]]) -> str:
    """Render the Settings-page Prop Accounts panel HTML."""

    # Build existing account rows
    account_rows = ""
    for cfg in configs_ui:
        key = cfg["key"]
        prop_firm_options = "".join(
            f'<option value="{pf["value"]}"'
            f"{' selected' if pf['value'] == cfg['prop_firm'] else ''}>"
            f"{pf['label']}</option>"
            for pf in PROP_FIRM_OPTIONS
        )
        gateway_options = "".join(
            f'<option value="{g}"{" selected" if g == cfg["gateway"] else ""}>{g}</option>'
            for g in ["Chicago", "Sydney", "Sao Paulo", "test"]
        )
        acct_size = cfg.get("account_size", 150_000)
        account_size_options = "".join(
            f'<option value="{v}"{" selected" if v == acct_size else ""}>${v:,}</option>'
            for v in [25_000, 50_000, 100_000, 150_000, 200_000, 300_000]
        )
        enabled_checked = "checked" if cfg.get("enabled", True) else ""
        username_hint = cfg.get("username_hint", "")
        placeholder_user = f"Current: {username_hint}" if username_hint else "Rithmic username"
        placeholder_pass = "Leave blank to keep current" if cfg.get("password_set") else "Rithmic password"

        account_rows += f"""
<div class="rithmic-account-card" id="rithmic-card-{key}"
     style="border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:10px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <span style="font-size:0.8rem;font-weight:700">{cfg["label"]}</span>
        <div style="display:flex;gap:6px;align-items:center">
            <label style="display:flex;align-items:center;gap:4px;font-size:0.72rem;color:var(--muted)">
                <input type="checkbox" id="rith-{key}-enabled" {enabled_checked}
                       onchange="saveRithmicAccount('{key}')"/> Enabled
            </label>
            <button onclick="removeRithmicAccount('{key}')"
                    style="background:none;border:1px solid rgba(239,68,68,0.4);border-radius:4px;
                           padding:2px 8px;font-size:0.68rem;color:#f87171;cursor:pointer">
                ✕ Remove
            </button>
        </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div>
            <label style="font-size:0.68rem;color:var(--muted);display:block;margin-bottom:3px">Label</label>
            <input type="text" id="rith-{key}-label" value="{cfg["label"]}"
                   style="width:100%;background:var(--bg-input);border:1px solid var(--border);
                          border-radius:4px;padding:4px 8px;font-size:0.75rem;color:var(--text);
                          font-family:inherit"/>
        </div>
        <div>
            <label style="font-size:0.68rem;color:var(--muted);display:block;margin-bottom:3px">Prop Firm</label>
            <select id="rith-{key}-propfirm"
                    onchange="applyPropFirmPreset('{key}')"
                    style="width:100%;background:var(--bg-input);border:1px solid var(--border);
                           border-radius:4px;padding:4px 8px;font-size:0.75rem;color:var(--text);
                           font-family:inherit">
                {prop_firm_options}
            </select>
        </div>
        <div>
            <label style="font-size:0.68rem;color:var(--muted);display:block;margin-bottom:3px">
                Username
            </label>
            <input type="text" id="rith-{key}-user" placeholder="{placeholder_user}"
                   autocomplete="off"
                   style="width:100%;background:var(--bg-input);border:1px solid var(--border);
                          border-radius:4px;padding:4px 8px;font-size:0.75rem;color:var(--text);
                          font-family:inherit"/>
        </div>
        <div>
            <label style="font-size:0.68rem;color:var(--muted);display:block;margin-bottom:3px">
                Password
            </label>
            <input type="password" id="rith-{key}-pass" placeholder="{placeholder_pass}"
                   autocomplete="new-password"
                   style="width:100%;background:var(--bg-input);border:1px solid var(--border);
                          border-radius:4px;padding:4px 8px;font-size:0.75rem;color:var(--text);
                          font-family:inherit"/>
        </div>
        <div>
            <label style="font-size:0.68rem;color:var(--muted);display:block;margin-bottom:3px">
                Gateway
            </label>
            <select id="rith-{key}-gateway"
                    style="width:100%;background:var(--bg-input);border:1px solid var(--border);
                           border-radius:4px;padding:4px 8px;font-size:0.75rem;color:var(--text);
                           font-family:inherit">
                {gateway_options}
            </select>
        </div>
        <div>
            <label style="font-size:0.68rem;color:var(--muted);display:block;margin-bottom:3px">
                Account Size
            </label>
            <select id="rith-{key}-acctsize"
                    style="width:100%;background:var(--bg-input);border:1px solid var(--border);
                           border-radius:4px;padding:4px 8px;font-size:0.75rem;color:var(--text);
                           font-family:inherit">
                {account_size_options}
            </select>
        </div>
        <div>
            <label style="font-size:0.68rem;color:var(--muted);display:block;margin-bottom:3px">
                System Name <span style="color:var(--faint)">(auto-filled)</span>
            </label>
            <input type="text" id="rith-{key}-sysname" value="{cfg["system_name"]}"
                   placeholder="e.g. Rithmic Paper Trading"
                   style="width:100%;background:var(--bg-input);border:1px solid var(--border);
                          border-radius:4px;padding:4px 8px;font-size:0.75rem;color:var(--text);
                          font-family:inherit"/>
        </div>
    </div>

    <div style="margin-top:8px;display:flex;gap:6px;align-items:center">
        <button onclick="saveRithmicAccount('{key}')"
                style="background:#3b82f6;border:none;border-radius:4px;padding:4px 12px;
                       font-size:0.75rem;color:#fff;cursor:pointer;font-family:inherit">
            💾 Save
        </button>
        <button onclick="testRithmicAccount('{key}')"
                style="background:none;border:1px solid var(--border);border-radius:4px;
                       padding:4px 12px;font-size:0.75rem;color:var(--text);cursor:pointer;
                       font-family:inherit">
            🔌 Test Connection
        </button>
        <span id="rith-{key}-msg" style="font-size:0.72rem;color:var(--muted)"></span>
    </div>
</div>"""

    presets_json = json.dumps(PROP_FIRM_PRESETS)

    return f"""
<div style="margin-bottom:12px;font-size:0.72rem;color:var(--muted);line-height:1.5;
            background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);
            border-radius:7px;padding:10px 14px">
    📋 <strong>Read-only mode</strong> — connects to Rithmic to pull account
    balances, positions, and P&L. No orders are placed. Uses the same
    credentials as your prop firm's desktop platform.
    <br/>
    ⚠️ Before first use: accept market data agreements at
    <a href="https://rtraderpro.rithmic.com" target="_blank"
       style="color:#818cf8">rtraderpro.rithmic.com</a> (one-time per account).
</div>

{
        account_rows
        if account_rows
        else '<div style="color:var(--muted);font-size:0.8rem;text-align:center;padding:16px 0">'
        'No accounts configured. Click "+ Add Account" below.</div>'
    }

<div style="display:flex;gap:8px;margin-top:8px">
    <button onclick="addRithmicAccount()"
            style="background:none;border:1px solid var(--border);border-radius:4px;
                   padding:5px 14px;font-size:0.75rem;color:var(--text);cursor:pointer;
                   font-family:inherit">
        + Add Account
    </button>
    <span id="rithmic-global-msg" style="font-size:0.72rem;color:var(--muted);align-self:center"></span>
</div>

<script>
(function() {{
var _presets = {presets_json};

// Apply prop firm preset values when the dropdown changes
window.applyPropFirmPreset = function(key) {{
    var sel = document.getElementById('rith-' + key + '-propfirm');
    if (!sel) return;
    var preset = _presets[sel.value] || {{}};
    var sysnameEl = document.getElementById('rith-' + key + '-sysname');
    if (sysnameEl && preset.system_name) sysnameEl.value = preset.system_name;
    var gwEl = document.getElementById('rith-' + key + '-gateway');
    if (gwEl && preset.gateway) gwEl.value = preset.gateway;
}};

window.saveRithmicAccount = function(key) {{
    var data = {{
        key:         key,
        label:       (document.getElementById('rith-' + key + '-label')    || {{}}).value || key,
        prop_firm:   (document.getElementById('rith-' + key + '-propfirm') || {{}}).value || 'tpt',
        system_name: (document.getElementById('rith-' + key + '-sysname')  || {{}}).value || '',
        gateway:     (document.getElementById('rith-' + key + '-gateway')  || {{}}).value || 'Chicago',
        account_size: parseInt((document.getElementById('rith-' + key + '-acctsize') || {{}}).value) || 150000,
        username:    (document.getElementById('rith-' + key + '-user')     || {{}}).value || '',
        password:    (document.getElementById('rith-' + key + '-pass')     || {{}}).value || '',
        enabled:     (document.getElementById('rith-' + key + '-enabled')  || {{checked:true}}).checked,
    }};
    var msgEl = document.getElementById('rith-' + key + '-msg');
    if (msgEl) msgEl.textContent = 'Saving…';
    fetch('/api/rithmic/account/' + key + '/save', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(data),
    }}).then(function(r) {{ return r.json(); }})
      .then(function(d) {{
        if (msgEl) msgEl.textContent = d.ok ? '✅ Saved' : ('❌ ' + (d.error || 'error'));
        // Clear password field after save for security
        var passEl = document.getElementById('rith-' + key + '-pass');
        if (passEl) passEl.value = '';
        setTimeout(function() {{ if (msgEl) msgEl.textContent = ''; }}, 3000);
      }}).catch(function(e) {{ if (msgEl) msgEl.textContent = '❌ ' + e; }});
}};

window.testRithmicAccount = function(key) {{
    var msgEl = document.getElementById('rith-' + key + '-msg');
    if (msgEl) msgEl.textContent = '🔌 Connecting…';
    fetch('/api/rithmic/account/' + key + '/refresh', {{method:'POST'}})
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{
            if (msgEl) {{
                msgEl.textContent = d.connected
                    ? ('✅ Connected (' + (d.accounts||[]).length + ' account(s))')
                    : ('❌ ' + (d.error || 'failed'));
            }}
        }}).catch(function(e) {{ if (msgEl) msgEl.textContent = '❌ ' + e; }});
}};

window.removeRithmicAccount = function(key) {{
    if (!confirm('Remove account "' + key + '"? This cannot be undone.')) return;
    fetch('/api/rithmic/account/' + key + '/remove', {{method:'DELETE'}})
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{
            var card = document.getElementById('rithmic-card-' + key);
            if (card) card.remove();
            var gm = document.getElementById('rithmic-global-msg');
            if (gm) {{ gm.textContent = d.ok ? 'Removed.' : ('Error: ' + d.error); }}
        }});
}};

var _addCounter = 0;
window.addRithmicAccount = function() {{
    _addCounter++;
    var newKey = 'acc' + Date.now();
    // Build a minimal empty card by refreshing the settings panel
    fetch('/api/rithmic/config/new-key', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{key: newKey, label: 'Account ' + _addCounter}}),
    }}).then(function(r) {{ return r.json(); }})
      .then(function() {{
        // Reload the whole section
        if (typeof htmx !== 'undefined') {{
            htmx.ajax('GET', '/settings/rithmic/panel', {{
                target: '#rithmic-settings-panel', swap: 'innerHTML'
            }});
        }} else {{
            location.reload();
        }}
      }});
}};

}})();
</script>"""


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.get("/api/rithmic/accounts")
def list_accounts():
    """Return all configured accounts (no credentials)."""
    mgr = get_manager()
    return JSONResponse({"accounts": mgr.get_all_ui()})


@router.get("/api/rithmic/status")
def get_status():
    """Return last-known live status for all accounts."""
    mgr = get_manager()
    return JSONResponse(
        {
            "status": mgr.get_all_status(),
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.get("/api/rithmic/status/html", response_class=HTMLResponse)
def get_status_html():
    """HTMX fragment for the Connections page Rithmic panel."""
    mgr = get_manager()
    html = _render_status_html(mgr.get_all_status(), mgr.get_all_ui())
    return HTMLResponse(content=html)


@router.get("/api/rithmic/account/{key}")
def get_account(key: str):
    """Return status for a single account."""
    mgr = get_manager()
    return JSONResponse(mgr.get_status(key))


@router.post("/api/rithmic/account/{key}/refresh")
async def refresh_account(key: str):
    """Force-refresh a single account's live data."""
    mgr = get_manager()
    result = await mgr.refresh_account(key)
    return JSONResponse(result)


@router.post("/api/rithmic/refresh-all")
async def refresh_all():
    """Refresh all enabled accounts (runs concurrently)."""
    mgr = get_manager()
    await mgr.refresh_all()
    return JSONResponse({"ok": True, "message": "refresh queued"})


@router.get("/api/rithmic/fills/{key}")
async def get_account_fills(key: str):
    """Retrieve today's order/fill history for a single Rithmic account.

    Opens a short-lived session, calls ``show_order_history_summary()``,
    caches the result in Redis (24 h TTL), and returns the fill list.

    Each fill dict contains:
        account_key, order_id, symbol, exchange, buy_sell, qty,
        fill_price, fill_time, status, commission.
    """
    mgr = get_manager()
    fills = await mgr.get_today_fills(key)
    return JSONResponse(
        {
            "ok": True,
            "account_key": key,
            "fills": fills,
            "count": len(fills),
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.get("/api/rithmic/fills")
async def get_all_fills():
    """Retrieve today's order/fill history for all enabled Rithmic accounts.

    Calls ``get_today_fills`` concurrently for every enabled account and
    returns a combined flat list along with a per-account breakdown.
    """
    mgr = get_manager()
    fills = await mgr.get_all_today_fills()

    # Build per-account breakdown for convenience
    by_account: dict[str, list[dict]] = {}
    for f in fills:
        ak = f.get("account_key", "unknown")
        by_account.setdefault(ak, []).append(f)

    return JSONResponse(
        {
            "ok": True,
            "fills": fills,
            "count": len(fills),
            "by_account": {k: {"count": len(v), "fills": v} for k, v in by_account.items()},
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.post("/api/rithmic/eod-close")
async def eod_close(req: _FastAPIRequest):
    """Cancel all working orders and flatten all positions across every enabled account.

    Optional JSON body:
        { "dry_run": true }   — connect + discover but skip cancel/exit calls.

    This endpoint is called by the scheduler at 16:00 ET and can also be
    triggered manually from the dashboard.
    """
    body: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        body = await req.json()

    dry_run: bool = bool(body.get("dry_run", False))

    mgr = get_manager()
    results = await mgr.eod_close_all_positions(dry_run=dry_run)

    any_error = any(r.get("error") for r in results)
    logger.info(
        "EOD close triggered via API: dry_run=%s accounts=%d any_error=%s",
        dry_run,
        len(results),
        any_error,
    )
    return JSONResponse(
        {
            "ok": not any_error,
            "dry_run": dry_run,
            "results": results,
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.delete("/api/rithmic/account/{key}/remove")
def remove_account(key: str):
    """Remove an account config permanently."""
    configs = _load_configs()
    original_len = len(configs)
    configs = [c for c in configs if c.key != key]
    if len(configs) == original_len:
        return JSONResponse({"ok": False, "error": f"account '{key}' not found"})
    _save_configs(configs)
    mgr = get_manager()
    mgr.reload_configs()
    mgr._status.pop(key, None)
    return JSONResponse({"ok": True})


@router.post("/api/rithmic/config/new-key")
async def create_empty_account(request: Request):
    """Create a blank account placeholder so the UI can show an edit card."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    new_key = body.get("key", f"acc_{int(datetime.now().timestamp())}")
    label = body.get("label", "New Account")

    configs = _load_configs()
    if any(c.key == new_key for c in configs):
        return JSONResponse({"ok": True, "key": new_key, "message": "already exists"})

    new_cfg = RithmicAccountConfig(
        key=new_key,
        label=label,
        prop_firm="tpt",
        enabled=False,  # disabled until credentials are entered
    )
    configs.append(new_cfg)
    _save_configs(configs)
    get_manager().reload_configs()
    return JSONResponse({"ok": True, "key": new_key})


@router.get("/settings/rithmic/panel", response_class=HTMLResponse)
def rithmic_settings_panel():
    """HTMX fragment: render just the Rithmic account cards for the Settings page."""
    mgr = get_manager()
    html = _render_settings_panel(mgr.get_all_ui())
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Save + dependency-check endpoints
# ---------------------------------------------------------------------------

from fastapi import Request as _FastAPIRequest  # noqa: E402 — needed after router definition


@router.get("/api/rithmic/deps")
def check_deps():
    """Return installation status for packages required by the Rithmic integration."""
    import importlib

    packages = {
        "async-rithmic": "async_rithmic",
        "cryptography": "cryptography",
        "httpx": "httpx",
    }
    result: dict[str, dict[str, Any]] = {}
    for display_name, import_name in packages.items():
        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", None) or getattr(mod, "version", None) or "installed"
            result[display_name] = {"installed": True, "version": str(version)}
        except ImportError:
            result[display_name] = {"installed": False, "version": None}

    all_ok = all(v["installed"] for v in result.values())
    return JSONResponse({"ok": all_ok, "packages": result})


@router.post("/api/rithmic/account/{key}/save")
async def save_account_ui(key: str, req: _FastAPIRequest):
    """Save account config from the Settings UI.

    Identical to /config but uses the path the frontend JS calls.
    Body JSON: key, label, prop_firm, system_name, gateway,
               username (plaintext), password (plaintext), enabled.
    Password is only updated when a non-empty value is provided.
    """
    try:
        body: dict[str, Any] = await req.json()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"invalid JSON: {exc}"}, status_code=400)

    body_key = body.get("key", key)
    configs = _load_configs()
    existing = next((c for c in configs if c.key == body_key), None)
    if existing is None:
        existing = RithmicAccountConfig(key=body_key, label=body.get("label", body_key))
        configs.append(existing)

    existing.label = body.get("label", existing.label)
    existing.prop_firm = body.get("prop_firm", existing.prop_firm)
    existing.gateway = body.get("gateway", existing.gateway)
    existing.enabled = bool(body.get("enabled", existing.enabled))
    existing.account_size = int(body.get("account_size", existing.account_size))

    sys_override = body.get("system_name", "").strip()
    preset = PROP_FIRM_PRESETS.get(existing.prop_firm, {})
    existing.system_name = sys_override or preset.get("system_name", existing.system_name)

    new_user = body.get("username", "").strip()
    new_pass = body.get("password", "").strip()
    if new_user:
        existing._username_enc = _encrypt(new_user)
    if new_pass:
        existing._password_enc = _encrypt(new_pass)

    _save_configs(configs)
    get_manager().reload_configs()
    logger.info("rithmic: saved config for account '%s' via UI", body_key)
    return JSONResponse({"ok": True, "key": body_key})


@router.post("/api/rithmic/account/{key}/config")
async def save_account_config(key: str, req: _FastAPIRequest):
    """Save (upsert) a single account config from the Settings UI.

    Body (JSON):
        key, label, prop_firm, system_name, gateway,
        username  (plaintext — encrypted server-side, optional),
        password  (plaintext — encrypted server-side, optional),
        enabled   (bool)
    """
    try:
        body: dict[str, Any] = await req.json()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"invalid JSON: {exc}"}, status_code=400)

    body_key = body.get("key", key)
    if body_key != key:
        return JSONResponse({"ok": False, "error": "key mismatch"}, status_code=400)

    configs = _load_configs()
    existing = next((c for c in configs if c.key == key), None)

    if existing is None:
        existing = RithmicAccountConfig(key=key, label=body.get("label", key))
        configs.append(existing)

    existing.label = body.get("label", existing.label)
    existing.prop_firm = body.get("prop_firm", existing.prop_firm)
    existing.gateway = body.get("gateway", existing.gateway)
    existing.enabled = bool(body.get("enabled", existing.enabled))
    existing.app_name = body.get("app_name", existing.app_name)
    existing.app_version = body.get("app_version", existing.app_version)
    existing.account_size = int(body.get("account_size", existing.account_size))

    # Resolve system_name: explicit > preset > existing
    sys_override = body.get("system_name", "").strip()
    preset = PROP_FIRM_PRESETS.get(existing.prop_firm, {})
    existing.system_name = sys_override or preset.get("system_name", existing.system_name)

    # Only update credentials when provided (non-empty strings)
    new_user = body.get("username", "").strip()
    new_pass = body.get("password", "").strip()
    if new_user:
        existing._username_enc = _encrypt(new_user)
    if new_pass:
        existing._password_enc = _encrypt(new_pass)

    _save_configs(configs)
    get_manager().reload_configs()

    logger.info("rithmic: saved config for account '%s'", key)
    return JSONResponse({"ok": True, "key": key})


# ---------------------------------------------------------------------------
# Streaming endpoints (RITHMIC-STREAM-A)
# ---------------------------------------------------------------------------


@router.get("/api/rithmic/stream/status")
def stream_plant_states():
    """Return per-plant connection state from Redis ``rithmic:connection:{plant}`` keys.

    Used by the dashboard Connections page to show granular plant health
    (TICKER_PLANT, PNL_PLANT, HISTORY_PLANT, ORDER_PLANT).
    """
    try:
        from integrations.rithmic_client import get_stream_manager  # type: ignore[import-unresolved]

        sm = get_stream_manager()
        return JSONResponse({"ok": True, "plants": sm.plant_states})
    except Exception as exc:
        logger.warning("rithmic stream_plant_states error: %s", exc)
        return JSONResponse({"ok": False, "plants": {}, "error": str(exc)})


@router.get("/api/rithmic/stream/state")
def stream_status():
    """Return the current state of the persistent stream manager.

    Response fields:
        live          — True when RITHMIC_LIVE_DATA=1 AND connected
        connected     — raw _connected flag (ignores env var)
        env_enabled   — True when RITHMIC_LIVE_DATA=1
        subscribed_symbols — list of currently subscribed symbols
    """
    sm = get_stream_manager()
    return JSONResponse(
        {
            "live": sm.is_live(),
            "connected": sm._connected,
            "env_enabled": os.getenv("RITHMIC_LIVE_DATA", "0") == "1",
            "subscribed_symbols": sorted(sm._subscribed_symbols),
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.post("/api/rithmic/stream/subscribe")
async def stream_subscribe(req: _FastAPIRequest):
    """Subscribe the stream manager to a list of symbols.

    Body JSON:
        { "symbols": ["MES", "MNQ"] }

    Returns 503 when the stream is not connected.
    Symbols are passed directly to ``subscribe_symbols``; each one triggers
    a ``subscribe_to_market_data`` call on the live TICKER_PLANT connection.
    """
    try:
        body: dict[str, Any] = await req.json()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"invalid JSON: {exc}"}, status_code=400)

    symbols: list[str] = body.get("symbols", [])
    if not symbols or not isinstance(symbols, list):
        return JSONResponse({"ok": False, "error": "symbols must be a non-empty list"}, status_code=400)

    sm = get_stream_manager()

    if not sm._connected:
        return JSONResponse(
            {"ok": False, "error": "stream not connected — start the stream first"},
            status_code=503,
        )

    await sm.subscribe_symbols([str(s) for s in symbols])

    return JSONResponse(
        {
            "ok": True,
            "requested": symbols,
            "subscribed_symbols": sorted(sm._subscribed_symbols),
        }
    )


@router.get("/api/rithmic/stream/l1/{symbol}")
async def stream_l1(symbol: str):
    """Return the latest L1 bid/ask/last snapshot for *symbol* from Redis.

    The value is written by ``RithmicStreamManager.on_tick`` with a 2 s TTL.
    Returns 404 when no recent tick has arrived (stream not live or no data).
    """
    sm = get_stream_manager()
    snapshot = await sm.get_l1_snapshot(symbol.upper())
    if snapshot is None:
        return JSONResponse(
            {"ok": False, "error": f"no L1 data for {symbol} — stream may not be live"},
            status_code=404,
        )
    return JSONResponse({"ok": True, "symbol": symbol.upper(), "l1": snapshot})


@router.get("/api/rithmic/stream/ticks/{symbol}")
async def stream_ticks(symbol: str, n: int = 50):
    """Return the *n* most recent ticks for *symbol* from Redis.

    Query param:
        n — number of ticks to return (1–300, default 50)

    Ticks are ordered newest-first.  Returns an empty list when the stream
    has not published any ticks for this symbol yet.
    """
    n = max(1, min(n, 300))
    sm = get_stream_manager()
    ticks = await sm.get_recent_ticks(symbol.upper(), n=n)
    return JSONResponse(
        {
            "ok": True,
            "symbol": symbol.upper(),
            "count": len(ticks),
            "ticks": ticks,
        }
    )


@router.get("/api/rithmic/stream/bars/{symbol}")
async def stream_bars(symbol: str, n: int = 50):
    """Return the *n* most recent completed 1-minute bars for *symbol*.

    Bars are aggregated in-memory by ``RithmicStreamManager.on_tick`` and
    pushed to ``bars:live:{symbol}`` in Redis each time a minute boundary
    is crossed.  They are also upserted into the ``historical_bars``
    Postgres table so the rolling dataset stays current.

    Query param:
        n — number of bars to return (1–500, default 50)

    Bars are ordered newest-first.  Returns an empty list when the stream
    has not yet closed a 1-minute bar for this symbol (i.e. fewer than
    60 seconds of tick data have been received since the stream started).
    """
    n = max(1, min(n, 500))
    sm = get_stream_manager()
    bars = await sm.get_recent_bars(symbol.upper(), n=n)
    return JSONResponse(
        {
            "ok": True,
            "symbol": symbol.upper(),
            "count": len(bars),
            "bars": bars,
        }
    )


@router.get("/api/rithmic/stream/pnl")
async def stream_pnl_all():
    """Return live P&L snapshots for all accounts from ``pnl:live:*`` Redis keys.

    Each entry contains unrealized, realized, total, and ts fields as
    published by the ``_pnl_poll_loop`` background task.
    """
    try:
        from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

        if not REDIS_AVAILABLE or _r is None:
            return JSONResponse(
                {"ok": False, "error": "Redis unavailable", "accounts": {}},
                status_code=503,
            )

        accounts: dict[str, dict[str, Any]] = {}
        # Scan for all pnl:live:* keys (exclude the last_reported_realized helper key)
        for raw_key in _r.scan_iter(match="pnl:live:*", count=100):
            key_str = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
            if key_str == "pnl:live:last_reported_realized":
                continue
            account_id = key_str.replace("pnl:live:", "", 1)
            raw = _r.hgetall(raw_key)
            if raw:
                decoded = {
                    (k.decode() if isinstance(k, bytes) else str(k)): (v.decode() if isinstance(v, bytes) else str(v))
                    for k, v in raw.items()
                }
                # Coerce numeric fields
                for field in ("unrealized", "realized", "total"):
                    if field in decoded:
                        with contextlib.suppress(ValueError, TypeError):
                            decoded[field] = float(decoded[field])
                accounts[account_id] = decoded

        return JSONResponse({"ok": True, "accounts": accounts})

    except Exception as exc:
        logger.warning("stream_pnl_all error: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc), "accounts": {}}, status_code=500)


@router.get("/api/rithmic/stream/pnl/{account_id}")
async def stream_pnl_account(account_id: str):
    """Return the live P&L snapshot for a single account from ``pnl:live:{account_id}``.

    Returns 404 when no P&L data has been published for the given account.
    """
    try:
        from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

        if not REDIS_AVAILABLE or _r is None:
            return JSONResponse(
                {"ok": False, "error": "Redis unavailable"},
                status_code=503,
            )

        raw = _r.hgetall(f"pnl:live:{account_id}")
        if not raw:
            return JSONResponse(
                {"ok": False, "error": f"no P&L data for account {account_id}"},
                status_code=404,
            )

        decoded: dict[str, Any] = {
            (k.decode() if isinstance(k, bytes) else str(k)): (v.decode() if isinstance(v, bytes) else str(v))
            for k, v in raw.items()
        }
        for field in ("unrealized", "realized", "total"):
            if field in decoded:
                with contextlib.suppress(ValueError, TypeError):
                    decoded[field] = float(decoded[field])

        return JSONResponse({"ok": True, "account_id": account_id, "pnl": decoded})

    except Exception as exc:
        logger.warning("stream_pnl_account(%s) error: %s", account_id, exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/api/rithmic/stream/orders")
async def stream_orders():
    """Return recent order events from the in-memory ORDER_PLANT state.

    Each entry contains the order's current lifecycle state including
    order_id, status, fill_price, fill_qty, symbol, and timestamp.
    """
    sm = get_stream_manager()
    orders = list(sm._order_states.values())
    return JSONResponse(
        {
            "ok": True,
            "connected": sm.is_order_connected,
            "count": len(orders),
            "orders": orders,
        }
    )


@router.get("/api/rithmic/stream/orders/{order_id}")
async def stream_order_detail(order_id: str):
    """Return the lifecycle state of a specific order from ORDER_PLANT.

    Returns 404 when no order event has been received for the given order_id.
    """
    sm = get_stream_manager()
    state = sm._order_states.get(order_id)
    if state is None:
        # Also check Redis as a fallback
        try:
            from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

            if REDIS_AVAILABLE and _r is not None:
                raw = _r.hgetall(f"rithmic:order:{order_id}")
                if raw:
                    state = {
                        (k.decode() if isinstance(k, bytes) else str(k)): (
                            v.decode() if isinstance(v, bytes) else str(v)
                        )
                        for k, v in raw.items()
                    }
        except Exception:
            pass

    if state is None:
        return JSONResponse(
            {"ok": False, "error": f"no order event for {order_id}"},
            status_code=404,
        )

    return JSONResponse({"ok": True, "order_id": order_id, "state": state})


@router.post("/api/rithmic/stream/backfill")
async def stream_backfill(req: _FastAPIRequest):
    """Trigger historical bar backfill via the HISTORY_PLANT connection.

    Body JSON:
        { "symbols": ["MGC", "MES"], "days_back": 365 }

    Connects to HISTORY_PLANT (if not already connected), then fetches
    historical bars for each requested symbol and writes them to Postgres.

    Returns a list of result dicts, one per symbol:
        { "symbol": "MGC", "bars_written": 12345, "error": "" }
    """
    try:
        body: dict[str, Any] = await req.json()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"invalid JSON: {exc}"}, status_code=400)

    symbols: list[str] = body.get("symbols", [])
    if not symbols or not isinstance(symbols, list):
        return JSONResponse({"ok": False, "error": "symbols must be a non-empty list"}, status_code=400)

    days_back: int = int(body.get("days_back", 365))
    days_back = max(1, min(days_back, 3650))  # clamp to sane range

    sm = get_stream_manager()

    # Auto-connect HISTORY_PLANT if not already connected
    if not sm.is_history_connected:
        if sm._config is None:
            return JSONResponse(
                {"ok": False, "error": "stream not configured — start the ticker stream first"},
                status_code=503,
            )
        connected = await sm.connect_history_plant(sm._config)
        if not connected:
            return JSONResponse(
                {"ok": False, "error": "failed to connect to HISTORY_PLANT"},
                status_code=503,
            )

    results: list[dict[str, Any]] = []
    for symbol in symbols:
        result = await sm.backfill_bars(str(symbol).upper(), days_back=days_back)
        results.append(result)

    return JSONResponse(
        {
            "ok": True,
            "results": results,
            "total_bars_written": sum(r.get("bars_written", 0) for r in results),
        }
    )


# ---------------------------------------------------------------------------
# Stream lifecycle — start / stop
# ---------------------------------------------------------------------------


@router.post("/api/rithmic/stream/start")
async def stream_start(req: _FastAPIRequest):
    """Start the persistent Rithmic stream (TICKER_PLANT + PNL_PLANT).

    Resolves the first enabled :class:`RithmicAccountConfig` and calls
    :meth:`RithmicStreamManager.start` (TICKER_PLANT) and
    :meth:`RithmicStreamManager.connect_pnl_plant` (PNL_PLANT).

    Optional JSON body:
        { "account_key": "acc1", "symbols": ["MES", "NQ"] }

    When ``account_key`` is omitted, the first enabled account is used.
    When ``symbols`` is omitted, the ``RITHMIC_SYMBOLS`` env var (or the
    default list MES,NQ,ES,RTY,YM) is used.

    Returns 400 when no enabled account is found.
    Returns 503 when the connection attempt fails.
    """
    body: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        body = await req.json()

    account_key: str | None = body.get("account_key") or None
    symbols_override: list[str] | None = body.get("symbols") or None

    # Resolve config
    configs = _load_configs()
    config: RithmicAccountConfig | None = None
    if account_key:
        config = next((c for c in configs if c.key == account_key and c.enabled), None)
        if config is None:
            return JSONResponse(
                {"ok": False, "error": f"account '{account_key}' not found or disabled"},
                status_code=400,
            )
    else:
        config = next((c for c in configs if c.enabled), None)
        if config is None:
            return JSONResponse(
                {"ok": False, "error": "no enabled Rithmic account found — configure one first"},
                status_code=400,
            )

    sm = get_stream_manager()

    # Connect TICKER_PLANT
    ticker_ok = await sm.start(config)
    if not ticker_ok:
        return JSONResponse(
            {"ok": False, "error": "TICKER_PLANT connect failed — check credentials and network"},
            status_code=503,
        )

    # Connect PNL_PLANT (non-fatal)
    pnl_ok = False
    with contextlib.suppress(Exception):
        pnl_ok = await sm.connect_pnl_plant(config)

    # Subscribe to symbols
    symbols = symbols_override or [
        s.strip().upper() for s in os.getenv("RITHMIC_SYMBOLS", "MES,NQ,ES,RTY,YM").split(",") if s.strip()
    ]
    await sm.subscribe_symbols(symbols)

    logger.info(
        "rithmic-stream: started via API — account=%s symbols=%s pnl=%s",
        config.key,
        symbols,
        pnl_ok,
    )

    return JSONResponse(
        {
            "ok": True,
            "account_key": config.key,
            "subscribed_symbols": sorted(sm._subscribed_symbols),
            "pnl_connected": pnl_ok,
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.post("/api/rithmic/stream/stop")
async def stream_stop():
    """Gracefully stop the persistent Rithmic stream (all plants).

    Calls :meth:`RithmicStreamManager.stop` which disconnects TICKER_PLANT,
    PNL_PLANT, HISTORY_PLANT, and ORDER_PLANT and cancels the reconnect task.
    Also updates ``rithmic:health`` in Redis to ``connected=false``.
    """
    sm = get_stream_manager()
    await sm.stop()

    # Update health key in Redis
    try:
        from core.cache import REDIS_AVAILABLE, _r

        if REDIS_AVAILABLE and _r is not None:
            _r.hset(
                "rithmic:health",
                mapping={
                    "connected": "false",
                    "account_key": "",
                    "error": "stopped via API",
                    "ts": datetime.now(tz=_EST).isoformat(),
                    "live_data": os.getenv("RITHMIC_LIVE_DATA", "0"),
                },
            )
            _r.expire("rithmic:health", 30)
    except Exception as exc:
        logger.debug("stream_stop: health key update failed (non-fatal): %s", exc)

    logger.info("rithmic-stream: stopped via API")

    return JSONResponse(
        {
            "ok": True,
            "message": "stream stopped",
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# /api/rithmic/live/* — high-level RithmicPositionEngine endpoints
#
# These endpoints read from the Redis keys written by the TICKER_PLANT
# and PNL_PLANT background tasks.  They go through RithmicPositionEngine
# so they automatically fall back to mock data when live data is absent.
# ---------------------------------------------------------------------------


def _get_position_engine() -> Any:
    """Return the data-service RithmicPositionEngine from app.state, or a
    freshly-created offline instance as a fallback."""
    # Prefer the instance stored by the data-service lifespan
    try:
        # FastAPI request context is not available here, so we probe the
        # module-level engine_helpers singleton as a second option.
        from services.engine.engine_helpers import _rithmic_engine as _eng

        if _eng is not None:
            return _eng
    except Exception:
        pass

    # Last resort: create a transient offline instance
    try:
        from services.engine.rithmic_position_engine import RithmicPositionEngine

        return RithmicPositionEngine()
    except Exception:
        return None


@router.get("/api/rithmic/live/health")
def live_health():
    """Return RithmicPositionEngine health and plant connection states.

    Combines the ``rithmic:health`` Redis key (written by the data-service
    lifespan on every connect/disconnect) with the per-plant states from
    ``rithmic:connection:{plant}`` keys.

    Response fields:
        connected       — True when TICKER_PLANT is live
        account_key     — the account used for the active stream
        live_data_env   — value of ``RITHMIC_LIVE_DATA`` env var
        plant_states    — per-plant connection state dicts
        ts              — ISO timestamp of the last health update
    """
    # Read from Redis health key
    health: dict[str, Any] = {
        "connected": False,
        "account_key": "",
        "live_data_env": os.getenv("RITHMIC_LIVE_DATA", "0"),
        "error": "",
        "ts": "",
        "plant_states": {},
    }
    try:
        from core.cache import REDIS_AVAILABLE, _r

        if REDIS_AVAILABLE and _r is not None:
            raw = _r.hgetall("rithmic:health")
            if raw:
                for k, v in raw.items():
                    key_s = k.decode() if isinstance(k, bytes) else str(k)
                    val_s = v.decode() if isinstance(v, bytes) else str(v)
                    if key_s == "connected":
                        health["connected"] = val_s == "true"
                    else:
                        health[key_s] = val_s
    except Exception as exc:
        health["error"] = str(exc)

    health["plant_states"] = get_stream_manager().get_plant_states()
    return JSONResponse({"ok": True, "health": health})


@router.get("/api/rithmic/live/positions")
async def live_positions(account_key: str | None = None):
    """Return current open positions via :class:`RithmicPositionEngine`.

    When ``RITHMIC_LIVE_DATA=1`` and the stream is connected, reads from
    the Redis account-status cache (``rithmic:account_status:{account_key}``)
    populated by :meth:`RithmicAccountManager.refresh_account`.

    Falls back to a mock dataset in offline / paper-trading mode.

    Query params:
        account_key — Rithmic account key (optional; defaults to the
                      primary streaming account).  Use ``all`` to
                      aggregate across every enabled account.

    Returns:
        ``{ "ok": true, "positions": [...], "account_key": "...",
            "count": N, "source": "live"|"mock", "timestamp": "..." }``
    """
    engine = _get_position_engine()
    if engine is None:
        return JSONResponse(
            {"ok": False, "error": "RithmicPositionEngine not available"},
            status_code=503,
        )

    positions = await engine.get_positions(account_key=account_key)
    source = "mock" if (positions and positions[0].get("_mock")) else "live"

    return JSONResponse(
        {
            "ok": True,
            "positions": positions,
            "account_key": account_key or engine._account_key or "all",
            "count": len(positions),
            "source": source,
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.get("/api/rithmic/live/pnl/{account_key}")
async def live_pnl(account_key: str):
    """Return real-time P&L for an account via :class:`RithmicPositionEngine`.

    Reads from ``pnl:live:{account_key}`` in Redis (written every 5 seconds
    by the PNL_PLANT background poll loop).

    Returns zero values in offline / paper-trading mode.

    Path params:
        account_key — Rithmic account identifier.

    Returns:
        ``{ "ok": true, "account_key": "...", "pnl": { daily_pnl, unrealized_pnl,
            realized_pnl, ts }, "source": "live"|"offline" }``
    """
    engine = _get_position_engine()
    if engine is None:
        return JSONResponse(
            {"ok": False, "error": "RithmicPositionEngine not available"},
            status_code=503,
        )

    pnl = await engine.get_pnl(account_key)
    source = "live" if pnl.get("_live") else "offline"
    pnl_clean = {k: v for k, v in pnl.items() if not k.startswith("_")}

    return JSONResponse(
        {
            "ok": True,
            "account_key": account_key,
            "pnl": pnl_clean,
            "source": source,
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.get("/api/rithmic/live/l1/{symbol}")
async def live_l1(symbol: str):
    """Return the latest Level-1 bid/ask/last for *symbol*.

    Reads from ``rithmic:l1:{symbol}`` in Redis (2 s TTL, written by the
    TICKER_PLANT ``on_tick`` callback).  Returns a static mock when the key
    is absent (no recent tick) or when live data is not enabled.

    Path params:
        symbol — Instrument symbol (case-insensitive, e.g. ``MES``).

    Returns:
        ``{ "ok": true, "symbol": "MES", "l1": { bid, ask, last, volume, ts },
            "source": "live"|"mock" }``
    """
    sym = symbol.upper()
    engine = _get_position_engine()
    if engine is None:
        return JSONResponse(
            {"ok": False, "error": "RithmicPositionEngine not available"},
            status_code=503,
        )

    l1 = await engine.get_l1(sym)
    source = "live" if l1.get("_live") else "mock"
    l1_clean = {k: v for k, v in l1.items() if not k.startswith("_")}

    return JSONResponse(
        {
            "ok": True,
            "symbol": sym,
            "l1": l1_clean,
            "source": source,
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.get("/api/rithmic/live/l2/{symbol}")
async def live_l2(symbol: str, levels: int = 10):
    """Return Level-2 depth-of-market for *symbol*.

    NOTE: The current implementation returns a realistic *mock* dataset
    because ``async_rithmic`` does not yet include a DOM subscription.
    The ``_mock: true`` flag in the response indicates this.  Once DOM
    support is wired (see ``RithmicPositionEngine.get_l2`` docstring),
    this endpoint will return live data automatically.

    Path params:
        symbol — Instrument symbol (case-insensitive).

    Query params:
        levels — Number of price levels per side (1–20, default 10).

    Returns:
        ``{ "ok": true, "symbol": "MES", "bids": [...], "asks": [...],
            "source": "live"|"mock" }``
    """
    sym = symbol.upper()
    levels = max(1, min(levels, 20))

    engine = _get_position_engine()
    if engine is None:
        return JSONResponse(
            {"ok": False, "error": "RithmicPositionEngine not available"},
            status_code=503,
        )

    l2 = await engine.get_l2(sym, levels=levels)
    source = "live" if not l2.get("_mock") else "mock"
    l2_clean = {k: v for k, v in l2.items() if not k.startswith("_")}

    return JSONResponse(
        {
            "ok": True,
            "symbol": sym,
            "source": source,
            "levels": levels,
            **l2_clean,
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.get("/api/rithmic/live/trades/{symbol}")
async def live_trades(symbol: str, n: int = 20):
    """Return the *n* most recent time-and-sales trades for *symbol*.

    Reads from ``ticks:live:{symbol}`` in Redis (rolling 300-tick list,
    written by the TICKER_PLANT ``on_tick`` callback) and converts raw
    tick dicts to the trade format.

    Falls back to a static mock dataset in offline / paper-trading mode.

    Path params:
        symbol — Instrument symbol (case-insensitive).

    Query params:
        n — Maximum number of trades to return (1–300, default 20).

    Returns:
        ``{ "ok": true, "symbol": "MES", "trades": [...], "count": N,
            "source": "live"|"mock" }``
    """
    sym = symbol.upper()
    n = max(1, min(n, 300))

    engine = _get_position_engine()
    if engine is None:
        return JSONResponse(
            {"ok": False, "error": "RithmicPositionEngine not available"},
            status_code=503,
        )

    trades = await engine.get_recent_trades(sym, n=n)
    source = "mock" if (trades and trades[0].get("_mock")) else "live"
    trades_clean = [{k: v for k, v in t.items() if not k.startswith("_")} for t in trades]

    return JSONResponse(
        {
            "ok": True,
            "symbol": sym,
            "trades": trades_clean,
            "count": len(trades_clean),
            "source": source,
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )


@router.get("/api/rithmic/live/status")
async def live_status():
    """Return the combined status of the RithmicPositionEngine.

    Aggregates:
      - ``rithmic:health`` Redis key (data-service lifespan writes this)
      - Per-plant connection states from ``rithmic:connection:{plant}``
      - Current subscribed symbols from the stream manager
      - Whether ``RITHMIC_LIVE_DATA=1`` is set

    Returns:
        ``{ "ok": true, "connected": bool, "account_key": "...",
            "subscribed_symbols": [...], "plant_states": {...},
            "live_data_env": "0"|"1", "pnl_connected": bool,
            "order_connected": bool, "history_connected": bool }``
    """
    sm = get_stream_manager()
    plant_states = sm.get_plant_states()

    health: dict[str, Any] = {
        "connected": False,
        "account_key": "",
        "live_data_env": os.getenv("RITHMIC_LIVE_DATA", "0"),
        "ts": "",
        "error": "",
    }
    try:
        from core.cache import REDIS_AVAILABLE, _r

        if REDIS_AVAILABLE and _r is not None:
            raw = _r.hgetall("rithmic:health")
            if raw:
                for k, v in raw.items():
                    key_s = k.decode() if isinstance(k, bytes) else str(k)
                    val_s = v.decode() if isinstance(v, bytes) else str(v)
                    if key_s == "connected":
                        health["connected"] = val_s == "true"
                    else:
                        health[key_s] = val_s
    except Exception:
        pass

    return JSONResponse(
        {
            "ok": True,
            "connected": health["connected"],
            "account_key": health.get("account_key", ""),
            "live_data_env": health.get("live_data_env", "0"),
            "subscribed_symbols": sorted(sm._subscribed_symbols),
            "plant_states": plant_states,
            "pnl_connected": sm.is_pnl_connected,
            "order_connected": sm.is_order_connected,
            "history_connected": sm.is_history_connected,
            "ticker_connected": sm._connected,
            "last_health_ts": health.get("ts", ""),
            "timestamp": datetime.now(tz=_EST).isoformat(),
        }
    )
