"""Unit tests for State Encoder.

Tests cover:
- Single symbol state encoding
- Multi-symbol state encoding
- Tick processing with various formats
- Delta sequence processing
- State transition tracking
"""

import pytest
from decimal import Decimal
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'src' / 'services' / 'app' / 'src'))

from strategies.asmbtr.encoder import StateEncoder, MultiSymbolEncoder
from strategies.asmbtr.btr import BTRState


class TestStateEncoder:
    """Tests for StateEncoder class."""
    
    def test_encoder_initialization(self):
        """Test StateEncoder initialization with default depth."""
        encoder = StateEncoder()
        
        assert encoder.depth == 8
        assert encoder.encoder is not None
        assert encoder.encoder.depth == 8
        assert encoder.last_price is None
    
    def test_process_tick_first(self):
        """Test processing first tick (should return None)."""
        encoder = StateEncoder(depth=4)
        
        tick = {
            'timestamp': datetime.now(),
            'symbol': 'EUR/USDT',
            'last': Decimal("1.08500")
        }
        
        state = encoder.process_tick(tick)
        
        # First tick has no previous price to compare
        assert state is None
        assert encoder.last_price == Decimal("1.08500")
    
    def test_process_tick_sequence(self):
        """Test processing sequence of ticks."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'last': Decimal("1.08500")},
            {'last': Decimal("1.08520")},  # UP
            {'last': Decimal("1.08510")},  # DOWN
            {'last': Decimal("1.08530")},  # UP
            {'last': Decimal("1.08540")}   # UP
        ]
        
        states = []
        for tick in ticks:
            state = encoder.process_tick(tick)
            if state:
                states.append(state)
        
        # Should have 1 state after 5 ticks (4 movements + 1 initial)
        assert len(states) == 1
        assert states[0].sequence == "1011"
    
    def test_process_tick_custom_price_key(self):
        """Test processing tick with custom price key."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'price': Decimal("1.08500")},
            {'price': Decimal("1.08520")},
            {'price': Decimal("1.08510")},
            {'price': Decimal("1.08530")},
            {'price': Decimal("1.08540")}
        ]
        
        states = []
        for tick in ticks:
            state = encoder.process_tick(tick, price_key='price')
            if state:
                states.append(state)
        
        assert len(states) == 1
        assert states[0].sequence == "1011"
    
    def test_process_tick_float_conversion(self):
        """Test automatic float to Decimal conversion."""
        encoder = StateEncoder(depth=4)
        
        # Use float prices (should auto-convert)
        ticks = [
            {'last': 1.08500},
            {'last': 1.08520},
            {'last': 1.08510},
            {'last': 1.08530},
            {'last': 1.08540}
        ]
        
        states = []
        for tick in ticks:
            state = encoder.process_tick(tick)
            if state:
                states.append(state)
        
        assert len(states) == 1
    
    def test_process_ticks_batch(self):
        """Test batch processing of ticks."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'last': Decimal("1.08500")},
            {'last': Decimal("1.08520")},  # UP
            {'last': Decimal("1.08510")},  # DOWN
            {'last': Decimal("1.08530")},  # UP
            {'last': Decimal("1.08540")}   # UP
        ]
        
        states = encoder.process_ticks(ticks)
        
        # Should have 1 state
        assert len(states) == 1
        assert states[0].sequence == "1011"
    
    def test_process_delta_sequence(self):
        """Test processing delta sequence directly."""
        encoder = StateEncoder(depth=4)
        
        deltas = [
            Decimal("0.00020"),   # UP
            Decimal("-0.00010"),  # DOWN
            Decimal("0.00020"),   # UP
            Decimal("0.00010")    # UP
        ]
        
        state = encoder.process_delta_sequence(deltas)
        
        assert state is not None
        assert state.sequence == "1011"
    
    def test_get_current_state_no_data(self):
        """Test getting current state with no data."""
        encoder = StateEncoder(depth=4)
        
        state = encoder.get_current_state()
        assert state is None
    
    def test_get_current_state_with_data(self):
        """Test getting current state with sufficient data."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'last': Decimal("1.08500")},
            {'last': Decimal("1.08520")},
            {'last': Decimal("1.08510")},
            {'last': Decimal("1.08530")},
            {'last': Decimal("1.08540")}
        ]
        
        for tick in ticks:
            encoder.process_tick(tick)
        
        state = encoder.get_current_state()
        
        assert state is not None
        assert state.sequence == "1011"
    
    def test_state_updates_with_new_ticks(self):
        """Test that state updates as new ticks arrive."""
        encoder = StateEncoder(depth=4)
        
        # First batch
        ticks1 = [
            {'last': Decimal("1.08500")},
            {'last': Decimal("1.08520")},  # UP
            {'last': Decimal("1.08510")},  # DOWN
            {'last': Decimal("1.08530")},  # UP
            {'last': Decimal("1.08540")}   # UP
        ]
        
        for tick in ticks1:
            encoder.process_tick(tick)
        
        state1 = encoder.get_current_state()
        assert state1.sequence == "1011"
        
        # Add one more tick (DOWN)
        encoder.process_tick({'last': Decimal("1.08530")})
        
        state2 = encoder.get_current_state()
        # Should slide window: 011 + 0 = 0110
        assert state2.sequence == "0110"


class TestMultiSymbolEncoder:
    """Tests for MultiSymbolEncoder class."""
    
    def test_encoder_initialization(self):
        """Test multi-symbol encoder initialization."""
        encoder = MultiSymbolEncoder(depth=8)
        
        assert encoder.depth == 8
        assert len(encoder.encoders) == 0
    
    def test_process_tick_new_symbol(self):
        """Test processing tick for new symbol."""
        encoder = MultiSymbolEncoder(depth=4)
        
        tick = {
            'timestamp': datetime.now(),
            'symbol': 'EUR/USDT',
            'last': Decimal("1.08500")
        }
        
        state = encoder.process_tick(tick)
        
        # First tick should return None
        assert state is None
        
        # Should have created encoder for symbol
        assert 'EUR/USDT' in encoder.encoders
    
    def test_process_tick_multiple_symbols(self):
        """Test processing ticks for multiple symbols."""
        encoder = MultiSymbolEncoder(depth=4)
        
        # EUR/USDT ticks
        eur_ticks = [
            {'symbol': 'EUR/USDT', 'last': Decimal("1.08500")},
            {'symbol': 'EUR/USDT', 'last': Decimal("1.08520")},
            {'symbol': 'EUR/USDT', 'last': Decimal("1.08510")},
            {'symbol': 'EUR/USDT', 'last': Decimal("1.08530")},
            {'symbol': 'EUR/USDT', 'last': Decimal("1.08540")}
        ]
        
        # GBP/USDT ticks
        gbp_ticks = [
            {'symbol': 'GBP/USDT', 'last': Decimal("1.25000")},
            {'symbol': 'GBP/USDT', 'last': Decimal("1.25010")},
            {'symbol': 'GBP/USDT', 'last': Decimal("1.25020")},
            {'symbol': 'GBP/USDT', 'last': Decimal("1.25015")},
            {'symbol': 'GBP/USDT', 'last': Decimal("1.25025")}
        ]
        
        # Process EUR ticks
        for tick in eur_ticks:
            encoder.process_tick(tick)
        
        # Process GBP ticks
        for tick in gbp_ticks:
            encoder.process_tick(tick)
        
        # Should have 2 encoders
        assert len(encoder.encoders) == 2
        assert 'EUR/USDT' in encoder.encoders
        assert 'GBP/USDT' in encoder.encoders
        
        # Check states
        eur_state = encoder.get_state('EUR/USDT')
        gbp_state = encoder.get_state('GBP/USDT')
        
        assert eur_state is not None
        assert gbp_state is not None
        
        # States should be different
        assert eur_state.sequence != gbp_state.sequence
    
    def test_get_state_unknown_symbol(self):
        """Test getting state for unknown symbol."""
        encoder = MultiSymbolEncoder(depth=4)
        
        state = encoder.get_state('UNKNOWN/USDT')
        assert state is None
    
    def test_get_all_states_empty(self):
        """Test getting all states when empty."""
        encoder = MultiSymbolEncoder(depth=4)
        
        all_states = encoder.get_all_states()
        assert len(all_states) == 0
    
    def test_get_all_states_multiple_symbols(self):
        """Test getting all states for multiple symbols."""
        encoder = MultiSymbolEncoder(depth=4)
        
        # Process ticks for 3 symbols
        symbols = ['EUR/USDT', 'GBP/USDT', 'BTC/USDT']
        
        for symbol in symbols:
            ticks = [
                {'symbol': symbol, 'last': Decimal("1.00000")},
                {'symbol': symbol, 'last': Decimal("1.00010")},
                {'symbol': symbol, 'last': Decimal("1.00020")},
                {'symbol': symbol, 'last': Decimal("1.00015")},
                {'symbol': symbol, 'last': Decimal("1.00025")}
            ]
            
            for tick in ticks:
                encoder.process_tick(tick)
        
        all_states = encoder.get_all_states()
        
        assert len(all_states) == 3
        assert 'EUR/USDT' in all_states
        assert 'GBP/USDT' in all_states
        assert 'BTC/USDT' in all_states


class TestStateEncoderEdgeCases:
    """Edge case tests for StateEncoder."""
    
    def test_zero_price_change(self):
        """Test handling zero price change (zero changes are skipped)."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'last': Decimal("1.08500")},  # First price
            {'last': Decimal("1.08500")},  # ZERO - SKIPPED
            {'last': Decimal("1.08490")},  # DOWN
            {'last': Decimal("1.08510")},  # UP
            {'last': Decimal("1.08510")},  # ZERO - SKIPPED
            {'last': Decimal("1.08505")},  # DOWN
            {'last': Decimal("1.08520")},  # UP
            {'last': Decimal("1.08525")}   # UP
        ]
        
        for tick in ticks:
            encoder.process_tick(tick)
        
        state = encoder.get_current_state()
        
        # Movements: DOWN(0), UP(1), DOWN(0), UP(1), UP(1)
        # Last 4 movements: UP, DOWN, UP, UP = 1011
        assert state is not None
        assert state.sequence == "1011"
    
    def test_very_large_price(self):
        """Test handling very large prices."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'last': Decimal("1000000.00")},
            {'last': Decimal("1000001.00")},
            {'last': Decimal("1000000.50")},
            {'last': Decimal("1000002.00")},
            {'last': Decimal("1000003.00")}
        ]
        
        for tick in ticks:
            encoder.process_tick(tick)
        
        state = encoder.get_current_state()
        assert state is not None
    
    def test_very_small_price_changes(self):
        """Test handling very small price changes."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'last': Decimal("1.085000000")},
            {'last': Decimal("1.085000001")},  # Very small UP
            {'last': Decimal("1.085000000")},  # Very small DOWN
            {'last': Decimal("1.085000002")},  # Very small UP
            {'last': Decimal("1.085000003")}   # Very small UP
        ]
        
        for tick in ticks:
            encoder.process_tick(tick)
        
        state = encoder.get_current_state()
        assert state is not None
        assert state.sequence == "1011"
    
    def test_missing_price_key(self):
        """Test handling of missing price key in tick."""
        encoder = StateEncoder(depth=4)
        
        tick = {
            'timestamp': datetime.now(),
            'symbol': 'EUR/USDT'
            # Missing 'last' key
        }
        
        # Should return None and log warning, not raise exception
        result = encoder.process_tick(tick)
        assert result is None
    
    def test_continuous_uptrend(self):
        """Test continuous uptrend produces all 1s."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'last': Decimal("1.08500")},
            {'last': Decimal("1.08510")},  # UP
            {'last': Decimal("1.08520")},  # UP
            {'last': Decimal("1.08530")},  # UP
            {'last': Decimal("1.08540")}   # UP
        ]
        
        for tick in ticks:
            encoder.process_tick(tick)
        
        state = encoder.get_current_state()
        assert state.sequence == "1111"
    
    def test_continuous_downtrend(self):
        """Test continuous downtrend produces all 0s."""
        encoder = StateEncoder(depth=4)
        
        ticks = [
            {'last': Decimal("1.08500")},
            {'last': Decimal("1.08490")},  # DOWN
            {'last': Decimal("1.08480")},  # DOWN
            {'last': Decimal("1.08470")},  # DOWN
            {'last': Decimal("1.08460")}   # DOWN
        ]
        
        for tick in ticks:
            encoder.process_tick(tick)
        
        state = encoder.get_current_state()
        assert state.sequence == "0000"
    
    def test_alternating_pattern(self):
        """Test alternating up/down pattern."""
        encoder = StateEncoder(depth=8)
        
        ticks = [
            {'last': Decimal("1.08500")},
            {'last': Decimal("1.08510")},  # UP
            {'last': Decimal("1.08500")},  # DOWN
            {'last': Decimal("1.08510")},  # UP
            {'last': Decimal("1.08500")},  # DOWN
            {'last': Decimal("1.08510")},  # UP
            {'last': Decimal("1.08500")},  # DOWN
            {'last': Decimal("1.08510")},  # UP
            {'last': Decimal("1.08500")}   # DOWN
        ]
        
        for tick in ticks:
            encoder.process_tick(tick)
        
        state = encoder.get_current_state()
        assert state.sequence == "10101010"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
