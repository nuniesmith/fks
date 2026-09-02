\set ON_ERROR_STOP on
BEGIN;

\i 018_edge_deployments.sql

-- Fixtures, inside the transaction so nothing survives the rollback.
INSERT INTO accounts (account_id, tier, account_class, role)
VALUES ('test-prop', 2, 'prop', 'human-trade-source'),
       ('test-personal', 1, 'personal-crypto', 'bot-trade');

INSERT INTO edge_experiments
    (study_name, config_fingerprint, symbol, bar_minutes, n_trials, verdict)
VALUES ('t-usable', 'fp', 'GC', 5, 100, 'USABLE'),
       ('t-reject', 'fp', 'GC', 5, 100, 'DO NOT PASTE');

CREATE TEMP TABLE results (ok BOOLEAN, label TEXT);

CREATE OR REPLACE FUNCTION expect_reject(sql TEXT, label TEXT) RETURNS VOID AS $f$
BEGIN
    EXECUTE sql;
    INSERT INTO results VALUES (FALSE, 'NOT REJECTED: ' || label);
EXCEPTION WHEN check_violation OR unique_violation OR foreign_key_violation
       OR not_null_violation THEN
    INSERT INTO results VALUES (TRUE, 'rejected: ' || label);
END;
$f$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION expect_ok(sql TEXT, label TEXT) RETURNS VOID AS $f$
BEGIN
    EXECUTE sql;
    INSERT INTO results VALUES (TRUE, 'allowed:  ' || label);
EXCEPTION WHEN OTHERS THEN
    INSERT INTO results VALUES (FALSE, 'WRONGLY REJECTED: ' || label || ' -- ' || SQLERRM);
END;
$f$ LANGUAGE plpgsql;

-- ── entry point ─────────────────────────────────────────────────────────────
SELECT expect_ok($$
  INSERT INTO edge_deployments (id, experiment_id, account_id, symbol, params_snapshot)
  SELECT 1, id, 'test-personal', 'GC', '{}' FROM edge_experiments WHERE study_name='t-usable'
$$, 'INSERT starts at backtest');

SELECT expect_reject($$
  INSERT INTO edge_deployments (experiment_id, account_id, symbol, params_snapshot, stage)
  SELECT id, 'test-personal', 'ES', '{}', 'live' FROM edge_experiments WHERE study_name='t-usable'
$$, 'INSERT directly at live (walks around every rule)');

-- ── prop accounts can never be automated ────────────────────────────────────
SELECT expect_reject($$
  INSERT INTO edge_deployments (experiment_id, account_id, symbol, params_snapshot, execution)
  SELECT id, 'test-prop', 'GC', '{}', 'auto' FROM edge_experiments WHERE study_name='t-usable'
$$, 'execution=auto on a PROP account');

SELECT expect_ok($$
  INSERT INTO edge_deployments (experiment_id, account_id, symbol, params_snapshot, execution)
  SELECT id, 'test-personal', 'NQ', '{}', 'auto' FROM edge_experiments WHERE study_name='t-usable'
$$, 'execution=auto on a PERSONAL account');

-- ── backtest -> forward needs a USABLE verdict AND a declared N ─────────────
SELECT expect_reject($$
  INSERT INTO edge_deployments (id, experiment_id, account_id, symbol, params_snapshot)
  SELECT 2, id, 'test-personal', 'CL', '{}' FROM edge_experiments WHERE study_name='t-reject';
  UPDATE edge_deployments SET stage='forward', forward_sessions_required=20 WHERE id=2
$$, 'backtest->forward on a DO NOT PASTE experiment');

SELECT expect_reject($$
  UPDATE edge_deployments SET stage='forward' WHERE id=1
$$, 'backtest->forward without declaring forward_sessions_required');

SELECT expect_reject($$
  UPDATE edge_deployments SET stage='live' WHERE id=1
$$, 'backtest->live (skipping a rung)');

SELECT expect_ok($$
  UPDATE edge_deployments SET stage='forward', forward_sessions_required=20 WHERE id=1
$$, 'backtest->forward with USABLE + declared N');

-- ── the bar cannot move once the test is underway ───────────────────────────
SELECT expect_reject($$
  UPDATE edge_deployments SET forward_sessions_required=2 WHERE id=1
$$, 'lowering forward_sessions_required after leaving backtest');

-- ── forward -> live needs the declared evidence ─────────────────────────────
SELECT expect_reject($$
  UPDATE edge_deployments SET stage='live', forward_sessions_observed=19 WHERE id=1
$$, 'forward->live with 19 of 20 sessions');

SELECT expect_ok($$
  UPDATE edge_deployments SET stage='live', forward_sessions_observed=20 WHERE id=1
$$, 'forward->live with 20 of 20 sessions');

-- ── one live edge per instrument per account ────────────────────────────────
SELECT expect_reject($$
  INSERT INTO edge_deployments (id, experiment_id, account_id, symbol, params_snapshot,
                                stage, forward_sessions_required, forward_sessions_observed)
  SELECT 3, id, 'test-personal', 'GC', '{}', 'backtest', NULL, 0
    FROM edge_experiments WHERE study_name='t-usable';
  UPDATE edge_deployments SET stage='forward', forward_sessions_required=1 WHERE id=3;
  UPDATE edge_deployments SET stage='live', forward_sessions_observed=1 WHERE id=3
$$, 'a SECOND live edge on the same (account, symbol)');

-- ── retirement: unconditional, but must say why, and is terminal ────────────
SELECT expect_reject($$
  UPDATE edge_deployments SET stage='retired' WHERE id=1
$$, 'retiring without a reason');

SELECT expect_ok($$
  UPDATE edge_deployments SET stage='retired', retired_reason='divergence' WHERE id=1
$$, 'live->retired with a reason (no approval needed)');

SELECT expect_reject($$
  UPDATE edge_deployments SET stage='live' WHERE id=1
$$, 'un-retiring (retired is terminal)');

-- ── report ──────────────────────────────────────────────────────────────────
SELECT CASE WHEN ok THEN '  PASS  ' ELSE '  ****FAIL**** ' END || label AS outcome
  FROM results ORDER BY ctid;
SELECT count(*) FILTER (WHERE NOT ok) AS failures, count(*) AS total FROM results;

ROLLBACK;
