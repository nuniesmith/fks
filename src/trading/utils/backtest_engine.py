"""
Backtesting engine for fks trading strategies.
Migrated from src/backtest.py

Simulates trading strategies on historical data with:
- Multi-symbol portfolio management
- Transaction fees
- Risk metrics (Sharpe, Sortino, Calmar)
- Drawdown analysis
- Trade logging
"""

import pandas as pd
import numpy as np
import talib
from datetime import timedelta
from typing import Dict, List, Tuple
from decimal import Decimal


def run_backtest(
    df_prices: Dict[str, pd.DataFrame],
    M: int,
    atr_period: int = 14,
    sl_multiplier: float = 2.0,
    tp_multiplier: float = 3.0,
    symbols_config: Dict = None,
    fee_rate: float = 0.001
) -> Tuple[Dict, pd.Series, pd.Series, List[Dict]]:
    """
    Run backtest on historical data
    
    Args:
        df_prices: Dictionary of symbol -> DataFrame with OHLCV data
        M: Moving average period for signal generation
        atr_period: ATR period for volatility calculation
        sl_multiplier: Stop-loss multiplier (ATR)
        tp_multiplier: Take-profit multiplier (ATR)
        symbols_config: Configuration dict with 'SYMBOLS', 'MAINS', 'ALTS'
        fee_rate: Transaction fee rate (default 0.1%)
    
    Returns:
        Tuple of (metrics, returns, cumulative_returns, trades)
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
    
    # Combine into multi-symbol DataFrames
    closes = pd.DataFrame({
        sym.split('USDT')[0]: df_prices[sym]['close']
        for sym in SYMBOLS if sym in df_prices
    })
    highs = pd.DataFrame({
        sym.split('USDT')[0]: df_prices[sym]['high']
        for sym in SYMBOLS if sym in df_prices
    })
    lows = pd.DataFrame({
        sym.split('USDT')[0]: df_prices[sym]['low']
        for sym in SYMBOLS if sym in df_prices
    })
    
    if closes.empty:
        return create_empty_backtest_result()
    
    # Normalize and create equal-weighted index
    norm_closes = closes / closes.iloc[0]
    index_price = norm_closes.mean(axis=1)
    
    # Calculate indicators with TA-Lib
    sma = talib.SMA(index_price, timeperiod=M)
    
    # Calculate ATR for each symbol
    atrs = {}
    for sym in closes.columns:
        try:
            atrs[sym] = talib.ATR(highs[sym], lows[sym], closes[sym], timeperiod=atr_period)
        except Exception as e:
            print(f"Error calculating ATR for {sym}: {e}")
            atrs[sym] = pd.Series([0] * len(closes), index=closes.index)
    
    # Generate signals: 1 if index > SMA, else 0
    signal = (index_price > sma).astype(int)
    
    # Initialize backtest simulation
    capital = 1.0  # Start with 1.0 (100%) for percentage returns
    position = 0  # 0: cash, 1: holding assets
    holdings = {sym: 0.0 for sym in closes.columns}  # units held
    equity = [capital]
    trades = []
    daily_returns = []
    
    # Allocation strategy: 50% to mains, 50% to alts
    main_symbols = [sym.split('USDT')[0] for sym in MAINS]
    alt_symbols = [sym.split('USDT')[0] for sym in ALTS]
    
    main_alloc = 0.5 / len(main_symbols) if main_symbols else 0
    alt_alloc = 0.5 / len(alt_symbols) if alt_symbols else 0
    
    # Append equity for the first bar (index 0) - no trading yet, just capital
    equity.append(capital)
    daily_returns.append(0.0)  # No return on first day
    
    # Run simulation
    for i in range(1, len(signal)):
        date = closes.index[i]
        prev_signal = signal.iloc[i-1]
        curr_signal = signal.iloc[i]
        
        # Entry signal: transition from 0 to 1
        if prev_signal == 0 and curr_signal == 1:
            entry_capital = capital * (1 - fee_rate)  # Deduct fees
            
            # Buy main fkss
            for sym in main_symbols:
                if sym in closes.columns:
                    price = closes[sym].iloc[i]
                    if price > 0:
                        holdings[sym] = (entry_capital * main_alloc) / price
            
            # Buy alt fkss
            for sym in alt_symbols:
                if sym in closes.columns:
                    price = closes[sym].iloc[i]
                    if price > 0:
                        holdings[sym] = (entry_capital * alt_alloc) / price
            
            capital = 0.0
            position = 1
            
            # Calculate average ATR and price for SL/TP
            valid_atrs = [atrs[sym].iloc[i] for sym in closes.columns if sym in atrs and atrs[sym].iloc[i] > 0]
            valid_prices = [closes[sym].iloc[i] for sym in closes.columns if closes[sym].iloc[i] > 0]
            
            avg_atr = sum(valid_atrs) / len(valid_atrs) if valid_atrs else 0
            avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0
            
            sl = avg_price - sl_multiplier * avg_atr
            tp = avg_price + tp_multiplier * avg_atr
            
            trades.append({
                'date': date,
                'action': 'ENTER',
                'symbols': SYMBOLS,
                'prices': [closes[sym].iloc[i] for sym in closes.columns],
                'sl': sl,
                'tp': tp,
                'capital_deployed': entry_capital
            })
        
        # Exit signal: transition from 1 to 0
        elif prev_signal == 1 and curr_signal == 0:
            exit_capital = 0.0
            
            # Sell all holdings
            for sym in closes.columns:
                if holdings[sym] > 0:
                    price = closes[sym].iloc[i]
                    exit_capital += holdings[sym] * price
                    holdings[sym] = 0.0
            
            capital = exit_capital * (1 - fee_rate)  # Deduct fees
            position = 0
            
            trades.append({
                'date': date,
                'action': 'EXIT',
                'symbols': SYMBOLS,
                'prices': [closes[sym].iloc[i] for sym in closes.columns],
                'capital_received': capital
            })
        
        # Calculate daily equity
        if position == 1:
            current_value = sum(
                holdings[sym] * closes[sym].iloc[i]
                for sym in closes.columns
                if holdings[sym] > 0
            )
        else:
            current_value = capital
        
        # Calculate daily return
        daily_ret = (current_value / equity[-1]) - 1 if equity[-1] > 0 else 0
        daily_returns.append(daily_ret)
        equity.append(current_value)
    
    # Create equity series with correct index
    equity_index = [closes.index[0] - timedelta(days=1)] + list(closes.index)
    cum_ret = pd.Series(equity, index=equity_index)[1:]
    cum_ret = (cum_ret / cum_ret.iloc[0]).fillna(1)
    
    # Calculate metrics
    metrics = calculate_metrics(daily_returns, cum_ret, trades, closes.index)
    
    # Convert returns to Series (should match closes.index since we now have returns for all bars)
    returns = pd.Series(daily_returns, index=closes.index)
    
    return metrics, returns, cum_ret, trades


def calculate_metrics(
    daily_returns: List[float],
    cum_ret: pd.Series,
    trades: List[Dict],
    index: pd.DatetimeIndex
) -> Dict:
    """
    Calculate performance metrics
    
    Args:
        daily_returns: List of daily returns
        cum_ret: Cumulative return series
        trades: List of trade dictionaries
        index: DateTime index
    
    Returns:
        Dictionary of performance metrics
    """
    returns = pd.Series(daily_returns, index=index)
    
    # Basic metrics
    total_return = cum_ret.iloc[-1] - 1 if not cum_ret.empty else 0
    num_days = len(returns)
    
    # Annualized return
    if num_days > 0:
        annualized_return = (1 + total_return) ** (365 / num_days) - 1
    else:
        annualized_return = 0
    
    # Sharpe ratio
    if returns.std() != 0:
        sharpe = returns.mean() / returns.std() * (365 ** 0.5)
    else:
        sharpe = 0
    
    # Sortino ratio
    downside_returns = returns[returns < 0]
    downside_dev = downside_returns.std() if len(downside_returns) > 0 else 0
    
    if downside_dev != 0:
        sortino = returns.mean() / downside_dev * (365 ** 0.5)
    else:
        sortino = 0
    
    # Drawdown metrics
    cum_max = cum_ret.cummax()
    drawdown = (cum_ret - cum_max) / cum_max
    max_dd = drawdown.min()
    
    # Calmar ratio
    if max_dd != 0:
        calmar = annualized_return / abs(max_dd)
    else:
        calmar = 0
    
    # Win rate
    winning_days = len(returns[returns > 0])
    losing_days = len(returns[returns < 0])
    win_rate = winning_days / len(returns) if len(returns) > 0 else 0
    
    # Number of trades (count entry-exit pairs)
    num_trades = len([t for t in trades if t['action'] == 'ENTER'])
    
    return {
        'Sharpe': round(sharpe, 2),
        'Sortino': round(sortino, 2),
        'Max Drawdown': round(max_dd, 4),
        'Calmar': round(calmar, 2),
        'Total Return': round(total_return, 4),
        'Annualized Return': round(annualized_return, 4),
        'Win Rate': round(win_rate, 4),
        'Trades': num_trades,
        'Days': num_days
    }


def create_empty_backtest_result() -> Tuple[Dict, pd.Series, pd.Series, List[Dict]]:
    """
    Create empty backtest result for error cases
    
    Returns:
        Empty metrics, returns, cumulative returns, and trades
    """
    metrics = {
        'Sharpe': 0,
        'Sortino': 0,
        'Max Drawdown': 0,
        'Calmar': 0,
        'Total Return': 0,
        'Annualized Return': 0,
        'Win Rate': 0,
        'Trades': 0,
        'Days': 0
    }
    
    returns = pd.Series([])
    cum_ret = pd.Series([1.0])
    trades = []
    
    return metrics, returns, cum_ret, trades


def analyze_trade_distribution(trades: List[Dict]) -> Dict:
    """
    Analyze trade distribution and patterns
    
    Args:
        trades: List of trade dictionaries
    
    Returns:
        Dictionary with trade analysis
    """
    if not trades:
        return {'total_trades': 0}
    
    entries = [t for t in trades if t['action'] == 'ENTER']
    exits = [t for t in trades if t['action'] == 'EXIT']
    
    # Calculate hold times
    hold_times = []
    for i in range(min(len(entries), len(exits))):
        entry_date = entries[i]['date']
        exit_date = exits[i]['date']
        hold_time = (exit_date - entry_date).days
        hold_times.append(hold_time)
    
    return {
        'total_trades': len(entries),
        'avg_hold_time_days': np.mean(hold_times) if hold_times else 0,
        'min_hold_time_days': min(hold_times) if hold_times else 0,
        'max_hold_time_days': max(hold_times) if hold_times else 0,
    }
