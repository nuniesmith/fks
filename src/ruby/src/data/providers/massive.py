"""Massive.com provider adapter for the DataFactory.

Wraps the synchronous :class:`~lib.integrations.massive_client.MassiveDataProvider`
REST client, bridging its blocking calls into the async DataFactory pipeline
via :func:`asyncio.to_thread`.

Supported asset class : CME futures only.
Supported intervals   : 1m, 5m, 15m, 1h, 1d
                        (5m / 15m / 1h are fetched at 1-minute resolution
                         and resampled client-side with pandas.)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pandas as pd

from core.logging_config import get_logger
from integrations.massive_client import (
    YAHOO_TO_MASSIVE_PRODUCT,
    _dropna_ohlc,
    _parse_timestamp_index,
    _resample_to_interval,
    get_massive_provider,
)

from ..registry.schemas import AssetClass, DataInterval, ProviderName
from .base import BaseProvider, OHLCVBar

if TYPE_CHECKING:
    from ..registry.schemas import AssetConfig

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Intervals that cannot be fetched natively and must be built from 1-minute
# bars by resampling client-side.
_NEEDS_RESAMPLE: frozenset[str] = frozenset({"5m", "15m", "1h"})


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class MassiveProvider(BaseProvider):
    """DataFactory adapter for the Massive.com CME futures data API.

    All network I/O is delegated to the existing synchronous
    :class:`~lib.integrations.massive_client.MassiveDataProvider` singleton,
    which is called inside :func:`asyncio.to_thread` so the event loop is
    never blocked.

    Contract resolution (``resolve_from_yahoo_at_date``) and the raw
    aggregate fetch (``list_futures_aggregates``) are executed in the *same*
    worker thread to avoid repeated thread-pool round-trips and to stay
    within the provider's :attr:`_lock` semantics.
    """

    # -- identity -----------------------------------------------------------

    @property
    def name(self) -> ProviderName:
        return ProviderName.MASSIVE

    # -- availability -------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """``True`` when the Massive API key is configured and the client is ready."""
        return get_massive_provider().is_available

    # -- capability queries -------------------------------------------------

    @property
    def max_history_days(self) -> int:
        """Two years of history are available via the Massive REST API."""
        return 730

    def supported_intervals(self) -> list[DataInterval]:
        return [
            DataInterval.ONE_MIN,
            DataInterval.FIVE_MIN,
            DataInterval.FIFTEEN_MIN,
            DataInterval.ONE_HOUR,
            DataInterval.ONE_DAY,
        ]

    async def supports_symbol(
        self,
        symbol: str,
        config: AssetConfig,
    ) -> bool:
        """Return ``True`` only for CME futures with a known Massive product.

        The check converts the provider symbol to its Yahoo-style ticker
        (appending ``=F`` when absent) and verifies it appears in the
        :data:`~lib.integrations.massive_client.YAHOO_TO_MASSIVE_PRODUCT`
        mapping.
        """
        if config.asset_class is not AssetClass.FUTURES_CME:
            return False
        yahoo_ticker = _to_yahoo_ticker(config)
        return yahoo_ticker in YAHOO_TO_MASSIVE_PRODUCT

    # -- bar fetching -------------------------------------------------------

    async def fetch_bars(
        self,
        symbol: str,
        interval: DataInterval,
        start: datetime,
        end: datetime,
        config: AssetConfig,
    ) -> list[OHLCVBar]:
        """Fetch historical OHLCV bars from Massive for *symbol* over [*start*, *end*).

        Steps
        -----
        1. Validate that the provider is available and the symbol is mapped.
        2. Resolve the active contract ticker for the requested date window
           via :meth:`~MassiveDataProvider.resolve_from_yahoo_at_date`.
        3. Fetch raw 1-minute (or daily) aggregates from the REST API.
        4. Parse timestamps, drop incomplete bars, and optionally resample
           to the requested interval using pandas.
        5. Normalise every row to an :class:`~.base.OHLCVBar` with a
           UTC-aware ``bar_time``.

        Raises
        ------
        RuntimeError
            If ``MASSIVE_API_KEY`` is not configured.
        ValueError
            If the symbol has no Massive product-code mapping.
        """
        provider = get_massive_provider()
        if not provider.is_available:
            raise RuntimeError(
                "Massive provider is unavailable — MASSIVE_API_KEY is not set "
                "or the massive package could not be initialised."
            )

        yahoo_ticker = _to_yahoo_ticker(config)
        if yahoo_ticker not in YAHOO_TO_MASSIVE_PRODUCT:
            raise ValueError(
                f"No Massive product-code mapping for Yahoo ticker '{yahoo_ticker}' "
                f"(symbol='{symbol}').  Add it to YAHOO_TO_MASSIVE_PRODUCT in "
                "lib/integrations/massive_client.py."
            )

        interval_str = interval.value  # e.g. "1m", "5m", "1d"
        # Massive REST API only supports "1sec", "1min", and "1day".
        # Everything intraday is fetched at 1-minute resolution; multi-minute
        # intervals are resampled afterwards.
        resolution = "1min" if interval_str != "1d" else "1day"
        needs_resample = interval_str in _NEEDS_RESAMPLE

        # Normalise start / end to UTC for consistent API formatting.
        start_utc = _ensure_utc(start)
        end_utc = _ensure_utc(end)

        # ISO-8601 strings expected by the Massive aggregates endpoint.
        start_api = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_api = end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Date strings for contract resolution (date portion only).
        date_str = start_utc.strftime("%Y-%m-%d")
        end_date_str = end_utc.strftime("%Y-%m-%d")

        log.debug(
            "fetch_bars: starting Massive fetch",
            symbol=symbol,
            yahoo_ticker=yahoo_ticker,
            interval=interval_str,
            resolution=resolution,
            start=start_api,
            end=end_api,
        )

        # ------------------------------------------------------------------
        # All blocking work runs in a single thread-pool worker.
        # ------------------------------------------------------------------
        def _sync_fetch() -> pd.DataFrame:
            # Step 1 — resolve the front-month contract for this date window.
            massive_ticker = provider.resolve_from_yahoo_at_date(
                yahoo_ticker,
                date_str,
                end_date_str=end_date_str,
            )
            if not massive_ticker:
                log.warning(
                    "Massive contract resolution returned None",
                    yahoo_ticker=yahoo_ticker,
                    date_str=date_str,
                    end_date_str=end_date_str,
                )
                return pd.DataFrame()

            log.debug(
                "Resolved Massive contract",
                yahoo_ticker=yahoo_ticker,
                massive_ticker=massive_ticker,
                resolution=resolution,
            )

            # Step 2 — fetch raw aggregates (thread-safe via provider._lock).
            client = provider._client  # type safety: is_available guarantees non-None
            with provider._lock:
                aggs = list(
                    client.list_futures_aggregates(  # type: ignore[union-attr]
                        ticker=massive_ticker,
                        resolution=resolution,
                        window_start_gte=start_api,
                        window_start_lte=end_api,
                        limit=50_000,
                        sort="asc",
                    )
                )

            if not aggs:
                log.debug(
                    "No aggregates returned from Massive",
                    massive_ticker=massive_ticker,
                    interval=interval_str,
                    start=start_api,
                    end=end_api,
                )
                return pd.DataFrame()

            # Step 3 — convert to DataFrame.
            rows = [
                {
                    "Open": getattr(agg, "open", None),
                    "High": getattr(agg, "high", None),
                    "Low": getattr(agg, "low", None),
                    "Close": getattr(agg, "close", None),
                    "Volume": float(getattr(agg, "volume", 0) or 0),
                    "timestamp": getattr(agg, "window_start", None),
                }
                for agg in aggs
            ]
            df = pd.DataFrame(rows)

            # Step 4 — parse timestamps → tz-aware EST DatetimeIndex.
            df = _parse_timestamp_index(df)

            # Step 5 — drop bars with any missing OHLC value.
            df = _dropna_ohlc(df)

            # Step 6 — resample to the requested interval when needed.
            if needs_resample and not df.empty:
                df = _resample_to_interval(df, interval_str)

            return df

        df: pd.DataFrame = await asyncio.to_thread(_sync_fetch)

        if df.empty:
            log.debug(
                "Massive returned empty DataFrame after processing",
                symbol=symbol,
                interval=interval_str,
            )
            return []

        # ------------------------------------------------------------------
        # Normalise DataFrame rows → OHLCVBar dataclasses.
        # The index is EST (from _parse_timestamp_index); convert to UTC.
        # ------------------------------------------------------------------
        bars: list[OHLCVBar] = []
        for ts, row in df.iterrows():
            bar_time = _ts_to_utc(ts)

            # Client-side range guard — the API may return partial bars at
            # the edges of the requested window.
            if bar_time < start_utc or bar_time >= end_utc:
                continue

            bars.append(
                OHLCVBar(
                    symbol=symbol,
                    interval=interval_str,
                    bar_time=bar_time,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                    source=ProviderName.MASSIVE.value,
                )
            )

        log.info(
            "Massive fetch complete",
            symbol=symbol,
            yahoo_ticker=yahoo_ticker,
            interval=interval_str,
            bar_count=len(bars),
        )
        return bars


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _to_yahoo_ticker(config: AssetConfig) -> str:
    """Return the Yahoo-style ticker for *config*, ensuring it ends with ``=F``.

    For CME futures the provider_symbol_map will typically contain a
    ``"yfinance"`` key such as ``"GC=F"``.  When the Massive key is absent
    (the common case), ``provider_symbol`` falls back to the raw symbol
    (e.g. ``"MGC"``), so we append ``=F`` to form the correct Yahoo ticker.
    """
    ticker = config.provider_symbol(ProviderName.MASSIVE)
    if not ticker.endswith("=F"):
        ticker = f"{ticker}=F"
    return ticker


def _ensure_utc(dt: datetime) -> datetime:
    """Return *dt* as a timezone-aware UTC :class:`datetime`."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _ts_to_utc(ts: object) -> datetime:
    """Convert a pandas :class:`~pandas.Timestamp` (or similar) to UTC datetime."""
    # ts arrives as a pd.Timestamp from df.iterrows(); .to_pydatetime() gives
    # a timezone-aware datetime (EST, set by _parse_timestamp_index).
    pdt: datetime = ts.to_pydatetime()  # type: ignore[attr-defined]
    if pdt.tzinfo is None:
        return pdt.replace(tzinfo=UTC)
    return pdt.astimezone(UTC)
