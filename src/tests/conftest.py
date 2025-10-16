"""
Pytest configuration and shared fixtures
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture(scope='session')
def test_db_engine():
    """Create test database engine"""
    engine = create_engine('sqlite:///:memory:')
    return engine


@pytest.fixture(scope='function')
def db_session(test_db_engine):
    """Create database session for each test"""
    from database import Base
    
    # Create tables
    Base.metadata.create_all(test_db_engine)
    
    # Create session
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    
    yield session
    
    # Cleanup
    session.close()
    Base.metadata.drop_all(test_db_engine)


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    
    opens = 100 + np.cumsum(np.random.randn(100) * 2)
    closes = opens + np.random.randn(100) * 2
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(100))
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(100))
    volumes = np.random.randint(1000, 10000, 100)
    
    df = pd.DataFrame({
        'time': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })
    
    return df


@pytest.fixture
def sample_trades():
    """Generate sample trade data"""
    trades = [
        {
            'symbol': 'BTC/USD',
            'side': 'buy',
            'quantity': Decimal('0.5'),
            'entry_price': Decimal('50000.0'),
            'exit_price': Decimal('51000.0'),
            'pnl': Decimal('500.0'),
            'entry_time': datetime(2023, 1, 1, 10, 0, 0),
            'exit_time': datetime(2023, 1, 2, 14, 0, 0),
            'status': 'closed'
        },
        {
            'symbol': 'ETH/USD',
            'side': 'buy',
            'quantity': Decimal('2.0'),
            'entry_price': Decimal('3000.0'),
            'exit_price': Decimal('3100.0'),
            'pnl': Decimal('200.0'),
            'entry_time': datetime(2023, 1, 3, 9, 0, 0),
            'exit_time': datetime(2023, 1, 4, 16, 0, 0),
            'status': 'closed'
        },
        {
            'symbol': 'BTC/USD',
            'side': 'sell',
            'quantity': Decimal('0.3'),
            'entry_price': Decimal('52000.0'),
            'exit_price': Decimal('51500.0'),
            'pnl': Decimal('150.0'),
            'entry_time': datetime(2023, 1, 5, 11, 0, 0),
            'exit_time': datetime(2023, 1, 6, 13, 0, 0),
            'status': 'closed'
        }
    ]
    
    return trades


@pytest.fixture
def sample_account(db_session):
    """Create sample account in database"""
    from database import Account
    
    account = Account(
        exchange='binance',
        account_type='spot',
        api_key='test_api_key',
        api_secret='test_api_secret',
        status='active'
    )
    
    db_session.add(account)
    db_session.commit()
    
    return account


@pytest.fixture
def sample_positions(db_session, sample_account):
    """Create sample positions in database"""
    from database import Position
    
    positions = [
        Position(
            account_id=sample_account.id,
            symbol='BTC/USD',
            side='long',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.0'),
            current_price=Decimal('51000.0'),
            unrealized_pnl=Decimal('500.0'),
            stop_loss=Decimal('48000.0'),
            take_profit=Decimal('55000.0'),
            status='open'
        ),
        Position(
            account_id=sample_account.id,
            symbol='ETH/USD',
            side='long',
            quantity=Decimal('2.0'),
            entry_price=Decimal('3000.0'),
            current_price=Decimal('3100.0'),
            unrealized_pnl=Decimal('200.0'),
            stop_loss=Decimal('2900.0'),
            take_profit=Decimal('3300.0'),
            status='open'
        )
    ]
    
    for position in positions:
        db_session.add(position)
    
    db_session.commit()
    
    return positions


@pytest.fixture
def sample_strategy():
    """Generate sample strategy parameters"""
    return {
        'name': 'momentum_strategy',
        'parameters': {
            'M': 20,
            'threshold': 0.02,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.10
        },
        'status': 'active'
    }


@pytest.fixture
def mock_exchange():
    """Create mock exchange for testing"""
    from unittest.mock import Mock
    
    exchange = Mock()
    
    # Mock fetch_ohlcv
    exchange.fetch_ohlcv = Mock(return_value=[
        [1609459200000, 100.0, 105.0, 95.0, 102.0, 1000.0],
        [1609545600000, 102.0, 108.0, 100.0, 106.0, 1200.0],
        [1609632000000, 106.0, 110.0, 104.0, 108.0, 1100.0],
    ])
    
    # Mock fetch_balance
    exchange.fetch_balance = Mock(return_value={
        'total': {'USD': 10000.0, 'BTC': 0.5, 'ETH': 2.0},
        'free': {'USD': 9000.0, 'BTC': 0.4, 'ETH': 1.5},
        'used': {'USD': 1000.0, 'BTC': 0.1, 'ETH': 0.5}
    })
    
    # Mock create_order
    exchange.create_order = Mock(return_value={
        'id': '12345',
        'symbol': 'BTC/USD',
        'type': 'limit',
        'side': 'buy',
        'price': 50000.0,
        'amount': 0.1,
        'status': 'open'
    })
    
    return exchange


@pytest.fixture
def sample_market_data():
    """Generate sample market data with multiple symbols"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    
    data = {}
    symbols = ['BTC/USD', 'ETH/USD', 'XRP/USD']
    
    for i, symbol in enumerate(symbols):
        base_price = [50000, 3000, 0.5][i]
        
        closes = base_price + np.cumsum(np.random.randn(100) * base_price * 0.02)
        opens = closes + np.random.randn(100) * base_price * 0.01
        highs = np.maximum(opens, closes) + np.abs(np.random.randn(100)) * base_price * 0.01
        lows = np.minimum(opens, closes) - np.abs(np.random.randn(100)) * base_price * 0.01
        volumes = np.random.randint(1000, 10000, 100)
        
        df = pd.DataFrame({
            'time': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        
        data[symbol] = df
    
    return data


@pytest.fixture
def sample_backtest_results():
    """Generate sample backtest results"""
    return {
        'total_return': 0.25,
        'sharpe_ratio': 1.5,
        'max_drawdown': -0.15,
        'win_rate': 0.65,
        'total_trades': 50,
        'winning_trades': 33,
        'losing_trades': 17,
        'avg_win': 0.05,
        'avg_loss': -0.03,
        'profit_factor': 2.2,
        'expectancy': 0.02
    }


@pytest.fixture(autouse=True)
def reset_random_seed():
    """Reset random seed before each test"""
    np.random.seed(42)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
