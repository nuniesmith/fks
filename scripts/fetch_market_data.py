#!/usr/bin/env python3
"""Fetch real market data for ASMBTR optimization.

This script fetches high-frequency tick data from various sources for
validating the ASMBTR strategy optimization framework.

Usage:
    python scripts/fetch_market_data.py --symbol BTCUSDT --interval 1m --limit 2000
    python scripts/fetch_market_data.py --symbol EURUSD --source yfinance --limit 2000
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fetch_with_ccxt(symbol: str, interval: str = '1m', limit: int = 2000) -> List[Dict[str, Any]]:
    """Fetch data using CCXT (for crypto pairs).
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USDT', 'ETH/USDT')
        interval: Timeframe ('1m', '5m', '15m', '1h')
        limit: Number of candles to fetch
    
    Returns:
        List of tick dicts with timestamp, open, high, low, close, volume
    """
    try:
        import ccxt
    except ImportError:
        logger.warning("CCXT not installed locally. Trying yfinance as fallback...")
        # Convert symbol for yfinance (BTC/USDT -> BTC-USD)
        yf_symbol = symbol.replace('/', '-').replace('USDT', 'USD')
        logger.info(f"Converting to yfinance symbol: {yf_symbol}")
        return fetch_with_yfinance(yf_symbol, interval, days=2)
    
    logger.info(f"Fetching {limit} {interval} candles for {symbol} from Binance...")
    
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    
    # Fetch OHLCV data
    ohlcv = exchange.fetch_ohlcv(symbol, interval, limit=limit)
    
    # Convert to our format
    ticks = []
    for candle in ohlcv:
        timestamp, open_price, high, low, close, volume = candle
        ticks.append({
            'timestamp': datetime.fromtimestamp(timestamp / 1000).isoformat(),
            'open': float(open_price),
            'high': float(high),
            'low': float(low),
            'close': float(close),
            'volume': float(volume)
        })
    
    logger.info(f"Fetched {len(ticks)} candles from {ticks[0]['timestamp']} to {ticks[-1]['timestamp']}")
    return ticks


def fetch_with_yfinance(symbol: str, interval: str = '1m', days: int = 7) -> List[Dict[str, Any]]:
    """Fetch data using yfinance (for FX via currency ETFs or =X pairs).
    
    Args:
        symbol: Ticker symbol (e.g., 'EURUSD=X', 'FXE' for EUR/USD ETF)
        interval: Timeframe ('1m', '5m', '15m', '1h', '1d')
        days: Number of days of historical data
    
    Returns:
        List of tick dicts with timestamp, open, high, low, close, volume
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        sys.exit(1)
    
    logger.info(f"Fetching {days} days of {interval} data for {symbol} from Yahoo Finance...")
    
    # Download data
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=f'{days}d', interval=interval)
    
    if df.empty:
        logger.error(f"No data returned for {symbol}. Check symbol format (e.g., EURUSD=X)")
        sys.exit(1)
    
    # Convert to our format
    ticks = []
    for timestamp, row in df.iterrows():
        ticks.append({
            'timestamp': timestamp.isoformat(),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': float(row['Volume']) if 'Volume' in row else 0.0
        })
    
    logger.info(f"Fetched {len(ticks)} candles from {ticks[0]['timestamp']} to {ticks[-1]['timestamp']}")
    return ticks


def calculate_statistics(ticks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate basic statistics on the data.
    
    Args:
        ticks: List of tick data
    
    Returns:
        Dict with mean price, volatility, trend info
    """
    import numpy as np
    
    prices = [t['close'] for t in ticks]
    returns = np.diff(np.log(prices))
    
    stats = {
        'n_ticks': len(ticks),
        'mean_price': float(np.mean(prices)),
        'std_price': float(np.std(prices)),
        'min_price': float(np.min(prices)),
        'max_price': float(np.max(prices)),
        'mean_return': float(np.mean(returns)),
        'volatility': float(np.std(returns)),
        'autocorr_lag1': float(np.corrcoef(returns[:-1], returns[1:])[0, 1]),
        'trend': 'uptrend' if prices[-1] > prices[0] else 'downtrend',
        'price_change_pct': float((prices[-1] - prices[0]) / prices[0] * 100)
    }
    
    return stats


def save_data(ticks: List[Dict[str, Any]], output_path: Path, stats: Dict[str, Any]):
    """Save tick data and statistics to files.
    
    Args:
        ticks: Tick data to save
        output_path: Base path for output files
        stats: Statistics to include in metadata
    """
    # Save ticks
    data = {
        'metadata': {
            'symbol': stats.get('symbol', 'UNKNOWN'),
            'source': stats.get('source', 'UNKNOWN'),
            'interval': stats.get('interval', '1m'),
            'fetched_at': datetime.now().isoformat(),
            'n_ticks': len(ticks)
        },
        'statistics': stats,
        'ticks': ticks
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved {len(ticks)} ticks to {output_path}")
    
    # Also save just the ticks array for easy loading in optimize.py
    ticks_only_path = output_path.parent / f"{output_path.stem}_ticks_only.json"
    with open(ticks_only_path, 'w') as f:
        json.dump(ticks, f, indent=2)
    
    logger.info(f"Saved ticks-only format to {ticks_only_path}")


def main():
    parser = argparse.ArgumentParser(description='Fetch real market data for ASMBTR optimization')
    parser.add_argument('--symbol', type=str, default='BTC/USDT', 
                       help='Trading symbol (e.g., BTC/USDT for CCXT, EURUSD=X for yfinance)')
    parser.add_argument('--source', type=str, choices=['ccxt', 'yfinance'], default='ccxt',
                       help='Data source')
    parser.add_argument('--interval', type=str, default='1m',
                       help='Timeframe (1m, 5m, 15m, 1h, 1d)')
    parser.add_argument('--limit', type=int, default=2000,
                       help='Number of candles to fetch (for CCXT)')
    parser.add_argument('--days', type=int, default=7,
                       help='Number of days to fetch (for yfinance)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file path (default: data/market_data_{symbol}_{timestamp}.json)')
    
    args = parser.parse_args()
    
    # Fetch data
    if args.source == 'ccxt':
        ticks = fetch_with_ccxt(args.symbol, args.interval, args.limit)
    else:
        ticks = fetch_with_yfinance(args.symbol, args.interval, args.days)
    
    # Calculate statistics
    stats = calculate_statistics(ticks)
    stats['symbol'] = args.symbol
    stats['source'] = args.source
    stats['interval'] = args.interval
    
    # Print summary
    logger.info("\n=== Data Summary ===")
    logger.info(f"Symbol: {args.symbol}")
    logger.info(f"Ticks: {stats['n_ticks']}")
    logger.info(f"Price Range: {stats['min_price']:.2f} - {stats['max_price']:.2f}")
    logger.info(f"Mean Price: {stats['mean_price']:.2f}")
    logger.info(f"Volatility: {stats['volatility']:.6f}")
    logger.info(f"Autocorrelation (lag 1): {stats['autocorr_lag1']:.3f}")
    logger.info(f"Trend: {stats['trend']} ({stats['price_change_pct']:.2f}%)")
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        data_dir = Path(__file__).parent.parent / 'data' / 'market_data'
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize symbol for filename
        symbol_clean = args.symbol.replace('/', '_').replace('=', '')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = data_dir / f"{symbol_clean}_{args.interval}_{timestamp}.json"
    
    # Save data
    save_data(ticks, output_path, stats)
    
    logger.info(f"\n✅ Data fetch complete!")
    logger.info(f"Use this file with ASMBTROptimizer:")
    logger.info(f"  import json")
    logger.info(f"  with open('{output_path}', 'r') as f:")
    logger.info(f"      data = json.load(f)")
    logger.info(f"      ticks = data['ticks']")


if __name__ == '__main__':
    main()
docker-compose logs --tail=50 celery_beat | grep -E "asmbtr|beat|Scheduler"