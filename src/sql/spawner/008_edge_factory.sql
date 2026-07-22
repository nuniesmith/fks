-- =============================================================================
-- 008-edge_factory.sql — Edge factory: edge registry + backtest-run ledger
-- =============================================================================
-- Creates the edges and backtest_runs tables in fks_db (see 001_init.sql for
-- why the database keeps the fks_db name). Owned by the fks_bot_spawner
-- service (fks-spawner crates/spawner/), which exposes:
--   GET    /edges                     — list the registry (active first)
--   POST   /edges                     — UPSERT one edge by edge_id
--   DELETE /edges/{id}                — soft-delete (active = FALSE)
--   GET    /edges/{id}/backtests      — recent backtest runs w/ results
--   POST   /edges/{id}/backtest       — record a run + spawn its container
--
-- WHY (the edge factory — fks-state docs/ARCHITECTURE.md):
--   the platform runs a PORTFOLIO of edges — janus's adaptive edge plus
--   hand-found operator rule-edges (orb, funding-reversion, …) — and every
--   edge faces the SAME honest validation bar: backtest → paper in its own
--   spawner container → validate → promote → demote on decay. The `edges`
--   registry is the portfolio's source of truth (pattern-matches the
--   `accounts` registry, 007); `backtest_runs` is the factory's run ledger:
--   one row per invoked backtest, written by TWO parties — the spawner
--   INSERTs the row (status 'running') when it spawns the one-shot
--   fks-bot-* backtest container, and the CONTAINER ITSELF (handed its row
--   id + this DB's URL via BACKTEST_RUN_ID / BACKTEST_DB_URL env) UPDATEs
--   it with results + status on completion. Rows whose container died
--   without reporting are swept to 'failed' by the spawner (2h staleness
--   sweep piggybacked on the net-worth sampler tick).
--
-- ID CHOICE: `edges` is a small registry keyed by its natural id
--   (edge_id TEXT), like `accounts`. `backtest_runs` is an append-mostly run
--   series, so it uses a monotonic BIGINT identity PK like `transfers` — and
--   the id doubles as the run handle passed to the backtest container.
--
-- SEEDING: nothing is seeded — the operator registers edges via POST /edges
--   (doctrine seeds: janus-adaptive on all assets, orb on GC/NQ/ES,
--   funding-reversion on KuCoin perps).
--
-- SECURITY: `edges` holds NO credentials and no executable config beyond the
--   backtest image NAME — the spawner's fks-bot- image-prefix guard, network
--   pinning and cap-drop still apply to every backtest container it spawns.
--
-- Prerequisites:
--   • 001_init.sql     — creates the database.
--   • 002_spawner.sql  — defines the shared set_updated_at() trigger function,
--                        reused here. (Init scripts run in lexicographic order,
--                        so 25-spawner.sql lands before 30-edge-factory.sql.)
--
-- Idempotent — safe to re-run (CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT
-- EXISTS, DROP TRIGGER IF EXISTS).
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker exec -i fks_postgres sh -c \
--     'psql -U "$POSTGRES_USER" -d fks_db' < src/sql/spawner/008_edge_factory.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv fks_db   RUBY_DB

\connect :fks_db

-- =============================================================================
-- edges — the edge registry: the edge portfolio's source of truth
-- =============================================================================
-- One row per portfolio edge. `edge_type` splits the two doctrine kinds:
--   'adaptive' — janus's learning core (asset-agnostic, never "finished")
--   'rule'     — a hand-found operator rule (asset-scoped: ORB, funding-
--                reversion, …)
-- `status` is the factory lifecycle: research → paper → live → retired
-- (demotion on decay moves a live edge back down — decay detection is as
-- important as validation).
-- =============================================================================

CREATE TABLE IF NOT EXISTS edges (
    -- Natural key: the logical edge identity ("janus-adaptive", "orb",
    -- "funding-reversion", …). Also lands in per-edge attribution (ledger
    -- rows carry edge_id) and in the backtest container name
    -- (bt-{edge_id}-{run_id}), so it must stay identifier-shaped.
    edge_id           TEXT        PRIMARY KEY,

    -- Human-friendly label for the WebUI ("Opening Range Breakout", …).
    display_name      TEXT,

    -- 'adaptive' (janus's learning core) | 'rule' (operator rule-edge).
    edge_type         TEXT        NOT NULL
                                  CHECK (edge_type IN ('adaptive', 'rule')),

    -- JSON list of symbols the edge applies to (e.g. ["GC","NQ","ES"] or
    -- ["ETHUSDTM"]). EMPTY list = all assets (the adaptive edge's scope).
    asset_scope       JSONB       NOT NULL DEFAULT '[]',

    -- Factory lifecycle stage: research → paper → live → retired. Every edge
    -- climbs (and can fall back down) through the SAME honest validation bar.
    status            TEXT        NOT NULL DEFAULT 'research'
                                  CHECK (status IN ('research', 'paper',
                                                    'live', 'retired')),

    -- The fks-bot-* Docker image that runs this edge's backtest as a one-shot
    -- container (POST /edges/{id}/backtest). NULL = the edge has no
    -- containerized backtest yet, so a backtest request is a 400.
    backtest_image    TEXT,

    -- The edge's honest-stats validation evidence (fee-inclusive,
    -- multi-regime, de-overlapped significance, …). Free-form JSON the
    -- operator / validation tooling maintains; later phases gate promotion
    -- on it.
    validation_record JSONB       NOT NULL DEFAULT '{}',

    -- Free-form operator annotation ("ETH-only reversion, see PROBE-B", …).
    notes             TEXT,

    -- Soft-delete flag: DELETE /edges/{id} flips this to FALSE; the edge's
    -- backtest_runs history is never dropped.
    active            BOOLEAN     NOT NULL DEFAULT TRUE,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  edges                   IS 'Edge registry — source of truth for the edge portfolio (janus-adaptive + operator rule-edges). Every edge faces the same validation bar.';
COMMENT ON COLUMN edges.edge_id           IS 'Logical edge identity (janus-adaptive, orb, funding-reversion, …); joins backtest_runs and per-edge PnL attribution';
COMMENT ON COLUMN edges.edge_type         IS 'adaptive (janus learning core) | rule (hand-found operator rule)';
COMMENT ON COLUMN edges.asset_scope       IS 'JSON list of symbols the edge applies to; empty list = all assets';
COMMENT ON COLUMN edges.status            IS 'Factory lifecycle: research | paper | live | retired (demote on decay)';
COMMENT ON COLUMN edges.backtest_image    IS 'fks-bot-* image that runs this edge''s backtest container; NULL = not yet containerized';
COMMENT ON COLUMN edges.validation_record IS 'Honest-stats validation evidence JSON (fee-inclusive, multi-regime, de-overlapped)';
COMMENT ON COLUMN edges.notes             IS 'Free-form operator annotation';
COMMENT ON COLUMN edges.active            IS 'Soft-delete flag — FALSE hides the edge without dropping its run history';

-- Stamp updated_at on every change. Reuses set_updated_at() from 002_spawner.sql.
DROP TRIGGER IF EXISTS trg_edges_updated_at ON edges;
CREATE TRIGGER trg_edges_updated_at
    BEFORE UPDATE ON edges
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- backtest_runs — the factory's run ledger: one row per invoked backtest
-- =============================================================================
-- WRITE PROTOCOL (two writers, one row):
--   1. The spawner INSERTs the row (status 'running', params from the
--      request) BEFORE spawning the container, then passes the row id in as
--      BACKTEST_RUN_ID (+ BACKTEST_EDGE_ID / BACKTEST_PARAMS /
--      BACKTEST_DB_URL) and stores the resulting container id.
--   2. The one-shot backtest container runs the harness and UPDATEs its own
--      row: status 'completed' + results (the harness's own summary,
--      honestly labeled) + finished_at — or status 'failed' + results
--      {error} on a harness error — then exits.
--   3. A container that dies without reporting leaves the row 'running';
--      the spawner's staleness sweep (finished_at IS NULL AND started_at <
--      now() - interval '2 hours', piggybacked on the net-worth sampler
--      tick) marks it 'failed'.
-- =============================================================================

CREATE TABLE IF NOT EXISTS backtest_runs (
    -- Monotonic surrogate key; doubles as the run handle the container gets
    -- (BACKTEST_RUN_ID) and the bot_id suffix (bt-{edge_id}-{id}).
    id           BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Which edge the run belongs to. Deliberately NOT a FK — run history must
    -- never lose rows to registry edits (the transfers/accounts precedent).
    edge_id      TEXT        NOT NULL,

    -- Short Docker container id of the spawned backtest container (the
    -- spawner records it after the spawn returns). NULL if the spawn failed
    -- before a container existed.
    container_id TEXT,

    -- Run lifecycle: 'running' (spawned, awaiting the container's report) |
    -- 'completed' (container wrote results) | 'failed' (container reported
    -- an error, or the staleness sweep gave up on it).
    status       TEXT        NOT NULL DEFAULT 'running'
                             CHECK (status IN ('running', 'completed',
                                               'failed')),

    -- The request's parameter overrides, passed to the container verbatim as
    -- BACKTEST_PARAMS (a JSON object; {} = the harness's defaults).
    params       JSONB       NOT NULL DEFAULT '{}',

    -- The harness's own result summary, written by the backtest container on
    -- completion ({error: …} on failure). NULL until the run reports.
    results      JSONB,

    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- When the run reported (or was swept as stale). NULL while running.
    finished_at  TIMESTAMPTZ
);

COMMENT ON TABLE  backtest_runs              IS 'Edge-factory backtest run ledger: spawner inserts (running), the one-shot backtest container updates its own row with results, stale rows swept to failed.';
COMMENT ON COLUMN backtest_runs.edge_id      IS 'edges registry id the run belongs to; not a FK (history survives registry edits)';
COMMENT ON COLUMN backtest_runs.container_id IS 'Short Docker id of the spawned backtest container';
COMMENT ON COLUMN backtest_runs.status       IS 'running | completed | failed';
COMMENT ON COLUMN backtest_runs.params       IS 'Request parameter overrides handed to the container as BACKTEST_PARAMS';
COMMENT ON COLUMN backtest_runs.results      IS 'Harness''s own result summary JSON (container-written; {error} on failure; NULL until the run reports)';
COMMENT ON COLUMN backtest_runs.finished_at  IS 'When the run reported or was swept stale; NULL while running';

-- Primary access pattern: one edge's runs, newest first
-- (GET /edges/{id}/backtests).
CREATE INDEX IF NOT EXISTS idx_backtest_runs_edge_started
    ON backtest_runs (edge_id, started_at DESC);

-- =============================================================================
-- Privileges
-- =============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;
