-- Adversarial suite for 029_edge_forward_sessions.sql. NOT a migration. Run
-- against a scratch database that has 018, 020, 025 and 029:
--   psql -d fks_db -f 029_edge_forward_sessions.validate.sql
-- Every attack (F*) must print "refused"; every control (C*) must print "ok".
-- Each case starts from the same clean state (savepoints); nothing is kept.
--
-- Checked non-vacuous on 2026-11-02: with 020's guard restored and the
-- ledger's admit trigger dropped (the schema before 029), F1-F6 and F8-F12
-- print SUCCEEDED: on that schema a counter of 999 and a promotion to live
-- pass in one statement. F7 (the unique key), F13 (a CHECK) and F14 (the
-- grants) stay refused without them.
BEGIN;
INSERT INTO accounts (account_id, tier, account_class, role) VALUES ('fwd-test', 1, 'prop', 'watch');
INSERT INTO edge_experiments (id, study_name, config_fingerprint, symbol, bar_minutes,
                              tuned_params, n_trials, verdict, verdict_reasons, outcome)
VALUES (999701, 'fwd-test', 'orb:test', 'MES', 1, '{}', 1, 'USABLE', '{}', 'pending');
INSERT INTO edge_deployments (id, experiment_id, account_id, symbol, params_snapshot, forward_sessions_required)
VALUES (999701, 999701, 'fwd-test', 'MES', '{"orb_minutes": 15}'::jsonb, 20),
       (999702, 999701, 'fwd-test', 'MES', '{"orb_minutes": 15}'::jsonb, 20),
       (999703, 999701, 'fwd-test', 'MES', '{"orb_minutes": 15}'::jsonb, 3);
UPDATE edge_deployments SET stage = 'forward' WHERE id IN (999701, 999703);
-- Fixture only: they entered forward 30 days ago (the guard now stamps since).
ALTER TABLE edge_deployments DISABLE TRIGGER trg_edge_deployments_promotion;
UPDATE edge_deployments SET since = now() - interval '30 days' WHERE id IN (999701, 999703);
ALTER TABLE edge_deployments ENABLE TRIGGER trg_edge_deployments_promotion;
SAVEPOINT clean;

-- C1: a session that happened yesterday-ish is recorded and counted.
DO $$ DECLARE n INT; BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 3, 'MES', TRUE, '{"side": 1}', 0.0012, '[{"path": "ES/1m/x.csv.gz", "sha256": "ab"}]', 'fwd', 'abc123');
  SELECT forward_sessions_observed INTO n FROM edge_deployments WHERE id = 999701;
  IF n = 1 THEN RAISE NOTICE 'C1 record one session       : ok';
  ELSE RAISE NOTICE 'C1 record one session       : *** WRONG *** observed %', n; END IF;
END $$;
ROLLBACK TO clean;

-- C2: two sessions in one statement count two.
DO $$ DECLARE n INT; BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 3, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc'),
         (999701, current_date - 2, 'MES', FALSE, NULL, 0, '[{"path": "b", "sha256": "2"}]', 'fwd', 'abc');
  SELECT forward_sessions_observed INTO n FROM edge_deployments WHERE id = 999701;
  IF n = 2 THEN RAISE NOTICE 'C2 two in one statement      : ok';
  ELSE RAISE NOTICE 'C2 two in one statement      : *** WRONG *** observed %', n; END IF;
END $$;
ROLLBACK TO clean;

-- F1: write the counter.
DO $$ BEGIN
  UPDATE edge_deployments SET forward_sessions_observed = 20 WHERE id = 999701;
  RAISE NOTICE 'F1 forge the counter         : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F1 forge the counter         : refused'; END $$;
ROLLBACK TO clean;

-- F2: write the counter and go live in one statement.
DO $$ BEGIN
  UPDATE edge_deployments SET forward_sessions_observed = 20, stage = 'live' WHERE id = 999701;
  RAISE NOTICE 'F2 forge and go live         : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F2 forge and go live         : refused'; END $$;
ROLLBACK TO clean;

-- F3: a session from before the deployment entered forward.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 31, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  RAISE NOTICE 'F3 before the forward start  : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F3 before the forward start  : refused'; END $$;
ROLLBACK TO clean;

-- F4: today's session, before it is over.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, (now() AT TIME ZONE 'UTC')::date, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  RAISE NOTICE 'F4 a session not over yet    : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F4 a session not over yet    : refused'; END $$;
ROLLBACK TO clean;

-- F5: a backfill 15 days later.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 15, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  RAISE NOTICE 'F5 a late backfill           : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F5 a late backfill           : refused'; END $$;
ROLLBACK TO clean;

-- F6: rewrite a recorded session, then delete one.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 3, 'MES', TRUE, '{"side": -1}', -0.004, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  UPDATE edge_forward_sessions SET session_return = 0.004, trade = '{"side": 1}' WHERE deployment_id = 999701;
  RAISE NOTICE 'F6a rewrite a session        : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F6a rewrite a session        : refused'; END $$;
ROLLBACK TO clean;
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 3, 'MES', TRUE, '{"side": -1}', -0.004, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  DELETE FROM edge_forward_sessions WHERE deployment_id = 999701;
  RAISE NOTICE 'F6b delete a session         : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F6b delete a session         : refused'; END $$;
ROLLBACK TO clean;

-- F7: the same session twice.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 3, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc'),
         (999701, current_date - 3, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  RAISE NOTICE 'F7 one session twice         : *** SUCCEEDED ***';
EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'F7 one session twice         : refused'; END $$;
ROLLBACK TO clean;

-- F8: a session for a deployment still at backtest.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999702, current_date - 3, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  RAISE NOTICE 'F8 not at forward            : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F8 not at forward            : refused'; END $$;
ROLLBACK TO clean;

-- F9: a session of another symbol.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 3, 'MNQ', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  RAISE NOTICE 'F9 another symbol            : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F9 another symbol            : refused'; END $$;
ROLLBACK TO clean;

-- F10: swap what is deployed (params, then symbol).
DO $$ BEGIN
  UPDATE edge_deployments SET params_snapshot = '{"orb_minutes": 30}' WHERE id = 999701;
  RAISE NOTICE 'F10a swap the parameters     : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F10a swap the parameters     : refused'; END $$;
ROLLBACK TO clean;
DO $$ BEGIN
  UPDATE edge_deployments SET symbol = 'MNQ' WHERE id = 999702;
  RAISE NOTICE 'F10b swap the symbol         : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F10b swap the symbol         : refused'; END $$;
ROLLBACK TO clean;

-- F11: move the forward start earlier.
DO $$ BEGIN
  UPDATE edge_deployments SET since = since - interval '60 days' WHERE id = 999701;
  RAISE NOTICE 'F11 move the forward start   : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F11 move the forward start   : refused'; END $$;
ROLLBACK TO clean;

-- F12: a deployment born with evidence.
DO $$ BEGIN
  INSERT INTO edge_deployments (experiment_id, account_id, symbol, params_snapshot, forward_sessions_observed)
  VALUES (999701, 'fwd-test', 'MES', '{}', 5);
  RAISE NOTICE 'F12 born with evidence       : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F12 born with evidence       : refused'; END $$;
ROLLBACK TO clean;

-- F13: a flat session with a return; a traded one without its trade.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 3, 'MES', FALSE, NULL, 0.01, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  RAISE NOTICE 'F13 a flat day that earned   : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'F13 a flat day that earned   : refused'; END $$;
ROLLBACK TO clean;

-- C3: three recorded sessions meet a requirement of three: live is allowed.
DO $$ BEGIN
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  SELECT 999703, current_date - g, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc'
    FROM generate_series(1, 3) g;
  UPDATE edge_deployments SET stage = 'live' WHERE id = 999703;
  RAISE NOTICE 'C3 live after the ledger     : ok';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'C3 live after the ledger     : *** REFUSED ***'; END $$;
ROLLBACK TO clean;

-- C4 / F14: the research role records a session (the counter follows,
-- through the SECURITY DEFINER trigger), but can't write the counter itself.
DO $$ DECLARE n INT; BEGIN
  SET LOCAL ROLE fks_backtest;
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return, data_ref, runner, code_version)
  VALUES (999701, current_date - 3, 'MES', FALSE, NULL, 0, '[{"path": "a", "sha256": "1"}]', 'fwd', 'abc');
  SELECT forward_sessions_observed INTO n FROM edge_deployments WHERE id = 999701;
  RESET ROLE;
  IF n = 1 THEN RAISE NOTICE 'C4 the runner role records   : ok';
  ELSE RAISE NOTICE 'C4 the runner role records   : *** WRONG *** observed %', n; END IF;
END $$;
ROLLBACK TO clean;
DO $$ BEGIN
  SET LOCAL ROLE fks_backtest;
  UPDATE edge_deployments SET forward_sessions_observed = 20 WHERE id = 999701;
  RESET ROLE;
  RAISE NOTICE 'F14 the runner role forges   : *** SUCCEEDED ***';
EXCEPTION WHEN insufficient_privilege OR check_violation THEN RAISE NOTICE 'F14 the runner role forges   : refused'; END $$;
ROLLBACK TO clean;

ROLLBACK;
