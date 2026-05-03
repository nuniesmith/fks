"""Base provider protocol — abstract interface every data provider must implement.

All concrete providers (Polygon, Alpaca, Benzinga, …) subclass
:class:`BaseProvider` and normalise their upstream responses into the
canonical :class:`OHLCVBar` and :class:`NewsItem` dataclasses defined here.
This guarantees a uniform shape for downstream consumers regardless of
which provider sourced the data.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

    from ..registry.schemas import AssetConfig, DataInterval, ProviderName


# ---------------------------------------------------------------------------
# Canonical data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """Canonical bar format that all providers normalise to."""

    symbol: str
    interval: str
    bar_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str  # provider name, for provenance tracking


@dataclass(frozen=True, slots=True)
class NewsItem:
    """Canonical news format that all providers normalise to."""

    source: str  # provider name
    url: str  # canonical dedup key
    headline: str
    body: str | None
    published_at: datetime
    symbols: list[str]  # pre-matched symbols
    tags: list[str]  # sector / category tags
    sentiment: float | None  # pre-scored if the provider supplies it


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class BaseProvider(abc.ABC):
    """Abstract base class that every data provider must implement.

    Concrete subclasses **must** override every ``@abstractmethod``.  The
    non-abstract helpers (``fetch_news``, ``stream_bars``) provide sensible
    defaults so that providers which only supply bars need not stub them out.
    """

    # -- identity -----------------------------------------------------------

    @property
    @abc.abstractmethod
    def name(self) -> ProviderName:
        """Unique, machine-readable provider identifier."""

    # -- capability queries -------------------------------------------------

    @abc.abstractmethod
    async def supports_symbol(
        self,
        symbol: str,
        config: AssetConfig,
    ) -> bool:
        """Return ``True`` if *symbol* can be served under *config*."""

    @abc.abstractmethod
    def supported_intervals(self) -> list[DataInterval]:
        """Return every bar interval this provider can supply."""

    @property
    @abc.abstractmethod
    def max_history_days(self) -> int:
        """Maximum look-back depth (in calendar days) the provider allows."""

    # -- bar fetching -------------------------------------------------------

    @abc.abstractmethod
    async def fetch_bars(
        self,
        symbol: str,
        interval: DataInterval,
        start: datetime,
        end: datetime,
        config: AssetConfig,
    ) -> list[OHLCVBar]:
        """Fetch historical OHLCV bars for *symbol* over [*start*, *end*)."""

    # -- news fetching (optional) -------------------------------------------

    async def fetch_news(
        self,
        config: AssetConfig,
        since: datetime,
    ) -> list[NewsItem]:
        """Fetch news items published after *since*.

        The default implementation returns an empty list so that bar-only
        providers do not need to override this method.
        """
        return []

    # -- real-time streaming (optional) -------------------------------------

    async def stream_bars(
        self,
        symbol: str,
        interval: DataInterval,
        config: AssetConfig,
    ) -> AsyncIterator[OHLCVBar]:
        """Yield bars in real time.

        The default implementation raises :exc:`NotImplementedError` so that
        providers which do not support streaming fail fast.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support real-time streaming",
        )
        # Make the function a valid async generator despite the early raise.
        yield  # pragma: no cover  # noqa: RET503

    # -- dunder -------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name.value}>"
