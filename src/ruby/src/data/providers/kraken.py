"""Kraken exchange provider adapter for the DataFactory.

Wraps the synchronous :class:`~lib.integrations.kraken_client.KrakenDataProvider`
REST client (public endpoints — no API key required for OHLCV data) and
paginates transparently across Kraken's 720-candle-per-call limit to cover
arbitrary date ranges.

Supported asset class : Crypto only.
Supported intervals   : 1m, 5m, 15m, 1h, 4h, 1d
                        (all fetched natively — Kraken supports all of these
                         as REST interval values.)
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pandas as pd

from core.logging_config import get_logger
from integrations.kraken_client import (
    INTERVAL_TO_KRAKEN_MINUTES,
    get_kraken_provider,
)

from ..registry.schemas import AssetClass, DataInterval, ProviderName
from .base import BaseProvider, OHLCVBar

if TYPE_CHECKING:
    from ..registry.schemas import AssetConfig

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Mirror the rate-limit delay used inside KrakenDataProvider so our
# pagination loop is consistent with the client's own throttling.
_PUBLIC_RATE_LIMIT: float = 0.35  # seconds between public API calls

# Maximum candles Kraken returns in a single OHLC response.
_MAX_CANDLES_PER_CALL: int = 720


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class KrakenProvider(BaseProvider):
    """DataFactory adapter for Kraken's public OHLCV REST API.

    Kraken returns at most :data:`_MAX_CANDLES_PER_CALL` (720) bars per
    request.  :meth:`fetch_bars` handles pagination automatically: it
    advances the ``since`` cursor after each response and stitches the
    chunks into a single deduplicated, sorted DataFrame before normalising
    to :class:`~.base.OHLCVBar` objects.

    All blocking network I/O is delegated to
    :class:`~lib.integrations.kraken_client.KrakenDataProvider` and wrapped
    in :func:`asyncio.to_thread` so the event loop is never blocked.
    """

    # -- identity -----------------------------------------------------------

    @property
    def name(self) -> ProviderName:
        return ProviderName.KRAKEN

    # -- availability -------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """``True`` when the Kraken REST client is initialised (no API key required for public endpoints)."""
        return get_kraken_provider().is_available

    # -- capability queries -------------------------------------------------

    @property
    def max_history_days(self) -> int:
        """Five years; intraday history is pagination-limited but covered."""
        return 1825

    def supported_intervals(self) -> list[DataInterval]:
        return [
            DataInterval.ONE_MIN,
            DataInterval.FIVE_MIN,
            DataInterval.FIFTEEN_MIN,
            DataInterval.ONE_HOUR,
            DataInterval.FOUR_HOUR,
            DataInterval.ONE_DAY,
        ]

    async def supports_symbol(
        self,
        symbol: str,
        config: AssetConfig,
    ) -> bool:
        """Return ``True`` only for crypto assets with a Kraken pair configured.

        The asset must have ``asset_class == CRYPTO`` *and* the
        ``provider_symbol_map`` must contain a ``"kraken"`` key, e.g.::

            provider_symbol_map={"kraken": "XXBTZUSD", ...}
        """
        if config.asset_class is not AssetClass.CRYPTO:
            return False
        return ProviderName.KRAKEN.value in config.provider_symbol_map

    # -- bar fetching -------------------------------------------------------

    async def fetch_bars(
        self,
        symbol: str,
        interval: DataInterval,
        start: datetime,
        end: datetime,
        config: AssetConfig,
    ) -> list[OHLCVBar]:
        """Fetch historical OHLCV bars from Kraken for *symbol* over [*start*, *end*).

        Steps
        -----
        1. Resolve the Kraken REST pair name from ``config.provider_symbol``.
        2. Map the :class:`DataInterval` to the Kraken ``interval`` integer
           (minutes).
        3. Paginate :meth:`~KrakenDataProvider.get_ohlcv` calls, advancing
           the ``since`` timestamp cursor after each chunk, until the end of
           the requested window is reached or no new data is returned.
        4. Concatenate all chunks, deduplicate on the timestamp index, and
           sort chronologically.
        5. Normalise each row to an :class:`~.base.OHLCVBar` with a
           UTC-aware ``bar_time``, filtering to the precise [*start*, *end*)
           window.

        Raises
        ------
        RuntimeError
            If the Kraken REST client is not available (e.g. ``requests``
            is not installed).
        ValueError
            If *interval* is not supported by Kraken.
        """
        provider = get_kraken_provider()
        if not provider.is_available:
            raise RuntimeError("Kraken REST client is not available — the 'requests' library may not be installed.")

        pair = config.provider_symbol(ProviderName.KRAKEN)  # e.g. "XXBTZUSD"
        interval_str = interval.value  # e.g. "1h", "4h"

        kraken_minutes = INTERVAL_TO_KRAKEN_MINUTES.get(interval_str)
        if kraken_minutes is None:
            raise ValueError(
                f"Interval '{interval_str}' is not supported by Kraken. "
                f"Supported intervals: {', '.join(INTERVAL_TO_KRAKEN_MINUTES.keys())}"
            )

        start_utc = _ensure_utc(start)
        end_utc = _ensure_utc(end)
        end_ts = int(end_utc.timestamp())

        log.debug(
            "fetch_bars: starting Kraken paginated fetch",
            symbol=symbol,
            pair=pair,
            interval=interval_str,
            kraken_minutes=kraken_minutes,
            start=start_utc.isoformat(),
            end=end_utc.isoformat(),
        )

        # ------------------------------------------------------------------
        # All blocking work (network calls + rate-limit sleeps) runs inside
        # a single asyncio.to_thread worker so the event loop stays free.
        # ------------------------------------------------------------------
        def _sync_paginate() -> pd.DataFrame:
            all_frames: list[pd.DataFrame] = []
            current_since = int(start_utc.timestamp())
            iteration = 0

            while True:
                iteration += 1
                log.debug(
                    "Kraken OHLCV page request",
                    pair=pair,
                    interval=interval_str,
                    since=current_since,
                    iteration=iteration,
                )

                df = provider.get_ohlcv(
                    pair,
                    interval=interval_str,
                    since_timestamp=current_since,
                )

                if df.empty:
                    log.debug(
                        "Kraken returned empty page — stopping pagination",
                        pair=pair,
                        iteration=iteration,
                    )
                    break

                all_frames.append(df)

                # Advance the cursor to just after the last returned candle.
                # Kraken timestamps in the index are in EST (set by the client);
                # convert back to a Unix timestamp for the next `since` param.
                assert isinstance(df.index, pd.DatetimeIndex)
                last_idx: pd.Timestamp = df.index[-1]  # type: ignore[assignment]
                next_since = int(last_idx.timestamp()) + kraken_minutes * 60

                if next_since >= end_ts:
                    # We've reached (or passed) the requested end boundary.
                    break

                if next_since <= current_since:
                    # Defensive guard: no forward progress — avoid infinite loop.
                    log.warning(
                        "Kraken pagination cursor did not advance — aborting",
                        pair=pair,
                        current_since=current_since,
                        next_since=next_since,
                    )
                    break

                current_since = next_since

                # Respect Kraken's public-endpoint rate limit between pages.
                time.sleep(_PUBLIC_RATE_LIMIT)

            if not all_frames:
                return pd.DataFrame()

            # Stitch all pages into one DataFrame, dedup, and sort.
            combined: pd.DataFrame = pd.concat(all_frames)
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
            return combined

        df: pd.DataFrame = await asyncio.to_thread(_sync_paginate)

        if df.empty:
            log.debug(
                "Kraken returned no data after pagination",
                symbol=symbol,
                interval=interval_str,
            )
            return []

        # ------------------------------------------------------------------
        # Normalise DataFrame rows → OHLCVBar dataclasses.
        # The index from get_ohlcv() is EST; convert each timestamp to UTC.
        # ------------------------------------------------------------------
        bars: list[OHLCVBar] = []
        for ts, row in df.iterrows():
            bar_time = _ts_to_utc(ts)

            # Client-side precision filter — trim any bars that fall outside
            # the exact [start, end) window returned by the paginator.
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
                    source=ProviderName.KRAKEN.value,
                )
            )

        log.info(
            "Kraken fetch complete",
            symbol=symbol,
            pair=pair,
            interval=interval_str,
            bar_count=len(bars),
        )
        return bars


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _ensure_utc(dt: datetime) -> datetime:
    """Return *dt* as a timezone-aware UTC :class:`datetime`."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _ts_to_utc(ts: object) -> datetime:
    """Convert a pandas :class:`~pandas.Timestamp` index value to a UTC datetime.

    :func:`~lib.integrations.kraken_client.KrakenDataProvider.get_ohlcv`
    converts the raw Unix timestamps to an EST-localised
    :class:`~pandas.DatetimeIndex`.  We undo that localisation here to
    produce the canonical UTC ``bar_time`` stored in :class:`~.base.OHLCVBar`.
    """
    pdt: datetime = ts.to_pydatetime()  # type: ignore[attr-defined]
    if pdt.tzinfo is None:
        return pdt.replace(tzinfo=UTC)
    return pdt.astimezone(UTC)
