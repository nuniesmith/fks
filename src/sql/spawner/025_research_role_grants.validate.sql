-- What fks_backtest can and can't do after 025. NOT a migration. Run as the
-- superuser against a scratch database that has 009 + 017 + 018 + 024 + 025:
--   psql -d fks_db -f 025_research_role_grants.validate.sql
-- Every "can" must print ok, every "can't" refused. Nothing is kept.
BEGIN;
INSERT INTO edges (edge_id, edge_type) VALUES ('grant-test', 'rule');
INSERT INTO edge_hypotheses (id, edge_id, idea, symbols, dataset, holdout_share, params, baseline, metric, costs)
VALUES (999801, 'grant-test', 'A test hypothesis, long enough to register.', '{BTCUSDT}',
        'raw/x 1d 2020-01-01..2021-01-01', 0.25, '[{"name":"lookback","min":50,"max":200,"step":50}]',
        'buy-and-hold', 'net return after fees', '{"maker_bps":40,"taker_bps":80,"slippage_bps":5}');
SET LOCAL ROLE fks_backtest;
SAVEPOINT clean;

DO $$ BEGIN PERFORM 1 FROM edge_hypotheses WHERE id = 999801; RAISE NOTICE 'can  read hypotheses      : ok';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'can  read hypotheses      : *** REFUSED ***'; END $$;
ROLLBACK TO clean;
DO $$ BEGIN PERFORM sum(trials_total) FROM edge_search_effort; RAISE NOTICE 'can  read the effort view : ok';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'can  read the effort view : *** REFUSED ***'; END $$;
ROLLBACK TO clean;
DO $$ BEGIN
  INSERT INTO edge_experiments (study_name, config_fingerprint, symbol, bar_minutes, n_trials, verdict, hypothesis_id, finished_at)
  VALUES ('grant-test-1', 'fp', 'BTCUSDT', 1440, 6, 'DO NOT PASTE', 999801, now() + interval '1 second');
  RAISE NOTICE 'can  write an experiment  : ok';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'can  write an experiment  : *** REFUSED ***'; END $$;
ROLLBACK TO clean;

DO $$ BEGIN UPDATE edge_experiments SET verdict = 'USABLE'; RAISE NOTICE 'can''t rewrite a verdict  : *** ALLOWED ***';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'can''t rewrite a verdict  : refused'; END $$;
ROLLBACK TO clean;
DO $$ BEGIN DELETE FROM edge_experiments; RAISE NOTICE 'can''t delete experiments : *** ALLOWED ***';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'can''t delete experiments : refused'; END $$;
ROLLBACK TO clean;
DO $$ BEGIN INSERT INTO edge_hypotheses (edge_id, idea, symbols, dataset, holdout_share, params, baseline, metric, costs)
  VALUES ('grant-test', 'A hypothesis written by the job itself.', '{BTCUSDT}', 'x', 0.25, '[{"name":"a"}]', 'b', 'm', '{}');
  RAISE NOTICE 'can''t register hypotheses: *** ALLOWED ***';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'can''t register hypotheses: refused'; END $$;
ROLLBACK TO clean;
DO $$ BEGIN PERFORM 1 FROM edge_deployments; RAISE NOTICE 'can''t read deployments   : *** ALLOWED ***';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'can''t read deployments   : refused'; END $$;
ROLLBACK TO clean;
DO $$ BEGIN PERFORM 1 FROM exchange_secrets; RAISE NOTICE 'can''t read secrets       : *** ALLOWED ***';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'can''t read secrets       : refused'; END $$;
ROLLBACK TO clean;
ROLLBACK;
