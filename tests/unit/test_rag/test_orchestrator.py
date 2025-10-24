"""
Unit tests for RAG IntelligenceOrchestrator.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from web.rag.orchestrator import IntelligenceOrchestrator, create_orchestrator


class TestIntelligenceOrchestrator:
    """Test IntelligenceOrchestrator class."""
    
    @pytest.fixture
    def mock_intelligence(self):
        """Create mock FKSIntelligence."""
        mock = Mock()
        mock.query.return_value = {
            'answer': 'Based on historical data, BUY signal for BTCUSDT. '
                     'RSI oversold at 35, MACD shows bullish divergence. '
                     'Confidence: 85%. Entry: $42,000. Stop loss: $40,500. '
                     'Take profit: $44,000. Risk: medium.',
            'sources': [
                {'chunk_id': 1, 'similarity': 0.92, 'doc_type': 'signal'},
                {'chunk_id': 2, 'similarity': 0.88, 'doc_type': 'backtest'},
            ],
            'context_used': 2,
            'response_time_ms': 1500
        }
        return mock
    
    @pytest.fixture
    def orchestrator(self, mock_intelligence):
        """Create orchestrator with mocked intelligence."""
        with patch('web.rag.orchestrator.create_intelligence', return_value=mock_intelligence):
            return IntelligenceOrchestrator()
    
    def test_initialization(self):
        """Test orchestrator initialization."""
        with patch('web.rag.orchestrator.create_intelligence') as mock_create:
            mock_create.return_value = Mock()
            
            orchestrator = IntelligenceOrchestrator(
                use_local=True,
                local_llm_model="llama3.2:3b",
                embedding_model="all-MiniLM-L6-v2"
            )
            
            assert orchestrator.intelligence is not None
            mock_create.assert_called_once_with(
                use_local=True,
                local_llm_model="llama3.2:3b",
                embedding_model="all-MiniLM-L6-v2"
            )
    
    def test_create_orchestrator(self):
        """Test convenience function."""
        with patch('web.rag.orchestrator.create_intelligence') as mock_create:
            mock_create.return_value = Mock()
            
            orchestrator = create_orchestrator(use_local=True)
            
            assert isinstance(orchestrator, IntelligenceOrchestrator)
            mock_create.assert_called_once()
    
    def test_get_trading_recommendation_basic(self, orchestrator, mock_intelligence):
        """Test basic trading recommendation."""
        result = orchestrator.get_trading_recommendation(
            symbol='BTCUSDT',
            account_balance=10000.00,
            context='current market conditions'
        )
        
        # Check structure
        assert 'symbol' in result
        assert 'action' in result
        assert 'position_size_usd' in result
        assert 'risk_assessment' in result
        assert 'reasoning' in result
        assert 'confidence' in result
        assert 'timestamp' in result
        
        # Check values
        assert result['symbol'] == 'BTCUSDT'
        assert result['action'] in ['BUY', 'SELL', 'HOLD']
        assert result['position_size_usd'] > 0
        assert result['risk_assessment'] in ['low', 'medium', 'high']
        assert 0 <= result['confidence'] <= 1
        
        # Verify intelligence was called
        mock_intelligence.query.assert_called_once()
        call_args = mock_intelligence.query.call_args
        assert 'BTCUSDT' in call_args[1]['question']
        assert call_args[1]['symbol'] == 'BTCUSDT'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
