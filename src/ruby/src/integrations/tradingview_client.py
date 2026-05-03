"""
TradingView Real-Time Data Client
===================================
WebSocket-based real-time market data integration using the ``TradingView-API``
package (v1.0.1).  Provides a singleton async client that lazily connects to
TradingView's data feed, manages symbol subscriptions via ``ChartSession``,
and publishes incoming tick data to Redis pub/sub channels for consumption
by other FKS services (engine, dashboard SSE, alerting).

Architecture
------------
::

    TradingView WebSocket servers
        ↕  (wss)
    TradingView-API  (sync library)
        ↕  (asyncio.to_thread / executor bridge)
    TradingViewDataClient                       (this module)
        ├── on_connect / on_login               — lifecycle events
        ├── on_data                             — tick dispatch
        ├── on_error / on_close                 — error handling
        └── Redis publish  →  tv:ticks:{symbol} — fan-out to consumers

    Other FKS services
        └── Redis subscribe  ←  tv:ticks:{symbol}

Connection lifecycle
--------------------
The client is created lazily by :func:`get_tv_client` and connects on first
use (``connect()``).  The underlying ``TradingView-API`` library is
synchronous, so all blocking calls are wrapped via ``asyncio.to_thread()``
to avoid starving the event loop.

Subscription management
-----------------------
Each call to :meth:`subscribe` creates a ``ChartSession`` for the given
``EXCHANGE:SYMBOL`` pair.  Active sessions are tracked in
``_subscriptions`` and can be torn down individually via
:meth:`unsubscribe` or all at once via :meth:`disconnect`.

Redis publishing
----------------
Every incoming tick is published to ``tv:ticks:{symbol}`` as a JSON blob::

    {
        "symbol": "BINANCE:BTCUSDT",
        "price": 67432.10,
        "volume": 1.234,
        "timestamp": "2024-06-15T14:30:00+00:00",
        "source": "tradingview"
    }

Services can subscribe with ``SUBSCRIBE tv:ticks:BINANCE:BTCUSDT`` or use
pattern subscriptions ``PSUBSCRIBE tv:ticks:*``.

Environment variables
---------------------
``TV_SESSION_ID``
    Optional TradingView session token for authenticated access (premium
    data, more symbols).  When omitted the client connects anonymously
    with free-tier limitations.

``REDIS_URL``
    Redis connection URL used for tick publishing.
    Default: ``redis://localhost:6379/0``.

Usage — async
-------------
::

    from integrations.tradingview_client import get_tv_client

    client = get_tv_client()
    await client.connect()

    async for tick in client.subscribe("BINANCE:BTCUSDT"):
        print(tick)

    await client.unsubscribe("BINANCE:BTCUSDT")
    await client.disconnect()

Usage — singleton lifecycle
---------------------------
::

    from integrations.tradingview_client import (
        get_tv_client,
        reset_tv_client,
    )

    client = get_tv_client()          # always the same instance
    await client.connect()
    # ... at shutdown ...
    await client.disconnect()
    reset_tv_client()                 # discard singleton (tests)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import structlog

# ---------------------------------------------------------------------------
# Lazy TradingView-API import guard
# ---------------------------------------------------------------------------
# The ``TradingView-API`` pip package may not be installed in every
# environment (e.g. CI, lightweight dev containers).  We defer the import
# and surface a clear error only when the client is actually used.

_TV_AVAILABLE = False
_TV_IMPORT_ERROR: str | None = None

try:
    from TradingView import ChartSession, SymbolSearch, TradingViewClient  # type: ignore[import-untyped]

    _TV_AVAILABLE = True
except ImportError as _exc:
    _TV_IMPORT_ERROR = (
        f"TradingView-API package is not installed ({_exc}). Install it with:  pip install TradingView-API==1.0.1"
    )

    # Placeholder symbols so the rest of the module can be parsed/imported
    # without raising NameError at class definition time.
    TradingViewClient = None  # type: ignore[assignment,misc]
    ChartSession = None  # type: ignore[assignment,misc]
    SymbolSearch = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Logger (structlog — project convention)
# ---------------------------------------------------------------------------

logger = structlog.get_logger("integrations.tradingview_client")

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"

# Redis channel prefix for tick data fan-out
_TICK_CHANNEL_PREFIX = "tv:ticks"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TradingViewError(Exception):
    """Base exception for all TradingView client errors."""


class TradingViewConnectionError(TradingViewError):
    """Raised when the TradingView WebSocket connection fails."""


class TradingViewSubscriptionError(TradingViewError):
    """Raised when a symbol subscription cannot be created or maintained."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_tv_api() -> None:
    """Raise :exc:`TradingViewError` if the TradingView-API package is missing."""
    if not _TV_AVAILABLE:
        raise TradingViewError(_TV_IMPORT_ERROR)


def _get_redis_client() -> Any | None:
    """Return a Redis client for publishing ticks, or ``None`` if unavailable.

    Tries the project-level cache module first (shared connection pool), then
    falls back to creating a standalone ``redis.Redis`` from ``REDIS_URL``.
    """
    # 1. Try project cache (shared pool, already connected)
    try:
        from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

        if REDIS_AVAILABLE and _r is not None:
            return _r
    except Exception:
        pass

    # 2. Fallback: create our own connection from REDIS_URL
    try:
        import redis as redis_lib  # type: ignore[import-untyped]

        url = os.getenv("REDIS_URL", _DEFAULT_REDIS_URL)
        client = redis_lib.from_url(url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def _get_async_redis_client() -> Any | None:
    """Return an async Redis client for publishing ticks, or ``None``."""
    try:
        import redis.asyncio as redis_async  # type: ignore[import-untyped]

        url = os.getenv("REDIS_URL", _DEFAULT_REDIS_URL)
        return redis_async.from_url(url, decode_responses=True)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core client
# ---------------------------------------------------------------------------


class TradingViewDataClient:
    """Async wrapper around the synchronous ``TradingView-API`` library.

    The underlying library uses blocking WebSocket I/O.  This class bridges
    to asyncio via ``asyncio.to_thread()`` so the event loop is never
    blocked.

    The client is **lazy**: the WebSocket connection is not established until
    :meth:`connect` is called explicitly.  Subscriptions are tracked
    internally and cleaned up on :meth:`disconnect`.

    Args:
        session_id: TradingView session token.  Falls back to
            ``TV_SESSION_ID`` env var.  ``None`` means anonymous access.
    """

    def __init__(self, session_id: str | None = None) -> None:
        self._session_id: str | None = session_id or os.getenv("TV_SESSION_ID") or None

        # Internal state — populated lazily
        self._client: Any | None = None
        self._connected: bool = False
        self._connecting: bool = False

        # symbol → ChartSession mapping
        self._subscriptions: dict[str, Any] = {}

        # asyncio queues for each subscribed symbol (tick fan-out)
        self._tick_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}

        # Background tasks for feed loops
        self._feed_tasks: dict[str, asyncio.Task[None]] = {}

        # Redis for tick publishing
        self._redis: Any | None = None
        self._async_redis: Any | None = None

        # Shutdown event
        self._shutdown_event = asyncio.Event()

        logger.info(
            "TradingViewDataClient initialised",
            session_id_set=self._session_id is not None,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """``True`` when the WebSocket connection is established."""
        return self._connected

    @property
    def active_subscriptions(self) -> list[str]:
        """List of currently subscribed symbols."""
        return list(self._subscriptions.keys())

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_connect(self) -> None:
        """Called when the WebSocket connection is established."""
        self._connected = True
        logger.info("TradingView WebSocket connected")

    def on_login(self, session_info: dict[str, Any] | None = None) -> None:
        """Called after successful authentication (or anonymous login)."""
        logger.info(
            "TradingView session authenticated",
            anonymous=self._session_id is None,
            session_info=session_info,
        )

    def on_data(self, symbol: str, data: dict[str, Any]) -> None:
        """Called on every incoming tick / bar update.

        Normalises the data and pushes it to the per-symbol asyncio queue
        and publishes to Redis.
        """
        tick = {
            "symbol": symbol,
            "price": data.get("price") or data.get("close") or data.get("lp"),
            "volume": data.get("volume") or data.get("volume_real"),
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "tradingview",
            "raw": data,
        }

        # Push to local asyncio queue (for async-for consumers)
        queue = self._tick_queues.get(symbol)
        if queue is not None:
            try:
                queue.put_nowait(tick)
            except asyncio.QueueFull:
                # Drop oldest tick to avoid unbounded memory growth
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                queue.put_nowait(tick)

        # Publish to Redis channel for cross-service fan-out
        self._publish_tick_to_redis(symbol, tick)

        logger.debug("tick_received", symbol=symbol, price=tick.get("price"))

    def on_error(self, error: Exception | str) -> None:
        """Called when a WebSocket or protocol error occurs."""
        logger.error("TradingView error", error=str(error))

    def on_close(self) -> None:
        """Called when the WebSocket connection is closed."""
        self._connected = False
        logger.warning("TradingView WebSocket closed")

    # ------------------------------------------------------------------
    # Redis publishing
    # ------------------------------------------------------------------

    def _publish_tick_to_redis(self, symbol: str, tick: dict[str, Any]) -> None:
        """Publish a tick to ``tv:ticks:{symbol}`` Redis channel.

        Non-fatal — if Redis is unavailable the tick is silently dropped
        (it is still delivered via the local asyncio queue).
        """
        try:
            r = self._redis
            if r is None:
                r = _get_redis_client()
                self._redis = r
            if r is None:
                return

            channel = f"{_TICK_CHANNEL_PREFIX}:{symbol}"
            # Strip the 'raw' field to keep the published message lean
            payload = {k: v for k, v in tick.items() if k != "raw"}
            r.publish(channel, json.dumps(payload))
        except Exception as exc:
            logger.debug("redis_publish_failed", symbol=symbol, error=str(exc))

    async def _publish_tick_to_redis_async(self, symbol: str, tick: dict[str, Any]) -> None:
        """Async variant of Redis tick publishing."""
        try:
            ar = self._async_redis
            if ar is None:
                ar = _get_async_redis_client()
                self._async_redis = ar
            if ar is None:
                return

            channel = f"{_TICK_CHANNEL_PREFIX}:{symbol}"
            payload = {k: v for k, v in tick.items() if k != "raw"}
            await ar.publish(channel, json.dumps(payload))
        except Exception as exc:
            logger.debug("redis_async_publish_failed", symbol=symbol, error=str(exc))

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish the TradingView WebSocket connection.

        This method is idempotent — calling it when already connected is a
        no-op.  The blocking ``TradingViewClient()`` constructor is
        dispatched to a thread so the event loop is not blocked.

        Raises:
            TradingViewError: If the TradingView-API package is not installed.
            TradingViewConnectionError: If the WebSocket handshake fails.
        """
        _require_tv_api()

        if self._connected:
            logger.debug("connect called but already connected")
            return

        if self._connecting:
            logger.debug("connect already in progress, waiting")
            # Wait for the in-flight connect to finish
            while self._connecting:
                await asyncio.sleep(0.1)
            return

        self._connecting = True
        try:
            logger.info("Connecting to TradingView WebSocket …")
            self._client = await asyncio.to_thread(self._create_client)
            self.on_connect()
            self.on_login()
        except TradingViewError:
            raise
        except Exception as exc:
            raise TradingViewConnectionError(f"Failed to connect to TradingView: {exc}") from exc
        finally:
            self._connecting = False

    def _create_client(self) -> Any:
        """Blocking helper — instantiate the sync ``TradingViewClient``.

        Called inside ``asyncio.to_thread()`` from :meth:`connect`.
        """
        _require_tv_api()

        kwargs: dict[str, Any] = {}
        if self._session_id:
            kwargs["session_id"] = self._session_id

        try:
            client = TradingViewClient(**kwargs)  # type: ignore[misc]
        except Exception as exc:
            raise TradingViewConnectionError(f"TradingViewClient constructor failed: {exc}") from exc

        return client

    async def disconnect(self) -> None:
        """Tear down all subscriptions and close the WebSocket.

        Safe to call multiple times.
        """
        logger.info(
            "Disconnecting TradingView client",
            active_subs=len(self._subscriptions),
        )

        self._shutdown_event.set()

        # Cancel all feed tasks
        for _symbol, task in list(self._feed_tasks.items()):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._feed_tasks.clear()

        # Unsubscribe all
        symbols = list(self._subscriptions.keys())
        for sym in symbols:
            await self._remove_subscription(sym)

        # Close the underlying client
        if self._client is not None:
            try:
                await asyncio.to_thread(self._close_client)
            except Exception as exc:
                logger.warning("Error closing TradingView client", error=str(exc))
            self._client = None

        # Close async redis
        if self._async_redis is not None:
            with contextlib.suppress(Exception):
                await self._async_redis.close()
            self._async_redis = None

        self._connected = False
        self._shutdown_event.clear()
        self.on_close()

    def _close_client(self) -> None:
        """Blocking close — called inside ``asyncio.to_thread()``."""
        if self._client is not None:
            with contextlib.suppress(Exception):
                if hasattr(self._client, "close"):
                    self._client.close()
                elif hasattr(self._client, "disconnect"):
                    self._client.disconnect()

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    async def subscribe(self, symbol: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to real-time data for *symbol* and yield tick dicts.

        Creates a ``ChartSession`` for the given ``EXCHANGE:SYMBOL`` string
        (e.g. ``"BINANCE:BTCUSDT"``, ``"CME_MINI:ES1!"``) and yields
        normalised tick dictionaries as they arrive.

        The subscription is tracked internally and can be cancelled via
        :meth:`unsubscribe` or :meth:`disconnect`.

        Args:
            symbol: TradingView symbol in ``EXCHANGE:SYMBOL`` format.

        Yields:
            Tick dictionaries with keys ``symbol``, ``price``, ``volume``,
            ``timestamp``, ``source``.

        Raises:
            TradingViewError: If the package is not installed.
            TradingViewConnectionError: If not connected.
            TradingViewSubscriptionError: If the ChartSession fails.
        """
        _require_tv_api()

        if not self._connected or self._client is None:
            await self.connect()

        if symbol in self._subscriptions:
            logger.info("Already subscribed, attaching to existing feed", symbol=symbol)
        else:
            await self._create_subscription(symbol)

        # Ensure a queue exists for this symbol
        if symbol not in self._tick_queues:
            self._tick_queues[symbol] = asyncio.Queue(maxsize=1000)

        queue = self._tick_queues[symbol]
        logger.info("subscribe_yielding", symbol=symbol)

        try:
            while not self._shutdown_event.is_set():
                try:
                    tick = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield tick
                except TimeoutError:
                    # No tick within 1 s — loop back and check shutdown flag
                    continue
        except asyncio.CancelledError:
            logger.debug("subscribe iterator cancelled", symbol=symbol)
            raise

    async def _create_subscription(self, symbol: str) -> None:
        """Create a ``ChartSession`` for *symbol* in a background thread.

        The session is stored in ``_subscriptions`` and a background
        asyncio task is started to poll the session for data.
        """
        _require_tv_api()

        logger.info("Creating ChartSession", symbol=symbol)

        try:
            session = await asyncio.to_thread(self._create_chart_session, symbol)
        except Exception as exc:
            raise TradingViewSubscriptionError(f"Failed to create ChartSession for {symbol}: {exc}") from exc

        self._subscriptions[symbol] = session

        if symbol not in self._tick_queues:
            self._tick_queues[symbol] = asyncio.Queue(maxsize=1000)

        # Start background feed task
        task = asyncio.create_task(
            self._feed_loop(symbol, session),
            name=f"tv-feed-{symbol}",
        )
        self._feed_tasks[symbol] = task

        logger.info("Subscription active", symbol=symbol)

    def _create_chart_session(self, symbol: str) -> Any:
        """Blocking helper — create a ``ChartSession`` (runs in thread)."""
        _require_tv_api()
        return ChartSession(self._client, symbol)  # type: ignore[misc]

    async def _feed_loop(self, symbol: str, session: Any) -> None:
        """Background task that polls a ``ChartSession`` for new data.

        Runs until the subscription is removed or the client shuts down.
        """
        logger.debug("Feed loop started", symbol=symbol)

        try:
            while not self._shutdown_event.is_set():
                try:
                    data = await asyncio.to_thread(self._read_session, session)
                    if data is not None:
                        self.on_data(symbol, data)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.on_error(exc)
                    # Back off briefly on error before retrying
                    await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.debug("Feed loop cancelled", symbol=symbol)
        finally:
            logger.debug("Feed loop exited", symbol=symbol)

    def _read_session(self, session: Any) -> dict[str, Any] | None:
        """Blocking read from a ``ChartSession`` (runs in thread).

        Returns a data dict or ``None`` if no data is available.
        """
        try:
            if hasattr(session, "get_data"):
                return session.get_data()  # type: ignore[no-any-return]
            if hasattr(session, "data"):
                return session.data  # type: ignore[no-any-return]
            if hasattr(session, "read"):
                return session.read()  # type: ignore[no-any-return]
        except Exception:
            return None
        return None

    async def unsubscribe(self, symbol: str) -> None:
        """Remove the subscription for *symbol*.

        Cancels the background feed task and closes the ``ChartSession``.
        Safe to call for symbols that are not currently subscribed.

        Args:
            symbol: The symbol to unsubscribe from.
        """
        if symbol not in self._subscriptions:
            logger.debug("unsubscribe called for unknown symbol", symbol=symbol)
            return

        # Cancel feed task
        task = self._feed_tasks.pop(symbol, None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        await self._remove_subscription(symbol)
        logger.info("Unsubscribed", symbol=symbol)

    async def _remove_subscription(self, symbol: str) -> None:
        """Remove a subscription's session and queue."""
        session = self._subscriptions.pop(symbol, None)
        if session is not None:
            try:
                await asyncio.to_thread(self._close_session, session)
            except Exception as exc:
                logger.debug("Error closing ChartSession", symbol=symbol, error=str(exc))

        self._tick_queues.pop(symbol, None)

    def _close_session(self, session: Any) -> None:
        """Blocking close of a ``ChartSession`` (runs in thread)."""
        with contextlib.suppress(Exception):
            if hasattr(session, "close"):
                session.close()
            elif hasattr(session, "delete"):
                session.delete()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> TradingViewDataClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()


# ---------------------------------------------------------------------------
# Module-level singleton registry
# ---------------------------------------------------------------------------

_tv_client: TradingViewDataClient | None = None


def get_tv_client(
    session_id: str | None = None,
) -> TradingViewDataClient:
    """Return the module-level :class:`TradingViewDataClient` singleton.

    The *session_id* argument is honoured **only on first call**; subsequent
    calls return the cached instance regardless of arguments supplied.

    Args:
        session_id: Override ``TV_SESSION_ID`` environment variable.

    Returns:
        Shared :class:`TradingViewDataClient` instance.
    """
    global _tv_client
    if _tv_client is None:
        _tv_client = TradingViewDataClient(session_id=session_id)
    return _tv_client


def reset_tv_client() -> None:
    """Discard the singleton (primarily for use in tests).

    The next call to :func:`get_tv_client` will create a fresh
    :class:`TradingViewDataClient`.  Note: this does **not** disconnect the
    existing client — call :meth:`TradingViewDataClient.disconnect` before
    resetting if you need a clean shutdown.
    """
    global _tv_client
    _tv_client = None
    logger.debug("TradingViewDataClient singleton reset")


# ---------------------------------------------------------------------------
# Public API summary
# ---------------------------------------------------------------------------

__all__ = [
    "TradingViewDataClient",
    "TradingViewError",
    "TradingViewConnectionError",
    "TradingViewSubscriptionError",
    "get_tv_client",
    "reset_tv_client",
]
