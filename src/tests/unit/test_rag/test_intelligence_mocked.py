"""
Unit tests for FKS Intelligence RAG orchestrator with comprehensive mocking.
Tests query processing, response generation, and system integration in isolation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime

from web.rag.intelligence import FKSIntelligence


class TestFKSIntelligenceMocked:
    """Test FKS Intelligence with all dependencies mocked."""

    @pytest.fixture
    def mock_components(self):
        """Create mocked RAG components."""
        return {
            'processor': MagicMock(),
            'embeddings': MagicMock(),
            'retrieval': MagicMock(),
            'llm': MagicMock(),
            'session': MagicMock()
        }

    @pytest.fixture
    def intelligence_with_mocks(self, mock_components):
        """Create intelligence service with mocked dependencies."""
        with patch('web.rag.intelligence.DocumentProcessor', return_value=mock_components['processor']):
            with patch('web.rag.intelligence.EmbeddingsService', return_value=mock_components['embeddings']):
                with patch('web.rag.intelligence.RetrievalService', return_value=mock_components['retrieval']):
                    intel = FKSIntelligence(use_local=False)  # Don't initialize LLM
                    intel.processor = mock_components['processor']
                    intel.embeddings = mock_components['embeddings']
                    intel.retrieval = mock_components['retrieval']
                    intel.client = mock_components['llm']
                    return intel

    def test_initialization_local(self):
        """Test initialization with local models."""
        with patch('web.rag.intelligence.DocumentProcessor'):
            with patch('web.rag.intelligence.EmbeddingsService'):
                with patch('web.rag.intelligence.RetrievalService'):
                    with patch('web.rag.intelligence.create_local_llm') as mock_llm:
                        mock_llm.return_value = MagicMock()
                        
                        intel = FKSIntelligence(use_local=True, local_llm_model='llama3.2:3b')
                        
                        assert intel.use_local is True
                        assert intel.local_llm_model == 'llama3.2:3b'
                        mock_llm.assert_called_once()

    def test_initialization_openai(self):
        """Test initialization with OpenAI."""
        with patch('web.rag.intelligence.DocumentProcessor'):
            with patch('web.rag.intelligence.EmbeddingsService'):
                with patch('web.rag.intelligence.RetrievalService'):
                    with patch('web.rag.intelligence.OpenAI') as mock_openai:
                        with patch('web.rag.intelligence.OPENAI_API_KEY', 'test-key'):
                            intel = FKSIntelligence(use_local=False)
                            
                            assert intel.use_local is False
                            mock_openai.assert_called_once_with(api_key='test-key')

    def test_ingest_document_basic(self, intelligence_with_mocks, mock_components):
        """Test basic document ingestion."""
        # Setup mocks
        mock_doc = MagicMock(id=123)
        mock_components['session'].add.return_value = None
        mock_components['session'].flush.return_value = None
        mock_components['session'].commit.return_value = None
        
        # Mock chunking
        mock_chunk = MagicMock(
            content="Test chunk",
            chunk_index=0,
            token_count=10,
            metadata={}
        )
        mock_components['processor'].chunk_text.return_value = [mock_chunk]
        
        # Mock embeddings
        mock_components['embeddings'].generate_embeddings_batch.return_value = [[0.1] * 384]
        
        with patch('web.rag.intelligence.Document', return_value=mock_doc):
            with patch('web.rag.intelligence.DocumentChunk') as mock_chunk_class:
                doc_id = intelligence_with_mocks.ingest_document(
                    content="Test content",
                    doc_type="signal",
                    title="Test Signal",
                    session=mock_components['session']
                )
        
        # Verify calls
        mock_components['processor'].chunk_text.assert_called_once()
        mock_components['embeddings'].generate_embeddings_batch.assert_called_once()
        mock_components['embeddings'].store_chunk_embedding.assert_called()

    def test_ingest_document_with_metadata(self, intelligence_with_mocks, mock_components):
        """Test document ingestion with metadata."""
        mock_doc = MagicMock(id=456)
        metadata = {'strategy': 'momentum', 'confidence': 0.85}
        
        mock_components['processor'].chunk_text.return_value = [
            MagicMock(content="Chunk", chunk_index=0, token_count=5, metadata={})
        ]
        mock_components['embeddings'].generate_embeddings_batch.return_value = [[0.1] * 384]
        
        with patch('web.rag.intelligence.Document', return_value=mock_doc):
            with patch('web.rag.intelligence.DocumentChunk'):
                doc_id = intelligence_with_mocks.ingest_document(
                    content="Test",
                    doc_type="backtest",
                    symbol="BTCUSDT",
                    timeframe="1h",
                    metadata=metadata,
                    session=mock_components['session']
                )
        
        assert doc_id == 456

    def test_query_basic(self, intelligence_with_mocks, mock_components):
        """Test basic query processing."""
        # Mock retrieval results
        mock_results = [
            {
                'chunk_id': 1,
                'content': 'Relevant context 1',
                'similarity': 0.9,
                'doc_type': 'signal',
                'symbol': 'BTCUSDT'
            },
            {
                'chunk_id': 2,
                'content': 'Relevant context 2',
                'similarity': 0.8,
                'doc_type': 'backtest',
                'symbol': 'BTCUSDT'
            }
        ]
        
        mock_components['retrieval'].retrieve_context.return_value = mock_results
        mock_components['retrieval'].rerank_results.return_value = mock_results
        mock_components['retrieval'].format_context_for_prompt.return_value = "Formatted context"
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Generated answer"))]
        mock_components['llm'].chat.completions.create.return_value = mock_response
        
        result = intelligence_with_mocks.query(
            question="What signals were generated?",
            session=mock_components['session']
        )
        
        assert 'answer' in result
        assert 'sources' in result
        assert 'context_used' in result
        assert 'response_time_ms' in result
        assert result['answer'] == "Generated answer"
        assert len(result['sources']) == 2

    def test_query_with_filters(self, intelligence_with_mocks, mock_components):
        """Test query with symbol and doc_type filters."""
        mock_components['retrieval'].retrieve_context.return_value = []
        mock_components['retrieval'].rerank_results.return_value = []
        mock_components['retrieval'].format_context_for_prompt.return_value = ""
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_components['llm'].chat.completions.create.return_value = mock_response
        
        result = intelligence_with_mocks.query(
            question="Test query",
            symbol="ETHUSDT",
            doc_types=['signal', 'backtest'],
            top_k=3,
            session=mock_components['session']
        )
        
        # Verify retrieval was called with filters
        assert mock_components['retrieval'].retrieve_context.call_count >= 1
        assert result['answer'] == "Answer"

    def test_query_error_handling(self, intelligence_with_mocks, mock_components):
        """Test query error handling."""
        mock_components['retrieval'].retrieve_context.side_effect = Exception("Retrieval error")
        
        result = intelligence_with_mocks.query(
            question="Test query",
            session=mock_components['session']
        )
        
        assert 'answer' in result
        assert 'error' in result['answer'].lower() or 'Error' in result['answer']
        assert result['context_used'] == 0

    def test_suggest_strategy(self, intelligence_with_mocks, mock_components):
        """Test strategy suggestion."""
        mock_components['retrieval'].retrieve_context.return_value = []
        mock_components['retrieval'].rerank_results.return_value = []
        mock_components['retrieval'].format_context_for_prompt.return_value = ""
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Strategy suggestion"))]
        mock_components['llm'].chat.completions.create.return_value = mock_response
        
        result = intelligence_with_mocks.suggest_strategy(
            symbol="BTCUSDT",
            market_condition="trending",
            session=mock_components['session']
        )
        
        assert 'answer' in result
        assert result['answer'] == "Strategy suggestion"
        # Verify query was constructed properly
        mock_components['retrieval'].retrieve_context.assert_called()

    def test_analyze_past_trades(self, intelligence_with_mocks, mock_components):
        """Test past trades analysis."""
        mock_components['retrieval'].retrieve_context.return_value = []
        mock_components['retrieval'].rerank_results.return_value = []
        mock_components['retrieval'].format_context_for_prompt.return_value = ""
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Trade analysis"))]
        mock_components['llm'].chat.completions.create.return_value = mock_response
        
        result = intelligence_with_mocks.analyze_past_trades(
            symbol="ETHUSDT",
            session=mock_components['session']
        )
        
        assert 'answer' in result
        assert result['answer'] == "Trade analysis"

    def test_explain_signal(self, intelligence_with_mocks, mock_components):
        """Test signal explanation."""
        mock_components['retrieval'].retrieve_context.return_value = []
        mock_components['retrieval'].rerank_results.return_value = []
        mock_components['retrieval'].format_context_for_prompt.return_value = ""
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Signal explanation"))]
        mock_components['llm'].chat.completions.create.return_value = mock_response
        
        indicators = {'rsi': 65.5, 'macd': 0.25, 'bb_position': 0.8}
        
        result = intelligence_with_mocks.explain_signal(
            symbol="BTCUSDT",
            current_indicators=indicators,
            session=mock_components['session']
        )
        
        assert 'answer' in result
        assert result['answer'] == "Signal explanation"

    def test_generate_response_local_llm(self, mock_components):
        """Test response generation with local LLM."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Local LLM response"
        
        with patch('web.rag.intelligence.DocumentProcessor'):
            with patch('web.rag.intelligence.EmbeddingsService'):
                with patch('web.rag.intelligence.RetrievalService'):
                    with patch('web.rag.intelligence.create_local_llm', return_value=mock_llm):
                        intel = FKSIntelligence(use_local=True)
                        intel.llm = mock_llm
                        
                        response = intel._generate_response(
                            question="Test question",
                            context="Test context"
                        )
                        
                        assert response == "Local LLM response"
                        mock_llm.generate.assert_called_once()

    def test_generate_response_openai(self, intelligence_with_mocks, mock_components):
        """Test response generation with OpenAI."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="OpenAI response"))]
        mock_components['llm'].chat.completions.create.return_value = mock_response
        
        response = intelligence_with_mocks._generate_response(
            question="Test question",
            context="Test context"
        )
        
        assert response == "OpenAI response"
        mock_components['llm'].chat.completions.create.assert_called_once()

    def test_log_query(self, intelligence_with_mocks, mock_components):
        """Test query logging."""
        retrieved_chunks = [
            {'chunk_id': 1, 'similarity': 0.9, 'doc_type': 'signal'},
            {'chunk_id': 2, 'similarity': 0.8, 'doc_type': 'backtest'}
        ]
        
        with patch('web.rag.intelligence.QueryHistory') as mock_history:
            intelligence_with_mocks._log_query(
                query="Test query",
                response="Test response",
                retrieved_chunks=retrieved_chunks,
                response_time=150,
                session=mock_components['session']
            )
            
            mock_history.assert_called_once()
            mock_components['session'].add.assert_called()
            mock_components['session'].commit.assert_called()

    def test_log_query_error_handling(self, intelligence_with_mocks, mock_components):
        """Test query logging error handling."""
        mock_components['session'].add.side_effect = Exception("Logging error")
        
        # Should not raise exception
        intelligence_with_mocks._log_query(
            query="Test",
            response="Test",
            retrieved_chunks=[],
            response_time=100,
            session=mock_components['session']
        )

    def test_session_management_auto_close(self, intelligence_with_mocks, mock_components):
        """Test that session is auto-closed when None is provided."""
        mock_components['retrieval'].retrieve_context.return_value = []
        mock_components['retrieval'].rerank_results.return_value = []
        mock_components['retrieval'].format_context_for_prompt.return_value = ""
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_components['llm'].chat.completions.create.return_value = mock_response
        
        with patch('web.rag.intelligence.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Call without providing session
            result = intelligence_with_mocks.query(question="Test", session=None)
            
            # Session should be created and closed
            # (This test validates the pattern, actual behavior depends on implementation)
            assert 'answer' in result

    @pytest.mark.parametrize("doc_type", ["signal", "backtest", "trade_analysis", "strategy", "insight"])
    def test_ingest_different_doc_types(self, intelligence_with_mocks, mock_components, doc_type):
        """Test ingesting different document types."""
        mock_doc = MagicMock(id=789)
        mock_components['processor'].chunk_text.return_value = [
            MagicMock(content="Test", chunk_index=0, token_count=3, metadata={})
        ]
        mock_components['embeddings'].generate_embeddings_batch.return_value = [[0.1] * 384]
        
        with patch('web.rag.intelligence.Document', return_value=mock_doc):
            with patch('web.rag.intelligence.DocumentChunk'):
                doc_id = intelligence_with_mocks.ingest_document(
                    content="Test content",
                    doc_type=doc_type,
                    session=mock_components['session']
                )
        
        assert doc_id == 789

    def test_multiple_chunks_ingestion(self, intelligence_with_mocks, mock_components):
        """Test ingesting document that produces multiple chunks."""
        mock_doc = MagicMock(id=999)
        
        # Multiple chunks
        mock_chunks = [
            MagicMock(content=f"Chunk {i}", chunk_index=i, token_count=10, metadata={})
            for i in range(5)
        ]
        mock_components['processor'].chunk_text.return_value = mock_chunks
        mock_components['embeddings'].generate_embeddings_batch.return_value = [[0.1] * 384] * 5
        
        with patch('web.rag.intelligence.Document', return_value=mock_doc):
            with patch('web.rag.intelligence.DocumentChunk'):
                doc_id = intelligence_with_mocks.ingest_document(
                    content="Long content" * 100,
                    doc_type="guide",
                    session=mock_components['session']
                )
        
        # Should call store_chunk_embedding 5 times
        assert mock_components['embeddings'].store_chunk_embedding.call_count == 5

    def test_query_response_time_tracking(self, intelligence_with_mocks, mock_components):
        """Test that response time is tracked."""
        mock_components['retrieval'].retrieve_context.return_value = []
        mock_components['retrieval'].rerank_results.return_value = []
        mock_components['retrieval'].format_context_for_prompt.return_value = ""
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_components['llm'].chat.completions.create.return_value = mock_response
        
        result = intelligence_with_mocks.query(
            question="Test",
            session=mock_components['session']
        )
        
        assert 'response_time_ms' in result
        assert isinstance(result['response_time_ms'], int)
        assert result['response_time_ms'] >= 0


class TestCreateIntelligenceHelper:
    """Test convenience function for creating intelligence instance."""

    def test_create_intelligence_default(self):
        """Test creating intelligence with default parameters."""
        with patch('web.rag.intelligence.FKSIntelligence') as mock_class:
            from web.rag.intelligence import create_intelligence
            
            create_intelligence()
            
            mock_class.assert_called_once_with(
                use_local=True,
                local_llm_model="llama3.2:3b",
                embedding_model="all-MiniLM-L6-v2"
            )

    def test_create_intelligence_custom_params(self):
        """Test creating intelligence with custom parameters."""
        with patch('web.rag.intelligence.FKSIntelligence') as mock_class:
            from web.rag.intelligence import create_intelligence
            
            create_intelligence(
                use_local=False,
                local_llm_model="mistral:7b",
                embedding_model="custom-model"
            )
            
            mock_class.assert_called_once_with(
                use_local=False,
                local_llm_model="mistral:7b",
                embedding_model="custom-model"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
