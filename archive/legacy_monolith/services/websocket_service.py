#!/usr/bin/env python3
# src/websocket_service.py
"""
WebSocket service for real-time fks price updates
Connects to Binance WebSocket streams and stores live prices in Redis
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import pytz
import websockets
from cache import redis_client
from redis import Redis

from framework.config.constants import REDIS_DB, REDIS_HOST, REDIS_PORT, SYMBOLS, WS_PING_INTERVAL, WS_RECONNECT_DELAY

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TIMEZONE = pytz.timezone("America/Toronto")
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"


class BinanceWebSocketClient:
    """Real-time WebSocket client for Binance price feeds"""

    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.running = False
        self.websocket = None
        self.redis = redis_client

        # Create stream names (e.g., btcusdt@ticker)
        self.streams = [f"{symbol.lower()}@ticker" for symbol in symbols]

        # WebSocket URL with combined streams
        streams_param = "/".join(self.streams)
        self.ws_url = f"{BINANCE_WS_URL}/{streams_param}"

        logger.info(f"Initialized WebSocket client for {len(symbols)} symbols")

    async def connect(self):
        """Connect to Binance WebSocket"""
        try:
            logger.info("Connecting to Binance WebSocket...")
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=WS_PING_INTERVAL,
                ping_timeout=10,
                close_timeout=5,
            )
            logger.info("✅ WebSocket connected successfully")
            self.update_connection_status("connected")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.update_connection_status("disconnected", str(e))
            return False

    def update_connection_status(self, status: str, error: Optional[str] = None):
        """Update WebSocket connection status in Redis"""
        status_data = {
            "status": status,
            "timestamp": datetime.now(TIMEZONE).isoformat(),
            "error": error or "",
        }
        self.redis.set("ws:connection_status", json.dumps(status_data))
        self.redis.expire("ws:connection_status", 300)  # 5 minutes TTL

    def store_price_update(self, symbol: str, data: dict):
        """
        Store price update in Redis

        Stores both individual symbol price and aggregated index
        """
        try:
            price_data = {
                "symbol": symbol,
                "price": float(data.get("c", 0)),  # Current close price
                "high_24h": float(data.get("h", 0)),
                "low_24h": float(data.get("l", 0)),
                "volume_24h": float(data.get("v", 0)),
                "quote_volume_24h": float(data.get("q", 0)),
                "price_change_24h": float(data.get("p", 0)),
                "price_change_percent_24h": float(data.get("P", 0)),
                "weighted_avg_price": float(data.get("w", 0)),
                "bid_price": float(data.get("b", 0)),
                "ask_price": float(data.get("a", 0)),
                "timestamp": datetime.now(TIMEZONE).isoformat(),
                "event_time": datetime.fromtimestamp(
                    int(data.get("E", 0)) / 1000, tz=TIMEZONE
                ).isoformat(),
            }

            # Store individual symbol price
            key = f"live_price:{symbol}"
            self.redis.set(key, json.dumps(price_data))
            self.redis.expire(key, 60)  # 1 minute TTL

            # Update last update timestamp
            self.redis.set(f"live_price:{symbol}:last_update", price_data["timestamp"])
            self.redis.expire(f"live_price:{symbol}:last_update", 60)

            # Store in sorted set for easy retrieval of all prices
            self.redis.zadd(
                "live_prices:all", {symbol: datetime.now(TIMEZONE).timestamp()}
            )

            logger.debug(
                f"📊 {symbol}: ${price_data['price']:,.2f} "
                f"({price_data['price_change_percent_24h']:+.2f}%)"
            )

        except Exception as e:
            logger.error(f"Error storing price update for {symbol}: {e}")

    async def handle_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)

            # Binance ticker format
            if "e" in data and data["e"] == "24hrTicker":
                symbol = data.get("s", "").upper()
                if symbol in self.symbols:
                    self.store_price_update(symbol, data)

            # Combined stream format
            elif "stream" in data and "data" in data:
                ticker_data = data["data"]
                symbol = ticker_data.get("s", "").upper()
                if symbol in self.symbols:
                    self.store_price_update(symbol, ticker_data)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")

    async def listen(self):
        """Listen for WebSocket messages"""
        try:
            async for message in self.websocket:
                await self.handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.update_connection_status("disconnected", "Connection closed")
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}")
            self.update_connection_status("error", str(e))

    async def run(self):
        """Main run loop with auto-reconnect"""
        self.running = True
        logger.info("Starting WebSocket service...")

        while self.running:
            try:
                # Connect to WebSocket
                connected = await self.connect()

                if connected:
                    # Listen for messages
                    await self.listen()

                # If disconnected, wait before reconnecting
                if self.running:
                    logger.info(f"Reconnecting in {WS_RECONNECT_DELAY} seconds...")
                    await asyncio.sleep(WS_RECONNECT_DELAY)

            except KeyboardInterrupt:
                logger.info("Received stop signal")
                self.stop()
            except Exception as e:
                logger.error(f"Unexpected error in run loop: {e}")
                await asyncio.sleep(WS_RECONNECT_DELAY)

        logger.info("WebSocket service stopped")

    def stop(self):
        """Stop the WebSocket service"""
        logger.info("Stopping WebSocket service...")
        self.running = False
        self.update_connection_status("stopped")
        if self.websocket:
            asyncio.create_task(self.websocket.close())


class PriceAggregator:
    """Aggregates prices and calculates market index"""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def get_live_price(self, symbol: str) -> Optional[dict]:
        """Get live price for a symbol from Redis"""
        try:
            key = f"live_price:{symbol}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting live price for {symbol}: {e}")
            return None

    def get_all_live_prices(self) -> dict[str, dict]:
        """Get all live prices"""
        prices = {}
        for symbol in SYMBOLS:
            price_data = self.get_live_price(symbol)
            if price_data:
                prices[symbol] = price_data
        return prices

    def calculate_market_index(
        self, base_prices: Optional[dict[str, float]] = None
    ) -> Optional[float]:
        """
        Calculate normalized market index

        Args:
            base_prices: Base prices for normalization (optional)

        Returns:
            Current market index value
        """
        try:
            live_prices = self.get_all_live_prices()

            if not live_prices:
                return None

            # Calculate average normalized price
            if base_prices:
                normalized_prices = [
                    live_prices[sym]["price"] / base_prices.get(sym, 1)
                    for sym in SYMBOLS
                    if sym in live_prices and sym in base_prices
                ]
            else:
                # Use equal weight
                normalized_prices = [
                    live_prices[sym]["price"] for sym in SYMBOLS if sym in live_prices
                ]

            if normalized_prices:
                return sum(normalized_prices) / len(normalized_prices)

            return None

        except Exception as e:
            logger.error(f"Error calculating market index: {e}")
            return None

    def get_connection_status(self) -> dict:
        """Get WebSocket connection status"""
        try:
            status_json = self.redis.get("ws:connection_status")
            if status_json:
                return json.loads(status_json)
            return {"status": "unknown", "timestamp": None, "error": ""}
        except Exception as e:
            logger.error(f"Error getting connection status: {e}")
            return {"status": "error", "timestamp": None, "error": str(e)}


async def main():
    """Main entry point"""
    import sys

    # Create WebSocket client
    client = BinanceWebSocketClient(SYMBOLS)

    try:
        # Run the WebSocket service
        await client.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        client.stop()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
