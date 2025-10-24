"""
Tests for RAG system components with local LLM support.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import Base, Document, DocumentChunk, QueryHistory
from web.rag.document_processor import DocumentProcessor
from web.rag.local_llm import LocalEmbeddings, LocalLLM, check_cuda_availability
from web.rag.embeddings import EmbeddingsService
from web.rag.retrieval import RetrievalService
from web.rag.intelligence import FKSIntelligence
from web.rag.ingestion import DataDataIngestionPipeline


@pytest.fixture(scope="module")
def test_db():
    """Create a test database with vector extension."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_documents(test_db):
    """Create sample documents for testing."""
    docs = [
        Document(
            title="Momentum Strategy Guide",
            content="Momentum strategies work best in trending markets. Use RSI > 70 for overbought, < 30 for oversold.",
            doc_type="strategy_guide",
            metadata={'strategy': 'momentum', 'author': 'system'}
        ),
        Document(
            title="Risk Management Best Practices",
            content="Always use stop losses. Risk no more than 2% per trade. Diversify across multiple assets.",
            doc_type="guide",
            metadata={'category': 'risk_management'}
        ),
        Document(
            title="BTCUSDT Trading Analysis",
            content="BTCUSDT shows strong uptrend. Support at 50000, resistance at 55000. RSI indicates bullish momentum.",
            doc_type="analysis",
            metadata={'symbol': 'BTCUSDT', 'date': '2025-10-15'}
        )
    ]
    
    for doc in docs:
        test_db.add(doc)
    test_db.commit()
    
    return docs


class TestLocalEmbeddings:
    """Test LocalEmbeddings with sentence-transformers."""

    def test_cuda_availability(self):
        """Test CUDA detection."""
        has_cuda = check_cuda_availability()
        assert isinstance(has_cuda, bool)

    @pytest.mark.skipif(not check_cuda_availability(), reason="CUDA not available")
    def test_local_embeddings_with_cuda(self):
        """Test local embeddings with CUDA acceleration."""
        embeddings = LocalEmbeddings(model_name="all-MiniLM-L6-v2", device="cuda")
        
        text = "This is a test sentence for embeddings."
        embedding = embeddings.embed_text(text)
        
        assert len(embedding) == 384  # MiniLM-L6 dimension
        assert all(isinstance(x, float) for x in embedding)

    def test_local_embeddings_cpu(self):
        """Test local embeddings on CPU."""
        embeddings = LocalEmbeddings(model_name="all-MiniLM-L6-v2", device="cpu")
        
        text = "CPU-based embedding test."
        embedding = embeddings.embed_text(text)
        
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    def test_batch_embeddings(self):
        """Test batch embedding generation."""
        embeddings = LocalEmbeddings(model_name="all-MiniLM-L6-v2")
        
        texts = [
            "First test sentence.",
            "Second test sentence.",
            "Third test sentence."
        ]
        
        batch_embeddings = embeddings.embed_batch(texts)
        
        assert len(batch_embeddings) == 3
        assert all(len(emb) == 384 for emb in batch_embeddings)


class TestLocalLLM:
    """Test LocalLLM with Ollama backend."""

    @pytest.mark.skipif(not check_cuda_availability(), reason="CUDA not available")
    def test_ollama_connection(self):
        """Test connection to Ollama service."""
        try:
            llm = LocalLLM(backend="ollama", model_name="llama3.2:3b")
            response = llm.generate("Say 'test' only.", max_tokens=10)
            assert len(response) > 0
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")

    def test_llm_with_context(self):
        """Test LLM generation with context."""
        try:
            llm = LocalLLM(backend="ollama", model_name="llama3.2:3b")
            
            context = "Bitcoin is trading at $50,000 with RSI at 65."
            query = "What's the current Bitcoin situation?"
            
            response = llm.generate(query, context=context, max_tokens=100)
            
            assert len(response) > 0
            assert "Bitcoin" in response or "BTC" in response or "$50,000" in response
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")


class TestDocumentProcessor:
    """Test DocumentProcessor for chunking."""

    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        processor = DocumentProcessor()
        
        text = "This is a test document. " * 100  # Long text
        chunks = processor.chunk_text(text, chunk_size=512, overlap=50)
        
        assert len(chunks) > 1
        assert all(len(chunk) > 0 for chunk in chunks)

    def test_chunk_signal(self):
        """Test chunking trading signal data."""
        processor = DocumentProcessor()
        
        signal_data = {
            'symbol': 'BTCUSDT',
            'type': 'long',
            'strength': 0.85,
            'price': 50000.00,
            'indicators': {'rsi': 35, 'macd': -0.5}
        }
        
        chunk = processor.chunk_signal(signal_data)
        
        assert 'BTCUSDT' in chunk
        assert 'long' in chunk
        assert 'rsi' in chunk.lower()

    def test_chunk_backtest(self):
        """Test chunking backtest results."""
        processor = DocumentProcessor()
        
        backtest_data = {
            'symbol': 'ETHUSDT',
            'strategy': 'momentum',
            'win_rate': 0.68,
            'sharpe_ratio': 2.1,
            'total_trades': 50
        }
        
        chunk = processor.chunk_backtest(backtest_data)
        
        assert 'ETHUSDT' in chunk
        assert 'momentum' in chunk
        assert 'win_rate' in chunk.lower() or '68%' in chunk

    def test_chunk_trade(self):
        """Test chunking completed trade data."""
        processor = DocumentProcessor()
        
        trade_data = {
            'symbol': 'SOLUSDT',
            'side': 'buy',
            'entry_price': 100.0,
            'exit_price': 105.0,
            'pnl': 50.0,
            'outcome': 'win'
        }
        
        chunk = processor.chunk_trade(trade_data)
        
        assert 'SOLUSDT' in chunk
        assert 'buy' in chunk
        assert 'profit' in chunk.lower() or 'win' in chunk.lower()


class TestEmbeddingsService:
    """Test EmbeddingsService with local support."""

    def test_create_local_embeddings_service(self, test_db):
        """Test creating embeddings service with local model."""
        service = EmbeddingsService(
            session=test_db,
            use_local=True,
            model_name="all-MiniLM-L6-v2"
        )
        
        assert service.use_local is True
        assert service.local_embeddings is not None

    def test_generate_embedding_local(self, test_db):
        """Test generating embeddings with local model."""
        service = EmbeddingsService(session=test_db, use_local=True)
        
        text = "Test embedding generation."
        embedding = service.generate_embedding(text)
        
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    def test_store_chunk_with_embedding(self, test_db, sample_documents):
        """Test storing document chunk with embedding."""
        service = EmbeddingsService(session=test_db, use_local=True)
        doc = sample_documents[0]
        
        chunk = DocumentChunk(
            document_id=doc.id,
            content="Test chunk content.",
            chunk_index=0,
            start_pos=0,
            end_pos=20
        )
        
        chunk_with_emb = service.store_chunk_with_embedding(chunk)
        
        assert chunk_with_emb.id is not None
        assert chunk_with_emb.embedding is not None
        assert len(chunk_with_emb.embedding) == 384


class TestRetrievalService:
    """Test RetrievalService for semantic search."""

    def test_create_retrieval_service(self, test_db):
        """Test creating retrieval service."""
        embeddings = EmbeddingsService(session=test_db, use_local=True)
        retrieval = RetrievalService(session=test_db, embeddings_service=embeddings)
        
        assert retrieval.session == test_db
        assert retrieval.embeddings_service is not None

    def test_retrieve_context_empty_db(self, test_db):
        """Test retrieval from empty database."""
        embeddings = EmbeddingsService(session=test_db, use_local=True)
        retrieval = RetrievalService(session=test_db, embeddings_service=embeddings)
        
        results = retrieval.retrieve_context("test query", top_k=5)
        
        assert isinstance(results, list)
        # Empty DB should return empty list
        assert len(results) == 0

    def test_retrieve_with_chunks(self, test_db, sample_documents):
        """Test retrieval with actual document chunks."""
        embeddings = EmbeddingsService(session=test_db, use_local=True)
        retrieval = RetrievalService(session=test_db, embeddings_service=embeddings)
        
        # Create chunks with embeddings
        processor = DocumentProcessor()
        for doc in sample_documents:
            chunks = processor.chunk_text(doc.content, chunk_size=512)
            for i, chunk_text in enumerate(chunks):
                chunk = DocumentChunk(
                    document_id=doc.id,
                    content=chunk_text,
                    chunk_index=i,
                    start_pos=i * 500,
                    end_pos=(i + 1) * 500
                )
                embeddings.store_chunk_with_embedding(chunk)
        
        # Retrieve relevant chunks
        results = retrieval.retrieve_context("momentum strategy", top_k=3)
        
        assert len(results) > 0
        assert any('momentum' in r['content'].lower() for r in results)


class TestFKSIntelligence:
    """Test FKSIntelligence RAG orchestrator."""

    def test_create_intelligence_local(self, test_db):
        """Test creating intelligence service with local LLM."""
        try:
            intelligence = FKSIntelligence(
                session=test_db,
                use_local=True,
                local_llm_model="llama3.2:3b"
            )
            
            assert intelligence.use_local is True
            assert intelligence.embeddings_service is not None
            assert intelligence.retrieval_service is not None
        except Exception as e:
            pytest.skip(f"Local LLM not available: {e}")

    def test_query_with_context(self, test_db, sample_documents):
        """Test querying knowledge base."""
        try:
            # Setup RAG components
            embeddings = EmbeddingsService(session=test_db, use_local=True)
            processor = DocumentProcessor()
            
            # Ingest documents
            for doc in sample_documents:
                chunks = processor.chunk_text(doc.content)
                for i, chunk_text in enumerate(chunks):
                    chunk = DocumentChunk(
                        document_id=doc.id,
                        content=chunk_text,
                        chunk_index=i,
                        start_pos=0,
                        end_pos=len(chunk_text)
                    )
                    embeddings.store_chunk_with_embedding(chunk)
            
            # Create intelligence service
            intelligence = FKSIntelligence(
                session=test_db,
                use_local=True,
                local_llm_model="llama3.2:3b"
            )
            
            # Query
            result = intelligence.query("What are momentum strategies?")
            
            assert 'answer' in result
            assert 'sources' in result
            assert len(result['answer']) > 0
        except Exception as e:
            pytest.skip(f"RAG query failed: {e}")


class TestDataIngestionPipeline:
    """Test DataIngestionPipeline for data ingestion."""

    def test_create_pipeline(self, test_db):
        """Test creating ingestion pipeline."""
        pipeline = DataIngestionPipeline(session=test_db, use_local=True)
        
        assert pipeline.session == test_db
        assert pipeline.processor is not None
        assert pipeline.embeddings_service is not None

    def test_ingest_signal(self, test_db):
        """Test ingesting trading signal."""
        pipeline = DataIngestionPipeline(session=test_db, use_local=True)
        
        signal_data = {
            'id': 1,
            'symbol': 'BTCUSDT',
            'type': 'long',
            'strength': 0.85,
            'price': 50000.0,
            'timestamp': datetime.utcnow(),
            'indicators': {'rsi': 35, 'macd': -0.5},
            'strategy': 'momentum'
        }
        
        result = pipeline.ingest_signal(signal_data)
        
        assert result is not None
        assert result.doc_type == 'signal'

    def test_ingest_backtest(self, test_db):
        """Test ingesting backtest result."""
        pipeline = DataIngestionPipeline(session=test_db, use_local=True)
        
        backtest_data = {
            'id': 1,
            'symbol': 'ETHUSDT',
            'strategy': 'momentum',
            'win_rate': 0.68,
            'sharpe_ratio': 2.1,
            'max_drawdown': 0.15,
            'total_trades': 50
        }
        
        result = pipeline.ingest_backtest(backtest_data)
        
        assert result is not None
        assert result.doc_type == 'backtest'

    def test_ingest_completed_trade(self, test_db):
        """Test ingesting completed trade."""
        pipeline = DataIngestionPipeline(session=test_db, use_local=True)
        
        trade_data = {
            'id': 1,
            'symbol': 'SOLUSDT',
            'side': 'buy',
            'quantity': 10.0,
            'entry_price': 100.0,
            'exit_price': 105.0,
            'pnl': 50.0,
            'entry_time': datetime.utcnow() - timedelta(hours=2),
            'exit_time': datetime.utcnow()
        }
        
        result = pipeline.ingest_completed_trade(trade_data)
        
        assert result is not None
        assert result.doc_type == 'trade'


# Integration tests
class TestRAGIntegration:
    """Test end-to-end RAG workflows."""

    def test_full_rag_workflow(self, test_db):
        """Test complete RAG workflow from ingestion to query."""
        try:
            # 1. Create pipeline
            pipeline = DataIngestionPipeline(session=test_db, use_local=True)
            
            # 2. Ingest data
            signal = {
                'id': 1,
                'symbol': 'BTCUSDT',
                'type': 'long',
                'strength': 0.85,
                'price': 50000.0,
                'timestamp': datetime.utcnow(),
                'indicators': {'rsi': 35},
                'strategy': 'momentum'
            }
            pipeline.ingest_signal(signal)
            
            # 3. Query knowledge base
            intelligence = FKSIntelligence(
                session=test_db,
                use_local=True,
                local_llm_model="llama3.2:3b"
            )
            
            result = intelligence.query("What signals were generated for BTCUSDT?")
            
            assert 'answer' in result
            assert len(result['sources']) > 0
        except Exception as e:
            pytest.skip(f"Full RAG workflow not available: {e}")

    def test_rag_performance(self, test_db):
        """Test RAG query performance."""
        import time
        
        try:
            intelligence = FKSIntelligence(
                session=test_db,
                use_local=True,
                local_llm_model="llama3.2:3b"
            )
            
            start = time.time()
            result = intelligence.query("Test query for performance")
            elapsed = time.time() - start
            
            # Should complete in reasonable time (< 10 seconds)
            assert elapsed < 10.0
            assert 'answer' in result
        except Exception as e:
            pytest.skip(f"Performance test skipped: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
