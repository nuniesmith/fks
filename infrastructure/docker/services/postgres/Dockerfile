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
#   src/sql/spawner/   — fks_db schema      (Bot Spawner: bot_configs/bot_runs)
#
# NOTE: the Python "Ruby" service was removed (docs/architecture/RUST_MIGRATION.md).
# Its fks_db schema is gone EXCEPT the bootstrap + spawner tables the Bot
# Spawner service still needs — those now live in src/sql/spawner/. The database
# was renamed fks_db (from ruby_db) on 2026-07-21; the env var name RUBY_DB is retained.
#
# Init scripts are copied into /docker-entrypoint-initdb.d/ with a numeric
# prefix that controls lexicographic run order:
#
#   01-02  — Database + user bootstrap   (must run before any migrations)
#   10     — Janus migrations
#   25     — Spawner schema       (bot_configs / bot_runs)
#   26     — Exchange secrets     (exchange_secrets — WebUI Phase E)
#   27     — Notification channels (notification_channels — Discord webhooks)
#   28     — Net-worth history    (net_worth_snapshots)
#   29     — Treasury             (transfers ledger + accounts registry)
#   30     — Edge factory         (edges registry + backtest_runs ledger)
#   31     — UI layouts           (ui_layouts — server-side saved dock layouts)
#   32     — Backtest role        (fks_backtest — scoped creds for backtest containers)
#   33     — WebUI auth           (webui_users/sessions/audit + fks_webui role)
#
# ⚠️ Every src/sql/{janus,spawner}/*.sql file MUST be COPY'd below — initdb
# only runs on an EMPTY volume, so a missing script here means a fresh-host
# (or volume-loss) bootstrap silently drops that schema.
#
# Rebuild whenever SQL files change:
#   docker compose build postgres
#
# Environment variables consumed by the init scripts (passed via docker-compose):
#   POSTGRES_USER      — shared DB user for all databases  (default: fks_user)
#   POSTGRES_PASSWORD  — shared password
#   JANUS_DB           — Janus database name               (default: janus_db)
#   RUBY_DB            — Spawner database name (var name retained) (default: fks_db)
#   BACKTEST_DB_PASSWORD — password for the scoped fks_backtest role (009);
#                        empty/unset = role created but not loggable-into
#   WEBUI_DB_PASSWORD    — password for the scoped fks_webui role (010);
#                        empty/unset = role created but not loggable-into
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
# Phase 3 — Spawner schema (fks_db) — bot_configs / bot_runs
# ---------------------------------------------------------------------------
COPY src/sql/spawner/002_spawner.sql                      /docker-entrypoint-initdb.d/25-spawner.sql

# ---------------------------------------------------------------------------
# Phase 4 — Exchange secrets (fks_db) — exchange_secrets (WebUI Phase E)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/003_secrets.sql                      /docker-entrypoint-initdb.d/26-secrets.sql

# ---------------------------------------------------------------------------
# Phase 5 — Notification channels (fks_db) — notification_channels
# (Discord webhooks; store + management API only, sending is a follow-up)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/004_notifications.sql                /docker-entrypoint-initdb.d/27-notifications.sql

# ---------------------------------------------------------------------------
# Phase 6 — Net-worth history (fks_db) — net_worth_snapshots
# (durable, append-only; written by the spawner's periodic /status sampler)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/006_net_worth_snapshots.sql          /docker-entrypoint-initdb.d/28-net-worth-snapshots.sql

# ---------------------------------------------------------------------------
# Phase 7 — Treasury (fks_db) — transfers ledger + accounts registry
# (deposit/withdrawal ledger so net-worth drift decomposes into deposits vs
# profit, plus the multi-account topology's source of truth)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/007_treasury.sql                     /docker-entrypoint-initdb.d/29-treasury.sql

# ---------------------------------------------------------------------------
# Phase 8 — Edge factory (fks_db) — edges registry + backtest_runs ledger
# (the edge-portfolio's source of truth plus the factory's backtest run
# ledger: spawner inserts a run, the one-shot backtest container reports
# its own results back)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/008_edge_factory.sql                 /docker-entrypoint-initdb.d/30-edge-factory.sql

# ---------------------------------------------------------------------------
# Phase 9 — UI layouts (fks_db) — ui_layouts
# (server-side saved dock layouts so /workspace layouts follow the operator)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/005_ui_layouts.sql                   /docker-entrypoint-initdb.d/31-ui-layouts.sql

# ---------------------------------------------------------------------------
# Phase 10 — Backtest role (cluster + fks_db) — fks_backtest
# (scoped LOGIN role handed to one-shot factory backtest containers via
# BACKTEST_DB_URL: SELECT + UPDATE(status,results,finished_at) on
# backtest_runs ONLY — never the spawner's full fks_user credentials.
# Must run AFTER 30-edge-factory.sql, which creates backtest_runs.)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/009_backtest_role.sql                /docker-entrypoint-initdb.d/32-backtest-role.sql

# ---------------------------------------------------------------------------
# Phase 11 — WebUI auth (cluster + fks_db) — webui_users/sessions/audit +
# the scoped fks_webui LOGIN role (SELECT/INSERT/UPDATE/DELETE on the three
# webui_* tables + USAGE on their sequences ONLY — never the spawner's full
# fks_user creds). Companion to fks-web #47 so a fresh host boots auth-ready
# instead of fail-closed 503. Runs AFTER 02-spawner-init.sql (creates fks_db).
# ---------------------------------------------------------------------------
COPY src/sql/spawner/010_webui_auth.sql                   /docker-entrypoint-initdb.d/33-webui-auth.sql

# ---------------------------------------------------------------------------
# Phase 12 — WebUI alert acks (fks_db) — webui_alert_acks
# (alert-ack inbox: incident identity = sha256(labels + activeAt), acks are
# irrevocable audit rows — fks_webui gets SELECT/INSERT only, sequence by
# name. Must run AFTER 33-webui-auth.sql, which creates the fks_webui role.)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/011_webui_alert_acks.sql             /docker-entrypoint-initdb.d/34-webui-alert-acks.sql

# ---------------------------------------------------------------------------
# Phase 13 — WebUI invites (fks_db) — webui_invites
# (one-time signup URLs: token sha256 at rest, single-use enforced atomically
# by the webui, no admin-by-invite. fks_webui gets SELECT/INSERT/UPDATE,
# sequence by name. Must run AFTER 33-webui-auth.sql — FK to webui_users +
# the role itself.)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/012_webui_invites.sql                /docker-entrypoint-initdb.d/35-webui-invites.sql

# ---------------------------------------------------------------------------
# Phase 14 — Notification delivery ledger (fks_db) — notification_log
# (every webhook delivery attempt gets a row: event, channel, outcome,
# status; detail never contains the URL. Written best-effort/off-path by
# the spawner's fks_user; pruned by the spawner, not SQL.)
# ---------------------------------------------------------------------------
COPY src/sql/spawner/013_notification_log.sql             /docker-entrypoint-initdb.d/36-notification-log.sql

# ---------------------------------------------------------------------------
# Phase 15 — Funding state (cluster + fks_db) — the private crypto-futures
# funding bot's four self-owned tables (framework_risk_state,
# funding_open_trades, funding_paper_records, funding_kill_switch) + the scoped
# fks_funding LOGIN role (SELECT/INSERT/UPDATE/DELETE on those four + USAGE on
# funding_paper_records_id_seq ONLY — never the spawner's full fks_user creds,
# never exchange_secrets/treasury/webui_*). Review H1: swaps the funding bot off
# the superuser URL. Pre-creating the tables (H3) also lets a --data-only DR
# restore load the runtime-created breaker + kill-switch state onto a fresh host.
# Self-contained — only needs 02-spawner-init.sql (creates fks_db).
# ---------------------------------------------------------------------------
COPY src/sql/spawner/014_funding_state.sql                /docker-entrypoint-initdb.d/37-funding-state.sql
COPY src/sql/spawner/015_net_worth_stale_provenance.sql   /docker-entrypoint-initdb.d/38-net-worth-stale-provenance.sql
COPY src/sql/spawner/016_rithmic_accounts.sql             /docker-entrypoint-initdb.d/39-rithmic-accounts.sql

# ---------------------------------------------------------------------------
# Phase 16 — Edge factory evidence + the promotion ladder.
#
# WHY THESE ARE HERE. External review (Sol, 2026-09-04, R5) found the list
# above ended at 016, so a database built from this image had NO
# edge_experiments, NO edge_deployments, and none of the guards on them —
# while the repo carried all four migrations and the LIVE database had them
# applied by hand. Adding a migration to `src/sql/` is therefore not the same
# act as making a clean rebuild reproduce it, and that gap is invisible until
# someone actually rebuilds.
#
# Order is dependency order, not filename order by accident:
#   017 creates edge_experiments (018's FK target)
#   018 creates edge_deployments + the promotion guard
#   019 grants the webui SELECT on exchange_secrets(exchange) ONLY
#   020 REPLACES 018's guard function — it must run after 018 or the
#       corrected body is overwritten by the defective one.
#
# The `*.validate.sql` files are deliberately NOT copied: they are adversarial
# test fixtures that INSERT rows and ROLLBACK, not production schema. Copying
# `*.sql` wholesale would run them at initdb.
# ---------------------------------------------------------------------------
COPY src/sql/spawner/017_edge_experiments.sql             /docker-entrypoint-initdb.d/40-edge-experiments.sql
COPY src/sql/spawner/018_edge_deployments.sql             /docker-entrypoint-initdb.d/41-edge-deployments.sql
COPY src/sql/spawner/019_webui_secret_presence_grant.sql  /docker-entrypoint-initdb.d/42-webui-secret-presence-grant.sql
COPY src/sql/spawner/020_promotion_guard_freeze.sql       /docker-entrypoint-initdb.d/43-promotion-guard-freeze.sql
