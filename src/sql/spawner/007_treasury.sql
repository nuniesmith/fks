-- =============================================================================
-- 007-treasury.sql — Treasury layer: deposit/transfer ledger + account registry
-- =============================================================================
-- Creates the transfers and accounts tables in ruby_db (see 001_init.sql for
-- why the database keeps the ruby_db name). Owned by the fks_bot_spawner
-- service (crates/spawner/), which exposes:
--   POST   /transfers      — append one signed cash-flow row
--   GET    /transfers      — list a window of the ledger
--   GET    /accounts       — list the registry (active first)
--   POST   /accounts       — UPSERT one account by account_id
--   DELETE /accounts/{id}  — soft-delete (active = FALSE)
--   GET    /profit         — net-worth drift decomposed into deposits vs profit
--
-- WHY (P0.4 / P0.5 of the treasury roadmap):
--   net_worth_snapshots (006) lets the platform SEE net worth, but net-worth
--   drift still conflates deposits with trading profit — the spot bot's own
--   status code documents "later deposits show up as PnL — no deposit ledger
--   yet". The operator DCAs cash in regularly, so decomposing
--       drift = deposits + profit
--   needs a durable cash-flow ledger (`transfers`). The `accounts` registry is
--   the source of truth for the multi-account topology (cold-BTC backbone /
--   personal-crypto / rithmic-main / prop copy-targets) that later treasury
--   phases key off.
--
-- ID CHOICE: like net_worth_snapshots (006), `transfers` is an append-only
--   series, so it uses a monotonic BIGINT identity PK rather than a UUID.
--   `accounts` is a small registry keyed by its natural id (account_id TEXT).
--
-- SECURITY: `accounts` holds NO credentials — API keys live in the encrypted
--   exchange_secrets store (003_secrets.sql) and are never duplicated here.
--   risk_caps/sizing are plain operator-set policy JSON, not secrets.
--
-- Prerequisites:
--   • 001_init.sql     — creates the database.
--   • 002_spawner.sql  — defines the shared set_updated_at() trigger function,
--                        reused here. (Init scripts run in lexicographic order,
--                        so 25-spawner.sql lands before 29-treasury.sql.)
--
-- Idempotent — safe to re-run (CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT
-- EXISTS, DROP TRIGGER IF EXISTS).
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker exec -i fks_postgres sh -c \
--     'psql -U "$POSTGRES_USER" -d ruby_db' < src/sql/spawner/007_treasury.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv ruby_db   RUBY_DB

\connect :ruby_db

-- =============================================================================
-- transfers — the cash-flow ledger: one row per deposit/withdrawal/payout/sweep
-- =============================================================================
-- SIGN CONVENTION: `amount` is signed from the ACCOUNT's point of view —
--   positive  = money INTO the account (deposit)
--   negative  = money OUT of the account (withdrawal)
-- `kind` labels the flow; the sign carries the direction. Profit decomposition
-- is then: profit = (end net worth − start net worth) − SUM(amount) over the
-- window.
-- =============================================================================

CREATE TABLE IF NOT EXISTS transfers (
    -- Monotonic surrogate key for an append-only ledger (see header).
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Which account the flow belongs to: a bot_id (the fks.bot_id label, so
    -- ledger rows join against net_worth_snapshots.bot_id) or an `accounts`
    -- registry id. Deliberately NOT a FK — bot accounts exist before they are
    -- registered, and the ledger must never lose rows to registry edits.
    account_id  TEXT        NOT NULL,

    -- When the flow happened. Defaults to insert time, but manual entries may
    -- backdate (the operator records a deposit after the fact).
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Signed flow in `currency` (positive = in, negative = out — see header).
    -- NUMERIC (not float) so a years-horizon ledger never accrues rounding
    -- drift; zero rows are meaningless and rejected.
    amount      NUMERIC(38, 18) NOT NULL CHECK (amount <> 0),

    -- Denomination of `amount`.
    currency    TEXT        NOT NULL DEFAULT 'USD',

    -- What the flow is: 'deposit' | 'withdrawal' | 'payout' (e.g. prop-firm
    -- payout) | 'sweep' (moving funds between own accounts).
    kind        TEXT        NOT NULL
                            CHECK (kind IN ('deposit', 'withdrawal', 'payout', 'sweep')),

    -- Which writer produced the row: 'manual' (operator entry via the WebUI)
    -- or 'bot_detected' (a bot noticing an unexplained balance jump).
    source      TEXT        NOT NULL DEFAULT 'manual',

    -- Free-form operator annotation ("July DCA", "APEX payout #3", …).
    note        TEXT
);

COMMENT ON TABLE  transfers            IS 'Cash-flow ledger (deposits/withdrawals/payouts/sweeps) so net-worth drift decomposes into deposits vs trading profit. Append-only.';
COMMENT ON COLUMN transfers.account_id IS 'bot_id (joins net_worth_snapshots.bot_id) or accounts registry id; not a FK';
COMMENT ON COLUMN transfers.ts         IS 'When the flow happened (defaults to insert time; manual entries may backdate)';
COMMENT ON COLUMN transfers.amount     IS 'Signed flow in `currency`: positive = into the account (deposit), negative = out (withdrawal); non-zero';
COMMENT ON COLUMN transfers.currency   IS 'Denomination of amount';
COMMENT ON COLUMN transfers.kind       IS 'deposit | withdrawal | payout | sweep';
COMMENT ON COLUMN transfers.source     IS 'Row writer: manual (operator) | bot_detected (balance-jump detection)';
COMMENT ON COLUMN transfers.note       IS 'Free-form operator annotation';

-- Primary access pattern: one account's ledger, newest first (also serves the
-- profit-decomposition window scan).
CREATE INDEX IF NOT EXISTS idx_transfers_account_ts
    ON transfers (account_id, ts DESC);

-- =============================================================================
-- accounts — the account registry: the multi-account topology's source of truth
-- =============================================================================
-- One row per real-world account the platform watches or trades. Tiers map the
-- treasury topology:
--   0 = cold-BTC backbone   (watch-only cold storage)
--   1 = personal-crypto     (exchange accounts the bots trade)
--   2 = rithmic-main        (the human-traded futures account)
--   3 = prop-copy-target    (prop-firm accounts mirroring tier 2)
--
-- NO CREDENTIALS LIVE HERE. API keys/secrets stay in the encrypted
-- exchange_secrets store (003_secrets.sql, ChaCha20-Poly1305 at rest); this
-- registry carries only topology + policy metadata. Nothing is seeded — the
-- operator registers accounts via POST /accounts.
-- =============================================================================

CREATE TABLE IF NOT EXISTS accounts (
    -- Natural key: the logical account identity (for bot-traded accounts, the
    -- fks.bot_id label, so registry rows join net_worth_snapshots/transfers).
    account_id       TEXT        PRIMARY KEY,

    -- Human-friendly label for the WebUI ("Kraken main", "APEX eval #2", …).
    display_name     TEXT,

    -- Treasury tier: 0 = cold-BTC backbone, 1 = personal-crypto,
    -- 2 = rithmic-main, 3 = prop-copy-target.
    tier             SMALLINT    NOT NULL,

    -- Coarse classification, e.g. 'personal-crypto', 'paper', 'prop',
    -- 'cold-storage'.
    account_class    TEXT        NOT NULL,

    -- Venue/exchange/broker the account lives at (kraken, kucoin, rithmic, …).
    venue            TEXT,

    -- How the platform interacts with the account:
    --   'watch'              — observe only (e.g. cold storage)
    --   'bot-trade'          — a bot trades it
    --   'human-trade-source' — the human trades it; copies flow FROM it
    --   'copy-target'        — receives mirrored trades
    role             TEXT        NOT NULL
                                 CHECK (role IN ('watch', 'bot-trade',
                                                 'human-trade-source', 'copy-target')),

    -- Prop firm the account belongs to (NULL for non-prop accounts).
    firm             TEXT,

    -- Copy-trading compliance posture: 'manual-mirror' (a human confirms every
    -- mirrored fill — the platform-wide no-autonomous-execution default) vs
    -- 'auto-fill' (only where a firm's rules explicitly allow it).
    compliance_flag  TEXT        NOT NULL DEFAULT 'manual-mirror'
                                 CHECK (compliance_flag IN ('manual-mirror', 'auto-fill')),

    -- Operator-set risk policy (max drawdown, daily loss caps, …). Free-form
    -- JSON; later phases enforce it.
    risk_caps        JSONB       DEFAULT '{}',

    -- Operator-set sizing policy (contract multipliers, scale factors, …).
    sizing           JSONB       DEFAULT '{}',

    -- Soft-delete flag: DELETE /accounts/{id} flips this to FALSE; history
    -- (transfers/net-worth rows keyed by account_id) is never dropped.
    active           BOOLEAN     NOT NULL DEFAULT TRUE,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  accounts                 IS 'Account registry — source of truth for the multi-account treasury topology (tiers 0-3). Carries NO credentials (those live encrypted in exchange_secrets).';
COMMENT ON COLUMN accounts.account_id      IS 'Logical account identity (bot_id for bot-traded accounts); joins transfers/net_worth_snapshots';
COMMENT ON COLUMN accounts.tier            IS '0 = cold-BTC backbone, 1 = personal-crypto, 2 = rithmic-main, 3 = prop-copy-target';
COMMENT ON COLUMN accounts.account_class   IS 'Coarse classification: personal-crypto | paper | prop | cold-storage | …';
COMMENT ON COLUMN accounts.venue           IS 'Venue/exchange/broker (kraken, rithmic, …)';
COMMENT ON COLUMN accounts.role            IS 'watch | bot-trade | human-trade-source | copy-target';
COMMENT ON COLUMN accounts.firm            IS 'Prop firm (NULL for non-prop accounts)';
COMMENT ON COLUMN accounts.compliance_flag IS 'manual-mirror (human confirms every mirrored fill) | auto-fill (only where firm rules allow)';
COMMENT ON COLUMN accounts.risk_caps       IS 'Operator-set risk policy JSON (enforced by later phases)';
COMMENT ON COLUMN accounts.sizing          IS 'Operator-set sizing policy JSON';
COMMENT ON COLUMN accounts.active          IS 'Soft-delete flag — FALSE hides the account without dropping its history';

-- Stamp updated_at on every change. Reuses set_updated_at() from 002_spawner.sql.
DROP TRIGGER IF EXISTS trg_accounts_updated_at ON accounts;
CREATE TRIGGER trg_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- Privileges
-- =============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;
