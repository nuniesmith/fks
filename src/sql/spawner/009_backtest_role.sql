-- =============================================================================
-- 009-backtest_role.sql — Scoped DB role for factory backtest containers
-- =============================================================================
-- Creates the fks_backtest LOGIN role: the credentials handed to one-shot
-- edge-factory backtest containers (BACKTEST_DB_URL) instead of the spawner's
-- own fks_user URL, which carries full read/write over ALL of ruby_db —
-- exchange_secrets, transfers, accounts, net_worth_snapshots, edges included
-- (2026-07-11 audit, api-security MEDIUM).
--
-- WHAT A BACKTEST CONTAINER ACTUALLY NEEDS (the write protocol in
-- 008_edge_factory.sql; both shipped reporters — fks-state
-- bots/crypto-futures/src/bin/factory_backtest.rs and crates/orb-backtest —
-- run exactly ONE statement):
--
--     UPDATE backtest_runs
--        SET status = $2, results = $3, finished_at = now()
--      WHERE id = $1
--
-- So the role gets, and ONLY gets:
--   • CONNECT on ruby_db + USAGE on schema public
--   • SELECT on backtest_runs            (the UPDATE's WHERE reads `id`)
--   • UPDATE (status, results, finished_at) on backtest_runs — the exact
--     columns the container-side protocol writes; params/edge_id/container_id
--     stay spawner-owned
--
-- Deliberately NOT granted: anything on exchange_secrets, transfers, accounts,
-- net_worth_snapshots, edges, bot_configs, bot_runs, notification_channels,
-- ui_layouts — and no INSERT/sequence usage (the spawner INSERTs the row as
-- fks_user; the container only reports into its own row). 001_init.sql's
-- ALTER DEFAULT PRIVILEGES targets fks_user only, so future tables are NOT
-- auto-granted to this role either.
--
-- Password comes from the container env var BACKTEST_DB_PASSWORD (passed by
-- docker-compose to the postgres service), consumed via psql \getenv — the
-- same mechanism 001_init.sql uses for POSTGRES_USER/RUBY_DB. If the env var
-- is unset/empty the role is still created (grants and all) but keeps NO
-- valid password, so logins fail closed until the script is re-run with the
-- password set — re-running is also how you rotate it.
--
-- Idempotent — safe to re-run and safe to apply BY HAND to the live,
-- non-empty database (baked initdb scripts only run on an EMPTY volume):
--   role creation is existence-guarded, ALTER ROLE/GRANT are idempotent.
--
-- Prerequisites:
--   • 001_init.sql        — creates ruby_db.
--   • 008_edge_factory.sql — creates backtest_runs (lexicographic order:
--     30-edge-factory.sql lands before 32-backtest-role.sql).
--
-- Manual execution (existing volumes skip initdb — apply by hand once, with
-- the password injected into the exec env; -d postgres because role creation
-- is cluster-wide and the script \connects to ruby_db itself):
--   docker exec -i -e BACKTEST_DB_PASSWORD="$BACKTEST_DB_PASSWORD" \
--     fks_postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' \
--     < src/sql/spawner/009_backtest_role.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv ruby_db   RUBY_DB

-- Default the password to '' so the script also runs where the env var is
-- absent entirely (\getenv leaves the variable untouched when unset).
\set backtest_password ''
\getenv backtest_password BACKTEST_DB_PASSWORD

-- ---------------------------------------------------------------------------
-- Create the role if it does not already exist (CREATE ROLE has no
-- IF NOT EXISTS — the SELECT … \gexec pattern mirrors 001_init.sql).
-- ---------------------------------------------------------------------------
SELECT 'CREATE ROLE fks_backtest WITH LOGIN'
WHERE NOT EXISTS (
    SELECT FROM pg_roles WHERE rolname = 'fks_backtest'
)\gexec

-- Set/rotate the password whenever one is provided (skipped when empty, so a
-- password-less bootstrap cannot silently enable empty-password logins).
SELECT format('ALTER ROLE fks_backtest WITH LOGIN PASSWORD %L',
              :'backtest_password')
WHERE length(:'backtest_password') > 0\gexec

-- ---------------------------------------------------------------------------
-- Minimal privileges (see header). GRANTs are idempotent.
-- ---------------------------------------------------------------------------
GRANT CONNECT ON DATABASE :ruby_db TO fks_backtest;

\connect :ruby_db

GRANT USAGE ON SCHEMA public TO fks_backtest;

-- The UPDATE's WHERE clause reads `id`, which requires SELECT; table-level
-- SELECT also keeps run-ledger debugging possible from inside a container
-- (backtest_runs holds no credentials — params/results JSON only).
GRANT SELECT ON backtest_runs TO fks_backtest;

-- Column-scoped: exactly what the container-side write protocol touches.
GRANT UPDATE (status, results, finished_at) ON backtest_runs TO fks_backtest;
