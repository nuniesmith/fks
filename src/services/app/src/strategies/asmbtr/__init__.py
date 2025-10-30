"""ASMBTR (Adaptive State Model on Binary Tree Representation) Strategy.

This module implements a non-AI probabilistic baseline trading strategy
that encodes price movements as binary sequences and uses state-based
prediction for trading decisions.

Phase: AI Enhancement Plan - Phase 2
Target: Calmar ratio >0.3 on backtests
"""

from .btr import BTREncoder, BTRState
from .encoder import StateEncoder, MultiSymbolEncoder
from .predictor import PredictionTable, StatePrediction
from .strategy import (
    ASMBTRStrategy,
    StrategyConfig,
    StrategyMetrics,
    TradingSignal,
    SignalType,
    Position
)
from .backtest import (
    HistoricalBacktest,
    BacktestMetrics,
    Trade,
    EquityPoint
)
from .optimize import ASMBTROptimizer, generate_synthetic_data

__all__ = [
    # BTR encoding
    'BTREncoder',
    'BTRState',
    
    # State encoding
    'StateEncoder',
    'MultiSymbolEncoder',
    
    # Prediction
    'PredictionTable',
    'StatePrediction',
    
    # Strategy
    'ASMBTRStrategy',
    'StrategyConfig',
    'StrategyMetrics',
    'TradingSignal',
    'SignalType',
    'Position',
    
    # Backtesting
    'HistoricalBacktest',
    'BacktestMetrics',
    'Trade',
    'EquityPoint',
    
    # Optimization
    'ASMBTROptimizer',
    'generate_synthetic_data',
]
