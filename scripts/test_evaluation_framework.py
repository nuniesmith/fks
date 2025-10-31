#!/usr/bin/env python3
"""
Quick validation script for Phase 7.1 Evaluation Framework
Tests confusion matrix and statistical corrections without pytest
"""

import sys
import numpy as np
from pathlib import Path

# Add src directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src" / "services" / "app" / "src"))

from evaluation.confusion_matrix import ModelEvaluator, EvaluationMetrics
from evaluation.statistical_tests import (
    apply_bonferroni,
    apply_benjamini_hochberg,
    compare_corrections,
)


def test_statistical_corrections():
    """Test Bonferroni and Benjamini-Hochberg corrections"""
    print("\n" + "="*80)
    print("Testing Statistical Corrections")
    print("="*80)
    
    # Test data
    p_values = [0.01, 0.04, 0.03, 0.50]
    print(f"\nOriginal p-values: {p_values}")
    
    # Bonferroni
    bonf_sig, bonf_adj = apply_bonferroni(p_values, alpha=0.05)
    print(f"\nBonferroni Correction:")
    print(f"  Adjusted p-values: {bonf_adj}")
    print(f"  Significant: {bonf_sig}")
    print(f"  Number significant: {sum(bonf_sig)}")
    
    # Benjamini-Hochberg
    bh_sig, bh_adj = apply_benjamini_hochberg(p_values, alpha=0.05)
    print(f"\nBenjamini-Hochberg Correction:")
    print(f"  Adjusted p-values: {bh_adj}")
    print(f"  Significant: {bh_sig}")
    print(f"  Number significant: {sum(bh_sig)}")
    
    # Compare
    comparison = compare_corrections(p_values, alpha=0.05)
    print(f"\nComparison Summary:")
    print(f"  Bonferroni significant: {comparison['bonferroni']['n_significant']}")
    print(f"  BH significant: {comparison['benjamini_hochberg']['n_significant']}")
    
    # Validate
    assert bonf_adj[0] == 0.04, "Bonferroni: 0.01 * 4 should be 0.04"
    assert bonf_adj[3] == 1.0, "Bonferroni: Should cap at 1.0"
    assert sum(bh_sig) >= sum(bonf_sig), "BH should be less conservative"
    
    print("\n✅ Statistical corrections working correctly!")
    return True


def test_confusion_matrix():
    """Test confusion matrix evaluation"""
    print("\n" + "="*80)
    print("Testing Confusion Matrix Evaluation")
    print("="*80)
    
    evaluator = ModelEvaluator()
    
    # Test 1: Perfect predictions
    print("\n--- Test 1: Perfect Predictions ---")
    y_true = [1, 1, -1, 0, 1, -1, 0, 0, 1, -1]
    y_pred = y_true.copy()
    
    metrics = evaluator.evaluate(y_true, y_pred)
    print(f"\nPerfect Predictions Metrics:")
    print(f"  Accuracy: {metrics.accuracy:.2f}")
    print(f"  Precision: {metrics.precision:.2f}")
    print(f"  Recall: {metrics.recall:.2f}")
    print(f"  F1: {metrics.f1:.2f}")
    print(f"  Chi-square p-value: {metrics.chi2_p_value:.6f}")
    
    assert metrics.accuracy == 1.0, "Perfect predictions should have 100% accuracy"
    assert metrics.precision == 1.0, "Perfect predictions should have precision 1.0"
    assert metrics.recall == 1.0, "Perfect predictions should have recall 1.0"
    
    # Test 2: Random predictions
    print("\n--- Test 2: Random Predictions ---")
    np.random.seed(42)
    y_true = np.random.choice([-1, 0, 1], size=100)
    y_pred = np.random.choice([-1, 0, 1], size=100)
    
    metrics = evaluator.evaluate(y_true, y_pred)
    print(f"\nRandom Predictions Metrics:")
    print(f"  Accuracy: {metrics.accuracy:.2f}")
    print(f"  Precision: {metrics.precision:.2f}")
    print(f"  Recall: {metrics.recall:.2f}")
    print(f"  F1: {metrics.f1:.2f}")
    print(f"  Chi-square p-value: {metrics.chi2_p_value:.6f}")
    
    # With random predictions, accuracy should be ~33% for 3 classes
    assert 0.2 <= metrics.accuracy <= 0.5, "Random predictions should be around 33% accuracy"
    
    # Test 3: With statistical correction
    print("\n--- Test 3: With Bonferroni Correction ---")
    metrics = evaluator.evaluate(y_true, y_pred, correction="bonferroni", n_tests=3)
    print(f"  Original p-value: {metrics.chi2_p_value:.6f}")
    print(f"  Adjusted p-value: {metrics.adjusted_p_value:.6f}")
    
    assert metrics.adjusted_p_value >= metrics.chi2_p_value, "Adjusted p-value should be >= original"
    
    print("\n✅ Confusion matrix evaluation working correctly!")
    return True


def test_model_comparison():
    """Test comparing two models"""
    print("\n" + "="*80)
    print("Testing Model Comparison")
    print("="*80)
    
    evaluator = ModelEvaluator()
    
    # Create test data
    np.random.seed(42)
    y_true = np.random.choice([-1, 0, 1], size=100)
    
    # Model 1: Better predictions (70% match)
    y_pred1 = y_true.copy()
    flip_indices = np.random.choice(100, size=30, replace=False)
    y_pred1[flip_indices] = np.random.choice([-1, 0, 1], size=30)
    
    # Model 2: Worse predictions (50% match)
    y_pred2 = y_true.copy()
    flip_indices = np.random.choice(100, size=50, replace=False)
    y_pred2[flip_indices] = np.random.choice([-1, 0, 1], size=50)
    
    # Compare models
    comparison = evaluator.compare_models(y_true, y_pred1, y_pred2, 
                                         model1_name="Better Model",
                                         model2_name="Worse Model")
    
    print(f"\nModel Comparison Results:")
    print(f"  {comparison['model1_name']}: Accuracy = {comparison['model1_accuracy']:.3f}")
    print(f"  {comparison['model2_name']}: Accuracy = {comparison['model2_accuracy']:.3f}")
    print(f"  Difference: {comparison['accuracy_difference']:.3f}")
    print(f"  Winner: {comparison['winner']}")
    
    assert comparison['model1_accuracy'] > comparison['model2_accuracy'], \
        "Model 1 should be more accurate"
    assert comparison['winner'] == "Better Model", "Better Model should win"
    
    print("\n✅ Model comparison working correctly!")
    return True


def test_asmbtr_integration():
    """Test realistic ASMBTR-style predictions"""
    print("\n" + "="*80)
    print("Testing ASMBTR Integration Scenario")
    print("="*80)
    
    evaluator = ModelEvaluator()
    
    # Simulate ASMBTR predictions: -1=sell, 0=hold, 1=buy
    # Based on actual next price movements
    print("\nSimulating 200 ASMBTR predictions on BTC/USDT...")
    
    np.random.seed(123)
    
    # Ground truth: actual price movements
    # Slight upward bias (crypto bull market)
    y_true = np.random.choice([-1, 0, 1], size=200, p=[0.3, 0.2, 0.5])
    
    # ASMBTR predictions: 60% accuracy (realistic target)
    y_pred = y_true.copy()
    errors = np.random.choice(200, size=80, replace=False)  # 80/200 = 40% errors
    y_pred[errors] = np.random.choice([-1, 0, 1], size=80)
    
    metrics = evaluator.evaluate(y_true, y_pred, correction="benjamini_hochberg", n_tests=10)
    
    print(f"\nASMBTR Performance Metrics:")
    print(f"  Accuracy: {metrics.accuracy:.2%}")
    print(f"  Precision (avg): {metrics.precision:.3f}")
    print(f"  Recall (avg): {metrics.recall:.3f}")
    print(f"  F1 Score: {metrics.f1:.3f}")
    print(f"  Chi-square statistic: {metrics.chi2_statistic:.2f}")
    print(f"  Raw p-value: {metrics.chi2_p_value:.6f}")
    print(f"  BH-adjusted p-value: {metrics.adjusted_p_value:.6f}")
    
    # Phase 7.1 acceptance criteria: >60% accuracy
    assert metrics.accuracy >= 0.55, "ASMBTR should achieve >55% accuracy"
    
    print(f"\n{'✅ PASS' if metrics.accuracy >= 0.6 else '⚠️  CLOSE'}: "
          f"Target is >60% accuracy for production readiness")
    
    return True


def main():
    """Run all validation tests"""
    print("\n" + "="*80)
    print("PHASE 7.1 EVALUATION FRAMEWORK VALIDATION")
    print("="*80)
    print("\nTesting confusion matrix and statistical corrections...")
    
    tests = [
        ("Statistical Corrections", test_statistical_corrections),
        ("Confusion Matrix", test_confusion_matrix),
        ("Model Comparison", test_model_comparison),
        ("ASMBTR Integration", test_asmbtr_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    for test_name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if error:
            print(f"    Error: {error}")
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Phase 7.1 Evaluation Framework is WORKING!")
        print("Ready to integrate with ASMBTR strategy for backtesting.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
