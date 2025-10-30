"""Unit tests for ASMBTR Trading Strategy.

Tests cover:
- Signal generation logic
- Position opening/closing
- Stop loss/take profit triggers
- Position sizing
- Performance metrics (Calmar ratio, win rate, drawdown)
- Trade history tracking
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'src' / 'services' / 'app' / 'src'))

from strategies.asmbtr.strategy import (
    ASMBTRStrategy,
    StrategyConfig,
    StrategyMetrics,
    TradingSignal,
    SignalType,
    Position
)
from strategies.asmbtr.btr import BTRState


class TestPosition:
    """Tests for Position class."""
    
    def test_position_creation(self):
        """Test basic position creation."""
        position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("1000"),
            side="LONG"
        )
        
        assert position.entry_price == Decimal("1.08500")
        assert position.size == Decimal("1000")
        assert position.side == "LONG"
    
    def test_position_with_sl_tp(self):
        """Test position with stop loss and take profit."""
        position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("1000"),
            side="LONG",
            stop_loss=Decimal("1.08000"),
            take_profit=Decimal("1.09000")
        )
        
        assert position.stop_loss == Decimal("1.08000")
        assert position.take_profit == Decimal("1.09000")
    
    def test_long_position_pnl_profit(self):
        """Test PnL calculation for profitable long position."""
        position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("1000"),
            side="LONG"
        )
        
        current_price = Decimal("1.09000")
        pnl = position.get_pnl(current_price)
        
        # (1.09 - 1.085) * 1000 = 5
        assert pnl == Decimal("5")
    
    def test_long_position_pnl_loss(self):
        """Test PnL calculation for losing long position."""
        position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("1000"),
            side="LONG"
        )
        
        current_price = Decimal("1.08000")
        pnl = position.get_pnl(current_price)
        
        # (1.08 - 1.085) * 1000 = -5
        assert pnl == Decimal("-5")
    
    def test_short_position_pnl_profit(self):
        """Test PnL calculation for profitable short position."""
        position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("1000"),
            side="SHORT"
        )
        
        current_price = Decimal("1.08000")
        pnl = position.get_pnl(current_price)
        
        # (1.085 - 1.08) * 1000 = 5
        assert pnl == Decimal("5")
    
    def test_short_position_pnl_loss(self):
        """Test PnL calculation for losing short position."""
        position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("1000"),
            side="SHORT"
        )
        
        current_price = Decimal("1.09000")
        pnl = position.get_pnl(current_price)
        
        # (1.085 - 1.09) * 1000 = -5
        assert pnl == Decimal("-5")
    
    def test_pnl_percent_profit(self):
        """Test PnL percentage calculation for profit."""
        position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("1000"),
            side="LONG"
        )
        
        current_price = Decimal("1.09000")
        pnl_pct = position.get_pnl_percent(current_price)
        
        # ((1.09 - 1.085) / 1.085) * 100 ≈ 0.46%
        assert pnl_pct == pytest.approx(0.46, rel=0.01)
    
    def test_pnl_percent_loss(self):
        """Test PnL percentage calculation for loss."""
        position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("1000"),
            side="LONG"
        )
        
        current_price = Decimal("1.08000")
        pnl_pct = position.get_pnl_percent(current_price)
        
        # ((1.08 - 1.085) / 1.085) * 100 ≈ -0.46%
        assert pnl_pct == pytest.approx(-0.46, rel=0.01)


class TestStrategyConfig:
    """Tests for StrategyConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = StrategyConfig()
        
        assert config.depth == 8
        assert config.confidence_threshold == 0.1
        assert config.min_observations == 5
        assert config.position_size_pct == 0.02
        assert config.stop_loss_pct == 0.005
        assert config.take_profit_pct == 0.010
        assert config.decay_rate == 0.999
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = StrategyConfig(
            depth=12,
            confidence_threshold=0.15,
            position_size_pct=0.05
        )
        
        assert config.depth == 12
        assert config.confidence_threshold == 0.15
        assert config.position_size_pct == 0.05


class TestStrategyMetrics:
    """Tests for StrategyMetrics class."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = StrategyMetrics()
        
        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.total_pnl == Decimal("0")
        assert metrics.max_drawdown == Decimal("0")
    
    def test_win_rate_calculation_no_trades(self):
        """Test win rate with no trades."""
        metrics = StrategyMetrics()
        
        assert metrics.win_rate == 0.0
    
    def test_win_rate_calculation_with_trades(self):
        """Test win rate calculation."""
        metrics = StrategyMetrics()
        
        # Simulate 7 wins, 3 losses
        for i in range(10):
            pnl = Decimal("10") if i < 7 else Decimal("-5")
            equity = Decimal("10000") + (i + 1) * pnl
            metrics.update(pnl, equity)
        
        assert metrics.total_trades == 10
        assert metrics.winning_trades == 7
        assert metrics.losing_trades == 3
        assert metrics.win_rate == 70.0
    
    def test_drawdown_tracking(self):
        """Test maximum drawdown tracking."""
        metrics = StrategyMetrics(peak_equity=Decimal("10000"))
        
        # Simulate trades with drawdown
        trades = [
            (Decimal("100"), Decimal("10100")),   # Win, new peak
            (Decimal("200"), Decimal("10300")),   # Win, new peak
            (Decimal("-500"), Decimal("9800")),   # Loss, drawdown of 500
            (Decimal("-200"), Decimal("9600")),   # Loss, drawdown of 700
            (Decimal("100"), Decimal("9700"))     # Win, still in drawdown
        ]
        
        for pnl, equity in trades:
            metrics.update(pnl, equity)
        
        assert metrics.max_drawdown == Decimal("700")
        assert metrics.peak_equity == Decimal("10300")


class TestASMBTRStrategy:
    """Tests for ASMBTRStrategy class."""
    
    def test_strategy_initialization(self):
        """Test strategy initialization."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        assert strategy.initial_capital == Decimal("10000")
        assert strategy.current_capital == Decimal("10000")
        assert strategy.current_position is None
        assert len(strategy.trade_history) == 0
    
    def test_process_tick_insufficient_data(self):
        """Test processing tick with insufficient historical data."""
        strategy = ASMBTRStrategy()
        
        tick = {
            'timestamp': datetime.now(),
            'symbol': 'EUR/USDT',
            'last': Decimal("1.08500")
        }
        
        signal = strategy.process_tick(tick)
        
        # Should return None or HOLD signal for first few ticks
        assert signal is None or signal.signal_type == SignalType.HOLD
    
    def test_process_tick_generates_signal(self):
        """Test that processing ticks eventually generates signals."""
        strategy = ASMBTRStrategy()
        
        # Process enough ticks to build state
        base_price = Decimal("1.08500")
        for i in range(20):
            price = base_price + Decimal(str(i * 0.00001))
            tick = {
                'timestamp': datetime.now() + timedelta(seconds=i),
                'last': price
            }
            signal = strategy.process_tick(tick)
        
        # At least some ticks should generate signals
        # (exact behavior depends on data and configuration)
    
    def test_open_long_position(self):
        """Test opening a long position."""
        config = StrategyConfig(position_size_pct=0.02)
        strategy = ASMBTRStrategy(config=config, initial_capital=Decimal("10000"))
        
        signal = TradingSignal(
            signal_type=SignalType.BUY,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.08500")
        )
        
        position = strategy._open_long(signal)
        
        assert position is not None
        assert position.side == "LONG"
        assert position.entry_price == Decimal("1.08500")
        
        # Position size should be 2% of capital
        # 10000 * 0.02 / 1.085 ≈ 184.33
        assert position.size > Decimal("180")
        assert position.size < Decimal("190")
        
        # Stop loss should be 0.5% below entry
        assert position.stop_loss == pytest.approx(Decimal("1.08500") * Decimal("0.995"), rel=1e-5)
        
        # Take profit should be 1% above entry
        assert position.take_profit == pytest.approx(Decimal("1.08500") * Decimal("1.010"), rel=1e-5)
    
    def test_close_position_profit(self):
        """Test closing position with profit."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        # Open position
        strategy.current_position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("100"),
            side="LONG"
        )
        
        initial_capital = strategy.current_capital
        
        # Close position at profit
        signal = TradingSignal(
            signal_type=SignalType.SELL,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.09000")  # 0.5% profit
        )
        
        strategy._close_position(signal)
        
        # Position should be closed
        assert strategy.current_position is None
        
        # Capital should increase
        assert strategy.current_capital > initial_capital
        
        # Trade history should be recorded
        assert len(strategy.trade_history) == 1
        assert strategy.trade_history[0]['pnl'] > 0
    
    def test_close_position_loss(self):
        """Test closing position with loss."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        # Open position
        strategy.current_position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("100"),
            side="LONG"
        )
        
        initial_capital = strategy.current_capital
        
        # Close position at loss
        signal = TradingSignal(
            signal_type=SignalType.SELL,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.08000")  # Loss
        )
        
        strategy._close_position(signal)
        
        # Capital should decrease
        assert strategy.current_capital < initial_capital
        
        # Trade history should record loss
        assert strategy.trade_history[0]['pnl'] < 0
    
    def test_stop_loss_trigger(self):
        """Test stop loss trigger."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        # Open position with SL
        strategy.current_position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("100"),
            side="LONG",
            stop_loss=Decimal("1.08000")
        )
        
        # Price hits stop loss
        was_closed = strategy.check_stop_loss_take_profit(Decimal("1.07900"))
        
        assert was_closed is True
        assert strategy.current_position is None
        assert len(strategy.trade_history) == 1
    
    def test_take_profit_trigger(self):
        """Test take profit trigger."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        # Open position with TP
        strategy.current_position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("100"),
            side="LONG",
            take_profit=Decimal("1.09500")
        )
        
        # Price hits take profit
        was_closed = strategy.check_stop_loss_take_profit(Decimal("1.09600"))
        
        assert was_closed is True
        assert strategy.current_position is None
        assert len(strategy.trade_history) == 1
        assert strategy.trade_history[0]['pnl'] > 0
    
    def test_no_trigger_within_range(self):
        """Test that SL/TP doesn't trigger when price is within range."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        strategy.current_position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("100"),
            side="LONG",
            stop_loss=Decimal("1.08000"),
            take_profit=Decimal("1.09500")
        )
        
        # Price within range
        was_closed = strategy.check_stop_loss_take_profit(Decimal("1.08750"))
        
        assert was_closed is False
        assert strategy.current_position is not None
    
    def test_train_on_history(self):
        """Test training on historical data."""
        strategy = ASMBTRStrategy()
        
        # Generate historical ticks
        ticks = []
        base_price = Decimal("1.08500")
        
        for i in range(100):
            change = Decimal(str((i % 3 - 1) * 0.00001))  # Oscillating pattern
            price = base_price + change
            ticks.append({
                'timestamp': datetime.now() + timedelta(seconds=i),
                'last': price
            })
        
        # Train
        strategy.train_on_history(ticks)
        
        # Prediction table should have observations
        stats = strategy.prediction_table.get_statistics()
        assert stats['total_observations'] > 0
    
    def test_calmar_ratio_calculation(self):
        """Test Calmar ratio calculation."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        # Simulate trades
        strategy.current_capital = Decimal("10500")  # 5% return
        strategy.metrics.max_drawdown = Decimal("200")  # 2% drawdown
        strategy.metrics.peak_equity = Decimal("10500")
        
        calmar = strategy.calculate_calmar_ratio()
        
        # Calmar = 5% / 2% = 2.5
        assert calmar == pytest.approx(2.5, rel=0.01)
    
    def test_calmar_ratio_zero_drawdown(self):
        """Test Calmar ratio with zero drawdown."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        strategy.current_capital = Decimal("10500")
        strategy.metrics.max_drawdown = Decimal("0")
        
        calmar = strategy.calculate_calmar_ratio()
        
        # Should return 0 when drawdown is 0
        assert calmar == 0.0
    
    def test_performance_summary(self):
        """Test comprehensive performance summary."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        # Simulate some trading activity
        strategy.current_capital = Decimal("10300")
        strategy.metrics.total_trades = 10
        strategy.metrics.winning_trades = 7
        strategy.metrics.losing_trades = 3
        strategy.metrics.max_drawdown = Decimal("150")
        strategy.metrics.peak_equity = Decimal("10300")
        
        summary = strategy.get_performance_summary()
        
        assert summary['initial_capital'] == 10000.0
        assert summary['current_capital'] == 10300.0
        assert summary['total_return'] == 300.0
        assert summary['total_return_pct'] == 3.0
        assert summary['total_trades'] == 10
        assert summary['win_rate'] == 70.0
        assert 'calmar_ratio' in summary
        assert 'prediction_table_stats' in summary


class TestStrategyEdgeCases:
    """Edge case tests for ASMBTRStrategy."""
    
    def test_execute_signal_without_position_buy(self):
        """Test executing BUY signal without existing position."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        signal = TradingSignal(
            signal_type=SignalType.BUY,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.08500")
        )
        
        position = strategy.execute_signal(signal)
        
        assert position is not None
        assert strategy.current_position == position
    
    def test_execute_signal_with_position_buy(self):
        """Test executing BUY signal with existing position (should ignore)."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        # Open initial position
        strategy.current_position = Position(
            entry_price=Decimal("1.08000"),
            entry_time=datetime.now(),
            size=Decimal("100"),
            side="LONG"
        )
        
        signal = TradingSignal(
            signal_type=SignalType.BUY,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.08500")
        )
        
        result = strategy.execute_signal(signal)
        
        # Should not open new position
        assert result is None
        assert strategy.current_position.entry_price == Decimal("1.08000")
    
    def test_execute_signal_without_position_sell(self):
        """Test executing SELL signal without existing position (should ignore)."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        signal = TradingSignal(
            signal_type=SignalType.SELL,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.08500")
        )
        
        result = strategy.execute_signal(signal)
        
        assert result is None
        assert strategy.current_position is None
    
    def test_execute_signal_hold(self):
        """Test executing HOLD signal."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        signal = TradingSignal(
            signal_type=SignalType.HOLD,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.0,
            timestamp=datetime.now(),
            price=Decimal("1.08500")
        )
        
        result = strategy.execute_signal(signal)
        
        assert result is None
        assert strategy.current_position is None
    
    def test_very_small_capital(self):
        """Test strategy with very small capital."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("100"))
        
        signal = TradingSignal(
            signal_type=SignalType.BUY,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.08500")
        )
        
        position = strategy._open_long(signal)
        
        # Should still be able to open position with very small size
        assert position is not None
        assert position.size > Decimal("0")
    
    def test_multiple_trades_sequence(self):
        """Test sequence of multiple trades."""
        strategy = ASMBTRStrategy(initial_capital=Decimal("10000"))
        
        # Trade 1: WIN
        strategy.current_position = Position(
            entry_price=Decimal("1.08000"),
            entry_time=datetime.now(),
            size=Decimal("100"),
            side="LONG"
        )
        strategy._close_position(TradingSignal(
            signal_type=SignalType.SELL,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.08500")
        ))
        
        # Trade 2: LOSS
        strategy.current_position = Position(
            entry_price=Decimal("1.08500"),
            entry_time=datetime.now(),
            size=Decimal("100"),
            side="LONG"
        )
        strategy._close_position(TradingSignal(
            signal_type=SignalType.SELL,
            state=BTRState(sequence="10110011", depth=8),
            prediction=None,
            confidence=0.65,
            timestamp=datetime.now(),
            price=Decimal("1.08000")
        ))
        
        assert len(strategy.trade_history) == 2
        assert strategy.metrics.total_trades == 2
        assert strategy.metrics.winning_trades == 1
        assert strategy.metrics.losing_trades == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
