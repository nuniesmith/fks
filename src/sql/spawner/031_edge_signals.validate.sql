-- Adversarial suite for 031_edge_signals.sql. NOT a migration. Run against a
-- scratch database with 017-031 applied:
--   psql -d fks_db -f 031_edge_signals.validate.sql
-- Every attack (S-F*) must print "refused"; every control (S-C*) "ok".
BEGIN;
INSERT INTO accounts (account_id, tier, account_class, role) VALUES ('sig-test', 1, 'prop', 'watch');
INSERT INTO edge_experiments (id, study_name, config_fingerprint, symbol, bar_minutes, n_trials, verdict,
                              selected_params, finished_at, holdout_returns)
VALUES (999501, 'sig-test', 'orb:test', 'MES+MNQ', 1, 1, 'USABLE', '{"orb_minutes": 15}',
        now() - interval '40 days', '{0.001,-0.001}');
INSERT INTO edge_deployments (id, experiment_id, account_id, symbol, params_snapshot, forward_sessions_required)
VALUES (999501, 999501, 'sig-test', 'MES+MNQ', '{"orb_minutes": 15}', 20),
       (999502, 999501, 'sig-test', 'MES+MNQ', '{"orb_minutes": 15}', 20);
UPDATE edge_deployments SET stage = 'forward' WHERE id = 999501;

CREATE FUNCTION pg_temp.say(p_dep BIGINT, p_kind TEXT, p_symbol TEXT DEFAULT 'MES',
                            p_day DATE DEFAULT current_date) RETURNS BIGINT LANGUAGE sql AS $$
    INSERT INTO edge_signals (deployment_id, session_date, symbol, kind, stage, contract, side, price,
                              stop, target, bar_at, reason, runner, code_version)
    VALUES (p_dep, p_day, p_symbol, p_kind, 'live', 'ESZ6',
            CASE WHEN p_kind = 'range' THEN NULL ELSE 1 END, 6000, 5990, 6020, now(), 'test', 'sig', 'abc')
    RETURNING id
$$;
SAVEPOINT clean;

DO $$ DECLARE s TEXT; BEGIN
  PERFORM pg_temp.say(999501, 'entry');
  SELECT stage INTO s FROM edge_signals WHERE deployment_id = 999501;
  IF s = 'forward' THEN RAISE NOTICE 'S-C1 a forward signal is paper   : ok';
  ELSE RAISE NOTICE 'S-C1 a forward signal is paper   : *** WRONG *** %', s; END IF;
END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  PERFORM pg_temp.say(999501, 'entry');
  PERFORM pg_temp.say(999501, 'entry');
  RAISE NOTICE 'S-F1 the same entry twice         : *** SUCCEEDED ***';
EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'S-F1 the same entry twice         : refused'; END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  PERFORM pg_temp.say(999502, 'entry');
  RAISE NOTICE 'S-F2 a backtest deployment signals: *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'S-F2 a backtest deployment signals: refused'; END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  PERFORM pg_temp.say(999501, 'entry', 'MGC');
  RAISE NOTICE 'S-F3 a symbol it doesn''t trade    : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'S-F3 a symbol it doesn''t trade    : refused'; END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  PERFORM pg_temp.say(999501, 'entry', 'MES', current_date + 2);
  RAISE NOTICE 'S-F4 a session not started        : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'S-F4 a session not started        : refused'; END $$;
ROLLBACK TO clean;

DO $$ DECLARE i BIGINT; BEGIN
  i := pg_temp.say(999501, 'entry');
  UPDATE edge_signals SET delivered_at = now() WHERE id = i;
  BEGIN
    UPDATE edge_signals SET price = 6100 WHERE id = i;
    RAISE NOTICE 'S-F5a rewrite what was said       : *** SUCCEEDED ***';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'S-F5a rewrite what was said       : refused'; END;
  BEGIN
    UPDATE edge_signals SET delivered_at = now() + interval '1 hour' WHERE id = i;
    RAISE NOTICE 'S-F5b deliver it twice            : *** SUCCEEDED ***';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'S-F5b deliver it twice            : refused'; END;
  BEGIN
    DELETE FROM edge_signals WHERE id = i;
    RAISE NOTICE 'S-F5c delete it                   : *** SUCCEEDED ***';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'S-F5c delete it                   : refused'; END;
END $$;
ROLLBACK TO clean;

DO $$ BEGIN
  INSERT INTO edge_signals (deployment_id, session_date, symbol, kind, stage, contract, side, price,
                            bar_at, reason, runner, code_version)
  VALUES (999501, current_date, 'MES', 'exit', 'live', 'ESZ6', NULL, 6000, now(), 'x', 'sig', 'abc');
  RAISE NOTICE 'S-F6 an exit without a side       : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'S-F6 an exit without a side       : refused'; END $$;
ROLLBACK TO clean;

-- The runner's role: inserts and marks delivered; nothing else.
SET LOCAL ROLE fks_backtest;
DO $$ DECLARE i BIGINT; BEGIN
  i := pg_temp.say(999501, 'range');
  UPDATE edge_signals SET delivered_at = now() WHERE id = i;
  RAISE NOTICE 'S-C2 the runner says and delivers : ok';
EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'S-C2 the runner says and delivers : *** REFUSED *** %', SQLERRM; END $$;
DO $$ BEGIN
  UPDATE edge_signals SET reason = 'x';
  RAISE NOTICE 'S-F7 the runner rewrites a reason : *** SUCCEEDED ***';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'S-F7 the runner rewrites a reason : refused'; END $$;
RESET ROLE;
ROLLBACK TO clean;

ROLLBACK;
