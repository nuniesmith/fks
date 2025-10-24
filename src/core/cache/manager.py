# src/cache.py
"""
Redis cache management for:
- Live price data
- Session state persistence
- WebSocket connection status
- Temporary data caching
"""

import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytz
import redis

from framework.config.constants import REDIS_DB, REDIS_HOST, REDIS_PORT

TIMEZONE = pytz.timezone("America/Toronto")

# Redis client singleton
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=False,  # We'll handle encoding ourselves
)


class SessionStateManager:
    """Manage Streamlit session state in Redis for persistence"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.session_prefix = "session:"
        self.default_ttl = 3600 * 24  # 24 hours

    def save_state(self, session_id: str, state_data: dict, ttl: int | None = None):
        """
        Save session state to Redis

        Args:
            session_id: Unique session identifier
            state_data: Dictionary of state data to save
            ttl: Time to live in seconds (default: 24 hours)
        """
        try:
            key = f"{self.session_prefix}{session_id}"

            # Add metadata
            state_data["_last_updated"] = datetime.now(TIMEZONE).isoformat()

            # Serialize and store
            serialized = pickle.dumps(state_data)
            self.redis.set(key, serialized)
            self.redis.expire(key, ttl or self.default_ttl)

            return True
        except Exception as e:
            print(f"Error saving session state: {e}")
            return False

    def load_state(self, session_id: str) -> dict | None:
        """
        Load session state from Redis

        Args:
            session_id: Unique session identifier

        Returns:
            Dictionary of state data or None if not found
        """
        try:
            key = f"{self.session_prefix}{session_id}"
            data = self.redis.get(key)

            if data:
                state_data = pickle.loads(data)
                return state_data

            return None
        except Exception as e:
            print(f"Error loading session state: {e}")
            return None

    def delete_state(self, session_id: str):
        """Delete session state"""
        try:
            key = f"{self.session_prefix}{session_id}"
            self.redis.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting session state: {e}")
            return False

    def update_state_field(self, session_id: str, field: str, value: Any):
        """Update a specific field in session state"""
        state = self.load_state(session_id) or {}
        state[field] = value
        return self.save_state(session_id, state)

    def get_state_field(self, session_id: str, field: str, default: Any = None):
        """Get a specific field from session state"""
        state = self.load_state(session_id)
        if state:
            return state.get(field, default)
        return default


class LivePriceCache:
    """Manage live price data from WebSocket"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.price_prefix = "live_price:"

    def get_price(self, symbol: str) -> dict | None:
        """Get live price for a symbol"""
        try:
            key = f"{self.price_prefix}{symbol}"
            data = self.redis.get(key)

            if data:
                # Decode if bytes
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                return json.loads(data)

            return None
        except Exception as e:
            print(f"Error getting live price for {symbol}: {e}")
            return None

    def get_all_prices(self, symbols: list) -> dict[str, dict]:
        """Get live prices for multiple symbols"""
        prices = {}
        for symbol in symbols:
            price_data = self.get_price(symbol)
            if price_data:
                prices[symbol] = price_data
        return prices

    def set_price(self, symbol: str, price_data: dict, ttl: int = 60):
        """
        Set live price for a symbol

        Args:
            symbol: Trading pair symbol
            price_data: Price data dictionary
            ttl: Time to live in seconds
        """
        try:
            key = f"{self.price_prefix}{symbol}"
            self.redis.set(key, json.dumps(price_data))
            self.redis.expire(key, ttl)
            return True
        except Exception as e:
            print(f"Error setting live price for {symbol}: {e}")
            return False

    def get_connection_status(self) -> dict:
        """Get WebSocket connection status"""
        try:
            data = self.redis.get("ws:connection_status")
            if data:
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                return json.loads(data)
            return {"status": "unknown", "timestamp": None, "error": ""}
        except Exception as e:
            print(f"Error getting connection status: {e}")
            return {"status": "error", "timestamp": None, "error": str(e)}

    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        status = self.get_connection_status()
        return status.get("status") == "connected"


class CacheManager:
    """General purpose cache manager"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def set(self, key: str, value: Any, ttl: int | None = None):
        """Set a cache value"""
        try:
            serialized = pickle.dumps(value)
            self.redis.set(key, serialized)
            if ttl:
                self.redis.expire(key, ttl)
            return True
        except Exception as e:
            print(f"Error setting cache value: {e}")
            return False

    def get(self, key: str, default: Any = None):
        """Get a cache value"""
        try:
            data = self.redis.get(key)
            if data:
                return pickle.loads(data)
            return default
        except Exception as e:
            print(f"Error getting cache value: {e}")
            return default

    def delete(self, key: str):
        """Delete a cache value"""
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting cache value: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if a key exists"""
        try:
            return bool(self.redis.exists(key))
        except Exception as e:
            print(f"Error checking key existence: {e}")
            return False

    def set_json(self, key: str, value: dict, ttl: int | None = None):
        """Set a JSON value"""
        try:
            self.redis.set(key, json.dumps(value))
            if ttl:
                self.redis.expire(key, ttl)
            return True
        except Exception as e:
            print(f"Error setting JSON value: {e}")
            return False

    def get_json(self, key: str, default: Any = None):
        """Get a JSON value"""
        try:
            data = self.redis.get(key)
            if data:
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                return json.loads(data)
            return default
        except Exception as e:
            print(f"Error getting JSON value: {e}")
            return default


# Global instances
session_manager = SessionStateManager(redis_client)
price_cache = LivePriceCache(redis_client)
cache_manager = CacheManager(redis_client)
