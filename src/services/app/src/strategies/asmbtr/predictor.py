"""Prediction Table for ASMBTR Strategy.

This module implements the state-to-probability mapping that forms
the core prediction engine of ASMBTR. It learns from historical data
to predict the next price movement based on current BTR state.

The prediction table maps:
  BTR State (e.g., "10110011") → Probability of next UP move

Phase: AI Enhancement Plan - Phase 2
Target: >0.5 prediction accuracy
"""

from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
import logging
from collections import defaultdict

from .btr import BTRState, create_all_states

logger = logging.getLogger(__name__)


@dataclass
class StatePrediction:
    """Prediction for a BTR state.
    
    Attributes:
        state: The BTR state
        up_probability: Probability of next move being UP (0.0-1.0)
        down_probability: Probability of next move being DOWN (0.0-1.0)
        observations: Number of times this state was observed
        up_count: Number of times next move was UP
        down_count: Number of times next move was DOWN
    """
    state: BTRState
    up_probability: float
    down_probability: float
    observations: int
    up_count: int
    down_count: int
    
    @property
    def prediction(self) -> str:
        """Get predicted direction.
        
        Returns:
            "UP", "DOWN", or "NEUTRAL" based on probabilities
        """
        if self.up_probability > self.down_probability:
            return "UP"
        elif self.down_probability > self.up_probability:
            return "DOWN"
        else:
            return "NEUTRAL"
    
    @property
    def confidence(self) -> float:
        """Get prediction confidence.
        
        Returns:
            Absolute difference between up and down probabilities (0.0-1.0)
        """
        return abs(self.up_probability - self.down_probability)
    
    def __str__(self) -> str:
        return (f"StatePrediction(state={self.state.sequence}, "
                f"pred={self.prediction}, "
                f"up_prob={self.up_probability:.3f}, "
                f"confidence={self.confidence:.3f}, "
                f"obs={self.observations})")


class PredictionTable:
    """Maps BTR states to next-move probabilities.
    
    The prediction table learns from historical price sequences:
    1. Observe a BTR state (e.g., "10110011")
    2. Record the next price movement (UP or DOWN)
    3. Update probability: P(UP|state) = up_count / total_count
    
    Attributes:
        depth: BTR state depth
        state_counts: Tracks observations for each state
        decay_rate: Optional decay for older observations (default: 1.0 = no decay)
    """
    
    def __init__(self, depth: int = 8, decay_rate: float = 1.0):
        """Initialize prediction table.
        
        Args:
            depth: BTR state depth (2-64, default: 8)
            decay_rate: Decay factor for older observations (0.95-1.0, default: 1.0)
        
        Raises:
            ValueError: If parameters out of valid range
        """
        if not 2 <= depth <= 64:
            raise ValueError(f"Depth must be between 2 and 64, got {depth}")
        
        if not 0.9 <= decay_rate <= 1.0:
            raise ValueError(f"Decay rate must be between 0.9 and 1.0, got {decay_rate}")
        
        self.depth = depth
        self.decay_rate = decay_rate
        
        # State tracking: {state_sequence: {'up': count, 'down': count}}
        self.state_counts: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {'up': 0.0, 'down': 0.0}
        )
        
        self.total_observations = 0
        
        logger.info(f"PredictionTable initialized: depth={depth}, decay={decay_rate}")
    
    def observe(self, state: BTRState, next_move_up: bool) -> None:
        """Record an observation of state → next move.
        
        Args:
            state: Current BTR state
            next_move_up: True if next move was UP, False if DOWN
        """
        if state.depth != self.depth:
            logger.warning(f"State depth {state.depth} doesn't match table depth {self.depth}")
            return
        
        # Update counts
        if next_move_up:
            self.state_counts[state.sequence]['up'] += 1.0
        else:
            self.state_counts[state.sequence]['down'] += 1.0
        
        self.total_observations += 1
        
        if self.total_observations % 1000 == 0:
            logger.debug(f"Observations: {self.total_observations}, "
                        f"Unique states: {len(self.state_counts)}")
    
    def observe_sequence(self, states: List[BTRState], outcomes: List[bool]) -> None:
        """Record multiple observations.
        
        Args:
            states: List of BTR states
            outcomes: List of next moves (True=UP, False=DOWN)
        
        Raises:
            ValueError: If lengths don't match
        """
        if len(states) != len(outcomes):
            raise ValueError(f"States ({len(states)}) and outcomes ({len(outcomes)}) must have same length")
        
        for state, outcome in zip(states, outcomes):
            self.observe(state, outcome)
        
        logger.info(f"Observed {len(states)} state transitions")
    
    def predict(self, state: BTRState, min_observations: int = 1) -> Optional[StatePrediction]:
        """Get prediction for a BTR state.
        
        Args:
            state: BTR state to predict
            min_observations: Minimum observations required (default: 1)
        
        Returns:
            StatePrediction or None if insufficient data
        """
        if state.depth != self.depth:
            logger.warning(f"State depth {state.depth} doesn't match table depth {self.depth}")
            return None
        
        counts = self.state_counts.get(state.sequence)
        if not counts:
            logger.debug(f"No observations for state {state.sequence}")
            return None
        
        up_count = counts['up']
        down_count = counts['down']
        total = up_count + down_count
        
        if total < min_observations:
            logger.debug(f"Insufficient observations for {state.sequence}: {total} < {min_observations}")
            return None
        
        up_prob = up_count / total if total > 0 else 0.5
        down_prob = down_count / total if total > 0 else 0.5
        
        return StatePrediction(
            state=state,
            up_probability=up_prob,
            down_probability=down_prob,
            observations=int(total),
            up_count=int(up_count),
            down_count=int(down_count)
        )
    
    def get_all_predictions(self, min_observations: int = 1) -> List[StatePrediction]:
        """Get predictions for all observed states.
        
        Args:
            min_observations: Minimum observations required
        
        Returns:
            List of StatePrediction objects
        """
        from .btr import BTRState
        
        predictions = []
        for sequence in self.state_counts.keys():
            state = BTRState(sequence=sequence, depth=len(sequence))
            pred = self.predict(state, min_observations=min_observations)
            if pred:
                predictions.append(pred)
        
        return predictions
    
    def apply_decay(self) -> None:
        """Apply decay to all observation counts.
        
        This reduces the weight of older observations, allowing the
        model to adapt to changing market conditions.
        """
        if self.decay_rate >= 1.0:
            return  # No decay
        
        for counts in self.state_counts.values():
            counts['up'] *= self.decay_rate
            counts['down'] *= self.decay_rate
        
        logger.info(f"Applied decay (rate={self.decay_rate}) to {len(self.state_counts)} states")
    
    def get_statistics(self) -> Dict:
        """Get prediction table statistics.
        
        Returns:
            Dictionary with stats
        """
        if not self.state_counts:
            return {
                'depth': self.depth,
                'total_observations': 0,
                'unique_states': 0,
                'coverage': 0.0,
                'avg_observations_per_state': 0.0
            }
        
        total_possible_states = 2 ** self.depth
        unique_states = len(self.state_counts)
        coverage = unique_states / total_possible_states
        
        total_obs = sum(
            counts['up'] + counts['down']
            for counts in self.state_counts.values()
        )
        avg_obs = total_obs / unique_states if unique_states > 0 else 0
        
        return {
            'depth': self.depth,
            'total_observations': int(total_obs),
            'unique_states': unique_states,
            'total_possible_states': total_possible_states,
            'coverage': round(coverage * 100, 2),
            'avg_observations_per_state': round(avg_obs, 2),
            'decay_rate': self.decay_rate
        }
    
    def get_top_states(self, n: int = 10, by: str = 'observations') -> List[StatePrediction]:
        """Get top N states by criteria.
        
        Args:
            n: Number of states to return
            by: Sort criteria ('observations', 'confidence', 'up_probability')
        
        Returns:
            List of top StatePrediction objects
        """
        predictions = self.get_all_predictions(min_observations=1)
        
        if by == 'observations':
            predictions.sort(key=lambda p: p.observations, reverse=True)
        elif by == 'confidence':
            predictions.sort(key=lambda p: p.confidence, reverse=True)
        elif by == 'up_probability':
            predictions.sort(key=lambda p: p.up_probability, reverse=True)
        else:
            raise ValueError(f"Invalid sort criteria: {by}")
        
        return predictions[:n]
    
    def save_to_dict(self) -> Dict:
        """Export prediction table to dictionary.
        
        Returns:
            Dictionary representation for serialization
        """
        return {
            'depth': self.depth,
            'decay_rate': self.decay_rate,
            'total_observations': self.total_observations,
            'state_counts': dict(self.state_counts)
        }
    
    @classmethod
    def load_from_dict(cls, data: Dict) -> 'PredictionTable':
        """Load prediction table from dictionary.
        
        Args:
            data: Dictionary from save_to_dict()
        
        Returns:
            Loaded PredictionTable instance
        """
        table = cls(depth=data['depth'], decay_rate=data['decay_rate'])
        table.total_observations = data['total_observations']
        table.state_counts = defaultdict(
            lambda: {'up': 0.0, 'down': 0.0},
            data['state_counts']
        )
        return table


if __name__ == "__main__":
    """Example usage."""
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print(" Prediction Table Example ".center(70, "="))
    print("="*70 + "\n")
    
    # Create prediction table
    table = PredictionTable(depth=8)
    
    # Simulate learning from historical data
    print("📚 Learning from simulated data...")
    
    from .btr import BTREncoder
    import random
    
    # Generate training data
    encoder = BTREncoder(depth=8)
    observations = []
    
    # Simulate 1000 price movements
    for _ in range(1000):
        is_up = random.random() > 0.5
        encoder.add_movement(is_up)
        
        if encoder.is_ready():
            state = encoder.get_state()
            next_move_up = random.random() > 0.4  # Slight bullish bias
            observations.append((state, next_move_up))
    
    # Train table
    states, outcomes = zip(*observations) if observations else ([], [])
    table.observe_sequence(list(states), list(outcomes))
    
    print(f"  Observed {len(observations)} transitions")
    
    # Get statistics
    stats = table.get_statistics()
    print(f"\n📊 Prediction Table Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Get top predictions
    print(f"\n🔝 Top 5 States by Observations:")
    top_states = table.get_top_states(n=5, by='observations')
    for i, pred in enumerate(top_states, 1):
        print(f"  {i}. State: {pred.state.sequence}")
        print(f"     Prediction: {pred.prediction} (confidence: {pred.confidence:.3f})")
        print(f"     Up prob: {pred.up_probability:.3f}, Observations: {pred.observations}")
    
    # Test prediction
    print(f"\n🔮 Example Prediction:")
    test_state = top_states[0].state
    prediction = table.predict(test_state)
    if prediction:
        print(f"  State: {prediction.state.sequence}")
        print(f"  Prediction: {prediction.prediction}")
        print(f"  Up probability: {prediction.up_probability:.3f}")
        print(f"  Confidence: {prediction.confidence:.3f}")
        print(f"  Based on {prediction.observations} observations")
    
    print("\n" + "="*70 + "\n")
