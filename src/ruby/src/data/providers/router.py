"""Health-aware provider router — selects the best available provider.

Selects the best available provider for each (symbol, interval) pair and
manages the fallback chain.  Priority is determined by:

1. The asset's ``providers`` list (explicit ordering in :class:`AssetConfig`).
2. Core in-memory asset registry (fallback when DataFactory config is sparse).
3. Provider health — providers on cooldown are skipped.
4. Interval coverage — the provider must support the requested interval.
5. History depth — the provider must cover the requested look-back window.

Provider health is tracked in Redis with a short-TTL circuit breaker so
that a failing upstream is temporarily excluded from the chain without
requiring a restart or manual intervention.

The router also exposes helpers that merge routing metadata from both the
DataFactory ``AssetConfig`` registry and the core in-memory
``asset_registry``, with the DataFactory config taking priority.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from core.logging_config import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from ..registry.schemas import AssetConfig, DataInterval, ProviderName
    from .base import BaseProvider, NewsItem, OHLCVBar

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HEALTH_KEY_PREFIX = "ruby:provider:health"
_COOLDOWN_KEY_PREFIX = "ruby:provider:cooldown"
_COOLDOWN_SECS = 300  # 5 min cooldown after failure
_HEALTH_TTL = 120  # 2 min health cache


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ProviderRouter:
    """Health-aware router that manages the provider fallback chain.

    Parameters
    ----------
    redis:
        An ``redis.asyncio`` connection used for health / cooldown tracking.
    providers:
        Fully-initialised provider instances to route across.
    """

    def __init__(
        self,
        redis: aioredis.Redis,  # type: ignore[name-defined]
        providers: list[BaseProvider],
    ) -> None:
        self._redis = redis
        self._providers: dict[ProviderName, BaseProvider] = {p.name: p for p in providers}

    # ------------------------------------------------------------------
    # Public API — bars
    # ------------------------------------------------------------------

    async def fetch_bars(
        self,
        symbol: str,
        interval: DataInterval,
        start: datetime,
        end: datetime,
        config: AssetConfig,
    ) -> tuple[list[OHLCVBar], ProviderName | None]:
        """Fetch OHLCV bars, walking the fallback chain until one succeeds.

        Returns
        -------
        tuple[list[OHLCVBar], ProviderName | None]
            The bars and the name of the provider that served them, or
            ``([], None)`` if every provider in the chain failed.
        """
        chain = await self._build_chain(config, interval, start)

        for provider in chain:
            try:
                bars = await provider.fetch_bars(
                    symbol,
                    interval,
                    start,
                    end,
                    config,
                )
                await self._mark_healthy(provider.name)
                log.info(
                    "bars_fetched",
                    provider=provider.name.value,
                    symbol=symbol,
                    interval=interval.value,
                    bar_count=len(bars),
                )
                return bars, provider.name
            except Exception:
                log.warning(
                    "provider_fetch_failed",
                    provider=provider.name.value,
                    symbol=symbol,
                    interval=interval.value,
                    exc_info=True,
                )
                await self._mark_failed(provider.name)

        log.error(
            "all_providers_exhausted",
            symbol=symbol,
            interval=interval.value,
            chain_length=len(chain),
        )
        return [], None

    # ------------------------------------------------------------------
    # Public API — news
    # ------------------------------------------------------------------

    async def fetch_news(
        self,
        config: AssetConfig,
        since: datetime,
    ) -> list[NewsItem]:
        """Fetch news from *all* registered providers (not just ``config.providers``).

        News coverage is broader than bar data, so every provider that is
        not on cooldown is consulted.
        """
        results: list[NewsItem] = []

        for provider in self._providers.values():
            if await self._is_on_cooldown(provider.name):
                continue
            try:
                items = await provider.fetch_news(config, since)
                results.extend(items)
            except Exception:
                log.warning(
                    "news_fetch_failed",
                    provider=provider.name.value,
                    symbol=config.symbol,
                    exc_info=True,
                )
                await self._mark_failed(provider.name)

        return results

    # ------------------------------------------------------------------
    # Public API — introspection
    # ------------------------------------------------------------------

    async def best_provider_for(
        self,
        config: AssetConfig,
        interval: DataInterval,
        days_back: int,
    ) -> ProviderName | None:
        """Return the first viable provider without actually fetching data."""
        start = datetime.now(UTC).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        # Shift start back so _build_chain can compute days_needed.
        start = start - timedelta(days=days_back)
        chain = await self._build_chain(config, interval, start)
        return chain[0].name if chain else None

    # ------------------------------------------------------------------
    # Chain building
    # ------------------------------------------------------------------

    async def _build_chain(
        self,
        config: AssetConfig,
        interval: DataInterval,
        start: datetime,
    ) -> list[BaseProvider]:
        """Build an ordered list of eligible providers for the request."""
        now = datetime.now(UTC)
        days_needed = (now - start).days

        provider_names = await self._resolve_provider_chain(config, interval, start)

        chain: list[BaseProvider] = []

        for provider_name in provider_names:
            provider = self._providers.get(provider_name)
            if provider is None:
                continue

            if await self._is_on_cooldown(provider_name):
                continue

            if interval not in provider.supported_intervals():
                continue

            if provider.max_history_days < days_needed:
                continue

            chain.append(provider)

        return chain

    # ------------------------------------------------------------------
    # Provider chain resolution (with core registry fallback)
    # ------------------------------------------------------------------

    async def _resolve_provider_chain(
        self,
        config: AssetConfig,
        interval: DataInterval,
        start: datetime,
    ) -> list[ProviderName]:
        """Resolve the ordered provider chain, falling back to the core registry.

        1. Uses ``config.providers`` as the primary source.
        2. If that list is empty, consults the core in-memory asset registry
           via ``core_reg.get_source_chain()`` and maps lowercase provider
           strings to :class:`ProviderName` enum values.

        Returns
        -------
        list[ProviderName]
            Ordered provider names to iterate through.
        """
        if config.providers:
            return list(config.providers)

        # -- Fallback: core in-memory registry ----------------------------
        try:
            from core import asset_registry as core_reg  # noqa: PLC0415

            chain_strings = core_reg.get_source_chain(config.symbol)
            if not chain_strings:
                log.debug(
                    "router.core_chain_empty",
                    symbol=config.symbol,
                )
                return []

            from ..registry.schemas import ProviderName as PN  # noqa: PLC0415

            resolved: list[ProviderName] = []
            for name in chain_strings:
                try:
                    resolved.append(PN(name.lower()))
                except ValueError:
                    log.debug(
                        "router.unknown_core_provider",
                        provider=name,
                        symbol=config.symbol,
                    )

            log.info(
                "router.resolved_chain_from_core_registry",
                symbol=config.symbol,
                chain=[p.value for p in resolved],
                source="core_registry",
            )
            return resolved

        except Exception:
            log.debug(
                "router.core_registry_fallback_failed",
                symbol=config.symbol,
                exc_info=True,
            )
            return []

    # ------------------------------------------------------------------
    # Provider symbol resolution
    # ------------------------------------------------------------------

    def resolve_provider_symbol(
        self,
        symbol: str,
        provider_name: ProviderName | str,
        config: AssetConfig | None = None,
    ) -> str:
        """Return the provider-specific symbol for an asset.

        Priority:
        1. ``config.provider_symbol_map`` (DataFactory — user-editable).
        2. Core in-memory registry ``get_provider_symbol()``.
        3. Passthrough (returns *symbol* unchanged).

        Parameters
        ----------
        symbol:
            The canonical asset symbol (e.g. ``"BTC/USD"``, ``"MGC"``).
        provider_name:
            Target provider as a :class:`ProviderName` enum or plain string.
        config:
            Optional :class:`AssetConfig`; checked first.
        """
        provider_str = provider_name.value if hasattr(provider_name, "value") else str(provider_name).lower()

        # 1. DataFactory config
        if config is not None and config.provider_symbol_map:
            mapped = config.provider_symbol_map.get(provider_str)
            if mapped:
                return mapped

        # 2. Core in-memory registry
        try:
            from core import asset_registry as core_reg  # noqa: PLC0415

            core_sym = core_reg.get_provider_symbol(symbol, provider_str)
            if core_sym and core_sym != symbol:
                return core_sym
        except Exception:
            log.debug(
                "router.core_provider_symbol_failed",
                symbol=symbol,
                provider=provider_str,
                exc_info=True,
            )

        return symbol

    # ------------------------------------------------------------------
    # WebSocket URL delegation
    # ------------------------------------------------------------------

    def get_ws_url(self, symbol: str) -> str:
        """Return the primary WebSocket URL for *symbol* from the core registry.

        Returns ``""`` when the core registry is unavailable or the symbol
        has no WS endpoint configured.
        """
        try:
            from core import asset_registry as core_reg  # noqa: PLC0415

            return core_reg.get_ws_url(symbol)
        except Exception:
            log.debug(
                "router.core_ws_url_failed",
                symbol=symbol,
                exc_info=True,
            )
            return ""

    # ------------------------------------------------------------------
    # Merged routing info
    # ------------------------------------------------------------------

    def get_routing_info(self, symbol: str, config: AssetConfig | None = None) -> dict:
        """Return a dict merging routing metadata from both registries.

        Returns
        -------
        dict
            ``{ws_url, source_chain, provider_symbols}`` with DataFactory
            config taking priority over the core registry.
        """
        try:
            from core.registry_bridge import merge_routing_for_symbol  # noqa: PLC0415

            return merge_routing_for_symbol(symbol, factory_config=config)
        except Exception:
            log.debug(
                "router.routing_info_failed",
                symbol=symbol,
                exc_info=True,
            )
            return {
                "ws_url": "",
                "source_chain": [],
                "provider_symbols": {},
                "requires_auth": False,
                "delay_info": "",
            }

    # ------------------------------------------------------------------
    # Health tracking
    # ------------------------------------------------------------------

    async def _mark_healthy(self, name: ProviderName) -> None:
        """Record a successful call — clear cooldown, set health to ``ok``."""
        health_key = f"{_HEALTH_KEY_PREFIX}:{name.value}"
        cooldown_key = f"{_COOLDOWN_KEY_PREFIX}:{name.value}"
        await self._redis.setex(health_key, _HEALTH_TTL, "ok")
        await self._redis.delete(cooldown_key)

    async def _mark_failed(self, name: ProviderName) -> None:
        """Record a failed call — activate cooldown and set health to ``down``."""
        health_key = f"{_HEALTH_KEY_PREFIX}:{name.value}"
        cooldown_key = f"{_COOLDOWN_KEY_PREFIX}:{name.value}"
        await self._redis.setex(cooldown_key, _COOLDOWN_SECS, "1")
        await self._redis.setex(health_key, _HEALTH_TTL, "down")

    async def _is_on_cooldown(self, name: ProviderName) -> bool:
        """Return ``True`` if *name* is currently in its cooldown window."""
        cooldown_key = f"{_COOLDOWN_KEY_PREFIX}:{name.value}"
        return await self._redis.exists(cooldown_key) == 1

    async def health_summary(self) -> dict[str, str]:
        """Return a snapshot of every registered provider's health status.

        Returns
        -------
        dict[str, str]
            Mapping of provider name to ``"ok"``, ``"down"``, or
            ``"unknown"`` (no health record in Redis).
        """
        summary: dict[str, str] = {}
        for name in self._providers:
            health_key = f"{_HEALTH_KEY_PREFIX}:{name.value}"
            value = await self._redis.get(health_key)
            if value is None:
                summary[name.value] = "unknown"
            else:
                summary[name.value] = value if isinstance(value, str) else value.decode()
        return summary
