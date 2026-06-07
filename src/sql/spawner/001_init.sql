-- =============================================================================
-- 001-init.sql — Spawner database bootstrap
-- =============================================================================
-- Creates the shared application database on the FKS PostgreSQL instance and
-- grants fks_user full access with proper schema defaults.
--
-- NOTE: the database is still named `ruby_db` (env var RUBY_DB) for backward
-- compatibility — the Python "Ruby" service that originally owned it has been
-- removed (see docs/architecture/RUST_MIGRATION.md), but the Bot Spawner
-- service (crates/spawner/) persists bot_runs/bot_configs here. The name is
-- retained so existing volumes + connection strings keep working; renaming to
-- `spawner_db` is an optional future cleanup.
--
-- Prerequisites:
--   • 01-janus-init.sql must have run first (creates fks_user).
--   • Runs automatically on first container start (empty data volume).
--     Subsequent starts skip initdb entirely (volume already populated).
--
-- Manual re-creation (e.g. after `./run.sh fresh --reset-volumes`):
--   docker compose exec postgres psql -U postgres \
--     -f /docker-entrypoint-initdb.d/02-spawner-init.sql
--
-- Databases managed here:
--   ruby_db — Spawner persistence (bot_configs, bot_runs); see 002_spawner.sql
-- =============================================================================

\getenv fks_user    POSTGRES_USER
\getenv ruby_db RUBY_DB

-- ---------------------------------------------------------------------------
-- Create ruby_db if it does not already exist.
-- The SELECT … \gexec pattern is the idiomatic "CREATE DATABASE IF NOT EXISTS"
-- because CREATE DATABASE cannot run inside a transaction block.
-- ---------------------------------------------------------------------------
SELECT
    'CREATE DATABASE ' || quote_ident(:'ruby_db') ||
    ' WITH OWNER '     || quote_ident(:'fks_user')    ||
    ' ENCODING ''UTF8'' LC_COLLATE ''C'' LC_CTYPE ''C'' TEMPLATE template0'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = :'ruby_db'
)\gexec

-- Grant database-level privileges (idempotent).
GRANT ALL PRIVILEGES ON DATABASE :ruby_db TO :fks_user;

-- ---------------------------------------------------------------------------
-- Switch to ruby_db and apply schema-level configuration.
-- All objects created by Rails/Ruby migrations will be owned by fks_user
-- and remain accessible to it automatically via the defaults below.
-- ---------------------------------------------------------------------------
\connect :ruby_db

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Schema ownership & privileges
ALTER SCHEMA public OWNER TO :fks_user;
GRANT  ALL PRIVILEGES ON SCHEMA public TO :fks_user;

-- Default privileges: any object created by postgres or fks_user in the
-- public schema is automatically granted to fks_user.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO :fks_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO :fks_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO :fks_user;
