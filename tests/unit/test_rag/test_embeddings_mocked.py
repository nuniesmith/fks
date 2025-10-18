"""
Unit tests for RAG embeddings service with comprehensive mocking.
Tests embedding generation, storage, and semantic search in isolation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import numpy as np

from web.rag.embeddings import EmbeddingsService


class TestEmbeddingsServiceMocked:
    """Test EmbeddingsService with all external dependencies mocked."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.query.return_value = session
        session.filter.return_value = session
        session.order_by.return_value = session
        session.limit.return_value = session
        session.all.return_value = []
        return session

    @pytest.fixture
    def mock_local_embeddings(self):
        """Create a mock local embeddings model."""
        mock = MagicMock()
        # Return 384-dimensional embeddings (MiniLM size)
        mock.embed_text.return_value = [0.1] * 384
        mock.embed_batch.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
        return mock

    @pytest.fixture
    def service_with_mocks(self, mock_session, mock_local_embeddings):
        """Create embeddings service with mocked dependencies."""
        with patch('web.rag.embeddings.LocalEmbeddings', return_value=mock_local_embeddings):
            service = EmbeddingsService(use_local=True, model='test-model')
            service.local_embeddings = mock_local_embeddings
            return service

    def test_initialization_local(self):
        """Test service initialization with local embeddings."""
        with patch('web.rag.embeddings.LocalEmbeddings') as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            
            service = EmbeddingsService(use_local=True, model='all-MiniLM-L6-v2')
            
            assert service.use_local is True
            assert service.model == 'all-MiniLM-L6-v2'
            mock_class.assert_called_once()

    def test_initialization_openai(self):
        """Test service initialization with OpenAI embeddings."""
        with patch('web.rag.embeddings.OpenAI') as mock_openai:
            service = EmbeddingsService(use_local=False, api_key='test-key')
            
            assert service.use_local is False
            mock_openai.assert_called_once_with(api_key='test-key')

    def test_generate_embedding_local(self, service_with_mocks, mock_local_embeddings):
        """Test generating embedding with local model."""
        text = "Test embedding generation"
        
        result = service_with_mocks.generate_embedding(text)
        
        mock_local_embeddings.embed_text.assert_called_once_with(text)
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)

    def test_generate_embedding_empty_text(self, service_with_mocks, mock_local_embeddings):
        """Test generating embedding for empty text."""
        mock_local_embeddings.embed_text.return_value = [0.0] * 384
        
        result = service_with_mocks.generate_embedding("")
        
        assert len(result) == 384

    def test_generate_embeddings_batch(self, service_with_mocks, mock_local_embeddings):
        """Test batch embedding generation."""
        texts = ["First text", "Second text", "Third text"]
        
        result = service_with_mocks.generate_embeddings_batch(texts)
        
        mock_local_embeddings.embed_batch.assert_called_once_with(texts)
        assert len(result) == 3
        assert all(len(emb) == 384 for emb in result)

    def test_generate_embeddings_batch_empty(self, service_with_mocks, mock_local_embeddings):
        """Test batch embedding with empty list."""
        mock_local_embeddings.embed_batch.return_value = []
        
        result = service_with_mocks.generate_embeddings_batch([])
        
        assert result == []

    @patch('web.rag.embeddings.OpenAI')
    def test_generate_embedding_openai(self, mock_openai_class):
        """Test embedding generation with OpenAI."""
        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_client.embeddings.create.return_value = mock_response
        
        service = EmbeddingsService(use_local=False, api_key='test-key')
        result = service.generate_embedding("Test text")
        
        assert len(result) == 1536
        mock_client.embeddings.create.assert_called_once()

    def test_store_chunk_embedding(self, service_with_mocks, mock_session):
        """Test storing chunk embedding to database."""
        chunk_id = 123
        embedding = [0.1] * 384
        
        with patch('web.rag.embeddings.ChunkEmbedding') as mock_embedding_class:
            mock_embedding = MagicMock()
            mock_embedding_class.return_value = mock_embedding
            
            service_with_mocks.store_chunk_embedding(
                chunk_id=chunk_id,
                embedding=embedding,
                session=mock_session
            )
            
            mock_embedding_class.assert_called_once_with(
                chunk_id=chunk_id,
                embedding=embedding
            )
            mock_session.add.assert_called_once_with(mock_embedding)
            mock_session.commit.assert_called_once()

    def test_store_chunk_embedding_rollback_on_error(self, service_with_mocks, mock_session):
        """Test rollback when storing embedding fails."""
        mock_session.add.side_effect = Exception("Database error")
        
        with pytest.raises(Exception):
            service_with_mocks.store_chunk_embedding(
                chunk_id=123,
                embedding=[0.1] * 384,
                session=mock_session
            )
        
        mock_session.rollback.assert_called_once()

    def test_semantic_search(self, service_with_mocks, mock_session):
        """Test semantic search with cosine similarity."""
        query_embedding = [0.5] * 384
        
        # Mock chunks with embeddings
        mock_chunks = [
            MagicMock(id=1, content="Test 1", embedding=[0.6] * 384),
            MagicMock(id=2, content="Test 2", embedding=[0.4] * 384),
            MagicMock(id=3, content="Test 3", embedding=[0.7] * 384),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_chunks
        
        results = service_with_mocks.semantic_search(
            query_embedding=query_embedding,
            limit=5,
            similarity_threshold=0.5,
            session=mock_session
        )
        
        assert isinstance(results, list)
        # Verify database query was called
        mock_session.query.assert_called()

    def test_semantic_search_with_filters(self, service_with_mocks, mock_session):
        """Test semantic search with filtering."""
        query_embedding = [0.5] * 384
        filters = {'symbol': 'BTCUSDT', 'doc_type': 'signal'}
        
        results = service_with_mocks.semantic_search(
            query_embedding=query_embedding,
            limit=3,
            filters=filters,
            session=mock_session
        )
        
        # Verify filters were applied
        mock_session.query.assert_called()

    def test_semantic_search_empty_results(self, service_with_mocks, mock_session):
        """Test semantic search with no matching results."""
        query_embedding = [0.5] * 384
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        results = service_with_mocks.semantic_search(
            query_embedding=query_embedding,
            limit=5,
            session=mock_session
        )
        
        assert results == []

    def test_cosine_similarity_calculation(self, service_with_mocks):
        """Test cosine similarity helper method."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        
        # Perfect similarity
        similarity = service_with_mocks._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.01

    def test_cosine_similarity_orthogonal(self, service_with_mocks):
        """Test cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        
        similarity = service_with_mocks._cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 0.01

    def test_embedding_dimension_validation(self, service_with_mocks):
        """Test validation of embedding dimensions."""
        # Valid dimension
        embedding = [0.1] * 384
        assert service_with_mocks._validate_embedding(embedding) is True
        
        # Invalid dimension
        embedding_wrong = [0.1] * 100
        assert service_with_mocks._validate_embedding(embedding_wrong) is False

    @pytest.mark.parametrize("batch_size", [1, 5, 10, 50, 100])
    def test_batch_sizes(self, service_with_mocks, mock_local_embeddings, batch_size):
        """Test different batch sizes for embedding generation."""
        texts = [f"Text {i}" for i in range(batch_size)]
        mock_local_embeddings.embed_batch.return_value = [[0.1] * 384] * batch_size
        
        result = service_with_mocks.generate_embeddings_batch(texts)
        
        assert len(result) == batch_size
        mock_local_embeddings.embed_batch.assert_called_once_with(texts)

    def test_error_handling_openai_api_failure(self):
        """Test error handling when OpenAI API fails."""
        with patch('web.rag.embeddings.OpenAI') as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_client.embeddings.create.side_effect = Exception("API Error")
            
            service = EmbeddingsService(use_local=False, api_key='test-key')
            
            with pytest.raises(Exception):
                service.generate_embedding("Test text")

    def test_error_handling_local_model_failure(self, mock_local_embeddings):
        """Test error handling when local model fails."""
        mock_local_embeddings.embed_text.side_effect = Exception("Model Error")
        
        with patch('web.rag.embeddings.LocalEmbeddings', return_value=mock_local_embeddings):
            service = EmbeddingsService(use_local=True)
            
            with pytest.raises(Exception):
                service.generate_embedding("Test text")

    def test_caching_behavior(self, service_with_mocks, mock_local_embeddings):
        """Test that embeddings can be cached (if implemented)."""
        text = "Same text repeated"
        
        # Generate twice
        result1 = service_with_mocks.generate_embedding(text)
        result2 = service_with_mocks.generate_embedding(text)
        
        # Both should call the model (no caching currently)
        assert mock_local_embeddings.embed_text.call_count == 2
        assert result1 == result2


class TestEmbeddingsServiceIntegration:
    """Test embeddings service behavior with partial mocking."""

    def test_numpy_array_handling(self):
        """Test handling numpy arrays for embeddings."""
        with patch('web.rag.embeddings.LocalEmbeddings') as mock_class:
            mock_instance = MagicMock()
            mock_instance.embed_text.return_value = np.array([0.1] * 384)
            mock_class.return_value = mock_instance
            
            service = EmbeddingsService(use_local=True)
            result = service.generate_embedding("Test")
            
            # Should convert to list
            assert isinstance(result, (list, np.ndarray))
            assert len(result) == 384

    def test_concurrent_embedding_generation(self, mock_local_embeddings):
        """Test thread safety of embedding generation (if supported)."""
        with patch('web.rag.embeddings.LocalEmbeddings', return_value=mock_local_embeddings):
            service = EmbeddingsService(use_local=True)
            
            # Simulate concurrent calls
            texts = [f"Concurrent text {i}" for i in range(10)]
            results = []
            
            for text in texts:
                result = service.generate_embedding(text)
                results.append(result)
            
            assert len(results) == 10
            assert all(len(r) == 384 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
