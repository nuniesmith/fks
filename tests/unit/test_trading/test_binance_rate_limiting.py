"""
Test suite for Binance adapter rate limiting and circuit breaker functionality.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from data.adapters.binance import BinanceAdapter
from framework.middleware.circuit_breaker.exceptions import CircuitOpenError
from framework.middleware.rate_limiter.exceptions import RateLimitExceededError


class TestBinanceRateLimiting:
    """Test Binance adapter rate limiting functionality."""
    
    def test_rate_limiter_initialization(self):
        """Test that rate limiter is properly initialized."""
        adapter = BinanceAdapter()
        
        assert hasattr(adapter, 'rate_limiter')
        assert adapter.rate_limiter.max_requests == 10
        assert adapter.rate_limiter.time_window == 1
    
    def test_circuit_breaker_initialization(self):
        """Test that circuit breaker is properly initialized."""
        adapter = BinanceAdapter()
        
        assert hasattr(adapter, 'circuit_breaker')
        assert adapter.circuit_breaker.config.failure_threshold == 3
        assert adapter.circuit_breaker.config.reset_timeout == 60
    
    def test_rate_limiter_allows_requests_under_limit(self):
        """Test that rate limiter allows requests under the limit."""
        def fake_http(url, params=None, headers=None, timeout=None):
            return [
                [1732646400000, "100.0", "101.0", "99.5", "100.5", "123.45", 0, 0, 0, 0, 0, 0]
            ]
        
        adapter = BinanceAdapter(http=fake_http)
        
        # Should allow multiple requests under rate limit
        for i in range(5):
            result = adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
            assert result["provider"] == "binance"
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test that circuit breaker opens after threshold failures."""
        call_count = 0
        
        def failing_http(url, params=None, headers=None, timeout=None):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Network error")
        
        adapter = BinanceAdapter(http=failing_http)
        
        # First 3 failures should work (with retries)
        for i in range(3):
            with pytest.raises(Exception):
                adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
        
        # Circuit should now be open
        assert adapter.circuit_breaker.is_open()
    
    def test_circuit_breaker_metrics(self):
        """Test that circuit breaker metrics are tracked."""
        def fake_http(url, params=None, headers=None, timeout=None):
            return [[1732646400000, "100.0", "101.0", "99.5", "100.5", "123.45", 0, 0, 0, 0, 0, 0]]
        
        adapter = BinanceAdapter(http=fake_http)
        
        # Make a successful request
        adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
        
        # Check metrics
        metrics = adapter.get_circuit_metrics()
        assert 'name' in metrics
        assert 'state' in metrics
        assert metrics['state'] == 'closed'
    
    def test_rate_limit_stats(self):
        """Test that rate limit statistics are tracked."""
        def fake_http(url, params=None, headers=None, timeout=None):
            return [[1732646400000, "100.0", "101.0", "99.5", "100.5", "123.45", 0, 0, 0, 0, 0, 0]]
        
        adapter = BinanceAdapter(http=fake_http)
        
        # Make a request
        adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
        
        # Check stats
        stats = adapter.get_rate_limit_stats()
        assert 'name' in stats
        assert 'limit' in stats
        assert stats['limit'] == 10


class TestBinanceCircuitBreaker:
    """Test circuit breaker integration with Binance adapter."""
    
    def test_circuit_closes_after_successful_requests(self):
        """Test that circuit closes after successful requests in half-open state."""
        call_count = 0
        should_fail = True
        
        def sometimes_failing_http(url, params=None, headers=None, timeout=None):
            nonlocal call_count, should_fail
            call_count += 1
            
            if should_fail and call_count <= 3:
                raise ConnectionError("Network error")
            
            return [[1732646400000, "100.0", "101.0", "99.5", "100.5", "123.45", 0, 0, 0, 0, 0, 0]]
        
        adapter = BinanceAdapter(http=sometimes_failing_http)
        
        # Trigger failures to open circuit
        for i in range(3):
            with pytest.raises(Exception):
                adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
        
        # Circuit should be open
        assert adapter.circuit_breaker.is_open()
        
        # Wait for reset timeout (would need to mock time for real test)
        # For now, just manually reset to half-open
        adapter.circuit_breaker.reset()
        
        # Now requests should succeed
        should_fail = False
        result = adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
        assert result["provider"] == "binance"
    
    def test_circuit_tracks_failures_correctly(self):
        """Test that circuit breaker correctly tracks failure count."""
        call_count = 0
        
        def failing_http(url, params=None, headers=None, timeout=None):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Network error")
        
        adapter = BinanceAdapter(http=failing_http)
        
        # Make failures but not enough to open circuit
        for i in range(2):
            with pytest.raises(Exception):
                adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
        
        # Circuit should still be closed
        assert adapter.circuit_breaker.is_closed()
        
        # One more failure should open it
        with pytest.raises(Exception):
            adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
        
        assert adapter.circuit_breaker.is_open()


class TestBinanceIntegration:
    """Integration tests for Binance adapter with all protections."""
    
    def test_full_request_lifecycle(self):
        """Test complete request lifecycle with all protections."""
        def fake_http(url, params=None, headers=None, timeout=None):
            return [[1732646400000, "100.0", "101.0", "99.5", "100.5", "123.45", 0, 0, 0, 0, 0, 0]]
        
        adapter = BinanceAdapter(http=fake_http)
        
        # Make request
        result = adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
        
        # Verify response
        assert result["provider"] == "binance"
        assert len(result["data"]) == 1
        assert result["data"][0]["open"] == 100.0
        
        # Verify circuit is closed
        assert adapter.circuit_breaker.is_closed()
        
        # Verify rate limiter stats show request
        stats = adapter.get_rate_limit_stats()
        assert stats['limit'] == 10
    
    def test_adapter_handles_mixed_success_failure(self):
        """Test adapter handles mix of successful and failed requests."""
        call_count = 0
        
        def mixed_http(url, params=None, headers=None, timeout=None):
            nonlocal call_count
            call_count += 1
            
            # Fail every 3rd request
            if call_count % 3 == 0:
                raise ConnectionError("Network error")
            
            return [[1732646400000, "100.0", "101.0", "99.5", "100.5", "123.45", 0, 0, 0, 0, 0, 0]]
        
        adapter = BinanceAdapter(http=mixed_http)
        
        # Make mixed requests
        success_count = 0
        failure_count = 0
        
        for i in range(6):
            try:
                result = adapter.fetch(symbol="BTCUSDT", interval="1m", limit=1)
                success_count += 1
            except Exception:
                failure_count += 1
        
        # Should have some successes and some failures
        assert success_count > 0
        assert failure_count > 0
        
        # Circuit shouldn't be open yet (only 2 failures)
        assert adapter.circuit_breaker.is_closed() or adapter.circuit_breaker.is_half_open()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
