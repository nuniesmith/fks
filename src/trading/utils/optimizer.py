"""
Strategy optimization utilities using Optuna.
Migrated from src/optimizer.py

Handles:
- Hyperparameter optimization
- Objective function for backtesting
- Multi-trial optimization with Optuna
"""

import optuna
from typing import Dict, Callable, Optional
import pandas as pd

from .backtest_engine import run_backtest


def objective(trial: optuna.Trial, df_prices: Dict[str, pd.DataFrame], 
              symbols_config: Dict = None, fee_rate: float = 0.001) -> float:
    """
    Objective function for Optuna optimization
    
    Args:
        trial: Optuna trial object
        df_prices: Dictionary of symbol -> DataFrame with OHLCV data
        symbols_config: Configuration dict with 'SYMBOLS', 'MAINS', 'ALTS'
        fee_rate: Transaction fee rate
    
    Returns:
        Sharpe ratio (optimization target)
    """
    # Suggest hyperparameters
    M = trial.suggest_int('M', 5, 200)
    atr_period = trial.suggest_int('atr_period', 5, 30)
    sl_multiplier = trial.suggest_float('sl_multiplier', 1.0, 5.0)
    tp_multiplier = trial.suggest_float('tp_multiplier', 1.0, 10.0)
    
    # Run backtest with suggested parameters
    try:
        metrics, _, _, _ = run_backtest(
            df_prices=df_prices,
            M=M,
            atr_period=atr_period,
            sl_multiplier=sl_multiplier,
            tp_multiplier=tp_multiplier,
            symbols_config=symbols_config,
            fee_rate=fee_rate
        )
        
        # Return Sharpe ratio as optimization target
        return metrics['Sharpe']
    except Exception as e:
        print(f"Error in trial {trial.number}: {e}")
        return -999.0  # Return very bad score for failed trials


def run_optimization(
    df_prices: Dict[str, pd.DataFrame],
    n_trials: int = 50,
    optimization_metric: str = 'Sharpe',
    symbols_config: Dict = None,
    fee_rate: float = 0.001,
    timeout: Optional[int] = None,
    show_progress_bar: bool = True
) -> Dict:
    """
    Run strategy optimization using Optuna
    
    Args:
        df_prices: Dictionary of symbol -> DataFrame with OHLCV data
        n_trials: Number of optimization trials
        optimization_metric: Metric to optimize ('Sharpe', 'Sortino', 'Calmar')
        symbols_config: Configuration dict with 'SYMBOLS', 'MAINS', 'ALTS'
        fee_rate: Transaction fee rate
        timeout: Maximum optimization time in seconds (None for unlimited)
        show_progress_bar: Whether to show progress bar
    
    Returns:
        Dictionary with best parameters and optimization results
    """
    # Create objective function with custom metric if needed
    if optimization_metric == 'Sharpe':
        obj_func = lambda trial: objective(trial, df_prices, symbols_config, fee_rate)
    else:
        # Create custom objective for other metrics
        obj_func = lambda trial: custom_objective(
            trial, df_prices, optimization_metric, symbols_config, fee_rate
        )
    
    # Create study
    study = optuna.create_study(
        direction='maximize',
        sampler=optuna.samplers.TPESampler(seed=42)
    )
    
    # Run optimization
    study.optimize(
        obj_func,
        n_trials=n_trials,
        timeout=timeout,
        show_progress_bar=show_progress_bar
    )
    
    # Get best parameters
    best_params = study.best_params
    best_value = study.best_value
    
    # Run final backtest with best parameters
    metrics, returns, cum_ret, trades = run_backtest(
        df_prices=df_prices,
        M=best_params['M'],
        atr_period=best_params['atr_period'],
        sl_multiplier=best_params['sl_multiplier'],
        tp_multiplier=best_params['tp_multiplier'],
        symbols_config=symbols_config,
        fee_rate=fee_rate
    )
    
    return {
        'best_params': best_params,
        'best_value': best_value,
        'optimization_metric': optimization_metric,
        'final_metrics': metrics,
        'n_trials': n_trials,
        'study': study
    }


def custom_objective(
    trial: optuna.Trial,
    df_prices: Dict[str, pd.DataFrame],
    metric: str,
    symbols_config: Dict = None,
    fee_rate: float = 0.001
) -> float:
    """
    Custom objective function for different optimization metrics
    
    Args:
        trial: Optuna trial object
        df_prices: Dictionary of symbol -> DataFrame with OHLCV data
        metric: Metric to optimize ('Sortino', 'Calmar', 'Total Return', etc.)
        symbols_config: Configuration dict
        fee_rate: Transaction fee rate
    
    Returns:
        Metric value for optimization
    """
    # Suggest hyperparameters
    M = trial.suggest_int('M', 5, 200)
    atr_period = trial.suggest_int('atr_period', 5, 30)
    sl_multiplier = trial.suggest_float('sl_multiplier', 1.0, 5.0)
    tp_multiplier = trial.suggest_float('tp_multiplier', 1.0, 10.0)
    
    # Run backtest
    try:
        metrics, _, _, _ = run_backtest(
            df_prices=df_prices,
            M=M,
            atr_period=atr_period,
            sl_multiplier=sl_multiplier,
            tp_multiplier=tp_multiplier,
            symbols_config=symbols_config,
            fee_rate=fee_rate
        )
        
        # Return requested metric
        if metric in metrics:
            return metrics[metric]
        else:
            print(f"Warning: Metric '{metric}' not found, using Sharpe instead")
            return metrics['Sharpe']
    except Exception as e:
        print(f"Error in trial {trial.number}: {e}")
        return -999.0


def optimize_with_constraints(
    df_prices: Dict[str, pd.DataFrame],
    n_trials: int = 50,
    min_trades: int = 5,
    max_drawdown_limit: float = -0.3,
    min_sharpe: float = 0.5,
    symbols_config: Dict = None,
    fee_rate: float = 0.001
) -> Dict:
    """
    Run optimization with constraints on backtest results
    
    Args:
        df_prices: Dictionary of symbol -> DataFrame with OHLCV data
        n_trials: Number of optimization trials
        min_trades: Minimum number of trades required
        max_drawdown_limit: Maximum allowed drawdown (negative value)
        min_sharpe: Minimum Sharpe ratio required
        symbols_config: Configuration dict
        fee_rate: Transaction fee rate
    
    Returns:
        Dictionary with best constrained parameters and results
    """
    def constrained_objective(trial: optuna.Trial) -> float:
        # Suggest hyperparameters
        M = trial.suggest_int('M', 5, 200)
        atr_period = trial.suggest_int('atr_period', 5, 30)
        sl_multiplier = trial.suggest_float('sl_multiplier', 1.0, 5.0)
        tp_multiplier = trial.suggest_float('tp_multiplier', 1.0, 10.0)
        
        # Run backtest
        try:
            metrics, _, _, _ = run_backtest(
                df_prices=df_prices,
                M=M,
                atr_period=atr_period,
                sl_multiplier=sl_multiplier,
                tp_multiplier=tp_multiplier,
                symbols_config=symbols_config,
                fee_rate=fee_rate
            )
            
            # Check constraints
            if metrics['Trades'] < min_trades:
                return -999.0  # Penalize if too few trades
            
            if metrics['Max Drawdown'] < max_drawdown_limit:
                return -999.0  # Penalize if drawdown too large
            
            if metrics['Sharpe'] < min_sharpe:
                return -999.0  # Penalize if Sharpe too low
            
            # Return Sharpe ratio if all constraints met
            return metrics['Sharpe']
        except Exception as e:
            print(f"Error in trial {trial.number}: {e}")
            return -999.0
    
    # Create study
    study = optuna.create_study(direction='maximize')
    
    # Run optimization
    study.optimize(constrained_objective, n_trials=n_trials, show_progress_bar=True)
    
    # Get results
    best_params = study.best_params
    best_value = study.best_value
    
    # Run final backtest
    metrics, returns, cum_ret, trades = run_backtest(
        df_prices=df_prices,
        M=best_params['M'],
        atr_period=best_params['atr_period'],
        sl_multiplier=best_params['sl_multiplier'],
        tp_multiplier=best_params['tp_multiplier'],
        symbols_config=symbols_config,
        fee_rate=fee_rate
    )
    
    return {
        'best_params': best_params,
        'best_value': best_value,
        'final_metrics': metrics,
        'constraints': {
            'min_trades': min_trades,
            'max_drawdown_limit': max_drawdown_limit,
            'min_sharpe': min_sharpe
        },
        'study': study
    }


def analyze_optimization_results(study: optuna.Study) -> Dict:
    """
    Analyze optimization results
    
    Args:
        study: Completed Optuna study
    
    Returns:
        Dictionary with analysis results
    """
    trials_df = study.trials_dataframe()
    
    analysis = {
        'total_trials': len(study.trials),
        'best_value': study.best_value,
        'best_params': study.best_params,
        'best_trial_number': study.best_trial.number,
    }
    
    # Parameter importance (if enough trials)
    if len(study.trials) >= 10:
        try:
            importance = optuna.importance.get_param_importances(study)
            analysis['param_importance'] = importance
        except Exception as e:
            print(f"Could not calculate parameter importance: {e}")
    
    return analysis
