-- Adversarial suite for 032_edge_signals_open_exit.sql. NOT a migration. Run
-- against a scratch database with 017-032 applied:
--   psql -d fks_db -f 032_edge_signals_open_exit.validate.sql
-- Every attack (O-F*) must print "refused"; every control (O-C*) "ok".
--
-- Checked non-vacuous on 2026-11-02: with 031's edge_signals_admit()
-- re-applied, O-C1 prints REFUSED (the open trade's exit was lost).
BEGIN;
INSERT INTO accounts (account_id, tier, account_class, role) VALUES ('open-test', 1, 'prop', 'watch');
INSERT INTO edge_experiments (id, study_name, config_fingerprint, symbol, bar_minutes, n_trials, verdict,
                              selected_params, finished_at, holdout_returns)
VALUES (999401, 'open-test', 'orb:test', 'MES+MNQ', 1, 1, 'USABLE', '{"orb_minutes": 15}',
        now() - interval '40 days', '{0.001,-0.001}');
INSERT INTO edge_deployments (id, experiment_id, account_id, symbol, params_snapshot, forward_sessions_required)
VALUES (999401, 999401, 'open-test', 'MES+MNQ', '{"orb_minutes": 15}', 20);
UPDATE edge_deployments SET stage = 'forward' WHERE id = 999401;

CREATE FUNCTION pg_temp.say(p_kind TEXT, p_symbol TEXT DEFAULT 'MES') RETURNS BIGINT LANGUAGE sql AS $$
    INSERT INTO edge_signals (deployment_id, session_date, symbol, kind, stage, contract, side, price,
                              stop, target, bar_at, reason, runner, code_version)
    VALUES (999401, current_date, p_symbol, p_kind, 'live', 'ESZ6',
            CASE WHEN p_kind = 'range' THEN NULL ELSE 1 END, 6000, 5990, 6020, now(), 'test', 'sig', 'abc')
    RETURNING id
$$;
-- The morning: the range and an MES entry, said while forward. Then retired.
SELECT pg_temp.say('range');
SELECT pg_temp.say('entry');
UPDATE edge_deployments SET stage = 'retired', retired_reason = 'monitor (test): retired mid-session'
 WHERE id = 999401;
SAVEPOINT clean;

DO $$ DECLARE s TEXT; BEGIN
  PERFORM pg_temp.say('exit');
  SELECT stage INTO s FROM edge_signals WHERE deployment_id = 999401 AND kind = 'exit';
  IF s = 'forward' THEN RAISE NOTICE 'O-C1 the open trade''s exit is said: ok';
  ELSE RAISE NOTICE 'O-C1 the open trade''s exit is said: *** WRONG *** stage %', s; END IF;
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'O-C1 the open trade''s exit is said: *** REFUSED *** %', SQLERRM; END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  PERFORM pg_temp.say('entry', 'MNQ');
  RAISE NOTICE 'O-F1 a new entry once retired     : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'O-F1 a new entry once retired     : refused'; END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  PERFORM pg_temp.say('range', 'MNQ');
  RAISE NOTICE 'O-F2 a range once retired         : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'O-F2 a range once retired         : refused'; END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  PERFORM pg_temp.say('exit', 'MNQ');
  RAISE NOTICE 'O-F3 an exit with no entry        : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'O-F3 an exit with no entry        : refused'; END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  PERFORM pg_temp.say('exit');
  PERFORM pg_temp.say('exit');
  RAISE NOTICE 'O-F4 the same exit twice          : *** SUCCEEDED ***';
EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'O-F4 the same exit twice          : refused'; END $$;
ROLLBACK TO clean;

ROLLBACK;
