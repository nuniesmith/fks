-- Migration to create RAG (Retrieval-Augmented Generation) tables
-- Run this before 001_add_pgvector.sql
-- These tables support the FKS Intelligence system for AI-powered trading insights

-- ============================================================================
-- DOCUMENTS TABLE
-- Store source documents for RAG knowledge base
-- ============================================================================
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    doc_type VARCHAR(50) NOT NULL CHECK (
        doc_type IN ('signal', 'backtest', 'trade_analysis', 'market_report', 'strategy', 'log', 'insight', 'other')
    ),
    title VARCHAR(500),
    content TEXT NOT NULL,
    source VARCHAR(255),  -- file path, url, or source identifier
    symbol VARCHAR(20),  -- related trading pair
    timeframe VARCHAR(10),  -- related timeframe
    metadata JSONB,  -- additional context (strategy name, metrics, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE documents IS 'RAG knowledge base documents for trading insights';
COMMENT ON COLUMN documents.doc_type IS 'Type of document: signal, backtest, trade_analysis, market_report, strategy, log, insight, other';
COMMENT ON COLUMN documents.metadata IS 'Additional context and metrics in JSON format';

-- ============================================================================
-- DOCUMENT CHUNKS TABLE
-- Store document chunks with embeddings for semantic search
-- ============================================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,  -- order within document
    content TEXT NOT NULL,
    embedding FLOAT[],  -- Will be converted to vector type by pgvector migration
    token_count INTEGER,
    metadata JSONB,  -- chunk-specific metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE document_chunks IS 'Document chunks with embeddings for semantic search';
COMMENT ON COLUMN document_chunks.embedding IS 'Embedding vector (will be vector type after pgvector migration)';
COMMENT ON COLUMN document_chunks.chunk_index IS 'Order of chunk within parent document';

-- ============================================================================
-- QUERY HISTORY TABLE
-- Track RAG queries and responses for analysis
-- ============================================================================
CREATE TABLE IF NOT EXISTS query_history (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    response TEXT,
    retrieved_chunks JSONB,  -- list of chunk IDs and relevance scores
    model_used VARCHAR(50),
    query_type VARCHAR(50),  -- 'strategy_suggestion', 'market_analysis', 'trade_insight', etc.
    response_time_ms INTEGER,
    user_feedback INTEGER CHECK (user_feedback >= 1 AND user_feedback <= 5),  -- rating 1-5
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE query_history IS 'History of RAG queries and responses for analysis';
COMMENT ON COLUMN query_history.retrieved_chunks IS 'JSON array of retrieved chunk IDs and relevance scores';
COMMENT ON COLUMN query_history.user_feedback IS 'User rating from 1 (poor) to 5 (excellent)';

-- ============================================================================
-- TRADING INSIGHTS TABLE
-- Curated trading insights and lessons learned
-- ============================================================================
CREATE TABLE IF NOT EXISTS trading_insights (
    id SERIAL PRIMARY KEY,
    insight_type VARCHAR(50) NOT NULL,  -- 'lesson_learned', 'pattern_observed', 'strategy_improvement', 'risk_observation'
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    symbol VARCHAR(20),
    related_trades JSONB,  -- trade IDs
    related_backtests JSONB,  -- backtest IDs
    impact VARCHAR(20),  -- 'high', 'medium', 'low'
    category VARCHAR(50),  -- 'technical', 'fundamental', 'risk_management', 'psychology'
    tags TEXT[],  -- array of tags
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE trading_insights IS 'Curated trading insights and lessons learned';
COMMENT ON COLUMN trading_insights.insight_type IS 'Type: lesson_learned, pattern_observed, strategy_improvement, risk_observation';
COMMENT ON COLUMN trading_insights.impact IS 'Impact level: high, medium, low';
COMMENT ON COLUMN trading_insights.category IS 'Category: technical, fundamental, risk_management, psychology';

-- ============================================================================
-- INDEXES
-- Basic indexes for query performance
-- ============================================================================

-- Documents indexes
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_symbol ON documents(symbol);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

-- Document chunks indexes
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);

-- Query history indexes
CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_history_query_type ON query_history(query_type);

-- Trading insights indexes
CREATE INDEX IF NOT EXISTS idx_trading_insights_symbol ON trading_insights(symbol);
CREATE INDEX IF NOT EXISTS idx_trading_insights_impact ON trading_insights(impact);
CREATE INDEX IF NOT EXISTS idx_trading_insights_category ON trading_insights(category);
CREATE INDEX IF NOT EXISTS idx_trading_insights_created_at ON trading_insights(created_at DESC);

-- ============================================================================
-- TRIGGER FOR UPDATED_AT
-- Automatically update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trading_insights_updated_at
    BEFORE UPDATE ON trading_insights
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA (OPTIONAL)
-- ============================================================================

-- You can add initial insights or documentation here
-- Example:
-- INSERT INTO trading_insights (insight_type, title, content, impact, category)
-- VALUES (
--     'strategy_improvement',
--     'Risk Management Best Practice',
--     'Always use stop losses and risk no more than 2% per trade.',
--     'high',
--     'risk_management'
-- );
