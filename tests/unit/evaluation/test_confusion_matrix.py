"""
Unit Tests for Confusion Matrix and Model Evaluation
"""

import pytest
import numpy as np
from evaluation.confusion_matrix import (
    ModelEvaluator,
    compute_prediction_accuracy,
    EvaluationMetrics,
)


class TestModelEvaluator:
    """Test suite for ModelEvaluator class"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.evaluator = ModelEvaluator()
    
    def test_perfect_predictions(self):
        """Test with perfect predictions"""
        y_true = [1, 1, -1, 0, 1, -1]
        y_pred = [1, 1, -1, 0, 1, -1]
        
        metrics = self.evaluator.evaluate(y_true, y_pred)
        
        assert metrics.accuracy == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0
    
    def test_random_predictions(self):
        """Test with partially correct predictions"""
        y_true = [1, 1, -1, 0, 1, -1, 0, 0, 1, -1]
        y_pred = [1, 0, -1, 0, 1, -1, 1, 0, 1, 0]
        
        metrics = self.evaluator.evaluate(y_true, y_pred)
        
        # Should have reasonable accuracy (not 0 or 1)
        assert 0.5 <= metrics.accuracy <= 0.9
        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 <= metrics.f1_score <= 1.0
    
    def test_confusion_matrix_shape(self):
        """Test confusion matrix has correct shape"""
        y_true = [1, -1, 0, 1, -1]
        y_pred = [1, -1, 1, 0, -1]
        
        metrics = self.evaluator.evaluate(y_true, y_pred)
        
        assert metrics.confusion_matrix.shape == (3, 3)
        assert np.sum(metrics.confusion_matrix) == len(y_true)
    
    def test_bonferroni_correction(self):
        """Test Bonferroni p-value correction"""
        y_true = [1, 1, -1, 0, 1, -1]
        y_pred = [1, 0, -1, 0, 1, -1]
        
        metrics = self.evaluator.evaluate(
            y_true, y_pred, correction="bonferroni", n_tests=3
        )
        
        # Adjusted p-value should be larger (more conservative)
        assert metrics.adjusted_p_value >= metrics.p_value
        assert metrics.adjusted_p_value <= 1.0
    
    def test_length_mismatch_raises_error(self):
        """Test that mismatched lengths raise ValueError"""
        y_true = [1, -1, 0]
        y_pred = [1, -1]
        
        with pytest.raises(ValueError, match="Length mismatch"):
            self.evaluator.evaluate(y_true, y_pred)
    
    def test_binary_classification(self):
        """Test binary classification (buy/sell only)"""
        y_true = [1, 0, 1, 1, 0, 0]
        y_pred = [1, 0, 0, 1, 0, 1]
        
        metrics = self.evaluator.evaluate_binary(y_true, y_pred)
        
        assert 0.0 <= metrics.accuracy <= 1.0
        assert isinstance(metrics.confusion_matrix, np.ndarray)
    
    def test_to_dict_conversion(self):
        """Test metrics can be converted to dictionary"""
        y_true = [1, -1, 0, 1]
        y_pred = [1, -1, 1, 1]
        
        metrics = self.evaluator.evaluate(y_true, y_pred)
        metrics_dict = metrics.to_dict()
        
        assert isinstance(metrics_dict, dict)
        assert "accuracy" in metrics_dict
        assert "precision" in metrics_dict
        assert "recall" in metrics_dict
        assert "f1_score" in metrics_dict
        assert "confusion_matrix" in metrics_dict
        assert isinstance(metrics_dict["confusion_matrix"], list)


class TestPredictionAccuracy:
    """Test suite for prediction accuracy computation"""
    
    def test_perfect_directional_predictions(self):
        """Test perfect directional predictions"""
        price_changes = [0.5, -0.3, 0.2, -0.1, 0.8]
        predictions = [1, -1, 1, -1, 1]
        
        accuracy, metrics = compute_prediction_accuracy(price_changes, predictions)
        
        assert accuracy == 100.0
        assert metrics.accuracy == 1.0
    
    def test_mixed_predictions(self):
        """Test mixed correct/incorrect predictions"""
        price_changes = [0.5, -0.3, 0.2, -0.1]
        predictions = [1, -1, -1, 1]  # 2 correct, 2 wrong
        
        accuracy, metrics = compute_prediction_accuracy(price_changes, predictions)
        
        assert accuracy == 50.0
        assert metrics.accuracy == 0.5
    
    def test_zero_price_changes(self):
        """Test handling of zero price changes (hold)"""
        price_changes = [0.0, 0.0, 0.5, -0.3]
        predictions = [0, 0, 1, -1]
        
        accuracy, metrics = compute_prediction_accuracy(price_changes, predictions)
        
        assert accuracy == 100.0


class TestModelComparison:
    """Test suite for comparing multiple models"""
    
    def test_compare_two_models(self):
        """Test comparison of two models"""
        evaluator = ModelEvaluator()
        
        y_true = [1, 1, -1, 0, 1, -1, 0, 0]
        
        model_predictions = {
            "model_a": [1, 0, -1, 0, 1, -1, 0, 0],  # 7/8 correct
            "model_b": [1, 1, -1, 1, 1, -1, 0, 0],  # 6/8 correct
        }
        
        comparison = evaluator.compare_models(y_true, model_predictions)
        
        assert len(comparison) == 2
        assert "model" in comparison.columns
        assert "accuracy" in comparison.columns
        assert "f1_score" in comparison.columns
        
        # Best model should be first
        assert comparison.iloc[0]["model"] == "model_a"
    
    def test_compare_multiple_models(self):
        """Test comparison of multiple models"""
        evaluator = ModelEvaluator()
        
        y_true = [1, -1, 0, 1, -1, 0] * 5  # 30 samples
        
        model_predictions = {
            "asmbtr": y_true,  # Perfect
            "ml_model": [1 if x == 1 else -1 for x in y_true],  # No holds
            "random": [1, -1, 0] * 10,  # Random pattern
        }
        
        comparison = evaluator.compare_models(y_true, model_predictions)
        
        assert len(comparison) == 3
        # ASMBTR should win with perfect predictions
        assert comparison.iloc[0]["model"] == "asmbtr"
        assert comparison.iloc[0]["accuracy"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
