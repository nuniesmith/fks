"""
Integration tests for RAG-powered Celery tasks.

Tests the integration between IntelligenceOrchestrator and trading tasks.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal

# Import the orchestrator
from src.rag.orchestrator import IntelligenceOrchestrator, create_orchestrator


class TestIntelligenceOrchestratorIntegration:
    """Test IntelligenceOrchestrator integration with tasks."""
    
    def test_orchestrator_initialization(self):
        """Test that orchestrator can be initialized."""
        orchestrator = IntelligenceOrchestrator(use_local=True)
        assert orchestrator is not None
        assert orchestrator.intelligence is not None
    
    def test_create_orchestrator_factory(self):
        """Test factory function."""
        orchestrator = create_orchestrator(use_local=True)
        assert isinstance(orchestrator, IntelligenceOrchestrator)
    
    def test_get_trading_recommendation_basic(self):
        """Test basic trading recommendation."""
        orchestrator = IntelligenceOrchestrator(use_local=True)
        
        result = orchestrator.get_trading_recommendation(
            symbol='BTCUSDT',
            account_balance=10000.00,
            available_cash=8000.00,
            context='current market conditions'
        )
        
        # Verify response structure
        assert 'symbol' in result
        assert 'action' in result
        assert 'position_size_usd' in result
        assert 'reasoning' in result
        assert 'risk_assessment' in result
        assert 'confidence' in result
        assert 'timestamp' in result
        
        # Verify values
        assert result['symbol'] == 'BTCUSDT'
        assert result['action'] in ['BUY', 'SELL', 'HOLD']
        assert isinstance(result['position_size_usd'], float)
        assert result['risk_assessment'] in ['low', 'medium', 'high']
        assert 0 <= result['confidence'] <= 1
    
    def test_get_trading_recommendation_with_positions(self):
        """Test recommendation with existing positions."""
        orchestrator = IntelligenceOrchestrator(use_local=True)
        
        current_positions = {
            'BTCUSDT': {
                'quantity': 0.1,
                'entry_price': 42000.0,
                'current_price': 43000.0,
                'unrealized_pnl': 100.0
            }
        }
        
        result = orchestrator.get_trading_recommendation(
            symbol='ETHUSDT',
            account_balance=10000.00,
            available_cash=5000.00,
            current_positions=current_positions
        )
        
        assert result['symbol'] == 'ETHUSDT'
        assert 'action' in result
    
    def test_get_daily_signals(self):
        """Test daily signal generation."""
        orchestrator = IntelligenceOrchestrator(use_local=True)
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        result = orchestrator.get_daily_signals(
            symbols=symbols,
            min_confidence=0.7
        )
        
        # Verify response structure
        assert 'date' in result
        assert 'signals' in result
        assert 'high_confidence_count' in result
        
        # Verify signals for each symbol
        for symbol in symbols:
            assert symbol in result['signals']
            signal = result['signals'][symbol]
            assert 'recommendation' in signal
            assert 'confidence' in signal
            assert 'action' in signal
    
    def test_optimize_portfolio(self):
        """Test portfolio optimization."""
        orchestrator = IntelligenceOrchestrator(use_local=True)
        
        symbols = ['BTCUSDT', 'ETHUSDT']
        current_positions = {
            'BTCUSDT': {
                'quantity': 0.1,
                'entry_price': 42000.0,
                'current_price': 43000.0
            }
        }
        
        result = orchestrator.optimize_portfolio(
            symbols=symbols,
            account_balance=10000.00,
            available_cash=5000.00,
            current_positions=current_positions,
            market_condition='bullish'
        )
        
        # Verify response structure
        assert 'symbols' in result
        assert 'portfolio_advice' in result
        assert 'rebalance_needed' in result
        assert 'timestamp' in result
        
        # Verify it's a boolean
        assert isinstance(result['rebalance_needed'], bool)


class TestTaskIntegrationWithRAG:
    """Test that tasks can use IntelligenceOrchestrator."""
    
    def test_generate_signals_task_imports(self):
        """Test that generate_signals_task can import and use orchestrator."""
        import sys
        sys.path.insert(0, '/home/runner/work/fks/fks/src')
        
        # This should not raise ImportError
        try:
            from trading.tasks import generate_signals_task, RAG_AVAILABLE
            assert generate_signals_task is not None
            assert isinstance(RAG_AVAILABLE, bool)
            import_success = True
        except ImportError as e:
            import_success = False
            pytest.fail(f"Failed to import: {e}")
        
        assert import_success
    
    def test_optimize_portfolio_task_imports(self):
        """Test that optimize_portfolio_task can import orchestrator."""
        import sys
        sys.path.insert(0, '/home/runner/work/fks/fks/src')
        
        try:
            from trading.tasks import optimize_portfolio_task, RAG_AVAILABLE
            assert optimize_portfolio_task is not None
            assert isinstance(RAG_AVAILABLE, bool)
            import_success = True
        except ImportError as e:
            import_success = False
            pytest.fail(f"Failed to import: {e}")
        
        assert import_success
    
    def test_generate_daily_rag_signals_task_imports(self):
        """Test that generate_daily_rag_signals_task can import."""
        import sys
        sys.path.insert(0, '/home/runner/work/fks/fks/src')
        
        try:
            from trading.tasks import generate_daily_rag_signals_task, RAG_AVAILABLE
            assert generate_daily_rag_signals_task is not None
            assert isinstance(RAG_AVAILABLE, bool)
            import_success = True
        except ImportError as e:
            import_success = False
            pytest.fail(f"Failed to import: {e}")
        
        assert import_success


class TestRegressionSafety:
    """Ensure tasks still work without full RAG infrastructure."""
    
    def test_orchestrator_graceful_degradation(self):
        """Test that orchestrator works even with mock intelligence."""
        # This should not raise an exception
        orchestrator = IntelligenceOrchestrator(use_local=True)
        
        # Should return HOLD when RAG not fully available
        result = orchestrator.get_trading_recommendation(
            symbol='BTCUSDT',
            account_balance=10000.00,
            available_cash=8000.00
        )
        
        # Should have valid structure even if using mock
        assert result['action'] in ['BUY', 'SELL', 'HOLD']
        assert isinstance(result['confidence'], float)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
