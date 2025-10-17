"""
Tests for trading assets and market data functionality.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import (
    Base, TradingAsset, MarketData, Signal, Trade,
    BacktestResult, Position
)


@pytest.fixture(scope="module")
def test_db():
    """Create a test database."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_asset(test_db):
    """Create a sample trading asset."""
    asset = TradingAsset(
        symbol="BTCUSDT",
        exchange="binance",
        asset_type="spot",
        base_asset="BTC",
        quote_asset="USDT",
        is_active=True,
        min_quantity=Decimal("0.001"),
        min_notional=Decimal("10.0"),
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.00001")
    )
    test_db.add(asset)
    test_db.commit()
    return asset


class TestTradingAsset:
    """Test TradingAsset model and operations."""

    def test_create_asset(self, test_db):
        """Test creating a new trading asset."""
        asset = TradingAsset(
            symbol="ETHUSDT",
            exchange="binance",
            asset_type="spot",
            base_asset="ETH",
            quote_asset="USDT",
            is_active=True
        )
        test_db.add(asset)
        test_db.commit()

        assert asset.id is not None
        assert asset.symbol == "ETHUSDT"
        assert asset.is_active is True

    def test_asset_constraints(self, test_db):
        """Test asset validation constraints."""
        asset = TradingAsset(
            symbol="SOLUSDT",
            exchange="binance",
            asset_type="spot",
            base_asset="SOL",
            quote_asset="USDT",
            min_quantity=Decimal("0.1"),
            min_notional=Decimal("5.0")
        )
        test_db.add(asset)
        test_db.commit()

        assert asset.min_quantity > 0
        assert asset.min_notional > 0

    def test_query_active_assets(self, test_db, sample_asset):
        """Test querying active trading assets."""
        active = test_db.query(TradingAsset).filter_by(is_active=True).all()
        assert len(active) >= 1
        assert sample_asset in active

    def test_update_asset_status(self, test_db, sample_asset):
        """Test updating asset active status."""
        sample_asset.is_active = False
        test_db.commit()

        updated = test_db.query(TradingAsset).filter_by(symbol="BTCUSDT").first()
        assert updated.is_active is False


class TestMarketData:
    """Test MarketData model and operations."""

    def test_create_market_data(self, test_db, sample_asset):
        """Test creating market data entry."""
        data = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49500.00"),
            close=Decimal("50500.00"),
            volume=Decimal("1234.567"),
            quote_volume=Decimal("62000000.00"),
            num_trades=15000
        )
        test_db.add(data)
        test_db.commit()

        assert data.id is not None
        assert data.close > data.low
        assert data.high >= data.close

    def test_ohlc_validation(self, test_db, sample_asset):
        """Test OHLC price relationships."""
        data = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49000.00"),
            close=Decimal("50200.00"),
            volume=Decimal("100.0")
        )
        test_db.add(data)
        test_db.commit()

        # Validate OHLC relationships
        assert data.high >= data.open
        assert data.high >= data.close
        assert data.low <= data.open
        assert data.low <= data.close

    def test_query_market_data_range(self, test_db, sample_asset):
        """Test querying market data by time range."""
        now = datetime.utcnow()
        
        # Create multiple data points
        for i in range(5):
            data = MarketData(
                symbol="BTCUSDT",
                timestamp=now - timedelta(minutes=i),
                open=Decimal("50000.00"),
                high=Decimal("51000.00"),
                low=Decimal("49000.00"),
                close=Decimal("50500.00"),
                volume=Decimal("100.0")
            )
            test_db.add(data)
        test_db.commit()

        # Query last 3 minutes
        start_time = now - timedelta(minutes=3)
        recent = test_db.query(MarketData).filter(
            MarketData.symbol == "BTCUSDT",
            MarketData.timestamp >= start_time
        ).all()

        assert len(recent) >= 3


class TestSignal:
    """Test Signal model and operations."""

    def test_create_signal(self, test_db, sample_asset):
        """Test creating a trading signal."""
        signal = Signal(
            symbol="BTCUSDT",
            signal_type="long",
            strength=Decimal("0.85"),
            price=Decimal("50000.00"),
            timestamp=datetime.utcnow(),
            indicators={
                'rsi': 35,
                'macd': -0.5,
                'sma_20': 49500.00
            },
            strategy="momentum"
        )
        test_db.add(signal)
        test_db.commit()

        assert signal.id is not None
        assert signal.signal_type in ['long', 'short', 'neutral']
        assert 0 <= signal.strength <= 1

    def test_signal_strength_validation(self, test_db, sample_asset):
        """Test signal strength is between 0 and 1."""
        signal = Signal(
            symbol="BTCUSDT",
            signal_type="short",
            strength=Decimal("0.75"),
            price=Decimal("50000.00"),
            timestamp=datetime.utcnow()
        )
        test_db.add(signal)
        test_db.commit()

        assert signal.strength >= 0
        assert signal.strength <= 1

    def test_query_recent_signals(self, test_db, sample_asset):
        """Test querying recent signals."""
        now = datetime.utcnow()
        
        # Create signals
        for i in range(3):
            signal = Signal(
                symbol="BTCUSDT",
                signal_type="long",
                strength=Decimal("0.7"),
                price=Decimal("50000.00"),
                timestamp=now - timedelta(minutes=i)
            )
            test_db.add(signal)
        test_db.commit()

        recent = test_db.query(Signal).filter(
            Signal.symbol == "BTCUSDT",
            Signal.timestamp >= now - timedelta(hours=1)
        ).all()

        assert len(recent) >= 3


class TestTrade:
    """Test Trade model and operations."""

    def test_create_trade(self, test_db, sample_asset):
        """Test creating a trade."""
        trade = Trade(
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            entry_time=datetime.utcnow(),
            status="open"
        )
        test_db.add(trade)
        test_db.commit()

        assert trade.id is not None
        assert trade.side in ['buy', 'sell']
        assert trade.status == "open"

    def test_close_trade(self, test_db, sample_asset):
        """Test closing a trade and calculating PnL."""
        trade = Trade(
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            entry_time=datetime.utcnow(),
            status="open"
        )
        test_db.add(trade)
        test_db.commit()

        # Close trade
        trade.exit_price = Decimal("51000.00")
        trade.exit_time = datetime.utcnow()
        trade.status = "closed"
        
        # Calculate PnL
        trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
        test_db.commit()

        assert trade.status == "closed"
        assert trade.pnl > 0  # Profitable trade

    def test_trade_pnl_calculation(self, test_db, sample_asset):
        """Test trade PnL calculation."""
        # Long trade - profit
        long_trade = Trade(
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal("1.0"),
            entry_price=Decimal("50000.00"),
            exit_price=Decimal("51000.00"),
            status="closed"
        )
        long_pnl = (long_trade.exit_price - long_trade.entry_price) * long_trade.quantity
        assert long_pnl == Decimal("1000.00")

        # Short trade - profit
        short_trade = Trade(
            symbol="BTCUSDT",
            side="sell",
            quantity=Decimal("1.0"),
            entry_price=Decimal("50000.00"),
            exit_price=Decimal("49000.00"),
            status="closed"
        )
        short_pnl = (short_trade.entry_price - short_trade.exit_price) * short_trade.quantity
        assert short_pnl == Decimal("1000.00")


class TestBacktestResult:
    """Test BacktestResult model and operations."""

    def test_create_backtest(self, test_db, sample_asset):
        """Test creating backtest result."""
        backtest = BacktestResult(
            symbol="BTCUSDT",
            strategy="momentum",
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
            initial_capital=Decimal("10000.00"),
            final_capital=Decimal("11500.00"),
            total_trades=50,
            winning_trades=32,
            losing_trades=18,
            win_rate=Decimal("0.64"),
            profit_factor=Decimal("1.8"),
            sharpe_ratio=Decimal("2.1"),
            max_drawdown=Decimal("0.15")
        )
        test_db.add(backtest)
        test_db.commit()

        assert backtest.id is not None
        assert backtest.final_capital > backtest.initial_capital
        assert backtest.win_rate == Decimal("0.64")

    def test_backtest_metrics(self, test_db, sample_asset):
        """Test backtest performance metrics."""
        backtest = BacktestResult(
            symbol="BTCUSDT",
            strategy="mean_reversion",
            start_date=datetime.utcnow() - timedelta(days=60),
            end_date=datetime.utcnow(),
            initial_capital=Decimal("10000.00"),
            final_capital=Decimal("12000.00"),
            total_trades=100,
            winning_trades=55,
            losing_trades=45,
            sharpe_ratio=Decimal("1.5")
        )
        test_db.add(backtest)
        test_db.commit()

        # Calculate returns
        returns = (backtest.final_capital - backtest.initial_capital) / backtest.initial_capital
        assert returns == Decimal("0.2")  # 20% return


class TestPosition:
    """Test Position model and operations."""

    def test_create_position(self, test_db, sample_asset):
        """Test creating a position."""
        position = Position(
            symbol="BTCUSDT",
            side="long",
            quantity=Decimal("0.5"),
            entry_price=Decimal("50000.00"),
            current_price=Decimal("50500.00"),
            unrealized_pnl=Decimal("250.00"),
            status="open"
        )
        test_db.add(position)
        test_db.commit()

        assert position.id is not None
        assert position.status == "open"
        assert position.unrealized_pnl > 0

    def test_update_position_price(self, test_db, sample_asset):
        """Test updating position with new price."""
        position = Position(
            symbol="BTCUSDT",
            side="long",
            quantity=Decimal("1.0"),
            entry_price=Decimal("50000.00"),
            current_price=Decimal("50000.00"),
            unrealized_pnl=Decimal("0.00"),
            status="open"
        )
        test_db.add(position)
        test_db.commit()

        # Update price
        position.current_price = Decimal("51000.00")
        position.unrealized_pnl = (position.current_price - position.entry_price) * position.quantity
        test_db.commit()

        assert position.current_price == Decimal("51000.00")
        assert position.unrealized_pnl == Decimal("1000.00")


# Integration tests
class TestTradingWorkflow:
    """Test complete trading workflow."""

    def test_signal_to_trade_workflow(self, test_db, sample_asset):
        """Test workflow from signal generation to trade execution."""
        # 1. Generate signal
        signal = Signal(
            symbol="BTCUSDT",
            signal_type="long",
            strength=Decimal("0.85"),
            price=Decimal("50000.00"),
            timestamp=datetime.utcnow(),
            strategy="momentum"
        )
        test_db.add(signal)
        test_db.commit()

        # 2. Execute trade based on signal
        trade = Trade(
            symbol=signal.symbol,
            side="buy",
            quantity=Decimal("0.1"),
            entry_price=signal.price,
            entry_time=datetime.utcnow(),
            status="open",
            signal_id=signal.id
        )
        test_db.add(trade)
        test_db.commit()

        # 3. Create position
        position = Position(
            symbol=trade.symbol,
            side="long",
            quantity=trade.quantity,
            entry_price=trade.entry_price,
            current_price=trade.entry_price,
            unrealized_pnl=Decimal("0.00"),
            status="open",
            trade_id=trade.id
        )
        test_db.add(position)
        test_db.commit()

        # Verify workflow
        assert signal.id is not None
        assert trade.signal_id == signal.id
        assert position.trade_id == trade.id

    def test_backtest_to_live_workflow(self, test_db, sample_asset):
        """Test workflow from backtest to live trading."""
        # 1. Run backtest
        backtest = BacktestResult(
            symbol="BTCUSDT",
            strategy="momentum",
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
            initial_capital=Decimal("10000.00"),
            final_capital=Decimal("12000.00"),
            total_trades=50,
            winning_trades=35,
            win_rate=Decimal("0.70"),
            sharpe_ratio=Decimal("2.0")
        )
        test_db.add(backtest)
        test_db.commit()

        # 2. If backtest successful, deploy to live
        if backtest.sharpe_ratio >= 1.5 and backtest.win_rate >= 0.6:
            # Deploy strategy
            asset = test_db.query(TradingAsset).filter_by(symbol="BTCUSDT").first()
            asset.is_active = True
            test_db.commit()

            assert asset.is_active is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
