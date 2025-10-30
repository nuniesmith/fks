"""Feature engineering pipeline for trading strategies.

This module provides comprehensive feature engineering capabilities including:
- Technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Statistical features (log returns, volatility, momentum)
- Time-based features (hour of day, day of week, etc.)
- Market microstructure features (bid-ask spreads, volume patterns)

All features are designed to work with high-frequency data and support
both batch processing and real-time streaming updates.

Phase: AI Enhancement Plan Phase 1 - Data Foundation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import logging
from decimal import Decimal
import asyncio
import time

# Technical Analysis Library
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    logging.warning("TA-Lib not available - using numpy implementations")

# Redis caching
try:
    from ..cache.feature_cache import get_cache_instance, FeatureCache
    HAS_CACHE = True
except ImportError:
    HAS_CACHE = False
    logging.warning("Redis cache not available - features will not be cached")

logger = logging.getLogger(__name__)


class FeatureProcessor:
    """Comprehensive feature engineering for trading data.
    
    This processor creates technical indicators, statistical features,
    and market microstructure features from OHLCV price data.
    
    Attributes:
        cache_enabled: Whether to cache computed features
        batch_size: Size of batches for processing large datasets
        feature_cache: Dictionary storing computed features
    """
    
    def __init__(
        self,
        cache_enabled: bool = True,
        batch_size: int = 10000,
        min_periods: int = 100,
        redis_url: Optional[str] = None,
    ):
        """Initialize feature processor.
        
        Args:
            cache_enabled: Enable feature caching for performance
            batch_size: Batch size for large dataset processing
            min_periods: Minimum periods required for indicator calculation
            redis_url: Redis connection URL (optional, uses default if None)
        """
        self.cache_enabled = cache_enabled and HAS_CACHE
        self.batch_size = batch_size
        self.min_periods = min_periods
        self.feature_cache: Dict[str, pd.DataFrame] = {}  # Legacy in-memory cache
        self.use_talib = HAS_TALIB
        self.logger = logger
        
        # Initialize Redis cache
        if self.cache_enabled and HAS_CACHE:
            try:
                self.redis_cache = get_cache_instance(redis_url=redis_url, namespace="features")
                logger.info(f"✅ Redis cache initialized for FeatureProcessor")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Redis cache: {e}, falling back to in-memory")
                self.redis_cache = None
                self.cache_enabled = False
        else:
            self.redis_cache = None
        
        logger.info(
            f"FeatureProcessor initialized "
            f"(cache={'Redis' if self.redis_cache else 'Memory' if cache_enabled else 'Disabled'}, "
            f"batch_size={batch_size}, talib={self.use_talib})"
        )
    
    def process_ohlcv_features(
        self,
        data: pd.DataFrame,
        symbol: str = "",
        timeframe: str = "1m",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Process comprehensive OHLCV features.
        
        Args:
            data: DataFrame with OHLCV columns (open, high, low, close, volume)
            symbol: Trading symbol for caching
            timeframe: Data timeframe (1m, 5m, 1h, etc.)
            use_cache: Whether to use Redis cache (default: True)
            
        Returns:
            DataFrame with original data plus engineered features
        """
        if data.empty or len(data) < self.min_periods:
            logger.warning(f"Insufficient data for {symbol} ({len(data)} < {self.min_periods})")
            return data
        
        # Check Redis cache first (if enabled and symbol provided)
        if use_cache and self.redis_cache and symbol:
            cached_features = self.redis_cache.get(symbol, timeframe, "ohlcv_features")
            if cached_features is not None and len(cached_features) == len(data):
                # Verify data hasn't changed by checking last timestamp
                if 'timestamp' in data.columns and 'timestamp' in cached_features.columns:
                    if data['timestamp'].iloc[-1] == cached_features['timestamp'].iloc[-1]:
                        logger.info(f"✅ Using cached features for {symbol} ({timeframe})")
                        return cached_features
        
        logger.info(f"🔄 Computing features for {len(data)} OHLCV records: {symbol} ({timeframe})")
        start_time = time.time()
        
        # Make a copy to avoid modifying original
        df = data.copy()
        
        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # 1. Price-based features
        df = self._add_price_features(df)
        
        # 2. Technical indicators
        df = self._add_technical_indicators(df)
        
        # 3. Statistical features
        df = self._add_statistical_features(df)
        
        # 4. Volume features
        df = self._add_volume_features(df)
        
        # 5. Time-based features
        df = self._add_time_features(df)
        
        # 6. Market microstructure features
        df = self._add_microstructure_features(df)
        
        duration = time.time() - start_time
        logger.info(f"✅ Processed {len(df.columns)} features for {symbol} in {duration:.2f}s")
        
        # Store in Redis cache if enabled
        if use_cache and self.redis_cache and symbol:
            try:
                self.redis_cache.set(symbol, timeframe, "ohlcv_features", df)
                logger.debug(f"💾 Cached features for {symbol} ({timeframe})")
            except Exception as e:
                logger.warning(f"⚠️ Failed to cache features: {e}")
        
        # Also store in legacy memory cache for backwards compatibility
        if self.cache_enabled and symbol:
            cache_key = f"{symbol}_{timeframe}"
            self.feature_cache[cache_key] = df.copy()
        
        return df
    
    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add basic price-derived features."""
        # Price changes and returns
        df['price_change'] = df['close'] - df['close'].shift(1)
        df['price_change_pct'] = df['close'].pct_change()
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        
        # OHLC relationships
        df['high_low_ratio'] = df['high'] / df['low']
        df['open_close_ratio'] = df['open'] / df['close']
        df['hl2'] = (df['high'] + df['low']) / 2
        df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
        df['ohlc4'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        
        # Price range and volatility proxies
        df['true_range'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        
        return df
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators using TA-Lib or numpy implementations."""
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        if self.use_talib:
            # TA-Lib implementations (more accurate)
            try:
                # Trend indicators
                df['sma_20'] = talib.SMA(close, timeperiod=20)
                df['sma_50'] = talib.SMA(close, timeperiod=50)
                df['ema_12'] = talib.EMA(close, timeperiod=12)
                df['ema_26'] = talib.EMA(close, timeperiod=26)
                
                # MACD
                macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
                df['macd'] = macd
                df['macd_signal'] = macd_signal
                df['macd_histogram'] = macd_hist
                
                # RSI
                df['rsi_14'] = talib.RSI(close, timeperiod=14)
                
                # Bollinger Bands
                bb_upper, bb_middle, bb_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
                df['bb_upper'] = bb_upper
                df['bb_middle'] = bb_middle
                df['bb_lower'] = bb_lower
                df['bb_width'] = (bb_upper - bb_lower) / bb_middle
                df['bb_position'] = (close - bb_lower) / (bb_upper - bb_lower)
                
                # Stochastic
                slowk, slowd = talib.STOCH(high, low, close, fastk_period=5, slowk_period=3, slowd_period=3)
                df['stoch_k'] = slowk
                df['stoch_d'] = slowd
                
                # Average True Range
                df['atr_14'] = talib.ATR(high, low, close, timeperiod=14)
                
                # Volume indicators
                df['ad_line'] = talib.AD(high, low, close, volume)
                df['obv'] = talib.OBV(close, volume)
                
            except Exception as e:
                logger.warning(f"TA-Lib calculation error: {e}, falling back to numpy")
                self.use_talib = False
        
        if not self.use_talib:
            # Numpy implementations (fallback)
            df = self._add_numpy_indicators(df)
        
        return df
    
    def _add_numpy_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators using numpy (fallback when TA-Lib unavailable)."""
        # Simple Moving Averages
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        
        # Exponential Moving Averages
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        
        # MACD
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # RSI (simplified)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Average True Range
        df['atr_14'] = df['true_range'].rolling(window=14).mean()
        
        # Volume indicators (simplified)
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).cumsum()
        
        return df
    
    def _add_statistical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add statistical and volatility features."""
        # Rolling volatility (multiple periods)
        for period in [5, 21, 63]:  # ~1 week, 1 month, 3 months (1m bars)
            df[f'volatility_{period}d'] = df['log_return'].rolling(window=period * 1440).std() * np.sqrt(1440)  # Annualized
            df[f'realized_vol_{period}d'] = df['log_return'].rolling(window=period * 1440).std()
        
        # Rolling momentum
        for period in [5, 21, 63]:
            df[f'momentum_{period}d'] = df['close'] / df['close'].shift(period * 1440) - 1
        
        # Rolling statistics
        df['skewness_21d'] = df['log_return'].rolling(window=21 * 1440).skew()
        df['kurtosis_21d'] = df['log_return'].rolling(window=21 * 1440).kurt()
        
        # Price percentiles (where current price sits in recent range)
        for period in [20, 50, 200]:
            rolling_min = df['close'].rolling(window=period).min()
            rolling_max = df['close'].rolling(window=period).max()
            df[f'price_percentile_{period}'] = (df['close'] - rolling_min) / (rolling_max - rolling_min)
        
        # Volatility regime indicators
        df['vol_regime_5_21'] = df['volatility_5d'] / df['volatility_21d']  # Short vs medium term vol
        df['vol_regime_21_63'] = df['volatility_21d'] / df['volatility_63d']  # Medium vs long term vol
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume-based features."""
        # Volume moving averages
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']
        
        # Volume-price relationship
        df['vwap_20'] = (df['volume'] * df['close']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
        df['price_volume_trend'] = ((df['close'] - df['close'].shift(1)) / df['close'].shift(1) * df['volume']).cumsum()
        
        # Volume volatility
        df['volume_volatility'] = df['volume'].rolling(window=20).std()
        df['volume_z_score'] = (df['volume'] - df['volume_sma_20']) / df['volume_volatility']
        
        return df
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features."""
        if df.index.name != 'timestamp' and 'timestamp' not in df.columns:
            logger.warning("No timestamp information available for time features")
            return df
        
        # Use index if it's datetime, otherwise timestamp column
        if pd.api.types.is_datetime64_any_dtype(df.index):
            dt = df.index
        elif 'timestamp' in df.columns:
            dt = pd.to_datetime(df['timestamp'])
        else:
            return df
        
        # Basic time features
        df['hour'] = dt.dt.hour
        df['day_of_week'] = dt.dt.dayofweek
        df['day_of_month'] = dt.dt.day
        df['month'] = dt.dt.month
        df['quarter'] = dt.dt.quarter
        
        # Market session indicators (assuming UTC timestamps)
        # US market hours: 14:30-21:00 UTC (9:30-16:00 EST)
        # European market hours: 8:00-16:30 UTC
        # Asian market hours: 0:00-6:00 UTC (JST 9:00-15:00)
        df['us_session'] = ((dt.dt.hour >= 14) & (dt.dt.hour < 21)).astype(int)
        df['eu_session'] = ((dt.dt.hour >= 8) & (dt.dt.hour < 17)).astype(int)
        df['asia_session'] = ((dt.dt.hour >= 0) & (dt.dt.hour < 6)).astype(int)
        
        # Weekend indicator
        df['is_weekend'] = (dt.dt.dayofweek >= 5).astype(int)
        
        return df
    
    def _add_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market microstructure features."""
        # Price efficiency measures
        df['price_impact'] = abs(df['close'] - df['open']) / df['volume']
        df['amihud_illiquidity'] = abs(df['log_return']) / df['volume']
        
        # Market pressure indicators
        df['buying_pressure'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        df['selling_pressure'] = (df['high'] - df['close']) / (df['high'] - df['low'])
        
        # Intraday patterns
        df['intraday_return'] = (df['close'] - df['open']) / df['open']
        df['overnight_return'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        # Gap analysis
        df['gap_up'] = ((df['open'] > df['close'].shift(1)) & (df['open'] > df['high'].shift(1))).astype(int)
        df['gap_down'] = ((df['open'] < df['close'].shift(1)) & (df['open'] < df['low'].shift(1))).astype(int)
        
        return df
    
    def get_feature_importance(self, df: pd.DataFrame, target_col: str = 'log_return') -> pd.DataFrame:
        """Calculate feature importance using correlation analysis.
        
        Args:
            df: DataFrame with features
            target_col: Target column for importance calculation
            
        Returns:
            DataFrame with feature importance scores
        """
        if target_col not in df.columns:
            logger.error(f"Target column '{target_col}' not found")
            return pd.DataFrame()
        
        # Calculate correlations with target
        correlations = df.corr()[target_col].abs().sort_values(ascending=False)
        
        # Remove self-correlation
        correlations = correlations.drop(target_col, errors='ignore')
        
        importance_df = pd.DataFrame({
            'feature': correlations.index,
            'importance': correlations.values,
            'abs_correlation': correlations.values
        })
        
        return importance_df
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats including Redis and in-memory stats
        """
        stats = {
            "cache_enabled": self.cache_enabled,
            "cache_type": "redis" if self.redis_cache else "memory",
        }
        
        # Redis cache stats
        if self.redis_cache:
            try:
                redis_stats = self.redis_cache.get_stats()
                stats["redis"] = redis_stats
                redis_info = self.redis_cache.get_info()
                stats["redis_info"] = {
                    "key_count": redis_info.get("key_count", 0),
                    "connected": redis_info.get("connected", False),
                }
            except Exception as e:
                logger.warning(f"⚠️ Failed to get Redis cache stats: {e}")
                stats["redis"] = {"error": str(e)}
        
        # In-memory cache stats
        stats["memory"] = {
            "cached_symbols": len(self.feature_cache),
            "total_memory_mb": sum(
                df.memory_usage(deep=True).sum() / 1024 / 1024 
                for df in self.feature_cache.values()
            ),
            "cache_keys": list(self.feature_cache.keys())
        }
        
        return stats
    
    def clear_cache(self, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        """Clear feature cache (both Redis and in-memory).
        
        Args:
            symbol: Specific symbol to clear, or None to clear all
            timeframe: Specific timeframe to clear, or None to clear all
        """
        # Clear Redis cache
        if self.redis_cache:
            try:
                deleted = self.redis_cache.invalidate(symbol=symbol, timeframe=timeframe)
                logger.info(f"🗑️ Cleared {deleted} Redis cache entries")
            except Exception as e:
                logger.warning(f"⚠️ Failed to clear Redis cache: {e}")
        
        # Clear in-memory cache
        if symbol:
            # Clear specific symbol (and optionally timeframe)
            pattern = f"{symbol}_{timeframe}" if timeframe else symbol
            keys_to_remove = [key for key in self.feature_cache.keys() if key.startswith(pattern)]
            for key in keys_to_remove:
                del self.feature_cache[key]
            logger.info(f"Cleared in-memory cache for {symbol} ({len(keys_to_remove)} entries)")
        else:
            # Clear all in-memory cache
            cache_size = len(self.feature_cache)
            self.feature_cache.clear()
            logger.info(f"Cleared all in-memory cache ({cache_size} entries)")


def create_feature_matrix(
    ohlcv_data: pd.DataFrame,
    symbols: List[str],
    processor: Optional[FeatureProcessor] = None
) -> pd.DataFrame:
    """Create a comprehensive feature matrix for multiple symbols.
    
    Args:
        ohlcv_data: Multi-symbol OHLCV data with symbol column
        symbols: List of symbols to process
        processor: FeatureProcessor instance (creates new if None)
        
    Returns:
        Combined feature matrix with all symbols
    """
    if processor is None:
        processor = FeatureProcessor()
    
    logger.info(f"Creating feature matrix for {len(symbols)} symbols")
    
    feature_matrices = []
    
    for symbol in symbols:
        try:
            # Filter data for this symbol
            symbol_data = ohlcv_data[ohlcv_data['symbol'] == symbol].copy()
            
            if symbol_data.empty:
                logger.warning(f"No data found for {symbol}")
                continue
            
            # Process features
            features = processor.process_ohlcv_features(symbol_data, symbol=symbol)
            features['symbol'] = symbol
            
            feature_matrices.append(features)
            
        except Exception as e:
            logger.error(f"Error processing features for {symbol}: {e}")
            continue
    
    if feature_matrices:
        combined_matrix = pd.concat(feature_matrices, ignore_index=True)
        logger.info(f"✅ Created feature matrix: {len(combined_matrix)} rows, {len(combined_matrix.columns)} columns")
        return combined_matrix
    else:
        logger.error("❌ No feature matrices created")
        return pd.DataFrame()


# Quick test/example function
def test_feature_processor():
    """Test the feature processor with sample data."""
    # Create sample OHLCV data
    dates = pd.date_range('2025-01-01', periods=1000, freq='1T')  # 1-minute bars
    np.random.seed(42)
    
    sample_data = pd.DataFrame({
        'timestamp': dates,
        'open': 100 + np.cumsum(np.random.randn(1000) * 0.1),
        'high': 0,
        'low': 0, 
        'close': 0,
        'volume': np.random.randint(100, 10000, 1000)
    })
    
    # Generate realistic OHLC from close prices
    sample_data['close'] = sample_data['open'] + np.random.randn(1000) * 0.05
    sample_data['high'] = np.maximum(sample_data['open'], sample_data['close']) + np.random.rand(1000) * 0.02
    sample_data['low'] = np.minimum(sample_data['open'], sample_data['close']) - np.random.rand(1000) * 0.02
    
    # Set timestamp as index
    sample_data.set_index('timestamp', inplace=True)
    
    # Process features
    processor = FeatureProcessor()
    features = processor.process_ohlcv_features(sample_data, symbol="TEST", timeframe="1m")
    
    print(f"Sample feature processing complete:")
    print(f"  Input shape: {sample_data.shape}")
    print(f"  Output shape: {features.shape}")
    print(f"  Features added: {features.shape[1] - sample_data.shape[1]}")
    print(f"  Feature columns: {list(features.columns)}")
    
    return features


if __name__ == "__main__":
    # Run test
    test_features = test_feature_processor()