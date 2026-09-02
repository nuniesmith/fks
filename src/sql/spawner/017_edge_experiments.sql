-- ============================================================================
-- 017_edge_experiments.sql — the experiment registry
-- ============================================================================
-- WHY. Every Optuna study today lives in its own SQLite file with its results
-- in `user_attrs`. That makes one study readable and the SET of studies
-- invisible: there is no way to ask what has been tried, what survived, what
-- died, or — the question that actually matters — HOW MANY THINGS HAVE BEEN
-- TESTED IN TOTAL.
--
-- That last number is not bookkeeping. `docs/edge_research.md` §4 in the
-- futures repo already names this as the prerequisite it is waiting on:
--
--     "Track every tried rule and asset. Add a multiple-testing correction
--      such as the Deflated Sharpe Ratio once the experiment registry and
--      per-trial return series are available."
--
-- Without N, every additional experiment silently inflates the best result and
-- nothing counts the inflation. A search that runs 800 trials and reports its
-- winner's Sharpe is reporting the maximum of 800 draws, not an estimate of an
-- edge — and that is not a hypothetical here: the 2026-07 GC study did exactly
-- that and its winner took ZERO trades on the holdout, with an overfit gap of
-- 668. More trials made it strictly worse. This table is how that becomes
-- visible before the next one.
--
-- ONE ROW PER EXPERIMENT, NOT PER TRIAL. The trials stay in Optuna where they
-- belong; this is the layer above, and it is deliberately small enough that a
-- human can read the whole thing.
--
-- THE HYPOTHESIS COLUMN IS THE POINT. It is nullable only because history
-- cannot be back-filled honestly. Going forward a row whose `hypothesis` was
-- written after `finished_at` is not evidence of anything, so the registry
-- records `registered_at` separately and the two dates are meant to be
-- compared. A hypothesis written after seeing the answer is not a hypothesis.
-- ============================================================================

CREATE TABLE IF NOT EXISTS edge_experiments (
    id                     BIGSERIAL PRIMARY KEY,

    -- ── Identity ────────────────────────────────────────────────────────────
    -- The Optuna study this summarises. UNIQUE so re-ingesting the same study
    -- updates rather than duplicating — an experiment counted twice corrupts
    -- exactly the N this table exists to provide.
    study_name             TEXT        NOT NULL UNIQUE,
    -- The optimizer's own identity hash over dataset + folds + risk policy +
    -- search space. Two rows sharing it were searching the same problem; two
    -- rows differing on it are NOT comparable, whatever their scores say.
    config_fingerprint     TEXT        NOT NULL,
    symbol                 TEXT        NOT NULL,
    bar_minutes            INTEGER     NOT NULL,

    -- ── The hypothesis, ideally written FIRST ───────────────────────────────
    hypothesis             TEXT,
    registered_at          TIMESTAMPTZ,

    -- ── What was searched ───────────────────────────────────────────────────
    -- The dimensions actually tuned. A 4-name array and a 71-name array are
    -- different experiments even at identical trial counts, and the difference
    -- is the whole argument about overfitting.
    tuned_params           TEXT[]      NOT NULL DEFAULT '{}',
    n_trials               INTEGER     NOT NULL,
    train_days             INTEGER,
    test_days              INTEGER,
    folds                  INTEGER,
    holdout_folds          INTEGER,

    -- ── What came out ───────────────────────────────────────────────────────
    -- selection_score is what the search MAXIMISED and is therefore the most
    -- flattered number here. holdout_score is the only one nobody selected on.
    selection_score        DOUBLE PRECISION,
    holdout_score          DOUBLE PRECISION,
    baseline_holdout_score DOUBLE PRECISION,
    overfit_gap            DOUBLE PRECISION,
    selection_trades       INTEGER,
    holdout_trades         INTEGER,

    -- ── The verdict, verbatim ───────────────────────────────────────────────
    -- Stored as the optimizer emitted it. Re-deriving a verdict later from
    -- stored scores would let a change in the gate silently rewrite history.
    verdict                TEXT        NOT NULL,
    verdict_reasons        TEXT[]      NOT NULL DEFAULT '{}',

    -- What the OPERATOR did about it, which is not the same as what the gate
    -- said. An adopted row whose verdict was 'DO NOT PASTE' is exactly the kind
    -- of thing this registry should make impossible to forget.
    outcome                TEXT        NOT NULL DEFAULT 'pending',

    finished_at            TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT edge_experiments_verdict_known
        CHECK (verdict IN ('USABLE', 'DO NOT PASTE')),
    CONSTRAINT edge_experiments_outcome_known
        CHECK (outcome IN ('pending', 'adopted', 'rejected', 'superseded')),
    CONSTRAINT edge_experiments_trials_positive
        CHECK (n_trials > 0)
);

-- The DSR query counts trials per symbol/fingerprint family.
CREATE INDEX IF NOT EXISTS edge_experiments_family_idx
    ON edge_experiments (symbol, config_fingerprint);
CREATE INDEX IF NOT EXISTS edge_experiments_finished_idx
    ON edge_experiments (finished_at DESC);

COMMENT ON TABLE edge_experiments IS
    'One row per Optuna study. Exists so the NUMBER of things tried is knowable, '
    'which is the prerequisite for any multiple-testing correction.';
COMMENT ON COLUMN edge_experiments.hypothesis IS
    'Written BEFORE the result, ideally. Compare registered_at with finished_at.';
COMMENT ON COLUMN edge_experiments.selection_score IS
    'What the search maximised — the most flattered number in the row.';
COMMENT ON COLUMN edge_experiments.holdout_score IS
    'Scored once, on folds the search never saw. The only number not selected for.';

-- ── The view the whole table exists for ─────────────────────────────────────
-- Cumulative trial count per family. This is the N that a Deflated Sharpe Ratio
-- needs, and it is deliberately a VIEW so it can never drift from the rows.
CREATE OR REPLACE VIEW edge_search_effort AS
SELECT
    symbol,
    config_fingerprint,
    count(*)                          AS experiments,
    sum(n_trials)                     AS trials_total,
    max(holdout_score)                AS best_holdout,
    count(*) FILTER (WHERE verdict = 'USABLE')   AS usable,
    count(*) FILTER (WHERE outcome  = 'adopted') AS adopted,
    min(finished_at)                  AS first_run,
    max(finished_at)                  AS last_run
FROM edge_experiments
GROUP BY symbol, config_fingerprint;

COMMENT ON VIEW edge_search_effort IS
    'trials_total is the N for a multiple-testing correction: how many draws the '
    'best result is the maximum of. Reporting a winner without it overstates.';

GRANT SELECT, INSERT, UPDATE ON edge_experiments TO fks_webui;
GRANT USAGE, SELECT ON SEQUENCE edge_experiments_id_seq TO fks_webui;
GRANT SELECT ON edge_search_effort TO fks_webui;
