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
#   src/sql/spawner/   — ruby_db schema      (Bot Spawner: bot_configs/bot_runs)
#
# NOTE: the Python "Ruby" service was removed (docs/architecture/RUST_MIGRATION.md).
# Its ruby_db schema is gone EXCEPT the bootstrap + spawner tables the Bot
# Spawner service still needs — those now live in src/sql/spawner/. The database
# keeps the ruby_db name (env RUBY_DB) for backward compatibility.
#
# Init scripts are copied into /docker-entrypoint-initdb.d/ with a numeric
# prefix that controls lexicographic run order:
#
#   01-02  — Database + user bootstrap   (must run before any migrations)
#   10     — Janus migrations
#   25     — Spawner schema       (bot_configs / bot_runs)
#   26     — Exchange secrets     (exchange_secrets — WebUI Phase E)
#   27     — Notification channels (notification_channels — Discord webhooks)
#
# Rebuild whenever SQL files change:
#   docker compose build postgres
#
# Environment variables consumed by the init scripts (passed via docker-compose):
#   POSTGRES_USER      — shared DB user for all databases  (default: fks_user)
#   POSTGRES_PASSWORD  — shared password
#   JANUS_DB           — Janus database name               (default: janus_db)
#   RUBY_DB            — Spawner database name (legacy name) (default: ruby_db)
# =============================================================================

FROM postgres:16-alpine

# ---------------------------------------------------------------------------
# Phase 1 — Database bootstrap (must run first; creates DBs + grants)
# ---------------------------------------------------------------------------
COPY src/sql/janus/001_init.sql                           /docker-entrypoint-initdb.d/01-janus-init.sql
COPY src/sql/spawner/001_init.sql                         /docker-entrypoint-initdb.d/02-spawner-init.sql

# ---------------------------------------------------------------------------
# Phase 2 — Janus migrations (janus_db)
# ---------------------------------------------------------------------------
COPY src/sql/janus/002_api_keys.sql                       /docker-entrypoint-initdb.d/10-janus-api-keys.sql

# ---------------------------------------------------------------------------
# Phase 3 — Spawner schema (ruby_db) — bot_configs / bot_runs
# ---------------------------------------------------------------------------
COPY src/sql/spawner/002_spawner.sql                      /docker-entrypoint-initdb.d/25-spawner.sql

# ---------------------------------------------------------------------------
# Phase 4 — Exchange secrets (ruby_db) — exchange_secrets (WebUI Phase E)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/003_secrets.sql                      /docker-entrypoint-initdb.d/26-secrets.sql

# ---------------------------------------------------------------------------
# Phase 5 — Notification channels (ruby_db) — notification_channels
# (Discord webhooks; store + management API only, sending is a follow-up)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/004_notifications.sql                /docker-entrypoint-initdb.d/27-notifications.sql

# ---------------------------------------------------------------------------
# Phase 6 — Net-worth history (ruby_db) — net_worth_snapshots
# (durable, append-only; written by the spawner's periodic /status sampler)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/006_net_worth_snapshots.sql          /docker-entrypoint-initdb.d/28-net-worth-snapshots.sql

# ---------------------------------------------------------------------------
# Phase 7 — Treasury (ruby_db) — transfers ledger + accounts registry
# (deposit/withdrawal ledger so net-worth drift decomposes into deposits vs
# profit, plus the multi-account topology's source of truth)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/007_treasury.sql                     /docker-entrypoint-initdb.d/29-treasury.sql

# ---------------------------------------------------------------------------
# Phase 8 — Edge factory (ruby_db) — edges registry + backtest_runs ledger
# (the edge-portfolio's source of truth plus the factory's backtest run
# ledger: spawner inserts a run, the one-shot backtest container reports
# its own results back)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/008_edge_factory.sql                 /docker-entrypoint-initdb.d/30-edge-factory.sql
