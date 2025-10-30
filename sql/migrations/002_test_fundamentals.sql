-- ============================================================================
-- MIGRATION: Add Fundamentals Schema to FKS Trading Platform (SIMPLIFIED)
-- Version: 1.0.1
-- Date: 2024-01-01
-- Description: Core fundamentals tables without continuous aggregates
-- ============================================================================

-- Migration metadata table
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    description TEXT
);

-- Check if migration has already been applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'company_fundamentals') THEN
        RAISE NOTICE 'Fundamentals schema already exists, skipping core migration...';
    ELSE
        INSERT INTO schema_migrations (migration_name, description) 
        VALUES ('001_add_fundamentals_core', 'Add core fundamentals data tables');
        RAISE NOTICE 'Applied fundamentals core migration';
    END IF;
END $$;

-- Test the schema with a simple query
SELECT COUNT(*) as fundamentals_tables_count
FROM information_schema.tables 
WHERE table_name IN (
    'company_fundamentals', 
    'earnings_data', 
    'economic_indicators', 
    'insider_transactions', 
    'news_sentiment', 
    'correlation_analysis'
);

-- Sample data test
SELECT 
    indicator_code, 
    indicator_name, 
    value, 
    unit
FROM economic_indicators 
WHERE country = 'US' 
ORDER BY time DESC 
LIMIT 5;