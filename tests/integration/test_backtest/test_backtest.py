"""
Test suite for backtest module
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from trading.backtest import run_backtest


class TestBacktest:
    """Test backtest functionality"""
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data for testing"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        
        # Create synthetic price data with trend
        np.random.seed(42)
        closes = 100 + np.cumsum(np.random.randn(100) * 2)
        highs = closes + np.abs(np.random.randn(100) * 1)
        lows = closes - np.abs(np.random.randn(100) * 1)
        opens = closes + np.random.randn(100) * 0.5
        volumes = np.random.randint(1000, 10000, 100)
        
        df = pd.DataFrame({
            'time': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        df.set_index('time', inplace=True)
        
        return df
    
    def test_run_backtest_basic(self, sample_data):
        """Test basic backtest execution"""
        M = 20
        atr_period = 14
        sl_multiplier = 2.0
        tp_multiplier = 3.0
        
        metrics, equity_curve, trades, signals = run_backtest(
            sample_data, M, atr_period, sl_multiplier, tp_multiplier
        )
        
        # Check that metrics is a dictionary with expected keys
        assert isinstance(metrics, dict)
        assert 'total_return' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
        assert 'win_rate' in metrics
        assert 'num_trades' in metrics
        
        # Check equity curve
        assert isinstance(equity_curve, pd.Series)
        assert len(equity_curve) > 0
        assert equity_curve.iloc[0] > 0  # Should start with positive equity
        
        # Check trades list
        assert isinstance(trades, list)
        
        # Check signals
        assert isinstance(signals, pd.DataFrame)
        assert len(signals) == len(sample_data)
    
    def test_run_backtest_no_trades(self):
        """Test backtest with conditions that generate no trades"""
        # Create flat price data
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        df = pd.DataFrame({
            'time': dates,
            'open': 100.0,
            'high': 100.1,
            'low': 99.9,
            'close': 100.0,
            'volume': 1000
        })
        df.set_index('time', inplace=True)
        
        metrics, equity_curve, trades, signals = run_backtest(
            df, M=20, atr_period=14, sl_multiplier=2.0, tp_multiplier=3.0
        )
        
        # Should complete without error
        assert metrics['num_trades'] >= 0
        assert len(equity_curve) > 0
    
    def test_run_backtest_parameters(self, sample_data):
        """Test backtest with different parameter combinations"""
        params = [
            (10, 7, 1.5, 2.0),
            (20, 14, 2.0, 3.0),
            (30, 21, 2.5, 4.0),
        ]
        
        for M, atr_period, sl_mult, tp_mult in params:
            metrics, equity_curve, trades, signals = run_backtest(
                sample_data, M, atr_period, sl_mult, tp_mult
            )
            
            # Should complete without error
            assert isinstance(metrics, dict)
            assert len(equity_curve) > 0
            assert isinstance(trades, list)
    
    def test_calculate_metrics_basic(self):
        """Test metrics calculation"""
        # Create sample equity curve
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        equity = pd.Series(
            1.0 + np.cumsum(np.random.randn(100) * 0.01),
            index=dates
        )
        
        trades = [
            {'pnl': 100, 'entry_price': 100, 'exit_price': 110},
            {'pnl': -50, 'entry_price': 110, 'exit_price': 105},
            {'pnl': 75, 'entry_price': 105, 'exit_price': 112},
        ]
        
        metrics = calculate_metrics(equity, trades)
        
        assert 'total_return' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
        assert 'win_rate' in metrics
        assert 'num_trades' in metrics
        
        assert metrics['num_trades'] == 3
        assert 0 <= metrics['win_rate'] <= 1
    
    def test_calculate_metrics_no_trades(self):
        """Test metrics calculation with no trades"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        equity = pd.Series(np.ones(100), index=dates)
        
        metrics = calculate_metrics(equity, [])
        
        assert metrics['num_trades'] == 0
        assert metrics['win_rate'] == 0
        assert metrics['total_return'] >= 0
    
    def test_equity_curve_consistency(self, sample_data):
        """Test that equity curve is consistent (no NaN, always positive)"""
        metrics, equity_curve, trades, signals = run_backtest(
            sample_data, M=20, atr_period=14, sl_multiplier=2.0, tp_multiplier=3.0
        )
        
        # Check for NaN values
        assert not equity_curve.isna().any()
        
        # Equity should always be positive
        assert (equity_curve > 0).all()
        
        # Check index continuity
        assert equity_curve.index.is_monotonic_increasing
    
    def test_backtest_length_consistency(self, sample_data):
        """Test that output lengths match input data"""
        metrics, equity_curve, trades, signals = run_backtest(
            sample_data, M=20, atr_period=14, sl_multiplier=2.0, tp_multiplier=3.0
        )
        
        # Signals should match input length
        assert len(signals) == len(sample_data)
        
        # Equity curve should match input length
        assert len(equity_curve) == len(sample_data)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
