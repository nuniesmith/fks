"""
Test suite for signals module
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from signals import generate_signals, calculate_rsi, calculate_macd


class TestSignals:
    """Test signal generation functionality"""
    
    @pytest.fixture
    def sample_prices(self):
        """Generate sample price data for testing"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        closes = 100 + np.cumsum(np.random.randn(100) * 2)
        
        df = pd.DataFrame({
            'time': dates,
            'close': closes
        })
        df.set_index('time', inplace=True)
        
        return df
    
    def test_calculate_rsi_basic(self, sample_prices):
        """Test RSI calculation"""
        rsi = calculate_rsi(sample_prices['close'], period=14)
        
        # Check output type and length
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(sample_prices)
        
        # RSI should be between 0 and 100
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()
        
        # First 14 values should be NaN
        assert rsi.iloc[:13].isna().all()
    
    def test_calculate_rsi_edge_cases(self):
        """Test RSI with edge cases"""
        # Constant price (no change)
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        constant_prices = pd.Series(100.0, index=dates)
        
        rsi = calculate_rsi(constant_prices, period=14)
        
        # RSI should be 50 for constant prices (or NaN)
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            assert ((valid_rsi == 50) | (valid_rsi.isna())).all()
    
    def test_calculate_macd_basic(self, sample_prices):
        """Test MACD calculation"""
        macd, signal, hist = calculate_macd(
            sample_prices['close'],
            fast_period=12,
            slow_period=26,
            signal_period=9
        )
        
        # Check output types and lengths
        assert isinstance(macd, pd.Series)
        assert isinstance(signal, pd.Series)
        assert isinstance(hist, pd.Series)
        
        assert len(macd) == len(sample_prices)
        assert len(signal) == len(sample_prices)
        assert len(hist) == len(sample_prices)
        
        # Histogram should equal MACD - Signal
        valid_idx = ~macd.isna() & ~signal.isna()
        np.testing.assert_array_almost_equal(
            hist[valid_idx].values,
            (macd - signal)[valid_idx].values,
            decimal=10
        )
    
    def test_generate_signals_basic(self, sample_prices):
        """Test signal generation"""
        M = 20
        
        signals = generate_signals(sample_prices, M)
        
        # Check output
        assert isinstance(signals, pd.DataFrame)
        assert len(signals) == len(sample_prices)
        
        # Check required columns
        required_cols = ['SMA', 'signal', 'ATR', 'RSI', 'MACD', 'MACD_signal']
        for col in required_cols:
            assert col in signals.columns
        
        # Signal should be -1, 0, or 1
        assert signals['signal'].isin([-1, 0, 1]).all()
    
    def test_generate_signals_parameters(self, sample_prices):
        """Test signal generation with different parameters"""
        params = [10, 20, 30, 50]
        
        for M in params:
            if M < len(sample_prices):
                signals = generate_signals(sample_prices, M)
                
                assert len(signals) == len(sample_prices)
                assert 'SMA' in signals.columns
                assert 'signal' in signals.columns
    
    def test_signals_no_lookahead_bias(self, sample_prices):
        """Test that signals don't use future data"""
        signals = generate_signals(sample_prices, M=20)
        
        # First M values should have NaN for SMA
        assert signals['SMA'].iloc[:19].isna().all()
        
        # First signal should not appear before M periods
        first_signal_idx = signals[signals['signal'] != 0].index
        if len(first_signal_idx) > 0:
            assert signals.index.get_loc(first_signal_idx[0]) >= 19


class TestRSI:
    """Dedicated tests for RSI calculation"""
    
    def test_rsi_trending_up(self):
        """Test RSI with uptrending prices"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        prices = pd.Series(range(100, 150), index=dates)
        
        rsi = calculate_rsi(prices, period=14)
        
        # RSI should be high for uptrending prices
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            assert valid_rsi.mean() > 50
    
    def test_rsi_trending_down(self):
        """Test RSI with downtrending prices"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        prices = pd.Series(range(150, 100, -1), index=dates)
        
        rsi = calculate_rsi(prices, period=14)
        
        # RSI should be low for downtrending prices
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            assert valid_rsi.mean() < 50


class TestMACD:
    """Dedicated tests for MACD calculation"""
    
    def test_macd_crossover(self):
        """Test MACD crossover detection"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        
        # Create price data with clear trend change
        np.random.seed(42)
        prices_up = 100 + np.cumsum(np.random.randn(50) + 0.5)
        prices_down = prices_up[-1] + np.cumsum(np.random.randn(50) - 0.5)
        prices = pd.Series(
            np.concatenate([prices_up, prices_down]),
            index=dates
        )
        
        macd, signal, hist = calculate_macd(prices)
        
        # Check for crossovers
        valid_idx = ~macd.isna() & ~signal.isna()
        if valid_idx.sum() > 1:
            # MACD should cross signal line
            crossovers = ((macd > signal).astype(int).diff() != 0).sum()
            assert crossovers > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
