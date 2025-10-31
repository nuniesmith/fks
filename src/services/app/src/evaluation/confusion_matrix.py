"""
Confusion Matrix and Model Evaluation

Implements comprehensive evaluation metrics for trading signal predictions
including confusion matrices, classification reports, and statistical corrections.
"""

from typing import Dict, List, Literal, Optional, Tuple
import numpy as np
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
)
from scipy.stats import chi2_contingency


SignalType = Literal[-1, 0, 1]  # sell, hold, buy


@dataclass
class EvaluationMetrics:
    """Container for model evaluation metrics"""
    
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    confusion_matrix: np.ndarray
    classification_report: str
    chi2_statistic: float
    p_value: float
    adjusted_p_value: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary"""
        return {
            "accuracy": float(self.accuracy),
            "precision": float(self.precision),
            "recall": float(self.recall),
            "f1_score": float(self.f1_score),
            "confusion_matrix": self.confusion_matrix.tolist(),
            "classification_report": self.classification_report,
            "chi2_statistic": float(self.chi2_statistic),
            "p_value": float(self.p_value),
            "adjusted_p_value": float(self.adjusted_p_value) if self.adjusted_p_value else None,
        }


class ModelEvaluator:
    """
    Comprehensive model evaluation with confusion matrices and statistical testing.
    
    Supports:
    - Binary classification (buy/sell)
    - Multi-class classification (buy/sell/hold)
    - Statistical significance testing (chi-square)
    - P-value corrections (Bonferroni, Benjamini-Hochberg)
    
    Example:
        >>> evaluator = ModelEvaluator()
        >>> y_true = [1, 1, -1, 0, 1, -1, 0, 0, 1, -1]
        >>> y_pred = [1, 0, -1, 0, 1, -1, 1, 0, 1, 0]
        >>> metrics = evaluator.evaluate(y_true, y_pred, correction="bonferroni", n_tests=3)
        >>> print(f"Accuracy: {metrics.accuracy:.2%}")
        >>> print(f"Adjusted p-value: {metrics.adjusted_p_value}")
    """
    
    def __init__(self):
        self.labels = [-1, 0, 1]  # sell, hold, buy
        self.target_names = ["Sell", "Hold", "Buy"]
    
    def evaluate(
        self,
        y_true: List[SignalType],
        y_pred: List[SignalType],
        correction: Optional[Literal["bonferroni", "benjamini_hochberg"]] = None,
        n_tests: int = 1,
    ) -> EvaluationMetrics:
        """
        Evaluate model predictions with comprehensive metrics.
        
        Args:
            y_true: Ground truth labels (-1: sell, 0: hold, 1: buy)
            y_pred: Predicted labels (-1: sell, 0: hold, 1: buy)
            correction: P-value correction method ("bonferroni" or "benjamini_hochberg")
            n_tests: Number of tests for correction (default: 1, no correction)
        
        Returns:
            EvaluationMetrics with all computed metrics
        
        Raises:
            ValueError: If y_true and y_pred have different lengths
        """
        if len(y_true) != len(y_pred):
            raise ValueError(
                f"Length mismatch: y_true ({len(y_true)}) != y_pred ({len(y_pred)})"
            )
        
        # Convert to numpy arrays
        y_true_arr = np.array(y_true)
        y_pred_arr = np.array(y_pred)
        
        # Compute confusion matrix
        cm = confusion_matrix(y_true_arr, y_pred_arr, labels=self.labels)
        
        # Compute metrics (weighted average for multi-class)
        accuracy = accuracy_score(y_true_arr, y_pred_arr)
        precision = precision_score(
            y_true_arr, y_pred_arr, labels=self.labels, average="weighted", zero_division=0
        )
        recall = recall_score(
            y_true_arr, y_pred_arr, labels=self.labels, average="weighted", zero_division=0
        )
        f1 = f1_score(
            y_true_arr, y_pred_arr, labels=self.labels, average="weighted", zero_division=0
        )
        
        # Classification report
        report = classification_report(
            y_true_arr,
            y_pred_arr,
            labels=self.labels,
            target_names=self.target_names,
            zero_division=0,
        )
        
        # Chi-square test for independence
        chi2, p_value, _, _ = chi2_contingency(cm)
        
        # Apply p-value correction if requested
        adjusted_p = None
        if correction and n_tests > 1:
            if correction == "bonferroni":
                adjusted_p = min(p_value * n_tests, 1.0)
            elif correction == "benjamini_hochberg":
                # For single p-value, BH is same as original
                # Full BH needs sorted p-values from multiple tests
                adjusted_p = p_value
        
        return EvaluationMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            confusion_matrix=cm,
            classification_report=report,
            chi2_statistic=chi2,
            p_value=p_value,
            adjusted_p_value=adjusted_p,
        )
    
    def evaluate_binary(
        self,
        y_true: List[int],
        y_pred: List[int],
    ) -> EvaluationMetrics:
        """
        Evaluate binary classification (buy=1, sell=0).
        
        Simplified version for strategies that only generate buy/sell signals.
        """
        # Map to -1/1 for consistency
        y_true_mapped = [1 if y == 1 else -1 for y in y_true]
        y_pred_mapped = [1 if y == 1 else -1 for y in y_pred]
        
        return self.evaluate(y_true_mapped, y_pred_mapped)
    
    def evaluate_time_series(
        self,
        predictions_df: pd.DataFrame,
        actual_df: pd.DataFrame,
        signal_col: str = "signal",
        actual_col: str = "actual_signal",
    ) -> EvaluationMetrics:
        """
        Evaluate predictions from time-series data.
        
        Args:
            predictions_df: DataFrame with predicted signals
            actual_df: DataFrame with actual outcomes
            signal_col: Column name for predicted signals
            actual_col: Column name for actual signals
        
        Returns:
            EvaluationMetrics
        """
        # Merge on index (timestamps)
        merged = predictions_df.join(actual_df, how="inner", rsuffix="_actual")
        
        y_true = merged[actual_col].tolist()
        y_pred = merged[signal_col].tolist()
        
        return self.evaluate(y_true, y_pred)
    
    def compare_models(
        self,
        y_true: List[SignalType],
        model_predictions: Dict[str, List[SignalType]],
    ) -> pd.DataFrame:
        """
        Compare multiple models on the same dataset.
        
        Args:
            y_true: Ground truth labels
            model_predictions: Dict mapping model names to predictions
        
        Returns:
            DataFrame comparing model metrics
        """
        results = []
        
        for model_name, y_pred in model_predictions.items():
            metrics = self.evaluate(y_true, y_pred)
            results.append({
                "model": model_name,
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "p_value": metrics.p_value,
            })
        
        return pd.DataFrame(results).sort_values("f1_score", ascending=False)


def compute_prediction_accuracy(
    price_changes: List[float],
    predicted_directions: List[SignalType],
) -> Tuple[float, EvaluationMetrics]:
    """
    Compute accuracy of directional predictions.
    
    Args:
        price_changes: Actual price changes (positive = up, negative = down, 0 = no change)
        predicted_directions: Predicted directions (-1: sell, 0: hold, 1: buy)
    
    Returns:
        Tuple of (accuracy_percentage, full_metrics)
    """
    # Convert price changes to signals
    actual_signals = [
        1 if change > 0 else -1 if change < 0 else 0
        for change in price_changes
    ]
    
    evaluator = ModelEvaluator()
    metrics = evaluator.evaluate(actual_signals, predicted_directions)
    
    return metrics.accuracy * 100, metrics


if __name__ == "__main__":
    # Example usage
    print("Testing ModelEvaluator...")
    
    # Sample data: 10 predictions
    y_true = [1, 1, -1, 0, 1, -1, 0, 0, 1, -1]
    y_pred = [1, 0, -1, 0, 1, -1, 1, 0, 1, 0]
    
    evaluator = ModelEvaluator()
    
    # Without correction
    print("\n=== Without P-value Correction ===")
    metrics = evaluator.evaluate(y_true, y_pred)
    print(f"Accuracy: {metrics.accuracy:.2%}")
    print(f"Precision: {metrics.precision:.2%}")
    print(f"Recall: {metrics.recall:.2%}")
    print(f"F1 Score: {metrics.f1_score:.2%}")
    print(f"P-value: {metrics.p_value:.4f}")
    print("\nConfusion Matrix:")
    print(metrics.confusion_matrix)
    print("\nClassification Report:")
    print(metrics.classification_report)
    
    # With Bonferroni correction (3 tests)
    print("\n=== With Bonferroni Correction (n=3) ===")
    metrics_bonf = evaluator.evaluate(y_true, y_pred, correction="bonferroni", n_tests=3)
    print(f"Original p-value: {metrics_bonf.p_value:.4f}")
    print(f"Adjusted p-value: {metrics_bonf.adjusted_p_value:.4f}")
    print(f"Significant at α=0.05: {metrics_bonf.adjusted_p_value < 0.05}")
