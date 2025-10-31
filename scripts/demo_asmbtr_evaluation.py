#!/usr/bin/env python3
"""
ASMBTR Evaluation Integration Demo

Demonstrates practical usage of Phase 7.1 evaluation framework
with ASMBTR backtest results.

Usage:
    python scripts/demo_asmbtr_evaluation.py
    
or in Docker:
    docker-compose exec fks_app python /app/scripts/demo_asmbtr_evaluation.py
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# Add paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src" / "services" / "app" / "src"))

from strategies.asmbtr.evaluation import ASMBTREvaluator
from evaluation.statistical_tests import compare_corrections


def demo_basic_evaluation():
    """Demo 1: Basic ASMBTR evaluation"""
    print("\n" + "="*80)
    print("DEMO 1: BASIC ASMBTR EVALUATION")
    print("="*80)
    
    # Simulate ASMBTR predictions on BTC/USDT
    np.random.seed(42)
    n_bars = 1000  # 1000 hourly bars ~= 41 days
    
    print(f"\nSimulating {n_bars} predictions on BTC/USDT (hourly bars)...")
    
    # Ground truth (actual price movements)
    # Bull market scenario: 55% up, 25% down, 20% sideways
    actual_movements = np.random.choice(
        [-1, 0, 1],
        size=n_bars,
        p=[0.25, 0.20, 0.55]
    )
    
    # ASMBTR predictions with 68% accuracy
    asmbtr_pred = actual_movements.copy()
    error_idx = np.random.choice(n_bars, size=320, replace=False)  # 32% errors
    asmbtr_pred[error_idx] = np.random.choice([-1, 0, 1], size=320)
    
    # Create backtest DataFrame
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n_bars, freq="1h"),
        "predicted_signal": asmbtr_pred,
        "actual_movement": actual_movements,
    })
    
    # Evaluate
    evaluator = ASMBTREvaluator()
    result = evaluator.evaluate_backtest_predictions(
        df,
        correction="bonferroni",
        n_tests=1,  # Single backtest
    )
    
    # Display results
    print(f"\n📊 RESULTS:")
    print(f"   Directional Accuracy: {result.directional_accuracy:.2%}")
    print(f"   Precision: {result.metrics.precision:.3f}")
    print(f"   Recall: {result.metrics.recall:.3f}")
    print(f"   F1 Score: {result.metrics.f1_score:.3f}")
    print(f"   Statistical Significance: {'✅ Yes' if result.statistical_significance else '❌ No'}")
    print(f"   Adjusted P-value: {result.adjusted_p_value:.6f}")
    
    # Show confusion matrix
    print(f"\n📈 CONFUSION MATRIX:")
    print(f"   {result.metrics.confusion_matrix}")
    print(f"\n   Rows: Actual | Columns: Predicted")
    print(f"   [0]: Sell (-1) | [1]: Hold (0) | [2]: Buy (1)")


def demo_multiple_testing_correction():
    """Demo 2: Multiple testing with p-value corrections"""
    print("\n" + "="*80)
    print("DEMO 2: MULTIPLE TESTING CORRECTION")
    print("="*80)
    
    print("\nScenario: Testing ASMBTR on 5 different pairs")
    print("BTC/USDT, ETH/USDT, BNB/USDT, ADA/USDT, SOL/USDT")
    
    np.random.seed(123)
    evaluator = ASMBTREvaluator()
    
    pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "ADA/USDT", "SOL/USDT"]
    results_bonf = []
    results_bh = []
    raw_p_values = []
    
    for pair in pairs:
        # Simulate predictions
        n_bars = 500
        actual = np.random.choice([-1, 0, 1], size=n_bars, p=[0.30, 0.20, 0.50])
        predicted = actual.copy()
        errors = np.random.choice(n_bars, size=int(0.33 * n_bars), replace=False)
        predicted[errors] = np.random.choice([-1, 0, 1], size=len(errors))
        
        df = pd.DataFrame({
            "predicted_signal": predicted,
            "actual_movement": actual,
        })
        
        # Evaluate with Bonferroni
        result_bonf = evaluator.evaluate_backtest_predictions(
            df, correction="bonferroni", n_tests=5
        )
        results_bonf.append(result_bonf)
        
        # Evaluate with BH
        result_bh = evaluator.evaluate_backtest_predictions(
            df, correction="benjamini_hochberg", n_tests=5
        )
        results_bh.append(result_bh)
        
        raw_p_values.append(result_bonf.metrics.p_value)
    
    # Display comparison
    print(f"\n📊 COMPARISON OF CORRECTION METHODS:")
    print(f"\n{'Pair':<15} {'Accuracy':<10} {'Raw p-val':<12} {'Bonferroni':<12} {'BH (FDR)':<12} {'Significant'}")
    print("-" * 80)
    
    for i, pair in enumerate(pairs):
        sig_bonf = "✅" if results_bonf[i].statistical_significance else "❌"
        sig_bh = "✅" if results_bh[i].statistical_significance else "❌"
        
        print(f"{pair:<15} {results_bonf[i].directional_accuracy:>6.2%}    "
              f"{raw_p_values[i]:>10.6f}  "
              f"{results_bonf[i].adjusted_p_value:>10.6f}  "
              f"{results_bh[i].adjusted_p_value:>10.6f}  "
              f"Bonf:{sig_bonf} BH:{sig_bh}")
    
    # Use comparison utility
    print(f"\n📈 STATISTICAL CORRECTION SUMMARY:")
    correction_comparison = compare_corrections(raw_p_values, alpha=0.05)
    print(f"   Bonferroni significant: {correction_comparison['bonferroni']['n_significant']}/5")
    print(f"   BH significant: {correction_comparison['benjamini_hochberg']['n_significant']}/5")
    print(f"\n   💡 BH is less conservative, finds more significant results")


def demo_variant_comparison():
    """Demo 3: Comparing ASMBTR variants"""
    print("\n" + "="*80)
    print("DEMO 3: COMPARING ASMBTR CONFIGURATIONS")
    print("="*80)
    
    print("\nScenario: Comparing different BTR tree depths")
    print("Testing depths: 6, 8, 10, 12")
    
    np.random.seed(456)
    n_bars = 800
    
    # Ground truth
    actual = np.random.choice([-1, 0, 1], size=n_bars, p=[0.30, 0.20, 0.50])
    
    # Simulate different depths with varying accuracy
    # Deeper trees might overfit or underfit
    variants = {}
    
    # Depth 6: 62% accuracy (underfitting)
    pred_6 = actual.copy()
    err = np.random.choice(n_bars, size=int(0.38 * n_bars), replace=False)
    pred_6[err] = np.random.choice([-1, 0, 1], size=len(err))
    variants["ASMBTR-Depth-6"] = pred_6.tolist()
    
    # Depth 8: 70% accuracy (optimal)
    pred_8 = actual.copy()
    err = np.random.choice(n_bars, size=int(0.30 * n_bars), replace=False)
    pred_8[err] = np.random.choice([-1, 0, 1], size=len(err))
    variants["ASMBTR-Depth-8"] = pred_8.tolist()
    
    # Depth 10: 68% accuracy (slight overfitting)
    pred_10 = actual.copy()
    err = np.random.choice(n_bars, size=int(0.32 * n_bars), replace=False)
    pred_10[err] = np.random.choice([-1, 0, 1], size=len(err))
    variants["ASMBTR-Depth-10"] = pred_10.tolist()
    
    # Depth 12: 64% accuracy (overfitting)
    pred_12 = actual.copy()
    err = np.random.choice(n_bars, size=int(0.36 * n_bars), replace=False)
    pred_12[err] = np.random.choice([-1, 0, 1], size=len(err))
    variants["ASMBTR-Depth-12"] = pred_12.tolist()
    
    # Compare
    evaluator = ASMBTREvaluator()
    comparison = evaluator.compare_asmbtr_variants(actual.tolist(), variants)
    
    print(f"\n📊 VARIANT COMPARISON (sorted by F1 score):")
    print("\n" + comparison.to_string(index=False))
    
    print(f"\n💡 Interpretation:")
    print(f"   Best performer: {comparison.iloc[0]['model']}")
    print(f"   F1 Score: {comparison.iloc[0]['f1_score']:.3f}")
    print(f"   Accuracy: {comparison.iloc[0]['accuracy']:.2%}")
    print(f"\n   ⚠️  Deeper isn't always better - watch for overfitting!")


def demo_state_analysis():
    """Demo 4: Per-state performance analysis"""
    print("\n" + "="*80)
    print("DEMO 4: PER-STATE PERFORMANCE ANALYSIS")
    print("="*80)
    
    print("\nScenario: Analyzing which BTR states predict best")
    print("Using 20 different states from ASMBTR tree")
    
    np.random.seed(789)
    n_bars = 1000
    n_states = 20
    
    # Create realistic state distribution
    # Some states appear more frequently
    state_probs = np.random.dirichlet(np.ones(n_states) * 2)
    states = [f"state_{i:02d}" for i in range(n_states)]
    state_sequence = np.random.choice(states, size=n_bars, p=state_probs)
    
    # Ground truth
    actual = np.random.choice([-1, 0, 1], size=n_bars, p=[0.30, 0.20, 0.50])
    
    # Predictions with state-dependent accuracy
    # Some states are better predictors
    predictions = []
    for i, state in enumerate(state_sequence):
        state_idx = int(state.split("_")[1])
        # States 5, 10, 15 are "good" predictors (80% accuracy)
        if state_idx in [5, 10, 15]:
            if np.random.random() < 0.80:
                predictions.append(actual[i])
            else:
                predictions.append(np.random.choice([-1, 0, 1]))
        # Other states: 65% accuracy
        else:
            if np.random.random() < 0.65:
                predictions.append(actual[i])
            else:
                predictions.append(np.random.choice([-1, 0, 1]))
    
    # Analyze per state
    evaluator = ASMBTREvaluator()
    state_results = evaluator.evaluate_state_predictions(
        state_sequence.tolist(),
        predictions,
        actual.tolist(),
        correction="benjamini_hochberg",
    )
    
    print(f"\n📊 TOP 5 PERFORMING STATES:")
    print(f"\n{'State':<12} {'Samples':<10} {'Accuracy':<10} {'F1 Score':<10} {'Adj P-val'}")
    print("-" * 60)
    
    for i, (state, metrics) in enumerate(list(state_results.items())[:5]):
        print(f"{state:<12} {metrics['sample_count']:<10} "
              f"{metrics['accuracy']:>7.2%}   "
              f"{metrics['f1_score']:>8.3f}   "
              f"{metrics.get('adjusted_p_value', 'N/A')}")
        if i >= 4:
            break
    
    print(f"\n💡 Insights:")
    print(f"   Total unique states: {len(state_results)}")
    print(f"   States with >75% accuracy: "
          f"{sum(1 for m in state_results.values() if m['accuracy'] > 0.75)}")
    print(f"   Use these high-performing states for position sizing!")


def main():
    """Run all demos"""
    print("\n" + "="*80)
    print("ASMBTR EVALUATION FRAMEWORK - INTEGRATION DEMOS")
    print("="*80)
    print("\nPhase 7.1: Confusion Matrix & Statistical Testing")
    print("Demonstrating practical usage with ASMBTR strategy")
    
    # Run demos
    demo_basic_evaluation()
    demo_multiple_testing_correction()
    demo_variant_comparison()
    demo_state_analysis()
    
    # Summary
    print("\n" + "="*80)
    print("✅ ALL DEMOS COMPLETE")
    print("="*80)
    print("\n📚 Key Takeaways:")
    print("   1. Confusion matrices show detailed classification performance")
    print("   2. P-value corrections prevent false positives in multiple testing")
    print("   3. Variant comparison helps optimize ASMBTR configuration")
    print("   4. Per-state analysis identifies best performing patterns")
    print("\n🎯 Next Steps:")
    print("   • Test on real BTC/ETH market data (2023-2024)")
    print("   • Integrate with live ASMBTR backtests")
    print("   • Add to Grafana dashboards")
    print("   • Compare against Multi-Agent AI predictions (Phase 6)")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
