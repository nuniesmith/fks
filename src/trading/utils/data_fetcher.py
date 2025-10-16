"""
Data fetching utilities for fks trading.
Migrated from src/data.py

Handles:
- Historical OHLCV data from Binance API
- Current price fetching
- Live price data with WebSocket integration
- Price statistics and 24h data
- Redis caching for performance
"""

import pandas as pd
import requests
import json
from typing import Optional, Dict, List
from datetime import datetime
import pytz
from django.core.cache import cache

TIMEZONE = pytz.timezone('America/Toronto')

# Cache TTL settings
HISTORICAL_DATA_TTL = 3600  # 1 hour for historical data
CURRENT_PRICE_TTL = 60  # 1 minute for current prices
PRICE_STATS_TTL = 300  # 5 minutes for statistics


def get_historical_data(symbol: str, interval: str = '1d', limit: int = 1000) -> pd.DataFrame:
    """
    Get historical OHLCV data from Binance API
    Uses Django cache to avoid repeated API calls
    
    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        interval: Candle interval ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M')
        limit: Number of candles to fetch (max 1000)
    
    Returns:
        DataFrame with OHLCV data indexed by timestamp
    
    Raises:
        Exception: If API request fails
    """
    cache_key = f"historical_{symbol}_{interval}_{limit}"
    
    # Try to get from Django cache
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        df = pd.read_json(cached_data)
        df.index = pd.to_datetime(df.index)  # Ensure index is datetime
        return df
    
    # Fetch from Binance API
    url = "https://api.binance.com/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching data for {symbol}: {str(e)}")
    
    # Parse response
    data = response.json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    
    # Convert timestamp and set as index
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Keep only OHLCV columns and convert to float
    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
    # Cache for 1 hour
    cache.set(cache_key, df.to_json(), HISTORICAL_DATA_TTL)
    
    return df


def get_current_price(symbol: str, use_live: bool = True) -> float:
    """
    Get current price for a symbol
    
    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        use_live: If True, try to get live price from cache first (WebSocket data)
    
    Returns:
        Current price as float
    
    Raises:
        Exception: If API request fails
    """
    # Try to get live price from cache (populated by WebSocket service)
    if use_live:
        live_price_key = f"live_price_{symbol}"
        live_price_data = cache.get(live_price_key)
        if live_price_data:
            return float(live_price_data.get('price', 0))
    
    # Fallback to REST API
    cache_key = f"current_price_{symbol}"
    
    # Check cache first
    cached_price = cache.get(cache_key)
    if cached_price is not None:
        return float(cached_price)
    
    # Fetch from Binance API
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {'symbol': symbol}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        price = float(response.json()['price'])
        
        # Cache for 1 minute
        cache.set(cache_key, price, CURRENT_PRICE_TTL)
        return price
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching current price for {symbol}: {str(e)}")


def get_live_prices(symbols: List[str]) -> Dict[str, float]:
    """
    Get live prices for multiple symbols
    
    Args:
        symbols: List of trading pair symbols
    
    Returns:
        Dictionary mapping symbol to current price
    """
    prices = {}
    
    for symbol in symbols:
        try:
            # Try live cache first
            live_price_key = f"live_price_{symbol}"
            live_data = cache.get(live_price_key)
            
            if live_data and 'price' in live_data:
                prices[symbol] = float(live_data['price'])
            else:
                # Fallback to REST API
                prices[symbol] = get_current_price(symbol, use_live=False)
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
            prices[symbol] = 0.0
    
    return prices


def get_price_stats(symbol: str) -> Optional[Dict]:
    """
    Get 24h price statistics
    
    Args:
        symbol: Trading pair symbol
    
    Returns:
        Dictionary with price statistics or None if error
    """
    cache_key = f"price_stats_{symbol}"
    
    # Check cache first
    cached_stats = cache.get(cache_key)
    if cached_stats is not None:
        return cached_stats
    
    # Try live cache first (from WebSocket)
    live_stats_key = f"live_price_{symbol}"
    live_data = cache.get(live_stats_key)
    if live_data:
        stats = {
            'symbol': symbol,
            'price': live_data.get('price'),
            'high_24h': live_data.get('high_24h'),
            'low_24h': live_data.get('low_24h'),
            'volume_24h': live_data.get('volume_24h'),
            'price_change_24h': live_data.get('price_change_24h'),
            'price_change_percent_24h': live_data.get('price_change_percent_24h'),
            'timestamp': live_data.get('timestamp', datetime.now(TIMEZONE).isoformat())
        }
        cache.set(cache_key, stats, PRICE_STATS_TTL)
        return stats
    
    # Fallback to REST API
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        params = {'symbol': symbol}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        stats = {
            'symbol': symbol,
            'price': float(data['lastPrice']),
            'high_24h': float(data['highPrice']),
            'low_24h': float(data['lowPrice']),
            'volume_24h': float(data['volume']),
            'price_change_24h': float(data['priceChange']),
            'price_change_percent_24h': float(data['priceChangePercent']),
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, stats, PRICE_STATS_TTL)
        return stats
    except Exception as e:
        print(f"Error fetching price stats for {symbol}: {e}")
        return None


def is_live_data_available() -> bool:
    """
    Check if live WebSocket data is available
    
    Returns:
        True if WebSocket connection is active
    """
    status_key = "websocket_status"
    status = cache.get(status_key)
    return status and status.get('connected', False)


def get_websocket_status() -> Dict:
    """
    Get WebSocket connection status
    
    Returns:
        Dictionary with connection status information
    """
    status_key = "websocket_status"
    status = cache.get(status_key)
    
    if status:
        return status
    
    return {
        'connected': False,
        'last_update': None,
        'error': None,
        'symbols_tracked': []
    }


def get_multiple_historical_data(symbols: List[str], interval: str = '1d', 
                                 limit: int = 1000) -> Dict[str, pd.DataFrame]:
    """
    Get historical data for multiple symbols
    
    Args:
        symbols: List of trading pair symbols
        interval: Candle interval
        limit: Number of candles to fetch
    
    Returns:
        Dictionary mapping symbol to DataFrame
    """
    df_prices = {}
    
    for symbol in symbols:
        try:
            df_prices[symbol] = get_historical_data(symbol, interval, limit)
        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")
            # Return empty DataFrame to prevent crashes
            df_prices[symbol] = pd.DataFrame()
    
    return df_prices


def align_dataframes(df_dict: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Align multiple DataFrames to common index
    
    Args:
        df_dict: Dictionary of symbol -> DataFrame
    
    Returns:
        Dictionary with aligned DataFrames
    """
    if not df_dict:
        return {}
    
    # Find common index across all DataFrames
    common_index = None
    for df in df_dict.values():
        if df.empty:
            continue
        if common_index is None:
            common_index = df.index
        else:
            common_index = common_index.intersection(df.index)
    
    if common_index is None or len(common_index) == 0:
        return df_dict
    
    # Align all DataFrames to common index
    aligned_dict = {}
    for symbol, df in df_dict.items():
        if not df.empty:
            aligned_dict[symbol] = df.loc[common_index]
        else:
            aligned_dict[symbol] = df
    
    return aligned_dict
