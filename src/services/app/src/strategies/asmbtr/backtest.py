"""ASMBTR Backtesting Framework.

This module provides comprehensive backtesting capabilities for the ASMBTR
strategy, including tick replay, equity curve generation, performance metrics,
and trade analysis.

Phase: AI Enhancement Plan - Phase 3.6
Target: Validate Calmar ratio >0.3 on EUR/USD 2024 data
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime
import logging
import json
from pathlib import Path
import pandas as pd
import numpy as np

from .strategy import ASMBTRStrategy, TradingSignal, Position, SignalType

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Completed trade record.
    
    Attributes:
        entry_time: When position was opened
        exit_time: When position was closed
        entry_price: Entry price
        exit_price: Exit price
        size: Position size
        side: "LONG" or "SHORT"
        pnl: Profit/loss in quote currency
        pnl_percent: Profit/loss as percentage
        exit_reason: Why position closed ("TP", "SL", "SIGNAL", "EOD")
        duration_seconds: How long position was held
    """
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    side: str
    pnl: Decimal
    pnl_percent: float
    exit_reason: str
    duration_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'entry_price': float(self.entry_price),
            'exit_price': float(self.exit_price),
            'size': float(self.size),
            'side': self.side,
            'pnl': float(self.pnl),
            'pnl_percent': self.pnl_percent,
            'exit_reason': self.exit_reason,
            'duration_seconds': self.duration_seconds
        }


@dataclass
class BacktestMetrics:
    """Comprehensive backtest performance metrics.
    
    Attributes:
        total_trades: Number of completed trades
        winning_trades: Number of profitable trades
        losing_trades: Number of losing trades
        win_rate: Percentage of winning trades
        total_pnl: Total profit/loss
        total_return_pct: Total return as percentage
        avg_win: Average profit per winning trade
        avg_loss: Average loss per losing trade
        profit_factor: Gross profit / gross loss
        sharpe_ratio: Risk-adjusted return (annualized)
        max_drawdown: Maximum drawdown from peak
        max_drawdown_pct: Maximum drawdown as percentage
        calmar_ratio: Total return / max drawdown
        avg_trade_duration_seconds: Average trade duration
        trades_per_day: Average number of trades per day
    """
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: Decimal = Decimal('0')
    total_return_pct: float = 0.0
    avg_win: Decimal = Decimal('0')
    avg_loss: Decimal = Decimal('0')
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: Decimal = Decimal('0')
    max_drawdown_pct: float = 0.0
    calmar_ratio: float = 0.0
    avg_trade_duration_seconds: float = 0.0
    trades_per_day: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 4),
            'total_pnl': float(self.total_pnl),
            'total_return_pct': round(self.total_return_pct, 4),
            'avg_win': float(self.avg_win),
            'avg_loss': float(self.avg_loss),
            'profit_factor': round(self.profit_factor, 4),
            'sharpe_ratio': round(self.sharpe_ratio, 4),
            'max_drawdown': float(self.max_drawdown),
            'max_drawdown_pct': round(self.max_drawdown_pct, 4),
            'calmar_ratio': round(self.calmar_ratio, 4),
            'avg_trade_duration_seconds': round(self.avg_trade_duration_seconds, 2),
            'trades_per_day': round(self.trades_per_day, 2)
        }


@dataclass
class EquityPoint:
    """Single point on equity curve.
    
    Attributes:
        timestamp: Time of equity snapshot
        balance: Account balance
        equity: Current equity (balance + unrealized PnL)
        drawdown: Current drawdown from peak
        drawdown_pct: Drawdown as percentage of peak
    """
    timestamp: datetime
    balance: Decimal
    equity: Decimal
    drawdown: Decimal
    drawdown_pct: float


class HistoricalBacktest:
    """Historical backtesting engine for ASMBTR strategy.
    
    Simulates trading on historical tick data with realistic execution,
    tracks equity curve, and generates comprehensive performance metrics.
    
    Example:
        >>> strategy = ASMBTRStrategy(symbol="EUR/USD", depth=8)
        >>> backtest = HistoricalBacktest(
        ...     strategy=strategy,
        ...     initial_balance=10000,
        ...     commission=0.0002
        ... )
        >>> 
        >>> # Load historical data
        >>> ticks = load_eur_usd_2024_data()
        >>> 
        >>> # Run backtest
        >>> backtest.run(ticks)
        >>> 
        >>> # Get results
        >>> metrics = backtest.get_metrics()
        >>> print(f"Calmar Ratio: {metrics.calmar_ratio:.3f}")
        >>> print(f"Win Rate: {metrics.win_rate:.2%}")
    """
    
    def __init__(
        self,
        strategy: ASMBTRStrategy,
        initial_balance: Decimal = Decimal('10000'),
        commission: Decimal = Decimal('0.0002'),  # 0.02% per trade
        slippage: Decimal = Decimal('0.0001'),    # 0.01% slippage
    ):
        """Initialize backtest engine.
        
        Args:
            strategy: ASMBTR strategy instance
            initial_balance: Starting capital
            commission: Commission per trade (as decimal, e.g., 0.0002 = 0.02%)
            slippage: Slippage per trade (as decimal)
        """
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.commission = commission
        self.slippage = slippage
        
        # State tracking
        self.balance = initial_balance
        self.current_position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[EquityPoint] = []
        self.signals: List[TradingSignal] = []
        
        # Performance tracking
        self.peak_equity = initial_balance
        self.current_drawdown = Decimal('0')
        self.max_drawdown = Decimal('0')
        
        logger.info(
            f"Initialized backtest: balance={initial_balance}, "
            f"commission={commission}, slippage={slippage}"
        )
    
    def run(self, ticks: List[Dict[str, Any]]) -> None:
        """Run backtest on historical tick data.
        
        Args:
            ticks: List of tick dictionaries with keys:
                   - 'timestamp': datetime
                   - 'last': Decimal (price)
                   - 'symbol': str (optional)
        
        Raises:
            ValueError: If ticks list is empty or malformed
        """
        if not ticks:
            raise ValueError("Ticks list cannot be empty")
        
        logger.info(f"Starting backtest with {len(ticks)} ticks")
        
        for i, tick in enumerate(ticks):
            # Validate tick format
            if 'last' not in tick or 'timestamp' not in tick:
                raise ValueError(f"Tick {i} missing required fields (last, timestamp)")
            
            # Process tick through strategy
            signal = self.strategy.process_tick(tick)
            
            if signal:
                self.signals.append(signal)
            
            # Check for position exits (SL/TP)
            if self.current_position:
                self._check_exit_conditions(tick)
            
            # Execute signal if generated
            if signal and signal.signal_type != SignalType.HOLD:
                self._execute_signal(signal, tick)
            
            # Update equity curve (sample every 100 ticks to reduce memory)
            if i % 100 == 0 or i == len(ticks) - 1:
                self._update_equity(tick)
        
        # Close any open position at end
        if self.current_position and ticks:
            last_tick = ticks[-1]
            self._close_position(
                price=last_tick['last'],
                timestamp=last_tick['timestamp'],
                reason="EOD"
            )
        
        logger.info(
            f"Backtest complete: {len(self.trades)} trades, "
            f"final balance={self.balance:.2f}"
        )
    
    def _execute_signal(self, signal: TradingSignal, tick: Dict[str, Any]) -> None:
        """Execute trading signal.
        
        Args:
            signal: Signal to execute
            tick: Current tick data
        """
        # Close existing position if opposite signal
        if self.current_position:
            if (signal.signal_type == SignalType.BUY and self.current_position.side == "SHORT") or \
               (signal.signal_type == SignalType.SELL and self.current_position.side == "LONG"):
                self._close_position(
                    price=signal.price,
                    timestamp=signal.timestamp,
                    reason="SIGNAL"
                )
        
        # Open new position if no position or just closed
        if not self.current_position:
            if signal.signal_type == SignalType.BUY:
                self._open_position(signal, tick, side="LONG")
            elif signal.signal_type == SignalType.SELL:
                self._open_position(signal, tick, side="SHORT")
    
    def _open_position(
        self,
        signal: TradingSignal,
        tick: Dict[str, Any],
        side: str
    ) -> None:
        """Open new position.
        
        Args:
            signal: Trading signal
            tick: Current tick data
            side: "LONG" or "SHORT"
        """
        # Apply slippage
        entry_price = signal.price * (1 + self.slippage if side == "LONG" else 1 - self.slippage)
        
        # Calculate position size (use strategy's configured size percentage)
        position_size = self.strategy.config.position_size_pct * self.balance
        
        # Apply commission
        commission_cost = position_size * self.commission
        
        # Calculate SL/TP based on strategy config
        if side == "LONG":
            stop_loss = entry_price * (Decimal('1') - self.strategy.config.stop_loss_pct)
            take_profit = entry_price * (Decimal('1') + self.strategy.config.take_profit_pct)
        else:
            stop_loss = entry_price * (Decimal('1') + self.strategy.config.stop_loss_pct)
            take_profit = entry_price * (Decimal('1') - self.strategy.config.take_profit_pct)
        
        self.current_position = Position(
            entry_price=entry_price,
            entry_time=signal.timestamp,
            size=position_size,
            side=side,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        # Deduct commission
        self.balance -= commission_cost
        
        logger.debug(
            f"Opened {side} position: price={entry_price:.5f}, "
            f"size={position_size:.2f}, SL={stop_loss:.5f}, TP={take_profit:.5f}"
        )
    
    def _check_exit_conditions(self, tick: Dict[str, Any]) -> None:
        """Check if current position should be closed due to SL/TP.
        
        Args:
            tick: Current tick data
        """
        if not self.current_position:
            return
        
        current_price = tick['last']
        timestamp = tick['timestamp']
        
        # Check stop loss
        if self.current_position.stop_loss:
            if self.current_position.side == "LONG" and current_price <= self.current_position.stop_loss:
                self._close_position(current_price, timestamp, "SL")
                return
            elif self.current_position.side == "SHORT" and current_price >= self.current_position.stop_loss:
                self._close_position(current_price, timestamp, "SL")
                return
        
        # Check take profit
        if self.current_position.take_profit:
            if self.current_position.side == "LONG" and current_price >= self.current_position.take_profit:
                self._close_position(current_price, timestamp, "TP")
                return
            elif self.current_position.side == "SHORT" and current_price <= self.current_position.take_profit:
                self._close_position(current_price, timestamp, "TP")
                return
    
    def _close_position(
        self,
        price: Decimal,
        timestamp: datetime,
        reason: str
    ) -> None:
        """Close current position.
        
        Args:
            price: Exit price
            timestamp: Exit time
            reason: Exit reason ("TP", "SL", "SIGNAL", "EOD")
        """
        if not self.current_position:
            return
        
        # Apply slippage
        exit_price = price * (
            1 - self.slippage if self.current_position.side == "LONG" else 1 + self.slippage
        )
        
        # Calculate PnL
        pnl = self.current_position.get_pnl(exit_price)
        pnl_percent = float(self.current_position.get_pnl_percent(exit_price))
        
        # Apply commission
        commission_cost = self.current_position.size * self.commission
        pnl -= commission_cost
        
        # Update balance
        self.balance += pnl
        
        # Calculate duration
        duration = (timestamp - self.current_position.entry_time).total_seconds()
        
        # Record trade
        trade = Trade(
            entry_time=self.current_position.entry_time,
            exit_time=timestamp,
            entry_price=self.current_position.entry_price,
            exit_price=exit_price,
            size=self.current_position.size,
            side=self.current_position.side,
            pnl=pnl,
            pnl_percent=pnl_percent,
            exit_reason=reason,
            duration_seconds=duration
        )
        
        self.trades.append(trade)
        self.current_position = None
        
        logger.debug(
            f"Closed position: pnl={pnl:.2f}, reason={reason}, "
            f"balance={self.balance:.2f}"
        )
    
    def _update_equity(self, tick: Dict[str, Any]) -> None:
        """Update equity curve.
        
        Args:
            tick: Current tick data
        """
        current_price = tick['last']
        timestamp = tick['timestamp']
        
        # Calculate equity (balance + unrealized PnL)
        unrealized_pnl = Decimal('0')
        if self.current_position:
            unrealized_pnl = self.current_position.get_pnl(current_price)
        
        equity = self.balance + unrealized_pnl
        
        # Update peak and drawdown
        if equity > self.peak_equity:
            self.peak_equity = equity
            self.current_drawdown = Decimal('0')
        else:
            self.current_drawdown = self.peak_equity - equity
            if self.current_drawdown > self.max_drawdown:
                self.max_drawdown = self.current_drawdown
        
        drawdown_pct = float(self.current_drawdown / self.peak_equity) if self.peak_equity > 0 else 0.0
        
        # Record equity point
        equity_point = EquityPoint(
            timestamp=timestamp,
            balance=self.balance,
            equity=equity,
            drawdown=self.current_drawdown,
            drawdown_pct=drawdown_pct
        )
        
        self.equity_curve.append(equity_point)
    
    def get_metrics(self) -> BacktestMetrics:
        """Calculate comprehensive performance metrics.
        
        Returns:
            BacktestMetrics object with all performance statistics
        """
        metrics = BacktestMetrics()
        
        if not self.trades:
            logger.warning("No trades executed, returning empty metrics")
            return metrics
        
        # Basic trade statistics
        metrics.total_trades = len(self.trades)
        metrics.winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        metrics.losing_trades = sum(1 for t in self.trades if t.pnl < 0)
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0.0
        
        # PnL statistics
        metrics.total_pnl = sum(t.pnl for t in self.trades)
        metrics.total_return_pct = float((self.balance - self.initial_balance) / self.initial_balance)
        
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]
        
        metrics.avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else Decimal('0')
        metrics.avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else Decimal('0')
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else Decimal('0')
        gross_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else Decimal('0')
        metrics.profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else 0.0
        
        # Sharpe ratio (simplified - using trade returns)
        if len(self.trades) > 1:
            returns = [float(t.pnl_percent) for t in self.trades]
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            metrics.sharpe_ratio = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0
        
        # Drawdown metrics
        metrics.max_drawdown = self.max_drawdown
        metrics.max_drawdown_pct = float(self.max_drawdown / self.peak_equity) if self.peak_equity > 0 else 0.0
        
        # Calmar ratio
        if metrics.max_drawdown_pct > 0:
            metrics.calmar_ratio = metrics.total_return_pct / metrics.max_drawdown_pct
        else:
            metrics.calmar_ratio = 0.0
        
        # Trade duration
        metrics.avg_trade_duration_seconds = np.mean([t.duration_seconds for t in self.trades])
        
        # Trades per day
        if self.trades and len(self.trades) >= 2:
            time_span = (self.trades[-1].exit_time - self.trades[0].entry_time).total_seconds() / 86400
            metrics.trades_per_day = metrics.total_trades / time_span if time_span > 0 else 0.0
        
        return metrics
    
    def export_trades(self, filepath: Path) -> None:
        """Export trade log to JSON file.
        
        Args:
            filepath: Path to output JSON file
        """
        trades_data = [t.to_dict() for t in self.trades]
        
        with open(filepath, 'w') as f:
            json.dump(trades_data, f, indent=2)
        
        logger.info(f"Exported {len(trades_data)} trades to {filepath}")
    
    def export_equity_curve(self, filepath: Path) -> None:
        """Export equity curve to CSV file.
        
        Args:
            filepath: Path to output CSV file
        """
        if not self.equity_curve:
            logger.warning("No equity curve data to export")
            return
        
        data = []
        for point in self.equity_curve:
            data.append({
                'timestamp': point.timestamp.isoformat(),
                'balance': float(point.balance),
                'equity': float(point.equity),
                'drawdown': float(point.drawdown),
                'drawdown_pct': point.drawdown_pct
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        
        logger.info(f"Exported equity curve ({len(data)} points) to {filepath}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive backtest summary.
        
        Returns:
            Dictionary with metrics, trade count, and configuration
        """
        metrics = self.get_metrics()
        
        return {
            'config': {
                'initial_balance': float(self.initial_balance),
                'final_balance': float(self.balance),
                'commission': float(self.commission),
                'slippage': float(self.slippage),
                'strategy': {
                    'depth': self.strategy.config.depth,
                    'confidence_threshold': self.strategy.config.confidence_threshold,
                    'position_size_pct': self.strategy.config.position_size_pct,
                    'stop_loss_pct': self.strategy.config.stop_loss_pct,
                    'take_profit_pct': self.strategy.config.take_profit_pct,
                    'decay_rate': self.strategy.config.decay_rate
                }
            },
            'metrics': metrics.to_dict(),
            'trade_count': len(self.trades),
            'signal_count': len(self.signals)
        }


if __name__ == "__main__":
    """Example usage and testing."""
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print(" ASMBTR Backtest Example ".center(60, "="))
    print("="*60 + "\n")
    
    # Example: Create synthetic tick data
    from datetime import timedelta
    
    base_price = Decimal("1.08500")
    base_time = datetime.now()
    
    ticks = []
    for i in range(1000):
        # Random walk price
        change = Decimal(str(np.random.randn() * 0.0001))
        base_price += change
        
        ticks.append({
            'timestamp': base_time + timedelta(seconds=i),
            'last': base_price,
            'symbol': 'EUR/USD'
        })
    
    # Create strategy
    strategy = ASMBTRStrategy(symbol="EUR/USD", depth=8)
    
    # Run backtest
    backtest = HistoricalBacktest(
        strategy=strategy,
        initial_balance=Decimal('10000'),
        commission=Decimal('0.0002')
    )
    
    backtest.run(ticks)
    
    # Print results
    summary = backtest.get_summary()
    print(f"\nBacktest Results:")
    print(f"Total Trades: {summary['trade_count']}")
    print(f"Win Rate: {summary['metrics']['win_rate']:.2%}")
    print(f"Total Return: {summary['metrics']['total_return_pct']:.2%}")
    print(f"Calmar Ratio: {summary['metrics']['calmar_ratio']:.3f}")
    print(f"Sharpe Ratio: {summary['metrics']['sharpe_ratio']:.3f}")
    print(f"Max Drawdown: {summary['metrics']['max_drawdown_pct']:.2%}")
