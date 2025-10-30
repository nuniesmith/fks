"""Unit tests for Redis feature cache.

Tests:
1. FeatureCache initialization and connection
2. Cache key building
3. DataFrame serialization/deserialization
4. Cache get/set operations
5. TTL management
6. Bulk operations
7. Cache invalidation
8. Statistics tracking
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.ping = MagicMock()
    redis_mock.get = MagicMock(return_value=None)
    redis_mock.setex = MagicMock()
    redis_mock.delete = MagicMock(return_value=0)
    redis_mock.scan_iter = MagicMock(return_value=iter([]))
    redis_mock.info = MagicMock(return_value={"redis_version": "7.0", "used_memory_human": "1M", "connected_clients": 1})
    return redis_mock


@pytest.fixture
def feature_cache(mock_redis):
    """Create FeatureCache with mocked Redis."""
    with patch("redis.from_url", return_value=mock_redis):
        with patch("redis.ConnectionPool.from_url"):
            from cache.feature_cache import FeatureCache
            cache = FeatureCache(namespace="test_features")
            cache.redis_client = mock_redis
            return cache


@pytest.fixture
def sample_df():
    """Create sample DataFrame for testing."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=100, freq="1H"),
        "close": np.random.uniform(100, 110, 100),
        "rsi_14": np.random.uniform(30, 70, 100),
        "macd": np.random.uniform(-1, 1, 100),
    })


class TestFeatureCache:
    """Test FeatureCache functionality."""

    def test_initialization(self, feature_cache):
        """Test cache initialization."""
        assert feature_cache.namespace == "test_features"
        assert feature_cache.default_ttl == 3600
        assert feature_cache.enable_stats is True
        assert feature_cache.redis_client is not None

    def test_build_key(self, feature_cache):
        """Test cache key building."""
        key = feature_cache._build_key("BTC/USDT", "1h", "rsi_14")
        
        assert key == "test_features:BTCUSDT:1h:rsi_14"
        assert "test_features" in key  # Namespace
        assert "BTCUSDT" in key  # Symbol normalized
        assert "1h" in key  # Timeframe
        assert "rsi_14" in key  # Feature name

    def test_build_key_normalization(self, feature_cache):
        """Test symbol and timeframe normalization."""
        key1 = feature_cache._build_key("BTC/USDT", "1H", "rsi")
        key2 = feature_cache._build_key("btc/usdt", "1h", "rsi")
        
        assert key1 == key2  # Should normalize to same key

    def test_get_ttl(self, feature_cache):
        """Test TTL lookup for different timeframes."""
        assert feature_cache._get_ttl("1m") == 60
        assert feature_cache._get_ttl("1h") == 3600
        assert feature_cache._get_ttl("1d") == 86400
        assert feature_cache._get_ttl("unknown") == feature_cache.default_ttl

    def test_serialize_deserialize_dataframe(self, feature_cache, sample_df):
        """Test DataFrame serialization/deserialization."""
        # Serialize
        serialized = feature_cache._serialize_dataframe(sample_df)
        assert isinstance(serialized, bytes)
        
        # Deserialize
        deserialized = feature_cache._deserialize_dataframe(serialized)
        assert isinstance(deserialized, pd.DataFrame)
        
        # Check equality
        pd.testing.assert_frame_equal(sample_df, deserialized)

    def test_cache_set_success(self, feature_cache, sample_df, mock_redis):
        """Test successful cache set operation."""
        success = feature_cache.set("BTCUSDT", "1h", "rsi_14", sample_df)
        
        assert success is True
        mock_redis.setex.assert_called_once()
        
        # Check call arguments
        call_args = mock_redis.setex.call_args
        key = call_args[0][0]
        ttl = call_args[0][1]
        
        assert "BTCUSDT" in key
        assert "rsi_14" in key
        assert ttl == 3600  # 1h timeframe

    def test_cache_set_custom_ttl(self, feature_cache, sample_df, mock_redis):
        """Test cache set with custom TTL."""
        feature_cache.set("BTCUSDT", "1h", "rsi_14", sample_df, ttl=7200)
        
        call_args = mock_redis.setex.call_args
        ttl = call_args[0][1]
        
        assert ttl == 7200  # Custom TTL used

    def test_cache_set_empty_dataframe(self, feature_cache):
        """Test cache set with empty DataFrame."""
        empty_df = pd.DataFrame()
        success = feature_cache.set("BTCUSDT", "1h", "rsi_14", empty_df)
        
        assert success is False  # Should not cache empty data

    def test_cache_get_hit(self, feature_cache, sample_df, mock_redis):
        """Test cache get with hit."""
        # Serialize sample data
        serialized = feature_cache._serialize_dataframe(sample_df)
        mock_redis.get.return_value = serialized
        
        # Get from cache
        result = feature_cache.get("BTCUSDT", "1h", "rsi_14")
        
        assert result is not None
        pd.testing.assert_frame_equal(result, sample_df)
        assert feature_cache.stats["hits"] == 1
        assert feature_cache.stats["misses"] == 0

    def test_cache_get_miss(self, feature_cache, mock_redis):
        """Test cache get with miss."""
        mock_redis.get.return_value = None
        
        result = feature_cache.get("BTCUSDT", "1h", "rsi_14")
        
        assert result is None
        assert feature_cache.stats["misses"] == 1
        assert feature_cache.stats["hits"] == 0

    def test_cache_get_no_redis(self):
        """Test cache get when Redis is unavailable."""
        with patch("redis.from_url", side_effect=Exception("Connection failed")):
            from cache.feature_cache import FeatureCache
            cache = FeatureCache()
            
            result = cache.get("BTCUSDT", "1h", "rsi_14")
            assert result is None

    def test_get_features_bulk(self, feature_cache, sample_df, mock_redis):
        """Test bulk feature retrieval."""
        serialized = feature_cache._serialize_dataframe(sample_df)
        mock_redis.get.return_value = serialized
        
        results = feature_cache.get_features("BTCUSDT", "1h", ["rsi_14", "macd", "sma_20"])
        
        assert len(results) == 3
        assert all(k in results for k in ["rsi_14", "macd", "sma_20"])

    def test_set_features_bulk(self, feature_cache, sample_df, mock_redis):
        """Test bulk feature storage."""
        features = {
            "rsi_14": sample_df[["timestamp", "rsi_14"]],
            "macd": sample_df[["timestamp", "macd"]],
        }
        
        count = feature_cache.set_features("BTCUSDT", "1h", features)
        
        assert count == 2
        assert mock_redis.setex.call_count == 2

    def test_invalidate_specific_symbol(self, feature_cache, mock_redis):
        """Test cache invalidation for specific symbol."""
        mock_redis.scan_iter.return_value = iter([
            b"test_features:BTCUSDT:1h:rsi_14",
            b"test_features:BTCUSDT:1h:macd",
        ])
        mock_redis.delete.return_value = 2
        
        deleted = feature_cache.invalidate(symbol="BTCUSDT")
        
        assert deleted == 2
        mock_redis.delete.assert_called_once()

    def test_invalidate_all(self, feature_cache, mock_redis):
        """Test cache invalidation for all data."""
        mock_redis.scan_iter.return_value = iter([
            b"test_features:BTCUSDT:1h:rsi_14",
            b"test_features:ETHUSDT:1h:rsi_14",
        ])
        mock_redis.delete.return_value = 2
        
        deleted = feature_cache.invalidate()
        
        assert deleted == 2

    def test_get_stats(self, feature_cache):
        """Test cache statistics retrieval."""
        # Simulate some cache activity
        feature_cache.stats["hits"] = 10
        feature_cache.stats["misses"] = 5
        feature_cache.stats["sets"] = 15
        
        stats = feature_cache.get_stats()
        
        assert stats["stats_enabled"] is True
        assert stats["hits"] == 10
        assert stats["misses"] == 5
        assert stats["total_requests"] == 15
        assert stats["hit_rate"] == 10 / 15

    def test_clear_stats(self, feature_cache):
        """Test statistics clearing."""
        feature_cache.stats["hits"] = 100
        feature_cache.stats["misses"] = 50
        
        feature_cache.clear_stats()
        
        assert feature_cache.stats["hits"] == 0
        assert feature_cache.stats["misses"] == 0

    def test_get_info(self, feature_cache, mock_redis):
        """Test Redis info retrieval."""
        mock_redis.scan_iter.return_value = iter([b"key1", b"key2", b"key3"])
        
        info = feature_cache.get_info()
        
        assert info["connected"] is True
        assert info["namespace"] == "test_features"
        assert info["key_count"] == 3
        assert "redis_version" in info

    def test_cache_statistics_tracking(self, feature_cache, sample_df, mock_redis):
        """Test that statistics are tracked correctly."""
        # Set
        feature_cache.set("BTCUSDT", "1h", "rsi_14", sample_df)
        assert feature_cache.stats["sets"] == 1
        
        # Hit
        serialized = feature_cache._serialize_dataframe(sample_df)
        mock_redis.get.return_value = serialized
        feature_cache.get("BTCUSDT", "1h", "rsi_14")
        assert feature_cache.stats["hits"] == 1
        
        # Miss
        mock_redis.get.return_value = None
        feature_cache.get("ETHUSDT", "1h", "rsi_14")
        assert feature_cache.stats["misses"] == 1

    def test_get_cache_instance_singleton(self):
        """Test that get_cache_instance returns singleton."""
        with patch("redis.from_url"):
            with patch("redis.ConnectionPool.from_url"):
                from cache.feature_cache import get_cache_instance
                
                cache1 = get_cache_instance()
                cache2 = get_cache_instance()
                
                assert cache1 is cache2  # Same instance


if __name__ == "__main__":
    pytest.main([__file__])
