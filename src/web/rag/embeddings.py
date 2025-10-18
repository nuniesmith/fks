"""
Embeddings service for RAG system.
Handles generating embeddings using OpenAI or local models with pgvector storage.
"""

from typing import List, Dict, Any, Optional
import os
from openai import OpenAI
import numpy as np
from sqlalchemy import text

from database import Session
from framework.config.constants import OPENAI_API_KEY


class EmbeddingsService:
    """Generate and manage embeddings for RAG"""
    
    def __init__(self, 
                 model: str = "text-embedding-3-small",
                 dimension: int = 1536,
                 use_local: bool = True):
        """
        Initialize embeddings service.
        
        Args:
            model: Model name (OpenAI or HuggingFace)
            dimension: Embedding dimension
            use_local: Use local model instead of OpenAI API
        """
        self.model = model
        self.dimension = dimension
        self.use_local = use_local
        
        if use_local:
            self._init_local_model()
        else:
            self._init_openai()
    
    def _init_local_model(self):
        """Initialize local embedding model"""
        try:
            from rag.local_llm import create_local_embeddings
            
            # Default to fast local model
            if self.model.startswith("text-embedding"):
                # Map OpenAI models to local equivalents
                self.model = "all-MiniLM-L6-v2"
                self.dimension = 384  # MiniLM dimension
            
            self.embeddings = create_local_embeddings(model_name=self.model)
            self.dimension = self.embeddings.dimension
            print(f"✓ Using local embeddings: {self.model} ({self.dimension}d)")
            
        except ImportError as e:
            print(f"⚠ Local embeddings not available: {e}")
            print("  Falling back to OpenAI...")
            self.use_local = False
            self._init_openai()
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set and local models not available")
        
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        print(f"✓ Using OpenAI embeddings: {self.model}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as list of floats
        """
        if not text or not text.strip():
            return [0.0] * self.dimension
        
        if self.use_local:
            return self.embeddings.generate_embedding(text)
        else:
            return self._generate_openai(text)
    
    def _generate_openai(self, text: str) -> List[float]:
        """Generate embedding using OpenAI"""
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return [0.0] * self.dimension
    
    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of input texts
            batch_size: Number of texts to process per API call (OpenAI) or batch (local)
            
        Returns:
            List of embedding vectors
        """
        if self.use_local:
            # Local model can handle larger batches efficiently
            batch_size = 32
            # Filter out empty texts
            texts = [text if text and text.strip() else " " for text in texts]
            return self.embeddings.generate_embeddings_batch(texts, batch_size=batch_size)
        else:
            return self._generate_openai_batch(texts, batch_size)
    
    def _generate_openai_batch(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """Generate embeddings using OpenAI in batches"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            # Filter out empty texts
            batch = [text if text and text.strip() else " " for text in batch]
            
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.model
                )
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
            except Exception as e:
                print(f"Error generating batch embeddings: {e}")
                # Add zero vectors for failed batch
                embeddings.extend([[0.0] * self.dimension] * len(batch))
        
        return embeddings
    
    def store_chunk_embedding(self, 
                              chunk_id: int, 
                              embedding: List[float],
                              session: Optional[Session] = None) -> bool:
        """
        Store embedding for a document chunk using pgvector.
        
        Args:
            chunk_id: Document chunk ID
            embedding: Embedding vector
            session: SQLAlchemy session (creates new if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            # Update chunk with embedding
            # Note: We use raw SQL for pgvector operations
            query = text("""
                UPDATE document_chunks 
                SET embedding = :embedding::vector
                WHERE id = :chunk_id
            """)
            
            session.execute(query, {
                'chunk_id': chunk_id,
                'embedding': str(embedding)  # pgvector accepts list as string
            })
            session.commit()
            return True
        except Exception as e:
            print(f"Error storing embedding: {e}")
            session.rollback()
            return False
        finally:
            if should_close:
                session.close()
    
    def semantic_search(self,
                        query_embedding: List[float],
                        limit: int = 5,
                        similarity_threshold: float = 0.7,
                        filters: Optional[Dict[str, Any]] = None,
                        session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Perform semantic search using cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)
            filters: Optional filters (symbol, doc_type, etc.)
            session: SQLAlchemy session
            
        Returns:
            List of matching chunks with metadata
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            # Build filter conditions
            where_conditions = ["embedding IS NOT NULL"]
            params = {
                'query_embedding': str(query_embedding),
                'limit': limit,
                'threshold': similarity_threshold
            }
            
            if filters:
                if 'symbol' in filters:
                    where_conditions.append("d.symbol = :symbol")
                    params['symbol'] = filters['symbol']
                
                if 'doc_type' in filters:
                    where_conditions.append("d.doc_type = :doc_type")
                    params['doc_type'] = filters['doc_type']
                
                if 'timeframe' in filters:
                    where_conditions.append("d.timeframe = :timeframe")
                    params['timeframe'] = filters['timeframe']
            
            where_clause = " AND ".join(where_conditions)
            
            # Semantic search query using pgvector cosine similarity
            query = text(f"""
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.content,
                    dc.chunk_index,
                    dc.metadata as chunk_metadata,
                    d.doc_type,
                    d.title,
                    d.symbol,
                    d.timeframe,
                    d.metadata as doc_metadata,
                    1 - (dc.embedding <=> :query_embedding::vector) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE {where_clause}
                    AND (1 - (dc.embedding <=> :query_embedding::vector)) >= :threshold
                ORDER BY dc.embedding <=> :query_embedding::vector
                LIMIT :limit
            """)
            
            results = session.execute(query, params).fetchall()
            
            return [
                {
                    'chunk_id': row[0],
                    'document_id': row[1],
                    'content': row[2],
                    'chunk_index': row[3],
                    'chunk_metadata': row[4],
                    'doc_type': row[5],
                    'title': row[6],
                    'symbol': row[7],
                    'timeframe': row[8],
                    'doc_metadata': row[9],
                    'similarity': float(row[10])
                }
                for row in results
            ]
        except Exception as e:
            print(f"Error in semantic search: {e}")
            return []
        finally:
            if should_close:
                session.close()
    
    def find_similar_chunks(self,
                           chunk_id: int,
                           limit: int = 5,
                           session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Find similar chunks to a given chunk.
        
        Args:
            chunk_id: Source chunk ID
            limit: Maximum number of results
            session: SQLAlchemy session
            
        Returns:
            List of similar chunks
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            query = text("""
                SELECT 
                    dc2.id,
                    dc2.content,
                    dc2.document_id,
                    1 - (dc1.embedding <=> dc2.embedding) as similarity
                FROM document_chunks dc1
                JOIN document_chunks dc2 ON dc1.id != dc2.id
                WHERE dc1.id = :chunk_id
                    AND dc1.embedding IS NOT NULL
                    AND dc2.embedding IS NOT NULL
                ORDER BY dc1.embedding <=> dc2.embedding
                LIMIT :limit
            """)
            
            results = session.execute(query, {
                'chunk_id': chunk_id,
                'limit': limit
            }).fetchall()
            
            return [
                {
                    'chunk_id': row[0],
                    'content': row[1],
                    'document_id': row[2],
                    'similarity': float(row[3])
                }
                for row in results
            ]
        except Exception as e:
            print(f"Error finding similar chunks: {e}")
            return []
        finally:
            if should_close:
                session.close()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    
    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


# Convenience function
def create_embeddings_service(model: str = "all-MiniLM-L6-v2", use_local: bool = True) -> EmbeddingsService:
    """
    Create embeddings service with local or OpenAI models.
    
    Args:
        model: Model name (local: HuggingFace model, OpenAI: text-embedding-*)
        use_local: Use local model (default: True)
        
    Returns:
        EmbeddingsService instance
    """
    return EmbeddingsService(model=model, use_local=use_local)
