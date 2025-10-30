-- ============================================================================
-- MIGRATION: Add Fundamentals Core Tables (Working Version)
-- Version: 1.0.2  
-- Date: 2024-01-01
-- Description: Core fundamentals tables without continuous aggregates
-- ============================================================================

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Migration tracking
INSERT INTO schema_migrations (migration_name, description) 
VALUES ('001_add_fundamentals_core_v2', 'Add core fundamentals data tables v2')
ON CONFLICT (migration_name) DO NOTHING;

-- ============================================================================
-- COMPANY FUNDAMENTALS TABLE
-- ============================================================================
CREATE TABLE company_fundamentals (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    reporting_period TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    period_type TEXT NOT NULL,
    
    -- Income Statement
    revenue DECIMAL(20, 2),
    net_income DECIMAL(20, 2),
    earnings_per_share DECIMAL(10, 4),
    
    -- Balance Sheet
    total_assets DECIMAL(20, 2),
    shareholders_equity DECIMAL(20, 2),
    total_debt DECIMAL(20, 2),
    
    -- Key Ratios
    pe_ratio DECIMAL(10, 4),
    pb_ratio DECIMAL(10, 4),
    roe DECIMAL(10, 4),
    
    -- Metadata
    currency TEXT DEFAULT 'USD',
    data_source TEXT DEFAULT 'EODHD',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('company_fundamentals', 'time');

CREATE INDEX idx_fundamentals_symbol_time 
    ON company_fundamentals (symbol, time DESC);

-- ============================================================================
-- EARNINGS DATA TABLE  
-- ============================================================================
CREATE TABLE earnings_data (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    reporting_period TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    
    eps_estimate DECIMAL(10, 4),
    eps_actual DECIMAL(10, 4),
    eps_surprise_percent DECIMAL(10, 4),
    
    revenue_estimate DECIMAL(20, 2),
    revenue_actual DECIMAL(20, 2),
    revenue_surprise_percent DECIMAL(10, 4),
    
    data_source TEXT DEFAULT 'EODHD',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('earnings_data', 'time');

CREATE INDEX idx_earnings_symbol_time 
    ON earnings_data (symbol, time DESC);

-- ============================================================================
-- ECONOMIC INDICATORS TABLE
-- ============================================================================
CREATE TABLE economic_indicators (
    time TIMESTAMPTZ NOT NULL,
    indicator_code TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    country TEXT NOT NULL,
    
    value DECIMAL(20, 6),
    previous_value DECIMAL(20, 6),
    change_percent DECIMAL(10, 4),
    
    frequency TEXT,
    unit TEXT,
    release_importance TEXT,
    data_source TEXT DEFAULT 'EODHD',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('economic_indicators', 'time');

CREATE UNIQUE INDEX idx_economic_unique 
    ON economic_indicators (indicator_code, time);

CREATE INDEX idx_economic_country_time 
    ON economic_indicators (country, time DESC);

-- ============================================================================
-- INSIDER TRANSACTIONS TABLE
-- ============================================================================
CREATE TABLE insider_transactions (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    insider_name TEXT,
    transaction_type TEXT NOT NULL,
    
    shares_traded DECIMAL(20, 0),
    price_per_share DECIMAL(10, 4),
    total_value DECIMAL(20, 2),
    
    data_source TEXT DEFAULT 'EODHD',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('insider_transactions', 'time');

CREATE INDEX idx_insider_symbol_time 
    ON insider_transactions (symbol, time DESC);

-- ============================================================================
-- NEWS SENTIMENT TABLE (Basic version without embeddings)
-- ============================================================================
CREATE TABLE news_sentiment (
    time TIMESTAMPTZ NOT NULL,
    article_id TEXT NOT NULL,
    symbol TEXT,
    
    title TEXT NOT NULL,
    source TEXT,
    
    sentiment_score DECIMAL(5, 4),
    sentiment_label TEXT,
    
    data_source TEXT DEFAULT 'EODHD',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('news_sentiment', 'time');

CREATE INDEX idx_news_symbol_time 
    ON news_sentiment (symbol, time DESC);

-- ============================================================================
-- CORRELATION ANALYSIS TABLE
-- ============================================================================
CREATE TABLE correlation_analysis (
    id SERIAL PRIMARY KEY,
    asset1_symbol TEXT NOT NULL,
    asset2_symbol TEXT NOT NULL,
    
    correlation_30d DECIMAL(5, 4),
    correlation_90d DECIMAL(5, 4),
    
    calculation_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_correlation_assets 
    ON correlation_analysis (asset1_symbol, asset2_symbol);

-- ============================================================================
-- SAMPLE DATA
-- ============================================================================
INSERT INTO economic_indicators (
    time, indicator_code, indicator_name, country, value, frequency, unit, release_importance
) VALUES 
    (NOW() - INTERVAL '1 month', 'US_GDP', 'Gross Domestic Product', 'US', 26854.60, 'quarterly', 'Billions USD', 'high'),
    (NOW() - INTERVAL '1 month', 'US_CPI', 'Consumer Price Index', 'US', 307.89, 'monthly', 'Index', 'high'),
    (NOW() - INTERVAL '1 month', 'FED_RATE', 'Federal Funds Rate', 'US', 5.25, 'meeting', 'Percent', 'high'),
    (NOW() - INTERVAL '1 month', 'US_UNEMPLOYMENT', 'Unemployment Rate', 'US', 3.7, 'monthly', 'Percent', 'medium')
ON CONFLICT (indicator_code, time) DO NOTHING;