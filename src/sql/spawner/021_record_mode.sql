-- =============================================================================
-- 021: bot_configs.mode allows 'record' (recorder instances)
-- =============================================================================
-- fks-spawner saves each recorder instance as a config in mode 'record': a
-- recorder holds no keys and trades nothing (fks-spawner src/instances.rs).
-- The constraint from 002 allowed only paper/live/backtest/optimise/train, so
-- saving one failed with bot_configs_mode_valid.
--
-- Idempotent, like every file here: fks-migrate re-runs files when it first
-- adopts a database initdb built.
\getenv fks_db RUBY_DB
\connect :fks_db

ALTER TABLE bot_configs DROP CONSTRAINT IF EXISTS bot_configs_mode_valid;
ALTER TABLE bot_configs ADD CONSTRAINT bot_configs_mode_valid CHECK (
    mode IN ('paper', 'live', 'backtest', 'optimise', 'train', 'record')
);
