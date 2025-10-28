"""
Timezone utilities for FKS API
"""
import os
from datetime import datetime
from typing import Optional
import pytz


def get_toronto_timezone() -> pytz.timezone:
    """Get the Toronto timezone object."""
    return pytz.timezone('America/Toronto')


def get_current_toronto_time() -> datetime:
    """Get current time in Toronto timezone."""
    toronto_tz = get_toronto_timezone()
    return datetime.now(toronto_tz)


def convert_utc_to_toronto(utc_time: datetime) -> datetime:
    """Convert UTC time to Toronto time."""
    if utc_time.tzinfo is None:
        # Assume naive datetime is UTC
        utc_time = pytz.utc.localize(utc_time)
    elif utc_time.tzinfo != pytz.utc:
        # Convert to UTC first if not already
        utc_time = utc_time.astimezone(pytz.utc)
    
    toronto_tz = get_toronto_timezone()
    return utc_time.astimezone(toronto_tz)


def convert_toronto_to_utc(toronto_time: datetime) -> datetime:
    """Convert Toronto time to UTC."""
    toronto_tz = get_toronto_timezone()
    
    if toronto_time.tzinfo is None:
        # Assume naive datetime is Toronto time
        toronto_time = toronto_tz.localize(toronto_time)
    
    return toronto_time.astimezone(pytz.utc)


def format_toronto_time(dt: Optional[datetime] = None, format_str: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """Format datetime in Toronto timezone."""
    if dt is None:
        dt = get_current_toronto_time()
    elif dt.tzinfo is None:
        # Convert UTC to Toronto if naive
        dt = convert_utc_to_toronto(dt)
    elif dt.tzinfo != get_toronto_timezone():
        # Convert to Toronto if different timezone
        dt = dt.astimezone(get_toronto_timezone())
    
    return dt.strftime(format_str)


def get_market_hours_info() -> dict:
    """Get trading market hours information for Toronto timezone."""
    toronto_tz = get_toronto_timezone()
    current_toronto = get_current_toronto_time()
    
    # Standard market hours (9:30 AM - 4:00 PM ET)
    market_open = current_toronto.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = current_toronto.replace(hour=16, minute=0, second=0, microsecond=0)
    
    is_market_hours = market_open <= current_toronto <= market_close
    is_weekday = current_toronto.weekday() < 5  # Monday = 0, Sunday = 6
    
    return {
        "current_time": format_toronto_time(current_toronto),
        "market_open": format_toronto_time(market_open),
        "market_close": format_toronto_time(market_close),
        "is_market_hours": is_market_hours and is_weekday,
        "is_weekday": is_weekday,
        "timezone": str(toronto_tz)
    }


# Configure logging to use Toronto timezone
def setup_toronto_logging():
    """Setup logging to display times in Toronto timezone."""
    import logging
    
    class TorontoFormatter(logging.Formatter):
        def converter(self, timestamp):
            dt = datetime.fromtimestamp(timestamp)
            return convert_utc_to_toronto(dt).timetuple()
    
    # Example usage in your logging setup
    formatter = TorontoFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S %Z'
    )
    return formatter
