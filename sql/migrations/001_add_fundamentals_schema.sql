-- ============================================================================
-- MIGRATION: Add Fundamentals Schema to FKS Trading Platform
-- Version: 1.0.0
-- Date: 2024-01-01
-- Description: Adds comprehensive fundamentals data support including:
--              - Company financials, earnings, economic indicators
--              - Insider transactions, news sentiment analysis
--              - Correlation analysis and continuous aggregates
-- ============================================================================

BEGIN;

-- Check if migration has already been applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'company_fundamentals') THEN
        RAISE NOTICE 'Fundamentals schema migration already applied, skipping...';
        ROLLBACK;
        RETURN;
    END IF;
END $$;

-- Migration metadata table
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    description TEXT
);

-- Record this migration
INSERT INTO schema_migrations (migration_name, description) 
VALUES ('001_add_fundamentals_schema', 'Add comprehensive fundamentals data support');

-- ============================================================================
-- Apply the fundamentals schema
-- ============================================================================

-- Enable pgvector extension for similarity search (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Company Fundamentals Table
CREATE TABLE company_fundamentals (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    reporting_period VARCHAR(10) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    period_type VARCHAR(10) NOT NULL,
    
    -- Income Statement Data
    revenue DECIMAL(20, 2),
    gross_profit DECIMAL(20, 2),
    operating_income DECIMAL(20, 2),
    net_income DECIMAL(20, 2),
    earnings_per_share DECIMAL(10, 4),
    
    -- Balance Sheet Data
    total_assets DECIMAL(20, 2),
    total_liabilities DECIMAL(20, 2),
    shareholders_equity DECIMAL(20, 2),
    cash_and_equivalents DECIMAL(20, 2),
    total_debt DECIMAL(20, 2),
    
    -- Cash Flow Data
    operating_cash_flow DECIMAL(20, 2),
    free_cash_flow DECIMAL(20, 2),
    capital_expenditures DECIMAL(20, 2),
    
    -- Key Ratios
    pe_ratio DECIMAL(10, 4),
    pb_ratio DECIMAL(10, 4),
    debt_to_equity DECIMAL(10, 4),
    roe DECIMAL(10, 4),
    roa DECIMAL(10, 4),
    profit_margin DECIMAL(10, 4),
    
    -- Metadata
    currency VARCHAR(10) DEFAULT 'USD',
    filing_date TIMESTAMPTZ,
    data_source VARCHAR(50) DEFAULT 'EODHD',
    fundamentals_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('company_fundamentals', 'time');

-- Indexes (time must be included in unique indexes for hypertables)
CREATE UNIQUE INDEX idx_fundamentals_unique 
    ON company_fundamentals (symbol, fiscal_year, reporting_period, period_type, time);

CREATE INDEX idx_fundamentals_symbol_time 
    ON company_fundamentals (symbol, time DESC);
    
CREATE INDEX idx_fundamentals_fiscal_year 
    ON company_fundamentals (fiscal_year, time DESC);

-- Compression
ALTER TABLE company_fundamentals SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('company_fundamentals', INTERVAL '1 year');

-- Earnings Data Table
CREATE TABLE earnings_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    reporting_period VARCHAR(10) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    
    eps_estimate DECIMAL(10, 4),
    eps_actual DECIMAL(10, 4),
    eps_surprise DECIMAL(10, 4),
    eps_surprise_percent DECIMAL(10, 4),
    
    revenue_estimate DECIMAL(20, 2),
    revenue_actual DECIMAL(20, 2),
    revenue_surprise DECIMAL(20, 2),
    revenue_surprise_percent DECIMAL(10, 4),
    
    guidance_eps_low DECIMAL(10, 4),
    guidance_eps_high DECIMAL(10, 4),
    guidance_revenue_low DECIMAL(20, 2),
    guidance_revenue_high DECIMAL(20, 2),
    
    announcement_time VARCHAR(20),
    conference_call_time TIMESTAMPTZ,
    currency VARCHAR(10) DEFAULT 'USD',
    data_source VARCHAR(50) DEFAULT 'EODHD',
    earnings_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('earnings_data', 'time');

CREATE UNIQUE INDEX idx_earnings_unique 
    ON earnings_data (symbol, fiscal_year, reporting_period, time);

CREATE INDEX idx_earnings_symbol_time 
    ON earnings_data (symbol, time DESC);
    
CREATE INDEX idx_earnings_surprise 
    ON earnings_data (eps_surprise_percent, time DESC);

-- Economic Indicators Table
CREATE TABLE economic_indicators (
    time TIMESTAMPTZ NOT NULL,
    indicator_code VARCHAR(50) NOT NULL,
    indicator_name VARCHAR(200) NOT NULL,
    country VARCHAR(10) NOT NULL,
    
    value DECIMAL(20, 6),
    previous_value DECIMAL(20, 6),
    change_value DECIMAL(20, 6),
    change_percent DECIMAL(10, 4),
    
    forecast DECIMAL(20, 6),
    surprise DECIMAL(20, 6),
    
    frequency VARCHAR(20),
    unit VARCHAR(50),
    data_source VARCHAR(50) DEFAULT 'EODHD',
    release_importance VARCHAR(10),
    indicator_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('economic_indicators', 'time');

CREATE UNIQUE INDEX idx_economic_unique 
    ON economic_indicators (indicator_code, time);

CREATE INDEX idx_economic_country_time 
    ON economic_indicators (country, time DESC);
    
CREATE INDEX idx_economic_indicator_time 
    ON economic_indicators (indicator_code, time DESC);
    
CREATE INDEX idx_economic_importance 
    ON economic_indicators (release_importance, time DESC);

ALTER TABLE economic_indicators SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'country, indicator_code',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('economic_indicators', INTERVAL '2 years');

-- Insider Transactions Table
CREATE TABLE insider_transactions (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    insider_name VARCHAR(200),
    insider_title VARCHAR(200),
    
    transaction_type VARCHAR(20) NOT NULL,
    shares_traded DECIMAL(20, 0),
    price_per_share DECIMAL(10, 4),
    total_value DECIMAL(20, 2),
    
    shares_owned_after DECIMAL(20, 0),
    ownership_percent DECIMAL(10, 6),
    
    sec_filing_type VARCHAR(20),
    filing_date TIMESTAMPTZ,
    data_source VARCHAR(50) DEFAULT 'EODHD',
    transaction_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('insider_transactions', 'time');

CREATE INDEX idx_insider_symbol_time 
    ON insider_transactions (symbol, time DESC);
    
CREATE INDEX idx_insider_type_time 
    ON insider_transactions (transaction_type, time DESC);
    
CREATE INDEX idx_insider_value 
    ON insider_transactions (total_value, time DESC);

-- News Sentiment Table
CREATE TABLE news_sentiment (
    time TIMESTAMPTZ NOT NULL,
    article_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20),
    
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    author VARCHAR(200),
    source VARCHAR(100),
    url TEXT,
    
    sentiment_score DECIMAL(5, 4),
    sentiment_label VARCHAR(20),
    confidence_score DECIMAL(5, 4),
    
    topics TEXT[],
    entities TEXT[],
    keywords TEXT[],
    
    content_embedding vector(384),
    
    language VARCHAR(10) DEFAULT 'en',
    data_source VARCHAR(50) DEFAULT 'EODHD',
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    news_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('news_sentiment', 'time');

CREATE UNIQUE INDEX idx_news_unique 
    ON news_sentiment (article_id, time);

CREATE INDEX idx_news_symbol_time 
    ON news_sentiment (symbol, time DESC);
    
CREATE INDEX idx_news_sentiment_time 
    ON news_sentiment (sentiment_score, time DESC);
    
CREATE INDEX idx_news_source_time 
    ON news_sentiment (source, time DESC);

CREATE INDEX idx_news_embedding 
    ON news_sentiment USING ivfflat (content_embedding vector_cosine_ops);

-- Correlation Analysis Table
CREATE TABLE correlation_analysis (
    id SERIAL PRIMARY KEY,
    asset1_type VARCHAR(50) NOT NULL,
    asset1_symbol VARCHAR(50) NOT NULL,
    asset2_type VARCHAR(50) NOT NULL,
    asset2_symbol VARCHAR(50) NOT NULL,
    
    correlation_1d DECIMAL(5, 4),
    correlation_7d DECIMAL(5, 4),
    correlation_30d DECIMAL(5, 4),
    correlation_90d DECIMAL(5, 4),
    
    correlation_mean DECIMAL(5, 4),
    correlation_std DECIMAL(5, 4),
    correlation_min DECIMAL(5, 4),
    correlation_max DECIMAL(5, 4),
    
    lookback_days INTEGER DEFAULT 252,
    calculation_date TIMESTAMPTZ NOT NULL,
    data_points_used INTEGER,
    statistical_significance DECIMAL(5, 4),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_correlation_assets 
    ON correlation_analysis (asset1_symbol, asset2_symbol);
    
CREATE INDEX idx_correlation_date 
    ON correlation_analysis (calculation_date DESC);

-- ============================================================================
-- Continuous Aggregates
-- ============================================================================

-- Quarterly earnings summary
CREATE MATERIALIZED VIEW quarterly_earnings_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('3 months', time) AS quarter,
    symbol,
    COUNT(*) as earnings_count,
    AVG(eps_surprise_percent) as avg_eps_surprise,
    AVG(revenue_surprise_percent) as avg_revenue_surprise,
    SUM(CASE WHEN eps_surprise > 0 THEN 1 ELSE 0 END) as eps_beats,
    SUM(CASE WHEN eps_surprise < 0 THEN 1 ELSE 0 END) as eps_misses
FROM earnings_data
WHERE eps_actual IS NOT NULL
GROUP BY quarter, symbol;

SELECT add_continuous_aggregate_policy('quarterly_earnings_summary',
    start_offset => INTERVAL '1 year',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- Monthly economic summary
CREATE MATERIALIZED VIEW monthly_economic_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 month', time) AS month,
    country,
    indicator_code,
    indicator_name,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    COUNT(*) as data_points
FROM economic_indicators
GROUP BY month, country, indicator_code, indicator_name;

SELECT add_continuous_aggregate_policy('monthly_economic_summary',
    start_offset => INTERVAL '2 years',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- ============================================================================
-- Functions
-- ============================================================================

-- Calculate financial ratios
CREATE OR REPLACE FUNCTION calculate_financial_ratios(
    p_revenue DECIMAL,
    p_net_income DECIMAL,
    p_total_assets DECIMAL,
    p_shareholders_equity DECIMAL,
    p_total_debt DECIMAL
) RETURNS JSONB AS $$
DECLARE
    ratios JSONB := '{}';
BEGIN
    IF p_revenue > 0 THEN
        ratios := jsonb_set(ratios, '{profit_margin}', to_jsonb((p_net_income / p_revenue)::DECIMAL(10,4)));
    END IF;
    
    IF p_total_assets > 0 THEN
        ratios := jsonb_set(ratios, '{roa}', to_jsonb((p_net_income / p_total_assets)::DECIMAL(10,4)));
    END IF;
    
    IF p_shareholders_equity > 0 THEN
        ratios := jsonb_set(ratios, '{roe}', to_jsonb((p_net_income / p_shareholders_equity)::DECIMAL(10,4)));
    END IF;
    
    IF p_shareholders_equity > 0 THEN
        ratios := jsonb_set(ratios, '{debt_to_equity}', to_jsonb((p_total_debt / p_shareholders_equity)::DECIMAL(10,4)));
    END IF;
    
    RETURN ratios;
END;
$$ LANGUAGE plpgsql;

-- Get latest fundamentals
CREATE OR REPLACE FUNCTION get_latest_fundamentals(p_symbol VARCHAR(20))
RETURNS TABLE(
    reporting_period VARCHAR(10),
    fiscal_year INTEGER,
    revenue DECIMAL(20,2),
    net_income DECIMAL(20,2),
    eps DECIMAL(10,4),
    pe_ratio DECIMAL(10,4),
    pb_ratio DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cf.reporting_period,
        cf.fiscal_year,
        cf.revenue,
        cf.net_income,
        cf.earnings_per_share,
        cf.pe_ratio,
        cf.pb_ratio
    FROM company_fundamentals cf
    WHERE cf.symbol = p_symbol
    ORDER BY cf.time DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Data Retention Policies
-- ============================================================================

SELECT add_retention_policy('insider_transactions', INTERVAL '5 years');
SELECT add_retention_policy('news_sentiment', INTERVAL '2 years');

-- ============================================================================
-- Sample Data
-- ============================================================================

INSERT INTO economic_indicators (
    time, indicator_code, indicator_name, country, value, frequency, unit, release_importance
) VALUES 
    (NOW() - INTERVAL '1 month', 'US_GDP', 'Gross Domestic Product', 'US', 26854.60, 'quarterly', 'Billions USD', 'high'),
    (NOW() - INTERVAL '1 month', 'US_CPI', 'Consumer Price Index', 'US', 307.89, 'monthly', 'Index', 'high'),
    (NOW() - INTERVAL '1 month', 'FED_RATE', 'Federal Funds Rate', 'US', 5.25, 'meeting', 'Percent', 'high'),
    (NOW() - INTERVAL '1 month', 'US_UNEMPLOYMENT', 'Unemployment Rate', 'US', 3.7, 'monthly', 'Percent', 'medium')
ON CONFLICT (indicator_code, time) DO NOTHING;

-- ============================================================================
-- Update triggers for updated_at columns
-- ============================================================================

CREATE TRIGGER trigger_fundamentals_updated_at
BEFORE UPDATE ON company_fundamentals
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_correlation_updated_at
BEFORE UPDATE ON correlation_analysis
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE company_fundamentals IS 'Quarterly and annual financial data for companies from earnings reports and SEC filings';
COMMENT ON TABLE earnings_data IS 'Earnings announcements with estimates vs actuals and surprise analysis';  
COMMENT ON TABLE economic_indicators IS 'Macroeconomic indicators including GDP, CPI, interest rates, and employment data';
COMMENT ON TABLE insider_transactions IS 'Corporate insider buy/sell transactions from SEC filings';
COMMENT ON TABLE news_sentiment IS 'News articles with sentiment analysis and embeddings for similarity search';
COMMENT ON TABLE correlation_analysis IS 'Pre-computed correlations between assets and economic indicators';

COMMIT;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Fundamentals schema migration completed successfully!';
    RAISE NOTICE 'Added tables: company_fundamentals, earnings_data, economic_indicators, insider_transactions, news_sentiment, correlation_analysis';
    RAISE NOTICE 'Added continuous aggregates: quarterly_earnings_summary, monthly_economic_summary';
    RAISE NOTICE 'Added functions: calculate_financial_ratios(), get_latest_fundamentals()';
END $$;