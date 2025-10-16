"""
Signal generation utilities for fks trading.
Migrated from src/signals.py

Generates trading signals based on technical indicators:
- Moving averages (SMA)
- ATR (Average True Range) for volatility
- Risk management with stop-loss and take-profit
"""

import pandas as pd
import talib
from typing import Dict, List, Tuple
from decimal import Decimal

from .data_fetcher import get_current_price


def get_current_signal(
    df_prices: Dict[str, pd.DataFrame],
    best_params: Dict,
    account_size: float,
    symbols_config: Dict = None,
    risk_per_trade: float = 0.01
) -> Tuple[int, List[Dict]]:
    """
    Generate current trading signal and position suggestions
    
    Args:
        df_prices: Dictionary of symbol -> DataFrame with OHLCV data
        best_params: Dictionary with optimized parameters (M, atr_period, sl_multiplier, tp_multiplier)
        account_size: Total account size in USDT
        symbols_config: Configuration dict with 'MAINS' and 'ALTS' lists
        risk_per_trade: Risk percentage per trade (default 0.01 = 1%)
    
    Returns:
        Tuple of (signal, suggestions)
        - signal: 1 for HOLD ASSETS, 0 for HOLD USDT
        - suggestions: List of trade suggestions with entry, SL, TP
    """
    # Default configuration
    if symbols_config is None:
        from django.conf import settings
        SYMBOLS = getattr(settings, 'TRADING_SYMBOLS', ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT', 'SUIUSDT'])
        MAINS = getattr(settings, 'TRADING_MAINS', ['BTCUSDT', 'ETHUSDT'])
        ALTS = getattr(settings, 'TRADING_ALTS', ['SOLUSDT', 'AVAXUSDT', 'SUIUSDT'])
    else:
        SYMBOLS = symbols_config.get('SYMBOLS', [])
        MAINS = symbols_config.get('MAINS', [])
        ALTS = symbols_config.get('ALTS', [])
    
    # Extract close prices for all symbols
    closes = pd.DataFrame({
        sym.split('USDT')[0]: df_prices[sym]['close'] 
        for sym in SYMBOLS if sym in df_prices
    })
    
    if closes.empty:
        return 0, [{'action': 'ERROR: No price data available'}]
    
    # Get current prices for all symbols
    current_prices = {}
    for sym in SYMBOLS:
        try:
            current_prices[sym] = get_current_price(sym)
        except Exception as e:
            print(f"Error getting current price for {sym}: {e}")
            # Use last available price from historical data
            if sym in df_prices and not df_prices[sym].empty:
                current_prices[sym] = df_prices[sym]['close'].iloc[-1]
            else:
                current_prices[sym] = 0.0
    
    # Normalize closes to create equal-weighted index
    norm_closes = closes / closes.iloc[0]
    index_price = norm_closes.mean(axis=1)
    
    # Calculate current index value approximation
    last_prices = closes.iloc[-1]
    price_ratios = []
    for sym in SYMBOLS:
        base_sym = sym.split('USDT')[0]
        if base_sym in last_prices and last_prices[base_sym] > 0:
            ratio = current_prices[sym] / last_prices[base_sym]
            price_ratios.append(ratio)
    
    if not price_ratios:
        return 0, [{'action': 'ERROR: Unable to calculate price ratios'}]
    
    avg_ratio = sum(price_ratios) / len(price_ratios)
    current_index_approx = index_price.iloc[-1] * avg_ratio
    
    # Calculate SMA with specified period
    M = best_params.get('M', 50)
    sma = talib.SMA(index_price, timeperiod=M)
    current_sma = sma.iloc[-1]
    
    # Generate signal: 1 if index > SMA (bullish), 0 otherwise (bearish)
    signal = 1 if current_index_approx > current_sma else 0
    
    if signal == 1:
        # BULLISH: Generate buy suggestions with risk management
        suggestions = generate_buy_suggestions(
            df_prices=df_prices,
            current_prices=current_prices,
            best_params=best_params,
            account_size=account_size,
            risk_per_trade=risk_per_trade,
            mains=MAINS,
            alts=ALTS
        )
        return signal, suggestions
    else:
        # BEARISH: Suggest holding USDT or selling
        return signal, [{'action': 'HOLD USDT or SELL if holding assets'}]


def generate_buy_suggestions(
    df_prices: Dict[str, pd.DataFrame],
    current_prices: Dict[str, float],
    best_params: Dict,
    account_size: float,
    risk_per_trade: float,
    mains: List[str],
    alts: List[str]
) -> List[Dict]:
    """
    Generate buy suggestions with position sizing and risk management
    
    Args:
        df_prices: Historical price data
        current_prices: Current prices for all symbols
        best_params: Optimized parameters
        account_size: Total account size
        risk_per_trade: Risk percentage
        mains: List of main fks symbols
        alts: List of alt fks symbols
    
    Returns:
        List of trade suggestions
    """
    atr_period = best_params.get('atr_period', 14)
    sl_multiplier = best_params.get('sl_multiplier', 2.0)
    tp_multiplier = best_params.get('tp_multiplier', 3.0)
    
    # Calculate ATR for each symbol
    atrs = {}
    for sym in list(mains) + list(alts):
        base_sym = sym.split('USDT')[0]
        if sym in df_prices and not df_prices[sym].empty:
            try:
                atr = talib.ATR(
                    df_prices[sym]['high'],
                    df_prices[sym]['low'],
                    df_prices[sym]['close'],
                    timeperiod=atr_period
                )
                atrs[base_sym] = atr.iloc[-1]
            except Exception as e:
                print(f"Error calculating ATR for {sym}: {e}")
                # Use a default percentage of current price
                if sym in current_prices and current_prices[sym] > 0:
                    atrs[base_sym] = current_prices[sym] * 0.02  # 2% default
                else:
                    atrs[base_sym] = 0
        else:
            atrs[base_sym] = 0
    
    # Calculate average ATR for risk calculation
    valid_atrs = [v for v in atrs.values() if v > 0]
    avg_atr = sum(valid_atrs) / len(valid_atrs) if valid_atrs else 0
    
    # Calculate total position size based on risk
    num_symbols = len(mains) + len(alts)
    risk_amount = account_size * risk_per_trade
    
    # Estimate position size (simplified)
    if sl_multiplier > 0 and avg_atr > 0:
        position_size_usdt = risk_amount * num_symbols / sl_multiplier
    else:
        position_size_usdt = account_size  # Fallback to full account
    
    # Allocations: 50% to mains, 50% to alts
    main_alloc = 0.5 / len(mains) if mains else 0
    alt_alloc = 0.5 / len(alts) if alts else 0
    
    suggestions = []
    
    # Generate suggestions for main fkss
    for sym in mains:
        suggestion = generate_trade_suggestion(
            symbol=sym,
            price=current_prices.get(sym, 0),
            atr=atrs.get(sym.split('USDT')[0], 0),
            allocation=main_alloc,
            position_size_usdt=position_size_usdt,
            sl_multiplier=sl_multiplier,
            tp_multiplier=tp_multiplier
        )
        if suggestion:
            suggestions.append(suggestion)
    
    # Generate suggestions for alt fkss
    for sym in alts:
        suggestion = generate_trade_suggestion(
            symbol=sym,
            price=current_prices.get(sym, 0),
            atr=atrs.get(sym.split('USDT')[0], 0),
            allocation=alt_alloc,
            position_size_usdt=position_size_usdt,
            sl_multiplier=sl_multiplier,
            tp_multiplier=tp_multiplier
        )
        if suggestion:
            suggestions.append(suggestion)
    
    return suggestions


def generate_trade_suggestion(
    symbol: str,
    price: float,
    atr: float,
    allocation: float,
    position_size_usdt: float,
    sl_multiplier: float,
    tp_multiplier: float
) -> Dict:
    """
    Generate a single trade suggestion
    
    Args:
        symbol: Trading pair symbol
        price: Current price
        atr: Average True Range
        allocation: Allocation percentage
        position_size_usdt: Total position size in USDT
        sl_multiplier: Stop-loss multiplier
        tp_multiplier: Take-profit multiplier
    
    Returns:
        Trade suggestion dictionary
    """
    if price <= 0:
        return None
    
    # Calculate stop-loss and take-profit
    sl = price - (sl_multiplier * atr) if atr > 0 else price * 0.95  # 5% default SL
    tp = price + (tp_multiplier * atr) if atr > 0 else price * 1.15  # 15% default TP
    
    # Calculate quantity based on allocation
    allocated_usdt = position_size_usdt * allocation
    quantity = allocated_usdt / price
    
    return {
        'symbol': symbol,
        'action': 'BUY LIMIT',
        'price': round(price, 8),
        'quantity': round(quantity, 8),
        'sl': round(max(sl, 0), 8),  # Ensure SL is not negative
        'tp': round(tp, 8),
        'allocated_usdt': round(allocated_usdt, 2)
    }


def calculate_position_pnl(
    entry_price: float,
    current_price: float,
    quantity: float,
    side: str = 'long'
) -> float:
    """
    Calculate position P&L
    
    Args:
        entry_price: Entry price
        current_price: Current price
        quantity: Position quantity
        side: 'long' or 'short'
    
    Returns:
        P&L in USDT
    """
    if side.lower() == 'long':
        pnl = (current_price - entry_price) * quantity
    else:  # short
        pnl = (entry_price - current_price) * quantity
    
    return pnl


def check_stop_loss_take_profit(
    current_price: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    side: str = 'long'
) -> str:
    """
    Check if stop-loss or take-profit has been hit
    
    Args:
        current_price: Current price
        entry_price: Entry price
        stop_loss: Stop-loss price
        take_profit: Take-profit price
        side: 'long' or 'short'
    
    Returns:
        'SL_HIT', 'TP_HIT', or 'NONE'
    """
    if side.lower() == 'long':
        if current_price <= stop_loss:
            return 'SL_HIT'
        elif current_price >= take_profit:
            return 'TP_HIT'
    else:  # short
        if current_price >= stop_loss:
            return 'SL_HIT'
        elif current_price <= take_profit:
            return 'TP_HIT'
    
    return 'NONE'
