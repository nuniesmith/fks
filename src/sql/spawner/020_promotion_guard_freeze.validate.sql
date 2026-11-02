-- Adversarial suite for edge_deployments_promotion_guard().
--
-- Each case runs from an IDENTICAL clean state via savepoints. The first draft
-- ran them sequentially in one transaction and the results were contaminated:
-- a successful attack moved the row to 'live', after which the next "attack"
-- was a same-stage no-op that reported success for the wrong reason.
--
-- It also lowered the requirement to 0, which the table CHECK
-- (forward_required_positive) rejects independently of the guard — so a refusal
-- proved nothing. The realistic attack lowers 20 -> 1.
BEGIN;
-- selected_params (029): a deployment trades exactly its search's selection.
INSERT INTO edge_experiments (id, study_name, config_fingerprint, symbol, bar_minutes,
                              tuned_params, n_trials, verdict, verdict_reasons, outcome, selected_params, finished_at)
VALUES (999901, 'guard-test', 'fp-test', 'GC', 5, '{}', 1, 'USABLE', '{}', 'pending', '{}', now() - interval '1 day');

INSERT INTO edge_deployments (id, experiment_id, account_id, symbol, stage, execution,
                              params_snapshot, forward_sessions_required, forward_sessions_observed)
VALUES (999901, 999901, 'crypto-spot', 'GC', 'backtest', 'manual', '{}'::jsonb, 20, 0);
UPDATE edge_deployments SET stage='forward' WHERE id=999901;
SAVEPOINT clean;

-- A1: promote AND lower the bar to something the CHECK still allows.
DO $$
BEGIN
  UPDATE edge_deployments SET stage='live', forward_sessions_required=1 WHERE id=999901;
  RAISE NOTICE 'A1 combined-lower  : *** SUCCEEDED *** live, bar rewritten 20 -> 1';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'A1 combined-lower  : refused';
END $$;
ROLLBACK TO clean;

-- A2: promote AND null the requirement.
DO $$
BEGIN
  UPDATE edge_deployments SET stage='live', forward_sessions_required=NULL WHERE id=999901;
  RAISE NOTICE 'A2 null-requirement: *** SUCCEEDED *** live with no requirement';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'A2 null-requirement: refused';
END $$;
ROLLBACK TO clean;

-- A3: promote on short evidence, requirement untouched (018 already caught this).
DO $$
BEGIN
  UPDATE edge_deployments SET stage='live' WHERE id=999901;
  RAISE NOTICE 'A3 short-evidence  : *** SUCCEEDED *** live with 0 of 20';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'A3 short-evidence  : refused';
END $$;
ROLLBACK TO clean;

-- A4: lower the bar first, promote second (two statements).
DO $$
BEGIN
  UPDATE edge_deployments SET forward_sessions_required=1 WHERE id=999901;
  UPDATE edge_deployments SET stage='live' WHERE id=999901;
  RAISE NOTICE 'A4 two-step-lower  : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'A4 two-step-lower  : refused';
END $$;
ROLLBACK TO clean;

-- C1 control: a LEGITIMATE promotion must still work. Since 029 the
-- legitimate path records the 20 sessions in the forward ledger (writing the
-- counter directly is the forgery 029 refuses). The ledger's own admission
-- rules (dates, lateness) are 029's suite; here they are lifted for the
-- fixture, which was promoted moments ago.
DO $$
BEGIN
  ALTER TABLE edge_forward_sessions DISABLE TRIGGER trg_edge_forward_sessions_admit;
  INSERT INTO edge_forward_sessions (deployment_id, session_date, symbol, traded, trade,
                                     session_return, data_ref, runner, code_version)
  SELECT 999901, current_date - g, 'GC', FALSE, NULL, 0, '[{"path": "x", "sha256": "0"}]', 'test', 'test'
    FROM generate_series(1, 20) g;
  ALTER TABLE edge_forward_sessions ENABLE TRIGGER trg_edge_forward_sessions_admit;
  UPDATE edge_deployments SET stage='live' WHERE id=999901;
  RAISE NOTICE 'C1 legit promote   : accepted (correct)';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'C1 legit promote   : *** WRONGLY REFUSED *** %', SQLERRM;
END $$;
ROLLBACK TO clean;

-- C2 control: retirement must stay cheap.
DO $$
BEGIN
  UPDATE edge_deployments SET stage='retired', retired_reason='test' WHERE id=999901;
  RAISE NOTICE 'C2 retire          : accepted (correct)';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'C2 retire          : *** WRONGLY REFUSED *** %', SQLERRM;
END $$;
ROLLBACK TO clean;

-- C3 control: the prop-account doctrine rule still fires.
DO $$
BEGIN
  UPDATE accounts SET account_class='prop' WHERE account_id='crypto-spot';
  UPDATE edge_deployments SET execution='auto' WHERE id=999901;
  RAISE NOTICE 'C3 auto-on-prop    : *** ACCEPTED — DOCTRINE RULE NOT ENFORCED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'C3 auto-on-prop    : refused (correct)';
END $$;
ROLLBACK TO clean;

ROLLBACK;
