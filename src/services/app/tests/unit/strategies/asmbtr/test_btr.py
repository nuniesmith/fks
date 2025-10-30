"""Unit tests for BTR (Binary Tree Representation) encoder.

Tests cover:
- BTR state encoding correctness
- Variable depth handling (2-64)
- Movement sequence tracking
- State serialization/deserialization
- Edge cases and error handling
"""

import pytest
from decimal import Decimal
from collections import deque

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'src' / 'services' / 'app' / 'src'))

from strategies.asmbtr.btr import BTREncoder, BTRState


class TestBTRState:
    """Tests for BTRState dataclass."""
    
    def test_state_creation(self):
        """Test basic state creation."""
        state = BTRState(sequence="10110011", depth=8)
        
        assert state.sequence == "10110011"
        assert state.depth == 8
        assert len(state.sequence) == state.depth
    
    def test_state_to_decimal(self):
        """Test binary to decimal conversion."""
        state = BTRState(sequence="10110011", depth=8)
        
        # 10110011 = 179 in decimal
        assert state.to_decimal() == 179
    
    def test_state_from_decimal(self):
        """Test decimal to binary conversion."""
        state = BTRState.from_decimal(179, depth=8)
        
        assert state.sequence == "10110011"
        assert state.depth == 8
    
    def test_state_equality(self):
        """Test state equality comparison."""
        state1 = BTRState(sequence="10110011", depth=8)
        state2 = BTRState(sequence="10110011", depth=8)
        state3 = BTRState(sequence="10110010", depth=8)
        
        assert state1 == state2
        assert state1 != state3
    
    def test_state_str_representation(self):
        """Test string representation."""
        state = BTRState(sequence="10110011", depth=8)
        
        assert str(state) == "BTRState(10110011)"


class TestBTREncoder:
    """Tests for BTREncoder class."""
    
    def test_encoder_initialization(self):
        """Test encoder initialization with default depth."""
        encoder = BTREncoder()
        
        assert encoder.depth == 8
        assert len(encoder.buffer) == 0
        assert encoder.buffer.maxlen == 8
    
    def test_encoder_custom_depth(self):
        """Test encoder with custom depth."""
        encoder = BTREncoder(depth=12)
        
        assert encoder.depth == 12
        assert encoder.buffer.maxlen == 12
    
    def test_encoder_depth_validation(self):
        """Test depth validation (2-64 range)."""
        # Valid depths
        encoder_min = BTREncoder(depth=2)
        assert encoder_min.depth == 2
        
        encoder_max = BTREncoder(depth=64)
        assert encoder_max.depth == 64
        
        # Invalid depths
        with pytest.raises(ValueError, match="Depth must be between 2 and 64"):
            BTREncoder(depth=1)
        
        with pytest.raises(ValueError, match="Depth must be between 2 and 64"):
            BTREncoder(depth=65)
    
    def test_add_movement_up(self):
        """Test adding upward movement."""
        encoder = BTREncoder(depth=4)
        
        encoder.add_movement(up=True)
        
        assert len(encoder.buffer) == 1
        assert encoder.buffer[0] is True
    
    def test_add_movement_down(self):
        """Test adding downward movement."""
        encoder = BTREncoder(depth=4)
        
        encoder.add_movement(up=False)
        
        assert len(encoder.buffer) == 1
        assert encoder.buffer[0] is False
    
    def test_add_movement_sequence(self):
        """Test adding sequence of movements."""
        encoder = BTREncoder(depth=4)
        
        movements = [True, False, True, True]
        for movement in movements:
            encoder.add_movement(up=movement)
        
        assert len(encoder.buffer) == 4
        assert list(encoder.buffer) == movements
    
    def test_buffer_overflow(self):
        """Test buffer overflow (sliding window)."""
        encoder = BTREncoder(depth=4)
        
        # Add 5 movements (more than depth)
        movements = [True, False, True, True, False]
        for movement in movements:
            encoder.add_movement(up=movement)
        
        # Should keep only last 4
        assert len(encoder.buffer) == 4
        assert list(encoder.buffer) == [False, True, True, False]
    
    def test_get_state_insufficient_data(self):
        """Test get_state with insufficient data."""
        encoder = BTREncoder(depth=4)
        
        # Add only 2 movements
        encoder.add_movement(up=True)
        encoder.add_movement(up=False)
        
        state = encoder.get_state()
        assert state is None
    
    def test_get_state_exact_depth(self):
        """Test get_state with exact depth of data."""
        encoder = BTREncoder(depth=4)
        
        # Add exactly 4 movements
        encoder.add_movement(up=True)   # 1
        encoder.add_movement(up=False)  # 0
        encoder.add_movement(up=True)   # 1
        encoder.add_movement(up=True)   # 1
        
        state = encoder.get_state()
        
        assert state is not None
        assert state.sequence == "1011"
        assert state.depth == 4
    
    def test_get_state_overflow(self):
        """Test get_state with more than depth data."""
        encoder = BTREncoder(depth=4)
        
        # Add 6 movements
        movements = [True, False, True, True, False, True]
        for movement in movements:
            encoder.add_movement(up=movement)
        
        state = encoder.get_state()
        
        # Should use only last 4
        assert state is not None
        assert state.sequence == "1101"
    
    def test_encode_deltas(self):
        """Test encoding delta sequence."""
        encoder = BTREncoder(depth=4)
        
        deltas = [
            Decimal("0.001"),   # UP
            Decimal("-0.002"),  # DOWN
            Decimal("0.003"),   # UP
            Decimal("0.001")    # UP
        ]
        
        state = encoder.encode_deltas(deltas)
        
        assert state is not None
        assert state.sequence == "1011"
    
    def test_encode_deltas_insufficient(self):
        """Test encode_deltas with insufficient data."""
        encoder = BTREncoder(depth=4)
        
        deltas = [Decimal("0.001"), Decimal("-0.002")]
        
        state = encoder.encode_deltas(deltas)
        assert state is None
    
    def test_encode_deltas_zero_handling(self):
        """Test that zero deltas are treated as DOWN."""
        encoder = BTREncoder(depth=4)
        
        deltas = [
            Decimal("0.001"),   # UP
            Decimal("0.000"),   # ZERO -> DOWN
            Decimal("0.003"),   # UP
            Decimal("-0.001")   # DOWN
        ]
        
        state = encoder.encode_deltas(deltas)
        
        assert state is not None
        assert state.sequence == "1010"
    
    def test_create_all_states(self):
        """Test generation of all possible states."""
        encoder = BTREncoder(depth=3)
        
        all_states = encoder.create_all_states()
        
        # Should have 2^3 = 8 states
        assert len(all_states) == 8
        
        # Check specific states
        sequences = [state.sequence for state in all_states]
        assert "000" in sequences
        assert "001" in sequences
        assert "111" in sequences
    
    def test_create_all_states_depth_4(self):
        """Test state generation for depth 4."""
        encoder = BTREncoder(depth=4)
        
        all_states = encoder.create_all_states()
        
        # Should have 2^4 = 16 states
        assert len(all_states) == 16
    
    def test_reset(self):
        """Test encoder reset."""
        encoder = BTREncoder(depth=4)
        
        # Add some movements
        encoder.add_movement(up=True)
        encoder.add_movement(up=False)
        
        assert len(encoder.buffer) == 2
        
        # Reset
        encoder.reset()
        
        assert len(encoder.buffer) == 0
    
    def test_state_consistency(self):
        """Test that same movements produce same state."""
        encoder1 = BTREncoder(depth=8)
        encoder2 = BTREncoder(depth=8)
        
        movements = [True, False, True, True, False, True, False, False]
        
        for movement in movements:
            encoder1.add_movement(up=movement)
            encoder2.add_movement(up=movement)
        
        state1 = encoder1.get_state()
        state2 = encoder2.get_state()
        
        assert state1 == state2
    
    def test_different_depths_different_states(self):
        """Test that different depths produce different state spaces."""
        encoder_small = BTREncoder(depth=3)
        encoder_large = BTREncoder(depth=4)
        
        all_states_small = encoder_small.create_all_states()
        all_states_large = encoder_large.create_all_states()
        
        assert len(all_states_small) == 8   # 2^3
        assert len(all_states_large) == 16  # 2^4


class TestBTREncoderEdgeCases:
    """Edge case tests for BTREncoder."""
    
    def test_large_depth(self):
        """Test encoder with large depth (64)."""
        encoder = BTREncoder(depth=64)
        
        # Add 64 movements
        movements = [bool(i % 2) for i in range(64)]
        for movement in movements:
            encoder.add_movement(up=movement)
        
        state = encoder.get_state()
        
        assert state is not None
        assert len(state.sequence) == 64
    
    def test_minimum_depth(self):
        """Test encoder with minimum depth (2)."""
        encoder = BTREncoder(depth=2)
        
        encoder.add_movement(up=True)
        encoder.add_movement(up=False)
        
        state = encoder.get_state()
        
        assert state is not None
        assert state.sequence == "10"
    
    def test_empty_deltas(self):
        """Test encoding empty delta list."""
        encoder = BTREncoder(depth=4)
        
        state = encoder.encode_deltas([])
        assert state is None
    
    def test_very_small_deltas(self):
        """Test encoding very small deltas (near zero)."""
        encoder = BTREncoder(depth=4)
        
        deltas = [
            Decimal("0.0000001"),   # Very small UP
            Decimal("-0.0000001"),  # Very small DOWN
            Decimal("0.0000001"),   # Very small UP
            Decimal("0.0000001")    # Very small UP
        ]
        
        state = encoder.encode_deltas(deltas)
        
        assert state is not None
        assert state.sequence == "1011"
    
    def test_state_decimal_conversion_roundtrip(self):
        """Test roundtrip conversion: sequence -> decimal -> sequence."""
        original_sequence = "10110011"
        state1 = BTRState(sequence=original_sequence, depth=8)
        
        decimal_value = state1.to_decimal()
        state2 = BTRState.from_decimal(decimal_value, depth=8)
        
        assert state2.sequence == original_sequence


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
