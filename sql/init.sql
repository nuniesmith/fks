-- TimescaleDB Initialization Script
-- This script creates the database schema for fks trading application

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- ACCOUNTS TABLE
-- Track multiple personal and prop firm accounts
-- ============================================================================
CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    account_type VARCHAR(50) NOT NULL CHECK (account_type IN ('personal', 'prop_firm')),
    broker VARCHAR(100),
    initial_balance DECIMAL(20, 8) NOT NULL,
    current_balance DECIMAL(20, 8) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USDT',
    api_key_encrypted TEXT,  -- Encrypted API credentials
    api_secret_encrypted TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    account_metadata JSONB  -- Additional account-specific data
);

CREATE INDEX idx_accounts_active ON accounts(is_active);
CREATE INDEX idx_accounts_type ON accounts(account_type);

-- ============================================================================
-- OHLCV DATA TABLE (HYPERTABLE)
-- Time-series data for all symbols and timeframes
-- ============================================================================
CREATE TABLE IF NOT EXISTS ohlcv_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,  -- 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(30, 8) NOT NULL,
    quote_volume DECIMAL(30, 8),
    trades_count INTEGER,
    taker_buy_base_volume DECIMAL(30, 8),
    taker_buy_quote_volume DECIMAL(30, 8),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('ohlcv_data', 'time', if_not_exists => TRUE);

-- Create composite unique index to prevent duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlcv_unique 
    ON ohlcv_data (symbol, timeframe, time DESC);

-- Additional indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time 
    ON ohlcv_data (symbol, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_ohlcv_timeframe 
    ON ohlcv_data (timeframe, time DESC);

-- Enable compression (compress data older than 7 days)
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('ohlcv_data', INTERVAL '7 days', if_not_exists => TRUE);

-- ============================================================================
-- POSITIONS TABLE
-- Track current open positions per account
-- ============================================================================
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    position_type VARCHAR(10) CHECK (position_type IN ('LONG', 'SHORT')),
    quantity DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8),
    unrealized_pnl_percent DECIMAL(10, 4),
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'liquidated')),
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    position_metadata JSONB  -- Additional position data (leverage, fees, etc.)
);

CREATE INDEX idx_positions_account ON positions(account_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_opened ON positions(opened_at DESC);
CREATE INDEX idx_positions_status ON positions(status);

-- ============================================================================
-- TRADES TABLE (HYPERTABLE)
-- Complete trading history with full details
-- ============================================================================
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL,
    time TIMESTAMPTZ NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    trade_type VARCHAR(10) NOT NULL CHECK (trade_type IN ('BUY', 'SELL')),
    position_side VARCHAR(10) CHECK (position_side IN ('LONG', 'SHORT', 'BOTH')),
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8),
    fee_currency VARCHAR(10),
    realized_pnl DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    order_type VARCHAR(20),  -- MARKET, LIMIT, STOP_LOSS, etc.
    order_id VARCHAR(100),  -- Exchange order ID
    is_entry BOOLEAN DEFAULT true,
    notes TEXT,
    strategy_name VARCHAR(100),
    trade_metadata JSONB,  -- Additional trade data
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('trades', 'time', if_not_exists => TRUE);

-- Indexes for trades
CREATE INDEX IF NOT EXISTS idx_trades_account_time 
    ON trades (account_id, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time 
    ON trades (symbol, time DESC);
    
CREATE INDEX IF NOT EXISTS idx_trades_order_id 
    ON trades (order_id);

-- ============================================================================
-- BALANCE HISTORY TABLE (HYPERTABLE)
-- Track account balance over time for equity curve
-- ============================================================================
CREATE TABLE IF NOT EXISTS balance_history (
    time TIMESTAMPTZ NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    balance DECIMAL(20, 8) NOT NULL,
    equity DECIMAL(20, 8) NOT NULL,  -- Balance + unrealized PnL
    margin_used DECIMAL(20, 8),
    margin_available DECIMAL(20, 8),
    daily_pnl DECIMAL(20, 8),
    cumulative_pnl DECIMAL(20, 8),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('balance_history', 'time', if_not_exists => TRUE);

-- Indexes for balance history
CREATE INDEX IF NOT EXISTS idx_balance_account_time 
    ON balance_history (account_id, time DESC);

-- Enable compression
ALTER TABLE balance_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'account_id',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('balance_history', INTERVAL '30 days', if_not_exists => TRUE);

-- ============================================================================
-- SYNC STATUS TABLE
-- Track data synchronization state for each symbol/timeframe
-- ============================================================================
CREATE TABLE IF NOT EXISTS sync_status (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    last_sync_time TIMESTAMPTZ,
    oldest_data_time TIMESTAMPTZ,
    newest_data_time TIMESTAMPTZ,
    total_candles INTEGER DEFAULT 0,
    sync_status VARCHAR(20) DEFAULT 'pending' CHECK (sync_status IN ('pending', 'syncing', 'completed', 'error')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timeframe)
);

CREATE INDEX idx_sync_status_symbol ON sync_status(symbol);
CREATE INDEX idx_sync_status_timeframe ON sync_status(timeframe);
CREATE INDEX idx_sync_status_status ON sync_status(sync_status);

-- ============================================================================
-- INDICATORS CACHE TABLE (HYPERTABLE)
-- Pre-calculated technical indicators for performance
-- ============================================================================
CREATE TABLE IF NOT EXISTS indicators_cache (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    indicator_name VARCHAR(50) NOT NULL,
    value DECIMAL(20, 8),
    indicator_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('indicators_cache', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_indicators_lookup 
    ON indicators_cache (symbol, timeframe, indicator_name, time DESC);

-- ============================================================================
-- STRATEGY PARAMETERS TABLE
-- Store optimized strategy parameters
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategy_parameters (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20),
    timeframe VARCHAR(10),
    parameters JSONB NOT NULL,
    performance_metrics JSONB,
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_strategy_active ON strategy_parameters(is_active);
CREATE INDEX idx_strategy_name ON strategy_parameters(strategy_name);

-- ============================================================================
-- CONTINUOUS AGGREGATES (MATERIALIZED VIEWS)
-- Pre-aggregate data for faster queries
-- ============================================================================

-- Daily aggregated performance per account
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_account_performance
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    account_id,
    COUNT(*) as trades_count,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    SUM(realized_pnl) as total_pnl,
    AVG(realized_pnl) as avg_pnl,
    MAX(realized_pnl) as best_trade,
    MIN(realized_pnl) as worst_trade,
    SUM(fee) as total_fees
FROM trades
WHERE realized_pnl IS NOT NULL
GROUP BY day, account_id;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('daily_account_performance',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- ============================================================================
-- STRATEGIES TABLE
-- Trading strategy configurations
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    parameters JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'testing')),
    performance_metrics JSONB DEFAULT '{}',
    strategy_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_strategies_status ON strategies(status);
CREATE INDEX idx_strategies_name ON strategies(name);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for updated_at column on strategies
CREATE TRIGGER trigger_strategies_updated_at
BEFORE UPDATE ON strategies
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Function to update account balance
CREATE OR REPLACE FUNCTION update_account_balance()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE accounts
    SET current_balance = current_balance + NEW.realized_pnl,
        updated_at = NOW()
    WHERE id = NEW.account_id AND NEW.realized_pnl IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update account balance on trade
CREATE TRIGGER trigger_update_account_balance
AFTER INSERT ON trades
FOR EACH ROW
EXECUTE FUNCTION update_account_balance();

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at columns
CREATE TRIGGER trigger_accounts_updated_at
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_positions_updated_at
BEFORE UPDATE ON positions
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_sync_status_updated_at
BEFORE UPDATE ON sync_status
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA
-- Insert default account if none exists
-- ============================================================================
INSERT INTO accounts (name, account_type, initial_balance, current_balance, currency)
VALUES ('Default Account', 'personal', 10000.00, 10000.00, 'USDT')
ON CONFLICT (name) DO NOTHING;

-- Insert sync status records for all symbols and timeframes
DO $$
DECLARE
    sym VARCHAR(20);
    tf VARCHAR(10);
BEGIN
    FOREACH sym IN ARRAY ARRAY['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT', 'SUIUSDT']
    LOOP
        FOREACH tf IN ARRAY ARRAY['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M']
        LOOP
            INSERT INTO sync_status (symbol, timeframe, sync_status)
            VALUES (sym, tf, 'pending')
            ON CONFLICT (symbol, timeframe) DO NOTHING;
        END LOOP;
    END LOOP;
END $$;

-- ============================================================================
-- GRANTS (if needed for specific users)
-- ============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;
