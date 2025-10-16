#!/usr/bin/env python3
# src/data_sync_service.py
"""
Background service to synchronize historical and real-time fks data
This service runs independently and keeps the TimescaleDB up to date
"""

import time
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import SYMBOLS, TIMEFRAMES, BINANCE_INTERVALS, HISTORICAL_DAYS, MAX_CANDLES_PER_REQUEST
from db_utils import (
    bulk_insert_ohlcv, 
    update_sync_status, 
    get_sync_status,
    get_latest_ohlcv_time,
    get_oldest_ohlcv_time
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TIMEZONE = pytz.timezone('America/Toronto')
BINANCE_BASE_URL = "https://api.binance.com/api/v3"


class DataSyncService:
    """Service to sync historical and real-time OHLCV data"""
    
    def __init__(self):
        self.running = False
        self.symbols = SYMBOLS
        self.timeframes = TIMEFRAMES
    
    def fetch_historical_klines(
        self, 
        symbol: str, 
        interval: str, 
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = MAX_CANDLES_PER_REQUEST
    ) -> List[Dict]:
        """
        Fetch historical klines from Binance API
        
        Args:
            symbol: Trading pair symbol
            interval: Binance interval string
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Number of candles to fetch (max 1000)
        
        Returns:
            List of OHLCV data dictionaries
        """
        url = f"{BINANCE_BASE_URL}/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Convert to our format
            candles = []
            for candle in data:
                candles.append({
                    'time': datetime.fromtimestamp(candle[0] / 1000, tz=pytz.UTC).astimezone(TIMEZONE),
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5]),
                    'quote_volume': float(candle[7]),
                    'trades_count': int(candle[8]),
                    'taker_buy_base_volume': float(candle[9]),
                    'taker_buy_quote_volume': float(candle[10])
                })
            
            return candles
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data for {symbol} {interval}: {e}")
            return []
    
    def sync_historical_data(self, symbol: str, timeframe: str) -> bool:
        """
        Sync historical data for a symbol/timeframe pair
        Fetches up to HISTORICAL_DAYS of data in batches
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Starting historical sync for {symbol} {timeframe}")
        
        try:
            # Update status to syncing
            update_sync_status(symbol, timeframe, 'syncing')
            
            # Calculate start time (2 years ago)
            end_time = datetime.now(TIMEZONE)
            start_time = end_time - timedelta(days=HISTORICAL_DAYS)
            
            # Check if we already have data
            latest_time = get_latest_ohlcv_time(symbol, timeframe)
            oldest_time = get_oldest_ohlcv_time(symbol, timeframe)
            
            if latest_time and oldest_time:
                logger.info(f"{symbol} {timeframe} already has data from {oldest_time} to {latest_time}")
                # Sync only missing recent data
                start_time = latest_time
            
            interval = BINANCE_INTERVALS[timeframe]
            current_start = int(start_time.timestamp() * 1000)
            current_end = int(end_time.timestamp() * 1000)
            
            total_inserted = 0
            batch_count = 0
            
            # Fetch in batches
            while current_start < current_end:
                batch_count += 1
                candles = self.fetch_historical_klines(
                    symbol, 
                    interval, 
                    start_time=current_start,
                    end_time=current_end,
                    limit=MAX_CANDLES_PER_REQUEST
                )
                
                if not candles:
                    break
                
                # Insert into database
                inserted = bulk_insert_ohlcv(candles, symbol, timeframe)
                total_inserted += inserted
                
                logger.info(f"{symbol} {timeframe} - Batch {batch_count}: {inserted} candles inserted")
                
                # Update start time for next batch
                last_candle_time = candles[-1]['time']
                current_start = int(last_candle_time.timestamp() * 1000) + 1
                
                # Rate limiting
                time.sleep(0.5)
                
                # If we got less than requested, we've reached the end
                if len(candles) < MAX_CANDLES_PER_REQUEST:
                    break
            
            logger.info(f"Completed sync for {symbol} {timeframe}: {total_inserted} total candles")
            
            # Update status to completed
            update_sync_status(symbol, timeframe, 'completed')
            return True
        
        except Exception as e:
            logger.error(f"Error syncing {symbol} {timeframe}: {e}")
            update_sync_status(symbol, timeframe, 'error', str(e))
            return False
    
    def sync_latest_data(self, symbol: str, timeframe: str) -> bool:
        """
        Sync only the latest data (last 100 candles)
        Used for regular updates
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string
        
        Returns:
            True if successful, False otherwise
        """
        try:
            interval = BINANCE_INTERVALS[timeframe]
            candles = self.fetch_historical_klines(symbol, interval, limit=100)
            
            if candles:
                inserted = bulk_insert_ohlcv(candles, symbol, timeframe)
                logger.debug(f"Updated {symbol} {timeframe}: {inserted} candles")
                update_sync_status(symbol, timeframe, 'completed')
                return True
            return False
        
        except Exception as e:
            logger.error(f"Error updating {symbol} {timeframe}: {e}")
            return False
    
    def initial_sync_all(self, max_workers: int = 5):
        """
        Perform initial sync for all symbols and timeframes
        Uses ThreadPoolExecutor for parallel processing
        
        Args:
            max_workers: Maximum number of concurrent sync tasks
        """
        logger.info("Starting initial sync for all symbols and timeframes")
        
        tasks = []
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                tasks.append((symbol, timeframe))
        
        total_tasks = len(tasks)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(self.sync_historical_data, symbol, timeframe): (symbol, timeframe)
                for symbol, timeframe in tasks
            }
            
            for future in as_completed(future_to_task):
                symbol, timeframe = future_to_task[future]
                completed += 1
                try:
                    success = future.result()
                    status = "✓" if success else "✗"
                    logger.info(f"[{completed}/{total_tasks}] {status} {symbol} {timeframe}")
                except Exception as e:
                    logger.error(f"[{completed}/{total_tasks}] ✗ {symbol} {timeframe}: {e}")
        
        logger.info("Initial sync completed")
    
    def update_all_latest(self):
        """Update latest data for all symbols and timeframes"""
        logger.info("Updating latest data for all symbols...")
        
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                self.sync_latest_data(symbol, timeframe)
        
        logger.info("Latest data update completed")
    
    def run_continuous(self, update_interval: int = 60):
        """
        Run continuous sync service
        
        Args:
            update_interval: Seconds between updates
        """
        self.running = True
        logger.info(f"Starting continuous sync service (update every {update_interval}s)")
        
        # First, do initial sync for any missing data
        self.initial_sync_all(max_workers=3)
        
        # Then run continuous updates
        while self.running:
            try:
                self.update_all_latest()
                logger.info(f"Next update in {update_interval} seconds...")
                time.sleep(update_interval)
            except KeyboardInterrupt:
                logger.info("Received stop signal")
                self.stop()
            except Exception as e:
                logger.error(f"Error in continuous sync: {e}")
                time.sleep(10)
    
    def stop(self):
        """Stop the sync service"""
        logger.info("Stopping sync service...")
        self.running = False


def main():
    """Main entry point"""
    import sys
    
    service = DataSyncService()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            # Initial full sync
            service.initial_sync_all(max_workers=5)
        
        elif command == 'update':
            # Update latest data
            service.update_all_latest()
        
        elif command == 'continuous':
            # Run continuous service
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            service.run_continuous(update_interval=interval)
        
        elif command == 'status':
            # Show sync status
            status = get_sync_status()
            for s in status:
                print(f"{s['symbol']:12} {s['timeframe']:4} | Status: {s['status']:10} | "
                      f"Candles: {s['total_candles']:6} | Last sync: {s['last_sync']}")
        
        else:
            print("Unknown command. Use: init, update, continuous, or status")
    
    else:
        print("Usage: python data_sync_service.py [init|update|continuous|status]")
        print("")
        print("Commands:")
        print("  init       - Initial full historical sync (2 years)")
        print("  update     - Update latest data for all symbols")
        print("  continuous - Run continuous update service")
        print("  status     - Show sync status for all symbols")


if __name__ == "__main__":
    main()
