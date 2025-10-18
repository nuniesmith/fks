"""Oanda adapter for Forex and Futures data using ccxt-like pattern."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.exceptions import DataFetchError  # type: ignore

from .base import APIAdapter, get_env_any

# Import asset registry
try:
    from core.registry import AssetType, FuturesSubcategory, get_asset
except ImportError:
    # Fallback for environments without asset registry
    class AssetType:
        SPOT = "spot"
        FUTURES = "futures"

    class FuturesSubcategory:
        FOREX = "forex"
        COMMODITIES = "commodities"
        INDICES = "indices"

    def get_asset(symbol):
        return None


class OandaAdapter(APIAdapter):
    name = "oanda"
    # Oanda API endpoints
    base_url = "https://api-fxpractice.oanda.com"  # Practice environment
    # base_url = "https://api-fxtrade.oanda.com"  # Live environment
    rate_limit_per_sec = 5  # Conservative rate limiting

    # Symbol mapping for futures contracts
    FUTURES_SYMBOL_MAP = {
        # Forex Futures
        "6E": "EUR_USD",
        "6B": "GBP_USD",
        "6J": "USD_JPY",
        "6A": "AUD_USD",
        # Commodities (using CFDs as proxy)
        "GC": "XAU_USD",  # Gold
        "SI": "XAG_USD",  # Silver
        "CL": "BCO_USD",  # Oil (Brent)
        "NG": "NATGAS_USD",  # Natural Gas
        # Indices (using CFDs as proxy)
        "ES": "SPX500_USD",  # S&P 500
        "NQ": "NAS100_USD",  # NASDAQ 100
        "YM": "US30_USD",  # Dow Jones
    }

    def _build_request(self, **kwargs):  # noqa: D401
        symbol: str = kwargs.get("symbol", "EUR_USD")
        interval: str = kwargs.get("interval", "M1")
        limit: int = int(kwargs.get("limit", 500))
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")
        asset_type: str = kwargs.get("asset_type", AssetType.SPOT)

        # Map futures symbols to Oanda equivalents
        if symbol in self.FUTURES_SYMBOL_MAP:
            oanda_symbol = self.FUTURES_SYMBOL_MAP[symbol]
        else:
            oanda_symbol = symbol

        # Convert interval format (Binance-style to Oanda-style)
        oanda_granularity = self._convert_interval(interval)

        # Build Oanda REST API path for candles
        path = f"/v3/instruments/{oanda_symbol}/candles"

        params: dict[str, Any] = {"granularity": oanda_granularity, "count": limit}

        # Add time filters if provided
        if start_time:
            params["from"] = self._format_time(start_time)
        if end_time:
            params["to"] = self._format_time(end_time)

        # Headers for Oanda API (will need API token)
        api_token = get_env_any("OANDA_API_TOKEN", "OANDA_TOKEN")
        headers: dict[str, str] = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        return self.base_url + path, params, headers

    def _convert_interval(self, interval: str) -> str:
        """Convert interval from Binance format to Oanda format."""
        interval_map = {
            "1m": "M1",
            "5m": "M5",
            "15m": "M15",
            "30m": "M30",
            "1h": "H1",
            "4h": "H4",
            "1d": "D",
            "1w": "W",
            "1M": "M",
        }
        return interval_map.get(interval, "M1")

    def _format_time(self, timestamp: int) -> str:
        """Convert timestamp to Oanda time format."""
        from datetime import datetime

        dt = datetime.fromtimestamp(timestamp / 1000)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def _normalize(
        self, raw: Any, *, request_kwargs: dict[str, Any]
    ) -> dict[str, Any]:  # noqa: D401
        if not isinstance(raw, dict) or "candles" not in raw:
            raise DataFetchError(self.name, f"unexpected payload format: {type(raw)}")

        data: list[dict[str, Any]] = []
        symbol = request_kwargs.get("symbol", "")
        asset_type = request_kwargs.get("asset_type", AssetType.SPOT)

        # Determine asset category and subcategory
        asset = get_asset(symbol)
        category = None
        subcategory = None
        if asset:
            category = (
                asset.category.value
                if hasattr(asset.category, "value")
                else asset.category
            )
            subcategory = (
                asset.subcategory.value
                if asset.subcategory and hasattr(asset.subcategory, "value")
                else asset.subcategory
            )

        for candle in raw["candles"]:
            if not candle.get("complete", True):
                continue  # Skip incomplete candles

            try:
                mid = candle["mid"]
                time_str = candle["time"]

                # Parse Oanda timestamp
                from datetime import datetime

                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                timestamp = int(dt.timestamp())

                normalized_item = {
                    "ts": timestamp,
                    "open": float(mid["o"]),
                    "high": float(mid["h"]),
                    "low": float(mid["l"]),
                    "close": float(mid["c"]),
                    "volume": float(candle.get("volume", 0)),
                    "symbol": symbol,
                    "asset_type": asset_type,
                    "category": category,
                    "subcategory": subcategory,
                }
                data.append(normalized_item)
            except (KeyError, ValueError, TypeError):
                # Skip malformed candles
                continue

        return {"provider": self.name, "data": data, "request": request_kwargs}


__all__ = ["OandaAdapter"]
