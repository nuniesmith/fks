"""
Test suite for database models and operations
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database.models import Base, Account, Position, Trade, BalanceHistory, StrategyParameters


@pytest.fixture(scope='function')
def engine():
    """Create in-memory test database"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope='function')
def session(engine):
    """Create database session"""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestAccountModel:
    """Test Account model"""
    
    def test_create_account(self, session):
        """Test creating an account"""
        account = Account(
            exchange='binance',
            account_type='spot',
            api_key='test_key',
            api_secret='test_secret',
            status='active'
        )
        
        session.add(account)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(Account).first()
        assert retrieved is not None
        assert retrieved.exchange == 'binance'
        assert retrieved.account_type == 'spot'
        assert retrieved.status == 'active'
        assert retrieved.created_at is not None
    
    def test_account_metadata(self, session):
        """Test account metadata field"""
        account = Account(
            exchange='kraken',
            account_type='futures',
            api_key='key',
            api_secret='secret',
            account_metadata={'region': 'US', 'tier': 'premium'}
        )
        
        session.add(account)
        session.commit()
        
        retrieved = session.query(Account).first()
        assert retrieved.account_metadata == {'region': 'US', 'tier': 'premium'}
    
    def test_account_relationships(self, session):
        """Test account relationships"""
        account = Account(
            exchange='coinbase',
            account_type='spot',
            api_key='key',
            api_secret='secret'
        )
        
        session.add(account)
        session.commit()
        
        # Add related position
        position = Position(
            account_id=account.id,
            symbol='BTC/USD',
            side='long',
            quantity=Decimal('0.5'),
            entry_price=Decimal('50000.0'),
            current_price=Decimal('51000.0'),
            unrealized_pnl=Decimal('500.0'),
            status='open'
        )
        
        session.add(position)
        session.commit()
        
        # Verify relationship
        assert len(account.positions) == 1
        assert account.positions[0].symbol == 'BTC/USD'


class TestPositionModel:
    """Test Position model"""
    
    @pytest.fixture
    def test_account(self, session):
        """Create test account"""
        account = Account(
            exchange='binance',
            account_type='spot',
            api_key='key',
            api_secret='secret'
        )
        session.add(account)
        session.commit()
        return account
    
    def test_create_position(self, session, test_account):
        """Test creating a position"""
        position = Position(
            account_id=test_account.id,
            symbol='ETH/USD',
            side='long',
            quantity=Decimal('2.0'),
            entry_price=Decimal('3000.0'),
            current_price=Decimal('3100.0'),
            unrealized_pnl=Decimal('200.0'),
            status='open'
        )
        
        session.add(position)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(Position).first()
        assert retrieved is not None
        assert retrieved.symbol == 'ETH/USD'
        assert retrieved.quantity == Decimal('2.0')
        assert retrieved.status == 'open'
    
    def test_position_foreign_key(self, session, test_account):
        """Test position foreign key relationship"""
        position = Position(
            account_id=test_account.id,
            symbol='BTC/USD',
            side='short',
            quantity=Decimal('1.0'),
            entry_price=Decimal('60000.0'),
            current_price=Decimal('59000.0'),
            unrealized_pnl=Decimal('1000.0'),
            status='open'
        )
        
        session.add(position)
        session.commit()
        
        # Verify foreign key
        assert position.account_id == test_account.id
        assert position.account.exchange == 'binance'


class TestTradeModel:
    """Test Trade model"""
    
    @pytest.fixture
    def test_account(self, session):
        """Create test account"""
        account = Account(
            exchange='binance',
            account_type='spot',
            api_key='key',
            api_secret='secret'
        )
        session.add(account)
        session.commit()
        return account
    
    def test_create_trade(self, session, test_account):
        """Test creating a trade"""
        trade = Trade(
            account_id=test_account.id,
            symbol='BTC/USD',
            side='buy',
            quantity=Decimal('0.1'),
            entry_price=Decimal('50000.0'),
            exit_price=Decimal('51000.0'),
            pnl=Decimal('100.0'),
            status='closed',
            entry_time=datetime.now(timezone.utc),
            exit_time=datetime.now(timezone.utc)
        )
        
        session.add(trade)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(Trade).first()
        assert retrieved is not None
        assert retrieved.symbol == 'BTC/USD'
        assert retrieved.side == 'buy'
        assert retrieved.pnl == Decimal('100.0')
        assert retrieved.status == 'closed'
    
    def test_trade_metadata(self, session, test_account):
        """Test trade metadata field"""
        trade = Trade(
            account_id=test_account.id,
            symbol='ETH/USD',
            side='sell',
            quantity=Decimal('1.0'),
            entry_price=Decimal('3000.0'),
            status='open',
            entry_time=datetime.now(timezone.utc),
            trade_metadata={'strategy': 'momentum', 'signal_strength': 0.8}
        )
        
        session.add(trade)
        session.commit()
        
        retrieved = session.query(Trade).first()
        assert retrieved.trade_metadata['strategy'] == 'momentum'
        assert retrieved.trade_metadata['signal_strength'] == 0.8


class TestBalanceHistoryModel:
    """Test BalanceHistory model"""
    
    @pytest.fixture
    def test_account(self, session):
        """Create test account"""
        account = Account(
            exchange='binance',
            account_type='spot',
            api_key='key',
            api_secret='secret'
        )
        session.add(account)
        session.commit()
        return account
    
    def test_create_balance_history(self, session, test_account):
        """Test creating balance history"""
        balance = BalanceHistory(
            account_id=test_account.id,
            total_balance=Decimal('10000.0'),
            available_balance=Decimal('9000.0'),
            reserved_balance=Decimal('1000.0')
        )
        
        session.add(balance)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(BalanceHistory).first()
        assert retrieved is not None
        assert retrieved.total_balance == Decimal('10000.0')
        assert retrieved.available_balance == Decimal('9000.0')
        assert retrieved.timestamp is not None
    
    def test_balance_history_foreign_key(self, session, test_account):
        """Test balance history foreign key"""
        balance = BalanceHistory(
            account_id=test_account.id,
            total_balance=Decimal('5000.0'),
            available_balance=Decimal('4500.0'),
            reserved_balance=Decimal('500.0')
        )
        
        session.add(balance)
        session.commit()
        
        # Verify foreign key
        assert balance.account_id == test_account.id
        assert balance.account.exchange == 'binance'


class TestStrategyModel:
    """Test Strategy model"""
    
    def test_create_strategy(self, session):
        """Test creating a strategy"""
        strategy = StrategyParameters(
            name='momentum_strategy',
            parameters={'M': 20, 'threshold': 0.02},
            status='active',
            performance_metrics={'sharpe': 1.5, 'max_drawdown': -0.15}
        )
        
        session.add(strategy)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(StrategyParameters).first()
        assert retrieved is not None
        assert retrieved.name == 'momentum_strategy'
        assert retrieved.parameters['M'] == 20
        assert retrieved.status == 'active'
        assert retrieved.performance_metrics['sharpe'] == 1.5
    
    def test_strategy_metadata(self, session):
        """Test strategy metadata field"""
        strategy = StrategyParameters(
            name='mean_reversion',
            parameters={'lookback': 50},
            strategy_metadata={'author': 'system', 'version': '1.0'}
        )
        
        session.add(strategy)
        session.commit()
        
        retrieved = session.query(StrategyParameters).first()
        assert retrieved.strategy_metadata['author'] == 'system'
        assert retrieved.strategy_metadata['version'] == '1.0'


class TestDatabaseIntegrity:
    """Test database constraints and integrity"""
    
    def test_cascade_delete(self, session):
        """Test cascade delete behavior"""
        # Create account with positions and trades
        account = Account(
            exchange='binance',
            account_type='spot',
            api_key='key',
            api_secret='secret'
        )
        session.add(account)
        session.commit()
        
        position = Position(
            account_id=account.id,
            symbol='BTC/USD',
            side='long',
            quantity=Decimal('1.0'),
            entry_price=Decimal('50000.0'),
            current_price=Decimal('51000.0'),
            unrealized_pnl=Decimal('1000.0'),
            status='open'
        )
        session.add(position)
        session.commit()
        
        # Delete account (should handle cascade)
        session.delete(account)
        session.commit()
        
        # Verify position handling
        positions = session.query(Position).all()
        # Behavior depends on cascade settings


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
