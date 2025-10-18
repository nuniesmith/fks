"""
Unit tests for RAG DocumentProcessor.
"""
import pytest
from web.rag.document_processor import DocumentProcessor, Chunk, create_processor


class TestDocumentProcessor:
    """Test DocumentProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create a document processor."""
        return DocumentProcessor(chunk_size=512, chunk_overlap=50)
    
    def test_initialization(self):
        """Test processor initialization."""
        processor = DocumentProcessor(
            chunk_size=256,
            chunk_overlap=25,
            model_name="gpt-3.5-turbo"
        )
        
        assert processor.chunk_size == 256
        assert processor.chunk_overlap == 25
        assert processor.encoding is not None
    
    def test_create_processor(self):
        """Test convenience function."""
        processor = create_processor(chunk_size=512, chunk_overlap=50)
        
        assert isinstance(processor, DocumentProcessor)
        assert processor.chunk_size == 512
        assert processor.chunk_overlap == 50
    
    def test_count_tokens(self, processor):
        """Test token counting."""
        text = "Bitcoin is trading at $42,000"
        token_count = processor.count_tokens(text)
        
        assert isinstance(token_count, int)
        assert token_count > 0
    
    def test_chunk_text_empty(self, processor):
        """Test chunking empty text."""
        chunks = processor.chunk_text("")
        
        assert chunks == []
        
        chunks = processor.chunk_text("   ")
        assert chunks == []
    
    def test_chunk_text_short(self, processor):
        """Test chunking short text (single chunk)."""
        text = "This is a short test text."
        chunks = processor.chunk_text(text)
        
        assert len(chunks) == 1
        assert chunks[0].content.strip() == text.strip()
        assert chunks[0].chunk_index == 0
        assert chunks[0].token_count > 0
    
    def test_chunk_text_long(self, processor):
        """Test chunking long text (multiple chunks)."""
        # Create text that will require multiple chunks
        text = "Bitcoin trading analysis. " * 200  # Long text
        chunks = processor.chunk_text(text)
        
        assert len(chunks) > 1
        
        # Check chunk properties
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.token_count > 0
            assert chunk.token_count <= processor.chunk_size
            assert len(chunk.content) > 0
    
    def test_chunk_text_with_metadata(self, processor):
        """Test chunking with metadata."""
        text = "Test content"
        metadata = {'source': 'test', 'category': 'signal'}
        
        chunks = processor.chunk_text(text, metadata=metadata)
        
        assert len(chunks) == 1
        assert chunks[0].metadata == metadata
    
    def test_clean_text(self, processor):
        """Test text cleaning."""
        text = "Bitcoin   trading\n\n\n    analysis\t\twith   extra   spaces"
        cleaned = processor._clean_text(text)
        
        # Should normalize whitespace
        assert "  " not in cleaned
        assert "\n\n" not in cleaned
        assert "\t" not in cleaned
    
    def test_chunk_trading_signal(self, processor):
        """Test chunking trading signal data."""
        signal_data = {
            'symbol': 'BTCUSDT',
            'action': 'BUY',
            'price': 42000.00,
            'timestamp': '2024-10-18T10:00:00',
            'indicators': {
                'rsi': 35.5,
                'macd': -50.2,
                'bb_position': 0.15
            },
            'reasoning': 'RSI oversold + MACD divergence',
            'stop_loss': 40500.00,
            'take_profit': 44000.00
        }
        
        chunks = processor.chunk_trading_signal(signal_data)
        
        assert len(chunks) >= 1
        
        # Check that chunk contains key information
        chunk_text = chunks[0].content.lower()
        assert 'btcusdt' in chunk_text
        assert 'buy' in chunk_text
        assert 'rsi' in chunk_text
        
        # Check metadata
        assert chunks[0].metadata['type'] == 'signal'
        assert chunks[0].metadata['symbol'] == 'BTCUSDT'
        assert chunks[0].metadata['action'] == 'BUY'
    
    def test_chunk_backtest_result(self, processor):
        """Test chunking backtest results."""
        backtest_data = {
            'strategy_name': 'RSI Reversal',
            'symbol': 'ETHUSDT',
            'timeframe': '4h',
            'start_date': '2024-01-01',
            'end_date': '2024-10-01',
            'total_return': 45.2,
            'win_rate': 68.5,
            'sharpe_ratio': 2.1,
            'max_drawdown': -12.3,
            'total_trades': 85,
            'parameters': {
                'rsi_period': 14,
                'rsi_oversold': 30
            },
            'insights': 'Strategy performs well in ranging markets.'
        }
        
        chunks = processor.chunk_backtest_result(backtest_data)
        
        assert len(chunks) >= 1
        
        # Check content
        chunk_text = chunks[0].content
        assert 'RSI Reversal' in chunk_text
        assert 'ETHUSDT' in chunk_text
        assert '45.2' in chunk_text
        assert '68.5' in chunk_text
        
        # Check metadata
        assert chunks[0].metadata['type'] == 'backtest'
        assert chunks[0].metadata['symbol'] == 'ETHUSDT'
        assert chunks[0].metadata['total_return'] == 45.2
        assert chunks[0].metadata['win_rate'] == 68.5
    
    def test_chunk_trade_analysis(self, processor):
        """Test chunking trade analysis."""
        trade_data = {
            'symbol': 'SOLUSDT',
            'position_side': 'LONG',
            'entry_price': 100.0,
            'exit_price': 105.0,
            'quantity': 10.0,
            'realized_pnl': 50.0,
            'pnl_percent': 5.0,
            'duration': '2 hours',
            'time': '2024-10-18T10:00:00',
            'strategy_name': 'Momentum',
            'notes': 'Quick profit on breakout'
        }
        
        chunks = processor.chunk_trade_analysis(trade_data)
        
        assert len(chunks) >= 1
        
        # Check content
        chunk_text = chunks[0].content
        assert 'SOLUSDT' in chunk_text
        assert 'LONG' in chunk_text
        assert '100' in chunk_text
        assert '105' in chunk_text
        
        # Check metadata
        assert chunks[0].metadata['type'] == 'trade'
        assert chunks[0].metadata['symbol'] == 'SOLUSDT'
        assert chunks[0].metadata['pnl'] == 50.0
    
    def test_chunk_market_report(self, processor):
        """Test chunking market report."""
        report_text = """
        Bitcoin Technical Analysis - October 18, 2024
        
        Current Price: $42,150
        
        Key Levels:
        - Support: $41,500
        - Resistance: $43,200
        
        Technical Indicators:
        - RSI(14): 52 (neutral)
        - MACD: Bullish crossover
        - Volume: Above average
        """
        
        chunks = processor.chunk_market_report(
            report_text=report_text,
            symbol='BTCUSDT',
            timeframe='1d'
        )
        
        assert len(chunks) >= 1
        
        # Check metadata
        assert chunks[0].metadata['type'] == 'market_report'
        assert chunks[0].metadata['symbol'] == 'BTCUSDT'
        assert chunks[0].metadata['timeframe'] == '1d'
    
    def test_format_signal_text(self, processor):
        """Test signal formatting."""
        signal = {
            'symbol': 'BTCUSDT',
            'action': 'BUY',
            'timestamp': '2024-10-18T10:00:00',
            'price': 42000.00,
            'indicators': {'rsi': 35},
            'stop_loss': 40500.00,
            'reasoning': 'Good entry'
        }
        
        formatted = processor._format_signal_text(signal)
        
        assert 'BTCUSDT' in formatted
        assert 'BUY' in formatted
        assert 'rsi' in formatted.lower()
        assert '42000' in formatted
    
    def test_format_backtest_text(self, processor):
        """Test backtest formatting."""
        backtest = {
            'strategy_name': 'Test Strategy',
            'symbol': 'ETHUSDT',
            'timeframe': '1h',
            'total_return': 25.0,
            'win_rate': 65.0,
            'sharpe_ratio': 1.8,
            'max_drawdown': -10.0,
            'total_trades': 50
        }
        
        formatted = processor._format_backtest_text(backtest)
        
        assert 'Test Strategy' in formatted
        assert 'ETHUSDT' in formatted
        assert '25.00%' in formatted
        assert '65.00%' in formatted
    
    def test_format_trade_text(self, processor):
        """Test trade formatting."""
        trade = {
            'symbol': 'BNBUSDT',
            'position_side': 'SHORT',
            'entry_price': 300.0,
            'exit_price': 290.0,
            'quantity': 5.0,
            'realized_pnl': 50.0,
            'pnl_percent': 3.33
        }
        
        formatted = processor._format_trade_text(trade)
        
        assert 'BNBUSDT' in formatted
        assert 'SHORT' in formatted
        assert '300' in formatted
        assert '290' in formatted


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
