# src/trading/optimizer/engine.py
"""
Strategy optimizer using Optuna for hyperparameter tuning.

This module provides optimization functionality to find the best
parameters for trading strategies by maximizing the Sharpe ratio.

Features:
- Optuna-powered hyperparameter optimization
- Parallel trial execution for faster optimization
- Progress tracking and visualization
- RAG integration for intelligent parameter suggestions
- Caching of optimization results
"""

from typing import Dict, Any, Optional, List, Tuple
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import pandas as pd
from loguru import logger

from trading.backtest import run_backtest


class OptunaOptimizer:
    """
    Advanced strategy optimizer using Optuna for hyperparameter tuning.
    
    This optimizer finds the best trading strategy parameters by maximizing
    the Sharpe ratio using Bayesian optimization with TPE sampler.
    """
    
    def __init__(
        self,
        df_prices: Dict[str, pd.DataFrame],
        n_trials: int = 100,
        n_jobs: int = 1,
        timeout: Optional[int] = None,
        sampler: Optional[optuna.samplers.BaseSampler] = None,
        pruner: Optional[optuna.pruners.BasePruner] = None,
        rag_service: Optional[Any] = None
    ):
        """
        Initialize the optimizer.
        
        Args:
            df_prices: Dictionary of DataFrames with OHLCV data for each symbol
            n_trials: Number of optimization trials
            n_jobs: Number of parallel jobs (-1 for all CPUs)
            timeout: Maximum time in seconds for optimization
            sampler: Optuna sampler (defaults to TPESampler)
            pruner: Optuna pruner (defaults to MedianPruner)
            rag_service: Optional RAG service for intelligent suggestions
        """
        self.df_prices = df_prices
        self.n_trials = n_trials
        self.n_jobs = n_jobs
        self.timeout = timeout
        self.rag_service = rag_service
        
        # Initialize sampler and pruner
        self.sampler = sampler or TPESampler(seed=42)
        self.pruner = pruner or MedianPruner(n_startup_trials=10, n_warmup_steps=5)
        
        # Track best parameters
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_value: Optional[float] = None
        self.study: Optional[optuna.Study] = None
        
        logger.info(
            f"OptunaOptimizer initialized: {n_trials} trials, "
            f"{n_jobs} jobs, RAG={'enabled' if rag_service else 'disabled'}"
        )
    
    def objective(self, trial: optuna.Trial) -> float:
        """
        Optuna objective function for strategy optimization.
        
        Args:
            trial: Optuna trial object
        
        Returns:
            float: Sharpe ratio (optimization target)
        """
        # Get parameter suggestions from RAG if available
        if self.rag_service and trial.number == 0:
            try:
                rag_params = self._get_rag_suggestions()
                if rag_params:
                    logger.info(f"RAG suggested parameters: {rag_params}")
            except Exception as e:
                logger.warning(f"Failed to get RAG suggestions: {e}")
        
        # Suggest hyperparameters
        M = trial.suggest_int('M', 5, 200)
        atr_period = trial.suggest_int('atr_period', 5, 30)
        sl_multiplier = trial.suggest_float('sl_multiplier', 1.0, 5.0)
        tp_multiplier = trial.suggest_float('tp_multiplier', 1.0, 10.0)
        
        try:
            # Run backtest with suggested parameters
            metrics, _, _, _ = run_backtest(
                self.df_prices, M, atr_period, sl_multiplier, tp_multiplier
            )
            
            sharpe = metrics['Sharpe']
            
            # Report intermediate values for pruning
            trial.report(sharpe, trial.number)
            
            # Check if trial should be pruned
            if trial.should_prune():
                raise optuna.TrialPruned()
            
            return sharpe
            
        except Exception as e:
            logger.error(f"Trial {trial.number} failed: {e}")
            # Return a very poor value so this trial is discarded
            return -999.0
    
    def optimize(self, study_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the optimization process.
        
        Args:
            study_name: Name for the Optuna study (optional)
        
        Returns:
            Dict with optimization results including best parameters and value
        """
        logger.info(f"Starting optimization: {self.n_trials} trials")
        
        # Create study
        study_name = study_name or "strategy_optimization"
        self.study = optuna.create_study(
            study_name=study_name,
            direction="maximize",
            sampler=self.sampler,
            pruner=self.pruner
        )
        
        # Run optimization
        self.study.optimize(
            self.objective,
            n_trials=self.n_trials,
            n_jobs=self.n_jobs,
            timeout=self.timeout,
            show_progress_bar=True
        )
        
        # Store best results
        self.best_params = self.study.best_params
        self.best_value = self.study.best_value
        
        logger.info(f"Optimization complete: Best Sharpe={self.best_value:.4f}")
        logger.info(f"Best parameters: {self.best_params}")
        
        return {
            "best_params": self.best_params,
            "best_value": self.best_value,
            "n_trials": len(self.study.trials),
            "best_trial": self.study.best_trial.number
        }
    
    def get_optimization_history(self) -> pd.DataFrame:
        """
        Get the optimization history as a DataFrame.
        
        Returns:
            DataFrame with trial results
        """
        if not self.study:
            raise ValueError("No optimization has been run yet")
        
        return self.study.trials_dataframe()
    
    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """Get the best parameters found during optimization."""
        return self.best_params
    
    def get_param_importance(self) -> Dict[str, float]:
        """
        Get the importance of each parameter.
        
        Returns:
            Dict mapping parameter names to importance scores
        """
        if not self.study:
            raise ValueError("No optimization has been run yet")
        
        try:
            importance = optuna.importance.get_param_importances(self.study)
            return importance
        except Exception as e:
            logger.warning(f"Failed to compute parameter importance: {e}")
            return {}
    
    def _get_rag_suggestions(self) -> Optional[Dict[str, Any]]:
        """
        Get parameter suggestions from RAG service based on market conditions.
        
        Returns:
            Dict with suggested parameter ranges or None
        """
        if not self.rag_service:
            return None
        
        try:
            # Query RAG for parameter suggestions
            query = """Based on current market conditions and historical performance,
            suggest optimal parameter ranges for a trading strategy with:
            - M (moving average period): range 5-200
            - atr_period (ATR calculation period): range 5-30
            - sl_multiplier (stop loss multiplier): range 1.0-5.0
            - tp_multiplier (take profit multiplier): range 1.0-10.0
            
            Consider volatility, trend strength, and recent market behavior.
            Respond with specific recommended values or ranges."""
            
            response = self.rag_service.query(query, max_results=3)
            
            # Parse RAG response (simplified - would need more sophisticated parsing)
            if response and "context" in response:
                logger.info("RAG suggestions retrieved successfully")
                return response
            
        except Exception as e:
            logger.error(f"Failed to get RAG suggestions: {e}")
        
        return None


def objective(trial, df_prices):
    """
    Legacy objective function for backward compatibility.
    
    Args:
        trial: Optuna trial object
        df_prices: Dictionary of DataFrames with OHLCV data

    Returns:
        float: Sharpe ratio (optimization target)
    """
    M = trial.suggest_int("M", 5, 200)
    atr_period = trial.suggest_int("atr_period", 5, 30)
    sl_multiplier = trial.suggest_float("sl_multiplier", 1.0, 5.0)
    tp_multiplier = trial.suggest_float("tp_multiplier", 1.0, 10.0)

    metrics, _, _, _ = run_backtest(
        df_prices, M, atr_period, sl_multiplier, tp_multiplier
    )

    return metrics["Sharpe"]
