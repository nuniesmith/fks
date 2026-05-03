"""
CoinMarketCap provider -- free Basic plan.

Credit budget: ~6,000/month leaving 4,000 buffer.
All calls go through Redis cache to avoid duplicate fetches
when multiple consumers need the same data.

Endpoints used:
  /v1/cryptocurrency/quotes/latest      -> BTC/ETH/SOL prices + market data
  /v1/global-metrics/quotes/latest      -> total market cap, BTC dominance
  /v3/fear-and-greed/latest             -> sentiment index 0-100
  /v1/cryptocurrency/listings/latest    -> top 20 for broad context
  /v1/cryptocurrency/info               -> static metadata (cached long)
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import httpx

from core.logging_config import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = get_logger(__name__)

CMC_BASE = "https://pro-api.coinmarketcap.com"

# Cache TTLs -- aggressive caching is essential on the free plan
TTL_QUOTES = 840  # 14 min  (poll every 15 min -> always fresh)
TTL_GLOBAL = 1740  # 29 min  (poll every 30 min)
TTL_FEAR_GREED = 1740  # 29 min
TTL_LISTINGS = 21600  # 6 hours
TTL_INFO = 86400  # 24 hours -- metadata almost never changes


class CMCProvider:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis
        self._key = os.getenv("CMC_API_KEY", "")
        if not self._key:
            log.warning("CMC_API_KEY not set -- CoinMarketCap provider disabled")

    def _headers(self) -> dict:
        return {
            "X-CMC_PRO_API_KEY": self._key,
            "Accept": "application/json",
        }

    async def _cached_get(
        self,
        path: str,
        params: dict,
        cache_key: str,
        ttl: int,
    ) -> dict:
        """Get from Redis cache first, fall back to API call."""
        cached = await self._r.get(cache_key)
        if cached:
            return json.loads(cached)

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{CMC_BASE}{path}",
                params=params,
                headers=self._headers(),
            )
            if r.status_code != 200:
                log.warning("CMC %s -> %d: %s", path, r.status_code, r.text[:200])
                return {}

            data = r.json()
            if data.get("status", {}).get("error_code", 1) == 0:
                await self._r.setex(cache_key, ttl, json.dumps(data))
            return data

    # -- Quotes: BTC, ETH, SOL ------------------------------------------------

    async def quotes(self, symbols: list[str] | None = None) -> dict[str, dict]:
        """
        Latest price, market cap, volume, % changes for BTC/ETH/SOL.
        1 credit per call. Always batch all symbols.
        """
        if not self._key:
            return {}

        syms = ",".join(symbols or ["BTC", "ETH", "SOL"])
        cache_key = f"cmc:quotes:{syms}"

        data = await self._cached_get(
            "/v1/cryptocurrency/quotes/latest",
            {"symbol": syms, "convert": "USD"},
            cache_key,
            TTL_QUOTES,
        )

        result = {}
        for sym, coin_data in data.get("data", {}).items():
            quote = coin_data.get("quote", {}).get("USD", {})
            result[sym] = {
                "symbol": sym,
                "name": coin_data.get("name"),
                "cmc_rank": coin_data.get("cmc_rank"),
                "price": quote.get("price"),
                "market_cap": quote.get("market_cap"),
                "volume_24h": quote.get("volume_24h"),
                "pct_change_1h": quote.get("percent_change_1h"),
                "pct_change_24h": quote.get("percent_change_24h"),
                "pct_change_7d": quote.get("percent_change_7d"),
                "market_cap_dominance": quote.get("market_cap_dominance"),
                "fully_diluted_valuation": quote.get("fully_diluted_market_cap"),
                "circulating_supply": coin_data.get("circulating_supply"),
                "max_supply": coin_data.get("max_supply"),
                "last_updated": quote.get("last_updated"),
            }

        # Write individual keys for easy lookup
        pipe = self._r.pipeline()
        for sym, q in result.items():
            pipe.setex(f"cmc:quote:{sym}", TTL_QUOTES, json.dumps(q))
            if q.get("price"):
                pipe.setex(f"ruby:price:{sym}/USD", TTL_QUOTES, str(q["price"]))
                pipe.setex(
                    f"ruby:chg_pct:{sym}/USD",
                    TTL_QUOTES,
                    str(q.get("pct_change_24h", 0)),
                )
        await pipe.execute()

        return result

    # -- Global market metrics -------------------------------------------------

    async def global_metrics(self) -> dict:
        """
        Total crypto market cap, BTC/ETH dominance, 24h volume,
        active cryptos, stablecoin market cap and volume.
        1 credit per call.
        """
        if not self._key:
            return {}

        data = await self._cached_get(
            "/v1/global-metrics/quotes/latest",
            {"convert": "USD"},
            "cmc:global_metrics",
            TTL_GLOBAL,
        )

        raw = data.get("data", {})
        quote = raw.get("quote", {}).get("USD", {})

        result = {
            "total_market_cap": quote.get("total_market_cap"),
            "total_volume_24h": quote.get("total_volume_24h"),
            "total_volume_24h_reported": quote.get("total_volume_24h_reported"),
            "altcoin_market_cap": quote.get("altcoin_market_cap"),
            "altcoin_volume_24h": quote.get("altcoin_volume_24h"),
            "defi_market_cap": quote.get("defi_market_cap"),
            "defi_volume_24h": quote.get("defi_24h_volume"),
            "stablecoin_market_cap": quote.get("stablecoin_market_cap"),
            "stablecoin_volume_24h": quote.get("stablecoin_24h_volume"),
            "btc_dominance": raw.get("btc_dominance"),
            "btc_dominance_24h_pct_change": raw.get("btc_dominance_24h_percentage_change"),
            "eth_dominance": raw.get("eth_dominance"),
            "active_cryptocurrencies": raw.get("active_cryptocurrencies"),
            "active_market_pairs": raw.get("active_market_pairs"),
            "active_exchanges": raw.get("active_exchanges"),
            "last_updated": raw.get("last_updated"),
        }

        await self._r.setex("cmc:global_metrics", TTL_GLOBAL, json.dumps(result))
        if result.get("btc_dominance"):
            await self._r.setex("cmc:btc_dominance", TTL_GLOBAL, str(result["btc_dominance"]))
        return result

    # -- Fear & Greed Index ----------------------------------------------------

    async def fear_and_greed(self) -> dict:
        """
        CMC Fear & Greed Index: 0 (extreme fear) -> 100 (extreme greed).
        1 credit per call.
        """
        if not self._key:
            return {}

        data = await self._cached_get(
            "/v3/fear-and-greed/latest",
            {},
            "cmc:fear_greed",
            TTL_FEAR_GREED,
        )

        raw = data.get("data", {})
        value = raw.get("value", 0)
        label = raw.get("value_classification", "Unknown")

        result = {
            "value": value,
            "label": label,
            "sentiment": _fg_to_sentiment(value),
            "timestamp": raw.get("timestamp"),
        }

        await self._r.setex("cmc:fear_greed", TTL_FEAR_GREED, json.dumps(result))
        return result

    # -- Top listings for broad context ----------------------------------------

    async def top_listings(self, limit: int = 20) -> list[dict]:
        """
        Top N coins by market cap with price + volume data.
        1 credit per 100 results.
        """
        if not self._key:
            return []

        data = await self._cached_get(
            "/v1/cryptocurrency/listings/latest",
            {"limit": limit, "convert": "USD", "sort": "market_cap"},
            f"cmc:listings:{limit}",
            TTL_LISTINGS,
        )

        coins = []
        for coin in data.get("data", []):
            q = coin.get("quote", {}).get("USD", {})
            coins.append(
                {
                    "rank": coin.get("cmc_rank"),
                    "symbol": coin.get("symbol"),
                    "name": coin.get("name"),
                    "price": q.get("price"),
                    "market_cap": q.get("market_cap"),
                    "volume_24h": q.get("volume_24h"),
                    "pct_change_24h": q.get("percent_change_24h"),
                    "pct_change_7d": q.get("percent_change_7d"),
                    "dominance": q.get("market_cap_dominance"),
                }
            )

        await self._r.setex(f"cmc:listings:{limit}", TTL_LISTINGS, json.dumps(coins))
        return coins

    # -- Static metadata -------------------------------------------------------

    async def crypto_info(self, symbols: list[str] | None = None) -> dict:
        """
        Static metadata: description, logo, website, social links, tags.
        Cache for 24h. 1 credit per call.
        """
        if not self._key:
            return {}

        syms = ",".join(symbols or ["BTC", "ETH", "SOL"])
        cache_key = f"cmc:info:{syms}"

        data = await self._cached_get(
            "/v1/cryptocurrency/info",
            {"symbol": syms},
            cache_key,
            TTL_INFO,
        )

        result = {}
        for sym, info in data.get("data", {}).items():
            result[sym] = {
                "symbol": sym,
                "name": info.get("name"),
                "description": info.get("description", "")[:500],
                "logo": info.get("logo"),
                "website": (info.get("urls", {}).get("website") or [None])[0],
                "twitter": (info.get("urls", {}).get("twitter") or [None])[0],
                "reddit": (info.get("urls", {}).get("reddit") or [None])[0],
                "github": (info.get("urls", {}).get("source_code") or [None])[0],
                "tags": info.get("tags", [])[:10],
                "category": info.get("category"),
                "date_launched": info.get("date_launched"),
            }

        return result


# -- Scheduled polling worker --------------------------------------------------


class CMCWorker:
    """
    Runs as a task in the coordinator's TaskGroup.
    Polls CMC endpoints on their respective schedules and
    writes results to Redis for all consumers.
    """

    def __init__(self, provider: CMCProvider) -> None:
        self._cmc = provider

    async def run(self) -> None:
        import asyncio

        log.info("CMCWorker starting")

        await asyncio.gather(
            self._loop_quotes(),
            self._loop_global(),
            self._loop_fear_greed(),
            self._loop_listings(),
        )

    async def _loop_quotes(self) -> None:
        import asyncio

        interval = int(os.getenv("CMC_POLL_QUOTES", "900"))
        while True:
            try:
                q = await self._cmc.quotes(["BTC", "ETH", "SOL"])
                if q:
                    log.debug(
                        "CMC quotes: BTC=$%.0f ETH=$%.0f SOL=$%.2f",
                        q.get("BTC", {}).get("price", 0),
                        q.get("ETH", {}).get("price", 0),
                        q.get("SOL", {}).get("price", 0),
                    )
            except Exception:
                log.exception("CMCWorker quotes error")
            await asyncio.sleep(interval)

    async def _loop_global(self) -> None:
        import asyncio

        interval = int(os.getenv("CMC_POLL_GLOBAL", "1800"))
        await asyncio.sleep(30)
        while True:
            try:
                await self._cmc.global_metrics()
            except Exception:
                log.exception("CMCWorker global metrics error")
            await asyncio.sleep(interval)

    async def _loop_fear_greed(self) -> None:
        import asyncio

        interval = int(os.getenv("CMC_POLL_FEAR_GREED", "1800"))
        await asyncio.sleep(60)
        while True:
            try:
                fg = await self._cmc.fear_and_greed()
                if fg:
                    log.debug(
                        "CMC Fear & Greed: %d (%s)",
                        fg.get("value", 0),
                        fg.get("label", "?"),
                    )
            except Exception:
                log.exception("CMCWorker fear & greed error")
            await asyncio.sleep(interval)

    async def _loop_listings(self) -> None:
        import asyncio

        interval = int(os.getenv("CMC_POLL_LISTINGS", "21600"))
        await asyncio.sleep(120)
        while True:
            try:
                await self._cmc.top_listings(limit=20)
            except Exception:
                log.exception("CMCWorker listings error")
            await asyncio.sleep(interval)


# -- Helpers -------------------------------------------------------------------


def _fg_to_sentiment(value: int) -> str:
    if value >= 75:
        return "extreme_greed"
    if value >= 55:
        return "greed"
    if value >= 45:
        return "neutral"
    if value >= 25:
        return "fear"
    return "extreme_fear"
