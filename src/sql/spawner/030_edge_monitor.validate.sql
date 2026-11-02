-- Adversarial suite for 030_edge_monitor.sql. NOT a migration. Run against a
-- scratch database with 017-030 applied:
--   psql -d fks_db -f 030_edge_monitor.validate.sql
-- Every attack (M-F*) must print "refused"; every control (M-C*) "ok".
-- Each case starts from the same clean state (savepoints); nothing is kept.
--
-- The fixture's holdout alternates +0.003 / -0.001: mean 0.001, sd ≈ 0.00203,
-- per-session Sharpe ≈ 0.49, so k = 0.246 and h ≈ 7.35. Sessions at the
-- holdout's mean sit inside the band and never move the CUSUM; sessions of
-- -0.002 (z ≈ -1.5) fail a 5-session band; sessions of -0.004 (z ≈ -2.5)
-- trip the CUSUM in 4.
--
-- Checked non-vacuous on 2026-11-02: with 029's functions re-applied over
-- this schema (no monitor), M-F1, M-F2 and M-F7 print SUCCEEDED and M-C4,
-- M-C5, M-C7 WRONG: a forward window that lost every session went live and
-- nothing retired. M-F3 (029's freeze) and M-F4 (a CHECK) stay refused;
-- M-F5/M-F6 test 030's own table.
BEGIN;
INSERT INTO accounts (account_id, tier, account_class, role) VALUES ('mon-test', 1, 'personal', 'watch');
INSERT INTO edges (edge_id, edge_type) VALUES ('mon-test', 'rule');
INSERT INTO edge_hypotheses (id, edge_id, idea, symbols, dataset, holdout_share, params, baseline, metric, costs, evidence,
                             registered_at)
VALUES (999601, 'mon-test', 'A long-only trend band beats the hand-picked 200-day rule after costs.',
        '{BTCUSDT}', 'raw/binance/spot/spot-history 1d 2017-08-17..2026-10-31', 0.25,
        '[{"name":"lookback","min":60,"max":360,"step":20}]', 'buy-and-hold', 'sharpe after fees', '{}',
        'low-frequency', now() - interval '60 days');
INSERT INTO edge_experiments (id, study_name, config_fingerprint, symbol, bar_minutes, tuned_params, n_trials,
                              verdict, verdict_reasons, outcome, selected_params, finished_at, holdout_returns,
                              hypothesis_id)
VALUES (999601, 'mon-test', 'orb:test', 'MES', 1, '{}', 1, 'USABLE', '{}', 'pending', '{"orb_minutes": 15}',
        now() - interval '40 days',
        ARRAY(SELECT CASE WHEN g % 2 = 0 THEN 0.003 ELSE -0.001 END FROM generate_series(1, 40) g), NULL),
       (999602, 'mon-test-no-holdout', 'orb:test', 'MES', 1, '{}', 1, 'USABLE', '{}', 'pending',
        '{"orb_minutes": 15}', now() - interval '40 days', NULL, NULL),
       (999603, 'mon-test-lf', 'trend-band:test', 'BTCUSDT', 1440, '{}', 1, 'USABLE', '{}', 'pending',
        '{"lookback": 200}', now() - interval '40 days', NULL, 999601);
INSERT INTO edge_deployments (id, experiment_id, account_id, symbol, params_snapshot, forward_sessions_required)
VALUES (999601, 999601, 'mon-test', 'MES', '{"orb_minutes": 15}', 5),
       (999602, 999602, 'mon-test', 'MES', '{"orb_minutes": 15}', 5),
       (999603, 999603, 'mon-test', 'BTCUSDT', '{"lookback": 200}', 3),
       (999604, 999601, 'mon-test', 'MES', '{"orb_minutes": 15}', 20);
UPDATE edge_deployments SET stage = 'forward' WHERE id IN (999601, 999604);
-- Fixture only: they entered forward 30 days ago (the guard stamps since).
ALTER TABLE edge_deployments DISABLE TRIGGER trg_edge_deployments_promotion;
UPDATE edge_deployments SET since = now() - interval '30 days' WHERE id IN (999601, 999604);
ALTER TABLE edge_deployments ENABLE TRIGGER trg_edge_deployments_promotion;

-- n sessions of return r for a deployment, the last ending p_ago days ago.
CREATE FUNCTION pg_temp.sessions(p_dep BIGINT, p_n INT, p_r DOUBLE PRECISION, p_ago INT DEFAULT 1,
                                 p_symbol TEXT DEFAULT 'MES')
RETURNS VOID LANGUAGE sql AS $$
    INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return,
                                       data_ref, runner, code_version)
    SELECT p_dep, current_date - (p_n + p_ago) + g, p_symbol, p_r <> 0,
           CASE WHEN p_r <> 0 THEN '{"side": 1}'::jsonb END, p_r,
           '[{"path": "ES/1m/x.csv.gz", "sha256": "ab"}]', 'mon', 'abc123'
      FROM generate_series(1, p_n) g
$$;
SAVEPOINT clean;

-- M-C1: health before any session: the holdout is read, the band waits.
DO $$ DECLARE h JSONB; BEGIN
  h := edge_deployment_health(999601);
  IF (h->>'applies')::boolean AND h->'band'->>'verdict' = 'pending'
     AND abs((h->'holdout'->>'mean')::float8 - 0.001) < 1e-12
     AND abs((h->'cusum'->>'h')::float8 - edge_monitor_cusum_h((h->'cusum'->>'k')::float8, 500)) < 1e-12
  THEN RAISE NOTICE 'M-C1 health before sessions   : ok';
  ELSE RAISE NOTICE 'M-C1 health before sessions   : *** WRONG *** %', h; END IF;
END $$;
ROLLBACK TO clean;

-- M-F1: start forward with nothing to judge against.
DO $$ BEGIN
  UPDATE edge_deployments SET stage = 'forward' WHERE id = 999602;
  RAISE NOTICE 'M-F1 forward without a holdout : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-F1 forward without a holdout : refused'; END $$;
ROLLBACK TO clean;

-- M-C2: a low-frequency edge needs no holdout series (judged on mechanics).
DO $$ BEGIN
  UPDATE edge_deployments SET stage = 'forward' WHERE id = 999603;
  IF NOT (edge_deployment_health(999603)->>'applies')::boolean
  THEN RAISE NOTICE 'M-C2 low-frequency goes forward: ok';
  ELSE RAISE NOTICE 'M-C2 low-frequency goes forward: *** WRONG ***'; END IF;
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-C2 low-frequency goes forward: *** REFUSED *** %', SQLERRM; END $$;
ROLLBACK TO clean;

-- M-C3: five sessions at the holdout's mean pass the band and may go live.
DO $$ DECLARE h JSONB; BEGIN
  PERFORM pg_temp.sessions(999601, 5, 0.001);
  h := edge_deployment_health(999601);
  UPDATE edge_deployments SET stage = 'live' WHERE id = 999601;
  IF h->'band'->>'verdict' = 'pass' AND (h->'cusum'->>'value')::float8 = 0
  THEN RAISE NOTICE 'M-C3 a sound window goes live  : ok';
  ELSE RAISE NOTICE 'M-C3 a sound window goes live  : *** WRONG *** %', h; END IF;
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-C3 a sound window goes live  : *** REFUSED *** %', SQLERRM; END $$;
ROLLBACK TO clean;

-- M-F2: five losing sessions, then go live. The fifth retires it.
DO $$ BEGIN
  PERFORM pg_temp.sessions(999601, 5, -0.002);
  UPDATE edge_deployments SET stage = 'live' WHERE id = 999601;
  RAISE NOTICE 'M-F2 a failed window goes live : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-F2 a failed window goes live : refused'; END $$;
ROLLBACK TO clean;

-- M-C4: ...and what refused it is the monitor: retired, said why, event left.
DO $$ DECLARE s TEXT; why TEXT; n INT; BEGIN
  PERFORM pg_temp.sessions(999601, 5, -0.002);
  SELECT stage, retired_reason INTO s, why FROM edge_deployments WHERE id = 999601;
  SELECT count(*) INTO n FROM edge_monitor_events WHERE deployment_id = 999601 AND kind = 'retired';
  IF s = 'retired' AND why LIKE 'monitor (%band floor%' AND n = 1
  THEN RAISE NOTICE 'M-C4 the band retires it       : ok';
  ELSE RAISE NOTICE 'M-C4 the band retires it       : *** WRONG *** % / % / %', s, why, n; END IF;
END $$;
ROLLBACK TO clean;

-- M-F3: four losing sessions out of five required: go live anyway (the old
-- rule refuses this too; the point is what follows in M-C5).
-- M-C5: a steady loss trips the CUSUM before the 20-session window ends.
DO $$ DECLARE s TEXT; why TEXT; BEGIN
  PERFORM pg_temp.sessions(999604, 4, -0.004);
  SELECT stage, retired_reason INTO s, why FROM edge_deployments WHERE id = 999604;
  IF s = 'retired' AND why LIKE 'monitor (%CUSUM%'
  THEN RAISE NOTICE 'M-C5 the CUSUM retires it      : ok';
  ELSE RAISE NOTICE 'M-C5 the CUSUM retires it      : *** WRONG *** % / %', s, why; END IF;
END $$;
ROLLBACK TO clean;

-- M-F3: move the reference after seeing the forward results.
DO $$ BEGIN
  UPDATE edge_experiments SET holdout_returns = '{-0.01,-0.02}' WHERE id = 999601;
  RAISE NOTICE 'M-F3 lower the reference       : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-F3 lower the reference       : refused'; END $$;
ROLLBACK TO clean;

-- M-F4: a reference that isn't a number.
DO $$ BEGIN
  INSERT INTO edge_experiments (study_name, config_fingerprint, symbol, bar_minutes, n_trials, verdict, holdout_returns)
  VALUES ('mon-test-nan', 'orb:test', 'MES', 1, 1, 'USABLE', '{0.001,NaN}');
  RAISE NOTICE 'M-F4 a NaN in the reference    : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-F4 a NaN in the reference    : refused'; END $$;
ROLLBACK TO clean;

-- M-F5: rewrite, re-deliver or delete what the monitor did.
DO $$ DECLARE e BIGINT; BEGIN
  PERFORM pg_temp.sessions(999601, 5, -0.002);
  SELECT id INTO e FROM edge_monitor_events WHERE deployment_id = 999601;
  UPDATE edge_monitor_events SET delivered_at = now() WHERE id = e;  -- allowed, once
  BEGIN
    UPDATE edge_monitor_events SET reason = 'nothing happened' WHERE id = e;
    RAISE NOTICE 'M-F5a rewrite an event         : *** SUCCEEDED ***';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-F5a rewrite an event         : refused'; END;
  BEGIN
    UPDATE edge_monitor_events SET delivered_at = now() + interval '1 hour' WHERE id = e;
    RAISE NOTICE 'M-F5b deliver an event twice   : *** SUCCEEDED ***';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-F5b deliver an event twice   : refused'; END;
  BEGIN
    DELETE FROM edge_monitor_events WHERE id = e;
    RAISE NOTICE 'M-F5c delete an event          : *** SUCCEEDED ***';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-F5c delete an event          : refused'; END;
END $$;
ROLLBACK TO clean;

-- M-C6: once live, sessions keep being recorded, as live rows, and don't
-- count toward the forward requirement; a row claiming 'forward' is relabelled.
DO $$ DECLARE n INT; l INT; BEGIN
  PERFORM pg_temp.sessions(999601, 5, 0.001, 5);
  UPDATE edge_deployments SET stage = 'live' WHERE id = 999601;
  ALTER TABLE edge_deployments DISABLE TRIGGER trg_edge_deployments_promotion;
  UPDATE edge_deployments SET since = now() - interval '3 days' WHERE id = 999601;
  ALTER TABLE edge_deployments ENABLE TRIGGER trg_edge_deployments_promotion;
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade, session_return,
                                     data_ref, runner, code_version, stage)
  VALUES (999601, current_date - 1, 'MES', TRUE, '{"side": 1}', 0.001, '[{"path": "a", "sha256": "1"}]',
          'mon', 'abc', 'forward');
  SELECT forward_sessions_observed INTO n FROM edge_deployments WHERE id = 999601;
  SELECT count(*) INTO l FROM edge_forward_sessions WHERE deployment_id = 999601 AND stage = 'live';
  IF n = 5 AND l = 1 THEN RAISE NOTICE 'M-C6 live sessions are live    : ok';
  ELSE RAISE NOTICE 'M-C6 live sessions are live    : *** WRONG *** observed % live rows %', n, l; END IF;
END $$;
ROLLBACK TO clean;

-- M-C7: the research role records the session that breaches; the monitor
-- (SECURITY DEFINER) still retires it. M-F6: that role writes no events.
SET LOCAL ROLE fks_backtest;
DO $$ DECLARE s TEXT; BEGIN
  PERFORM pg_temp.sessions(999601, 5, -0.002);
  SELECT stage INTO s FROM edge_deployments WHERE id = 999601;
  IF s = 'retired' THEN RAISE NOTICE 'M-C7 the runner role breaches  : ok';
  ELSE RAISE NOTICE 'M-C7 the runner role breaches  : *** WRONG *** %', s; END IF;
END $$;
DO $$ BEGIN
  INSERT INTO edge_monitor_events (deployment_id, kind, reason, health) VALUES (999604, 'retired', 'x', '{}');
  RAISE NOTICE 'M-F6 the runner role forges one: *** SUCCEEDED ***';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'M-F6 the runner role forges one: refused'; END $$;
RESET ROLE;
ROLLBACK TO clean;

-- M-F7: a deployment that ran forward before the monitor (no holdout) goes live.
DO $$ BEGIN
  ALTER TABLE edge_deployments DISABLE TRIGGER trg_edge_deployments_promotion;
  UPDATE edge_deployments SET stage = 'forward', since = now() - interval '30 days' WHERE id = 999602;
  ALTER TABLE edge_deployments ENABLE TRIGGER trg_edge_deployments_promotion;
  PERFORM pg_temp.sessions(999602, 5, 0.001);
  UPDATE edge_deployments SET stage = 'live' WHERE id = 999602;
  RAISE NOTICE 'M-F7 live with nothing judged  : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'M-F7 live with nothing judged  : refused'; END $$;
ROLLBACK TO clean;

ROLLBACK;
