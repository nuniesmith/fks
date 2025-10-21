"""
Test suite for trading strategies module
"""

import pytest
from datetime import datetime
from trading.strategies.base import (
    BaseStrategy,
    TradingSignal,
    StrategyMetrics,
    MarketData,
    MarketEvent,
    StrategyState,
)


class MockStrategy(BaseStrategy):
    """Mock strategy for testing BaseStrategy functionality"""
    
    async def analyze(self, market_data: MarketData) -> TradingSignal | None:
        """Simple analysis that generates signals based on price threshold"""
        if market_data.price > 50000:
            return TradingSignal(
                strategy_id=self.strategy_id,
                symbol="BTCUSDT",
                action="BUY",
                quantity=0.1,
                confidence=0.8,
                reason="Price above threshold",
                metadata={"price": market_data.price},
                timestamp=datetime.utcnow()
            )
        elif market_data.price < 45000:
            return TradingSignal(
                strategy_id=self.strategy_id,
                symbol="BTCUSDT",
                action="SELL",
                quantity=0.1,
                confidence=0.7,
                reason="Price below threshold",
                metadata={"price": market_data.price},
                timestamp=datetime.utcnow()
            )
        return None


@pytest.mark.unit
@pytest.mark.trading
class TestBaseStrategy:
    """Test BaseStrategy class functionality"""
    
    def test_strategy_initialization(self):
        """Test strategy initialization with config"""
        config = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "risk_per_trade": 0.02
        }
        strategy = MockStrategy(strategy_id="test_strategy", config=config)
        
        assert strategy.strategy_id == "test_strategy"
        assert strategy.config == config
        assert strategy.is_active is True
        assert isinstance(strategy.state, dict)
        assert isinstance(strategy.metrics, StrategyMetrics)
    
    def test_strategy_state_initialization(self):
        """Test strategy state is properly initialized"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        
        assert strategy.state == {}
        assert strategy.is_active is True
    
    def test_strategy_metrics_initialization(self):
        """Test strategy metrics initialization"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        
        assert strategy.metrics.strategy_id == "test_strategy"
        assert strategy.metrics.total_return == 0.0
        assert strategy.metrics.sharpe_ratio == 0.0
        assert strategy.metrics.max_drawdown == 0.0
    
    @pytest.mark.asyncio
    async def test_process_event_generates_signal(self):
        """Test that process() generates signals from events"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        
        event = MarketEvent(
            event_type="price_update",
            data={
                "symbol": "BTCUSDT",
                "price": 51000.0,
                "volume": 1000.0,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        signal = await strategy.process(event)
        
        assert signal is not None
        assert signal.action == "BUY"
        assert signal.symbol == "BTCUSDT"
        assert signal.confidence == 0.8
    
    @pytest.mark.asyncio
    async def test_process_event_no_signal(self):
        """Test that process() returns None when no signal"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        
        event = MarketEvent(
            event_type="price_update",
            data={
                "symbol": "BTCUSDT",
                "price": 48000.0,  # Between thresholds
                "volume": 1000.0,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        signal = await strategy.process(event)
        
        assert signal is None
    
    @pytest.mark.asyncio
    async def test_should_process_active_strategy(self):
        """Test that active strategy processes valid events"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        
        event = MarketEvent(
            event_type="price_update",
            data={"symbol": "BTCUSDT", "price": 50000.0}
        )
        
        should_process = await strategy.should_process(event)
        
        assert should_process is True
    
    @pytest.mark.asyncio
    async def test_should_not_process_inactive_strategy(self):
        """Test that inactive strategy doesn't process events"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        strategy.is_active = False
        
        event = MarketEvent(
            event_type="price_update",
            data={"symbol": "BTCUSDT", "price": 50000.0}
        )
        
        should_process = await strategy.should_process(event)
        
        assert should_process is False
    
    @pytest.mark.asyncio
    async def test_should_not_process_invalid_event_type(self):
        """Test that strategy ignores invalid event types"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        
        event = MarketEvent(
            event_type="invalid_event",
            data={"symbol": "BTCUSDT", "price": 50000.0}
        )
        
        should_process = await strategy.should_process(event)
        
        assert should_process is False
    
    @pytest.mark.asyncio
    async def test_update_state_creates_new_symbol(self):
        """Test that update_state creates new symbols in state"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        
        event = MarketEvent(
            event_type="price_update",
            data={"symbol": "BTCUSDT", "price": 50000.0}
        )
        
        await strategy.update_state(event)
        
        assert "BTCUSDT" in strategy.state
        assert strategy.state["BTCUSDT"] == StrategyState.IDLE
    
    @pytest.mark.asyncio
    async def test_validate_signal_returns_signal(self):
        """Test that validate_signal returns the signal"""
        strategy = MockStrategy(strategy_id="test_strategy", config={})
        
        signal = TradingSignal(
            strategy_id="test_strategy",
            symbol="BTCUSDT",
            action="BUY",
            quantity=0.1,
            confidence=0.8,
            reason="Test signal",
            metadata={},
            timestamp=datetime.utcnow()
        )
        
        validated = await strategy.validate_signal(signal)
        
        assert validated == signal


@pytest.mark.unit
@pytest.mark.trading
class TestTradingSignal:
    """Test TradingSignal dataclass"""
    
    def test_trading_signal_creation(self):
        """Test creating a trading signal"""
        timestamp = datetime.utcnow()
        signal = TradingSignal(
            strategy_id="test_strategy",
            symbol="BTCUSDT",
            action="BUY",
            quantity=0.5,
            confidence=0.85,
            reason="Strong upward momentum",
            metadata={"rsi": 35, "macd": 0.5},
            timestamp=timestamp
        )
        
        assert signal.strategy_id == "test_strategy"
        assert signal.symbol == "BTCUSDT"
        assert signal.action == "BUY"
        assert signal.quantity == 0.5
        assert signal.confidence == 0.85
        assert signal.reason == "Strong upward momentum"
        assert signal.metadata["rsi"] == 35
        assert signal.timestamp == timestamp
    
    def test_trading_signal_valid_actions(self):
        """Test signal with different action types"""
        actions = ["BUY", "SELL", "HOLD"]
        
        for action in actions:
            signal = TradingSignal(
                strategy_id="test",
                symbol="BTCUSDT",
                action=action,
                quantity=0.1,
                confidence=0.7,
                reason="Test",
                metadata={},
                timestamp=datetime.utcnow()
            )
            assert signal.action == action


@pytest.mark.unit
@pytest.mark.trading
class TestStrategyMetrics:
    """Test StrategyMetrics dataclass"""
    
    def test_metrics_initialization(self):
        """Test metrics initialization with defaults"""
        metrics = StrategyMetrics(strategy_id="test_strategy")
        
        assert metrics.strategy_id == "test_strategy"
        assert metrics.total_return == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown == 0.0
    
    def test_metrics_with_values(self):
        """Test metrics with custom values"""
        metrics = StrategyMetrics(
            strategy_id="test_strategy",
            total_return=0.25,
            sharpe_ratio=2.1,
            max_drawdown=0.15
        )
        
        assert metrics.total_return == 0.25
        assert metrics.sharpe_ratio == 2.1
        assert metrics.max_drawdown == 0.15


@pytest.mark.unit
@pytest.mark.trading
class TestMarketData:
    """Test MarketData dataclass"""
    
    def test_market_data_creation(self):
        """Test creating market data"""
        data = MarketData(
            price=50000.0,
            volume=1234.56,
            timestamp="2023-01-01T00:00:00"
        )
        
        assert data.price == 50000.0
        assert data.volume == 1234.56
        assert data.timestamp == "2023-01-01T00:00:00"


@pytest.mark.unit
@pytest.mark.trading
class TestMarketEvent:
    """Test MarketEvent dataclass"""
    
    def test_market_event_creation(self):
        """Test creating a market event"""
        event = MarketEvent(
            event_type="price_update",
            data={
                "symbol": "BTCUSDT",
                "price": 50000.0,
                "volume": 1000.0
            }
        )
        
        assert event.event_type == "price_update"
        assert event.data["symbol"] == "BTCUSDT"
        assert event.data["price"] == 50000.0
    
    def test_market_event_different_types(self):
        """Test events with different types"""
        event_types = ["price_update", "market_data", "trade_execution", "order_update"]
        
        for event_type in event_types:
            event = MarketEvent(
                event_type=event_type,
                data={"test": "data"}
            )
            assert event.event_type == event_type


@pytest.mark.unit
@pytest.mark.trading
class TestStrategyState:
    """Test StrategyState enum"""
    
    def test_strategy_states(self):
        """Test all strategy states are defined"""
        assert StrategyState.IDLE.value == "idle"
        assert StrategyState.RUNNING.value == "running"
        assert StrategyState.STOPPED.value == "stopped"
    
    def test_state_comparison(self):
        """Test state comparisons"""
        state1 = StrategyState.IDLE
        state2 = StrategyState.IDLE
        state3 = StrategyState.RUNNING
        
        assert state1 == state2
        assert state1 != state3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
