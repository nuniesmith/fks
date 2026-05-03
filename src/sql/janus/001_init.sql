-- =============================================================================
-- 001-init-janus.sql — JANUS PostgreSQL initialisation
-- =============================================================================
-- Creates the schema required by the JANUS backward module.
--
-- IMPORTANT: This script must stay in sync with the sqlx migrations in:
--   src/janus/services/backward/migrations/
--
-- Runs automatically on first container start (empty data volume).
-- Subsequent starts skip initdb entirely (volume already populated).
--
-- Manual re-creation (e.g. after `./run.sh fresh --reset-volumes`):
--   docker compose exec postgres psql -U postgres \
--     -f /docker-entrypoint-initdb.d/001-init-janus.sql
--
-- Location: src/sql/janus/001_init.sql
-- =============================================================================

\getenv janus_db  JANUS_DB
\getenv fks_user  POSTGRES_USER

\connect :janus_db

-- Required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Database-level privileges
GRANT ALL PRIVILEGES ON DATABASE :janus_db TO :fks_user;

-- Schema ownership & privileges
ALTER SCHEMA public OWNER TO :fks_user;
GRANT  ALL PRIVILEGES ON SCHEMA public TO :fks_user;

-- Default privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO :fks_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO :fks_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO :fks_user;

-- =============================================================================
-- Migration 0001: signals
-- =============================================================================

CREATE TABLE IF NOT EXISTS signals (
    signal_id               UUID PRIMARY KEY,

    -- Metadata
    symbol                  VARCHAR(50)       NOT NULL,
    signal_type             VARCHAR(10)       NOT NULL CHECK (signal_type IN ('Buy', 'Sell', 'Hold')),
    timeframe               VARCHAR(10)       NOT NULL,

    -- Quality
    confidence              DOUBLE PRECISION  NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    strength                DOUBLE PRECISION  NOT NULL CHECK (strength   BETWEEN 0 AND 1),

    -- Timing
    timestamp               TIMESTAMPTZ       NOT NULL,
    created_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    -- Pricing
    entry_price             DECIMAL(20, 8),
    stop_loss               DECIMAL(20, 8),
    take_profit             DECIMAL(20, 8),

    -- Risk
    position_size           DECIMAL(20, 8),
    risk_amount             DECIMAL(20, 8),
    risk_reward_ratio       DOUBLE PRECISION,

    -- Source
    source_type             VARCHAR(50)       NOT NULL,
    source_name             VARCHAR(100),

    -- Strategy
    strategy_name           VARCHAR(100),
    strategy_score          DOUBLE PRECISION,

    -- ML model (optional)
    model_name              VARCHAR(100),
    model_version           VARCHAR(50),
    model_confidence        DOUBLE PRECISION,

    -- Flexible payload
    indicators              JSONB,
    metadata                JSONB,

    -- Lifecycle
    status                  VARCHAR(20)       DEFAULT 'generated'
                                CHECK (status IN ('generated', 'validated', 'executed', 'cancelled', 'expired')),
    filtered                BOOLEAN           DEFAULT FALSE,
    is_backtest             BOOLEAN           DEFAULT FALSE,

    -- Execution
    executed_at             TIMESTAMPTZ,
    execution_price         DECIMAL(20, 8),

    -- Settlement
    closed_at               TIMESTAMPTZ,
    close_price             DECIMAL(20, 8),
    pnl                     DECIMAL(20, 8),
    pnl_percentage          DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol            ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp         ON signals(timestamp         DESC);
CREATE INDEX IF NOT EXISTS idx_signals_created_at        ON signals(created_at        DESC);
CREATE INDEX IF NOT EXISTS idx_signals_confidence        ON signals(confidence        DESC);
CREATE INDEX IF NOT EXISTS idx_signals_signal_type       ON signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_status            ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_timeframe         ON signals(timeframe);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp  ON signals(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_indicators        ON signals USING GIN (indicators);
CREATE INDEX IF NOT EXISTS idx_signals_metadata          ON signals USING GIN (metadata);

-- =============================================================================
-- Migration 002: portfolios, positions, position_updates, portfolio_snapshots
-- =============================================================================

CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id            UUID PRIMARY KEY  DEFAULT gen_random_uuid(),
    name                    VARCHAR(100)      NOT NULL,
    account_id              VARCHAR(100)      NOT NULL,

    -- Balances
    initial_balance         DECIMAL(20, 8)    NOT NULL,
    current_balance         DECIMAL(20, 8)    NOT NULL,

    -- Performance
    total_pnl               DECIMAL(20, 8)    DEFAULT 0,
    total_pnl_percentage    DOUBLE PRECISION  DEFAULT 0,
    daily_pnl               DECIMAL(20, 8)    DEFAULT 0,
    daily_pnl_percentage    DOUBLE PRECISION  DEFAULT 0,

    -- Risk
    max_drawdown            DOUBLE PRECISION  DEFAULT 0,
    current_drawdown        DOUBLE PRECISION  DEFAULT 0,
    sharpe_ratio            DOUBLE PRECISION,

    -- Exposure
    total_exposure          DECIMAL(20, 8)    DEFAULT 0,
    exposure_percentage     DOUBLE PRECISION  DEFAULT 0,

    -- Position counts
    active_positions        INT               DEFAULT 0,
    total_positions_opened  INT               DEFAULT 0,
    winning_positions       INT               DEFAULT 0,
    losing_positions        INT               DEFAULT 0,

    -- Timing
    created_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    last_reset_at           TIMESTAMPTZ,

    -- Lifecycle
    status                  VARCHAR(20)       DEFAULT 'active'
                                CHECK (status IN ('active', 'inactive', 'suspended', 'archived')),

    -- Config
    risk_config             JSONB,

    UNIQUE (account_id, name)
);

CREATE TABLE IF NOT EXISTS positions (
    position_id             UUID PRIMARY KEY  DEFAULT gen_random_uuid(),
    portfolio_id            UUID              NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    signal_id               UUID              REFERENCES signals(signal_id),

    -- Identity
    symbol                  VARCHAR(50)       NOT NULL,
    side                    VARCHAR(10)       NOT NULL CHECK (side IN ('Long', 'Short')),

    -- Entry
    entry_price             DECIMAL(20, 8)    NOT NULL,
    quantity                DECIMAL(20, 8)    NOT NULL,
    position_value          DECIMAL(20, 8)    NOT NULL,

    -- Risk parameters
    stop_loss               DECIMAL(20, 8),
    take_profit             DECIMAL(20, 8),
    risk_amount             DECIMAL(20, 8),
    risk_percentage         DOUBLE PRECISION,
    risk_reward_ratio       DOUBLE PRECISION,

    -- Live state
    current_price           DECIMAL(20, 8),
    unrealized_pnl          DECIMAL(20, 8),
    unrealized_pnl_percentage DOUBLE PRECISION,

    -- Timing
    opened_at               TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    closed_at               TIMESTAMPTZ,

    -- Exit
    exit_price              DECIMAL(20, 8),
    realized_pnl            DECIMAL(20, 8),
    realized_pnl_percentage DOUBLE PRECISION,
    exit_reason             VARCHAR(50)
                                CHECK (exit_reason IN ('stop_loss', 'take_profit', 'manual',
                                                       'trailing_stop', 'time_exit', 'signal')),

    -- Lifecycle
    status                  VARCHAR(20)       DEFAULT 'open'
                                CHECK (status IN ('open', 'closed', 'partially_closed')),

    metadata                JSONB,
    notes                   TEXT
);

CREATE TABLE IF NOT EXISTS position_updates (
    update_id               BIGSERIAL PRIMARY KEY,
    position_id             UUID              NOT NULL REFERENCES positions(position_id) ON DELETE CASCADE,

    -- Update
    update_type             VARCHAR(20)       NOT NULL
                                CHECK (update_type IN ('open', 'update', 'close', 'stop_update', 'tp_update')),
    price                   DECIMAL(20, 8)    NOT NULL,
    stop_loss               DECIMAL(20, 8),
    take_profit             DECIMAL(20, 8),
    unrealized_pnl          DECIMAL(20, 8),
    unrealized_pnl_percentage DOUBLE PRECISION,

    updated_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    metadata                JSONB
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_id             BIGSERIAL PRIMARY KEY,
    portfolio_id            UUID              NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,

    -- Period
    snapshot_date           DATE              NOT NULL,
    snapshot_time           TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    -- Balances
    balance                 DECIMAL(20, 8)    NOT NULL,
    equity                  DECIMAL(20, 8)    NOT NULL,

    -- Performance
    daily_pnl               DECIMAL(20, 8),
    daily_pnl_percentage    DOUBLE PRECISION,
    cumulative_pnl          DECIMAL(20, 8),
    cumulative_pnl_percentage DOUBLE PRECISION,

    -- Risk
    exposure                DECIMAL(20, 8),
    exposure_percentage     DOUBLE PRECISION,
    drawdown                DOUBLE PRECISION,
    active_positions        INT,

    metadata                JSONB,

    UNIQUE (portfolio_id, snapshot_date)
);

-- Indexes — portfolios
CREATE INDEX IF NOT EXISTS idx_portfolios_account_id     ON portfolios(account_id);
CREATE INDEX IF NOT EXISTS idx_portfolios_status         ON portfolios(status);
CREATE INDEX IF NOT EXISTS idx_portfolios_created_at     ON portfolios(created_at DESC);

-- Indexes — positions
CREATE INDEX IF NOT EXISTS idx_positions_portfolio_id    ON positions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_positions_signal_id       ON positions(signal_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol          ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status          ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_opened_at       ON positions(opened_at  DESC);
CREATE INDEX IF NOT EXISTS idx_positions_closed_at       ON positions(closed_at  DESC);
CREATE INDEX IF NOT EXISTS idx_positions_portfolio_status ON positions(portfolio_id, status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol_status   ON positions(symbol, status);

-- Indexes — position_updates
CREATE INDEX IF NOT EXISTS idx_position_updates_position_id ON position_updates(position_id);
CREATE INDEX IF NOT EXISTS idx_position_updates_updated_at  ON position_updates(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_position_updates_type        ON position_updates(update_type);

-- Indexes — portfolio_snapshots
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_portfolio_id   ON portfolio_snapshots(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_date           ON portfolio_snapshots(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_portfolio_date ON portfolio_snapshots(portfolio_id, snapshot_date DESC);

-- ---------------------------------------------------------------------------
-- Shared trigger function: stamp updated_at on any row mutation.
-- Used by both portfolios and positions triggers below.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS portfolio_updated_at_trigger ON portfolios;
CREATE TRIGGER portfolio_updated_at_trigger
    BEFORE UPDATE ON portfolios
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS position_updated_at_trigger ON positions;
CREATE TRIGGER position_updated_at_trigger
    BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Trigger function: keep portfolio aggregate metrics in sync with positions.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sync_portfolio_metrics()
RETURNS TRIGGER AS $$
DECLARE
    v_portfolio_id      UUID;
    v_total_exposure    DECIMAL(20, 8);
    v_active_count      INT;
BEGIN
    v_portfolio_id := COALESCE(NEW.portfolio_id, OLD.portfolio_id);

    SELECT
        COALESCE(SUM(position_value), 0),
        COUNT(*)
    INTO v_total_exposure, v_active_count
    FROM positions
    WHERE portfolio_id = v_portfolio_id
      AND status = 'open';

    UPDATE portfolios
    SET
        total_exposure      = v_total_exposure,
        exposure_percentage = CASE
                                  WHEN current_balance > 0
                                  THEN (v_total_exposure / current_balance) * 100
                                  ELSE 0
                              END,
        active_positions    = v_active_count,
        updated_at          = NOW()
    WHERE portfolio_id = v_portfolio_id;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS position_metrics_trigger ON positions;
CREATE TRIGGER position_metrics_trigger
    AFTER INSERT OR UPDATE OR DELETE ON positions
    FOR EACH ROW EXECUTE FUNCTION sync_portfolio_metrics();

-- =============================================================================
-- Migration 003: trade_metrics, performance_stats, risk_metrics,
--               signal_performance, strategy_performance
-- =============================================================================

CREATE TABLE IF NOT EXISTS trade_metrics (
    metric_id               BIGSERIAL PRIMARY KEY,
    position_id             UUID              NOT NULL REFERENCES positions(position_id)  ON DELETE CASCADE,
    signal_id               UUID              REFERENCES signals(signal_id),
    portfolio_id            UUID              NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,

    -- Identity
    symbol                  VARCHAR(50)       NOT NULL,
    side                    VARCHAR(10)       NOT NULL,

    -- Trade
    entry_price             DECIMAL(20, 8)    NOT NULL,
    exit_price              DECIMAL(20, 8)    NOT NULL,
    quantity                DECIMAL(20, 8)    NOT NULL,

    -- Risk
    initial_risk            DECIMAL(20, 8),
    actual_risk             DECIMAL(20, 8),
    risk_reward_ratio       DOUBLE PRECISION,

    -- PnL
    gross_pnl               DECIMAL(20, 8)    NOT NULL,
    gross_pnl_percentage    DOUBLE PRECISION  NOT NULL,
    net_pnl                 DECIMAL(20, 8),
    net_pnl_percentage      DOUBLE PRECISION,
    commission              DECIMAL(20, 8)    DEFAULT 0,
    slippage                DECIMAL(20, 8)    DEFAULT 0,

    -- Duration
    entry_time              TIMESTAMPTZ       NOT NULL,
    exit_time               TIMESTAMPTZ       NOT NULL,
    holding_duration_seconds BIGINT,
    holding_duration_bars   INT,

    -- Exit
    exit_reason             VARCHAR(50),
    hit_stop_loss           BOOLEAN           DEFAULT FALSE,
    hit_take_profit         BOOLEAN           DEFAULT FALSE,

    -- Market conditions
    entry_volatility        DOUBLE PRECISION,
    entry_atr               DECIMAL(20, 8),
    entry_rsi               DOUBLE PRECISION,
    exit_volatility         DOUBLE PRECISION,
    exit_atr                DECIMAL(20, 8),
    exit_rsi                DOUBLE PRECISION,

    -- Excursion
    max_favorable_excursion     DECIMAL(20, 8),
    max_favorable_excursion_pct DOUBLE PRECISION,
    max_adverse_excursion       DECIMAL(20, 8),
    max_adverse_excursion_pct   DOUBLE PRECISION,

    metadata                JSONB,
    created_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS performance_stats (
    stat_id                 BIGSERIAL PRIMARY KEY,
    portfolio_id            UUID              NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    symbol                  VARCHAR(50),   -- NULL = portfolio-wide
    timeframe               VARCHAR(20),   -- 'daily' | 'weekly' | 'monthly' | 'all_time'

    -- Period
    period_start            TIMESTAMPTZ       NOT NULL,
    period_end              TIMESTAMPTZ       NOT NULL,

    -- Trade counts
    total_trades            INT               DEFAULT 0,
    winning_trades          INT               DEFAULT 0,
    losing_trades           INT               DEFAULT 0,
    breakeven_trades        INT               DEFAULT 0,
    win_rate                DOUBLE PRECISION,
    loss_rate               DOUBLE PRECISION,

    -- PnL
    gross_profit            DECIMAL(20, 8)    DEFAULT 0,
    gross_loss              DECIMAL(20, 8)    DEFAULT 0,
    net_profit              DECIMAL(20, 8)    DEFAULT 0,
    avg_win                 DECIMAL(20, 8),
    avg_loss                DECIMAL(20, 8),
    avg_win_pct             DOUBLE PRECISION,
    avg_loss_pct            DOUBLE PRECISION,
    largest_win             DECIMAL(20, 8),
    largest_loss            DECIMAL(20, 8),
    largest_win_pct         DOUBLE PRECISION,
    largest_loss_pct        DOUBLE PRECISION,

    -- Streaks
    max_consecutive_wins    INT,
    max_consecutive_losses  INT,
    current_streak          INT,
    current_streak_type     VARCHAR(10),   -- 'win' | 'loss'

    -- Ratios & expectancy
    profit_factor           DOUBLE PRECISION,
    expectancy              DECIMAL(20, 8),
    expectancy_pct          DOUBLE PRECISION,
    sharpe_ratio            DOUBLE PRECISION,
    sortino_ratio           DOUBLE PRECISION,
    calmar_ratio            DOUBLE PRECISION,
    avg_r_multiple          DOUBLE PRECISION,
    recovery_factor         DOUBLE PRECISION,

    -- Drawdown
    max_drawdown                DOUBLE PRECISION,
    max_drawdown_duration_days  INT,
    avg_drawdown                DOUBLE PRECISION,

    -- Holding time
    avg_holding_duration_seconds    BIGINT,
    median_holding_duration_seconds BIGINT,

    -- Volume & costs
    total_volume            DECIMAL(20, 8),
    total_commission        DECIMAL(20, 8),

    metadata                JSONB,
    calculated_at           TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    UNIQUE (portfolio_id, symbol, timeframe, period_start)
);

CREATE TABLE IF NOT EXISTS risk_metrics (
    risk_id                 BIGSERIAL PRIMARY KEY,
    portfolio_id            UUID              NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    measured_at             TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    -- Balances
    portfolio_value         DECIMAL(20, 8)    NOT NULL,
    cash_balance            DECIMAL(20, 8)    NOT NULL,

    -- Exposure
    total_exposure          DECIMAL(20, 8),
    exposure_percentage     DOUBLE PRECISION,
    gross_exposure          DECIMAL(20, 8),
    net_exposure            DECIMAL(20, 8),

    -- Positions
    active_positions        INT               DEFAULT 0,
    max_position_size       DECIMAL(20, 8),
    avg_position_size       DECIMAL(20, 8),

    -- Concentration
    largest_position_pct    DOUBLE PRECISION,
    top_5_concentration_pct DOUBLE PRECISION,

    -- Correlation
    avg_correlation         DOUBLE PRECISION,
    max_correlation         DOUBLE PRECISION,

    -- Heat & risk amounts
    portfolio_heat          DOUBLE PRECISION,
    total_risk_amount       DECIMAL(20, 8),
    avg_risk_per_position   DECIMAL(20, 8),
    max_risk_per_position   DECIMAL(20, 8),

    -- VaR
    var_95                  DECIMAL(20, 8),
    var_99                  DECIMAL(20, 8),
    cvar_95                 DECIMAL(20, 8),

    -- Volatility
    portfolio_volatility    DOUBLE PRECISION,
    realized_volatility     DOUBLE PRECISION,

    -- Drawdown
    current_drawdown        DOUBLE PRECISION,
    drawdown_from_peak      DECIMAL(20, 8),
    peak_portfolio_value    DECIMAL(20, 8),

    limits_exceeded         JSONB,
    metadata                JSONB
);

CREATE TABLE IF NOT EXISTS signal_performance (
    performance_id          BIGSERIAL PRIMARY KEY,
    signal_id               UUID              NOT NULL REFERENCES signals(signal_id)   ON DELETE CASCADE,
    position_id             UUID              REFERENCES positions(position_id),

    -- Signal identity
    symbol                  VARCHAR(50)       NOT NULL,
    signal_type             VARCHAR(10)       NOT NULL,
    timeframe               VARCHAR(10)       NOT NULL,
    signal_confidence       DOUBLE PRECISION,
    signal_strength         DOUBLE PRECISION,
    source_type             VARCHAR(50),
    strategy_name           VARCHAR(100),
    model_name              VARCHAR(100),

    -- Execution
    was_executed            BOOLEAN           DEFAULT FALSE,
    execution_delay_seconds INT,
    actual_entry_price      DECIMAL(20, 8),
    slippage                DECIMAL(20, 8),
    slippage_pct            DOUBLE PRECISION,

    -- Outcome
    outcome                 VARCHAR(20),   -- 'win' | 'loss' | 'breakeven' | 'pending' | 'not_executed'
    pnl                     DECIMAL(20, 8),
    pnl_percentage          DOUBLE PRECISION,
    entry_accuracy          DOUBLE PRECISION,
    stop_hit                BOOLEAN,
    target_hit              BOOLEAN,

    -- Timing
    signal_timestamp        TIMESTAMPTZ       NOT NULL,
    execution_timestamp     TIMESTAMPTZ,
    exit_timestamp          TIMESTAMPTZ,

    metadata                JSONB,
    created_at              TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_performance (
    strategy_perf_id        BIGSERIAL PRIMARY KEY,
    strategy_name           VARCHAR(100)      NOT NULL,
    portfolio_id            UUID              REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,

    -- Period
    period_start            TIMESTAMPTZ       NOT NULL,
    period_end              TIMESTAMPTZ       NOT NULL,
    timeframe               VARCHAR(20),

    -- Signal metrics
    total_signals           INT               DEFAULT 0,
    signals_executed        INT               DEFAULT 0,
    signals_filtered        INT               DEFAULT 0,
    execution_rate          DOUBLE PRECISION,

    -- Trade metrics
    total_trades            INT               DEFAULT 0,
    winning_trades          INT               DEFAULT 0,
    losing_trades           INT               DEFAULT 0,
    win_rate                DOUBLE PRECISION,
    total_pnl               DECIMAL(20, 8)    DEFAULT 0,
    avg_pnl                 DECIMAL(20, 8),
    profit_factor           DOUBLE PRECISION,

    -- Quality
    avg_confidence          DOUBLE PRECISION,
    avg_strength            DOUBLE PRECISION,
    sharpe_ratio            DOUBLE PRECISION,

    metadata                JSONB,
    calculated_at           TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    UNIQUE (strategy_name, portfolio_id, period_start, timeframe)
);

-- Indexes — trade_metrics
CREATE INDEX IF NOT EXISTS idx_trade_metrics_position_id  ON trade_metrics(position_id);
CREATE INDEX IF NOT EXISTS idx_trade_metrics_signal_id    ON trade_metrics(signal_id);
CREATE INDEX IF NOT EXISTS idx_trade_metrics_portfolio_id ON trade_metrics(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_trade_metrics_symbol       ON trade_metrics(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_metrics_entry_time   ON trade_metrics(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trade_metrics_exit_time    ON trade_metrics(exit_time  DESC);

-- Indexes — performance_stats
CREATE INDEX IF NOT EXISTS idx_performance_stats_portfolio_id    ON performance_stats(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_performance_stats_symbol          ON performance_stats(symbol);
CREATE INDEX IF NOT EXISTS idx_performance_stats_timeframe       ON performance_stats(timeframe);
CREATE INDEX IF NOT EXISTS idx_performance_stats_period          ON performance_stats(period_start DESC, period_end DESC);
CREATE INDEX IF NOT EXISTS idx_performance_stats_portfolio_period ON performance_stats(portfolio_id, period_start DESC);

-- Indexes — risk_metrics
CREATE INDEX IF NOT EXISTS idx_risk_metrics_portfolio_id   ON risk_metrics(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_risk_metrics_measured_at    ON risk_metrics(measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_metrics_portfolio_time ON risk_metrics(portfolio_id, measured_at DESC);

-- Indexes — signal_performance
CREATE INDEX IF NOT EXISTS idx_signal_performance_signal_id  ON signal_performance(signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_performance_position_id ON signal_performance(position_id);
CREATE INDEX IF NOT EXISTS idx_signal_performance_symbol     ON signal_performance(symbol);
CREATE INDEX IF NOT EXISTS idx_signal_performance_strategy   ON signal_performance(strategy_name);
CREATE INDEX IF NOT EXISTS idx_signal_performance_timestamp  ON signal_performance(signal_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signal_performance_outcome    ON signal_performance(outcome);

-- Indexes — strategy_performance
CREATE INDEX IF NOT EXISTS idx_strategy_performance_name        ON strategy_performance(strategy_name);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_portfolio   ON strategy_performance(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_period      ON strategy_performance(period_start DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_name_period ON strategy_performance(strategy_name, period_start DESC);

-- =============================================================================
-- Migration tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(50) PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_migrations (version, description) VALUES
    ('0001',  'Create signals table'),
    ('002',  'Create portfolio tables'),
    ('003',  'Create metrics tables'),
    ('init', 'Applied via PostgreSQL init script')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
-- Final privilege sweep (covers objects created above)
-- =============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;

-- =============================================================================
-- Table comments
-- =============================================================================

COMMENT ON TABLE signals              IS 'Trading signals generated by the JANUS service';
COMMENT ON TABLE portfolios           IS 'Portfolio configurations and aggregate performance';
COMMENT ON TABLE positions            IS 'Individual trading positions';
COMMENT ON TABLE position_updates     IS 'Audit trail of position modifications';
COMMENT ON TABLE portfolio_snapshots  IS 'Daily portfolio snapshots for historical analysis';
COMMENT ON TABLE trade_metrics        IS 'Detailed metrics for each completed trade';
COMMENT ON TABLE performance_stats    IS 'Aggregated performance statistics by time period';
COMMENT ON TABLE risk_metrics         IS 'Point-in-time portfolio risk snapshots';
COMMENT ON TABLE signal_performance   IS 'Outcome tracking for generated signals';
COMMENT ON TABLE strategy_performance IS 'Aggregate performance metrics per strategy';

-- =============================================================================
-- Done
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '✅  JANUS database schema initialised successfully';
    RAISE NOTICE '    signals, portfolios, positions, position_updates,';
    RAISE NOTICE '    portfolio_snapshots, trade_metrics, performance_stats,';
    RAISE NOTICE '    risk_metrics, signal_performance, strategy_performance';
END $$;