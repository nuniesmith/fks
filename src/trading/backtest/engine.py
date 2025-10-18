# src/trading/backtest/engine.py
"""
Backtesting engine for trading strategies.

This module provides backtesting functionality with:
- Multi-symbol support
- ATR-based stop loss and take profit
- Fee simulation
- Advanced performance metrics (Sharpe, Sortino, Calmar, etc.)
"""

from datetime import timedelta

import pandas as pd
import talib

from framework.config.constants import ALTS, FEE_RATE, MAINS, SYMBOLS


def run_backtest(df_prices, M, atr_period=14, sl_multiplier=2, tp_multiplier=3):
    """
    Run backtest on historical price data.

    Args:
        df_prices: Dictionary of DataFrames with OHLCV data for each symbol
        M: Moving average period for signal generation
        atr_period: ATR calculation period
        sl_multiplier: Stop loss multiplier (ATR)
        tp_multiplier: Take profit multiplier (ATR)

    Returns:
        tuple: (metrics, returns, cum_ret, trades)
            - metrics: Dict of performance metrics
            - returns: Series of daily returns
            - cum_ret: Series of cumulative returns
            - trades: List of trade dictionaries
    """
    # Combine into multi-symbol DF
    closes = pd.DataFrame(
        {sym.split("USDT")[0]: df_prices[sym]["close"] for sym in SYMBOLS}
    )
    highs = pd.DataFrame(
        {sym.split("USDT")[0]: df_prices[sym]["high"] for sym in SYMBOLS}
    )
    lows = pd.DataFrame(
        {sym.split("USDT")[0]: df_prices[sym]["low"] for sym in SYMBOLS}
    )

    # Normalize and create index (equal weight all, including mains and alts)
    norm_closes = closes / closes.iloc[0]
    index_price = norm_closes.mean(axis=1)

    # Indicators with TA-lib
    sma = talib.SMA(index_price, timeperiod=M)
    atrs = {
        sym: talib.ATR(highs[sym], lows[sym], closes[sym], timeperiod=atr_period)
        for sym in closes.columns
    }

    # Signal: 1 if index > SMA, else 0
    signal = (index_price > sma).astype(int)

    # Simulate trades with fees, no daily rebalance
    # When holding, allocate 50% to mains (25% each BTC/ETH), 50% to alts (equal ~16.67% each)
    capital = 1.0
    position = 0  # 0: cash, 1: holding
    holdings = dict.fromkeys(closes.columns, 0.0)  # units held
    equity = [capital]
    trades = []
    daily_returns = []

    main_alloc = 0.5 / len(MAINS)  # e.g., 0.25 each
    alt_alloc = 0.5 / len(ALTS)  # e.g., ~0.1667 each

    for i in range(1, len(signal)):
        date = closes.index[i]
        prev_signal = signal.iloc[i - 1]
        curr_signal = signal.iloc[i]

        if prev_signal == 0 and curr_signal == 1:  # Enter
            entry_capital = capital * (1 - FEE_RATE)
            for sym in MAINS:
                base_sym = sym.split("USDT")[0]
                price = closes[base_sym].iloc[i]
                holdings[base_sym] = (entry_capital * main_alloc) / price
            for sym in ALTS:
                base_sym = sym.split("USDT")[0]
                price = closes[base_sym].iloc[i]
                holdings[base_sym] = (entry_capital * alt_alloc) / price
            capital = 0.0
            position = 1
            # Use average ATR for SL/TP example
            avg_atr = sum(atrs[base_sym].iloc[i] for base_sym in closes.columns) / len(
                closes.columns
            )
            avg_price = sum(
                closes[base_sym].iloc[i] for base_sym in closes.columns
            ) / len(closes.columns)
            sl = avg_price - sl_multiplier * avg_atr
            tp = avg_price + tp_multiplier * avg_atr
            trades.append(
                {
                    "date": date,
                    "action": "ENTER",
                    "symbols": SYMBOLS,
                    "prices": [closes[base_sym].iloc[i] for base_sym in closes.columns],
                    "sl": sl,
                    "tp": tp,
                }
            )

        elif prev_signal == 1 and curr_signal == 0:  # Exit
            exit_capital = 0.0
            for base_sym in closes.columns:
                price = closes[base_sym].iloc[i]
                exit_capital += holdings[base_sym] * price
                holdings[base_sym] = 0.0
            capital = exit_capital * (1 - FEE_RATE)
            position = 0
            trades.append(
                {
                    "date": date,
                    "action": "EXIT",
                    "symbols": SYMBOLS,
                    "prices": [closes[base_sym].iloc[i] for base_sym in closes.columns],
                }
            )

        # Daily equity
        if position == 1:
            current_value = sum(
                holdings[base_sym] * closes[base_sym].iloc[i]
                for base_sym in closes.columns
            )
        else:
            current_value = capital
        daily_ret = (current_value / equity[-1]) - 1 if equity[-1] > 0 else 0
        daily_returns.append(daily_ret)
        equity.append(current_value)

    # Create equity series with correct index
    # equity has len(closes) + 1 elements (initial + one per day)
    equity_index = [closes.index[0] - timedelta(days=1)] + list(closes.index)
    cum_ret = pd.Series(equity, index=equity_index)[1:]
    cum_ret = (cum_ret / cum_ret.iloc[0]).fillna(1)

    # Advanced metrics
    returns = pd.Series(daily_returns, index=closes.index[1:])
    total_return = equity[-1] - 1
    annualized_return = (
        (1 + total_return) ** (365 / len(returns)) - 1 if len(returns) > 0 else 0
    )
    sharpe = returns.mean() / returns.std() * (365**0.5) if returns.std() != 0 else 0
    downside_dev = returns[returns < 0].std() if len(returns[returns < 0]) > 0 else 0
    sortino = returns.mean() / downside_dev * (365**0.5) if downside_dev != 0 else 0
    cum_max = cum_ret.cummax()
    drawdown = (cum_ret - cum_max) / cum_max
    max_dd = drawdown.min()
    calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0

    metrics = {
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max Drawdown": max_dd,
        "Calmar": calmar,
        "Total Return": total_return,
        "Annualized Return": annualized_return,
        "Trades": len(trades) // 2,  # Enter-exit pairs
    }

    return metrics, returns, cum_ret, trades
