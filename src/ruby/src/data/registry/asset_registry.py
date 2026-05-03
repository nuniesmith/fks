"""Persistent asset catalog backed by Postgres with a Redis cache layer.

Every tradeable asset tracked by the data factory lives in the
``asset_registry`` table.  A thin Redis cache (JSON blobs keyed by
``ruby:registry:assets``) sits in front of the database so that the
hot-path — ``enabled_assets()`` — rarely touches Postgres.

Assets can be enabled / disabled at runtime through the API.  All
factory workers call :meth:`AssetRegistry.enabled_assets` before
doing work so that changes propagate within one cache-TTL window.

On first boot the catalog is seeded from :data:`ASSET_CATALOG` defined
in :mod:`.schemas`.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from core.logging_config import get_logger

from .schemas import (
    ASSET_CATALOG,
    AssetClass,
    AssetConfig,
    DataInterval,
    NewsConfig,
    ProviderName,
    WindowTarget,
)

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncEngine

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CACHE_KEY: str = "ruby:registry:assets"
"""Redis key holding the full asset catalog as a JSON dict (symbol → config)."""

_CACHE_TTL: int = 300
"""Cache time-to-live in seconds (5 minutes)."""

_ENABLED_KEY: str = "ruby:registry:enabled"
"""Redis key holding a JSON list of currently-enabled symbols."""


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _config_to_dict(a: AssetConfig) -> dict[str, Any]:
    """Serialise an :class:`AssetConfig` to a plain dict suitable for JSON."""
    return {
        "symbol": a.symbol,
        "name": a.name,
        "asset_class": a.asset_class.value,
        "exchange": a.exchange,
        "enabled": a.enabled,
        "providers": [p.value for p in a.providers],
        "window_targets": [
            {
                "interval": wt.interval.value,
                "days": wt.days,
                "min_days": wt.min_days,
            }
            for wt in a.window_targets
        ],
        "news": {
            "enabled": a.news.enabled,
            "primary_keywords": a.news.primary_keywords,
            "secondary_keywords": a.news.secondary_keywords,
            "subreddits": a.news.subreddits,
            "min_sentiment_threshold": a.news.min_sentiment_threshold,
            "history_days": a.news.history_days,
        },
        "correlated": list(a.correlated),
        "provider_symbol_map": dict(a.provider_symbol_map),
        "point_value": a.point_value,
        "tick_size": a.tick_size,
        "currency": a.currency,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _dict_to_config(d: dict[str, Any]) -> AssetConfig:
    """Deserialise a plain dict back into an :class:`AssetConfig`."""
    providers = [ProviderName(v) for v in (d.get("providers") or [])]

    window_targets = [
        WindowTarget(
            interval=DataInterval(wt["interval"]),
            days=wt["days"],
            min_days=wt["min_days"],
        )
        for wt in (d.get("window_targets") or [])
    ]

    news_raw = d.get("news") or {}
    news = NewsConfig(
        enabled=news_raw.get("enabled", True),
        primary_keywords=news_raw.get("primary_keywords", []),
        secondary_keywords=news_raw.get("secondary_keywords", []),
        subreddits=news_raw.get("subreddits", []),
        min_sentiment_threshold=news_raw.get("min_sentiment_threshold", -1.0),
        history_days=news_raw.get("history_days", 365),
    )

    created_at = None
    if d.get("created_at"):
        created_at = datetime.fromisoformat(d["created_at"])

    updated_at = None
    if d.get("updated_at"):
        updated_at = datetime.fromisoformat(d["updated_at"])

    return AssetConfig(
        symbol=d["symbol"],
        name=d.get("name", d["symbol"]),
        asset_class=AssetClass(d["asset_class"]),
        exchange=d.get("exchange", ""),
        enabled=d.get("enabled", False),
        providers=providers,
        window_targets=window_targets,
        news=news,
        correlated=d.get("correlated", []),
        provider_symbol_map=d.get("provider_symbol_map", {}),
        point_value=d.get("point_value"),
        tick_size=d.get("tick_size"),
        currency=d.get("currency", "USD"),
        created_at=created_at,
        updated_at=updated_at,
    )


# ---------------------------------------------------------------------------
# AssetRegistry
# ---------------------------------------------------------------------------


class AssetRegistry:
    """Postgres-backed asset registry with a Redis read-through cache.

    Parameters
    ----------
    redis:
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    engine:
        An async SQLAlchemy engine pointing at the Postgres database.
    """

    def __init__(
        self,
        redis: aioredis.Redis,  # type: ignore[name-defined]
        engine: AsyncEngine,
    ) -> None:
        self._redis = redis
        self._engine = engine

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def bootstrap(self) -> None:
        """Seed the ``asset_registry`` table from :data:`ASSET_CATALOG`.

        Creates the table if it does not already exist (belt-and-suspenders
        alongside the SQL migration) then inserts every catalog entry using
        ``ON CONFLICT DO NOTHING`` so that previously-customised rows are
        never overwritten.
        """
        from sqlalchemy import text

        create_ddl = text(
            """
            CREATE TABLE IF NOT EXISTS asset_registry (
                symbol          TEXT PRIMARY KEY,
                name            TEXT NOT NULL DEFAULT '',
                asset_class     TEXT NOT NULL DEFAULT '',
                exchange        TEXT NOT NULL DEFAULT '',
                enabled         BOOLEAN NOT NULL DEFAULT FALSE,
                config_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
                disable_reason  TEXT NOT NULL DEFAULT '',
                disabled_at     TIMESTAMPTZ,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )

        insert_stmt = text(
            """
            INSERT INTO asset_registry (symbol, name, asset_class, exchange,
                                        enabled, config_json, created_at, updated_at)
            VALUES (:symbol, :name, :asset_class, :exchange,
                    :enabled, :config_json, now(), now())
            ON CONFLICT (symbol) DO NOTHING;
            """
        )

        async with self._engine.begin() as conn:
            await conn.execute(create_ddl)

            count = 0
            for asset in ASSET_CATALOG:
                config_blob = json.dumps(_config_to_dict(asset))
                await conn.execute(
                    insert_stmt,
                    {
                        "symbol": asset.symbol,
                        "name": asset.name,
                        "asset_class": asset.asset_class.value,
                        "exchange": asset.exchange,
                        "enabled": asset.enabled,
                        "config_json": config_blob,
                    },
                )
                count += 1

        await self._invalidate_cache()
        log.info("asset_registry.bootstrap", count=count)

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    async def all_assets(self) -> list[AssetConfig]:
        """Return every asset in the registry, using cached data when possible."""
        cached = await self._redis.get(_CACHE_KEY)
        if cached is not None:
            try:
                data: dict[str, Any] = json.loads(cached)
                return [_dict_to_config(v) for v in data.values()]
            except (json.JSONDecodeError, KeyError, TypeError):
                log.warning("asset_registry.cache_decode_failed")

        return await self._load_from_db_and_cache()

    async def enabled_assets(
        self,
        asset_class: AssetClass | str | None = None,
    ) -> list[AssetConfig]:
        """Return only enabled assets, optionally filtered by *asset_class*."""
        assets = await self.all_assets()
        result = [a for a in assets if a.enabled]

        if asset_class is not None:
            if isinstance(asset_class, str):
                asset_class = AssetClass(asset_class)
            result = [a for a in result if a.asset_class is asset_class]

        return result

    async def get(self, symbol: str) -> AssetConfig | None:
        """Look up a single asset by *symbol*, or return ``None``."""
        assets = await self.all_assets()
        for a in assets:
            if a.symbol == symbol:
                return a
        return None

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    async def enable(self, symbol: str) -> None:
        """Enable the asset identified by *symbol*."""
        from sqlalchemy import text

        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE asset_registry
                       SET enabled = TRUE,
                           disable_reason = '',
                           disabled_at = NULL,
                           updated_at = now()
                     WHERE symbol = :symbol;
                    """
                ),
                {"symbol": symbol},
            )
        log.info("asset_registry.enable", symbol=symbol)
        await self._invalidate_cache()

    async def disable(self, symbol: str, reason: str = "") -> None:
        """Disable the asset identified by *symbol* with an optional *reason*."""
        from sqlalchemy import text

        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE asset_registry
                       SET enabled = FALSE,
                           disable_reason = :reason,
                           disabled_at = now(),
                           updated_at = now()
                     WHERE symbol = :symbol;
                    """
                ),
                {"symbol": symbol, "reason": reason},
            )
        log.info("asset_registry.disable", symbol=symbol, reason=reason)
        await self._invalidate_cache()

    async def update_config(
        self,
        symbol: str,
        config: AssetConfig,
    ) -> None:
        """Overwrite the stored configuration for *symbol*."""
        from sqlalchemy import text

        config_blob = json.dumps(_config_to_dict(config))

        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE asset_registry
                       SET config_json  = :config_json,
                           name         = :name,
                           asset_class  = :asset_class,
                           updated_at   = now()
                     WHERE symbol = :symbol;
                    """
                ),
                {
                    "symbol": symbol,
                    "name": config.name,
                    "asset_class": config.asset_class.value,
                    "config_json": config_blob,
                },
            )
        log.info("asset_registry.update_config", symbol=symbol)
        await self._invalidate_cache()

    async def set_enabled_batch(
        self,
        symbols: list[str],
        enabled: bool,
    ) -> None:
        """Enable or disable a batch of assets atomically."""
        from sqlalchemy import text

        if not symbols:
            return

        if enabled:
            stmt = text(
                """
                UPDATE asset_registry
                   SET enabled = TRUE,
                       disable_reason = '',
                       disabled_at = NULL,
                       updated_at = now()
                 WHERE symbol = ANY(:symbols);
                """
            )
            params: dict[str, Any] = {"symbols": symbols}
        else:
            stmt = text(
                """
                UPDATE asset_registry
                   SET enabled = FALSE,
                       disabled_at = now(),
                       updated_at = now()
                 WHERE symbol = ANY(:symbols);
                """
            )
            params = {"symbols": symbols}

        async with self._engine.begin() as conn:
            await conn.execute(stmt, params)

        log.info(
            "asset_registry.set_enabled_batch",
            count=len(symbols),
            enabled=enabled,
        )
        await self._invalidate_cache()

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _load_from_db_and_cache(self) -> list[AssetConfig]:
        """Load every row from Postgres, cache in Redis, and return configs."""
        from sqlalchemy import text

        rows: list[Any] = []

        async with self._engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT symbol, name, asset_class, exchange, enabled,
                           config_json, disable_reason, disabled_at,
                           created_at, updated_at
                      FROM asset_registry
                     ORDER BY symbol;
                    """
                )
            )
            rows = result.fetchall()  # type: ignore[assignment]

        configs: list[AssetConfig] = []
        cache_payload: dict[str, Any] = {}

        for row in rows:
            (
                symbol,
                name,
                asset_class,
                exchange,
                enabled,
                config_json,
                _disable_reason,
                _disabled_at,
                created_at,
                updated_at,
            ) = row

            # The config_json blob is the authoritative source; overlay
            # top-level columns that the DB owns (enabled, name, …).
            if isinstance(config_json, str):
                data = json.loads(config_json)
            elif isinstance(config_json, dict):
                data = config_json
            else:
                data = {}

            data["symbol"] = symbol
            data["name"] = name
            data["asset_class"] = asset_class
            data["exchange"] = exchange
            data["enabled"] = enabled
            data["created_at"] = created_at.isoformat() if created_at else None
            data["updated_at"] = updated_at.isoformat() if updated_at else None

            cfg = _dict_to_config(data)
            configs.append(cfg)
            cache_payload[symbol] = _config_to_dict(cfg)

        # Write to Redis with TTL
        try:
            await self._redis.set(
                _CACHE_KEY,
                json.dumps(cache_payload),
                ex=_CACHE_TTL,
            )
        except Exception:
            log.warning("asset_registry.cache_write_failed", exc_info=True)

        log.debug("asset_registry.loaded_from_db", count=len(configs))
        return configs

    async def _invalidate_cache(self) -> None:
        """Delete the cached asset data from Redis."""
        try:
            await self._redis.delete(_CACHE_KEY)
        except Exception:
            log.warning("asset_registry.cache_invalidation_failed", exc_info=True)
