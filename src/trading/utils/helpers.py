"""
Helper utilities for fks trading.
Migrated from src/utils.py

Handles:
- Trade logging to database
- Discord notifications
- Formatting and conversion utilities
"""

import requests
from datetime import datetime
from typing import Dict, Optional
import pytz
from django.conf import settings

from ..models import Trade, Position, Signal

TIMEZONE = pytz.timezone('America/Toronto')


def log_trade_to_db(trade_info: Dict) -> Optional[Trade]:
    """
    Log a trade to the database
    
    Args:
        trade_info: Dictionary with trade information
            - action: Trade action (BUY, SELL, etc.)
            - symbols: Symbol(s) traded
            - prices: Price(s)
            - quantities: Quantity(ies)
            - sl: Stop-loss (optional)
            - tp: Take-profit (optional)
            - account: Account instance (optional)
    
    Returns:
        Created Trade instance or None if error
    """
    try:
        # Create trade record
        new_trade = Trade(
            account=trade_info.get('account'),
            symbol=str(trade_info.get('symbols', '')),
            side='long',  # Default to long, can be customized
            quantity=float(trade_info.get('quantities', 0)),
            entry_price=float(trade_info.get('prices', 0)),
            exit_price=None,  # Will be set when position closes
            stop_loss=float(trade_info.get('sl')) if trade_info.get('sl') else None,
            take_profit=float(trade_info.get('tp')) if trade_info.get('tp') else None,
            status='open',
            entry_time=datetime.now(TIMEZONE),
            trade_metadata={
                'action': trade_info.get('action', ''),
                'logged_at': datetime.now(TIMEZONE).isoformat()
            }
        )
        new_trade.save()
        return new_trade
    except Exception as e:
        print(f"Error logging trade to database: {e}")
        return None


def send_discord_notification(webhook_url: str, message: str, 
                              username: str = "FKS Trading Bot") -> bool:
    """
    Send notification to Discord webhook
    
    Args:
        webhook_url: Discord webhook URL
        message: Message to send
        username: Bot username for the message
    
    Returns:
        True if successful, False otherwise
    
    Raises:
        Exception: If webhook URL not provided or request fails
    """
    if not webhook_url:
        raise Exception("Discord webhook URL not provided")
    
    # Prepare payload
    data = {
        "content": message,
        "username": username
    }
    
    try:
        response = requests.post(webhook_url, json=data, timeout=10)
        
        if response.status_code == 204:
            return True
        else:
            raise Exception(f"Discord API returned status {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error sending Discord notification: {str(e)}")


def format_trade_suggestions_for_discord(suggestions: list) -> str:
    """
    Format trade suggestions for Discord notification
    
    Args:
        suggestions: List of trade suggestion dictionaries
    
    Returns:
        Formatted message string
    """
    if not suggestions:
        return "No trade suggestions available."
    
    message = "📊 **Current Trading Signals**\n\n"
    
    for i, sug in enumerate(suggestions, 1):
        if 'symbol' in sug:
            message += f"**{i}. {sug.get('symbol', 'N/A')}**\n"
            message += f"   • Action: {sug.get('action', 'N/A')}\n"
            message += f"   • Price: ${sug.get('price', 0):,.2f}\n"
            message += f"   • Quantity: {sug.get('quantity', 0):.6f}\n"
            message += f"   • Stop Loss: ${sug.get('sl', 0):,.2f}\n"
            message += f"   • Take Profit: ${sug.get('tp', 0):,.2f}\n"
            if 'allocated_usdt' in sug:
                message += f"   • Allocation: ${sug.get('allocated_usdt', 0):,.2f}\n"
            message += "\n"
        else:
            message += f"{sug.get('action', 'N/A')}\n"
    
    message += f"*Generated at {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')}*"
    
    return message


def format_backtest_results_for_discord(metrics: Dict, best_params: Dict) -> str:
    """
    Format backtest results for Discord notification
    
    Args:
        metrics: Dictionary of backtest metrics
        best_params: Dictionary of optimized parameters
    
    Returns:
        Formatted message string
    """
    message = "📈 **Backtest Results**\n\n"
    
    message += "**Performance Metrics:**\n"
    message += f"• Sharpe Ratio: {metrics.get('Sharpe', 0):.2f}\n"
    message += f"• Sortino Ratio: {metrics.get('Sortino', 0):.2f}\n"
    message += f"• Calmar Ratio: {metrics.get('Calmar', 0):.2f}\n"
    message += f"• Total Return: {metrics.get('Total Return', 0):.2%}\n"
    message += f"• Annualized Return: {metrics.get('Annualized Return', 0):.2%}\n"
    message += f"• Max Drawdown: {metrics.get('Max Drawdown', 0):.2%}\n"
    message += f"• Win Rate: {metrics.get('Win Rate', 0):.2%}\n"
    message += f"• Number of Trades: {metrics.get('Trades', 0)}\n\n"
    
    message += "**Optimized Parameters:**\n"
    message += f"• SMA Period (M): {best_params.get('M', 0)}\n"
    message += f"• ATR Period: {best_params.get('atr_period', 0)}\n"
    message += f"• Stop Loss Multiplier: {best_params.get('sl_multiplier', 0):.2f}\n"
    message += f"• Take Profit Multiplier: {best_params.get('tp_multiplier', 0):.2f}\n\n"
    
    message += f"*Completed at {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')}*"
    
    return message


def format_price_data(price: float, decimals: int = 2) -> str:
    """
    Format price for display
    
    Args:
        price: Price value
        decimals: Number of decimal places
    
    Returns:
        Formatted price string
    """
    if price >= 1000:
        return f"${price:,.{decimals}f}"
    elif price >= 1:
        return f"${price:.{decimals}f}"
    else:
        # For very small prices, show more decimals
        return f"${price:.8f}"


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values
    
    Args:
        old_value: Original value
        new_value: New value
    
    Returns:
        Percentage change
    """
    if old_value == 0:
        return 0.0
    
    return ((new_value - old_value) / old_value) * 100


def get_discord_webhook_url() -> Optional[str]:
    """
    Get Discord webhook URL from settings
    
    Returns:
        Webhook URL or None
    """
    return getattr(settings, 'DISCORD_WEBHOOK_URL', None)


def validate_trade_data(trade_info: Dict) -> tuple[bool, str]:
    """
    Validate trade data before logging
    
    Args:
        trade_info: Trade information dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['action', 'symbols', 'prices', 'quantities']
    
    for field in required_fields:
        if field not in trade_info:
            return False, f"Missing required field: {field}"
    
    # Validate numeric fields
    try:
        price = float(trade_info['prices'])
        quantity = float(trade_info['quantities'])
        
        if price <= 0:
            return False, "Price must be greater than 0"
        
        if quantity <= 0:
            return False, "Quantity must be greater than 0"
        
    except (ValueError, TypeError):
        return False, "Invalid numeric values for price or quantity"
    
    return True, ""


def create_signal_record(
    symbol: str,
    signal_type: str,
    price: float,
    indicators: Dict,
    strategy=None
) -> Optional[Signal]:
    """
    Create a signal record in the database
    
    Args:
        symbol: Trading symbol
        signal_type: 'BUY', 'SELL', 'HOLD'
        price: Current price
        indicators: Dictionary of indicator values
        strategy: Strategy instance (optional)
    
    Returns:
        Created Signal instance or None
    """
    try:
        signal = Signal(
            strategy=strategy,
            symbol=symbol,
            signal_type=signal_type.lower(),
            price=price,
            confidence=indicators.get('confidence', 0.5),
            indicators=indicators,
            created_at=datetime.now(TIMEZONE)
        )
        signal.save()
        return signal
    except Exception as e:
        print(f"Error creating signal record: {e}")
        return None
