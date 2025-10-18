#!/usr/bin/env python3
"""
Example script demonstrating strategy optimization with Optuna and RAG integration.

This script shows how to:
1. Use the enhanced Binance adapter with rate limiting and circuit breaker
2. Optimize trading strategy parameters using Optuna
3. Leverage RAG for intelligent parameter suggestions
4. Run backtests with optimized performance

Usage:
    python examples/optimize_strategy.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

# Import our enhanced components
from data.adapters.binance import BinanceAdapter
from trading.optimizer.engine import OptunaOptimizer
from trading.backtest.engine import run_backtest


def fetch_market_data(symbols, days=100):
    """
    Fetch market data using enhanced Binance adapter.
    
    Args:
        symbols: List of trading symbols
        days: Number of days of historical data to fetch
        
    Returns:
        Dictionary of DataFrames with OHLCV data
    """
    logger.info(f"Fetching {days} days of data for {len(symbols)} symbols")
    
    # Initialize adapter with rate limiting and circuit breaker
    adapter = BinanceAdapter()
    
    df_prices = {}
    
    for symbol in symbols:
        try:
            # Calculate time range
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            # Fetch data with rate limiting protection
            result = adapter.fetch(
                symbol=symbol,
                interval="1d",
                limit=days,
                start_time=start_time,
                end_time=end_time
            )
            
            # Convert to DataFrame
            data = result['data']
            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['ts'], unit='s')
            df = df.set_index('datetime')
            df_prices[symbol] = df[['open', 'high', 'low', 'close', 'volume']]
            
            logger.info(f"Fetched {len(df)} bars for {symbol}")
            
            # Show circuit breaker and rate limiter status
            circuit_metrics = adapter.get_circuit_metrics()
            rate_stats = adapter.get_rate_limit_stats()
            logger.debug(f"Circuit state: {circuit_metrics['state']}")
            logger.debug(f"Rate limit: {rate_stats['limit']} req/window")
            
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            
            # Check if circuit breaker is open
            if adapter.circuit_breaker.is_open():
                logger.warning("Circuit breaker is OPEN - API calls are blocked temporarily")
                break
    
    return df_prices


def optimize_strategy(df_prices, n_trials=50, use_rag=False):
    """
    Optimize trading strategy parameters using Optuna.
    
    Args:
        df_prices: Dictionary of DataFrames with OHLCV data
        n_trials: Number of optimization trials
        use_rag: Whether to use RAG for parameter suggestions
        
    Returns:
        Dictionary with optimization results
    """
    logger.info(f"Starting strategy optimization: {n_trials} trials")
    
    # Initialize RAG service if requested
    rag_service = None
    if use_rag:
        try:
            from services.rag_service import RAGService
            rag_service = RAGService(use_local=True)
            logger.info("RAG service initialized for parameter suggestions")
        except Exception as e:
            logger.warning(f"Could not initialize RAG service: {e}")
    
    # Create optimizer
    optimizer = OptunaOptimizer(
        df_prices=df_prices,
        n_trials=n_trials,
        n_jobs=2,  # Use 2 parallel jobs
        rag_service=rag_service
    )
    
    # Run optimization
    results = optimizer.optimize(study_name="strategy_optimization")
    
    logger.info("=" * 60)
    logger.info("OPTIMIZATION RESULTS")
    logger.info("=" * 60)
    logger.info(f"Best Sharpe Ratio: {results['best_value']:.4f}")
    logger.info(f"Best Parameters:")
    for param, value in results['best_params'].items():
        logger.info(f"  {param}: {value}")
    logger.info(f"Completed trials: {results['n_trials']}")
    logger.info(f"Best trial: {results['best_trial']}")
    
    # Get parameter importance
    try:
        importance = optimizer.get_param_importance()
        logger.info("\nParameter Importance:")
        for param, score in sorted(importance.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {param}: {score:.4f}")
    except Exception as e:
        logger.debug(f"Could not compute parameter importance: {e}")
    
    return results, optimizer


def run_optimized_backtest(df_prices, params):
    """
    Run backtest with optimized parameters.
    
    Args:
        df_prices: Dictionary of DataFrames with OHLCV data
        params: Dictionary of strategy parameters
        
    Returns:
        Backtest metrics
    """
    logger.info("Running backtest with optimized parameters (fast mode)")
    
    # Run backtest in fast mode
    metrics, returns, cum_ret, trades = run_backtest(
        df_prices,
        M=params['M'],
        atr_period=params['atr_period'],
        sl_multiplier=params['sl_multiplier'],
        tp_multiplier=params['tp_multiplier'],
        fast_mode=True
    )
    
    logger.info("=" * 60)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"Sharpe Ratio: {metrics['Sharpe']:.4f}")
    logger.info(f"Sortino Ratio: {metrics['Sortino']:.4f}")
    logger.info(f"Max Drawdown: {metrics['Max Drawdown']:.2%}")
    logger.info(f"Calmar Ratio: {metrics['Calmar']:.4f}")
    logger.info(f"Total Return: {metrics['Total Return']:.2%}")
    logger.info(f"Annualized Return: {metrics['Annualized Return']:.2%}")
    logger.info(f"Number of Trades: {metrics['Trades']}")
    
    return metrics, returns, cum_ret, trades


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("FKS STRATEGY OPTIMIZER")
    logger.info("=" * 60)
    
    # Define symbols to trade
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
    
    # Step 1: Fetch market data with rate limiting
    logger.info("\n[Step 1] Fetching market data...")
    df_prices = fetch_market_data(symbols, days=100)
    
    if not df_prices:
        logger.error("No data fetched - cannot proceed")
        return
    
    logger.info(f"Successfully fetched data for {len(df_prices)} symbols")
    
    # Step 2: Optimize strategy parameters
    logger.info("\n[Step 2] Optimizing strategy parameters...")
    results, optimizer = optimize_strategy(df_prices, n_trials=20, use_rag=False)
    
    # Step 3: Run backtest with optimized parameters
    logger.info("\n[Step 3] Running backtest with optimized parameters...")
    metrics, returns, cum_ret, trades = run_optimized_backtest(
        df_prices,
        results['best_params']
    )
    
    # Step 4: Export results
    logger.info("\n[Step 4] Exporting results...")
    
    # Save optimization history
    history = optimizer.get_optimization_history()
    history_file = "optimization_history.csv"
    history.to_csv(history_file)
    logger.info(f"Saved optimization history to {history_file}")
    
    # Save backtest results
    returns_file = "backtest_returns.csv"
    returns.to_csv(returns_file)
    logger.info(f"Saved backtest returns to {returns_file}")
    
    logger.info("\n" + "=" * 60)
    logger.info("OPTIMIZATION COMPLETE")
    logger.info("=" * 60)
    
    # Print summary
    logger.info("\nKey Findings:")
    logger.info(f"  - Optimized for Sharpe ratio: {metrics['Sharpe']:.4f}")
    logger.info(f"  - Total return: {metrics['Total Return']:.2%}")
    logger.info(f"  - Max drawdown: {metrics['Max Drawdown']:.2%}")
    logger.info(f"  - Number of trades: {metrics['Trades']}")
    
    logger.info("\nOptimal Parameters:")
    for param, value in results['best_params'].items():
        logger.info(f"  - {param}: {value}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Optimization interrupted by user")
    except Exception as e:
        logger.exception(f"Error during optimization: {e}")
        sys.exit(1)
