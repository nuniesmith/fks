-- Migration to add pgvector extension for RAG system
-- Run this after 000_create_rag_tables.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Convert embedding column from FLOAT[] to vector type
-- First, we need to handle the conversion for existing data
DO $$
BEGIN
    -- Check if the column exists and is not already vector type
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'document_chunks' 
        AND column_name = 'embedding'
        AND data_type != 'USER-DEFINED'
    ) THEN
        -- For new installs, directly change to vector type
        -- Dimension can be 384 (MiniLM) or 1536 (OpenAI)
        -- We'll use 1536 as default and embeddings service will handle dimension
        ALTER TABLE document_chunks 
        ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector;
        
        RAISE NOTICE 'Converted embedding column to vector(1536) type';
    END IF;
END $$;

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
