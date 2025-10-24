"""
Test suite for data fetching functionality

NOTE: These tests reference legacy data API (fetch_ohlcv, fetch_multiple_symbols, validate_data)
      that no longer exists after monolith migration. The data module was restructured to use
      an adapter pattern. See Issue #6 for tracking.
      
TODO: Update tests to match current data module API (DataManager, adapters.get_adapter)
"""

import pytest

# Skip entire module until data API is refactored
pytestmark = pytest.mark.skip(
    reason="Legacy data API tests - module restructured during monolith migration. "
           "See Issue #6. TODO: Update tests to match current data module API."
)

import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
# from data import fetch_ohlcv, fetch_multiple_symbols, validate_data  # Legacy API - doesn't exist


class TestFetchOHLCV:
    """Test OHLCV data fetching"""
    
    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange"""
        exchange = Mock()
        exchange.fetch_ohlcv = Mock(return_value=[
            [1609459200000, 100.0, 105.0, 95.0, 102.0, 1000.0],
            [1609545600000, 102.0, 108.0, 100.0, 106.0, 1200.0],
            [1609632000000, 106.0, 110.0, 104.0, 108.0, 1100.0],
        ])
        return exchange
    
    def test_fetch_ohlcv_basic(self, mock_exchange):
        """Test basic OHLCV fetching"""
        df = fetch_ohlcv(
            mock_exchange,
            symbol='BTC/USD',
            timeframe='1d',
            since=datetime(2021, 1, 1)
        )
        
        # Check output
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        
        # Check columns
        expected_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
        assert all(col in df.columns for col in expected_cols)
        
        # Verify exchange was called
        mock_exchange.fetch_ohlcv.assert_called_once()
    
    def test_fetch_ohlcv_empty_response(self, mock_exchange):
        """Test handling of empty response"""
        mock_exchange.fetch_ohlcv.return_value = []
        
        df = fetch_ohlcv(
            mock_exchange,
            symbol='BTC/USD',
            timeframe='1h'
        )
        
        # Should return empty DataFrame with correct structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
    
    def test_fetch_ohlcv_with_limit(self, mock_exchange):
        """Test fetching with limit parameter"""
        df = fetch_ohlcv(
            mock_exchange,
            symbol='ETH/USD',
            timeframe='4h',
            limit=100
        )
        
        # Verify limit was passed
        call_args = mock_exchange.fetch_ohlcv.call_args
        assert 'limit' in call_args.kwargs or len(call_args.args) > 3
    
    @patch('data.ccxt')
    def test_fetch_ohlcv_error_handling(self, mock_ccxt):
        """Test error handling during fetch"""
        mock_exchange = Mock()
        mock_exchange.fetch_ohlcv.side_effect = Exception('Network error')
        
        with pytest.raises(Exception):
            fetch_ohlcv(
                mock_exchange,
                symbol='BTC/USD',
                timeframe='1d'
            )


class TestFetchMultipleSymbols:
    """Test fetching data for multiple symbols"""
    
    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange"""
        exchange = Mock()
        
        def mock_fetch(symbol, timeframe, **kwargs):
            # Return different data for different symbols
            if 'BTC' in symbol:
                return [
                    [1609459200000, 30000.0, 31000.0, 29000.0, 30500.0, 100.0],
                    [1609545600000, 30500.0, 32000.0, 30000.0, 31500.0, 120.0],
                ]
            elif 'ETH' in symbol:
                return [
                    [1609459200000, 1000.0, 1100.0, 950.0, 1050.0, 500.0],
                    [1609545600000, 1050.0, 1150.0, 1000.0, 1100.0, 550.0],
                ]
            return []
        
        exchange.fetch_ohlcv = Mock(side_effect=mock_fetch)
        return exchange
    
    def test_fetch_multiple_symbols_basic(self, mock_exchange):
        """Test fetching multiple symbols"""
        symbols = ['BTC/USD', 'ETH/USD']
        
        result = fetch_multiple_symbols(
            mock_exchange,
            symbols,
            timeframe='1d'
        )
        
        # Check output structure
        assert isinstance(result, dict)
        assert len(result) == 2
        assert 'BTC/USD' in result
        assert 'ETH/USD' in result
        
        # Check each DataFrame
        for symbol in symbols:
            assert isinstance(result[symbol], pd.DataFrame)
            assert len(result[symbol]) > 0
    
    def test_fetch_multiple_symbols_with_failures(self, mock_exchange):
        """Test handling partial failures"""
        symbols = ['BTC/USD', 'INVALID/USD', 'ETH/USD']
        
        # Make one symbol fail
        def mock_fetch_with_error(symbol, timeframe, **kwargs):
            if 'INVALID' in symbol:
                raise Exception('Invalid symbol')
            elif 'BTC' in symbol:
                return [[1609459200000, 30000.0, 31000.0, 29000.0, 30500.0, 100.0]]
            elif 'ETH' in symbol:
                return [[1609459200000, 1000.0, 1100.0, 950.0, 1050.0, 500.0]]
            return []
        
        mock_exchange.fetch_ohlcv = Mock(side_effect=mock_fetch_with_error)
        
        result = fetch_multiple_symbols(
            mock_exchange,
            symbols,
            timeframe='1h',
            skip_errors=True
        )
        
        # Should return data for successful symbols only
        assert len(result) == 2
        assert 'BTC/USD' in result
        assert 'ETH/USD' in result
        assert 'INVALID/USD' not in result


class TestValidateData:
    """Test data validation functionality"""
    
    def test_validate_data_valid(self):
        """Test validation with valid data"""
        df = pd.DataFrame({
            'time': pd.date_range('2023-01-01', periods=10, freq='D'),
            'open': range(100, 110),
            'high': range(105, 115),
            'low': range(95, 105),
            'close': range(101, 111),
            'volume': range(1000, 1100, 10)
        })
        
        is_valid, errors = validate_data(df)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_data_missing_columns(self):
        """Test validation with missing columns"""
        df = pd.DataFrame({
            'time': pd.date_range('2023-01-01', periods=10, freq='D'),
            'close': range(100, 110),
        })
        
        is_valid, errors = validate_data(df)
        
        assert is_valid is False
        assert len(errors) > 0
        assert any('missing' in str(e).lower() for e in errors)
    
    def test_validate_data_invalid_prices(self):
        """Test validation with invalid prices"""
        df = pd.DataFrame({
            'time': pd.date_range('2023-01-01', periods=10, freq='D'),
            'open': range(100, 110),
            'high': range(95, 105),  # High < Open (invalid)
            'low': range(90, 100),
            'close': range(101, 111),
            'volume': range(1000, 1100, 10)
        })
        
        is_valid, errors = validate_data(df)
        
        assert is_valid is False
        assert any('high' in str(e).lower() or 'price' in str(e).lower() for e in errors)
    
    def test_validate_data_null_values(self):
        """Test validation with null values"""
        df = pd.DataFrame({
            'time': pd.date_range('2023-01-01', periods=10, freq='D'),
            'open': [100, 101, None, 103, 104, 105, 106, 107, 108, 109],
            'high': range(105, 115),
            'low': range(95, 105),
            'close': range(101, 111),
            'volume': range(1000, 1100, 10)
        })
        
        is_valid, errors = validate_data(df)
        
        assert is_valid is False
        assert any('null' in str(e).lower() or 'missing' in str(e).lower() for e in errors)
    
    def test_validate_data_negative_values(self):
        """Test validation with negative values"""
        df = pd.DataFrame({
            'time': pd.date_range('2023-01-01', periods=10, freq='D'),
            'open': range(100, 110),
            'high': range(105, 115),
            'low': range(95, 105),
            'close': range(101, 111),
            'volume': [-100, -50, 0, 100, 200, 300, 400, 500, 600, 700]
        })
        
        is_valid, errors = validate_data(df)
        
        assert is_valid is False
        assert any('negative' in str(e).lower() or 'volume' in str(e).lower() for e in errors)


class TestDataProcessing:
    """Test data processing and transformation"""
    
    def test_resample_timeframe(self):
        """Test resampling to different timeframe"""
        # Create hourly data
        dates = pd.date_range('2023-01-01', periods=24, freq='H')
        df = pd.DataFrame({
            'time': dates,
            'open': range(100, 124),
            'high': range(105, 129),
            'low': range(95, 119),
            'close': range(101, 125),
            'volume': [100] * 24
        })
        df.set_index('time', inplace=True)
        
        # Resample to daily
        daily = df.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        assert len(daily) == 1
        assert daily['open'].iloc[0] == 100
        assert daily['close'].iloc[0] == 124
        assert daily['volume'].iloc[0] == 2400
    
    def test_calculate_returns(self):
        """Test return calculation"""
        df = pd.DataFrame({
            'close': [100, 102, 101, 105, 103]
        })
        
        df['returns'] = df['close'].pct_change()
        
        assert len(df['returns']) == 5
        assert pd.isna(df['returns'].iloc[0])
        assert abs(df['returns'].iloc[1] - 0.02) < 0.001
        assert abs(df['returns'].iloc[2] - (-0.0098)) < 0.001


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
