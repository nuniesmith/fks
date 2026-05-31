# =============================================================================
# FKS — PostgreSQL Init Image
# =============================================================================
#
# Extends the official postgres:16-alpine image by baking all schema
# initialisation scripts directly into the image via COPY.
#
# This avoids bind-mounting individual host files into
# /docker-entrypoint-initdb.d/, which fails on read-only rootfs mounts.
#
# SQL sources (janus_db bootstrap is kept here; the janus service — built
# from its own repo — runs its detailed migrations at startup):
#
#   src/sql/janus/     — janus_db bootstrap  (db + user + api_keys)
#   src/ruby/sql/      — ruby_db schema      (Ruby engine + Spawner service)
#
# Init scripts are copied into /docker-entrypoint-initdb.d/ with a numeric
# prefix that controls lexicographic run order:
#
#   01-02  — Database + user bootstrap   (must run before any migrations)
#   10     — Janus migrations
#   20-26  — Ruby migrations
#
# Rebuild whenever SQL files change:
#   docker compose build postgres
#
# Environment variables consumed by the init scripts (passed via docker-compose):
#   POSTGRES_USER      — shared DB user for all databases  (default: fks_user)
#   POSTGRES_PASSWORD  — shared password
#   JANUS_DB           — Janus database name               (default: janus_db)
#   RUBY_DB            — Ruby engine database name         (default: ruby_db)
# =============================================================================

FROM postgres:16-alpine

# ---------------------------------------------------------------------------
# Phase 1 — Database bootstrap (must run first; creates DBs + grants)
# ---------------------------------------------------------------------------
COPY src/sql/janus/001_init.sql                           /docker-entrypoint-initdb.d/01-janus-init.sql
COPY src/ruby/sql/001_init.sql                            /docker-entrypoint-initdb.d/02-ruby-init.sql

# ---------------------------------------------------------------------------
# Phase 2 — Janus migrations (janus_db)
# ---------------------------------------------------------------------------
COPY src/sql/janus/002_api_keys.sql                       /docker-entrypoint-initdb.d/10-janus-api-keys.sql

# ---------------------------------------------------------------------------
# Phase 3 — Ruby migrations (ruby_db)  — includes Spawner schema
# ---------------------------------------------------------------------------
COPY src/ruby/sql/002_futures.sql                         /docker-entrypoint-initdb.d/20-ruby-futures.sql
COPY src/ruby/sql/003_backup_tables.sql                   /docker-entrypoint-initdb.d/21-ruby-backup-tables.sql
COPY src/ruby/sql/004_news_and_registry.sql               /docker-entrypoint-initdb.d/22-ruby-news-and-registry.sql
COPY src/ruby/sql/005_chain.sql                           /docker-entrypoint-initdb.d/23-ruby-chain.sql
COPY src/ruby/sql/006_memories.sql                        /docker-entrypoint-initdb.d/24-ruby-memories.sql
COPY src/ruby/sql/007_spawner.sql                         /docker-entrypoint-initdb.d/25-ruby-spawner.sql
COPY src/ruby/sql/008_accounts.sql                        /docker-entrypoint-initdb.d/26-ruby-accounts.sql
