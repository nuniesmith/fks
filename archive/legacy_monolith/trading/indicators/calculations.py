"""
Technical indicator calculation functions.

Provides core technical analysis indicators including RSI, MACD, Bollinger Bands,
and signal generation logic.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).
    
    RSI measures the magnitude of recent price changes to evaluate
    overbought or oversold conditions.
    
    Args:
        prices: Series of closing prices
        period: RSI period (default: 14)
        
    Returns:
        Series of RSI values (0-100)
        
    Example:
        >>> prices = pd.Series([100, 102, 101, 103, 105])
        >>> rsi = calculate_rsi(prices, period=14)
    """
    if len(prices) < period:
        return pd.Series([np.nan] * len(prices), index=prices.index)
    
    # Calculate price changes
    delta = prices.diff()
    
    # Separate gains and losses
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    
    # Calculate average gains and losses
    avg_gains = gains.rolling(window=period, min_periods=period).mean()
    avg_losses = losses.rolling(window=period, min_periods=period).mean()
    
    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
    
    # Handle edge cases
    rsi = rsi.fillna(50.0)  # Neutral RSI when no data
    
    return rsi


def calculate_macd(
    prices: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Moving Average Convergence Divergence (MACD).
    
    MACD is a trend-following momentum indicator that shows the relationship
    between two moving averages of prices.
    
    Args:
        prices: Series of closing prices
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)
        
    Returns:
        Tuple of (macd_line, signal_line, histogram)
        
    Example:
        >>> prices = pd.Series(range(100, 200))
        >>> macd, signal, hist = calculate_macd(prices)
    """
    # Calculate EMAs
    ema_fast = prices.ewm(span=fast_period, adjust=False).mean()
    ema_slow = prices.ewm(span=slow_period, adjust=False).mean()
    
    # Calculate MACD line
    macd_line = ema_fast - ema_slow
    
    # Calculate signal line
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    
    # Calculate histogram
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.
    
    Bollinger Bands consist of a middle band (SMA) and upper/lower bands
    that are standard deviations away from the middle band.
    
    Args:
        prices: Series of closing prices
        period: Moving average period (default: 20)
        num_std: Number of standard deviations for bands (default: 2.0)
        
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
        
    Example:
        >>> prices = pd.Series(range(100, 200))
        >>> upper, middle, lower = calculate_bollinger_bands(prices)
    """
    # Calculate middle band (SMA)
    middle_band = prices.rolling(window=period).mean()
    
    # Calculate standard deviation
    std = prices.rolling(window=period).std()
    
    # Calculate upper and lower bands
    upper_band = middle_band + (std * num_std)
    lower_band = middle_band - (std * num_std)
    
    return upper_band, middle_band, lower_band


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Simple Moving Average (SMA).
    
    Args:
        prices: Series of closing prices
        period: Moving average period
        
    Returns:
        Series of SMA values
    """
    return prices.rolling(window=period).mean()


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).
    
    Args:
        prices: Series of closing prices
        period: Moving average period
        
    Returns:
        Series of EMA values
    """
    return prices.ewm(span=period, adjust=False).mean()


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    ATR measures market volatility by decomposing the entire range of an asset
    price for that period.
    
    Args:
        high: Series of high prices
        low: Series of low prices
        close: Series of closing prices
        period: ATR period (default: 14)
        
    Returns:
        Series of ATR values
    """
    # Calculate true range components
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    
    # True range is the maximum of the three
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # ATR is the moving average of true range
    atr = true_range.rolling(window=period).mean()
    
    return atr


def generate_signals(
    df: pd.DataFrame,
    M: int = 20,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9
) -> pd.DataFrame:
    """
    Generate trading signals based on multiple technical indicators.
    
    Args:
        df: DataFrame with 'close', 'high', 'low' columns
        M: SMA period for main signal
        rsi_period: RSI calculation period
        macd_fast: MACD fast EMA period
        macd_slow: MACD slow EMA period
        macd_signal: MACD signal line period
        
    Returns:
        DataFrame with calculated indicators and signals
        
    Columns added:
        - SMA: Simple moving average
        - RSI: Relative Strength Index
        - MACD: MACD line
        - MACD_signal: MACD signal line
        - MACD_hist: MACD histogram
        - ATR: Average True Range (if high/low available)
        - signal: Trading signal (-1: sell, 0: hold, 1: buy)
    """
    result = df.copy()
    
    # Calculate SMA
    result['SMA'] = calculate_sma(df['close'], M)
    
    # Calculate RSI
    result['RSI'] = calculate_rsi(df['close'], rsi_period)
    
    # Calculate MACD
    macd, signal_line, histogram = calculate_macd(
        df['close'],
        macd_fast,
        macd_slow,
        macd_signal
    )
    result['MACD'] = macd
    result['MACD_signal'] = signal_line
    result['MACD_hist'] = histogram
    
    # Calculate ATR if high/low are available
    if 'high' in df.columns and 'low' in df.columns:
        result['ATR'] = calculate_atr(df['high'], df['low'], df['close'])
    
    # Generate trading signal
    # Signal = 1 (BUY) when price > SMA, Signal = -1 (SELL) when price < SMA
    result['signal'] = 0  # Initialize to HOLD
    result.loc[df['close'] > result['SMA'], 'signal'] = 1  # BUY
    result.loc[df['close'] < result['SMA'], 'signal'] = -1  # SELL
    
    return result


__all__ = [
    'calculate_rsi',
    'calculate_macd',
    'calculate_bollinger_bands',
    'calculate_sma',
    'calculate_ema',
    'calculate_atr',
    'generate_signals',
]
