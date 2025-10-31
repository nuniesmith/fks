"""
Integration Tests for ASMBTR Evaluation Framework

Tests the integration between Phase 7.1 evaluation framework
and ASMBTR strategy predictions.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add evaluation module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from strategies.asmbtr.evaluation import (
    ASMBTREvaluator,
    ASMBTREvaluationResult,
)
from evaluation.confusion_matrix import ModelEvaluator


class TestASMBTREvaluatorIntegration:
    """Test ASMBTR evaluation integration"""
    
    @pytest.fixture
    def sample_backtest_data(self):
        """Create sample backtest data"""
        np.random.seed(42)
        n_samples = 100
        
        # Actual movements
        actual = np.random.choice([-1, 0, 1], size=n_samples, p=[0.3, 0.2, 0.5])
        
        # Predictions with 70% accuracy
        predicted = actual.copy()
        error_idx = np.random.choice(n_samples, size=30, replace=False)
        predicted[error_idx] = np.random.choice([-1, 0, 1], size=30)
        
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n_samples, freq="1h"),
            "predicted_signal": predicted,
            "actual_movement": actual,
            "state": [f"state_{i % 10:02d}" for i in range(n_samples)],
        })
        
        return df
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance"""
        return ASMBTREvaluator()
    
    def test_evaluate_backtest_predictions(self, evaluator, sample_backtest_data):
        """Test basic backtest evaluation"""
        result = evaluator.evaluate_backtest_predictions(
            sample_backtest_data,
            correction="bonferroni",
            n_tests=1,
        )
        
        assert isinstance(result, ASMBTREvaluationResult)
        assert result.total_predictions == 100
        assert 0.6 <= result.directional_accuracy <= 0.8  # ~70% accuracy
        assert 0 <= result.metrics.precision <= 1
        assert 0 <= result.metrics.recall <= 1
        assert 0 <= result.metrics.f1_score <= 1
    
    def test_bonferroni_correction(self, evaluator, sample_backtest_data):
        """Test Bonferroni correction is applied"""
        result = evaluator.evaluate_backtest_predictions(
            sample_backtest_data,
            correction="bonferroni",
            n_tests=3,
        )
        
        # Adjusted p-value should be >= original p-value
        assert result.metrics.adjusted_p_value >= result.metrics.p_value
        # With 3 tests, max adjustment is 3x (capped at 1.0)
        assert result.metrics.adjusted_p_value <= 1.0
    
    def test_benjamini_hochberg_correction(self, evaluator, sample_backtest_data):
        """Test Benjamini-Hochberg correction"""
        result = evaluator.evaluate_backtest_predictions(
            sample_backtest_data,
            correction="benjamini_hochberg",
            n_tests=5,
        )
        
        assert result.correction_method == "benjamini_hochberg"
        assert result.metrics.adjusted_p_value is not None
    
    def test_statistical_significance(self, evaluator, sample_backtest_data):
        """Test statistical significance detection"""
        result = evaluator.evaluate_backtest_predictions(
            sample_backtest_data,
            correction="bonferroni",
            n_tests=1,
        )
        
        # With 70% accuracy on 100 samples, should be significant
        assert result.statistical_significance is True
        assert result.adjusted_p_value < 0.05
    
    def test_convert_price_changes_to_signals(self, evaluator):
        """Test price change conversion"""
        price_changes = [0.5, -0.3, 0.01, -0.01, 0.0]
        
        # No threshold
        signals = evaluator.convert_price_changes_to_signals(price_changes, threshold=0.0)
        assert signals == [1, -1, 1, -1, 0]
        
        # With threshold
        signals = evaluator.convert_price_changes_to_signals(price_changes, threshold=0.1)
        assert signals == [1, -1, 0, 0, 0]
    
    def test_evaluate_state_predictions(self, evaluator, sample_backtest_data):
        """Test per-state evaluation"""
        state_results = evaluator.evaluate_state_predictions(
            sample_backtest_data["state"].tolist(),
            sample_backtest_data["predicted_signal"].tolist(),
            sample_backtest_data["actual_movement"].tolist(),
            correction="bonferroni",
        )
        
        assert isinstance(state_results, dict)
        assert len(state_results) > 0
        
        # Check structure of results
        for state, metrics in state_results.items():
            assert "sample_count" in metrics
            assert "accuracy" in metrics
            assert "precision" in metrics
            assert "recall" in metrics
            assert "f1_score" in metrics
            assert "p_value" in metrics
            assert metrics["sample_count"] >= 5  # Min sample requirement
    
    def test_compare_asmbtr_variants(self, evaluator):
        """Test variant comparison"""
        np.random.seed(42)
        n_samples = 100
        
        y_true = np.random.choice([-1, 0, 1], size=n_samples).tolist()
        
        # Create variants with different accuracies
        variant_1 = y_true.copy()
        err_idx = np.random.choice(n_samples, size=20, replace=False)
        for idx in err_idx:
            variant_1[idx] = np.random.choice([-1, 0, 1])
        
        variant_2 = y_true.copy()
        err_idx = np.random.choice(n_samples, size=35, replace=False)
        for idx in err_idx:
            variant_2[idx] = np.random.choice([-1, 0, 1])
        
        variants = {
            "High Accuracy": variant_1,
            "Low Accuracy": variant_2,
        }
        
        comparison = evaluator.compare_asmbtr_variants(y_true, variants)
        
        assert isinstance(comparison, pd.DataFrame)
        assert len(comparison) == 2
        assert "model" in comparison.columns
        assert "accuracy" in comparison.columns
        assert "f1_score" in comparison.columns
        
        # High accuracy variant should be first (sorted by f1_score)
        assert comparison.iloc[0]["model"] == "High Accuracy"
        assert comparison.iloc[0]["accuracy"] > comparison.iloc[1]["accuracy"]
    
    def test_generate_evaluation_report(self, evaluator, sample_backtest_data):
        """Test report generation"""
        result = evaluator.evaluate_backtest_predictions(
            sample_backtest_data,
            correction="bonferroni",
            n_tests=1,
        )
        
        report = evaluator.generate_evaluation_report(result)
        
        assert isinstance(report, str)
        assert "ASMBTR EVALUATION REPORT" in report
        assert "OVERALL METRICS" in report
        assert "CLASSIFICATION METRICS" in report
        assert "STATISTICAL SIGNIFICANCE" in report
        assert "CONFUSION MATRIX" in report
        assert str(result.directional_accuracy) in report or f"{result.directional_accuracy:.2%}" in report
    
    def test_evaluation_result_to_dict(self, evaluator, sample_backtest_data):
        """Test result serialization"""
        result = evaluator.evaluate_backtest_predictions(
            sample_backtest_data,
            correction="bonferroni",
            n_tests=1,
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert "total_predictions" in result_dict
        assert "directional_accuracy" in result_dict
        assert "statistical_significance" in result_dict
        assert "evaluation_metrics" in result_dict
        
        # Check nested metrics
        eval_metrics = result_dict["evaluation_metrics"]
        assert "accuracy" in eval_metrics
        assert "precision" in eval_metrics
        assert "recall" in eval_metrics
        assert "f1_score" in eval_metrics
    
    def test_hold_accuracy_calculation(self, evaluator):
        """Test hold accuracy metric"""
        # Create data with specific hold patterns
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="1h"),
            "predicted_signal": [0, 0, 0, 1, 1, -1, -1, 0, 0, 0],
            "actual_movement": [0, 0, 1, 1, 1, -1, 0, 0, 0, -1],
        })
        
        result = evaluator.evaluate_backtest_predictions(df)
        
        # Hold predictions: indices 0,1,2,7,8,9
        # Correct holds: 0,1,7,8 = 4 out of 6
        expected_hold_accuracy = 4 / 6
        assert abs(result.hold_accuracy - expected_hold_accuracy) < 0.01


class TestASMBTRIntegrationWithRealScenarios:
    """Test integration with realistic ASMBTR scenarios"""
    
    def test_high_accuracy_scenario(self):
        """Test with high accuracy predictions (>80%)"""
        evaluator = ASMBTREvaluator()
        np.random.seed(123)
        
        n_samples = 200
        y_true = np.random.choice([-1, 0, 1], size=n_samples)
        y_pred = y_true.copy()
        
        # 85% accuracy
        error_idx = np.random.choice(n_samples, size=30, replace=False)
        y_pred[error_idx] = np.random.choice([-1, 0, 1], size=30)
        
        df = pd.DataFrame({
            "predicted_signal": y_pred,
            "actual_movement": y_true,
        })
        
        result = evaluator.evaluate_backtest_predictions(df)
        
        assert result.directional_accuracy >= 0.80
        assert result.statistical_significance is True
        assert result.metrics.f1_score >= 0.75
    
    def test_low_accuracy_scenario(self):
        """Test with low accuracy predictions (~40%)"""
        evaluator = ASMBTREvaluator()
        np.random.seed(456)
        
        n_samples = 200
        y_true = np.random.choice([-1, 0, 1], size=n_samples)
        y_pred = y_true.copy()
        
        # 40% accuracy (worse than random for 3 classes)
        error_idx = np.random.choice(n_samples, size=120, replace=False)
        y_pred[error_idx] = np.random.choice([-1, 0, 1], size=120)
        
        df = pd.DataFrame({
            "predicted_signal": y_pred,
            "actual_movement": y_true,
        })
        
        result = evaluator.evaluate_backtest_predictions(df)
        
        assert result.directional_accuracy < 0.50
        assert result.metrics.f1_score < 0.50
    
    def test_balanced_vs_imbalanced_data(self):
        """Test evaluation on balanced vs imbalanced datasets"""
        evaluator = ASMBTREvaluator()
        np.random.seed(789)
        
        n_samples = 300
        
        # Balanced dataset
        y_true_balanced = np.random.choice([-1, 0, 1], size=n_samples, p=[0.33, 0.34, 0.33])
        y_pred_balanced = y_true_balanced.copy()
        err = np.random.choice(n_samples, size=90, replace=False)
        y_pred_balanced[err] = np.random.choice([-1, 0, 1], size=90)
        
        df_balanced = pd.DataFrame({
            "predicted_signal": y_pred_balanced,
            "actual_movement": y_true_balanced,
        })
        
        # Imbalanced dataset (bull market: mostly upward)
        y_true_imbalanced = np.random.choice([-1, 0, 1], size=n_samples, p=[0.20, 0.15, 0.65])
        y_pred_imbalanced = y_true_imbalanced.copy()
        err = np.random.choice(n_samples, size=90, replace=False)
        y_pred_imbalanced[err] = np.random.choice([-1, 0, 1], size=90)
        
        df_imbalanced = pd.DataFrame({
            "predicted_signal": y_pred_imbalanced,
            "actual_movement": y_true_imbalanced,
        })
        
        result_balanced = evaluator.evaluate_backtest_predictions(df_balanced)
        result_imbalanced = evaluator.evaluate_backtest_predictions(df_imbalanced)
        
        # Both should have similar accuracy (~70%)
        assert 0.65 <= result_balanced.directional_accuracy <= 0.75
        assert 0.65 <= result_imbalanced.directional_accuracy <= 0.75
        
        # But F1 scores might differ due to class imbalance
        assert result_balanced.metrics.f1_score > 0
        assert result_imbalanced.metrics.f1_score > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
