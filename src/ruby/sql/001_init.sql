-- =============================================================================
-- 001-init-ruby.sql — Ruby data/engine database initialisation
-- =============================================================================
-- Creates ruby_db on the shared FKS PostgreSQL instance and grants fks_user
-- full access with proper schema defaults.
--
-- Prerequisites:
--   • 01-init-janus.sql must have run first (creates fks_user).
--   • Runs automatically on first container start (empty data volume).
--     Subsequent starts skip initdb entirely (volume already populated).
--
-- Manual re-creation (e.g. after `./run.sh fresh --reset-volumes`):
--   docker compose exec postgres psql -U postgres \
--     -f /docker-entrypoint-initdb.d/02-init-ruby.sql
--
-- Databases managed here:
--   ruby_db — Ruby data + engine service
--             (bars, journal, tasks, signals, news, chain, memories,
--              api_keys, asset_registry, paper trading)
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
