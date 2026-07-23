-- =============================================================================
-- 014-funding_state.sql — Funding bot's own tables + scoped LOGIN role
-- =============================================================================
-- Provisions the private crypto-futures FUNDING bot's persistent state schema in
-- fks_db AND the scoped fks_funding LOGIN role that replaces the bot's current
-- full-superuser URL (2026-07-23 review H1).
--
-- WHY THIS EXISTS (H1 — the biggest privilege reduction pre-M2-arm):
-- Today fks-bot-crypto-funding connects with FR_DATABASE_URL = the spawner's own
-- fks_user — the SOLE Postgres superuser (rolsuper=t). The least-trusted, most-
-- experimental bot therefore holds full-instance control: r/w across
-- fks_db+janus_db+postgres, tamper of the treasury ledger + webui_* auth tables,
-- and RCE inside the container via COPY … FROM PROGRAM. This mirrors the shipped
-- fks_backtest fix (009_backtest_role.sql): swap FR_DATABASE_URL to the scoped
-- fks_funding role below, which can touch ONLY the four tables the bot owns and
-- NOTHING else — no exchange_secrets, no treasury, no webui_*, no other DB.
--
-- WHY THE TABLES ARE CREATED HERE (not just the role):
-- The funding bot creates these tables itself at startup, running their DDL as
-- superuser (framework_state_store.rs::DDL + state_store.rs::DDL — the CREATE
-- statements below are mirrored BYTE-FAITHFULLY from those constants). A scoped,
-- non-superuser role has NO CREATE privilege, so with the role swap the tables
-- must ALREADY EXIST when the bot first connects — otherwise its own DDL fails.
-- This migration is what makes the role swap safe: it pre-creates every table so
-- the bot's `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` then simply
-- no-op. (This is also H3: `framework_risk_state` + `funding_kill_switch` were
-- app-created at runtime with no migration, so a --data-only DR restore had
-- nowhere to load them; now they have a CREATE that a fresh host bootstraps.)
--
-- THE FOUR TABLES the funding bot owns (and this role is scoped to):
--   • framework_risk_state  — rustrade framework gate state: the per-symbol
--                             SessionPnl daily-loss halt + CircuitBreaker streak
--                             (opaque key -> JSON blob). TEXT PK, no sequence.
--   • funding_open_trades   — open-position resume state. TEXT PK, no sequence.
--   • funding_paper_records — the PROBE-B paper PnL ledger (append-only).
--                             BIGSERIAL id -> funding_paper_records_id_seq. Plus
--                             the GENERATED accounting columns the bot's startup
--                             ALTERs add (idempotent; recomputed from `record`).
--   • funding_kill_switch   — M2 kill-switch sentinel, one row per instance
--                             ('paper' | 'live'). TEXT PK, no sequence.
--
-- ROLE (009/010 pattern): fks_funding is the LOGIN role the funding bot connects
-- as (FR_DATABASE_URL), NOT the spawner's full-access fks_user. It gets, and
-- ONLY gets:
--   • CONNECT on fks_db + USAGE on schema public
--   • SELECT,INSERT,UPDATE,DELETE on the four tables above
--   • USAGE,SELECT on funding_paper_records_id_seq — the ONLY sequence any of
--     these tables owns (the other three have TEXT primary keys)
--
-- Deliberately NOT granted: exchange_secrets, transfers, accounts,
-- net_worth_snapshots, edges, backtest_runs, bot_configs, bot_runs,
-- notification_channels, notification_log, ui_layouts, webui_users/sessions/
-- audit/invites/alert_acks — nor any other table/sequence in schema public, nor
-- any privilege on janus_db or postgres. That scoping IS the entire point of H1.
-- The sequence grant is BY NAME (never "ALL SEQUENCES IN SCHEMA public", which
-- would sweep in every spawner-owned sequence). 001_init.sql's ALTER DEFAULT
-- PRIVILEGES targets fks_user only, so future tables/sequences are not
-- auto-granted to this role either.
--
-- Password comes from the container env var FUNDING_DB_PASSWORD (passed by
-- docker-compose to the postgres service), consumed via psql \getenv — the same
-- mechanism 009_backtest_role.sql / 010_webui_auth.sql use. Empty/unset
-- FUNDING_DB_PASSWORD → the role is created (grants and all) but keeps NO valid
-- password, so logins fail closed until the script is re-run with the password
-- set — re-running is also how you rotate it.
--
-- Idempotent — safe to re-run and safe to apply BY HAND to the live, non-empty
-- database (baked initdb scripts only run on an EMPTY volume): CREATE TABLE IF
-- NOT EXISTS, ADD COLUMN IF NOT EXISTS, role creation is existence-guarded,
-- ALTER ROLE/GRANT are idempotent. On the live volume the bot ALREADY created
-- these tables as fks_user, so every CREATE/ALTER here no-ops and only the role
-- + grants are new.
--
-- Prerequisites:
--   • 001_init.sql — creates fks_db (02-spawner-init.sql, runs first). No other
--     migration is required: these four tables are self-contained (the funding
--     bot is their sole owner), so this script may run at any later slot.
--
-- Manual execution (existing volumes skip initdb — apply by hand once, with the
-- password injected into the exec env; -d postgres because role creation is
-- cluster-wide and the script \connects to fks_db itself):
--   docker exec -i -e FUNDING_DB_PASSWORD="$FUNDING_DB_PASSWORD" \
--     fks_postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' \
--     < src/sql/spawner/014_funding_state.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv fks_db   RUBY_DB

-- Default the password to '' so the script also runs where the env var is
-- absent entirely (\getenv leaves the variable untouched when unset).
\set funding_password ''
\getenv funding_password FUNDING_DB_PASSWORD

-- ---------------------------------------------------------------------------
-- Create the role if it does not already exist (CREATE ROLE has no
-- IF NOT EXISTS — the SELECT … \gexec pattern mirrors 009_backtest_role.sql).
-- ---------------------------------------------------------------------------
SELECT 'CREATE ROLE fks_funding WITH LOGIN'
WHERE NOT EXISTS (
    SELECT FROM pg_roles WHERE rolname = 'fks_funding'
)\gexec

-- Set/rotate the password whenever one is provided (skipped when empty, so a
-- password-less bootstrap cannot silently enable empty-password logins).
SELECT format('ALTER ROLE fks_funding WITH LOGIN PASSWORD %L',
              :'funding_password')
WHERE length(:'funding_password') > 0\gexec

GRANT CONNECT ON DATABASE :fks_db TO fks_funding;

\connect :fks_db

-- ---------------------------------------------------------------------------
-- Schema. Created as the privileged initdb user (owner = fks_user), so the
-- scoped fks_funding role never needs CREATE. Each CREATE/ALTER below is mirrored
-- BYTE-FAITHFULLY from the bot's own startup DDL so the bot's idempotent DDL
-- no-ops once these pre-exist:
--   • framework_risk_state  ← framework_state_store.rs (const DDL)
--   • funding_open_trades / funding_paper_records (+ GENERATED accounting
--     columns) / funding_kill_switch ← state_store.rs (const DDL)
-- ---------------------------------------------------------------------------

-- framework_risk_state — one opaque JSON blob per framework key
-- ("<bot>/risk/<symbol>"): the SessionPnl daily-loss halt + CircuitBreaker.
CREATE TABLE IF NOT EXISTS framework_risk_state (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- funding_open_trades — open-position resume state (a CLEARED trade is stored
-- as JSON null, not a row delete, so the row's existence marks postgres owns it).
CREATE TABLE IF NOT EXISTS funding_open_trades (
    symbol     TEXT PRIMARY KEY,
    state      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- funding_paper_records — the append-only PROBE-B paper PnL ledger.
CREATE TABLE IF NOT EXISTS funding_paper_records (
    id     BIGSERIAL PRIMARY KEY,
    ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
    record JSONB NOT NULL
);
-- P0.3 realized-USDT ledger columns (idempotent; needs PG >= 12). GENERATED
-- straight from the `record` JSONB so a column can never drift from the ledger
-- JSON the bot wrote.
ALTER TABLE funding_paper_records
    ADD COLUMN IF NOT EXISTS notional_usdt    double precision GENERATED ALWAYS AS ((record->>'notional_usdt')::double precision) STORED,
    ADD COLUMN IF NOT EXISTS gross_pnl_usdt   double precision GENERATED ALWAYS AS ((record->>'gross_pnl_usdt')::double precision) STORED,
    ADD COLUMN IF NOT EXISTS fees_usdt        double precision GENERATED ALWAYS AS ((record->>'fees_usdt')::double precision) STORED,
    ADD COLUMN IF NOT EXISTS funding_pnl_usdt double precision GENERATED ALWAYS AS ((record->>'funding_pnl_usdt')::double precision) STORED,
    ADD COLUMN IF NOT EXISTS net_pnl_usdt     double precision GENERATED ALWAYS AS ((record->>'net_pnl_usdt')::double precision) STORED;
-- Funding-accrual audit columns (idempotent).
ALTER TABLE funding_paper_records
    ADD COLUMN IF NOT EXISTS funding_settlements integer GENERATED ALWAYS AS ((record->>'funding_settlements')::integer) STORED,
    ADD COLUMN IF NOT EXISTS funding_coverage    text    GENERATED ALWAYS AS (record->>'funding_coverage') STORED;
-- M2 live-accounting columns (idempotent). `mode` COALESCEs to 'paper' so every
-- existing/paper row reads 'paper' with no migration; only ARMED live closes
-- stamp 'mode':'live'. Both GENERATED so a column can never drift from `record`.
ALTER TABLE funding_paper_records
    ADD COLUMN IF NOT EXISTS mode         text             GENERATED ALWAYS AS (COALESCE(record->>'mode', 'paper')) STORED,
    ADD COLUMN IF NOT EXISTS slippage_bps double precision GENERATED ALWAYS AS ((record->>'slippage_bps')::double precision) STORED;

-- funding_kill_switch — M2 kill-switch sentinel, one row per bot instance
-- (`instance` = 'paper' | 'live'); a present row = KILLED, re-arm stores null.
CREATE TABLE IF NOT EXISTS funding_kill_switch (
    instance   TEXT PRIMARY KEY,
    record     JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Minimal privileges (see header). GRANTs are idempotent.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO fks_funding;

GRANT SELECT, INSERT, UPDATE, DELETE ON framework_risk_state   TO fks_funding;
GRANT SELECT, INSERT, UPDATE, DELETE ON funding_open_trades    TO fks_funding;
GRANT SELECT, INSERT, UPDATE, DELETE ON funding_paper_records  TO fks_funding;
GRANT SELECT, INSERT, UPDATE, DELETE ON funding_kill_switch    TO fks_funding;

-- Sequence USAGE for the one BIGSERIAL id column — scoped BY NAME (never
-- "ALL SEQUENCES IN SCHEMA public"). The other three tables have TEXT primary
-- keys and own no sequence.
GRANT USAGE, SELECT ON SEQUENCE funding_paper_records_id_seq TO fks_funding;

-- ---------------------------------------------------------------------------
-- OWNERSHIP + CREATE (the runtime-DDL contract — added 2026-07-23 after the
-- live role swap panicked without it; H1 deploy).
--
-- The funding bot re-runs its OWN idempotent DDL at every startup:
--   CREATE TABLE IF NOT EXISTS …   (state_store.rs / framework_state_store.rs)
--   CREATE INDEX IF NOT EXISTS …   (on funding_paper_records)
-- and it ABORTS if that DDL errors (FR_STATE_BACKEND must never silently fall
-- back to file). Two Postgres facts make table-level DML grants insufficient:
--   1. CREATE TABLE IF NOT EXISTS checks CREATE-on-schema BEFORE the
--      "already exists" short-circuit — so USAGE alone → "permission denied
--      for schema public" even when the table exists.
--   2. CREATE INDEX / ALTER require table OWNERSHIP — so a non-owner → "must
--      be owner of table funding_paper_records".
-- The tightest correct model is therefore: the bot's role OWNS its own state
-- tables (nothing else) and may CREATE in public. This grants NO access to any
-- other role's tables (exchange_secrets, webui_*, treasury, other DBs stay
-- unreachable — the H1 win holds): ownership + CREATE-on-schema only lets it
-- manage its OWN four tables and make new tables in public, never read others'.
-- (A dedicated `funding` schema owned by the role would avoid CREATE-on-public
-- entirely; deferred — the tables already hold live paper-soak data in public.)
GRANT CREATE ON SCHEMA public TO fks_funding;

ALTER TABLE framework_risk_state          OWNER TO fks_funding;
ALTER TABLE funding_open_trades           OWNER TO fks_funding;
ALTER TABLE funding_paper_records         OWNER TO fks_funding;
ALTER TABLE funding_kill_switch           OWNER TO fks_funding;
ALTER SEQUENCE funding_paper_records_id_seq OWNER TO fks_funding;
