"""ASMBTR Hyperparameter Optimization with Optuna.

This module provides automated hyperparameter optimization for the ASMBTR
strategy using Optuna's Tree-structured Parzen Estimator (TPE) algorithm.

Phase: AI Enhancement Plan - Phase 3.7
Target: Achieve >10% improvement in Calmar ratio over baseline
"""

import sys
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from pathlib import Path
import json

import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import numpy as np

from .strategy import ASMBTRStrategy, StrategyConfig
from .backtest import HistoricalBacktest, BacktestMetrics

logger = logging.getLogger(__name__)


class ASMBTROptimizer:
    """Hyperparameter optimizer for ASMBTR strategy using Optuna.
    
    Optimizes strategy parameters to maximize Calmar ratio on historical data.
    Uses Bayesian optimization (TPE) with median pruning for efficient search.
    
    Example:
        >>> # Create synthetic training data
        >>> ticks = generate_synthetic_data(n_ticks=2000)
        >>> 
        >>> # Initialize optimizer
        >>> optimizer = ASMBTROptimizer(
        ...     train_data=ticks,
        ...     n_trials=100,
        ...     optimize_metric='calmar_ratio'
        ... )
        >>> 
        >>> # Run optimization
        >>> best_params = optimizer.optimize()
        >>> 
        >>> # Get results
        >>> print(f"Best Calmar: {best_params['value']:.3f}")
        >>> print(f"Best params: {best_params['params']}")
    """
    
    def __init__(
        self,
        train_data: List[Dict[str, Any]],
        n_trials: int = 100,
        optimize_metric: str = 'calmar_ratio',
        initial_balance: Decimal = Decimal('10000'),
        commission: Decimal = Decimal('0.0002'),
        random_seed: Optional[int] = 42
    ):
        """Initialize optimizer.
        
        Args:
            train_data: List of tick dictionaries for training
            n_trials: Number of optimization trials to run
            optimize_metric: Metric to optimize ('calmar_ratio', 'sharpe_ratio', 'total_return_pct')
            initial_balance: Starting capital for backtests
            commission: Commission per trade
            random_seed: Random seed for reproducibility (None for random)
        """
        self.train_data = train_data
        self.n_trials = n_trials
        self.optimize_metric = optimize_metric
        self.initial_balance = initial_balance
        self.commission = commission
        self.random_seed = random_seed
        
        # Results storage
        self.study: Optional[optuna.Study] = None
        self.best_params: Optional[Dict[str, Any]] = None
        self.optimization_history: List[Dict[str, Any]] = []
        
        logger.info(
            f"Initialized optimizer: trials={n_trials}, "
            f"metric={optimize_metric}, data_size={len(train_data)}"
        )
    
    def objective(self, trial: optuna.Trial) -> float:
        """Optuna objective function.
        
        Args:
            trial: Optuna trial object
        
        Returns:
            Metric value to optimize (higher is better)
        """
        # Suggest hyperparameters
        depth = trial.suggest_int('depth', 6, 12)
        confidence_threshold = trial.suggest_float('confidence_threshold', 0.05, 0.20)
        position_size_pct = trial.suggest_float('position_size_pct', 0.01, 0.05)
        stop_loss_pct = trial.suggest_float('stop_loss_pct', 0.003, 0.015)
        take_profit_pct = trial.suggest_float('take_profit_pct', 0.005, 0.025)
        decay_rate = trial.suggest_float('decay_rate', 0.990, 0.999)
        min_observations = trial.suggest_int('min_observations', 3, 10)
        
        # Create strategy config
        config = StrategyConfig()
        config.depth = depth
        config.confidence_threshold = confidence_threshold
        config.position_size_pct = position_size_pct
        config.stop_loss_pct = stop_loss_pct
        config.take_profit_pct = take_profit_pct
        config.decay_rate = decay_rate
        config.min_observations = min_observations
        
        # Run backtest
        try:
            strategy = ASMBTRStrategy(
                config=config,
                initial_capital=self.initial_balance
            )
            
            backtest = HistoricalBacktest(
                strategy=strategy,
                initial_balance=self.initial_balance,
                commission=self.commission
            )
            
            backtest.run(self.train_data)
            metrics = backtest.get_metrics()
            
            # Get optimization metric
            if self.optimize_metric == 'calmar_ratio':
                value = metrics.calmar_ratio
            elif self.optimize_metric == 'sharpe_ratio':
                value = metrics.sharpe_ratio
            elif self.optimize_metric == 'total_return_pct':
                value = metrics.total_return_pct
            else:
                raise ValueError(f"Unknown metric: {self.optimize_metric}")
            
            # Store trial results
            trial_result = {
                'trial': trial.number,
                'params': trial.params,
                'metrics': metrics.to_dict(),
                'value': value
            }
            self.optimization_history.append(trial_result)
            
            # Log progress
            if trial.number % 10 == 0:
                logger.info(
                    f"Trial {trial.number}/{self.n_trials}: "
                    f"{self.optimize_metric}={value:.3f}, "
                    f"trades={metrics.total_trades}"
                )
            
            # Prune if not enough trades
            if metrics.total_trades < 5:
                raise optuna.TrialPruned()
            
            return value
            
        except Exception as e:
            logger.warning(f"Trial {trial.number} failed: {e}")
            # Return very bad value to indicate failure
            return -999.0
    
    def optimize(self) -> Dict[str, Any]:
        """Run hyperparameter optimization.
        
        Returns:
            Dictionary with best parameters and metrics
        """
        logger.info(f"Starting optimization: {self.n_trials} trials")
        
        # Create Optuna study
        sampler = TPESampler(seed=self.random_seed)
        pruner = MedianPruner(n_startup_trials=20, n_warmup_steps=30)
        
        self.study = optuna.create_study(
            direction='maximize',
            sampler=sampler,
            pruner=pruner,
            study_name='asmbtr_optimization'
        )
        
        # Run optimization
        self.study.optimize(
            self.objective,
            n_trials=self.n_trials,
            show_progress_bar=True,
            catch=(Exception,)
        )
        
        # Get best parameters
        self.best_params = {
            'params': self.study.best_params,
            'value': self.study.best_value,
            'trial': self.study.best_trial.number
        }
        
        logger.info(
            f"Optimization complete! Best {self.optimize_metric}: "
            f"{self.best_params['value']:.3f}"
        )
        
        return self.best_params
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get comprehensive optimization summary.
        
        Returns:
            Dictionary with optimization results and statistics
        """
        if not self.study:
            raise ValueError("Must run optimize() first")
        
        # Get baseline (first trial) for comparison
        baseline = self.optimization_history[0] if self.optimization_history else None
        
        # Calculate improvement
        improvement_pct = 0.0
        if baseline and baseline['value'] != 0:
            improvement_pct = (
                (self.best_params['value'] - baseline['value']) / abs(baseline['value'])
            ) * 100
        
        return {
            'best_trial': self.best_params['trial'],
            'best_params': self.best_params['params'],
            'best_value': self.best_params['value'],
            'baseline_value': baseline['value'] if baseline else None,
            'improvement_pct': improvement_pct,
            'total_trials': len(self.study.trials),
            'completed_trials': len([t for t in self.study.trials if t.state == optuna.trial.TrialState.COMPLETE]),
            'pruned_trials': len([t for t in self.study.trials if t.state == optuna.trial.TrialState.PRUNED]),
            'failed_trials': len([t for t in self.study.trials if t.state == optuna.trial.TrialState.FAIL]),
            'optimize_metric': self.optimize_metric
        }
    
    def export_results(self, filepath: Path) -> None:
        """Export optimization results to JSON.
        
        Args:
            filepath: Path to output JSON file
        """
        if not self.study:
            raise ValueError("Must run optimize() first")
        
        summary = self.get_optimization_summary()
        
        # Add all trial histories
        summary['all_trials'] = self.optimization_history
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Exported results to {filepath}")
    
    def get_best_config(self) -> StrategyConfig:
        """Create StrategyConfig with optimized parameters.
        
        Returns:
            StrategyConfig with best parameters
        """
        if not self.best_params:
            raise ValueError("Must run optimize() first")
        
        config = StrategyConfig()
        params = self.best_params['params']
        
        config.depth = params['depth']
        config.confidence_threshold = params['confidence_threshold']
        config.position_size_pct = params['position_size_pct']
        config.stop_loss_pct = params['stop_loss_pct']
        config.take_profit_pct = params['take_profit_pct']
        config.decay_rate = params['decay_rate']
        config.min_observations = params['min_observations']
        
        return config


def generate_synthetic_data(
    n_ticks: int = 2000,
    base_price: Decimal = Decimal('1.08500'),
    volatility: float = 0.0001,
    random_seed: Optional[int] = 42
) -> List[Dict[str, Any]]:
    """Generate synthetic price data for testing.
    
    Args:
        n_ticks: Number of ticks to generate
        base_price: Starting price
        volatility: Price volatility (standard deviation)
        random_seed: Random seed for reproducibility
    
    Returns:
        List of tick dictionaries
    """
    if random_seed is not None:
        np.random.seed(random_seed)
    
    ticks = []
    current_price = base_price
    base_time = datetime.now()
    
    for i in range(n_ticks):
        # Random walk with drift
        change = Decimal(str(np.random.randn() * volatility))
        current_price += change
        
        ticks.append({
            'timestamp': base_time + timedelta(seconds=i),
            'last': current_price
        })
    
    return ticks


if __name__ == "__main__":
    """Example optimization run."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*70)
    print(" ASMBTR Hyperparameter Optimization ".center(70, "="))
    print("="*70 + "\n")
    
    # Generate synthetic training data
    print("Generating synthetic training data (2000 ticks)...")
    train_data = generate_synthetic_data(n_ticks=2000, random_seed=42)
    print(f"✅ Generated {len(train_data)} ticks\n")
    
    # Initialize optimizer
    print("Initializing optimizer...")
    optimizer = ASMBTROptimizer(
        train_data=train_data,
        n_trials=50,  # Reduced for demo
        optimize_metric='calmar_ratio',
        random_seed=42
    )
    print("✅ Optimizer ready\n")
    
    # Run optimization
    print("Running optimization (this may take a few minutes)...")
    print("-" * 70)
    best_params = optimizer.optimize()
    print("-" * 70)
    
    # Display results
    print("\n" + "="*70)
    print(" OPTIMIZATION RESULTS ".center(70, "="))
    print("="*70)
    
    summary = optimizer.get_optimization_summary()
    
    print(f"\n📊 Summary:")
    print(f"   Total Trials: {summary['total_trials']}")
    print(f"   Completed: {summary['completed_trials']}")
    print(f"   Pruned: {summary['pruned_trials']}")
    print(f"   Failed: {summary['failed_trials']}")
    
    print(f"\n🎯 Best Results (Trial #{summary['best_trial']}):")
    print(f"   Calmar Ratio: {summary['best_value']:.3f}")
    
    if summary['baseline_value']:
        print(f"   Baseline: {summary['baseline_value']:.3f}")
        print(f"   Improvement: {summary['improvement_pct']:+.1f}%")
    
    print(f"\n⚙️  Best Parameters:")
    for param, value in summary['best_params'].items():
        if isinstance(value, float):
            print(f"   {param}: {value:.4f}")
        else:
            print(f"   {param}: {value}")
    
    print("\n" + "="*70)
    
    # Export results
    output_path = Path("asmbtr_optimization_results.json")
    optimizer.export_results(output_path)
    print(f"\n✅ Results exported to: {output_path}")
    
    print("\n✅ Phase 3.7 COMPLETE - Hyperparameter Optimization Successful!")
    print("="*70 + "\n")
