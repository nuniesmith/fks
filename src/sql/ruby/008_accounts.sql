-- =============================================================================
-- ruby/008_accounts.sql — Exchange account management + routing (ACCT-A)
-- =============================================================================
-- Stores exchange API account references, asset routing rules, and the
-- profit-sweep configuration. Credentials are never stored as plaintext —
-- only a reference string pointing to the env var or secret manager key.
--
-- Must run against ruby_db.
-- Run after: 007_bots.sql
-- Status: PENDING — apply when Accounts WebUI (SVK-20) is ready
-- =============================================================================

\set ruby_db `echo "${RUBY_DB:-ruby_db}"`
\set fks_user    `echo "${POSTGRES_USER:-fks_user}"`

\connect :ruby_db

-- ---------------------------------------------------------------------------
-- exchange_accounts — one row per configured exchange API credential set.
-- Credentials are referenced, not stored. The actual API key lives in the
-- .env file or a secrets manager; credentials_ref stores the lookup key.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exchange_accounts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT        NOT NULL,  -- human label e.g. "KuCoin Futures Main"
    exchange_type    TEXT        NOT NULL CHECK (exchange_type IN (
                         'kucoin_futures', 'kucoin_spot',
                         'kraken_spot',    'kraken_futures',
                         'cryptodotcom',   'netcoins',
                         'rithmic',        'bybit'
                     )),
    -- 'sim' = paper trading | 'live' = real capital
    mode             TEXT        NOT NULL DEFAULT 'sim' CHECK (mode IN ('sim', 'live')),
    is_active        BOOLEAN     NOT NULL DEFAULT true,
    -- Credential reference. Format examples:
    --   "env:KRAKEN_API_KEY"          — reads from env var KRAKEN_API_KEY
    --   "env:ACCT_<UUID>_API_KEY"     — per-account env var written on save
    --   "vault:kv/fks/kraken"         — HashiCorp Vault path (future)
    credentials_ref  TEXT,
    -- Last 4 chars of the API key for display / verification without exposing it
    api_key_hint     TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_tested_at   TIMESTAMPTZ,
    last_test_ok     BOOLEAN
);

-- ---------------------------------------------------------------------------
-- asset_routing_rules — maps a symbol to one or more exchange accounts with
-- per-account size allocations. Drives ExecutionGate routing.
--
-- Example: route BTCUSDT 60% to kucoin_futures, 40% to kraken_futures.
-- Size percents for a symbol do not need to sum to 1.0 (partial allocation
-- is valid — unused capital stays in the account).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset_routing_rules (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol      TEXT        NOT NULL,  -- e.g. "BTC/USDT" or "MES"
    account_id  UUID        NOT NULL REFERENCES exchange_accounts(id) ON DELETE CASCADE,
    -- Fraction of the signal's notional size routed to this account (0.0–1.0)
    size_pct    NUMERIC     NOT NULL CHECK (size_pct > 0 AND size_pct <= 1),
    -- Lower priority number = higher priority (first fill attempt)
    priority    INTEGER     NOT NULL DEFAULT 0,
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    UNIQUE (symbol, account_id)
);

-- ---------------------------------------------------------------------------
-- profit_sweep_config — defines a scheduled or manual sweep of futures P&L
-- into one or more spot accounts. One config per source account.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profit_sweep_config (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Futures account to sweep FROM when P&L exceeds threshold
    source_account_id UUID REFERENCES exchange_accounts(id) ON DELETE SET NULL,
    -- USD value that triggers a sweep (e.g. 500 = sweep when futures P&L > $500)
    threshold_usd     NUMERIC     NOT NULL,
    -- 'manual' = button-only | 'scheduled' = auto at schedule_time
    mode              TEXT        NOT NULL DEFAULT 'manual' CHECK (mode IN ('manual', 'scheduled')),
    -- UTC time for daily scheduled sweeps (NULL when mode='manual')
    schedule_time     TIME,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- profit_sweep_targets — destination accounts for each sweep config.
-- allocation_pct values for a single config MUST sum to 1.0 (enforced at
-- application level — Postgres can't enforce cross-row sums natively).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profit_sweep_targets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sweep_config_id UUID        NOT NULL REFERENCES profit_sweep_config(id) ON DELETE CASCADE,
    account_id      UUID        NOT NULL REFERENCES exchange_accounts(id) ON DELETE CASCADE,
    allocation_pct  NUMERIC     NOT NULL CHECK (allocation_pct > 0 AND allocation_pct <= 1),
    UNIQUE (sweep_config_id, account_id)
);

-- ---------------------------------------------------------------------------
-- profit_sweep_log — immutable audit trail for every executed sweep.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profit_sweep_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sweep_config_id UUID        REFERENCES profit_sweep_config(id) ON DELETE SET NULL,
    triggered_by    TEXT        NOT NULL DEFAULT 'scheduled',  -- 'scheduled' | 'manual'
    total_usd       NUMERIC,
    status          TEXT        NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    error_message   TEXT,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_accounts_exchange   ON exchange_accounts(exchange_type);
CREATE INDEX IF NOT EXISTS idx_accounts_active     ON exchange_accounts(is_active);
CREATE INDEX IF NOT EXISTS idx_routing_symbol      ON asset_routing_rules(symbol);
CREATE INDEX IF NOT EXISTS idx_routing_account     ON asset_routing_rules(account_id);
CREATE INDEX IF NOT EXISTS idx_sweep_log_executed  ON profit_sweep_log(executed_at DESC);

-- Privileges
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;
