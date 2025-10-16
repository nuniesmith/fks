# src/data.py

import pandas as pd
import requests
import json
from typing import Optional, Dict
from datetime import datetime
import pytz

from cache import redis_client, price_cache, cache_manager

TIMEZONE = pytz.timezone('America/Toronto')


def get_historical_data(symbol, interval='1d', limit=1000):
    """
    Get historical OHLCV data from Binance API
    Uses Redis cache to avoid repeated API calls
    """
    cache_key = f"historical_{symbol}_{interval}_{limit}"
    
    # Try to get from cache
    cached_data = cache_manager.get(cache_key)
    if cached_data is not None:
        df = pd.read_json(cached_data)
        df.index = pd.to_datetime(df.index)  # Ensure index is datetime
        return df
    
    # Fetch from API
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Error fetching data for {symbol}: {response.text}")
    
    data = json.loads(response.text)
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 
        'close_time', 'quote_asset_volume', 'number_of_trades', 
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
    # Cache for 1 hour
    cache_manager.set(cache_key, df.to_json(), ttl=3600)
    
    return df


def get_current_price(symbol: str, use_live: bool = True) -> float:
    """
    Get current price for a symbol
    
    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        use_live: If True, try to get live price from WebSocket first
    
    Returns:
        Current price as float
    """
    # Try to get live price from WebSocket cache
    if use_live:
        live_price_data = price_cache.get_price(symbol)
        if live_price_data:
            return float(live_price_data['price'])
    
    # Fallback to REST API
    cache_key = f"current_price_{symbol}"
    
    # Check cache first
    cached_price = cache_manager.get(cache_key)
    if cached_price is not None:
        return float(cached_price)
    
    # Fetch from API
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {'symbol': symbol}
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        price = float(json.loads(response.text)['price'])
        cache_manager.set(cache_key, price, ttl=60)  # Cache for 1 minute
        return price
    else:
        raise Exception(f"Error fetching current price for {symbol}")


def get_live_prices(symbols: list) -> Dict[str, float]:
    """
    Get live prices for multiple symbols
    
    Args:
        symbols: List of trading pair symbols
    
    Returns:
        Dictionary mapping symbol to current price
    """
    prices = {}
    
    # Try to get from WebSocket cache first
    live_data = price_cache.get_all_prices(symbols)
    
    for symbol in symbols:
        if symbol in live_data:
            prices[symbol] = float(live_data[symbol]['price'])
        else:
            # Fallback to REST API
            try:
                prices[symbol] = get_current_price(symbol, use_live=False)
            except Exception as e:
                print(f"Error getting price for {symbol}: {e}")
                prices[symbol] = 0.0
    
    return prices


def get_price_stats(symbol: str) -> Optional[Dict]:
    """
    Get 24h price statistics
    
    Returns live data if available, otherwise fetches from API
    """
    # Try live cache first
    live_data = price_cache.get_price(symbol)
    if live_data:
        return {
            'symbol': symbol,
            'price': live_data['price'],
            'high_24h': live_data['high_24h'],
            'low_24h': live_data['low_24h'],
            'volume_24h': live_data['volume_24h'],
            'price_change_24h': live_data['price_change_24h'],
            'price_change_percent_24h': live_data['price_change_percent_24h'],
            'timestamp': live_data['timestamp']
        }
    
    # Fallback to REST API
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        params = {'symbol': symbol}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'symbol': symbol,
                'price': float(data['lastPrice']),
                'high_24h': float(data['highPrice']),
                'low_24h': float(data['lowPrice']),
                'volume_24h': float(data['volume']),
                'price_change_24h': float(data['priceChange']),
                'price_change_percent_24h': float(data['priceChangePercent']),
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }
    except Exception as e:
        print(f"Error fetching price stats for {symbol}: {e}")
    
    return None


def is_live_data_available() -> bool:
    """Check if live WebSocket data is available"""
    return price_cache.is_connected()


def get_websocket_status() -> Dict:
    """Get WebSocket connection status"""
    return price_cache.get_connection_status()
