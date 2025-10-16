"""Binance adapter (Futures/Spot klines minimal) built on Week 2 scaffolding."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .base import APIAdapter, get_env_any
from shared_python.exceptions import DataFetchError  # type: ignore

# Import asset registry
try:
    from assets.registry import AssetType, get_asset
except ImportError:
    # Fallback for environments without asset registry
    class AssetType:
        SPOT = "spot"
        FUTURES = "futures"
    def get_asset(symbol): return None


class BinanceAdapter(APIAdapter):
    name = "binance"
    # Base URLs for different endpoints
    spot_base_url = "https://api.binance.com"
    futures_base_url = "https://fapi.binance.com"
    base_url = futures_base_url  # Default to futures for backward compatibility
    rate_limit_per_sec = 10  # conservative (Binance allows more, we keep low)

    def _build_request(self, **kwargs):  # noqa: D401
        symbol: str = kwargs.get("symbol", "BTCUSDT")
        interval: str = kwargs.get("interval", "1m")
        limit: int = int(kwargs.get("limit", 500))
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")
        asset_type: str = kwargs.get("asset_type", AssetType.FUTURES)
        
        # Determine endpoint and base URL based on asset type
        asset = get_asset(symbol)
        if asset and hasattr(asset, 'asset_type'):
            is_spot = asset.asset_type.value == AssetType.SPOT if hasattr(asset.asset_type, 'value') else asset.asset_type == AssetType.SPOT
        else:
            # Fallback: check if explicitly requested as spot
            is_spot = asset_type == AssetType.SPOT
        
        if is_spot:
            base_url = self.spot_base_url
            path = "/api/v3/klines"  # Spot endpoint
        else:
            base_url = self.futures_base_url
            path = "/fapi/v1/klines"  # Futures endpoint
        
        params: Dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        # Binance public klines need no auth; placeholder for future API key usage
        headers: Dict[str, str] | None = None
        return base_url + path, params, headers

    def _normalize(self, raw: Any, *, request_kwargs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401
        if not isinstance(raw, list):  # Unexpected shape
            raise DataFetchError(self.name, f"unexpected payload type: {type(raw)}")
        data: List[Dict[str, Any]] = []
        symbol = request_kwargs.get("symbol", "")
        asset_type = request_kwargs.get("asset_type", AssetType.FUTURES)
        
        for item in raw:
            # Official format: [ openTime, open, high, low, close, volume, closeTime, ... ]
            try:
                normalized_item = {
                    "ts": int(item[0] // 1000),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                    "symbol": symbol,
                    "asset_type": asset_type,
                }
                data.append(normalized_item)
            except Exception as e:  # pragma: no cover - skip malformed row
                continue
        return {"provider": self.name, "data": data, "request": request_kwargs}


__all__ = ["BinanceAdapter"]