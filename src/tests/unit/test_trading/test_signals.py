"""
Test suite for signals module
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from trading.indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_sma,
    calculate_ema,
    calculate_atr,
    generate_signals,
)


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
        
        # First values should have less reliable data (our implementation fills with 50.0)
        # So we just check that RSI is calculated and reasonable
        assert not rsi.iloc[14:].isna().any()  # After period, should have values
    
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
        
        # Check required columns (ATR not included since sample_prices only has 'close')
        required_cols = ['SMA', 'signal', 'RSI', 'MACD', 'MACD_signal']
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


class TestBollingerBands:
    """Tests for Bollinger Bands calculation"""
    
    def test_bollinger_bands_basic(self):
        """Test basic Bollinger Bands calculation"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        np.random.seed(42)
        prices = pd.Series(100 + np.cumsum(np.random.randn(50)), index=dates)
        
        upper, middle, lower = calculate_bollinger_bands(prices, period=20, num_std=2.0)
        
        # Check output types and lengths
        assert isinstance(upper, pd.Series)
        assert isinstance(middle, pd.Series)
        assert isinstance(lower, pd.Series)
        assert len(upper) == len(prices)
        assert len(middle) == len(prices)
        assert len(lower) == len(prices)
        
        # Upper band should be above middle, lower should be below
        valid_idx = ~upper.isna() & ~middle.isna() & ~lower.isna()
        assert (upper[valid_idx] >= middle[valid_idx]).all()
        assert (lower[valid_idx] <= middle[valid_idx]).all()
    
    def test_bollinger_bands_width(self):
        """Test Bollinger Bands width scales with volatility"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        
        # Low volatility prices
        np.random.seed(42)
        low_vol_prices = pd.Series(100 + np.cumsum(np.random.randn(100) * 0.1), index=dates)
        
        # High volatility prices
        high_vol_prices = pd.Series(100 + np.cumsum(np.random.randn(100) * 2.0), index=dates)
        
        upper_low, middle_low, lower_low = calculate_bollinger_bands(low_vol_prices, period=20)
        upper_high, middle_high, lower_high = calculate_bollinger_bands(high_vol_prices, period=20)
        
        # High volatility should have wider bands
        low_width = (upper_low - lower_low).mean()
        high_width = (upper_high - lower_high).mean()
        
        assert high_width > low_width
    
    def test_bollinger_bands_different_std(self):
        """Test Bollinger Bands with different standard deviations"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        np.random.seed(42)
        prices = pd.Series(100 + np.cumsum(np.random.randn(50)), index=dates)
        
        upper_2std, middle_2std, lower_2std = calculate_bollinger_bands(prices, num_std=2.0)
        upper_3std, middle_3std, lower_3std = calculate_bollinger_bands(prices, num_std=3.0)
        
        # Middle bands should be the same
        pd.testing.assert_series_equal(middle_2std, middle_3std)
        
        # 3 std bands should be wider than 2 std bands
        valid_idx = ~upper_2std.isna()
        assert (upper_3std[valid_idx] >= upper_2std[valid_idx]).all()
        assert (lower_3std[valid_idx] <= lower_2std[valid_idx]).all()


class TestSMA:
    """Tests for Simple Moving Average"""
    
    def test_sma_basic(self):
        """Test basic SMA calculation"""
        prices = pd.Series([10, 20, 30, 40, 50])
        sma = calculate_sma(prices, period=3)
        
        # First 2 values should be NaN
        assert sma.iloc[:2].isna().all()
        # Third value should be average of first 3
        assert sma.iloc[2] == 20.0
        assert sma.iloc[3] == 30.0
        assert sma.iloc[4] == 40.0
    
    def test_sma_period_equals_length(self):
        """Test SMA when period equals data length"""
        prices = pd.Series([10, 20, 30, 40, 50])
        sma = calculate_sma(prices, period=5)
        
        # Only last value should be valid
        assert sma.iloc[:-1].isna().all()
        assert sma.iloc[-1] == 30.0  # Average of all values


class TestEMA:
    """Tests for Exponential Moving Average"""
    
    def test_ema_basic(self):
        """Test basic EMA calculation"""
        prices = pd.Series([10, 20, 30, 40, 50])
        ema = calculate_ema(prices, period=3)
        
        # EMA should be defined for all values
        assert not ema.isna().any()
        
        # EMA should be between min and max
        assert ema.min() >= prices.min()
        assert ema.max() <= prices.max()
    
    def test_ema_reacts_faster_than_sma(self):
        """Test that EMA reacts faster to price changes than SMA"""
        # Create prices with a sudden jump
        prices = pd.Series([100] * 20 + [120] * 20)
        
        sma = calculate_sma(prices, period=10)
        ema = calculate_ema(prices, period=10)
        
        # After the jump, EMA should reach higher value faster
        jump_idx = 20
        # Check a few periods after the jump
        for i in range(1, 5):
            idx = jump_idx + i
            if not pd.isna(sma.iloc[idx]) and not pd.isna(ema.iloc[idx]):
                assert ema.iloc[idx] >= sma.iloc[idx]


class TestATR:
    """Tests for Average True Range"""
    
    def test_atr_basic(self):
        """Test basic ATR calculation"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        np.random.seed(42)
        
        close = pd.Series(100 + np.cumsum(np.random.randn(50)), index=dates)
        high = close + np.abs(np.random.randn(50) * 2)
        low = close - np.abs(np.random.randn(50) * 2)
        
        atr = calculate_atr(high, low, close, period=14)
        
        # Check output type and length
        assert isinstance(atr, pd.Series)
        assert len(atr) == len(close)
        
        # ATR should be positive
        valid_atr = atr.dropna()
        assert (valid_atr >= 0).all()
    
    def test_atr_volatility_correlation(self):
        """Test ATR increases with volatility"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        np.random.seed(42)
        
        # Low volatility
        close_low = pd.Series(100 + np.cumsum(np.random.randn(50) * 0.1), index=dates)
        high_low = close_low + np.abs(np.random.randn(50) * 0.1)
        low_low = close_low - np.abs(np.random.randn(50) * 0.1)
        
        # High volatility
        close_high = pd.Series(100 + np.cumsum(np.random.randn(50) * 2.0), index=dates)
        high_high = close_high + np.abs(np.random.randn(50) * 2.0)
        low_high = close_high - np.abs(np.random.randn(50) * 2.0)
        
        atr_low = calculate_atr(high_low, low_low, close_low, period=14)
        atr_high = calculate_atr(high_high, low_high, close_high, period=14)
        
        # High volatility should have higher ATR
        assert atr_high.mean() > atr_low.mean()


class TestGenerateSignals:
    """Tests for combined signal generation"""
    
    def test_generate_signals_with_full_data(self):
        """Test signal generation with complete OHLC data"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        close = 100 + np.cumsum(np.random.randn(100))
        high = close + np.abs(np.random.randn(100) * 2)
        low = close - np.abs(np.random.randn(100) * 2)
        
        df = pd.DataFrame({
            'close': close,
            'high': high,
            'low': low
        }, index=dates)
        
        signals = generate_signals(df, M=20)
        
        # Check all expected columns are present
        expected_cols = ['close', 'high', 'low', 'SMA', 'RSI', 'MACD', 
                        'MACD_signal', 'MACD_hist', 'ATR', 'signal']
        for col in expected_cols:
            assert col in signals.columns
        
        # Check signal values are valid
        assert signals['signal'].isin([-1, 0, 1]).all()
    
    def test_generate_signals_without_high_low(self):
        """Test signal generation with only close prices"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        df = pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(100))
        }, index=dates)
        
        signals = generate_signals(df, M=20)
        
        # ATR should not be calculated without high/low
        assert 'ATR' not in signals.columns or signals['ATR'].isna().all()
        
        # Other indicators should still be present
        assert 'SMA' in signals.columns
        assert 'RSI' in signals.columns
        assert 'MACD' in signals.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
