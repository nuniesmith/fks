#!/usr/bin/env python3
"""
Quick validation script for Ground Truth Validator.

Tests the validator can be imported and instantiated correctly.
Run this outside container to validate the code structure.
"""

import sys
import os
from pathlib import Path

# Add AI service to path
ai_service_path = Path(__file__).parent.parent / "src" / "services" / "ai" / "src"
sys.path.insert(0, str(ai_service_path))

print("=" * 80)
print("Ground Truth Validator - Quick Validation")
print("=" * 80)

# Test 1: Import modules
print("\n[1/6] Testing imports...")
try:
    from evaluators.ground_truth import (
        GroundTruthValidator,
        AgentPrediction,
        OptimalTrade,
        ValidationResult,
        PredictionType,
        TradeOutcome
    )
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Create validator instance
print("\n[2/6] Creating GroundTruthValidator instance...")
try:
    validator = GroundTruthValidator(
        min_confidence=0.6,
        profit_threshold=2.0,
        slippage_percent=0.1,
        fee_percent=0.1
    )
    print(f"✅ Validator created: {validator}")
except Exception as e:
    print(f"❌ Validator creation failed: {e}")
    sys.exit(1)

# Test 3: Create AgentPrediction
print("\n[3/6] Creating AgentPrediction...")
try:
    from datetime import datetime
    prediction = AgentPrediction(
        timestamp=datetime(2024, 10, 31, 12, 0),
        agent_name="test_agent",
        symbol="BTCUSDT",
        prediction=PredictionType.BULLISH,
        confidence=0.85,
        reasoning="Test prediction",
        timeframe="1h",
        price_at_prediction=65000.0,
        metadata={"test": True}
    )
    print(f"✅ AgentPrediction created: {prediction.agent_name} - {prediction.prediction}")
except Exception as e:
    print(f"❌ AgentPrediction creation failed: {e}")
    sys.exit(1)

# Test 4: Create OptimalTrade
print("\n[4/6] Creating OptimalTrade...")
try:
    from datetime import timedelta
    trade = OptimalTrade(
        entry_time=datetime(2024, 10, 31, 12, 0),
        exit_time=datetime(2024, 10, 31, 13, 0),
        direction="long",
        entry_price=65000.0,
        exit_price=66500.0,
        profit_percent=2.31,
        max_profit_percent=2.31,
        slippage_percent=0.1,
        fee_percent=0.1
    )
    print(f"✅ OptimalTrade created: {trade.direction} - {trade.profit_percent}%")
    print(f"   Net profit: {trade.net_profit_percent}%")
except Exception as e:
    print(f"❌ OptimalTrade creation failed: {e}")
    sys.exit(1)

# Test 5: Create ValidationResult
print("\n[5/6] Creating ValidationResult...")
try:
    result = ValidationResult(
        agent_name="test_agent",
        symbol="BTCUSDT",
        start_date=datetime(2024, 10, 1),
        end_date=datetime(2024, 10, 31),
        timeframe="1h",
        total_predictions=10,
        total_optimal_trades=8,
        true_positives=5,
        false_positives=2,
        true_negatives=2,
        false_negatives=1,
        accuracy=0.7,
        precision=0.71,
        recall=0.83,
        f1_score=0.77,
        confusion_matrix=[[5, 2], [1, 2]],
        agent_total_profit_percent=15.0,
        optimal_total_profit_percent=20.0,
        efficiency_ratio=0.75,
        correct_predictions=5,
        incorrect_predictions=3,
        missed_opportunities=2,
        avg_confidence_correct=0.85,
        avg_confidence_incorrect=0.60,
        prediction_distribution={"BULLISH": 7, "BEARISH": 2, "NEUTRAL": 1}
    )
    print(f"✅ ValidationResult created:")
    print(f"   Accuracy: {result.accuracy:.2%}")
    print(f"   Precision: {result.precision:.2%}")
    print(f"   Recall: {result.recall:.2%}")
    print(f"   F1 Score: {result.f1_score:.2%}")
    print(f"   Efficiency: {result.efficiency_ratio:.2%}")
except Exception as e:
    print(f"❌ ValidationResult creation failed: {e}")
    sys.exit(1)

# Test 6: Serialize to dict
print("\n[6/6] Testing serialization...")
try:
    result_dict = result.to_dict()
    assert isinstance(result_dict, dict)
    assert result_dict["accuracy"] == 0.7
    assert result_dict["agent_name"] == "test_agent"
    print(f"✅ Serialization successful")
    print(f"   Dict keys: {list(result_dict.keys())[:5]}...")
except Exception as e:
    print(f"❌ Serialization failed: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ ALL VALIDATION TESTS PASSED")
print("=" * 80)
print("\nGround Truth Validator is ready for deployment!")
print("Next steps:")
print("  1. Add FastAPI endpoint: POST /ai/validate/ground-truth")
print("  2. Test with real ChromaDB and TimescaleDB data")
print("  3. Run integration tests in container")
print("  4. Create documentation")
