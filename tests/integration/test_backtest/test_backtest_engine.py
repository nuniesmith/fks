"""
Test suite for trading.utils.backtest_engine module

Tests cover:
- Length consistency between equity and index arrays
- Proper return calculations
- Trade execution logic
- Edge cases and error handling
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.backtest import run_backtest


class TestBacktestEngine:
    """Test backtest engine functionality"""
    
    @pytest.fixture
    def sample_prices(self):
        """Generate sample multi-symbol OHLCV data for testing"""
        dates = pd.date_range(start='2023-01-01', periods=1000, freq='1h')
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        df_prices = {}
        
        np.random.seed(42)
        for i, symbol in enumerate(symbols):
            # Create synthetic price data with trend
            base_price = 100 * (i + 1)  # Different base prices
            closes = base_price + np.cumsum(np.random.randn(1000) * 2)
            highs = closes + np.abs(np.random.randn(1000) * 1)
            lows = closes - np.abs(np.random.randn(1000) * 1)
            opens = closes + np.random.randn(1000) * 0.5
            volumes = np.random.randint(1000, 10000, 1000)
            
            df = pd.DataFrame({
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            }, index=dates)
            
            df_prices[symbol] = df
        
        return df_prices
    
    @pytest.fixture
    def symbols_config(self):
        """Standard symbols configuration"""
        return {
            'SYMBOLS': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
            'MAINS': ['BTCUSDT', 'ETHUSDT'],
            'ALTS': ['SOLUSDT']
        }
    
    def test_array_length_consistency(self, sample_prices, symbols_config):
        """
        Critical test: Verify equity array and equity_index have matching lengths
        This was the bug causing: "Length of values (1000) does not match length of index (1001)"
        """
        M = 78
        atr_period = 29
        sl_multiplier = 3.9
        tp_multiplier = 6.4
        
        # Run backtest - should not raise ValueError
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices=sample_prices,
            M=M,
            atr_period=atr_period,
            sl_multiplier=sl_multiplier,
            tp_multiplier=tp_multiplier,
            symbols_config=symbols_config,
            fee_rate=0.001
        )
        
        # Verify no errors occurred
        assert metrics is not None
        assert returns is not None
        assert cum_ret is not None
        assert trades is not None
        
        # Verify return series length matches expected
        # cum_ret should have same length as the price data
        assert len(cum_ret) == 1000, f"cum_ret length {len(cum_ret)} != 1000"
        
        # Verify returns series length
        assert len(returns) == 1000, f"returns length {len(returns)} != 1000"
        
        # Verify cumulative returns start at 1.0 (normalized)
        assert cum_ret.iloc[0] == 1.0, f"cum_ret should start at 1.0, got {cum_ret.iloc[0]}"
    
    def test_basic_backtest_execution(self, sample_prices, symbols_config):
        """Test basic backtest execution with standard parameters"""
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices=sample_prices,
            M=20,
            atr_period=14,
            sl_multiplier=2.0,
            tp_multiplier=3.0,
            symbols_config=symbols_config,
            fee_rate=0.001
        )
        
        # Check metrics structure
        assert isinstance(metrics, dict)
        required_metrics = ['Sharpe', 'Sortino', 'Calmar', 'Total Return', 
                          'Max Drawdown', 'Win Rate', 'Num Trades']
        for metric in required_metrics:
            assert metric in metrics, f"Missing metric: {metric}"
        
        # Check return series
        assert isinstance(returns, pd.Series)
        assert len(returns) > 0
        assert not returns.isna().all()
        
        # Check cumulative returns
        assert isinstance(cum_ret, pd.Series)
        assert len(cum_ret) > 0
        assert cum_ret.iloc[0] == 1.0  # Should start normalized to 1
        
        # Check trades
        assert isinstance(trades, list)
    
    def test_multiple_optuna_trials(self, sample_prices, symbols_config):
        """
        Test multiple backtest runs with different parameters (simulating Optuna trials)
        This replicates the scenario from the error log
        """
        trial_params = [
            {'M': 78, 'atr_period': 29, 'sl_multiplier': 3.9, 'tp_multiplier': 6.4},
            {'M': 35, 'atr_period': 9, 'sl_multiplier': 1.2, 'tp_multiplier': 8.8},
            {'M': 122, 'atr_period': 23, 'sl_multiplier': 1.1, 'tp_multiplier': 9.7},
            {'M': 168, 'atr_period': 10, 'sl_multiplier': 1.7, 'tp_multiplier': 2.7},
            {'M': 64, 'atr_period': 18, 'sl_multiplier': 2.7, 'tp_multiplier': 3.6},
        ]
        
        for i, params in enumerate(trial_params):
            try:
                metrics, returns, cum_ret, trades = run_backtest(
                    df_prices=sample_prices,
                    M=params['M'],
                    atr_period=params['atr_period'],
                    sl_multiplier=params['sl_multiplier'],
                    tp_multiplier=params['tp_multiplier'],
                    symbols_config=symbols_config,
                    fee_rate=0.001
                )
                
                # All trials should complete without ValueError
                assert metrics is not None
                assert len(cum_ret) == 1000
                assert len(returns) == 1000
                
            except ValueError as e:
                pytest.fail(f"Trial {i} failed with ValueError: {e}")
    
    def test_edge_case_short_data(self, symbols_config):
        """Test backtest with minimal data length"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='1h')
        
        df_prices = {}
        for symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
            df = pd.DataFrame({
                'open': 100.0,
                'high': 101.0,
                'low': 99.0,
                'close': 100.0,
                'volume': 1000
            }, index=dates)
            df_prices[symbol] = df
        
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices=df_prices,
            M=10,
            atr_period=5,
            sl_multiplier=2.0,
            tp_multiplier=3.0,
            symbols_config=symbols_config,
            fee_rate=0.001
        )
        
        # Should complete without error
        assert len(cum_ret) == 50
        assert len(returns) == 50
        assert metrics is not None
    
    def test_no_signal_changes(self, symbols_config):
        """Test backtest where signal never changes (no trades)"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
        
        # Create strongly trending up data (signal will stay 1 after initial period)
        df_prices = {}
        for symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
            closes = 100 + np.arange(100) * 2  # Strong uptrend
            df = pd.DataFrame({
                'open': closes,
                'high': closes + 1,
                'low': closes - 1,
                'close': closes,
                'volume': 1000
            }, index=dates)
            df_prices[symbol] = df
        
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices=df_prices,
            M=10,
            atr_period=5,
            sl_multiplier=2.0,
            tp_multiplier=3.0,
            symbols_config=symbols_config,
            fee_rate=0.001
        )
        
        # Should complete without error even with few/no trades
        assert len(cum_ret) == 100
        assert len(returns) == 100
        assert metrics['Num Trades'] >= 0
    
    def test_returns_calculation(self, sample_prices, symbols_config):
        """Test that returns are calculated correctly"""
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices=sample_prices,
            M=20,
            atr_period=14,
            sl_multiplier=2.0,
            tp_multiplier=3.0,
            symbols_config=symbols_config,
            fee_rate=0.001
        )
        
        # First return should be 0 (no change from initial capital)
        assert returns.iloc[0] == 0.0, f"First return should be 0, got {returns.iloc[0]}"
        
        # Returns should be finite
        assert not returns.isna().any(), "Returns contain NaN values"
        assert not np.isinf(returns).any(), "Returns contain infinite values"
        
        # Cumulative returns should be monotonic or have reasonable variance
        assert cum_ret.min() > 0, "Cumulative returns should be positive"
    
    def test_fee_impact(self, sample_prices, symbols_config):
        """Test that transaction fees impact returns"""
        # Run with no fees
        metrics_no_fee, returns_no_fee, cum_ret_no_fee, trades_no_fee = run_backtest(
            df_prices=sample_prices,
            M=20,
            atr_period=14,
            sl_multiplier=2.0,
            tp_multiplier=3.0,
            symbols_config=symbols_config,
            fee_rate=0.0
        )
        
        # Run with fees
        metrics_with_fee, returns_with_fee, cum_ret_with_fee, trades_with_fee = run_backtest(
            df_prices=sample_prices,
            M=20,
            atr_period=14,
            sl_multiplier=2.0,
            tp_multiplier=3.0,
            symbols_config=symbols_config,
            fee_rate=0.001
        )
        
        # If there are trades, fees should reduce returns
        if metrics_no_fee['Num Trades'] > 0:
            assert metrics_with_fee['Total Return'] <= metrics_no_fee['Total Return'], \
                "Fees should reduce or maintain total returns"
    
    def test_parameter_ranges(self, sample_prices, symbols_config):
        """Test backtest with extreme parameter values"""
        extreme_params = [
            {'M': 5, 'atr_period': 5, 'sl_multiplier': 1.0, 'tp_multiplier': 1.0},
            {'M': 200, 'atr_period': 30, 'sl_multiplier': 5.0, 'tp_multiplier': 10.0},
            {'M': 100, 'atr_period': 15, 'sl_multiplier': 0.5, 'tp_multiplier': 20.0},
        ]
        
        for params in extreme_params:
            metrics, returns, cum_ret, trades = run_backtest(
                df_prices=sample_prices,
                M=params['M'],
                atr_period=params['atr_period'],
                sl_multiplier=params['sl_multiplier'],
                tp_multiplier=params['tp_multiplier'],
                symbols_config=symbols_config,
                fee_rate=0.001
            )
            
            # Should complete without error
            assert metrics is not None
            assert len(cum_ret) == 1000
            assert len(returns) == 1000
    
    def test_single_symbol(self):
        """Test backtest with single symbol"""
        dates = pd.date_range(start='2023-01-01', periods=500, freq='1h')
        
        np.random.seed(42)
        closes = 100 + np.cumsum(np.random.randn(500) * 2)
        df = pd.DataFrame({
            'open': closes,
            'high': closes + np.abs(np.random.randn(500)),
            'low': closes - np.abs(np.random.randn(500)),
            'close': closes,
            'volume': 1000
        }, index=dates)
        
        df_prices = {'BTCUSDT': df}
        symbols_config = {
            'SYMBOLS': ['BTCUSDT'],
            'MAINS': ['BTCUSDT'],
            'ALTS': []
        }
        
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices=df_prices,
            M=20,
            atr_period=14,
            sl_multiplier=2.0,
            tp_multiplier=3.0,
            symbols_config=symbols_config,
            fee_rate=0.001
        )
        
        # Should complete without error
        assert len(cum_ret) == 500
        assert len(returns) == 500
        assert metrics is not None
    
    def test_trades_structure(self, sample_prices, symbols_config):
        """Test that trade records have correct structure"""
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices=sample_prices,
            M=20,
            atr_period=14,
            sl_multiplier=2.0,
            tp_multiplier=3.0,
            symbols_config=symbols_config,
            fee_rate=0.001
        )
        
        if len(trades) > 0:
            # Check ENTER trades
            enter_trades = [t for t in trades if t['action'] == 'ENTER']
            if enter_trades:
                trade = enter_trades[0]
                assert 'date' in trade
                assert 'action' in trade
                assert 'symbols' in trade
                assert 'prices' in trade
                assert 'sl' in trade
                assert 'tp' in trade
                assert 'capital_deployed' in trade
            
            # Check EXIT trades
            exit_trades = [t for t in trades if t['action'] == 'EXIT']
            if exit_trades:
                trade = exit_trades[0]
                assert 'date' in trade
                assert 'action' in trade
                assert 'symbols' in trade
                assert 'prices' in trade
                assert 'capital_received' in trade


class TestCalculateMetrics:
    """Test metrics calculation function"""
    
    def test_metrics_calculation_basic(self):
        """Test basic metrics calculation"""
        # Create sample returns
        daily_returns = [0.0] + [0.01] * 50 + [-0.01] * 30 + [0.02] * 20
        
        dates = pd.date_range(start='2023-01-01', periods=len(daily_returns), freq='D')
        cum_ret = pd.Series([1.0] * len(daily_returns), index=dates)
        cum_ret = cum_ret * (1 + pd.Series(daily_returns)).cumprod()
        
        trades = [
            {'action': 'ENTER', 'date': dates[10]},
            {'action': 'EXIT', 'date': dates[30]},
            {'action': 'ENTER', 'date': dates[40]},
            {'action': 'EXIT', 'date': dates[60]},
        ]
        
        metrics = calculate_metrics(daily_returns, cum_ret, trades, dates)
        
        # Check all required metrics are present
        assert 'Sharpe' in metrics
        assert 'Sortino' in metrics
        assert 'Calmar' in metrics
        assert 'Total Return' in metrics
        assert 'Max Drawdown' in metrics
        assert 'Win Rate' in metrics
        assert 'Num Trades' in metrics
        
        # Check metric ranges
        assert metrics['Max Drawdown'] <= 0  # Should be negative or zero
        assert 0 <= metrics['Win Rate'] <= 1  # Should be between 0 and 1
        assert metrics['Num Trades'] >= 0  # Should be non-negative
    
    def test_metrics_no_trades(self):
        """Test metrics calculation with no trades"""
        daily_returns = [0.0] * 100
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        cum_ret = pd.Series([1.0] * 100, index=dates)
        trades = []
        
        metrics = calculate_metrics(daily_returns, cum_ret, trades, dates)
        
        assert metrics['Num Trades'] == 0
        assert metrics['Win Rate'] == 0
        # Sharpe should be 0 or undefined for no returns
        assert metrics['Sharpe'] == 0 or np.isnan(metrics['Sharpe'])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
