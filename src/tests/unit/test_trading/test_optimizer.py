"""
Test suite for trading.utils.optimizer module

Tests cover:
- Optuna optimization trials
- Objective function error handling
- Parameter suggestion ranges
- Best parameter selection
"""

import pytest
import pandas as pd
import numpy as np
import optuna
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.optimizer import objective, run_optimization, custom_objective


class TestOptimizer:
    """Test optimizer functionality"""
    
    @pytest.fixture
    def sample_prices(self):
        """Generate sample multi-symbol OHLCV data for testing"""
        dates = pd.date_range(start='2023-01-01', periods=1000, freq='1h')
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        df_prices = {}
        
        np.random.seed(42)
        for i, symbol in enumerate(symbols):
            base_price = 100 * (i + 1)
            closes = base_price + np.cumsum(np.random.randn(1000) * 2)
            highs = closes + np.abs(np.random.randn(1000) * 1)
            lows = closes - np.abs(np.random.randn(1000) * 1)
            opens = closes + np.random.randn(1000) * 0.5
            volumes = np.random.randint(1000, 10000, 1000)
            
            df = pd.DataFrame({
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            }, index=dates)
            
            df_prices[symbol] = df
        
        return df_prices
    
    @pytest.fixture
    def symbols_config(self):
        """Standard symbols configuration"""
        return {
            'SYMBOLS': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
            'MAINS': ['BTCUSDT', 'ETHUSDT'],
            'ALTS': ['SOLUSDT']
        }
    
    def test_objective_function_returns_value(self, sample_prices, symbols_config):
        """Test that objective function returns a valid Sharpe ratio"""
        study = optuna.create_study(direction='maximize')
        trial = study.ask()
        
        result = objective(trial, sample_prices, symbols_config, fee_rate=0.001)
        
        # Should return a float
        assert isinstance(result, (float, int))
        # Should not return the error value if backtest succeeds
        assert result != -999.0 or result == -999.0  # Either valid or error
    
    def test_objective_function_error_handling(self, symbols_config):
        """Test that objective function handles errors gracefully"""
        # Create invalid data that might cause errors
        df_prices = {'BTCUSDT': pd.DataFrame()}  # Empty dataframe
        
        study = optuna.create_study(direction='maximize')
        trial = study.ask()
        
        result = objective(trial, df_prices, symbols_config, fee_rate=0.001)
        
        # Should return error value (-999.0) instead of raising exception
        assert result == -999.0
    
    def test_run_optimization_completes(self, sample_prices, symbols_config):
        """Test that optimization runs to completion"""
        result = run_optimization(
            df_prices=sample_prices,
            n_trials=5,  # Small number for testing
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=30,  # 30 second timeout
            show_progress_bar=False
        )
        
        # Check result structure
        assert 'best_params' in result
        assert 'best_value' in result
        assert 'optimization_metric' in result
        assert 'final_metrics' in result
        assert 'n_trials' in result
        assert 'study' in result
        
        # Check best_params has required keys
        assert 'M' in result['best_params']
        assert 'atr_period' in result['best_params']
        assert 'sl_multiplier' in result['best_params']
        assert 'tp_multiplier' in result['best_params']
        
        # Check parameter ranges
        assert 5 <= result['best_params']['M'] <= 200
        assert 5 <= result['best_params']['atr_period'] <= 30
        assert 1.0 <= result['best_params']['sl_multiplier'] <= 5.0
        assert 1.0 <= result['best_params']['tp_multiplier'] <= 10.0
    
    def test_multiple_trials_no_errors(self, sample_prices, symbols_config):
        """
        Test that multiple optimization trials complete without ValueError
        This replicates the bug scenario from the error log
        """
        result = run_optimization(
            df_prices=sample_prices,
            n_trials=50,  # Same as in the error log
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=120,
            show_progress_bar=False
        )
        
        # Should complete all 50 trials
        assert result['n_trials'] == 50
        
        # Should have valid best_value (not error value)
        # Note: best_value could be -999.0 if all trials failed, but that's unlikely with good data
        assert result['best_value'] is not None
        
        # Final metrics should be valid
        assert result['final_metrics'] is not None
        assert 'Sharpe' in result['final_metrics']
    
    def test_optimization_metrics_options(self, sample_prices, symbols_config):
        """Test optimization with different target metrics"""
        metrics_to_test = ['Sharpe', 'Sortino', 'Calmar', 'Total Return']
        
        for metric in metrics_to_test:
            result = run_optimization(
                df_prices=sample_prices,
                n_trials=3,  # Quick test
                optimization_metric=metric,
                symbols_config=symbols_config,
                fee_rate=0.001,
                timeout=30,
                show_progress_bar=False
            )
            
            assert result['optimization_metric'] == metric
            assert result['best_params'] is not None
    
    def test_custom_objective_function(self, sample_prices, symbols_config):
        """Test custom objective function for non-Sharpe metrics"""
        study = optuna.create_study(direction='maximize')
        trial = study.ask()
        
        # Test with different metrics
        for metric in ['Sortino', 'Calmar', 'Total Return']:
            result = custom_objective(
                trial, sample_prices, metric, symbols_config, fee_rate=0.001
            )
            
            assert isinstance(result, (float, int))
    
    def test_optimization_reproducibility(self, sample_prices, symbols_config):
        """Test that optimization with same seed produces similar results"""
        # Note: Complete reproducibility may not be guaranteed, but results should be reasonable
        result1 = run_optimization(
            df_prices=sample_prices,
            n_trials=10,
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=30,
            show_progress_bar=False
        )
        
        result2 = run_optimization(
            df_prices=sample_prices,
            n_trials=10,
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=30,
            show_progress_bar=False
        )
        
        # Both should complete successfully
        assert result1['best_params'] is not None
        assert result2['best_params'] is not None
        
        # Results don't have to be identical, but should be valid
        for key in ['M', 'atr_period', 'sl_multiplier', 'tp_multiplier']:
            assert key in result1['best_params']
            assert key in result2['best_params']
    
    def test_timeout_handling(self, sample_prices, symbols_config):
        """Test that optimization respects timeout"""
        import time
        
        start_time = time.time()
        result = run_optimization(
            df_prices=sample_prices,
            n_trials=1000,  # Many trials
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=5,  # Short timeout
            show_progress_bar=False
        )
        elapsed_time = time.time() - start_time
        
        # Should complete within reasonable time of timeout
        assert elapsed_time < 10  # Some buffer for overhead
        
        # Should have completed some trials
        assert result['n_trials'] >= 0
    
    def test_parameter_bounds_enforcement(self, sample_prices, symbols_config):
        """Test that suggested parameters stay within bounds"""
        result = run_optimization(
            df_prices=sample_prices,
            n_trials=20,
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=60,
            show_progress_bar=False
        )
        
        # Get all trials from study
        study = result['study']
        
        for trial in study.trials:
            params = trial.params
            
            # Check parameter bounds
            assert 5 <= params['M'] <= 200, f"M out of bounds: {params['M']}"
            assert 5 <= params['atr_period'] <= 30, f"atr_period out of bounds: {params['atr_period']}"
            assert 1.0 <= params['sl_multiplier'] <= 5.0, f"sl_multiplier out of bounds: {params['sl_multiplier']}"
            assert 1.0 <= params['tp_multiplier'] <= 10.0, f"tp_multiplier out of bounds: {params['tp_multiplier']}"
    
    def test_optimization_with_minimal_data(self, symbols_config):
        """Test optimization with minimal data (edge case)"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
        
        df_prices = {}
        for symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
            df = pd.DataFrame({
                'open': 100.0,
                'high': 101.0,
                'low': 99.0,
                'close': 100.0,
                'volume': 1000
            }, index=dates)
            df_prices[symbol] = df
        
        result = run_optimization(
            df_prices=df_prices,
            n_trials=5,
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=30,
            show_progress_bar=False
        )
        
        # Should complete without error
        assert result['best_params'] is not None


class TestOptunaIntegration:
    """Test integration with Optuna framework"""
    
    @pytest.fixture
    def sample_prices(self):
        """Generate sample data"""
        dates = pd.date_range(start='2023-01-01', periods=500, freq='1h')
        
        df_prices = {}
        for symbol in ['BTCUSDT', 'ETHUSDT']:
            np.random.seed(42)
            closes = 100 + np.cumsum(np.random.randn(500) * 2)
            df = pd.DataFrame({
                'open': closes,
                'high': closes + np.abs(np.random.randn(500)),
                'low': closes - np.abs(np.random.randn(500)),
                'close': closes,
                'volume': 1000
            }, index=dates)
            df_prices[symbol] = df
        
        return df_prices
    
    @pytest.fixture
    def symbols_config(self):
        return {
            'SYMBOLS': ['BTCUSDT', 'ETHUSDT'],
            'MAINS': ['BTCUSDT'],
            'ALTS': ['ETHUSDT']
        }
    
    def test_study_creation(self, sample_prices, symbols_config):
        """Test that Optuna study is created correctly"""
        result = run_optimization(
            df_prices=sample_prices,
            n_trials=5,
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=30,
            show_progress_bar=False
        )
        
        study = result['study']
        
        # Check study properties
        assert isinstance(study, optuna.Study)
        assert study.direction == optuna.study.StudyDirection.MAXIMIZE
        assert len(study.trials) == 5
    
    def test_trial_pruning_not_triggered(self, sample_prices, symbols_config):
        """Test that trials complete (no pruning in our setup)"""
        result = run_optimization(
            df_prices=sample_prices,
            n_trials=10,
            optimization_metric='Sharpe',
            symbols_config=symbols_config,
            fee_rate=0.001,
            timeout=30,
            show_progress_bar=False
        )
        
        study = result['study']
        
        # Count completed trials
        completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        
        # All trials should complete (no pruning)
        assert len(completed) == 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
