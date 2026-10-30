-- =============================================================================
-- 025_research_role_grants.sql — what a search job may read and write
-- =============================================================================
-- The edge-search job (fks-spawner bots/edge-search, EDGE_PROCESS steps 3-4)
-- runs as a one-shot job instance and connects as fks_backtest: the spawner
-- hands it BACKTEST_DB_URL as FKS_DB_URL, at spawn, never saved (fks-spawner
-- #69). 009 scoped that role to the backtest ledger; a search also needs the
-- research tables, and only those:
--
--   • SELECT on edges and edge_hypotheses: the hypothesis it tests;
--   • SELECT and INSERT on edge_experiments (+ its sequence): the N of every
--     trial already run for the edge, and its own one row;
--   • SELECT on edge_search_effort (the view over edge_experiments).
--
-- Still NOT granted, as in 009: exchange_secrets, transfers, accounts,
-- net_worth_snapshots, bot_configs, bot_runs, notification_*, webui_*,
-- edge_deployments. No UPDATE or DELETE on the research tables either: an
-- experiment is written once, and a hypothesis is frozen (024) anyway. The
-- registry holds no credentials (edges is metadata; 008).
--
-- Idempotent: GRANT is.
-- =============================================================================

\getenv fks_db   RUBY_DB

\connect :fks_db

GRANT SELECT ON edges, edge_hypotheses TO fks_backtest;
GRANT SELECT, INSERT ON edge_experiments TO fks_backtest;
GRANT USAGE ON SEQUENCE edge_experiments_id_seq TO fks_backtest;
GRANT SELECT ON edge_search_effort TO fks_backtest;
