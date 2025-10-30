"""Tests for feature processor functionality."""

import pandas as pd
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
import logging

# Local exception for testing (to avoid import issues)
class TALibNotFoundError(Exception):
    """Raised when TA-Lib is not available."""
    pass

class TestFeatureProcessor:
    """Test FeatureProcessor functionality."""

    @pytest.fixture
    def sample_data(self):
        """Sample OHLCV data for testing."""
        dates = pd.date_range('2024-01-01', periods=100, freq='1H')
        np.random.seed(42)
        
        # Generate realistic price data with trend
        price = 100.0
        prices = []
        for i in range(100):
            # Add trend with noise
            price += np.random.normal(0.1, 2.0)
            prices.append(max(price, 0.1))  # Avoid negative prices
        
        data = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
            'close': [p + np.random.normal(0, 0.5) for p in prices],
            'volume': np.random.randint(1000, 10000, 100)
        })
        
        # Ensure high >= low, close within range
        data['high'] = np.maximum(data['high'], data[['open', 'close']].max(axis=1))
        data['low'] = np.minimum(data['low'], data[['open', 'close']].min(axis=1))
        
        return data

    @pytest.fixture
    def processor(self):
        """Create FeatureProcessor instance."""
        from features.feature_processor import FeatureProcessor
        return FeatureProcessor()

    def test_feature_processor_initialization(self, processor):
        """Test FeatureProcessor initialization."""
        assert processor is not None
        assert hasattr(processor, 'use_talib')
        assert hasattr(processor, 'logger')

    def test_calculate_rsi_numpy(self, processor, sample_data):
        """Test RSI calculation with numpy implementation."""
        with patch.object(processor, 'use_talib', False):
            rsi = processor.calculate_rsi(sample_data['close'].values, period=14)
            
            assert len(rsi) == len(sample_data)
            assert not np.isnan(rsi[20:]).any()  # Should have values after warmup
            assert (rsi[20:] >= 0).all() and (rsi[20:] <= 100).all()

    def test_calculate_macd_numpy(self, processor, sample_data):
        """Test MACD calculation with numpy implementation."""
        with patch.object(processor, 'use_talib', False):
            macd_line, macd_signal, macd_histogram = processor.calculate_macd(
                sample_data['close'].values
            )
            
            assert len(macd_line) == len(sample_data)
            assert len(macd_signal) == len(sample_data)
            assert len(macd_histogram) == len(sample_data)
            
            # Check that histogram = macd_line - macd_signal (where not NaN)
            valid_idx = ~np.isnan(macd_line) & ~np.isnan(macd_signal)
            if valid_idx.any():
                np.testing.assert_array_almost_equal(
                    macd_histogram[valid_idx],
                    macd_line[valid_idx] - macd_signal[valid_idx],
                    decimal=10
                )

    def test_calculate_bollinger_bands_numpy(self, processor, sample_data):
        """Test Bollinger Bands calculation with numpy implementation."""
        with patch.object(processor, 'use_talib', False):
            upper, middle, lower = processor.calculate_bollinger_bands(
                sample_data['close'].values, period=20, std_dev=2
            )
            
            assert len(upper) == len(sample_data)
            assert len(middle) == len(sample_data)
            assert len(lower) == len(sample_data)
            
            # Check band ordering where not NaN
            valid_idx = ~np.isnan(upper) & ~np.isnan(middle) & ~np.isnan(lower)
            if valid_idx.any():
                assert (upper[valid_idx] >= middle[valid_idx]).all()
                assert (middle[valid_idx] >= lower[valid_idx]).all()

    def test_calculate_statistical_features(self, processor, sample_data):
        """Test statistical features calculation."""
        features = processor.calculate_statistical_features(sample_data)
        
        expected_features = [
            'returns', 'log_returns', 'volatility_21d', 'momentum_5d',
            'price_change_1d', 'volume_sma_10d', 'high_low_ratio'
        ]
        
        for feature in expected_features:
            assert feature in features.columns
            assert len(features[feature]) == len(sample_data)

    def test_calculate_technical_indicators(self, processor, sample_data):
        """Test technical indicators calculation."""
        indicators = processor.calculate_technical_indicators(sample_data)
        
        expected_indicators = [
            'rsi_14', 'macd_line', 'macd_signal', 'macd_histogram',
            'bb_upper', 'bb_middle', 'bb_lower', 'stoch_k', 'stoch_d',
            'williams_r', 'cci', 'atr', 'adx'
        ]
        
        for indicator in expected_indicators:
            assert indicator in indicators.columns
            assert len(indicators[indicator]) == len(sample_data)

    def test_calculate_market_microstructure(self, processor, sample_data):
        """Test market microstructure features calculation."""
        features = processor.calculate_market_microstructure_features(sample_data)
        
        expected_features = [
            'bid_ask_spread', 'mid_price', 'price_impact',
            'volume_imbalance', 'trade_intensity'
        ]
        
        for feature in expected_features:
            assert feature in features.columns
            assert len(features[feature]) == len(sample_data)

    def test_process_features_complete(self, processor, sample_data):
        """Test complete feature processing pipeline."""
        result = processor.process_features(sample_data)
        
        # Check that result is a DataFrame
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_data)
        
        # Check for presence of key feature categories
        columns = result.columns.tolist()
        
        # Technical indicators
        assert any('rsi' in col for col in columns)
        assert any('macd' in col for col in columns)
        assert any('bb_' in col for col in columns)
        
        # Statistical features
        assert 'returns' in columns
        assert 'volatility_21d' in columns
        assert 'momentum_5d' in columns
        
        # Market microstructure
        assert 'bid_ask_spread' in columns
        assert 'mid_price' in columns

    def test_process_features_with_nan_handling(self, processor):
        """Test feature processing with NaN values in input data."""
        # Create data with NaN values
        dates = pd.date_range('2024-01-01', periods=50, freq='1H')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': [100.0] * 25 + [np.nan] * 25,
            'high': [101.0] * 25 + [np.nan] * 25,
            'low': [99.0] * 25 + [np.nan] * 25,
            'close': [100.5] * 25 + [np.nan] * 25,
            'volume': [1000] * 50
        })
        
        result = processor.process_features(data)
        
        # Should handle NaN gracefully
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(data)

    def test_create_feature_matrix_function(self, sample_data):
        """Test standalone create_feature_matrix function."""
        from features.feature_processor import create_feature_matrix
        
        result = create_feature_matrix(sample_data)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_data)
        assert 'returns' in result.columns
        assert 'rsi_14' in result.columns

    def test_invalid_input_data(self, processor):
        """Test handling of invalid input data."""
        # Test with empty DataFrame
        empty_df = pd.DataFrame()
        
        with pytest.raises(ValueError, match="Input data cannot be empty"):
            processor.process_features(empty_df)
        
        # Test with missing required columns
        invalid_df = pd.DataFrame({'timestamp': [1, 2, 3]})
        
        with pytest.raises(ValueError, match="Required columns missing"):
            processor.process_features(invalid_df)

    def test_period_validation(self, processor, sample_data):
        """Test period parameter validation."""
        # Test with period longer than data
        with pytest.warns(UserWarning, match="Period .* is longer than data length"):
            processor.calculate_rsi(sample_data['close'].values, period=200)

    def test_logger_usage(self, processor, sample_data, caplog):
        """Test that logging works correctly."""
        with caplog.at_level(logging.INFO):
            processor.process_features(sample_data)
        
        # Should have logged feature processing
        assert any("Processing features" in record.message for record in caplog.records)

    @patch('features.feature_processor.importlib.util.find_spec')
    def test_talib_not_available(self, mock_find_spec, sample_data):
        """Test behavior when TA-Lib is not available."""
        mock_find_spec.return_value = None
        
        # Reimport to trigger the availability check
        import importlib
        import features.feature_processor
        importlib.reload(features.feature_processor)
        
        processor = features.feature_processor.FeatureProcessor()
        assert not processor.use_talib
        
        # Should still work with numpy fallback
        result = processor.process_features(sample_data)
        assert isinstance(result, pd.DataFrame)
        assert 'rsi_14' in result.columns

class TestFeatureUtilities:
    """Test utility functions."""

    def test_ema_calculation(self):
        """Test EMA utility function."""
        from features.feature_processor import FeatureProcessor
        
        processor = FeatureProcessor()
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        ema = processor._calculate_ema(data, period=3)
        
        assert len(ema) == len(data)
        assert not np.isnan(ema[-1])  # Last value should not be NaN
        
        # EMA should be between min and max of recent values
        assert ema[-1] >= min(data[-3:])
        assert ema[-1] <= max(data[-3:])

    def test_sma_calculation(self):
        """Test SMA utility function."""
        from features.feature_processor import FeatureProcessor
        
        processor = FeatureProcessor()
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        sma = processor._calculate_sma(data, period=3)
        
        assert len(sma) == len(data)
        
        # Check specific values
        assert np.isnan(sma[0])  # First values should be NaN
        assert np.isnan(sma[1])
        assert sma[2] == 2.0  # (1+2+3)/3 = 2
        assert sma[-1] == 9.0  # (8+9+10)/3 = 9

if __name__ == "__main__":
    pytest.main([__file__])