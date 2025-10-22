# src/trading/signals/generator.py
"""
Trading signal generation module.

Generates buy/sell signals based on technical indicators and market conditions.
Enhanced with RAG-powered AI recommendations for optimal signal generation.
"""

import pandas as pd
import talib
from typing import Optional, Dict, Any, Tuple, List
from data.api.binance import get_current_price

from framework.config.constants import ALTS, MAINS, RISK_PER_TRADE, SYMBOLS

# RAG Intelligence imports - gracefully degrade if not available
try:
    from web.rag.orchestrator import IntelligenceOrchestrator
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("⚠ RAG system not available - using technical signals only")


def get_current_signal(
    df_prices: Dict[str, pd.DataFrame],
    best_params: Dict[str, Any],
    account_size: float,
    risk_per_trade: float = RISK_PER_TRADE,
    use_rag: bool = True,
    available_cash: Optional[float] = None,
    current_positions: Optional[Dict[str, Any]] = None
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Generate current trading signal based on price data and strategy parameters.
    
    Enhanced with RAG-powered AI recommendations that combine technical analysis
    with historical performance insights for optimal signal generation.

    Args:
        df_prices: Dictionary of DataFrames with OHLCV data for each symbol
        best_params: Dictionary of optimized strategy parameters
        account_size: Total account balance
        risk_per_trade: Risk percentage per trade (default from config)
        use_rag: Whether to use RAG for enhanced signals (default: True)
        available_cash: Available cash for trading (defaults to account_size)
        current_positions: Dict of current positions {symbol: {quantity, entry_price, ...}}

    Returns:
        tuple: (signal, suggestions)
            - signal: 1 for BUY, 0 for HOLD/SELL
            - suggestions: List of trade suggestions with entry, SL, TP, RAG insights
    """
    # Set defaults
    if available_cash is None:
        available_cash = account_size
    if current_positions is None:
        current_positions = {}
    
    # Calculate technical indicators for index
    closes = pd.DataFrame(
        {sym.split("USDT")[0]: df_prices[sym]["close"] for sym in SYMBOLS}
    )
    current_prices = {sym: get_current_price(sym) for sym in SYMBOLS}

    norm_closes = closes / closes.iloc[0]
    index_price = norm_closes.mean(axis=1)
    last_prices = closes.iloc[-1]
    current_index_approx = index_price.iloc[-1] * (
        sum(current_prices[sym] / last_prices[sym.split("USDT")[0]] for sym in SYMBOLS)
        / len(SYMBOLS)
    )

    sma = talib.SMA(index_price, timeperiod=best_params["M"])
    current_sma = sma.iloc[-1]

    # Technical signal: BUY if index above SMA
    technical_signal = 1 if current_index_approx > current_sma else 0
    
    # Calculate technical indicators for each symbol (for RAG context)
    symbol_indicators = {}
    for sym in SYMBOLS:
        df = df_prices[sym]
        close_prices = df["close"]
        
        # Calculate RSI
        rsi = talib.RSI(close_prices, timeperiod=14)
        # Calculate MACD
        macd, signal_line, hist = talib.MACD(close_prices)
        # Calculate Bollinger Bands
        upper, middle, lower = talib.BBANDS(close_prices)
        
        symbol_indicators[sym] = {
            'rsi': rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None,
            'macd': macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else None,
            'macd_signal': signal_line.iloc[-1] if not pd.isna(signal_line.iloc[-1]) else None,
            'bb_upper': upper.iloc[-1] if not pd.isna(upper.iloc[-1]) else None,
            'bb_middle': middle.iloc[-1] if not pd.isna(middle.iloc[-1]) else None,
            'bb_lower': lower.iloc[-1] if not pd.isna(lower.iloc[-1]) else None,
            'current_price': current_prices[sym]
        }
    
    # Get RAG-enhanced recommendations if enabled and available
    rag_recommendations = {}
    if use_rag and RAG_AVAILABLE and technical_signal == 1:
        try:
            rag_recommendations = _get_rag_recommendations(
                symbols=SYMBOLS,
                account_size=account_size,
                available_cash=available_cash,
                current_positions=current_positions,
                symbol_indicators=symbol_indicators
            )
        except Exception as e:
            print(f"⚠ RAG recommendations failed: {e}. Using technical signals only.")
            rag_recommendations = {}

    # Generate final signal based on technical + RAG
    signal = technical_signal

    if signal == 1:
        # Risk sizing
        atrs = {
            sym.split("USDT")[0]: talib.ATR(
                df_prices[sym]["high"],
                df_prices[sym]["low"],
                df_prices[sym]["close"],
                timeperiod=best_params["atr_period"],
            ).iloc[-1]
            for sym in SYMBOLS
        }
        sum(atrs.values()) / len(atrs)
        risk_amount = account_size * risk_per_trade
        position_size_usdt = (
            risk_amount * len(SYMBOLS) / best_params["sl_multiplier"]
        )  # Approximate
        main_alloc = 0.5 / len(MAINS)
        alt_alloc = 0.5 / len(ALTS)

        suggestions = []
        for sym in MAINS + ALTS:
            base_sym = sym.split("USDT")[0]
            price = current_prices[sym]
            atr = atrs[base_sym]
            sl = price - best_params["sl_multiplier"] * atr
            tp = price + best_params["tp_multiplier"] * atr
            alloc = main_alloc if sym in MAINS else alt_alloc
            quantity = (position_size_usdt * alloc) / price
            
            # Merge technical suggestion with RAG recommendation
            suggestion = {
                "symbol": sym,
                "action": "BUY LIMIT",
                "price": price,  # Or set limit price
                "quantity": quantity,
                "sl": sl,
                "tp": tp,
            }
            
            # Add RAG insights if available
            if sym in rag_recommendations:
                rag_rec = rag_recommendations[sym]
                suggestion.update({
                    "rag_action": rag_rec.get('action', 'HOLD'),
                    "rag_confidence": rag_rec.get('confidence', 0),
                    "rag_reasoning": rag_rec.get('reasoning', ''),
                    "rag_risk_assessment": rag_rec.get('risk_assessment', 'medium'),
                    "rag_enhanced": True
                })
                
                # Adjust position size based on RAG confidence if high
                if rag_rec.get('confidence', 0) >= 0.8 and rag_rec.get('action') == 'BUY':
                    # Increase position size by up to 20% for high confidence signals
                    confidence_boost = (rag_rec['confidence'] - 0.8) / 0.2  # 0 to 1
                    suggestion['quantity'] = quantity * (1 + 0.2 * confidence_boost)
                    suggestion['rag_boosted'] = True
            else:
                suggestion['rag_enhanced'] = False
            
            suggestions.append(suggestion)
            
        return signal, suggestions
    else:
        return signal, [{"action": "HOLD USDT or SELL if holding"}]


def _get_rag_recommendations(
    symbols: List[str],
    account_size: float,
    available_cash: float,
    current_positions: Dict[str, Any],
    symbol_indicators: Dict[str, Dict[str, float]]
) -> Dict[str, Dict[str, Any]]:
    """
    Get RAG-powered trading recommendations for multiple symbols.
    
    Args:
        symbols: List of trading symbols to analyze
        account_size: Total account balance
        available_cash: Available cash for trading
        current_positions: Current positions dict
        symbol_indicators: Technical indicators for each symbol
        
    Returns:
        Dict mapping symbol to RAG recommendation
    """
    if not RAG_AVAILABLE:
        return {}
    
    orchestrator = IntelligenceOrchestrator(use_local=True)
    recommendations = {}
    
    for symbol in symbols:
        try:
            # Build context with technical indicators
            indicators = symbol_indicators.get(symbol, {})
            context_parts = []
            
            if indicators.get('rsi') is not None:
                context_parts.append(f"RSI={indicators['rsi']:.2f}")
            if indicators.get('macd') is not None:
                context_parts.append(f"MACD={indicators['macd']:.2f}")
            if indicators.get('bb_upper') is not None:
                current = indicators.get('current_price', 0)
                bb_upper = indicators['bb_upper']
                bb_lower = indicators.get('bb_lower', 0)
                if bb_upper > 0:
                    bb_position = ((current - bb_lower) / (bb_upper - bb_lower)) * 100
                    context_parts.append(f"BB_position={bb_position:.1f}%")
            
            context = ", ".join(context_parts) if context_parts else "current market conditions"
            
            # Get RAG recommendation
            rec = orchestrator.get_trading_recommendation(
                symbol=symbol,
                account_balance=account_size,
                available_cash=available_cash,
                context=context,
                current_positions=current_positions
            )
            
            recommendations[symbol] = rec
            
        except Exception as e:
            print(f"⚠ RAG recommendation failed for {symbol}: {e}")
            continue
    
    return recommendations

