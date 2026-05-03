"""Yahoo Finance provider adapter for the DataFactory.

Uses :mod:`yfinance` directly — no internal wrapper exists for historical
fetching in the canonical DataFactory style.  The provider is primarily a
fallback source for ETFs and equities, and also covers CME futures when a
``"yfinance"`` entry exists in the asset's ``provider_symbol_map``
(e.g. ``"GC=F"`` for Micro Gold, ``"ES=F"`` for Micro E-mini S&P 500).

Supported asset classes : ETF, EQUITY (always); FUTURES_CME (when a
                          ``"yfinance"`` symbol override is configured).
Supported intervals     : 1m, 5m, 15m, 1h, 1d
                          (4h is not available via yfinance and raises
                          :exc:`ValueError` if requested.)

.. warning::
    yfinance imposes strict per-interval history depth limits that are
    enforced server-side:

    =========  =============
    Interval   Max history
    =========  =============
    1m         7 days
    5m         60 days
    15m        60 days
    1h         730 days
    1d         unlimited
    =========  =============

    ``max_history_days`` is set conservatively to 60 so the
    :class:`~lib.data_factory.providers.router.ProviderRouter` prefers
    Massive or Kraken for longer look-backs.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from core.logging_config import get_logger

from ..registry.schemas import AssetClass, DataInterval, ProviderName
from .base import BaseProvider, OHLCVBar

if TYPE_CHECKING:
    import pandas as pd

    from ..registry.schemas import AssetConfig

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Map DataInterval values → yfinance interval strings.
# FOUR_HOUR is intentionally absent — yfinance does not support 4-hour bars.
_YF_INTERVAL: dict[str, str] = {
    DataInterval.ONE_MIN.value: "1m",
    DataInterval.FIVE_MIN.value: "5m",
    DataInterval.FIFTEEN_MIN.value: "15m",
    DataInterval.ONE_HOUR.value: "1h",
    DataInterval.ONE_DAY.value: "1d",
}

# Asset classes that yfinance always supports (no symbol-map check needed).
_ALWAYS_SUPPORTED: frozenset[AssetClass] = frozenset({AssetClass.ETF, AssetClass.EQUITY})


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class YFinanceProvider(BaseProvider):
    """DataFactory adapter for Yahoo Finance via :mod:`yfinance`.

    Historical data is fetched with :meth:`yfinance.Ticker.history`, which
    is a blocking HTTP call.  The call is executed inside
    :func:`asyncio.to_thread` so the event loop is never blocked.

    This provider is intentionally conservative: ``max_history_days=60``
    signals to the router that Massive or Kraken should be preferred for
    long-range intraday back-fills.  Daily data (``1d``) has no practical
    depth limit and is useful as a supplementary source for any supported
    asset class.
    """

    # -- identity -----------------------------------------------------------

    @property
    def name(self) -> ProviderName:
        return ProviderName.YFINANCE

    # -- capability queries -------------------------------------------------

    @property
    def max_history_days(self) -> int:
        """Conservative limit — use Massive / Kraken for longer ranges."""
        return 60

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
        """Return ``True`` when this provider can supply data for *config*.

        Rules
        -----
        * **ETF / EQUITY** — always supported; yfinance is the canonical
          source for exchange-listed securities.
        * **FUTURES_CME** — supported only when the asset's
          ``provider_symbol_map`` contains a ``"yfinance"`` key (e.g.
          ``"GC=F"``).  CME assets without an explicit override are skipped
          because the raw symbol (e.g. ``"MGC"``) is not a valid Yahoo
          ticker.
        * All other asset classes (CRYPTO, FOREX, …) — not supported;
          dedicated providers (Kraken, Binance, …) handle these.
        """
        if config.asset_class in _ALWAYS_SUPPORTED:
            return True
        if config.asset_class is AssetClass.FUTURES_CME:
            return ProviderName.YFINANCE.value in config.provider_symbol_map
        return False

    # -- bar fetching -------------------------------------------------------

    async def fetch_bars(
        self,
        symbol: str,
        interval: DataInterval,
        start: datetime,
        end: datetime,
        config: AssetConfig,
    ) -> list[OHLCVBar]:
        """Fetch historical OHLCV bars from Yahoo Finance over [*start*, *end*).

        Steps
        -----
        1. Resolve the Yahoo ticker via ``config.provider_symbol`` — e.g.
           ``"GC=F"``, ``"BTC-USD"``, or ``"SPY"``.
        2. Map the :class:`DataInterval` to the yfinance interval string.
        3. Call :meth:`yfinance.Ticker.history` inside
           :func:`asyncio.to_thread`.
        4. Convert the DatetimeIndex to UTC, filter to [*start*, *end*),
           and normalise each row to an :class:`~.base.OHLCVBar`.

        Raises
        ------
        ValueError
            If *interval* is not supported by yfinance (e.g. ``FOUR_HOUR``).
        """
        import yfinance as yf  # lazy import — optional dependency

        ticker = config.provider_symbol(ProviderName.YFINANCE)
        interval_str = interval.value

        yf_interval = _YF_INTERVAL.get(interval_str)
        if yf_interval is None:
            raise ValueError(
                f"Interval '{interval_str}' is not supported by yfinance. "
                f"Supported intervals: {', '.join(_YF_INTERVAL.keys())}. "
                "For 4-hour bars use a provider that supports native 4h resolution."
            )

        start_utc = _ensure_utc(start)
        end_utc = _ensure_utc(end)

        # yfinance accepts ISO date strings; the end date is exclusive for
        # intraday intervals and inclusive-ish for daily — using an exact
        # datetime string avoids ambiguity at day boundaries.
        start_str = start_utc.strftime("%Y-%m-%d")
        end_str = end_utc.strftime("%Y-%m-%d")

        log.debug(
            "fetch_bars: starting yfinance fetch",
            symbol=symbol,
            ticker=ticker,
            interval=interval_str,
            yf_interval=yf_interval,
            start=start_str,
            end=end_str,
        )

        # ------------------------------------------------------------------
        # Execute the blocking yfinance call in a thread-pool worker.
        # ------------------------------------------------------------------
        def _sync_fetch() -> pd.DataFrame:
            tkr = yf.Ticker(ticker)
            return tkr.history(
                start=start_str,
                end=end_str,
                interval=yf_interval,
                auto_adjust=True,  # adjusts OHLCV for splits/dividends
                prepost=False,  # exclude pre-market / after-hours bars
                raise_errors=False,  # return empty DataFrame on upstream errors
            )

        df: pd.DataFrame = await asyncio.to_thread(_sync_fetch)

        if df is None or df.empty:
            log.debug(
                "yfinance returned no data",
                ticker=ticker,
                interval=interval_str,
                start=start_str,
                end=end_str,
            )
            return []

        # ------------------------------------------------------------------
        # Normalise DataFrame rows → OHLCVBar dataclasses.
        #
        # yfinance sets a DatetimeIndex that is typically UTC for intraday
        # intervals and tz-naive (localised to exchange timezone) for daily.
        # We normalise every timestamp to an explicit UTC datetime.
        # ------------------------------------------------------------------
        bars: list[OHLCVBar] = []
        for ts, row in df.iterrows():
            bar_time = _ts_to_utc(ts)

            # Precise client-side window filter.  yfinance may return one
            # extra bar at the boundary when end falls mid-candle.
            if bar_time < start_utc or bar_time >= end_utc:
                continue

            # Guard against rows with missing OHLC — can occur at the edges
            # of the history window or for thinly-traded symbols.
            try:
                open_ = float(row["Open"])
                high = float(row["High"])
                low = float(row["Low"])
                close = float(row["Close"])
                volume = float(row["Volume"])
            except (KeyError, TypeError, ValueError) as exc:
                log.warning(
                    "Skipping malformed yfinance bar",
                    ticker=ticker,
                    bar_time=bar_time.isoformat(),
                    error=str(exc),
                )
                continue

            bars.append(
                OHLCVBar(
                    symbol=symbol,
                    interval=interval_str,
                    bar_time=bar_time,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    source=ProviderName.YFINANCE.value,
                )
            )

        log.info(
            "yfinance fetch complete",
            symbol=symbol,
            ticker=ticker,
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
    """Convert a pandas :class:`~pandas.Timestamp` index entry to a UTC datetime.

    yfinance returns a :class:`~pandas.DatetimeIndex` whose timezone varies
    by interval and symbol:

    * Intraday (1m … 1h) — UTC-aware ``pd.Timestamp``.
    * Daily (1d)         — may be tz-naive (exchange local) or UTC depending
                           on the yfinance version; we treat naive as UTC.

    Either way, the result is a proper UTC-aware :class:`datetime`.
    """
    pdt: datetime = ts.to_pydatetime()  # type: ignore[attr-defined]
    if pdt.tzinfo is None:
        return pdt.replace(tzinfo=UTC)
    return pdt.astimezone(UTC)
