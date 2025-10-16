-- Migration to add pgvector extension for RAG system
-- Run this after initial database setup

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector column to document_chunks if not exists
-- Note: This is handled by SQLAlchemy, but kept for reference
-- ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Create index for vector similarity search using HNSW (Hierarchical Navigable Small World)
-- This index provides fast approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat index (good for smaller datasets)
-- CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_ivfflat 
-- ON document_chunks 
-- USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);

-- Create composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_documents_type_symbol ON documents(doc_type, symbol);
CREATE INDEX IF NOT EXISTS idx_documents_symbol_created ON documents(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id_idx ON document_chunks(document_id, chunk_index);

-- Create index for query history analysis
CREATE INDEX IF NOT EXISTS idx_query_history_type_created ON query_history(query_type, created_at DESC);

-- Create GIN index for metadata JSONB fields for fast filtering
CREATE INDEX IF NOT EXISTS idx_documents_metadata_gin ON documents USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata_gin ON document_chunks USING GIN (metadata);

-- Create index for trading insights
CREATE INDEX IF NOT EXISTS idx_trading_insights_tags_gin ON trading_insights USING GIN (tags);

-- Vacuum analyze to update statistics
VACUUM ANALYZE documents;
VACUUM ANALYZE document_chunks;
VACUUM ANALYZE query_history;
VACUUM ANALYZE trading_insights;

COMMENT ON EXTENSION vector IS 'pgvector extension for storing and querying embeddings';
COMMENT ON TABLE documents IS 'RAG knowledge base documents';
COMMENT ON TABLE document_chunks IS 'Document chunks with embeddings for semantic search';
COMMENT ON TABLE query_history IS 'History of RAG queries and responses';
COMMENT ON TABLE trading_insights IS 'Curated trading insights and lessons learned';
