"""
Test suite for daily trading engine
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock


# Skip if dependencies not available
try:
    from daily_trading_engine import DailyTradingEngine, PositionAnalysis, TradingOpportunity
    from ml_models import TradingMLEngine
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False


@pytest.mark.skipif(not ENGINE_AVAILABLE, reason="Trading engine not available")
class TestDailyTradingEngine:
    """Test daily trading engine functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        session = Mock()
        return session
    
    @pytest.fixture
    def mock_ml_engine(self):
        """Create mock ML engine"""
        ml_engine = Mock()
        ml_engine.predict_regime.return_value = 0  # Bullish
        ml_engine.predict_price.return_value = 52000.0
        ml_engine.get_trading_signal.return_value = {
            'regime': 0,
            'confidence': 0.75,
            'recommendation': 'buy'
        }
        return ml_engine
    
    @pytest.fixture
    def sample_positions(self):
        """Generate sample positions"""
        return [
            {
                'symbol': 'BTC/USD',
                'side': 'long',
                'quantity': Decimal('0.5'),
                'entry_price': Decimal('50000.0'),
                'current_price': Decimal('51000.0'),
                'unrealized_pnl': Decimal('500.0'),
                'stop_loss': Decimal('48000.0'),
                'take_profit': Decimal('55000.0'),
                'entry_time': datetime.now() - timedelta(days=2)
            },
            {
                'symbol': 'ETH/USD',
                'side': 'long',
                'quantity': Decimal('2.0'),
                'entry_price': Decimal('3000.0'),
                'current_price': Decimal('3100.0'),
                'unrealized_pnl': Decimal('200.0'),
                'stop_loss': Decimal('2900.0'),
                'take_profit': Decimal('3300.0'),
                'entry_time': datetime.now() - timedelta(days=1)
            }
        ]
    
    @pytest.fixture
    def sample_market_data(self):
        """Generate sample market data"""
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        
        data = {}
        for symbol in ['BTC/USD', 'ETH/USD', 'XRP/USD']:
            base_price = {'BTC/USD': 50000, 'ETH/USD': 3000, 'XRP/USD': 0.5}[symbol]
            
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
    
    def test_engine_initialization(self, mock_db_session, mock_ml_engine):
        """Test engine initialization"""
        engine = DailyTradingEngine(
            db_session=mock_db_session,
            ml_engine=mock_ml_engine
        )
        
        assert engine.db_session is not None
        assert engine.ml_engine is not None
    
    def test_analyze_positions(self, mock_db_session, mock_ml_engine, sample_positions, sample_market_data):
        """Test position analysis"""
        engine = DailyTradingEngine(
            db_session=mock_db_session,
            ml_engine=mock_ml_engine
        )
        
        # Mock the position fetching
        with patch.object(engine, '_fetch_current_positions', return_value=sample_positions):
            with patch.object(engine, '_fetch_market_data', return_value=sample_market_data):
                analyses = engine.analyze_positions()
        
        assert isinstance(analyses, list)
        assert len(analyses) > 0
        
        # Check analysis structure
        for analysis in analyses:
            assert 'symbol' in analysis
            assert 'action' in analysis
            assert 'reason' in analysis
    
    def test_find_opportunities(self, mock_db_session, mock_ml_engine, sample_market_data):
        """Test opportunity finding"""
        engine = DailyTradingEngine(
            db_session=mock_db_session,
            ml_engine=mock_ml_engine
        )
        
        with patch.object(engine, '_fetch_market_data', return_value=sample_market_data):
            opportunities = engine.find_opportunities(
                symbols=['BTC/USD', 'ETH/USD', 'XRP/USD']
            )
        
        assert isinstance(opportunities, list)
        
        # Check opportunity structure
        for opp in opportunities:
            assert 'symbol' in opp
            assert 'action' in opp
            assert 'confidence' in opp
            assert 'entry_price' in opp
            assert 'score' in opp
            
            assert opp['action'] in ['buy', 'sell', 'hold']
            assert 0 <= opp['confidence'] <= 1
    
    def test_generate_daily_plan(self, mock_db_session, mock_ml_engine, sample_positions, sample_market_data):
        """Test daily trading plan generation"""
        engine = DailyTradingEngine(
            db_session=mock_db_session,
            ml_engine=mock_ml_engine
        )
        
        with patch.object(engine, '_fetch_current_positions', return_value=sample_positions):
            with patch.object(engine, '_fetch_market_data', return_value=sample_market_data):
                plan = engine.generate_daily_plan(
                    symbols=['BTC/USD', 'ETH/USD', 'XRP/USD']
                )
        
        assert isinstance(plan, dict)
        
        # Check plan structure
        assert 'date' in plan
        assert 'market_overview' in plan
        assert 'position_analyses' in plan
        assert 'new_opportunities' in plan
        assert 'risk_assessment' in plan
        assert 'recommendations' in plan
        
        assert isinstance(plan['position_analyses'], list)
        assert isinstance(plan['new_opportunities'], list)
    
    def test_calculate_position_size(self, mock_db_session, mock_ml_engine):
        """Test position size calculation"""
        engine = DailyTradingEngine(
            db_session=mock_db_session,
            ml_engine=mock_ml_engine,
            max_risk_per_trade=0.02
        )
        
        account_balance = 10000.0
        entry_price = 50000.0
        stop_loss = 48000.0
        
        position_size = engine.calculate_position_size(
            account_balance=account_balance,
            entry_price=entry_price,
            stop_loss=stop_loss
        )
        
        assert position_size > 0
        
        # Risk should not exceed max_risk_per_trade
        risk_per_unit = entry_price - stop_loss
        total_risk = position_size * risk_per_unit
        max_allowed_risk = account_balance * engine.max_risk_per_trade
        
        assert total_risk <= max_allowed_risk * 1.01  # Small tolerance
    
    def test_calculate_stop_loss(self, mock_db_session, mock_ml_engine, sample_market_data):
        """Test stop loss calculation"""
        engine = DailyTradingEngine(
            db_session=mock_db_session,
            ml_engine=mock_ml_engine
        )
        
        symbol = 'BTC/USD'
        entry_price = 50000.0
        side = 'long'
        
        stop_loss = engine.calculate_stop_loss(
            symbol=symbol,
            entry_price=entry_price,
            side=side,
            market_data=sample_market_data[symbol],
            regime='bullish'
        )
        
        assert stop_loss > 0
        
        # Stop loss should be below entry for long position
        if side == 'long':
            assert stop_loss < entry_price
        else:
            assert stop_loss > entry_price
    
    def test_calculate_take_profit(self, mock_db_session, mock_ml_engine, sample_market_data):
        """Test take profit calculation"""
        engine = DailyTradingEngine(
            db_session=mock_db_session,
            ml_engine=mock_ml_engine
        )
        
        symbol = 'BTC/USD'
        entry_price = 50000.0
        stop_loss = 48000.0
        side = 'long'
        
        take_profit = engine.calculate_take_profit(
            entry_price=entry_price,
            stop_loss=stop_loss,
            side=side,
            risk_reward_ratio=2.0
        )
        
        assert take_profit > 0
        
        # Take profit should be above entry for long position
        if side == 'long':
            assert take_profit > entry_price
        else:
            assert take_profit < entry_price
        
        # Check risk-reward ratio
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        
        assert abs(reward / risk - 2.0) < 0.1  # Approximately 2:1


class TestPositionAnalysis:
    """Test position analysis data structure"""
    
    def test_create_position_analysis(self):
        """Test creating position analysis"""
        analysis = {
            'symbol': 'BTC/USD',
            'current_pnl': 500.0,
            'pnl_percentage': 0.01,
            'hold_time_days': 2,
            'action': 'hold',
            'reason': 'Position trending favorably',
            'suggested_stop': 48000.0,
            'suggested_target': 55000.0
        }
        
        assert analysis['symbol'] == 'BTC/USD'
        assert analysis['action'] in ['hold', 'close', 'adjust_stops']
        assert analysis['pnl_percentage'] > 0


class TestTradingOpportunity:
    """Test trading opportunity data structure"""
    
    def test_create_opportunity(self):
        """Test creating trading opportunity"""
        opportunity = {
            'symbol': 'ETH/USD',
            'action': 'buy',
            'confidence': 0.75,
            'entry_price': 3000.0,
            'stop_loss': 2900.0,
            'take_profit': 3300.0,
            'position_size': 2.0,
            'score': 8.5,
            'regime': 'bullish',
            'reasons': ['Strong momentum', 'Positive ML signal']
        }
        
        assert opportunity['action'] in ['buy', 'sell']
        assert 0 <= opportunity['confidence'] <= 1
        assert opportunity['score'] > 0
        assert len(opportunity['reasons']) > 0


class TestRiskManagement:
    """Test risk management functionality"""
    
    @pytest.fixture
    def engine(self, mock_db_session, mock_ml_engine):
        """Create engine instance"""
        return DailyTradingEngine(
            db_session=mock_db_session,
            ml_engine=mock_ml_engine,
            max_risk_per_trade=0.02,
            max_positions=5
        )
    
    def test_max_risk_per_trade(self, engine):
        """Test max risk per trade enforcement"""
        account_balance = 10000.0
        entry_price = 50000.0
        stop_loss = 45000.0  # Large stop
        
        position_size = engine.calculate_position_size(
            account_balance=account_balance,
            entry_price=entry_price,
            stop_loss=stop_loss
        )
        
        # Calculate actual risk
        risk_per_unit = abs(entry_price - stop_loss)
        total_risk = position_size * risk_per_unit
        
        # Risk should not exceed limit
        max_risk = account_balance * engine.max_risk_per_trade
        assert total_risk <= max_risk * 1.01
    
    def test_max_positions_limit(self, engine, sample_positions):
        """Test maximum positions limit"""
        # Mock having max positions already
        with patch.object(engine, '_fetch_current_positions', return_value=sample_positions * 3):
            with patch.object(engine, '_fetch_market_data', return_value={}):
                plan = engine.generate_daily_plan(symbols=['BTC/USD'])
        
        # Should warn about max positions or limit opportunities
        assert 'risk_assessment' in plan
    
    def test_position_sizing_edge_cases(self, engine):
        """Test position sizing with edge cases"""
        # Very tight stop
        size1 = engine.calculate_position_size(
            account_balance=10000.0,
            entry_price=50000.0,
            stop_loss=49900.0
        )
        
        # Very wide stop
        size2 = engine.calculate_position_size(
            account_balance=10000.0,
            entry_price=50000.0,
            stop_loss=40000.0
        )
        
        # Tight stop should allow larger position
        assert size1 > size2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
