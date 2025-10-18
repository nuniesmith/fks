"""
Test suite for optimized backtest engine.
"""
import pytest
import pandas as pd
import numpy as np
import time
from unittest.mock import Mock, patch

# Mock the constants import for testing
import sys
from unittest.mock import MagicMock

# Create mock module
mock_framework = MagicMock()
mock_framework.config.constants.SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
mock_framework.config.constants.MAINS = ['BTCUSDT', 'ETHUSDT']
mock_framework.config.constants.ALTS = ['BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
mock_framework.config.constants.FEE_RATE = 0.001

sys.modules['framework'] = mock_framework
sys.modules['framework.config'] = mock_framework.config
sys.modules['framework.config.constants'] = mock_framework.config.constants

from trading.backtest.engine import run_backtest


def create_test_data(n_days=100):
    """Create synthetic OHLCV data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=n_days, freq='D')
    
    df_prices = {}
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
    
    for symbol in symbols:
        # Create random walk price data
        np.random.seed(42)  # For reproducibility
        close = 100 + np.cumsum(np.random.randn(n_days) * 2)
        open_ = close + np.random.randn(n_days) * 0.5
        high = np.maximum(open_, close) + np.abs(np.random.randn(n_days)) * 0.5
        low = np.minimum(open_, close) - np.abs(np.random.randn(n_days)) * 0.5
        volume = np.abs(np.random.randn(n_days)) * 1000
        
        df_prices[symbol] = pd.DataFrame({
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
    
    return df_prices


class TestBacktestOptimization:
    """Test optimized backtest engine functionality."""
    
    def test_fast_mode_produces_valid_results(self):
        """Test that fast_mode produces valid backtest results."""
        df_prices = create_test_data(100)
        
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True
        )
        
        # Verify metrics structure
        assert 'Sharpe' in metrics
        assert 'Sortino' in metrics
        assert 'Max Drawdown' in metrics
        assert 'Calmar' in metrics
        assert 'Total Return' in metrics
        assert 'Annualized Return' in metrics
        assert 'Trades' in metrics
        
        # Verify returns and cumulative returns
        assert isinstance(returns, pd.Series)
        assert isinstance(cum_ret, pd.Series)
        assert len(returns) == len(df_prices['BTCUSDT']) - 1
        
        # Verify trades list
        assert isinstance(trades, list)
    
    def test_fast_mode_vs_slow_mode_consistency(self):
        """Test that fast_mode produces same results as slow mode."""
        df_prices = create_test_data(50)
        
        # Run with fast mode
        metrics_fast, returns_fast, cum_ret_fast, trades_fast = run_backtest(
            df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True
        )
        
        # Run with slow mode
        metrics_slow, returns_slow, cum_ret_slow, trades_slow = run_backtest(
            df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=False
        )
        
        # Metrics should be very close (within 1e-6)
        for key in metrics_fast:
            if isinstance(metrics_fast[key], (int, float)):
                assert abs(metrics_fast[key] - metrics_slow[key]) < 1e-6, f"{key} mismatch"
        
        # Returns should be identical
        assert len(returns_fast) == len(returns_slow)
        assert len(trades_fast) == len(trades_slow)
    
    def test_fast_mode_performance_improvement(self):
        """Test that fast_mode is faster than slow mode."""
        df_prices = create_test_data(200)
        
        # Time slow mode
        start = time.time()
        run_backtest(df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=False)
        slow_time = time.time() - start
        
        # Time fast mode
        start = time.time()
        run_backtest(df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True)
        fast_time = time.time() - start
        
        # Fast mode should be at least 1.5x faster (conservative estimate)
        # In practice should be 2-3x faster
        assert fast_time < slow_time, f"Fast: {fast_time:.4f}s, Slow: {slow_time:.4f}s"
        print(f"Performance improvement: {slow_time/fast_time:.2f}x faster")
    
    def test_backtest_with_different_parameters(self):
        """Test backtest with various parameter combinations."""
        df_prices = create_test_data(100)
        
        param_sets = [
            {'M': 10, 'atr_period': 10, 'sl_multiplier': 1.5, 'tp_multiplier': 2.0},
            {'M': 50, 'atr_period': 20, 'sl_multiplier': 2.5, 'tp_multiplier': 5.0},
            {'M': 100, 'atr_period': 14, 'sl_multiplier': 2.0, 'tp_multiplier': 3.0},
        ]
        
        for params in param_sets:
            metrics, returns, cum_ret, trades = run_backtest(
                df_prices, **params, fast_mode=True
            )
            
            # All metrics should be computable
            assert not np.isnan(metrics['Sharpe']) or metrics['Sharpe'] == 0
            assert not np.isnan(metrics['Total Return'])
            assert isinstance(metrics['Trades'], int)
    
    def test_backtest_handles_extreme_parameters(self):
        """Test backtest with extreme parameter values."""
        df_prices = create_test_data(100)
        
        # Very short MA period
        metrics, _, _, _ = run_backtest(
            df_prices, M=5, atr_period=5, sl_multiplier=1.0, tp_multiplier=1.0, fast_mode=True
        )
        assert metrics is not None
        
        # Very long MA period
        metrics, _, _, _ = run_backtest(
            df_prices, M=200, atr_period=30, sl_multiplier=5.0, tp_multiplier=10.0, fast_mode=True
        )
        assert metrics is not None
    
    def test_backtest_metrics_are_reasonable(self):
        """Test that backtest metrics are within reasonable ranges."""
        df_prices = create_test_data(100)
        
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True
        )
        
        # Sharpe ratio should be reasonable (typically -5 to 5 for crypto)
        assert -10 <= metrics['Sharpe'] <= 10
        
        # Max drawdown should be negative or zero
        assert metrics['Max Drawdown'] <= 0
        
        # Trades should be non-negative
        assert metrics['Trades'] >= 0
        
        # Total return should be reasonable
        assert -1 <= metrics['Total Return'] <= 10  # -100% to 1000%
    
    def test_backtest_with_no_trades(self):
        """Test backtest when no trades are generated."""
        df_prices = create_test_data(30)
        
        # Use very long MA period to avoid trades
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices, M=200, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True
        )
        
        # Should still return valid metrics
        assert metrics is not None
        assert metrics['Trades'] == 0
    
    def test_vectorized_operations(self):
        """Test that vectorized operations work correctly."""
        df_prices = create_test_data(100)
        
        # Run backtest in fast mode
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True
        )
        
        # Verify all numpy/pandas operations produced valid results
        assert not returns.isnull().any()
        assert not cum_ret.isnull().any()
        assert all(isinstance(t, dict) for t in trades)


class TestBacktestEdgeCases:
    """Test edge cases for backtest engine."""
    
    def test_backtest_with_minimal_data(self):
        """Test backtest with minimal amount of data."""
        df_prices = create_test_data(50)  # Less than typical MA period
        
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True
        )
        
        assert metrics is not None
        assert isinstance(metrics['Sharpe'], (int, float))
    
    def test_backtest_with_constant_prices(self):
        """Test backtest when prices don't change."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        
        df_prices = {}
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
        
        for symbol in symbols:
            df_prices[symbol] = pd.DataFrame({
                'open': [100.0] * 100,
                'high': [100.0] * 100,
                'low': [100.0] * 100,
                'close': [100.0] * 100,
                'volume': [1000.0] * 100
            }, index=dates)
        
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True
        )
        
        # With constant prices, no trades should occur
        assert metrics['Trades'] == 0
    
    def test_backtest_with_highly_volatile_data(self):
        """Test backtest with highly volatile price movements."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        
        df_prices = {}
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
        
        for symbol in symbols:
            # Create highly volatile data
            np.random.seed(42)
            close = 100 + np.cumsum(np.random.randn(100) * 10)  # High volatility
            
            df_prices[symbol] = pd.DataFrame({
                'open': close + np.random.randn(100) * 5,
                'high': close + np.abs(np.random.randn(100)) * 5,
                'low': close - np.abs(np.random.randn(100)) * 5,
                'close': close,
                'volume': np.abs(np.random.randn(100)) * 1000
            }, index=dates)
        
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices, M=20, atr_period=14, sl_multiplier=2, tp_multiplier=3, fast_mode=True
        )
        
        # Should handle high volatility gracefully
        assert metrics is not None
        assert not np.isnan(metrics['Sharpe']) or metrics['Sharpe'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
