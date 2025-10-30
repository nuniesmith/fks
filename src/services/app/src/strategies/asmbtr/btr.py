"""BTR (Binary Tree Representation) Encoder.

This module implements the core BTR encoding mechanism that converts
price movement sequences into binary tree states for the ASMBTR strategy.

A BTR state represents the recent history of price movements as a binary
string where:
- "1" = price went up
- "0" = price went down

For example, with depth=8, the state "10110011" represents:
- Most recent: up (1)
- Before that: up (1)
- Before that: down (0)
- ... and so on for 8 movements

This creates 2^depth possible states (e.g., 256 states for depth=8).

Reference: AI Enhancement Plan Phase 2 (lines 907-948)
"""

from dataclasses import dataclass
from typing import List, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class BTRState:
    """Represents a BTR state with metadata.
    
    Attributes:
        sequence: Binary string representation (e.g., "10110011")
        depth: Number of movements in the sequence
        decimal_value: Integer representation of binary sequence
        total_states: Total possible states for this depth (2^depth)
    """
    sequence: str
    depth: int
    
    @property
    def decimal_value(self) -> int:
        """Convert binary sequence to decimal.
        
        Returns:
            Integer representation (e.g., "10110011" -> 179)
        """
        if not self.sequence:
            return 0
        return int(self.sequence, 2)
    
    @property
    def total_states(self) -> int:
        """Total possible states for this depth.
        
        Returns:
            2^depth (e.g., depth=8 -> 256 states)
        """
        return 2 ** self.depth
    
    def to_decimal(self) -> int:
        """Convert binary sequence to decimal (alias for decimal_value property).
        
        Returns:
            Integer representation (e.g., "10110011" -> 179)
        """
        return self.decimal_value
    
    @classmethod
    def from_decimal(cls, value: int, depth: int) -> 'BTRState':
        """Create BTRState from decimal value.
        
        Args:
            value: Decimal value to convert
            depth: Desired depth of binary sequence
        
        Returns:
            BTRState with binary sequence
        
        Example:
            >>> state = BTRState.from_decimal(179, depth=8)
            >>> print(state.sequence)  # "10110011"
        """
        # Convert to binary and remove '0b' prefix
        binary = bin(value)[2:]
        
        # Pad with zeros to match depth
        binary = binary.zfill(depth)
        
        return cls(sequence=binary, depth=depth)
    
    def __str__(self) -> str:
        return f"BTRState({self.sequence})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, BTRState):
            return False
        return self.sequence == other.sequence and self.depth == other.depth
    
    def __hash__(self) -> int:
        return hash((self.sequence, self.depth))


class BTREncoder:
    """Encodes price movements as Binary Tree Representation states.
    
    The encoder maintains a sliding window of recent price movements
    and generates BTR states that can be used for prediction lookup.
    
    Attributes:
        depth: Number of movements to track (default: 8)
        movement_buffer: Deque storing recent movements as "1" or "0"
    
    Example:
        >>> encoder = BTREncoder(depth=8)
        >>> encoder.add_movement(True)   # Price went up
        >>> encoder.add_movement(False)  # Price went down
        >>> encoder.add_movement(True)   # Price went up
        >>> state = encoder.get_state()
        >>> print(state.sequence)  # "101"
    """
    
    def __init__(self, depth: int = 8):
        """Initialize BTR encoder.
        
        Args:
            depth: Number of movements to track (2-64, default: 8)
        
        Raises:
            ValueError: If depth is not in valid range
        """
        if not 2 <= depth <= 64:
            raise ValueError(f"Depth must be between 2 and 64, got {depth}")
        
        self.depth = depth
        self.movement_buffer: deque = deque(maxlen=depth)
        
        logger.debug(f"Initialized BTREncoder with depth={depth} (total_states={2**depth})")
    
    @property
    def buffer(self) -> deque:
        """Alias for movement_buffer for backward compatibility.
        
        Returns:
            The movement buffer deque
        """
        return self.movement_buffer
    
    def add_movement(self, is_up: bool = None, up: bool = None) -> None:
        """Add a price movement to the buffer.
        
        Args:
            is_up: True if price went up, False if down (deprecated: use 'up' instead)
            up: True if price went up, False if down
        """
        # Support both parameter names for backward compatibility
        movement = up if up is not None else is_up
        if movement is None:
            raise ValueError("Either 'is_up' or 'up' parameter must be provided")
        
        self.movement_buffer.append(movement)  # Store as boolean
        
        if len(self.movement_buffer) == self.depth:
            logger.debug(f"Buffer full: {self.get_sequence()}")
    
    def add_binary(self, binary_value: str) -> None:
        """Add a movement using binary string representation.
        
        Args:
            binary_value: "1" for up, "0" for down
        
        Raises:
            ValueError: If binary_value is not "0" or "1"
        """
        if binary_value not in ("0", "1"):
            raise ValueError(f"Binary value must be '0' or '1', got '{binary_value}'")
        
        self.movement_buffer.append(binary_value == "1")  # Convert to boolean
    
    def add_sequence(self, sequence: str) -> None:
        """Add multiple movements from a binary sequence.
        
        Args:
            sequence: Binary string (e.g., "10110011")
        
        Raises:
            ValueError: If sequence contains non-binary characters
        """
        if not all(c in "01" for c in sequence):
            raise ValueError(f"Sequence must contain only '0' and '1', got '{sequence}'")
        
        for binary_char in sequence:
            self.add_binary(binary_char)
    
    def get_sequence(self) -> str:
        """Get current binary sequence.
        
        Returns:
            Binary string of recent movements (e.g., "10110011")
            Empty string if buffer is empty
        """
        return "".join("1" if is_up else "0" for is_up in self.movement_buffer)
    
    def get_state(self) -> Optional[BTRState]:
        """Get current BTR state.
        
        Returns:
            BTRState object if buffer has exactly depth movements, None otherwise
        """
        sequence = self.get_sequence()
        if not sequence or len(sequence) < self.depth:
            return None
        
        return BTRState(sequence=sequence, depth=len(sequence))
    
    def is_ready(self) -> bool:
        """Check if encoder has enough data for predictions.
        
        Returns:
            True if buffer is full (has depth movements)
        """
        return len(self.movement_buffer) == self.depth
    
    def reset(self) -> None:
        """Clear the movement buffer."""
        self.movement_buffer.clear()
        logger.debug("BTREncoder buffer cleared")
    
    def get_buffer_size(self) -> int:
        """Get current buffer size.
        
        Returns:
            Number of movements in buffer
        """
        return len(self.movement_buffer)
    
    def create_all_states(self) -> List[BTRState]:
        """Generate all possible BTR states for this encoder's depth.
        
        Instance method wrapper for module-level create_all_states function.
        Useful for initializing prediction tables with all states.
        
        Returns:
            List of all 2^depth possible BTR states
        
        Example:
            >>> encoder = BTREncoder(depth=3)
            >>> states = encoder.create_all_states()
            >>> len(states)
            8
        """
        return create_all_states(self.depth)
    
    def encode_deltas(self, deltas: List[float]) -> Optional[BTRState]:
        """Encode a list of price deltas to BTR state.
        
        Instance method that processes deltas and returns state.
        Uses the encoder's depth setting.
        Zero deltas are treated as DOWN (False/0).
        
        Args:
            deltas: List of price changes (positive=up, zero/negative=down)
        
        Returns:
            BTRState or None if insufficient data
        
        Example:
            >>> encoder = BTREncoder(depth=4)
            >>> deltas = [0.001, 0.000, 0.003, -0.001]
            >>> state = encoder.encode_deltas(deltas)
            >>> print(state.sequence)  # "1010"
        """
        for delta in deltas:
            # Treat zero and negative as DOWN, only positive as UP
            self.add_movement(is_up=(delta > 0))
        
        return self.get_state()
    
    @staticmethod
    def sequence_to_state(sequence: str) -> BTRState:
        """Convert a binary sequence string directly to BTRState.
        
        Args:
            sequence: Binary string (e.g., "10110011")
        
        Returns:
            BTRState object
        
        Raises:
            ValueError: If sequence is invalid
        """
        if not sequence:
            raise ValueError("Sequence cannot be empty")
        
        if not all(c in "01" for c in sequence):
            raise ValueError(f"Invalid binary sequence: {sequence}")
        
        return BTRState(sequence=sequence, depth=len(sequence))


def create_all_states(depth: int) -> List[BTRState]:
    """Generate all possible BTR states for a given depth.
    
    Useful for initializing prediction tables with all states.
    
    Args:
        depth: State depth (2-64)
    
    Returns:
        List of all 2^depth possible BTR states
    
    Example:
        >>> states = create_all_states(depth=3)
        >>> len(states)
        8
        >>> [s.sequence for s in states]
        ['000', '001', '010', '011', '100', '101', '110', '111']
    """
    if not 2 <= depth <= 64:
        raise ValueError(f"Depth must be between 2 and 64, got {depth}")
    
    total_states = 2 ** depth
    states = []
    
    for i in range(total_states):
        # Convert integer to binary, pad with zeros to reach depth
        binary_str = format(i, f'0{depth}b')
        states.append(BTRState(sequence=binary_str, depth=depth))
    
    logger.info(f"Generated {len(states)} states for depth={depth}")
    return states


if __name__ == "__main__":
    """Example usage and testing."""
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print(" BTR Encoder Example ".center(60, "="))
    print("="*60 + "\n")
    
    # Create encoder
    encoder = BTREncoder(depth=8)
    
    # Simulate price movements: up, up, down, up, down, down, up, up
    movements = [True, True, False, True, False, False, True, True]
    movement_labels = ["UP" if m else "DOWN" for m in movements]
    
    print("Adding movements:")
    for i, (movement, label) in enumerate(zip(movements, movement_labels), 1):
        encoder.add_movement(movement)
        print(f"  {i}. {label:4s} -> Buffer: {encoder.get_sequence()}")
    
    # Get final state
    state = encoder.get_state()
    print(f"\n✅ Final BTR State:")
    print(f"   Sequence: {state.sequence}")
    print(f"   Depth: {state.depth}")
    print(f"   Decimal: {state.decimal_value}")
    print(f"   Total possible states: {state.total_states}")
    
    # Test encode_deltas
    print(f"\n🔢 Testing encode_deltas:")
    deltas = [0.001, -0.002, 0.003, -0.001, 0.002]
    state2 = BTREncoder.encode_deltas(deltas, depth=5)
    print(f"   Deltas: {deltas}")
    print(f"   State: {state2.sequence} (decimal: {state2.decimal_value})")
    
    # Generate all states for depth=3
    print(f"\n🌳 All possible states for depth=3:")
    all_states = create_all_states(depth=3)
    for state in all_states:
        print(f"   {state.sequence} -> {state.decimal_value}")
    
    print("\n" + "="*60 + "\n")
