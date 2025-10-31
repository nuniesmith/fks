"""
ASMBTR Evaluation Integration

Integrates the Phase 7.1 evaluation framework with ASMBTR backtest results
to provide statistical validation of prediction accuracy.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

# Add evaluation module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evaluation.confusion_matrix import ModelEvaluator, EvaluationMetrics
from evaluation.statistical_tests import (
    apply_bonferroni,
    apply_benjamini_hochberg,
    compare_corrections,
)


@dataclass
class ASMBTREvaluationResult:
    """Results from ASMBTR evaluation"""
    
    metrics: EvaluationMetrics
    total_predictions: int
    correct_predictions: int
    directional_accuracy: float
    hold_accuracy: float
    statistical_significance: bool
    adjusted_p_value: float
    correction_method: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "directional_accuracy": float(self.directional_accuracy),
            "hold_accuracy": float(self.hold_accuracy),
            "statistical_significance": self.statistical_significance,
            "adjusted_p_value": float(self.adjusted_p_value),
            "correction_method": self.correction_method,
            "evaluation_metrics": self.metrics.to_dict(),
        }


class ASMBTREvaluator:
    """
    Evaluates ASMBTR prediction accuracy using confusion matrices
    and statistical testing.
    
    Integrates Phase 7.1 evaluation framework with ASMBTR backtest results.
    """
    
    def __init__(self):
        self.evaluator = ModelEvaluator()
    
    def evaluate_backtest_predictions(
        self,
        backtest_df: pd.DataFrame,
        prediction_col: str = "predicted_signal",
        actual_col: str = "actual_movement",
        correction: str = "bonferroni",
        n_tests: int = 1,
    ) -> ASMBTREvaluationResult:
        """
        Evaluate ASMBTR predictions from backtest DataFrame.
        
        Args:
            backtest_df: DataFrame with predictions and actual movements
            prediction_col: Column name for ASMBTR predicted signals (-1, 0, 1)
            actual_col: Column name for actual price movements (-1, 0, 1)
            correction: P-value correction method ("bonferroni" or "benjamini_hochberg")
            n_tests: Number of hypothesis tests (for multiple testing correction)
        
        Returns:
            ASMBTREvaluationResult with comprehensive metrics
        """
        # Extract predictions and actuals
        y_pred = backtest_df[prediction_col].tolist()
        y_true = backtest_df[actual_col].tolist()
        
        # Run evaluation
        metrics = self.evaluator.evaluate(
            y_true, y_pred, 
            correction=correction, 
            n_tests=n_tests
        )
        
        # Calculate additional ASMBTR-specific metrics
        total_predictions = len(y_pred)
        correct_predictions = sum(p == t for p, t in zip(y_pred, y_true))
        directional_accuracy = correct_predictions / total_predictions
        
        # Calculate hold accuracy (how often we correctly predicted no movement)
        hold_predictions = [(p, t) for p, t in zip(y_pred, y_true) if p == 0]
        hold_accuracy = (
            sum(p == t for p, t in hold_predictions) / len(hold_predictions)
            if hold_predictions else 0.0
        )
        
        # Statistical significance (using adjusted p-value)
        alpha = 0.05
        statistical_significance = (
            metrics.adjusted_p_value < alpha 
            if metrics.adjusted_p_value is not None 
            else metrics.p_value < alpha
        )
        
        return ASMBTREvaluationResult(
            metrics=metrics,
            total_predictions=total_predictions,
            correct_predictions=correct_predictions,
            directional_accuracy=directional_accuracy,
            hold_accuracy=hold_accuracy,
            statistical_significance=statistical_significance,
            adjusted_p_value=(
                metrics.adjusted_p_value 
                if metrics.adjusted_p_value is not None 
                else metrics.p_value
            ),
            correction_method=correction,
        )
    
    def convert_price_changes_to_signals(
        self,
        price_changes: List[float],
        threshold: float = 0.0,
    ) -> List[int]:
        """
        Convert price changes to trading signals (-1, 0, 1).
        
        Args:
            price_changes: List of price change percentages
            threshold: Minimum change to consider as movement (default: 0.0)
        
        Returns:
            List of signals: 1 (buy/up), 0 (hold/neutral), -1 (sell/down)
        """
        signals = []
        for change in price_changes:
            if abs(change) < threshold:
                signals.append(0)  # Hold
            elif change > 0:
                signals.append(1)  # Buy
            else:
                signals.append(-1)  # Sell
        return signals
    
    def evaluate_state_predictions(
        self,
        states: List[str],
        predictions: List[int],
        actual_outcomes: List[int],
        correction: str = "bonferroni",
    ) -> Dict:
        """
        Evaluate predictions per ASMBTR state.
        
        Analyzes which states produce the most accurate predictions.
        
        Args:
            states: List of ASMBTR state strings (e.g., "10110011")
            predictions: List of predicted movements (-1, 0, 1)
            actual_outcomes: List of actual movements (-1, 0, 1)
            correction: P-value correction method
        
        Returns:
            Dict mapping states to evaluation metrics
        """
        # Group by state
        state_groups = {}
        for state, pred, actual in zip(states, predictions, actual_outcomes):
            if state not in state_groups:
                state_groups[state] = {"predictions": [], "actuals": []}
            state_groups[state]["predictions"].append(pred)
            state_groups[state]["actuals"].append(actual)
        
        # Evaluate each state
        state_results = {}
        for state, data in state_groups.items():
            if len(data["predictions"]) < 5:  # Skip states with too few samples
                continue
            
            metrics = self.evaluator.evaluate(
                data["actuals"],
                data["predictions"],
                correction=correction,
                n_tests=len(state_groups),  # Multiple states = multiple tests
            )
            
            state_results[state] = {
                "sample_count": len(data["predictions"]),
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "p_value": metrics.p_value,
                "adjusted_p_value": metrics.adjusted_p_value,
            }
        
        # Sort by accuracy
        sorted_results = dict(
            sorted(
                state_results.items(),
                key=lambda x: x[1]["accuracy"],
                reverse=True,
            )
        )
        
        return sorted_results
    
    def compare_asmbtr_variants(
        self,
        y_true: List[int],
        variant_predictions: Dict[str, List[int]],
    ) -> pd.DataFrame:
        """
        Compare different ASMBTR configurations.
        
        Args:
            y_true: Ground truth movements
            variant_predictions: Dict mapping variant names to predictions
                e.g., {"depth_6": [...], "depth_8": [...], "depth_10": [...]}
        
        Returns:
            DataFrame comparing variant performance
        """
        return self.evaluator.compare_models(y_true, variant_predictions)
    
    def generate_evaluation_report(
        self,
        result: ASMBTREvaluationResult,
        save_path: Optional[Path] = None,
    ) -> str:
        """
        Generate human-readable evaluation report.
        
        Args:
            result: ASMBTREvaluationResult from evaluation
            save_path: Optional path to save report
        
        Returns:
            Report as string
        """
        report_lines = [
            "=" * 80,
            "ASMBTR EVALUATION REPORT",
            "=" * 80,
            f"Generated: {datetime.now().isoformat()}",
            "",
            "OVERALL METRICS",
            "-" * 80,
            f"Total Predictions: {result.total_predictions}",
            f"Correct Predictions: {result.correct_predictions}",
            f"Directional Accuracy: {result.directional_accuracy:.2%}",
            f"Hold Accuracy: {result.hold_accuracy:.2%}",
            "",
            "CLASSIFICATION METRICS",
            "-" * 80,
            f"Overall Accuracy: {result.metrics.accuracy:.2%}",
            f"Precision (avg): {result.metrics.precision:.3f}",
            f"Recall (avg): {result.metrics.recall:.3f}",
            f"F1 Score: {result.metrics.f1_score:.3f}",
            "",
            "STATISTICAL SIGNIFICANCE",
            "-" * 80,
            f"Correction Method: {result.correction_method}",
            f"Chi-Square Statistic: {result.metrics.chi2_statistic:.4f}",
            f"Original P-value: {result.metrics.p_value:.6f}",
            f"Adjusted P-value: {result.adjusted_p_value:.6f}",
            f"Statistically Significant (α=0.05): {result.statistical_significance}",
            "",
            "CONFUSION MATRIX",
            "-" * 80,
            f"{result.metrics.confusion_matrix}",
            "",
            "CLASSIFICATION REPORT",
            "-" * 80,
            result.metrics.classification_report,
            "=" * 80,
        ]
        
        report = "\n".join(report_lines)
        
        if save_path:
            save_path.write_text(report)
        
        return report


def example_integration():
    """
    Example of integrating evaluation framework with ASMBTR backtest.
    
    This demonstrates how to use the evaluation framework with
    real or simulated ASMBTR predictions.
    """
    print("\n" + "=" * 80)
    print("ASMBTR EVALUATION FRAMEWORK INTEGRATION EXAMPLE")
    print("=" * 80)
    
    # Simulate ASMBTR backtest results
    np.random.seed(42)
    n_samples = 500
    
    # Ground truth: actual price movements
    # Simulate crypto market with slight upward bias
    actual_movements = np.random.choice(
        [-1, 0, 1], 
        size=n_samples, 
        p=[0.30, 0.20, 0.50]  # 50% up, 30% down, 20% sideways
    )
    
    # ASMBTR predictions: 65% accuracy (realistic target)
    asmbtr_predictions = actual_movements.copy()
    error_indices = np.random.choice(n_samples, size=int(0.35 * n_samples), replace=False)
    asmbtr_predictions[error_indices] = np.random.choice([-1, 0, 1], size=len(error_indices))
    
    # Create DataFrame
    backtest_df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n_samples, freq="1H"),
        "predicted_signal": asmbtr_predictions,
        "actual_movement": actual_movements,
        "state": [f"state_{i % 20:02d}" for i in range(n_samples)],  # 20 different states
    })
    
    # Initialize evaluator
    evaluator = ASMBTREvaluator()
    
    # 1. Overall evaluation
    print("\n1. OVERALL EVALUATION")
    print("-" * 80)
    result = evaluator.evaluate_backtest_predictions(
        backtest_df,
        correction="bonferroni",
        n_tests=3,  # Testing on 3 different pairs, for example
    )
    
    print(f"Directional Accuracy: {result.directional_accuracy:.2%}")
    print(f"F1 Score: {result.metrics.f1_score:.3f}")
    print(f"Statistically Significant: {result.statistical_significance}")
    print(f"Adjusted P-value: {result.adjusted_p_value:.6f}")
    
    # 2. Per-state evaluation
    print("\n2. PER-STATE EVALUATION (Top 5 States)")
    print("-" * 80)
    state_results = evaluator.evaluate_state_predictions(
        backtest_df["state"].tolist(),
        backtest_df["predicted_signal"].tolist(),
        backtest_df["actual_movement"].tolist(),
        correction="benjamini_hochberg",
    )
    
    for i, (state, metrics) in enumerate(list(state_results.items())[:5]):
        print(f"\n{state}:")
        print(f"  Samples: {metrics['sample_count']}")
        print(f"  Accuracy: {metrics['accuracy']:.2%}")
        print(f"  F1 Score: {metrics['f1_score']:.3f}")
    
    # 3. Compare variants
    print("\n3. COMPARING ASMBTR VARIANTS")
    print("-" * 80)
    
    # Simulate different configurations
    depth_6_pred = actual_movements.copy()
    error_idx = np.random.choice(n_samples, size=int(0.40 * n_samples), replace=False)
    depth_6_pred[error_idx] = np.random.choice([-1, 0, 1], size=len(error_idx))
    
    depth_10_pred = actual_movements.copy()
    error_idx = np.random.choice(n_samples, size=int(0.33 * n_samples), replace=False)
    depth_10_pred[error_idx] = np.random.choice([-1, 0, 1], size=len(error_idx))
    
    variants = {
        "ASMBTR-Depth-6": depth_6_pred.tolist(),
        "ASMBTR-Depth-8": asmbtr_predictions.tolist(),
        "ASMBTR-Depth-10": depth_10_pred.tolist(),
    }
    
    comparison = evaluator.compare_asmbtr_variants(
        actual_movements.tolist(),
        variants,
    )
    
    print(comparison.to_string(index=False))
    
    # 4. Generate full report
    print("\n4. GENERATING FULL REPORT")
    print("-" * 80)
    report = evaluator.generate_evaluation_report(result)
    print(report)
    
    print("\n✅ Integration example complete!")
    print("\nNext steps:")
    print("  1. Use with real ASMBTR backtest results")
    print("  2. Test on BTC/ETH data (2023-2024)")
    print("  3. Compare against other strategies")
    print("  4. Integrate with Grafana dashboards")


if __name__ == "__main__":
    example_integration()
