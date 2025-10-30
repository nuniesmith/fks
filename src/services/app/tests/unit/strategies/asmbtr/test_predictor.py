"""Unit tests for Prediction Table.

Tests cover:
- Prediction accuracy
- Learning from observations
- Decay effects
- Confidence metrics
- Serialization/deserialization
- Statistics calculation
"""

import pytest
from decimal import Decimal
import tempfile
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'src' / 'services' / 'app' / 'src'))

from strategies.asmbtr.predictor import PredictionTable, StatePrediction
from strategies.asmbtr.btr import BTRState


class TestStatePrediction:
    """Tests for StatePrediction dataclass."""
    
    def test_prediction_creation(self):
        """Test basic prediction creation."""
        pred = StatePrediction(
            state=BTRState(sequence="10110011", depth=8),
            up_probability=0.75,
            down_probability=0.25,
            observations=100,
            up_count=75,
            down_count=25
        )
        
        assert pred.prediction == "UP"  # Property calculated from probabilities
        assert pred.confidence == 0.50  # |0.75 - 0.25|
        assert pred.observations == 100
    
    def test_prediction_str_representation(self):
        """Test string representation."""
        pred = StatePrediction(
            state=BTRState(sequence="1011", depth=4),
            up_probability=0.65,
            down_probability=0.35,
            observations=50,
            up_count=33,
            down_count=17
        )
        
        str_repr = str(pred)
        assert "UP" in str_repr
        assert "0.65" in str_repr


class TestPredictionTable:
    """Tests for PredictionTable class."""
    
    def test_table_initialization(self):
        """Test prediction table initialization."""
        table = PredictionTable(depth=8)
        
        assert table.depth == 8
        assert table.decay_rate == 1.0  # Default no decay
        assert len(table.state_counts) == 0
    
    def test_table_custom_decay(self):
        """Test table with custom decay rate."""
        table = PredictionTable(depth=8, decay_rate=0.999)
        
        assert table.decay_rate == 0.999
    
    def test_observe_new_state_up(self):
        """Test observing upward move for new state."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        table.observe(state, next_move_up=True)
        
        assert "1011" in table.state_counts
        assert table.state_counts["1011"]["up"] == 1
        assert table.state_counts["1011"]["down"] == 0
    
    def test_observe_new_state_down(self):
        """Test observing downward move for new state."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        table.observe(state, next_move_up=False)
        
        assert "1011" in table.state_counts
        assert table.state_counts["1011"]["up"] == 0
        assert table.state_counts["1011"]["down"] == 1
    
    def test_observe_multiple_same_state(self):
        """Test observing multiple outcomes for same state."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        # Observe 7 UP, 3 DOWN
        for _ in range(7):
            table.observe(state, next_move_up=True)
        
        for _ in range(3):
            table.observe(state, next_move_up=False)
        
        assert table.state_counts["1011"]["up"] == 7
        assert table.state_counts["1011"]["down"] == 3
    
    def test_predict_no_data(self):
        """Test prediction with no observations."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        prediction = table.predict(state)
        
        assert prediction is None
    
    def test_predict_insufficient_observations(self):
        """Test prediction with insufficient observations."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        # Only 3 observations (min default is 5)
        table.observe(state, next_move_up=True)
        table.observe(state, next_move_up=True)
        table.observe(state, next_move_up=False)
        
        prediction = table.predict(state, min_observations=5)
        
        assert prediction is None
    
    def test_predict_up_bias(self):
        """Test prediction with upward bias."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        # 8 UP, 2 DOWN
        for _ in range(8):
            table.observe(state, next_move_up=True)
        for _ in range(2):
            table.observe(state, next_move_up=False)
        
        prediction = table.predict(state, min_observations=5)
        
        assert prediction is not None
        assert prediction.prediction == "UP"
        assert prediction.up_probability == 0.8
        assert prediction.down_probability == 0.2
        assert prediction.confidence == pytest.approx(0.6, rel=1e-9)  # |0.8 - 0.2|
        assert prediction.observations == 10
    
    def test_predict_down_bias(self):
        """Test prediction with downward bias."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        # 3 UP, 7 DOWN
        for _ in range(3):
            table.observe(state, next_move_up=True)
        for _ in range(7):
            table.observe(state, next_move_up=False)
        
        prediction = table.predict(state, min_observations=5)
        
        assert prediction is not None
        assert prediction.prediction == "DOWN"
        assert prediction.up_probability == 0.3
        assert prediction.down_probability == 0.7
    
    def test_predict_neutral(self):
        """Test prediction for neutral state (50/50)."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        # 5 UP, 5 DOWN
        for _ in range(5):
            table.observe(state, next_move_up=True)
        for _ in range(5):
            table.observe(state, next_move_up=False)
        
        prediction = table.predict(state, min_observations=5)
        
        assert prediction is not None
        assert prediction.prediction == "NEUTRAL"
        assert prediction.up_probability == 0.5
        assert prediction.down_probability == 0.5
        assert prediction.confidence == 0.0  # No confidence for 50/50
    
    def test_observe_sequence(self):
        """Test batch observation of state sequence."""
        table = PredictionTable(depth=4)
        
        states = [
            BTRState(sequence="1011", depth=4),
            BTRState(sequence="1011", depth=4),
            BTRState(sequence="0110", depth=4),
            BTRState(sequence="1011", depth=4)
        ]
        
        outcomes = [True, False, True, True]
        
        table.observe_sequence(states, outcomes)
        
        # State 1011 should have 2 UP, 1 DOWN
        assert table.state_counts["1011"]["up"] == 2
        assert table.state_counts["1011"]["down"] == 1
        
        # State 0110 should have 1 UP, 0 DOWN
        assert table.state_counts["0110"]["up"] == 1
        assert table.state_counts["0110"]["down"] == 0
    
    def test_apply_decay(self):
        """Test decay application."""
        table = PredictionTable(depth=4, decay_rate=0.9)
        state = BTRState(sequence="1011", depth=4)
        
        # Initial observations
        table.observe(state, next_move_up=True)
        table.observe(state, next_move_up=True)
        table.observe(state, next_move_up=False)
        
        assert table.state_counts["1011"]["up"] == 2
        assert table.state_counts["1011"]["down"] == 1
        
        # Apply decay
        table.apply_decay()
        
        # Should be multiplied by 0.9
        assert table.state_counts["1011"]["up"] == pytest.approx(1.8, rel=1e-5)
        assert table.state_counts["1011"]["down"] == pytest.approx(0.9, rel=1e-5)
    
    def test_get_statistics_empty(self):
        """Test statistics for empty table."""
        table = PredictionTable(depth=4)
        
        stats = table.get_statistics()
        
        assert stats["unique_states"] == 0
        assert stats["total_observations"] == 0
        assert stats["coverage"] == 0.0
    
    def test_get_statistics_populated(self):
        """Test statistics for populated table."""
        table = PredictionTable(depth=4)
        
        # Depth 4 has 2^4 = 16 possible states
        # Observe 3 different states
        states = [
            BTRState(sequence="1011", depth=4),
            BTRState(sequence="0110", depth=4),
            BTRState(sequence="1111", depth=4)
        ]
        
        for state in states:
            table.observe(state, next_move_up=True)
            table.observe(state, next_move_up=False)
        
        stats = table.get_statistics()
        
        assert stats["unique_states"] == 3
        assert stats["total_observations"] == 6
        assert stats["coverage"] == pytest.approx(18.75, rel=1e-2)  # 3/16 * 100
        assert stats["avg_observations_per_state"] == pytest.approx(2.0, rel=1e-5)
    
    def test_save_load_roundtrip(self):
        """Test saving and loading table."""
        table1 = PredictionTable(depth=4, decay_rate=0.999)
        
        # Add some observations
        state1 = BTRState(sequence="1011", depth=4)
        state2 = BTRState(sequence="0110", depth=4)
        
        for _ in range(5):
            table1.observe(state1, next_move_up=True)
        for _ in range(3):
            table1.observe(state1, next_move_up=False)
        
        for _ in range(7):
            table1.observe(state2, next_move_up=False)
        
        # Save to dict and load back
        saved_data = table1.save_to_dict()
        table2 = PredictionTable.load_from_dict(saved_data)
        
        # Verify
        assert table2.depth == 4
        assert table2.decay_rate == 0.999
        assert table2.state_counts["1011"]["up"] == 5
        assert table2.state_counts["1011"]["down"] == 3
        assert table2.state_counts["0110"]["down"] == 7


class TestPredictionTableEdgeCases:
    """Edge case tests for PredictionTable."""
    
    def test_very_high_confidence(self):
        """Test prediction with very high confidence (100% up)."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        # 100 UP, 0 DOWN
        for _ in range(100):
            table.observe(state, next_move_up=True)
        
        prediction = table.predict(state)
        
        assert prediction.prediction == "UP"
        assert prediction.up_probability == 1.0
        assert prediction.confidence == 1.0  # |(1.0 - 0.5) / 0.5| = 1.0
    
    def test_very_low_confidence(self):
        """Test prediction with very low confidence (near 50/50)."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        # 51 UP, 49 DOWN (very close to 50/50)
        for _ in range(51):
            table.observe(state, next_move_up=True)
        for _ in range(49):
            table.observe(state, next_move_up=False)
        
        prediction = table.predict(state)
        
        assert prediction.prediction == "UP"  # Slightly up biased
        assert prediction.confidence < 0.05  # Very low confidence
    
    def test_multiple_states_different_patterns(self):
        """Test multiple states with different patterns."""
        table = PredictionTable(depth=4)
        
        # State 1: Strong UP bias
        state1 = BTRState(sequence="1111", depth=4)
        for _ in range(10):
            table.observe(state1, next_move_up=True)
        
        # State 2: Strong DOWN bias
        state2 = BTRState(sequence="0000", depth=4)
        for _ in range(10):
            table.observe(state2, next_move_up=False)
        
        # State 3: Neutral
        state3 = BTRState(sequence="1010", depth=4)
        for _ in range(5):
            table.observe(state3, next_move_up=True)
        for _ in range(5):
            table.observe(state3, next_move_up=False)
        
        # Verify predictions
        pred1 = table.predict(state1)
        pred2 = table.predict(state2)
        pred3 = table.predict(state3)
        
        assert pred1.prediction == "UP"
        assert pred2.prediction == "DOWN"
        assert pred3.prediction == "NEUTRAL"
    
    def test_decay_over_multiple_applications(self):
        """Test decay over multiple applications."""
        table = PredictionTable(depth=4, decay_rate=0.95)
        state = BTRState(sequence="1011", depth=4)
        
        # Initial observation
        table.observe(state, next_move_up=True)
        assert table.state_counts["1011"]["up"] == 1
        
        # Apply decay 3 times
        table.apply_decay()  # 1 * 0.95 = 0.95
        table.apply_decay()  # 0.95 * 0.95 = 0.9025
        table.apply_decay()  # 0.9025 * 0.95 = 0.857375
        
        assert table.state_counts["1011"]["up"] == pytest.approx(0.857375, rel=1e-5)
    
    def test_observe_sequence_length_mismatch(self):
        """Test observe_sequence with mismatched lengths."""
        table = PredictionTable(depth=4)
        
        states = [
            BTRState(sequence="1011", depth=4),
            BTRState(sequence="0110", depth=4)
        ]
        outcomes = [True]  # Only 1 outcome for 2 states
        
        with pytest.raises(ValueError, match="must have same length"):
            table.observe_sequence(states, outcomes)
    
    def test_prediction_with_custom_min_observations(self):
        """Test prediction with various min_observations thresholds."""
        table = PredictionTable(depth=4)
        state = BTRState(sequence="1011", depth=4)
        
        # Add 10 observations
        for _ in range(10):
            table.observe(state, next_move_up=True)
        
        # Should succeed with min=5
        pred1 = table.predict(state, min_observations=5)
        assert pred1 is not None
        
        # Should succeed with min=10
        pred2 = table.predict(state, min_observations=10)
        assert pred2 is not None
        
        # Should fail with min=11
        pred3 = table.predict(state, min_observations=11)
        assert pred3 is None
    
    def test_coverage_calculation_different_depths(self):
        """Test coverage calculation for different depths."""
        # Depth 3: 2^3 = 8 possible states
        table_small = PredictionTable(depth=3)
        for i in range(4):  # Observe half the states
            state = BTRState.from_decimal(i, depth=3)
            table_small.observe(state, next_move_up=True)
        
        stats_small = table_small.get_statistics()
        assert stats_small["coverage"] == 50.0  # 4/8 * 100
        
        # Depth 8: 2^8 = 256 possible states
        table_large = PredictionTable(depth=8)
        for i in range(64):  # Observe 1/4 of states
            state = BTRState.from_decimal(i, depth=8)
            table_large.observe(state, next_move_up=True)
        
        stats_large = table_large.get_statistics()
        assert stats_large["coverage"] == 25.0  # 64/256 * 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
