"""
Performance tests for RAG system using pytest-benchmark.
Benchmarks critical paths for embeddings, retrieval, and query processing.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from web.rag.document_processor import DocumentProcessor
from web.rag.embeddings import EmbeddingsService
from web.rag.retrieval import RetrievalService


@pytest.mark.benchmark
class TestDocumentProcessorPerformance:
    """Benchmark document processor operations."""

    @pytest.fixture
    def processor(self):
        return DocumentProcessor()

    @pytest.fixture
    def sample_text(self):
        """Generate sample text for benchmarking."""
        return "This is a sample sentence for testing. " * 100

    @pytest.fixture
    def large_text(self):
        """Generate large text for benchmarking."""
        return "Testing performance with longer content. " * 1000

    def test_chunk_text_performance(self, benchmark, processor, sample_text):
        """Benchmark text chunking performance."""
        result = benchmark(processor.chunk_text, sample_text, chunk_size=500, overlap=50)
        
        assert len(result) > 0
        # Log performance metrics
        stats = benchmark.stats.stats
        print(f"\nChunking stats: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_chunk_text_large_performance(self, benchmark, processor, large_text):
        """Benchmark chunking large text."""
        result = benchmark(processor.chunk_text, large_text, chunk_size=1000, overlap=100)
        
        assert len(result) > 0
        stats = benchmark.stats.stats
        print(f"\nLarge text chunking: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_chunk_signal_performance(self, benchmark, processor):
        """Benchmark signal formatting performance."""
        signal_data = {
            'id': 1,
            'symbol': 'BTCUSDT',
            'type': 'LONG',
            'strength': 0.85,
            'price': 50000.0,
            'indicators': {'rsi': 35, 'macd': -0.5, 'bb_position': 0.2},
            'strategy': 'momentum'
        }
        
        result = benchmark(processor.chunk_signal, signal_data)
        
        assert len(result) > 0
        stats = benchmark.stats.stats
        print(f"\nSignal formatting: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_chunk_backtest_performance(self, benchmark, processor):
        """Benchmark backtest formatting performance."""
        backtest_data = {
            'symbol': 'BTCUSDT',
            'strategy': 'momentum',
            'win_rate': 0.68,
            'sharpe_ratio': 2.1,
            'max_drawdown': 0.15,
            'total_trades': 50,
            'total_return': 0.35
        }
        
        result = benchmark(processor.chunk_backtest, backtest_data)
        
        assert len(result) > 0
        stats = benchmark.stats.stats
        print(f"\nBacktest formatting: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_chunk_trade_performance(self, benchmark, processor):
        """Benchmark trade formatting performance."""
        from datetime import datetime
        
        trade_data = {
            'symbol': 'ETHUSDT',
            'side': 'BUY',
            'quantity': 5.0,
            'entry_price': 2000.0,
            'exit_price': 2100.0,
            'pnl': 500.0,
            'entry_time': datetime(2025, 10, 18, 10, 0, 0),
            'exit_time': datetime(2025, 10, 18, 14, 0, 0)
        }
        
        result = benchmark(processor.chunk_trade, trade_data)
        
        assert len(result) > 0
        stats = benchmark.stats.stats
        print(f"\nTrade formatting: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")


@pytest.mark.benchmark
class TestEmbeddingsServicePerformance:
    """Benchmark embeddings service operations."""

    @pytest.fixture
    def mock_local_embeddings(self):
        """Create mock embeddings for benchmarking."""
        mock = MagicMock()
        mock.embed_text.return_value = np.random.rand(384).tolist()
        mock.embed_batch.return_value = [np.random.rand(384).tolist() for _ in range(10)]
        return mock

    @pytest.fixture
    def service_with_mocks(self, mock_local_embeddings):
        """Create service with mocks for benchmarking."""
        with patch('web.rag.embeddings.LocalEmbeddings', return_value=mock_local_embeddings):
            service = EmbeddingsService(use_local=True)
            service.local_embeddings = mock_local_embeddings
            return service

    def test_generate_embedding_performance(self, benchmark, service_with_mocks):
        """Benchmark single embedding generation."""
        text = "Performance test for embedding generation with reasonable length text."
        
        result = benchmark(service_with_mocks.generate_embedding, text)
        
        assert len(result) == 384
        stats = benchmark.stats.stats
        print(f"\nEmbedding generation: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_batch_embedding_performance(self, benchmark, service_with_mocks, mock_local_embeddings):
        """Benchmark batch embedding generation."""
        texts = [f"Batch text number {i} for performance testing." for i in range(10)]
        
        result = benchmark(service_with_mocks.generate_embeddings_batch, texts)
        
        assert len(result) == 10
        stats = benchmark.stats.stats
        print(f"\nBatch embeddings (10): mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_large_batch_embedding_performance(self, benchmark, service_with_mocks, mock_local_embeddings):
        """Benchmark large batch embedding generation."""
        texts = [f"Batch text {i}" for i in range(100)]
        mock_local_embeddings.embed_batch.return_value = [np.random.rand(384).tolist() for _ in range(100)]
        
        result = benchmark(service_with_mocks.generate_embeddings_batch, texts)
        
        assert len(result) == 100
        stats = benchmark.stats.stats
        print(f"\nBatch embeddings (100): mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_cosine_similarity_performance(self, benchmark, service_with_mocks):
        """Benchmark cosine similarity calculation."""
        vec1 = np.random.rand(384).tolist()
        vec2 = np.random.rand(384).tolist()
        
        result = benchmark(service_with_mocks._cosine_similarity, vec1, vec2)
        
        assert isinstance(result, float)
        stats = benchmark.stats.stats
        print(f"\nCosine similarity: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")


@pytest.mark.benchmark
class TestRetrievalServicePerformance:
    """Benchmark retrieval service operations."""

    @pytest.fixture
    def mock_embeddings_service(self):
        """Create mock embeddings service."""
        mock = MagicMock()
        mock.generate_embedding.return_value = np.random.rand(384).tolist()
        mock.semantic_search.return_value = [
            {
                'chunk_id': i,
                'content': f'Test content {i}',
                'similarity': 0.9 - (i * 0.05),
                'doc_type': 'signal',
                'symbol': 'BTCUSDT'
            }
            for i in range(10)
        ]
        return mock

    @pytest.fixture
    def retrieval_service(self, mock_embeddings_service):
        """Create retrieval service with mocks."""
        return RetrievalService(embeddings_service=mock_embeddings_service)

    def test_retrieve_context_performance(self, benchmark, retrieval_service):
        """Benchmark context retrieval."""
        query = "What trading signals were generated for BTCUSDT?"
        
        result = benchmark(
            retrieval_service.retrieve_context,
            query=query,
            top_k=5
        )
        
        assert isinstance(result, list)
        stats = benchmark.stats.stats
        print(f"\nContext retrieval: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_rerank_results_performance(self, benchmark, retrieval_service):
        """Benchmark result re-ranking."""
        query = "Test query"
        results = [
            {
                'chunk_id': i,
                'content': f'Content {i}',
                'similarity': 0.9 - (i * 0.05),
                'created_at': '2025-10-18T12:00:00'
            }
            for i in range(20)
        ]
        
        reranked = benchmark(
            retrieval_service.rerank_results,
            query=query,
            results=results,
            method='hybrid'
        )
        
        assert len(reranked) > 0
        stats = benchmark.stats.stats
        print(f"\nResult re-ranking: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_format_context_performance(self, benchmark, retrieval_service):
        """Benchmark context formatting."""
        results = [
            {
                'chunk_id': i,
                'content': f'Test content number {i} with more details for formatting.',
                'similarity': 0.9 - (i * 0.05),
                'doc_type': 'signal',
                'symbol': 'BTCUSDT'
            }
            for i in range(10)
        ]
        
        formatted = benchmark(
            retrieval_service.format_context_for_prompt,
            results=results,
            max_tokens=4000
        )
        
        assert len(formatted) > 0
        stats = benchmark.stats.stats
        print(f"\nContext formatting: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")


@pytest.mark.benchmark
class TestEndToEndRAGPerformance:
    """Benchmark end-to-end RAG operations."""

    @pytest.fixture
    def mock_components(self):
        """Create all mocked components for E2E testing."""
        processor = DocumentProcessor()
        
        embeddings_mock = MagicMock()
        embeddings_mock.generate_embedding.return_value = np.random.rand(384).tolist()
        embeddings_mock.generate_embeddings_batch.return_value = [
            np.random.rand(384).tolist() for _ in range(5)
        ]
        embeddings_mock.semantic_search.return_value = [
            {
                'chunk_id': i,
                'content': f'Relevant context {i}',
                'similarity': 0.9,
                'doc_type': 'signal'
            }
            for i in range(5)
        ]
        
        retrieval_mock = RetrievalService(embeddings_service=embeddings_mock)
        
        return {
            'processor': processor,
            'embeddings': embeddings_mock,
            'retrieval': retrieval_mock
        }

    def test_document_ingestion_pipeline_performance(self, benchmark, mock_components):
        """Benchmark full document ingestion pipeline."""
        content = "Test trading signal for BTCUSDT with momentum strategy. " * 10
        
        def ingest_pipeline():
            # Chunk
            chunks = mock_components['processor'].chunk_text(content)
            
            # Generate embeddings
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = mock_components['embeddings'].generate_embeddings_batch(chunk_texts)
            
            return len(embeddings)
        
        result = benchmark(ingest_pipeline)
        
        assert result > 0
        stats = benchmark.stats.stats
        print(f"\nIngestion pipeline: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")

    def test_query_pipeline_performance(self, benchmark, mock_components):
        """Benchmark full query pipeline."""
        query = "What are the best trading signals for BTCUSDT?"
        
        def query_pipeline():
            # Generate query embedding
            query_emb = mock_components['embeddings'].generate_embedding(query)
            
            # Retrieve context
            results = mock_components['retrieval'].retrieve_context(query, top_k=5)
            
            # Rerank
            reranked = mock_components['retrieval'].rerank_results(query, results, method='hybrid')
            
            # Format context
            context = mock_components['retrieval'].format_context_for_prompt(reranked)
            
            return len(context)
        
        result = benchmark(query_pipeline)
        
        assert result > 0
        stats = benchmark.stats.stats
        print(f"\nQuery pipeline: mean={stats.mean:.4f}s, stddev={stats.stddev:.4f}s")


@pytest.mark.benchmark
class TestScalabilityBenchmarks:
    """Test performance at different scales."""

    @pytest.fixture
    def processor(self):
        return DocumentProcessor()

    @pytest.mark.parametrize("text_multiplier", [10, 50, 100, 500])
    def test_chunking_scalability(self, benchmark, processor, text_multiplier):
        """Test chunking performance at different text sizes."""
        text = "Sample text for scalability testing. " * text_multiplier
        
        result = benchmark(processor.chunk_text, text, chunk_size=500, overlap=50)
        
        assert len(result) > 0
        print(f"\nText size: {len(text)} chars, chunks: {len(result)}")

    @pytest.mark.parametrize("batch_size", [1, 10, 50, 100])
    def test_batch_embedding_scalability(self, benchmark, batch_size):
        """Test batch embedding performance at different sizes."""
        mock = MagicMock()
        mock.embed_batch.return_value = [np.random.rand(384).tolist() for _ in range(batch_size)]
        
        with patch('web.rag.embeddings.LocalEmbeddings', return_value=mock):
            service = EmbeddingsService(use_local=True)
            service.local_embeddings = mock
            
            texts = [f"Text {i}" for i in range(batch_size)]
            result = benchmark(service.generate_embeddings_batch, texts)
            
            assert len(result) == batch_size
            print(f"\nBatch size: {batch_size}, time per item: {benchmark.stats.stats.mean/batch_size:.6f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "benchmark", "--benchmark-only"])
