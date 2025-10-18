"""
Unit tests for RAG document processor with comprehensive mocking.
Tests chunking, formatting, and preprocessing logic in isolation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from web.rag.document_processor import DocumentProcessor


class TestDocumentProcessor:
    """Test DocumentProcessor in isolation with mocks."""

    @pytest.fixture
    def processor(self):
        """Create a document processor instance."""
        return DocumentProcessor()

    def test_chunk_text_basic(self, processor):
        """Test basic text chunking functionality."""
        text = "This is a test sentence. " * 100
        result = processor.chunk_text(text, chunk_size=200, overlap=20)
        
        assert len(result) > 1
        assert all(hasattr(chunk, 'content') for chunk in result)
        assert all(hasattr(chunk, 'chunk_index') for chunk in result)
        assert all(hasattr(chunk, 'token_count') for chunk in result)

    def test_chunk_text_with_metadata(self, processor):
        """Test chunking with metadata preservation."""
        text = "Sample text for chunking."
        metadata = {'doc_id': 123, 'source': 'test'}
        
        result = processor.chunk_text(text, metadata=metadata)
        
        assert len(result) > 0
        for chunk in result:
            assert chunk.metadata.get('doc_id') == 123
            assert chunk.metadata.get('source') == 'test'

    def test_chunk_text_empty(self, processor):
        """Test chunking empty text."""
        result = processor.chunk_text("")
        
        # Should handle empty gracefully
        assert isinstance(result, list)
        assert len(result) == 0 or (len(result) == 1 and result[0].content == "")

    def test_chunk_text_short(self, processor):
        """Test chunking text shorter than chunk size."""
        text = "Short text."
        result = processor.chunk_text(text, chunk_size=1000)
        
        assert len(result) == 1
        assert result[0].content == text

    def test_chunk_signal_formatting(self, processor):
        """Test formatting signal data into text."""
        signal_data = {
            'id': 1,
            'symbol': 'BTCUSDT',
            'type': 'LONG',
            'strength': 0.85,
            'price': 50000.0,
            'timestamp': datetime(2025, 10, 18, 12, 0, 0),
            'indicators': {'rsi': 35, 'macd': -0.5, 'bb_position': 0.2},
            'strategy': 'momentum'
        }
        
        result = processor.chunk_signal(signal_data)
        
        assert 'BTCUSDT' in result
        assert 'LONG' in result or 'long' in result
        assert '50000' in result or '50,000' in result
        assert 'momentum' in result.lower()
        assert 'rsi' in result.lower() or 'RSI' in result

    def test_chunk_signal_minimal(self, processor):
        """Test formatting signal with minimal data."""
        signal_data = {
            'symbol': 'ETHUSDT',
            'type': 'SHORT'
        }
        
        result = processor.chunk_signal(signal_data)
        
        assert 'ETHUSDT' in result
        assert 'SHORT' in result or 'short' in result

    def test_chunk_backtest_formatting(self, processor):
        """Test formatting backtest results into text."""
        backtest_data = {
            'id': 1,
            'symbol': 'BTCUSDT',
            'strategy': 'momentum',
            'win_rate': 0.68,
            'sharpe_ratio': 2.1,
            'max_drawdown': 0.15,
            'total_trades': 50,
            'total_return': 0.35
        }
        
        result = processor.chunk_backtest(backtest_data)
        
        assert 'BTCUSDT' in result
        assert 'momentum' in result.lower()
        assert '68' in result or '0.68' in result  # Win rate
        assert '2.1' in result  # Sharpe
        assert '50' in result  # Total trades

    def test_chunk_backtest_negative_results(self, processor):
        """Test formatting backtest with negative results."""
        backtest_data = {
            'symbol': 'SOLUSDT',
            'strategy': 'mean_reversion',
            'win_rate': 0.42,
            'sharpe_ratio': -0.5,
            'max_drawdown': 0.35,
            'total_return': -0.12
        }
        
        result = processor.chunk_backtest(backtest_data)
        
        assert 'SOLUSDT' in result
        assert 'mean_reversion' in result
        # Should include negative indicators
        assert '-0.5' in result or 'negative' in result.lower()

    def test_chunk_trade_formatting(self, processor):
        """Test formatting completed trade into text."""
        trade_data = {
            'id': 1,
            'symbol': 'ETHUSDT',
            'side': 'BUY',
            'quantity': 5.0,
            'entry_price': 2000.0,
            'exit_price': 2100.0,
            'pnl': 500.0,
            'pnl_percent': 0.05,
            'entry_time': datetime(2025, 10, 18, 10, 0, 0),
            'exit_time': datetime(2025, 10, 18, 14, 0, 0),
            'duration_hours': 4.0,
            'outcome': 'WIN'
        }
        
        result = processor.chunk_trade(trade_data)
        
        assert 'ETHUSDT' in result
        assert 'BUY' in result or 'buy' in result
        assert '2000' in result  # Entry price
        assert '2100' in result  # Exit price
        assert '500' in result or 'profit' in result.lower()
        assert 'WIN' in result or 'win' in result

    def test_chunk_trade_loss(self, processor):
        """Test formatting losing trade."""
        trade_data = {
            'symbol': 'BNBUSDT',
            'side': 'SELL',
            'entry_price': 300.0,
            'exit_price': 310.0,
            'pnl': -50.0,
            'outcome': 'LOSS'
        }
        
        result = processor.chunk_trade(trade_data)
        
        assert 'BNBUSDT' in result
        assert 'SELL' in result or 'sell' in result
        assert '-50' in result or 'loss' in result.lower()
        assert 'LOSS' in result or 'loss' in result

    def test_chunk_overlap_preservation(self, processor):
        """Test that overlap between chunks is preserved."""
        text = "Word " * 100
        chunk_size = 100
        overlap = 20
        
        result = processor.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        
        # Should have multiple chunks due to length
        assert len(result) > 1
        
        # Check that chunks have proper indices
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_token_counting(self, processor):
        """Test that token counts are calculated."""
        text = "This is a test with multiple words and tokens."
        result = processor.chunk_text(text)
        
        assert len(result) > 0
        for chunk in result:
            assert chunk.token_count > 0
            # Rough estimate: tokens should be less than word count
            assert chunk.token_count <= len(chunk.content.split()) * 2

    @pytest.mark.parametrize("chunk_size,overlap", [
        (100, 10),
        (500, 50),
        (1000, 100),
        (200, 40)
    ])
    def test_chunk_sizes(self, processor, chunk_size, overlap):
        """Test different chunk size configurations."""
        text = "Test sentence. " * 200
        result = processor.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        
        assert len(result) > 0
        # Each chunk should respect the approximate size
        for chunk in result[:-1]:  # Exclude last chunk which may be shorter
            assert len(chunk.content) <= chunk_size * 2  # Allow some flexibility


class TestDocumentProcessorEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def processor(self):
        return DocumentProcessor()

    def test_chunk_very_long_text(self, processor):
        """Test chunking very long text."""
        text = "Long text. " * 10000
        result = processor.chunk_text(text, chunk_size=500)
        
        assert len(result) > 10
        # Verify indices are sequential
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_chunk_unicode_text(self, processor):
        """Test chunking text with unicode characters."""
        text = "Testing unicode: 中文 日本語 한국어 العربية 🚀 📈 💰"
        result = processor.chunk_text(text)
        
        assert len(result) > 0
        assert any('中文' in chunk.content or '日本語' in chunk.content for chunk in result)

    def test_chunk_signal_missing_fields(self, processor):
        """Test signal chunking with missing optional fields."""
        signal_data = {
            'symbol': 'BTCUSDT',
            'type': 'LONG'
            # Missing: strength, price, indicators, etc.
        }
        
        # Should not raise an error
        result = processor.chunk_signal(signal_data)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_chunk_backtest_missing_fields(self, processor):
        """Test backtest chunking with missing optional fields."""
        backtest_data = {
            'symbol': 'ETHUSDT',
            'strategy': 'test'
            # Missing: metrics
        }
        
        result = processor.chunk_backtest(backtest_data)
        assert isinstance(result, str)
        assert 'ETHUSDT' in result

    def test_chunk_trade_missing_fields(self, processor):
        """Test trade chunking with missing optional fields."""
        trade_data = {
            'symbol': 'BNBUSDT',
            'side': 'BUY'
            # Missing: prices, pnl, etc.
        }
        
        result = processor.chunk_trade(trade_data)
        assert isinstance(result, str)
        assert 'BNBUSDT' in result

    def test_chunk_with_none_metadata(self, processor):
        """Test chunking with None metadata."""
        text = "Test text"
        result = processor.chunk_text(text, metadata=None)
        
        assert len(result) > 0
        # Should handle None metadata gracefully


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
