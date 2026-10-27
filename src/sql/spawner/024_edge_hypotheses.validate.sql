-- Adversarial suite for 024_edge_hypotheses.sql. NOT a migration (fks-migrate
-- and the image skip *.validate.sql). Run against a scratch database:
--   psql -d fks_db -f 024_edge_hypotheses.validate.sql
-- Every attack must print "refused"; every control must print "ok". Each case
-- starts from the same clean state (savepoints), and nothing is kept.
--
-- Checked non-vacuous on 2026-10-27: with both triggers dropped, H1-H5 and
-- H7-H9 print SUCCEEDED. H6 and H10 stay refused without them: those are the
-- table's CHECK constraints (a withdrawal needs a reason; an idea, a dataset
-- and at least one parameter are required).
BEGIN;
INSERT INTO edges (edge_id, edge_type) VALUES ('hyp-test', 'rule');
INSERT INTO edge_hypotheses (id, edge_id, idea, symbols, dataset, holdout_share, params, baseline, metric, costs)
VALUES (999901, 'hyp-test',
        'Liquidation clusters overshoot; fading the 5-minute move earns the snap-back.',
        '{BTCUSDT}', 'lake raw/binance/usdm/btc, 2026-10-27..2027-01-27', 0.25,
        '[{"name":"threshold_usd","min":1000000,"max":20000000,"step":1000000}]',
        'buy-and-hold', 'net return after fees', '{"maker_bps":40,"taker_bps":80,"slippage_bps":5}');
SAVEPOINT clean;

-- H1: edit the idea after registering it.
DO $$ BEGIN
  UPDATE edge_hypotheses SET idea = 'Something else entirely, decided after the results.' WHERE id = 999901;
  RAISE NOTICE 'H1 edit idea          : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H1 edit idea          : refused'; END $$;
ROLLBACK TO clean;

-- H2: widen the parameter ranges after seeing the results.
DO $$ BEGIN
  UPDATE edge_hypotheses SET params = '[{"name":"threshold_usd","min":0,"max":90000000,"step":1}]' WHERE id = 999901;
  RAISE NOTICE 'H2 widen ranges       : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H2 widen ranges       : refused'; END $$;
ROLLBACK TO clean;

-- H3: backdate the registration.
DO $$ BEGIN
  UPDATE edge_hypotheses SET registered_at = registered_at - interval '30 days' WHERE id = 999901;
  RAISE NOTICE 'H3 backdate           : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H3 backdate           : refused'; END $$;
ROLLBACK TO clean;

-- H4: swap the baseline for an easier one.
DO $$ BEGIN
  UPDATE edge_hypotheses SET baseline = 'zero' WHERE id = 999901;
  RAISE NOTICE 'H4 easier baseline    : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H4 easier baseline    : refused'; END $$;
ROLLBACK TO clean;

-- H5: delete it.
DO $$ BEGIN
  DELETE FROM edge_hypotheses WHERE id = 999901;
  RAISE NOTICE 'H5 delete             : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H5 delete             : refused'; END $$;
ROLLBACK TO clean;

-- H6: withdraw without a reason.
DO $$ BEGIN
  UPDATE edge_hypotheses SET status = 'withdrawn', withdrawn_at = now() WHERE id = 999901;
  RAISE NOTICE 'H6 withdraw, no reason: *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H6 withdraw, no reason: refused'; END $$;
ROLLBACK TO clean;

-- H7: un-withdraw.
DO $$ BEGIN
  UPDATE edge_hypotheses SET status = 'withdrawn', withdrawn_reason = 'superseded', withdrawn_at = now() WHERE id = 999901;
  UPDATE edge_hypotheses SET status = 'registered', withdrawn_reason = NULL, withdrawn_at = NULL WHERE id = 999901;
  RAISE NOTICE 'H7 un-withdraw        : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H7 un-withdraw        : refused'; END $$;
ROLLBACK TO clean;

-- H8: an experiment that finished before the hypothesis was registered.
DO $$ BEGIN
  INSERT INTO edge_experiments (study_name, config_fingerprint, symbol, bar_minutes, n_trials,
                                verdict, finished_at, hypothesis_id)
  VALUES ('hyp-test-early', 'fp', 'BTCUSDT', 5, 10, 'USABLE', now() - interval '1 day', 999901);
  RAISE NOTICE 'H8 search before idea : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H8 search before idea : refused'; END $$;
ROLLBACK TO clean;

-- H9: attach an old finished experiment to the hypothesis afterwards.
DO $$ BEGIN
  INSERT INTO edge_experiments (study_name, config_fingerprint, symbol, bar_minutes, n_trials,
                                verdict, finished_at)
  VALUES ('hyp-test-old', 'fp', 'BTCUSDT', 5, 10, 'USABLE', now() - interval '1 day');
  UPDATE edge_experiments SET hypothesis_id = 999901 WHERE study_name = 'hyp-test-old';
  RAISE NOTICE 'H9 attach old result  : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H9 attach old result  : refused'; END $$;
ROLLBACK TO clean;

-- H10: a hypothesis with no parameters, or one word of idea.
DO $$ BEGIN
  INSERT INTO edge_hypotheses (edge_id, idea, symbols, dataset, holdout_share, params, baseline, metric, costs)
  VALUES ('hyp-test', 'it goes up', '{BTCUSDT}', 'x', 0.25, '[]', 'buy-and-hold', 'net', '{}');
  RAISE NOTICE 'H10 empty hypothesis  : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'H10 empty hypothesis  : refused'; END $$;
ROLLBACK TO clean;

-- C1 control: withdrawing with a reason works.
DO $$ BEGIN
  UPDATE edge_hypotheses SET status = 'withdrawn', withdrawn_reason = 'the dataset had a hole', withdrawn_at = now() WHERE id = 999901;
  RAISE NOTICE 'C1 withdraw           : ok';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'C1 withdraw           : *** REFUSED ***'; END $$;
ROLLBACK TO clean;

-- C2 control: a search that starts and finishes after the registration.
DO $$ BEGIN
  INSERT INTO edge_experiments (study_name, config_fingerprint, symbol, bar_minutes, n_trials,
                                verdict, hypothesis_id)
  VALUES ('hyp-test-ok', 'fp', 'BTCUSDT', 5, 10, 'DO NOT PASTE', 999901);
  UPDATE edge_experiments SET finished_at = now() + interval '1 second' WHERE study_name = 'hyp-test-ok';
  RAISE NOTICE 'C2 search after idea  : ok';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'C2 search after idea  : *** REFUSED ***'; END $$;
ROLLBACK TO clean;

-- C3 control: experiments without a hypothesis (the 2026-07 studies) are untouched.
DO $$ BEGIN
  INSERT INTO edge_experiments (study_name, config_fingerprint, symbol, bar_minutes, n_trials,
                                verdict, finished_at)
  VALUES ('hyp-test-legacy', 'fp', 'GC', 5, 800, 'DO NOT PASTE', now() - interval '90 days');
  RAISE NOTICE 'C3 legacy experiment  : ok';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'C3 legacy experiment  : *** REFUSED ***'; END $$;
ROLLBACK TO clean;

ROLLBACK;
