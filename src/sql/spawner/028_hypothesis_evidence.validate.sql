-- Adversarial suite for 028_hypothesis_evidence.sql. NOT a migration. Run
-- against a scratch database that has 024 and 028:
--   psql -d fks_db -f 028_hypothesis_evidence.validate.sql
-- Every attack must print "refused"; every control must print "ok".
--
-- Checked non-vacuous on 2026-11-02: with trg_edge_hypotheses_frozen dropped,
-- E1 and E3 print SUCCEEDED. E2 stays refused without it: that is the
-- table's CHECK constraint.
BEGIN;
INSERT INTO edges (edge_id, edge_type) VALUES ('evid-test', 'rule');
INSERT INTO edge_hypotheses (id, edge_id, idea, symbols, dataset, holdout_share, params, baseline, metric, costs)
VALUES (999801, 'evid-test',
        'A long-only trend band beats the hand-picked 200-day rule after costs.',
        '{BTCUSDT,ETHUSDT}', 'raw/binance/spot/spot-history 1d 2017-08-17..2026-10-31', 0.25,
        '[{"name":"lookback","min":60,"max":360,"step":20}]',
        'trend-200d-5pct', 'sharpe after fees', '{"taker_bps":80,"slippage_bps":5}');
SAVEPOINT clean;

-- C1: an existing (or undeclared) hypothesis is on the trades path.
DO $$ BEGIN
  IF (SELECT evidence FROM edge_hypotheses WHERE id = 999801) = 'trades'
  THEN RAISE NOTICE 'C1 default trades      : ok';
  ELSE RAISE NOTICE 'C1 default trades      : *** WRONG ***'; END IF;
END $$;

-- E1: switch to the low-frequency path after seeing too few trades.
DO $$ BEGIN
  UPDATE edge_hypotheses SET evidence = 'low-frequency' WHERE id = 999801;
  RAISE NOTICE 'E1 switch path later  : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'E1 switch path later  : refused'; END $$;
ROLLBACK TO clean;

-- E2: an evidence path nobody defined.
DO $$ BEGIN
  INSERT INTO edge_hypotheses (edge_id, idea, symbols, dataset, holdout_share, params, baseline, metric, costs, evidence)
  VALUES ('evid-test', 'A long-only trend band beats the hand-picked 200-day rule.', '{BTCUSDT}', 'x', 0.25,
          '[{"name":"lookback","min":60,"max":360,"step":20}]', 'buy-and-hold', 'sharpe after fees', '{}', 'vibes');
  RAISE NOTICE 'E2 unknown path       : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'E2 unknown path       : refused'; END $$;
ROLLBACK TO clean;

-- C2: declaring low-frequency AT registration is allowed.
DO $$ BEGIN
  INSERT INTO edge_hypotheses (edge_id, idea, symbols, dataset, holdout_share, params, baseline, metric, costs, evidence)
  VALUES ('evid-test', 'A long-only trend band beats the hand-picked 200-day rule.', '{BTCUSDT}', 'x', 0.25,
          '[{"name":"lookback","min":60,"max":360,"step":20}]', 'buy-and-hold', 'sharpe after fees', '{}', 'low-frequency');
  RAISE NOTICE 'C2 declare at register: ok';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'C2 declare at register: *** REFUSED ***'; END $$;
ROLLBACK TO clean;

-- E3: the 024 freeze still holds for the old columns (swap the baseline).
DO $$ BEGIN
  UPDATE edge_hypotheses SET baseline = 'buy-and-hold' WHERE id = 999801;
  RAISE NOTICE 'E3 024 freeze intact  : *** SUCCEEDED ***';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'E3 024 freeze intact  : refused'; END $$;
ROLLBACK TO clean;

ROLLBACK;
