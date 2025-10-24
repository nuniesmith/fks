"""Binance adapter (Futures/Spot klines minimal) built on Week 2 scaffolding."""

from __future__ import annotations

from typing import Any

from core.exceptions import DataFetchError  # type: ignore
from framework.middleware.circuit_breaker import CircuitBreaker
from framework.middleware.circuit_breaker.config import CircuitBreakerConfig
from framework.middleware.rate_limiter import RateLimiter

from .base import APIAdapter

# Import asset registry
try:
    from core.registry import AssetType, get_asset
except ImportError:
    # Fallback for environments without asset registry
    class AssetType:
        SPOT = "spot"
        FUTURES = "futures"

    def get_asset(symbol):
        return None


class BinanceAdapter(APIAdapter):
    name = "binance"
    # Base URLs for different endpoints
    spot_base_url = "https://api.binance.com"
    futures_base_url = "https://fapi.binance.com"
    base_url = futures_base_url  # Default to futures for backward compatibility
    rate_limit_per_sec = 10  # conservative (Binance allows more, we keep low)

    def __init__(self, *args, **kwargs):
        """Initialize Binance adapter with circuit breaker and rate limiter."""
        super().__init__(*args, **kwargs)
        
        # Configure circuit breaker for Binance API
        cb_config = CircuitBreakerConfig(
            failure_threshold=3,  # Open circuit after 3 failures
            reset_timeout=60,     # Try again after 60 seconds
            success_threshold=2,  # Close circuit after 2 successes
            timeout=30,           # Request timeout
            track_metrics=True
        )
        self.circuit_breaker = CircuitBreaker(
            name=f"{self.name}_api",
            config=cb_config
        )
        
        # Configure rate limiter (10 requests per second)
        self.rate_limiter = RateLimiter(
            max_requests=10,
            time_window=1,  # 1 second window
            algorithm="token_bucket",
            policy="wait",
            max_wait_time=5.0,
            name=f"{self.name}_rate_limit"
        )

    def _build_request(self, **kwargs):  # noqa: D401
        symbol: str = kwargs.get("symbol", "BTCUSDT")
        interval: str = kwargs.get("interval", "1m")
        limit: int = int(kwargs.get("limit", 500))
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")
        asset_type: str = kwargs.get("asset_type", AssetType.FUTURES)

        # Determine endpoint and base URL based on asset type
        asset = get_asset(symbol)
        if asset and hasattr(asset, "asset_type"):
            is_spot = (
                asset.asset_type.value == AssetType.SPOT
                if hasattr(asset.asset_type, "value")
                else asset.asset_type == AssetType.SPOT
            )
        else:
            # Fallback: check if explicitly requested as spot
            is_spot = asset_type == AssetType.SPOT

        if is_spot:
            base_url = self.spot_base_url
            path = "/api/v3/klines"  # Spot endpoint
        else:
            base_url = self.futures_base_url
            path = "/fapi/v1/klines"  # Futures endpoint

        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        # Binance public klines need no auth; placeholder for future API key usage
        headers: dict[str, str] | None = None
        return base_url + path, params, headers

    def fetch(self, **kwargs) -> dict[str, Any]:
        """Override fetch to add circuit breaker and rate limiter protection."""
        # Acquire rate limit token before making request
        self.rate_limiter.acquire()

        # Execute fetch with circuit breaker protection
        try:
            return self.circuit_breaker.execute(self._fetch_internal, **kwargs)
        except Exception:
            # Circuit breaker will handle failures, we just re-raise
            raise

    def _fetch_internal(self, **kwargs) -> dict[str, Any]:
        """Internal fetch implementation called by circuit breaker."""
        return super().fetch(**kwargs)

    def _normalize(self, raw: Any, *, request_kwargs: dict[str, Any]) -> dict[str, Any]:  # noqa: D401
        if not isinstance(raw, list):  # Unexpected shape
            raise DataFetchError(self.name, f"unexpected payload type: {type(raw)}")
        data: list[dict[str, Any]] = []
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
            except Exception:  # pragma: no cover - skip malformed row
                continue
        return {"provider": self.name, "data": data, "request": request_kwargs}

    def get_circuit_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics for monitoring."""
        return self.circuit_breaker.get_metrics()

    def get_rate_limit_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        return self.rate_limiter.get_stats()


__all__ = ["BinanceAdapter"]
