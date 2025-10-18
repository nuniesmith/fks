# src/signals.py

import pandas as pd
import talib

from framework.config.constants import SYMBOLS, MAINS, ALTS, RISK_PER_TRADE
from data import get_current_price

def get_current_signal(df_prices, best_params, account_size, risk_per_trade=RISK_PER_TRADE):
    closes = pd.DataFrame({sym.split('USDT')[0]: df_prices[sym]['close'] for sym in SYMBOLS})
    current_prices = {sym: get_current_price(sym) for sym in SYMBOLS}
    
    norm_closes = closes / closes.iloc[0]
    index_price = norm_closes.mean(axis=1)
    last_prices = closes.iloc[-1]
    current_index_approx = index_price.iloc[-1] * (sum(current_prices[sym] / last_prices[sym.split('USDT')[0]] for sym in SYMBOLS) / len(SYMBOLS))
    
    sma = talib.SMA(index_price, timeperiod=best_params['M'])
    current_sma = sma.iloc[-1]
    
    signal = 1 if current_index_approx > current_sma else 0
    
    if signal == 1:
        # Risk sizing
        atrs = {sym.split('USDT')[0]: talib.ATR(df_prices[sym]['high'], df_prices[sym]['low'], df_prices[sym]['close'], timeperiod=best_params['atr_period']).iloc[-1] for sym in SYMBOLS}
        avg_atr = sum(atrs.values()) / len(atrs)
        risk_amount = account_size * risk_per_trade
        position_size_usdt = risk_amount * len(SYMBOLS) / best_params['sl_multiplier']  # Approximate
        main_alloc = 0.5 / len(MAINS)
        alt_alloc = 0.5 / len(ALTS)
        
        suggestions = []
        for sym in MAINS + ALTS:
            base_sym = sym.split('USDT')[0]
            price = current_prices[sym]
            atr = atrs[base_sym]
            sl = price - best_params['sl_multiplier'] * atr
            tp = price + best_params['tp_multiplier'] * atr
            alloc = main_alloc if sym in MAINS else alt_alloc
            quantity = (position_size_usdt * alloc) / price
            suggestions.append({
                'symbol': sym,
                'action': 'BUY LIMIT',
                'price': price,  # Or set limit price
                'quantity': quantity,
                'sl': sl,
                'tp': tp
            })
        return signal, suggestions
    else:
        return signal, [{'action': 'HOLD USDT or SELL if holding'}]