-- ============================================================================
-- FUNDAMENTALS DATA SCHEMA EXTENSION
-- For FKS Trading Platform - Phase 5.3: TimescaleDB Fundamentals Schema
-- ============================================================================
-- This schema extension adds support for fundamental data from EODHD API:
-- - Company financials (balance sheet, income statement, cash flow)
-- - Earnings data (EPS, revenue, guidance)
-- - Economic indicators (GDP, CPI, unemployment, interest rates)
-- - Insider transactions and institutional holdings
-- - Exchange statistics and news sentiment
-- ============================================================================

-- Enable pgvector extension for similarity search (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- COMPANY FUNDAMENTALS TABLE (HYPERTABLE)
-- Quarterly and annual financial data for companies
-- ============================================================================
CREATE TABLE IF NOT EXISTS company_fundamentals (
    time TIMESTAMPTZ NOT NULL,               -- Reporting period end date
    symbol VARCHAR(20) NOT NULL,             -- Stock symbol (e.g., AAPL)
    reporting_period VARCHAR(10) NOT NULL,   -- Q1, Q2, Q3, Q4, FY
    fiscal_year INTEGER NOT NULL,            -- Fiscal year
    period_type VARCHAR(10) NOT NULL,        -- 'quarterly' or 'annual'
    
    -- Income Statement Data
    revenue DECIMAL(20, 2),                  -- Total revenue
    gross_profit DECIMAL(20, 2),            -- Gross profit
    operating_income DECIMAL(20, 2),        -- Operating income/EBIT
    net_income DECIMAL(20, 2),              -- Net income
    earnings_per_share DECIMAL(10, 4),      -- Diluted EPS
    
    -- Balance Sheet Data
    total_assets DECIMAL(20, 2),            -- Total assets
    total_liabilities DECIMAL(20, 2),       -- Total liabilities
    shareholders_equity DECIMAL(20, 2),     -- Shareholders' equity
    cash_and_equivalents DECIMAL(20, 2),    -- Cash and cash equivalents
    total_debt DECIMAL(20, 2),              -- Total debt
    
    -- Cash Flow Data
    operating_cash_flow DECIMAL(20, 2),     -- Operating cash flow
    free_cash_flow DECIMAL(20, 2),          -- Free cash flow
    capital_expenditures DECIMAL(20, 2),    -- CapEx
    
    -- Key Ratios (derived or provided)
    pe_ratio DECIMAL(10, 4),                -- Price-to-earnings ratio
    pb_ratio DECIMAL(10, 4),                -- Price-to-book ratio
    debt_to_equity DECIMAL(10, 4),          -- Debt-to-equity ratio
    roe DECIMAL(10, 4),                     -- Return on equity
    roa DECIMAL(10, 4),                     -- Return on assets
    profit_margin DECIMAL(10, 4),           -- Net profit margin
    
    -- Additional metadata
    currency VARCHAR(10) DEFAULT 'USD',      -- Currency of financial data
    filing_date TIMESTAMPTZ,                 -- SEC filing date
    data_source VARCHAR(50) DEFAULT 'EODHD', -- Data provider
    fundamentals_metadata JSONB,             -- Additional raw data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('company_fundamentals', 'time', if_not_exists => TRUE);

-- Unique constraint to prevent duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_fundamentals_unique 
    ON company_fundamentals (symbol, fiscal_year, reporting_period, period_type);

-- Additional indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_fundamentals_symbol_time 
    ON company_fundamentals (symbol, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_fundamentals_fiscal_year 
    ON company_fundamentals (fiscal_year, time DESC);

-- Enable compression (compress data older than 1 year)
ALTER TABLE company_fundamentals SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('company_fundamentals', INTERVAL '1 year', if_not_exists => TRUE);

-- ============================================================================
-- EARNINGS DATA TABLE (HYPERTABLE)
-- Earnings announcements, estimates, and actuals
-- ============================================================================
CREATE TABLE IF NOT EXISTS earnings_data (
    time TIMESTAMPTZ NOT NULL,               -- Earnings announcement date
    symbol VARCHAR(20) NOT NULL,             -- Stock symbol
    reporting_period VARCHAR(10) NOT NULL,   -- Q1, Q2, Q3, Q4
    fiscal_year INTEGER NOT NULL,            -- Fiscal year
    
    -- Earnings Estimates vs Actuals
    eps_estimate DECIMAL(10, 4),            -- Analyst EPS estimate
    eps_actual DECIMAL(10, 4),              -- Actual reported EPS
    eps_surprise DECIMAL(10, 4),            -- EPS surprise (actual - estimate)
    eps_surprise_percent DECIMAL(10, 4),    -- EPS surprise percentage
    
    revenue_estimate DECIMAL(20, 2),        -- Revenue estimate
    revenue_actual DECIMAL(20, 2),          -- Actual revenue
    revenue_surprise DECIMAL(20, 2),        -- Revenue surprise
    revenue_surprise_percent DECIMAL(10, 4), -- Revenue surprise percentage
    
    -- Guidance (if provided)
    guidance_eps_low DECIMAL(10, 4),        -- EPS guidance lower bound
    guidance_eps_high DECIMAL(10, 4),       -- EPS guidance upper bound
    guidance_revenue_low DECIMAL(20, 2),    -- Revenue guidance lower bound
    guidance_revenue_high DECIMAL(20, 2),   -- Revenue guidance upper bound
    
    -- Timing and metadata
    announcement_time VARCHAR(20),           -- 'before_market', 'after_market', 'during_market'
    conference_call_time TIMESTAMPTZ,       -- Conference call time
    currency VARCHAR(10) DEFAULT 'USD',
    data_source VARCHAR(50) DEFAULT 'EODHD',
    earnings_metadata JSONB,                 -- Additional data
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('earnings_data', 'time', if_not_exists => TRUE);

-- Unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_earnings_unique 
    ON earnings_data (symbol, fiscal_year, reporting_period);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_earnings_symbol_time 
    ON earnings_data (symbol, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_earnings_surprise 
    ON earnings_data (eps_surprise_percent, time DESC);

-- ============================================================================
-- ECONOMIC INDICATORS TABLE (HYPERTABLE)
-- Macroeconomic data (GDP, CPI, unemployment, interest rates, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS economic_indicators (
    time TIMESTAMPTZ NOT NULL,               -- Data release date
    indicator_code VARCHAR(50) NOT NULL,     -- Indicator code (e.g., 'US_GDP', 'US_CPI', 'FED_RATE')
    indicator_name VARCHAR(200) NOT NULL,    -- Human-readable name
    country VARCHAR(10) NOT NULL,            -- Country code (US, EU, JP, etc.)
    
    -- Data values
    value DECIMAL(20, 6),                    -- Indicator value
    previous_value DECIMAL(20, 6),          -- Previous period value
    change_value DECIMAL(20, 6),            -- Absolute change
    change_percent DECIMAL(10, 4),          -- Percentage change
    
    -- Forecasts and estimates
    forecast DECIMAL(20, 6),                -- Analyst forecast
    surprise DECIMAL(20, 6),                -- Actual vs forecast surprise
    
    -- Metadata
    frequency VARCHAR(20),                   -- 'monthly', 'quarterly', 'annually'
    unit VARCHAR(50),                       -- Unit of measurement
    data_source VARCHAR(50) DEFAULT 'EODHD',
    release_importance VARCHAR(10),         -- 'low', 'medium', 'high'
    indicator_metadata JSONB,               -- Additional data
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('economic_indicators', 'time', if_not_exists => TRUE);

-- Unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_economic_unique 
    ON economic_indicators (indicator_code, time);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_economic_country_time 
    ON economic_indicators (country, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_economic_indicator_time 
    ON economic_indicators (indicator_code, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_economic_importance 
    ON economic_indicators (release_importance, time DESC);

-- Enable compression
ALTER TABLE economic_indicators SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'country, indicator_code',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('economic_indicators', INTERVAL '2 years', if_not_exists => TRUE);

-- ============================================================================
-- INSIDER TRANSACTIONS TABLE (HYPERTABLE)
-- Corporate insider buy/sell transactions
-- ============================================================================
CREATE TABLE IF NOT EXISTS insider_transactions (
    time TIMESTAMPTZ NOT NULL,               -- Transaction date
    symbol VARCHAR(20) NOT NULL,             -- Stock symbol
    insider_name VARCHAR(200),               -- Name of insider
    insider_title VARCHAR(200),             -- Title/position
    
    -- Transaction details
    transaction_type VARCHAR(20) NOT NULL,   -- 'BUY', 'SELL', 'OPTION_EXERCISE', etc.
    shares_traded DECIMAL(20, 0),           -- Number of shares
    price_per_share DECIMAL(10, 4),         -- Transaction price per share
    total_value DECIMAL(20, 2),             -- Total transaction value
    
    -- Ownership after transaction
    shares_owned_after DECIMAL(20, 0),      -- Shares owned after transaction
    ownership_percent DECIMAL(10, 6),       -- Percentage ownership after transaction
    
    -- Metadata
    sec_filing_type VARCHAR(20),            -- Form type (Form 4, Form 5, etc.)
    filing_date TIMESTAMPTZ,                -- SEC filing date
    data_source VARCHAR(50) DEFAULT 'EODHD',
    transaction_metadata JSONB,             -- Additional data
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('insider_transactions', 'time', if_not_exists => TRUE);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_insider_symbol_time 
    ON insider_transactions (symbol, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_insider_type_time 
    ON insider_transactions (transaction_type, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_insider_value 
    ON insider_transactions (total_value, time DESC);

-- ============================================================================
-- NEWS SENTIMENT TABLE (HYPERTABLE)
-- News articles and sentiment analysis for market analysis
-- ============================================================================
CREATE TABLE IF NOT EXISTS news_sentiment (
    time TIMESTAMPTZ NOT NULL,               -- Publication time
    article_id VARCHAR(100) NOT NULL,        -- Unique article identifier
    symbol VARCHAR(20),                      -- Related symbol (if applicable)
    
    -- Content
    title TEXT NOT NULL,                     -- Article title
    content TEXT,                           -- Article content (if available)
    summary TEXT,                           -- Article summary
    author VARCHAR(200),                    -- Author name
    source VARCHAR(100),                    -- News source
    url TEXT,                              -- Article URL
    
    -- Sentiment Analysis
    sentiment_score DECIMAL(5, 4),          -- Sentiment score (-1 to 1)
    sentiment_label VARCHAR(20),            -- 'positive', 'negative', 'neutral'
    confidence_score DECIMAL(5, 4),         -- Confidence in sentiment (0 to 1)
    
    -- Topic Classification
    topics TEXT[],                          -- Array of topics/tags
    entities TEXT[],                        -- Named entities mentioned
    keywords TEXT[],                        -- Key terms
    
    -- Embeddings for similarity search (using pgvector)
    content_embedding vector(384),          -- Sentence transformer embedding
    
    -- Metadata
    language VARCHAR(10) DEFAULT 'en',
    data_source VARCHAR(50) DEFAULT 'EODHD',
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    news_metadata JSONB,                    -- Additional data
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('news_sentiment', 'time', if_not_exists => TRUE);

-- Unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_unique 
    ON news_sentiment (article_id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_news_symbol_time 
    ON news_sentiment (symbol, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_news_sentiment_time 
    ON news_sentiment (sentiment_score, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_news_source_time 
    ON news_sentiment (source, time DESC);

-- Vector similarity index for embeddings
CREATE INDEX IF NOT EXISTS idx_news_embedding 
    ON news_sentiment USING ivfflat (content_embedding vector_cosine_ops);

-- ============================================================================
-- CORRELATION ANALYSIS TABLE
-- Pre-computed correlations between assets and economic indicators
-- ============================================================================
CREATE TABLE IF NOT EXISTS correlation_analysis (
    id SERIAL PRIMARY KEY,
    asset1_type VARCHAR(50) NOT NULL,        -- 'stock', 'crypto', 'economic_indicator'
    asset1_symbol VARCHAR(50) NOT NULL,      -- Symbol or indicator code
    asset2_type VARCHAR(50) NOT NULL,
    asset2_symbol VARCHAR(50) NOT NULL,
    
    -- Correlation metrics
    correlation_1d DECIMAL(5, 4),           -- 1-day return correlation
    correlation_7d DECIMAL(5, 4),           -- 7-day return correlation
    correlation_30d DECIMAL(5, 4),          -- 30-day return correlation
    correlation_90d DECIMAL(5, 4),          -- 90-day return correlation
    
    -- Rolling statistics
    correlation_mean DECIMAL(5, 4),         -- Mean correlation over period
    correlation_std DECIMAL(5, 4),          -- Standard deviation of correlation
    correlation_min DECIMAL(5, 4),          -- Minimum correlation
    correlation_max DECIMAL(5, 4),          -- Maximum correlation
    
    -- Metadata
    lookback_days INTEGER DEFAULT 252,      -- Days used for calculation
    calculation_date TIMESTAMPTZ NOT NULL,  -- When correlation was calculated
    data_points_used INTEGER,               -- Number of data points in calculation
    statistical_significance DECIMAL(5, 4), -- P-value of correlation
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_correlation_assets 
    ON correlation_analysis (asset1_symbol, asset2_symbol);
    
CREATE INDEX IF NOT EXISTS idx_correlation_date 
    ON correlation_analysis (calculation_date DESC);

-- ============================================================================
-- CONTINUOUS AGGREGATES FOR FUNDAMENTALS
-- Pre-computed views for faster queries
-- ============================================================================

-- Quarterly earnings summary per symbol
CREATE MATERIALIZED VIEW IF NOT EXISTS quarterly_earnings_summary
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

-- Refresh policy for earnings summary
SELECT add_continuous_aggregate_policy('quarterly_earnings_summary',
    start_offset => INTERVAL '1 year',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Monthly economic indicators summary
CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_economic_summary
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

-- Refresh policy for economic summary
SELECT add_continuous_aggregate_policy('monthly_economic_summary',
    start_offset => INTERVAL '2 years',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- ============================================================================
-- FUNCTIONS FOR FUNDAMENTALS DATA
-- ============================================================================

-- Function to calculate financial ratios
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
    -- Profit margin
    IF p_revenue > 0 THEN
        ratios := jsonb_set(ratios, '{profit_margin}', to_jsonb((p_net_income / p_revenue)::DECIMAL(10,4)));
    END IF;
    
    -- Return on assets (ROA)
    IF p_total_assets > 0 THEN
        ratios := jsonb_set(ratios, '{roa}', to_jsonb((p_net_income / p_total_assets)::DECIMAL(10,4)));
    END IF;
    
    -- Return on equity (ROE)
    IF p_shareholders_equity > 0 THEN
        ratios := jsonb_set(ratios, '{roe}', to_jsonb((p_net_income / p_shareholders_equity)::DECIMAL(10,4)));
    END IF;
    
    -- Debt to equity ratio
    IF p_shareholders_equity > 0 THEN
        ratios := jsonb_set(ratios, '{debt_to_equity}', to_jsonb((p_total_debt / p_shareholders_equity)::DECIMAL(10,4)));
    END IF;
    
    RETURN ratios;
END;
$$ LANGUAGE plpgsql;

-- Function to get latest fundamentals for a symbol
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
-- DATA RETENTION POLICIES
-- Automatically drop old data to manage storage
-- ============================================================================

-- Keep insider transactions for 5 years
SELECT add_retention_policy('insider_transactions', INTERVAL '5 years', if_not_exists => TRUE);

-- Keep news sentiment for 2 years
SELECT add_retention_policy('news_sentiment', INTERVAL '2 years', if_not_exists => TRUE);

-- Keep economic indicators for 10 years (important historical data)
-- SELECT add_retention_policy('economic_indicators', INTERVAL '10 years', if_not_exists => TRUE);

-- ============================================================================
-- SAMPLE DATA INSERTION
-- Insert some sample data for testing
-- ============================================================================

-- Sample economic indicators
INSERT INTO economic_indicators (
    time, indicator_code, indicator_name, country, value, frequency, unit, release_importance
) VALUES 
    (NOW() - INTERVAL '1 month', 'US_GDP', 'Gross Domestic Product', 'US', 26854.60, 'quarterly', 'Billions USD', 'high'),
    (NOW() - INTERVAL '1 month', 'US_CPI', 'Consumer Price Index', 'US', 307.89, 'monthly', 'Index', 'high'),
    (NOW() - INTERVAL '1 month', 'FED_RATE', 'Federal Funds Rate', 'US', 5.25, 'meeting', 'Percent', 'high'),
    (NOW() - INTERVAL '1 month', 'US_UNEMPLOYMENT', 'Unemployment Rate', 'US', 3.7, 'monthly', 'Percent', 'medium')
ON CONFLICT (indicator_code, time) DO NOTHING;

-- ============================================================================
-- GRANTS AND PERMISSIONS
-- ============================================================================
-- Grant permissions to application user (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fks_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO fks_user;

-- ============================================================================
-- COMMENTS ON TABLES
-- ============================================================================
COMMENT ON TABLE company_fundamentals IS 'Quarterly and annual financial data for companies from earnings reports and SEC filings';
COMMENT ON TABLE earnings_data IS 'Earnings announcements with estimates vs actuals and surprise analysis';  
COMMENT ON TABLE economic_indicators IS 'Macroeconomic indicators including GDP, CPI, interest rates, and employment data';
COMMENT ON TABLE insider_transactions IS 'Corporate insider buy/sell transactions from SEC filings';
COMMENT ON TABLE news_sentiment IS 'News articles with sentiment analysis and embeddings for similarity search';
COMMENT ON TABLE correlation_analysis IS 'Pre-computed correlations between assets and economic indicators';

-- ============================================================================
-- END OF FUNDAMENTALS SCHEMA
-- ============================================================================