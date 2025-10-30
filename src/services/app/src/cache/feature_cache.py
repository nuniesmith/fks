"""Redis-based feature caching for FKS trading platform.

This module provides intelligent caching for:
1. Engineered features (technical indicators, statistical features)
2. OHLCV data transformations
3. Model predictions and signals

Cache Strategy:
- Key namespace: features:{symbol}:{timeframe}:{feature_name}
- TTL based on timeframe: 1m=60s, 5m=300s, 1h=3600s, 1d=86400s
- Automatic serialization/deserialization for pandas DataFrames
- Cache warming for frequently accessed features
- Invalidation on new data arrival

Phase: AI Enhancement Plan Phase 5.4 - Redis Caching Layer
"""

import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
import os

import pandas as pd
import numpy as np
import redis
from redis import ConnectionPool

logger = logging.getLogger(__name__)


class FeatureCache:
    """Redis-based cache for trading features and data.
    
    This cache provides:
    - Intelligent TTL based on data timeframe
    - DataFrame serialization with pickle
    - Namespace isolation for different data types
    - Bulk operations for efficiency
    - Cache statistics and monitoring
    
    Attributes:
        redis_client: Redis client instance
        default_ttl: Default TTL in seconds (3600 = 1 hour)
        namespace: Cache key namespace prefix
        stats: Cache hit/miss statistics
    """
    
    # TTL mapping for different timeframes (in seconds)
    TIMEFRAME_TTL = {
        "1m": 60,        # 1 minute
        "5m": 300,       # 5 minutes
        "15m": 900,      # 15 minutes
        "1h": 3600,      # 1 hour
        "4h": 14400,     # 4 hours
        "1d": 86400,     # 1 day
        "1w": 604800,    # 1 week
    }
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        namespace: str = "features",
        default_ttl: int = 3600,
        enable_stats: bool = True,
    ):
        """Initialize feature cache.
        
        Args:
            redis_url: Redis connection URL (defaults to env REDIS_URL)
            namespace: Cache key namespace (default: "features")
            default_ttl: Default TTL in seconds (default: 3600 = 1 hour)
            enable_stats: Enable cache statistics tracking
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://:@redis:6379/1")
        self.namespace = namespace
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats
        
        # Initialize Redis client with connection pooling
        try:
            pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=10,
                decode_responses=False,  # We need bytes for pickle
            )
            self.redis_client = redis.Redis(connection_pool=pool)
            
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ FeatureCache initialized: {self.redis_url} (namespace: {namespace})")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.redis_client = None
        
        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0,
        }
    
    def _build_key(self, symbol: str, timeframe: str, feature_name: str) -> str:
        """Build cache key with namespace.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            timeframe: Data timeframe (e.g., "1h")
            feature_name: Feature name (e.g., "rsi_14")
            
        Returns:
            Cache key string (e.g., "features:BTCUSDT:1h:rsi_14")
        """
        # Normalize symbol and timeframe
        symbol = symbol.upper().replace("/", "")
        timeframe = timeframe.lower()
        
        return f"{self.namespace}:{symbol}:{timeframe}:{feature_name}"
    
    def _get_ttl(self, timeframe: str) -> int:
        """Get TTL for timeframe.
        
        Args:
            timeframe: Data timeframe (e.g., "1h")
            
        Returns:
            TTL in seconds
        """
        return self.TIMEFRAME_TTL.get(timeframe.lower(), self.default_ttl)
    
    def _serialize_dataframe(self, df: pd.DataFrame) -> bytes:
        """Serialize DataFrame for Redis storage.
        
        Args:
            df: Pandas DataFrame to serialize
            
        Returns:
            Pickled bytes
        """
        return pickle.dumps(df, protocol=pickle.HIGHEST_PROTOCOL)
    
    def _deserialize_dataframe(self, data: bytes) -> pd.DataFrame:
        """Deserialize DataFrame from Redis.
        
        Args:
            data: Pickled bytes
            
        Returns:
            Pandas DataFrame
        """
        return pickle.loads(data)
    
    def get(
        self,
        symbol: str,
        timeframe: str,
        feature_name: str,
    ) -> Optional[pd.DataFrame]:
        """Get cached feature data.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            feature_name: Feature name
            
        Returns:
            Cached DataFrame or None if not found
        """
        if not self.redis_client:
            return None
        
        key = self._build_key(symbol, timeframe, feature_name)
        
        try:
            data = self.redis_client.get(key)
            
            if data:
                df = self._deserialize_dataframe(data)
                if self.enable_stats:
                    self.stats["hits"] += 1
                logger.debug(f"📦 Cache HIT: {key} ({len(df)} rows)")
                return df
            else:
                if self.enable_stats:
                    self.stats["misses"] += 1
                logger.debug(f"❌ Cache MISS: {key}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Cache GET error for {key}: {e}")
            if self.enable_stats:
                self.stats["errors"] += 1
            return None
    
    def set(
        self,
        symbol: str,
        timeframe: str,
        feature_name: str,
        data: pd.DataFrame,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set cached feature data.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            feature_name: Feature name
            data: DataFrame to cache
            ttl: Optional custom TTL (uses timeframe default if None)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client or data is None or data.empty:
            return False
        
        key = self._build_key(symbol, timeframe, feature_name)
        ttl = ttl or self._get_ttl(timeframe)
        
        try:
            serialized = self._serialize_dataframe(data)
            self.redis_client.setex(key, ttl, serialized)
            
            if self.enable_stats:
                self.stats["sets"] += 1
            
            logger.debug(f"💾 Cache SET: {key} ({len(data)} rows, TTL={ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache SET error for {key}: {e}")
            if self.enable_stats:
                self.stats["errors"] += 1
            return False
    
    def get_features(
        self,
        symbol: str,
        timeframe: str,
        feature_names: List[str],
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """Get multiple features at once.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            feature_names: List of feature names
            
        Returns:
            Dictionary mapping feature names to DataFrames
        """
        results = {}
        
        for feature_name in feature_names:
            results[feature_name] = self.get(symbol, timeframe, feature_name)
        
        return results
    
    def set_features(
        self,
        symbol: str,
        timeframe: str,
        features: Dict[str, pd.DataFrame],
        ttl: Optional[int] = None,
    ) -> int:
        """Set multiple features at once.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            features: Dictionary mapping feature names to DataFrames
            ttl: Optional custom TTL
            
        Returns:
            Number of features successfully cached
        """
        success_count = 0
        
        for feature_name, data in features.items():
            if self.set(symbol, timeframe, feature_name, data, ttl):
                success_count += 1
        
        return success_count
    
    def invalidate(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        feature_name: Optional[str] = None,
    ) -> int:
        """Invalidate cached data.
        
        Args:
            symbol: Optional symbol filter (None = all symbols)
            timeframe: Optional timeframe filter (None = all timeframes)
            feature_name: Optional feature name filter (None = all features)
            
        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0
        
        # Build pattern for key matching
        pattern_parts = [self.namespace]
        pattern_parts.append(symbol.upper().replace("/", "") if symbol else "*")
        pattern_parts.append(timeframe.lower() if timeframe else "*")
        pattern_parts.append(feature_name if feature_name else "*")
        
        pattern = ":".join(pattern_parts)
        
        try:
            # Scan for matching keys
            keys = []
            for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            # Delete in batches
            deleted = 0
            if keys:
                deleted = self.redis_client.delete(*keys)
            
            logger.info(f"🗑️ Invalidated {deleted} keys matching: {pattern}")
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Cache invalidation error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        if not self.enable_stats:
            return {"stats_enabled": False}
        
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            self.stats["hits"] / total_requests if total_requests > 0 else 0.0
        )
        
        return {
            "stats_enabled": True,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "sets": self.stats["sets"],
            "errors": self.stats["errors"],
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "hit_rate_pct": f"{hit_rate * 100:.1f}%",
        }
    
    def clear_stats(self):
        """Clear cache statistics."""
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0,
        }
        logger.info("📊 Cache statistics cleared")
    
    def get_info(self) -> Dict[str, Any]:
        """Get Redis info and cache metadata.
        
        Returns:
            Dictionary with Redis info
        """
        if not self.redis_client:
            return {"connected": False}
        
        try:
            info = self.redis_client.info()
            
            # Count keys in namespace
            pattern = f"{self.namespace}:*"
            key_count = sum(1 for _ in self.redis_client.scan_iter(match=pattern))
            
            return {
                "connected": True,
                "namespace": self.namespace,
                "key_count": key_count,
                "redis_version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "stats": self.get_stats(),
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get Redis info: {e}")
            return {"connected": False, "error": str(e)}
    
    def close(self):
        """Close Redis connection."""
        if self.redis_client:
            self.redis_client.close()
            logger.info("🔌 Redis connection closed")


# Global cache instance (singleton pattern)
_cache_instance: Optional[FeatureCache] = None


def get_cache_instance(
    redis_url: Optional[str] = None,
    namespace: str = "features",
) -> FeatureCache:
    """Get or create global cache instance.
    
    Args:
        redis_url: Redis connection URL
        namespace: Cache namespace
        
    Returns:
        FeatureCache instance
    """
    global _cache_instance
    
    if _cache_instance is None:
        _cache_instance = FeatureCache(redis_url=redis_url, namespace=namespace)
    
    return _cache_instance


# Example usage
if __name__ == "__main__":
    # Example: Cache feature data
    cache = get_cache_instance()
    
    # Create sample DataFrame
    sample_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=100, freq="1H"),
        "rsi_14": np.random.uniform(30, 70, 100),
        "macd": np.random.uniform(-1, 1, 100),
    })
    
    # Cache the data
    cache.set("BTCUSDT", "1h", "rsi_14", sample_df[["timestamp", "rsi_14"]])
    
    # Retrieve from cache
    cached_data = cache.get("BTCUSDT", "1h", "rsi_14")
    print(f"Cached data: {cached_data.head() if cached_data is not None else 'Not found'}")
    
    # Get stats
    print(f"Cache stats: {cache.get_stats()}")
