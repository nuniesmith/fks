-- =============================================================================
-- 02_futures.sql — Ruby data/engine database
-- Creates ruby_db database on the same postgres instance as janus_db (Janus).
-- Credentials are shared with the primary DB — same user, same password.
--
-- Variables resolved at container start from environment via \getenv:
--   POSTGRES_USER     — DB user (default: fks_user)
--   POSTGRES_PASSWORD — DB password
--   RUBY_DB  — secondary database name (default: ruby_db)
--
-- NOTE: \getenv requires psql 14+ (bundled with postgres:14+).
--
-- NOTE: psql does NOT perform :'variable' substitution inside dollar-quoted
--       DO $$ ... $$ blocks — the dollar-quoted body is sent verbatim to the
--       server, which rejects the bare colon with a syntax error.  All psql
--       variable references must therefore appear OUTSIDE any $$ block.
--
-- User creation is intentionally omitted here: the postgres image creates
-- POSTGRES_USER before any initdb script runs, so the role is guaranteed to
-- exist by the time this script executes.  If you ever run this script
-- standalone, create the role manually first:
--   CREATE USER fks_user WITH ENCRYPTED PASSWORD 'yourpassword';
-- =============================================================================

\getenv fks_user     POSTGRES_USER
\getenv fks_pass     POSTGRES_PASSWORD
\getenv ruby_db  RUBY_DB

-- ---------------------------------------------------------------------------
-- Create the data/engine database owned by the application user.
-- The SELECT ... \gexec pattern is a safe "CREATE DATABASE IF NOT EXISTS"
-- because CREATE DATABASE cannot run inside a transaction block.
-- ---------------------------------------------------------------------------
SELECT 'CREATE DATABASE ' || quote_ident(:'ruby_db') || ' OWNER ' || quote_ident(:'fks_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'ruby_db')\gexec

-- Grant full access (idempotent — safe to re-run).
-- Note: GRANT ON DATABASE does not grant schema access; the \connect block
-- below grants schema-level privileges so the service can create tables.
GRANT ALL PRIVILEGES ON DATABASE :ruby_db TO :fks_user;

\connect :ruby_db

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Grant schema-level access so the data service can create / alter tables
-- without needing superuser privileges.
GRANT ALL PRIVILEGES ON SCHEMA public TO :fks_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO :fks_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO :fks_user;
