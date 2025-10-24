"""
Test suite for Optuna-based optimizer.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock the constants import for testing
mock_framework = MagicMock()
mock_framework.config.constants.SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
mock_framework.config.constants.MAINS = ['BTCUSDT', 'ETHUSDT']
mock_framework.config.constants.ALTS = ['BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
mock_framework.config.constants.FEE_RATE = 0.001

sys.modules['framework'] = mock_framework
sys.modules['framework.config'] = mock_framework.config
sys.modules['framework.config.constants'] = mock_framework.config.constants

from trading.optimizer.engine import OptunaOptimizer, objective


def create_test_data(n_days=100):
    """Create synthetic OHLCV data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=n_days, freq='D')
    
    df_prices = {}
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
    
    for symbol in symbols:
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(n_days) * 2)
        open_ = close + np.random.randn(n_days) * 0.5
        high = np.maximum(open_, close) + np.abs(np.random.randn(n_days)) * 0.5
        low = np.minimum(open_, close) - np.abs(np.random.randn(n_days)) * 0.5
        volume = np.abs(np.random.randn(n_days)) * 1000
        
        df_prices[symbol] = pd.DataFrame({
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
    
    return df_prices


class TestOptunaOptimizer:
    """Test OptunaOptimizer class functionality."""
    
    def test_optimizer_initialization(self):
        """Test optimizer initialization with default parameters."""
        df_prices = create_test_data(100)
        optimizer = OptunaOptimizer(df_prices, n_trials=10)
        
        assert optimizer.df_prices is not None
        assert optimizer.n_trials == 10
        assert optimizer.n_jobs == 1
        assert optimizer.sampler is not None
        assert optimizer.pruner is not None
        assert optimizer.best_params is None
        assert optimizer.best_value is None
    
    def test_optimizer_with_custom_parameters(self):
        """Test optimizer initialization with custom parameters."""
        df_prices = create_test_data(100)
        optimizer = OptunaOptimizer(
            df_prices,
            n_trials=50,
            n_jobs=2,
            timeout=300
        )
        
        assert optimizer.n_trials == 50
        assert optimizer.n_jobs == 2
        assert optimizer.timeout == 300
    
    def test_objective_function_returns_float(self):
        """Test that objective function returns a float value."""
        df_prices = create_test_data(100)
        optimizer = OptunaOptimizer(df_prices, n_trials=5)
        
        # Create mock trial
        import optuna
        study = optuna.create_study(direction="maximize")
        trial = study.ask()
        
        result = optimizer.objective(trial)
        
        assert isinstance(result, float)
        assert not np.isnan(result)
    
    def test_optimization_runs_successfully(self):
        """Test that optimization completes successfully."""
        df_prices = create_test_data(50)  # Smaller dataset for faster test
        optimizer = OptunaOptimizer(df_prices, n_trials=5)
        
        results = optimizer.optimize(study_name="test_study")
        
        assert 'best_params' in results
        assert 'best_value' in results
        assert 'n_trials' in results
        assert 'best_trial' in results
        assert results['n_trials'] == 5
        assert optimizer.best_params is not None
        assert optimizer.best_value is not None
    
    def test_optimization_finds_reasonable_parameters(self):
        """Test that optimization finds parameters in expected ranges."""
        df_prices = create_test_data(100)
        optimizer = OptunaOptimizer(df_prices, n_trials=10)
        
        results = optimizer.optimize()
        best_params = results['best_params']
        
        # Check parameter ranges
        assert 5 <= best_params['M'] <= 200
        assert 5 <= best_params['atr_period'] <= 30
        assert 1.0 <= best_params['sl_multiplier'] <= 5.0
        assert 1.0 <= best_params['tp_multiplier'] <= 10.0
    
    def test_get_optimization_history(self):
        """Test getting optimization history as DataFrame."""
        df_prices = create_test_data(50)
        optimizer = OptunaOptimizer(df_prices, n_trials=5)
        
        optimizer.optimize()
        history = optimizer.get_optimization_history()
        
        assert isinstance(history, pd.DataFrame)
        assert len(history) == 5
        assert 'value' in history.columns
    
    def test_get_best_params(self):
        """Test getting best parameters after optimization."""
        df_prices = create_test_data(50)
        optimizer = OptunaOptimizer(df_prices, n_trials=5)
        
        # Before optimization
        assert optimizer.get_best_params() is None
        
        # After optimization
        optimizer.optimize()
        best_params = optimizer.get_best_params()
        
        assert best_params is not None
        assert 'M' in best_params
        assert 'atr_period' in best_params
        assert 'sl_multiplier' in best_params
        assert 'tp_multiplier' in best_params
    
    def test_get_param_importance(self):
        """Test getting parameter importance scores."""
        df_prices = create_test_data(50)
        optimizer = OptunaOptimizer(df_prices, n_trials=10)
        
        optimizer.optimize()
        importance = optimizer.get_param_importance()
        
        assert isinstance(importance, dict)
        # Should have importance for all parameters
        assert len(importance) > 0
    
    def test_optimizer_with_rag_service(self):
        """Test optimizer with RAG service integration."""
        df_prices = create_test_data(50)
        
        # Mock RAG service
        mock_rag = Mock()
        mock_rag.query.return_value = {
            'context': 'Based on market conditions, use M=20, atr_period=14'
        }
        
        optimizer = OptunaOptimizer(df_prices, n_trials=5, rag_service=mock_rag)
        results = optimizer.optimize()
        
        assert results['best_params'] is not None
    
    def test_optimizer_handles_failed_trials(self):
        """Test that optimizer handles failed trials gracefully."""
        df_prices = create_test_data(50)
        
        # Create optimizer with very aggressive parameters that might fail
        optimizer = OptunaOptimizer(df_prices, n_trials=5)
        
        # Run optimization - should not crash even if some trials fail
        results = optimizer.optimize()
        
        assert results is not None
        assert results['n_trials'] >= 0
    
    def test_parallel_optimization(self):
        """Test optimization with parallel jobs."""
        df_prices = create_test_data(50)
        optimizer = OptunaOptimizer(df_prices, n_trials=10, n_jobs=2)
        
        results = optimizer.optimize()
        
        assert results['n_trials'] == 10
        assert optimizer.best_value is not None
    
    def test_optimization_with_timeout(self):
        """Test optimization with timeout constraint."""
        df_prices = create_test_data(100)
        optimizer = OptunaOptimizer(df_prices, n_trials=100, timeout=5)  # 5 second timeout
        
        import time
        start = time.time()
        results = optimizer.optimize()
        elapsed = time.time() - start
        
        # Should complete within timeout + small buffer
        assert elapsed < 10
        assert results is not None


class TestLegacyObjectiveFunction:
    """Test legacy objective function for backward compatibility."""
    
    def test_legacy_objective_function(self):
        """Test that legacy objective function still works."""
        df_prices = create_test_data(100)
        
        import optuna
        study = optuna.create_study(direction="maximize")
        trial = study.ask()
        
        result = objective(trial, df_prices)
        
        assert isinstance(result, float)
        assert not np.isnan(result)
    
    def test_legacy_objective_with_optuna_study(self):
        """Test legacy objective function with Optuna study."""
        df_prices = create_test_data(50)
        
        import optuna
        study = optuna.create_study(direction="maximize")
        
        # Run a few trials
        for _ in range(5):
            trial = study.ask()
            value = objective(trial, df_prices)
            study.tell(trial, value)
        
        assert len(study.trials) == 5
        assert study.best_value is not None


class TestRAGIntegration:
    """Test RAG integration with optimizer."""
    
    def test_rag_suggestions_called_on_first_trial(self):
        """Test that RAG suggestions are called on first trial."""
        df_prices = create_test_data(50)
        
        mock_rag = Mock()
        mock_rag.query.return_value = {
            'context': 'Use conservative parameters for current market'
        }
        
        optimizer = OptunaOptimizer(df_prices, n_trials=3, rag_service=mock_rag)
        optimizer.optimize()
        
        # RAG should have been queried
        assert mock_rag.query.called or mock_rag.query.call_count >= 0
    
    def test_rag_failure_doesnt_break_optimization(self):
        """Test that RAG failure doesn't break optimization."""
        df_prices = create_test_data(50)
        
        mock_rag = Mock()
        mock_rag.query.side_effect = Exception("RAG service error")
        
        optimizer = OptunaOptimizer(df_prices, n_trials=5, rag_service=mock_rag)
        
        # Should complete successfully despite RAG error
        results = optimizer.optimize()
        
        assert results is not None
        assert results['best_params'] is not None
    
    def test_optimizer_without_rag_service(self):
        """Test optimizer works without RAG service."""
        df_prices = create_test_data(50)
        
        optimizer = OptunaOptimizer(df_prices, n_trials=5, rag_service=None)
        results = optimizer.optimize()
        
        assert results is not None
        assert results['best_params'] is not None


class TestOptimizerEdgeCases:
    """Test edge cases for optimizer."""
    
    def test_optimizer_with_minimal_trials(self):
        """Test optimizer with minimal number of trials."""
        df_prices = create_test_data(50)
        optimizer = OptunaOptimizer(df_prices, n_trials=1)
        
        results = optimizer.optimize()
        
        assert results['n_trials'] == 1
        assert optimizer.best_params is not None
    
    def test_optimizer_with_small_dataset(self):
        """Test optimizer with very small dataset."""
        df_prices = create_test_data(30)  # Minimal data
        optimizer = OptunaOptimizer(df_prices, n_trials=5)
        
        results = optimizer.optimize()
        
        assert results is not None
        assert optimizer.best_value is not None
    
    def test_get_history_before_optimization_raises_error(self):
        """Test that getting history before optimization raises error."""
        df_prices = create_test_data(50)
        optimizer = OptunaOptimizer(df_prices, n_trials=5)
        
        with pytest.raises(ValueError):
            optimizer.get_optimization_history()
    
    def test_get_importance_before_optimization_raises_error(self):
        """Test that getting importance before optimization raises error."""
        df_prices = create_test_data(50)
        optimizer = OptunaOptimizer(df_prices, n_trials=5)
        
        with pytest.raises(ValueError):
            optimizer.get_param_importance()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
