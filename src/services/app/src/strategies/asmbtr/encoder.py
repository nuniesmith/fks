"""State Encoder for ASMBTR Strategy.

This module converts price change sequences from the delta scanner
into BTR states for prediction lookup. It serves as the bridge between
raw tick data and the ASMBTR prediction engine.

Phase: AI Enhancement Plan - Phase 2
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
import logging

from .btr import BTREncoder, BTRState

logger = logging.getLogger(__name__)


class StateEncoder:
    """Encodes price changes into BTR states.
    
    This encoder takes price data (from forex_collector) and price changes
    (from delta_scanner) and produces BTR states ready for prediction lookup.
    
    Attributes:
        depth: BTR encoding depth (default: 8)
        encoder: BTREncoder instance
        last_price: Last price processed
        states_generated: Count of states generated
    """
    
    def __init__(self, depth: int = 8):
        """Initialize state encoder.
        
        Args:
            depth: BTR encoding depth (2-64, default: 8)
        """
        self.depth = depth
        self.encoder = BTREncoder(depth=depth)
        self.last_price: Optional[Decimal] = None
        self.states_generated = 0
        
        logger.info(f"StateEncoder initialized with depth={depth}")
    
    def process_price(self, price: Decimal) -> Optional[BTRState]:
        """Process a single price update and generate BTR state.
        
        Args:
            price: Current price
        
        Returns:
            BTRState if encoder is ready, None otherwise
        """
        if self.last_price is None:
            self.last_price = price
            return None
        
        # Determine movement direction
        is_up = price > self.last_price
        is_down = price < self.last_price
        
        # Only add if price actually moved
        if is_up or is_down:
            self.encoder.add_movement(is_up)
            self.last_price = price
            
            # Generate state if ready
            if self.encoder.is_ready():
                state = self.encoder.get_state()
                self.states_generated += 1
                logger.debug(f"Generated state {self.states_generated}: {state.sequence}")
                return state
        
        return None
    
    def process_tick(self, tick: Dict[str, Any], price_key: str = 'last') -> Optional[BTRState]:
        """Process a tick dictionary from forex_collector.
        
        Args:
            tick: Tick dictionary with price data
            price_key: Key to extract price from tick (default: 'last')
        
        Returns:
            BTRState if generated, None otherwise
        """
        price = tick.get(price_key)
        if price is None:
            logger.warning(f"Price key '{price_key}' not found in tick")
            return None
        
        if not isinstance(price, Decimal):
            price = Decimal(str(price))
        
        return self.process_price(price)
    
    def process_ticks(self, ticks: List[Dict[str, Any]], price_key: str = 'last') -> List[BTRState]:
        """Process multiple ticks and generate BTR states.
        
        Args:
            ticks: List of tick dictionaries
            price_key: Key to extract price from tick
        
        Returns:
            List of generated BTR states
        """
        states = []
        
        for tick in ticks:
            state = self.process_tick(tick, price_key=price_key)
            if state:
                states.append(state)
        
        logger.info(f"Processed {len(ticks)} ticks, generated {len(states)} states")
        return states
    
    def process_delta_sequence(self, deltas: List[float]) -> Optional[BTRState]:
        """Process a sequence of price deltas directly.
        
        Useful when you have pre-calculated deltas from delta_scanner.
        
        Args:
            deltas: List of price changes (positive=up, negative=down)
        
        Returns:
            BTRState or None if insufficient data
        """
        return self.encoder.encode_deltas(deltas)
    
    def process_binary_sequence(self, binary_sequence: str) -> BTRState:
        """Process a binary sequence directly to BTR state.
        
        Useful when you already have binary sequences from delta_scanner.
        
        Args:
            binary_sequence: Binary string (e.g., "10110011")
        
        Returns:
            BTRState object
        
        Raises:
            ValueError: If sequence is invalid
        """
        return BTREncoder.sequence_to_state(binary_sequence)
    
    def reset(self) -> None:
        """Reset encoder state."""
        self.encoder.reset()
        self.last_price = None
        logger.info("StateEncoder reset")
    
    def is_ready(self) -> bool:
        """Check if encoder is ready to generate states.
        
        Returns:
            True if encoder has enough data
        """
        return self.encoder.is_ready()
    
    def get_current_state(self) -> Optional[BTRState]:
        """Get current BTR state without adding new data.
        
        Returns:
            Current BTRState or None if not ready
        """
        return self.encoder.get_state()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get encoder statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            'depth': self.depth,
            'states_generated': self.states_generated,
            'buffer_size': self.encoder.get_buffer_size(),
            'is_ready': self.is_ready(),
            'current_sequence': self.encoder.get_sequence(),
            'last_price': float(self.last_price) if self.last_price else None
        }


class MultiSymbolEncoder:
    """Manages BTR encoding for multiple symbols.
    
    Useful for trading strategies that track multiple currency pairs
    or assets simultaneously.
    
    Attributes:
        depth: BTR encoding depth
        encoders: Dictionary mapping symbols to StateEncoder instances
    """
    
    def __init__(self, depth: int = 8):
        """Initialize multi-symbol encoder.
        
        Args:
            depth: BTR encoding depth for all symbols
        """
        self.depth = depth
        self.encoders: Dict[str, StateEncoder] = {}
        
        logger.info(f"MultiSymbolEncoder initialized with depth={depth}")
    
    def get_encoder(self, symbol: str) -> StateEncoder:
        """Get or create encoder for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "EUR/USDT")
        
        Returns:
            StateEncoder instance for the symbol
        """
        if symbol not in self.encoders:
            self.encoders[symbol] = StateEncoder(depth=self.depth)
            logger.info(f"Created encoder for {symbol}")
        
        return self.encoders[symbol]
    
    def process_tick(self, tick: Dict[str, Any], price_key: str = 'last') -> Optional[BTRState]:
        """Process a tick for its symbol.
        
        Args:
            tick: Tick dictionary with 'symbol' and price data
            price_key: Key to extract price from tick
        
        Returns:
            BTRState if generated, None otherwise
        """
        symbol = tick.get('symbol')
        if not symbol:
            logger.warning("Tick missing 'symbol' field")
            return None
        
        encoder = self.get_encoder(symbol)
        return encoder.process_tick(tick, price_key=price_key)
    
    def process_ticks(self, ticks: List[Dict[str, Any]], price_key: str = 'last') -> Dict[str, List[BTRState]]:
        """Process ticks for all symbols.
        
        Args:
            ticks: List of tick dictionaries
            price_key: Key to extract price from tick
        
        Returns:
            Dictionary mapping symbols to lists of BTR states
        """
        states_by_symbol: Dict[str, List[BTRState]] = {}
        
        for tick in ticks:
            state = self.process_tick(tick, price_key=price_key)
            if state:
                symbol = tick.get('symbol', 'UNKNOWN')
                if symbol not in states_by_symbol:
                    states_by_symbol[symbol] = []
                states_by_symbol[symbol].append(state)
        
        return states_by_symbol
    
    def get_state(self, symbol: str) -> Optional[BTRState]:
        """Get current state for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            BTRState or None if symbol not tracked or not ready
        """
        if symbol not in self.encoders:
            return None
        
        return self.encoders[symbol].get_current_state()
    
    def get_all_states(self) -> Dict[str, Optional[BTRState]]:
        """Get current states for all tracked symbols.
        
        Returns:
            Dictionary mapping symbols to their current states
        """
        return {
            symbol: encoder.get_current_state()
            for symbol, encoder in self.encoders.items()
        }
    
    def reset(self, symbol: Optional[str] = None) -> None:
        """Reset encoder(s).
        
        Args:
            symbol: Specific symbol to reset, or None to reset all
        """
        if symbol:
            if symbol in self.encoders:
                self.encoders[symbol].reset()
                logger.info(f"Reset encoder for {symbol}")
        else:
            for encoder in self.encoders.values():
                encoder.reset()
            logger.info("Reset all encoders")
    
    def get_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all symbols.
        
        Returns:
            Dictionary mapping symbols to their statistics
        """
        return {
            symbol: encoder.get_statistics()
            for symbol, encoder in self.encoders.items()
        }


if __name__ == "__main__":
    """Example usage."""
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print(" State Encoder Example ".center(60, "="))
    print("="*60 + "\n")
    
    # Single symbol encoding
    print("📊 Single Symbol Encoding (EUR/USDT):")
    encoder = StateEncoder(depth=8)
    
    # Simulate tick data
    base_price = Decimal("1.08500")
    ticks = []
    
    for i in range(12):
        import random
        change = Decimal(str(random.uniform(-0.0001, 0.0001)))
        new_price = base_price + change
        
        ticks.append({
            'symbol': 'EUR/USDT',
            'last': new_price,
            'timestamp': f"2025-10-29 12:{i:02d}:00"
        })
        
        base_price = new_price
    
    # Process ticks
    states = encoder.process_ticks(ticks)
    
    print(f"  Processed {len(ticks)} ticks")
    print(f"  Generated {len(states)} states")
    
    if states:
        print(f"\n  Sample States:")
        for i, state in enumerate(states[:3], 1):
            print(f"    {i}. {state.sequence} (decimal: {state.decimal_value})")
    
    # Statistics
    stats = encoder.get_statistics()
    print(f"\n  Statistics:")
    for key, value in stats.items():
        print(f"    {key}: {value}")
    
    # Multi-symbol encoding
    print(f"\n📊 Multi-Symbol Encoding:")
    multi_encoder = MultiSymbolEncoder(depth=8)
    
    # Add symbol to each tick
    for tick in ticks[:6]:
        tick['symbol'] = 'EUR/USDT'
    for tick in ticks[6:]:
        tick['symbol'] = 'GBP/USDT'
    
    states_by_symbol = multi_encoder.process_ticks(ticks)
    
    print(f"  Symbols tracked: {len(states_by_symbol)}")
    for symbol, states in states_by_symbol.items():
        print(f"    {symbol}: {len(states)} states")
    
    print("\n" + "="*60 + "\n")
