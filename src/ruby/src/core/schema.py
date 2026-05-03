"""
Schema definitions and database initialisation.

All DDL strings (CREATE TABLE, migrations, indexes) plus the
``_init_audit_tables()`` and ``init_db()`` entry points live here.
"""

import contextlib

from core.db_layer import (
    _USE_POSTGRES,
    _get_conn,
)
from core.logging_config import get_logger

logger = get_logger("models")

# ---------------------------------------------------------------------------
# Daily journal schema — simple end-of-day P&L entries
# ---------------------------------------------------------------------------
_SCHEMA_DAILY_JOURNAL_SQLITE = """
CREATE TABLE IF NOT EXISTS daily_journal (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date      TEXT    NOT NULL UNIQUE,
    account_size    INTEGER NOT NULL,
    gross_pnl       REAL    NOT NULL DEFAULT 0.0,
    net_pnl         REAL    NOT NULL DEFAULT 0.0,
    commissions     REAL    NOT NULL DEFAULT 0.0,
    num_contracts   INTEGER DEFAULT 0,
    instruments     TEXT    DEFAULT '',
    notes           TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL
);
"""

_SCHEMA_DAILY_JOURNAL_PG = """
CREATE TABLE IF NOT EXISTS daily_journal (
    id              SERIAL PRIMARY KEY,
    trade_date      TEXT    NOT NULL UNIQUE,
    account_size    INTEGER NOT NULL,
    gross_pnl       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    net_pnl         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    commissions     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    num_contracts   INTEGER DEFAULT 0,
    instruments     TEXT    DEFAULT '',
    notes           TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Audit event tables — persistent storage for risk blocks & ORB detections
# ---------------------------------------------------------------------------

_SCHEMA_RISK_EVENTS_SQLITE = """
CREATE TABLE IF NOT EXISTS risk_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    event_type      TEXT    NOT NULL,
    symbol          TEXT    NOT NULL DEFAULT '',
    side            TEXT    NOT NULL DEFAULT '',
    reason          TEXT    NOT NULL DEFAULT '',
    daily_pnl       REAL    NOT NULL DEFAULT 0.0,
    open_trades     INTEGER NOT NULL DEFAULT 0,
    account_size    INTEGER NOT NULL DEFAULT 0,
    risk_pct        REAL    NOT NULL DEFAULT 0.0,
    session         TEXT    NOT NULL DEFAULT '',
    metadata_json   TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_re_timestamp ON risk_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_re_event_type ON risk_events (event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_re_symbol ON risk_events (symbol, timestamp);
"""

_SCHEMA_RISK_EVENTS_PG = """
CREATE TABLE IF NOT EXISTS risk_events (
    id              SERIAL PRIMARY KEY,
    timestamp       TEXT    NOT NULL,
    event_type      TEXT    NOT NULL,
    symbol          TEXT    NOT NULL DEFAULT '',
    side            TEXT    NOT NULL DEFAULT '',
    reason          TEXT    NOT NULL DEFAULT '',
    daily_pnl       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    open_trades     INTEGER NOT NULL DEFAULT 0,
    account_size    INTEGER NOT NULL DEFAULT 0,
    risk_pct        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    session         TEXT    NOT NULL DEFAULT '',
    metadata_json   TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_re_timestamp ON risk_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_re_event_type ON risk_events (event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_re_symbol ON risk_events (symbol, timestamp);
"""

_SCHEMA_ORB_EVENTS_SQLITE = """
CREATE TABLE IF NOT EXISTS orb_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    symbol          TEXT    NOT NULL,
    or_high         REAL    NOT NULL DEFAULT 0.0,
    or_low          REAL    NOT NULL DEFAULT 0.0,
    or_range        REAL    NOT NULL DEFAULT 0.0,
    atr_value       REAL    NOT NULL DEFAULT 0.0,
    breakout_detected INTEGER NOT NULL DEFAULT 0,
    direction       TEXT    NOT NULL DEFAULT '',
    trigger_price   REAL    NOT NULL DEFAULT 0.0,
    long_trigger    REAL    NOT NULL DEFAULT 0.0,
    short_trigger   REAL    NOT NULL DEFAULT 0.0,
    bar_count       INTEGER NOT NULL DEFAULT 0,
    session         TEXT    NOT NULL DEFAULT '',
    metadata_json   TEXT    NOT NULL DEFAULT '{}',
    breakout_type   TEXT    NOT NULL DEFAULT 'ORB',
    mtf_score       REAL,
    macd_slope      REAL,
    divergence      TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_orb_timestamp ON orb_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_orb_symbol ON orb_events (symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_orb_breakout_type ON orb_events (breakout_type, timestamp);
"""

# ---------------------------------------------------------------------------
# Migration: add new columns to existing orb_events tables
# ---------------------------------------------------------------------------
_MIGRATE_ORB_EVENTS_ADD_COLS_SQLITE = """
ALTER TABLE orb_events ADD COLUMN breakout_type TEXT NOT NULL DEFAULT 'ORB';
ALTER TABLE orb_events ADD COLUMN mtf_score REAL;
ALTER TABLE orb_events ADD COLUMN macd_slope REAL;
ALTER TABLE orb_events ADD COLUMN divergence TEXT NOT NULL DEFAULT '';
"""

_MIGRATE_ORB_EVENTS_ADD_COLS_PG = [
    "ALTER TABLE orb_events ADD COLUMN IF NOT EXISTS breakout_type TEXT NOT NULL DEFAULT 'ORB'",
    "ALTER TABLE orb_events ADD COLUMN IF NOT EXISTS mtf_score DOUBLE PRECISION",
    "ALTER TABLE orb_events ADD COLUMN IF NOT EXISTS macd_slope DOUBLE PRECISION",
    "ALTER TABLE orb_events ADD COLUMN IF NOT EXISTS divergence TEXT NOT NULL DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS idx_orb_breakout_type ON orb_events (breakout_type, timestamp)",
]

_SCHEMA_ORB_EVENTS_PG = """
CREATE TABLE IF NOT EXISTS orb_events (
    id              SERIAL PRIMARY KEY,
    timestamp       TEXT    NOT NULL,
    symbol          TEXT    NOT NULL,
    or_high         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    or_low          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    or_range        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    atr_value       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    breakout_detected INTEGER NOT NULL DEFAULT 0,
    direction       TEXT    NOT NULL DEFAULT '',
    trigger_price   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    long_trigger    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    short_trigger   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    bar_count       INTEGER NOT NULL DEFAULT 0,
    session         TEXT    NOT NULL DEFAULT '',
    metadata_json   TEXT    NOT NULL DEFAULT '{}',
    breakout_type   TEXT    NOT NULL DEFAULT 'ORB',
    mtf_score       DOUBLE PRECISION,
    macd_slope      DOUBLE PRECISION,
    divergence      TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_orb_timestamp ON orb_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_orb_symbol ON orb_events (symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_orb_breakout_type ON orb_events (breakout_type, timestamp);
"""


# ---------------------------------------------------------------------------
# Trades schema
# ---------------------------------------------------------------------------

_SCHEMA_V2_SQLITE = """
CREATE TABLE IF NOT EXISTS trades_v2 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL,
    account_size    INTEGER NOT NULL,
    asset           TEXT    NOT NULL,
    direction       TEXT    NOT NULL,
    entry           REAL    NOT NULL,
    sl              REAL,
    tp              REAL,
    contracts       INTEGER NOT NULL DEFAULT 1,
    status          TEXT    NOT NULL DEFAULT 'OPEN',
    close_price     REAL,
    close_time      TEXT,
    pnl             REAL,
    rr              REAL,
    notes           TEXT    DEFAULT '',
    strategy        TEXT    DEFAULT '',
    grade           TEXT    DEFAULT '',
    source          TEXT    DEFAULT 'manual'
);
"""

_SCHEMA_V2_PG = """
CREATE TABLE IF NOT EXISTS trades_v2 (
    id              SERIAL PRIMARY KEY,
    created_at      TEXT    NOT NULL,
    account_size    INTEGER NOT NULL,
    asset           TEXT    NOT NULL,
    direction       TEXT    NOT NULL,
    entry           DOUBLE PRECISION NOT NULL,
    sl              DOUBLE PRECISION,
    tp              DOUBLE PRECISION,
    contracts       INTEGER NOT NULL DEFAULT 1,
    status          TEXT    NOT NULL DEFAULT 'OPEN',
    close_price     DOUBLE PRECISION,
    close_time      TEXT,
    pnl             DOUBLE PRECISION,
    rr              DOUBLE PRECISION,
    notes           TEXT    DEFAULT '',
    strategy        TEXT    DEFAULT '',
    grade           TEXT    DEFAULT '',
    source          TEXT    DEFAULT 'manual'
);
"""

# ---------------------------------------------------------------------------
# Migration: add grade + source columns to existing trades_v2 tables
# ---------------------------------------------------------------------------

# Postgres supports IF NOT EXISTS on ALTER TABLE ADD COLUMN (PG 9.6+)
_MIGRATE_ADD_GRADE_PG = [
    "ALTER TABLE trades_v2 ADD COLUMN IF NOT EXISTS grade TEXT DEFAULT '';",
    "ALTER TABLE trades_v2 ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'manual';",
]

# SQLite does NOT support IF NOT EXISTS on ALTER TABLE — use try/except in init_db
_MIGRATE_ADD_GRADE_SQLITE = [
    "ALTER TABLE trades_v2 ADD COLUMN grade TEXT DEFAULT '';",
    "ALTER TABLE trades_v2 ADD COLUMN source TEXT DEFAULT 'manual';",
]

_MIGRATE_V1 = """
INSERT INTO trades_v2
    (id, created_at, account_size, asset, direction, entry, sl, tp,
     contracts, status, close_price, close_time, pnl, rr, notes, strategy)
SELECT
    id,
    date,
    150000,
    asset,
    direction,
    entry,
    sl,
    tp,
    contracts,
    CASE WHEN exit_price IS NOT NULL AND exit_price != 0 THEN 'CLOSED' ELSE 'OPEN' END,
    CASE WHEN exit_price != 0 THEN exit_price ELSE NULL END,
    CASE WHEN exit_price IS NOT NULL AND exit_price != 0 THEN date ELSE NULL END,
    pnl,
    rr,
    COALESCE(notes, ''),
    COALESCE(strategy, '')
FROM trades;
"""


# ---------------------------------------------------------------------------
# Reddit posts schema
# ---------------------------------------------------------------------------

_SCHEMA_REDDIT_POSTS_SQLITE = """
CREATE TABLE IF NOT EXISTS reddit_posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id         TEXT        NOT NULL UNIQUE,
    subreddit       TEXT        NOT NULL,
    author          TEXT,
    title           TEXT,
    body            TEXT,
    url             TEXT,
    score           INTEGER     DEFAULT 0,
    num_comments    INTEGER     DEFAULT 0,
    is_comment      INTEGER     DEFAULT 0,
    asset           TEXT        NOT NULL,
    sentiment_score REAL,
    sentiment_label TEXT,
    upvote_ratio    REAL,
    created_utc     TEXT        NOT NULL,
    fetched_at      TEXT        NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_asset      ON reddit_posts (asset);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_created    ON reddit_posts (created_utc DESC);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_asset_time ON reddit_posts (asset, created_utc DESC);
"""

_SCHEMA_REDDIT_POSTS_PG = """
CREATE TABLE IF NOT EXISTS reddit_posts (
    id              SERIAL PRIMARY KEY,
    post_id         TEXT        NOT NULL UNIQUE,
    subreddit       TEXT        NOT NULL,
    author          TEXT,
    title           TEXT,
    body            TEXT,
    url             TEXT,
    score           INTEGER     DEFAULT 0,
    num_comments    INTEGER     DEFAULT 0,
    is_comment      BOOLEAN     DEFAULT FALSE,
    asset           TEXT        NOT NULL,
    sentiment_score DOUBLE PRECISION,
    sentiment_label TEXT,
    upvote_ratio    DOUBLE PRECISION,
    created_utc     TIMESTAMPTZ NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_asset      ON reddit_posts (asset);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_created    ON reddit_posts (created_utc DESC);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_asset_time ON reddit_posts (asset, created_utc DESC);
"""


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------


def _init_audit_tables(conn, use_postgres: bool) -> None:
    """Create audit event tables (risk_events, orb_events) idempotently.

    Called from init_db() after the core tables are created.
    Also runs non-destructive column migrations so existing deployments
    pick up the new breakout_type / mtf_score / macd_slope / divergence
    columns without requiring a manual ALTER TABLE.
    """
    if use_postgres:
        for schema in (_SCHEMA_RISK_EVENTS_PG, _SCHEMA_ORB_EVENTS_PG):
            for stmt in schema.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        conn.execute(stmt)
                    except Exception as exc:
                        # Index may already exist — not fatal
                        logger.debug("Audit table DDL (pg, non-fatal): %s", exc)
        conn.commit()
        # Run column-level migrations (ADD COLUMN IF NOT EXISTS — idempotent)
        for stmt in _MIGRATE_ORB_EVENTS_ADD_COLS_PG:
            try:
                conn.execute(stmt)
            except Exception as exc:
                logger.debug("ORB events column migration (pg, non-fatal): %s", exc)
        with contextlib.suppress(Exception):
            conn.commit()
    else:
        conn.executescript(_SCHEMA_RISK_EVENTS_SQLITE)
        conn.executescript(_SCHEMA_ORB_EVENTS_SQLITE)
        # SQLite: ALTER TABLE ADD COLUMN is idempotent only if we catch the error
        for stmt in _MIGRATE_ORB_EVENTS_ADD_COLS_SQLITE.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except Exception as exc:
                    # "duplicate column name" is expected on existing DBs — ignore
                    if "duplicate column" not in str(exc).lower():
                        logger.debug("ORB events column migration (sqlite, non-fatal): %s", exc)
        with contextlib.suppress(Exception):
            conn.commit()

    logger.info("Audit tables initialised (risk_events, orb_events)")


def init_db() -> None:
    """Initialise the trades_v2, daily_journal, and audit event tables.

    For SQLite: migrates from v1 schema if needed.
    For Postgres: creates tables idempotently (CREATE TABLE IF NOT EXISTS).
    """
    conn = _get_conn()

    if _USE_POSTGRES:
        try:
            conn.executescript(_SCHEMA_V2_PG)
            conn.executescript(_SCHEMA_DAILY_JOURNAL_PG)
            conn.commit()
            logger.info("Postgres tables initialised (trades_v2, daily_journal)")
        except Exception as exc:
            logger.error("Postgres init_db failed: %s", exc)
            conn.rollback()

        # Run grade/source column migrations (ADD COLUMN IF NOT EXISTS — idempotent on PG)
        for stmt in _MIGRATE_ADD_GRADE_PG:
            try:
                conn.execute(stmt)
            except Exception as exc:
                logger.debug("grade/source column migration (pg, non-fatal): %s", exc)
        with contextlib.suppress(Exception):
            conn.commit()

        # Create audit tables (separate try so core tables aren't rolled back)
        try:
            _init_audit_tables(conn, use_postgres=True)
        except Exception as exc:
            logger.error("Audit table init failed (non-fatal): %s", exc)
            with contextlib.suppress(Exception):
                conn.rollback()

        # Create reddit_posts table (separate try — non-fatal if praw not used)
        try:
            conn.executescript(_SCHEMA_REDDIT_POSTS_PG)
            conn.commit()
            logger.info("Postgres tables initialised (reddit_posts)")
        except Exception as exc:
            logger.warning("reddit_posts table init failed (non-fatal): %s", exc)
            with contextlib.suppress(Exception):
                conn.rollback()

        conn.close()
        return

    # --- SQLite path ---
    # Check if new table already exists
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades_v2'")
    if cur.fetchone() is not None:
        # trades_v2 exists — ensure daily_journal + audit tables exist, then run column migrations
        conn.executescript(_SCHEMA_DAILY_JOURNAL_SQLITE)
        _init_audit_tables(conn, use_postgres=False)
        # Run grade/source column migrations (SQLite doesn't support IF NOT EXISTS — use try/except)
        for stmt in _MIGRATE_ADD_GRADE_SQLITE:
            try:
                conn.execute(stmt)
            except Exception as exc:
                # "duplicate column name" is expected on already-migrated DBs — ignore
                if "duplicate column" not in str(exc).lower():
                    logger.debug("grade/source column migration (sqlite, non-fatal): %s", exc)
        with contextlib.suppress(Exception):
            conn.commit()
        conn.close()
        return

    # Create v2 schema
    conn.executescript(_SCHEMA_V2_SQLITE)

    # Create daily journal schema
    conn.executescript(_SCHEMA_DAILY_JOURNAL_SQLITE)

    # Create audit tables
    _init_audit_tables(conn, use_postgres=False)

    # Create reddit_posts table
    try:
        conn.executescript(_SCHEMA_REDDIT_POSTS_SQLITE)
    except Exception as exc:
        logger.warning("reddit_posts table init failed (non-fatal): %s", exc)

    # Migrate from v1 if it exists
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
    if cur.fetchone() is not None:
        try:
            conn.executescript(_MIGRATE_V1)
            conn.execute("ALTER TABLE trades RENAME TO trades_v1_backup")
            conn.commit()
        except Exception:
            conn.rollback()

    conn.close()


# ---------------------------------------------------------------------------
# __all__ — public API for wildcard imports
# ---------------------------------------------------------------------------
__all__ = [
    # Schema DDL strings (exposed for tests / tooling that inspect them)
    "_SCHEMA_DAILY_JOURNAL_SQLITE",
    "_SCHEMA_DAILY_JOURNAL_PG",
    "_SCHEMA_RISK_EVENTS_SQLITE",
    "_SCHEMA_RISK_EVENTS_PG",
    "_SCHEMA_ORB_EVENTS_SQLITE",
    "_SCHEMA_ORB_EVENTS_PG",
    "_MIGRATE_ORB_EVENTS_ADD_COLS_SQLITE",
    "_MIGRATE_ORB_EVENTS_ADD_COLS_PG",
    "_SCHEMA_V2_SQLITE",
    "_SCHEMA_V2_PG",
    "_MIGRATE_ADD_GRADE_PG",
    "_MIGRATE_ADD_GRADE_SQLITE",
    "_MIGRATE_V1",
    "_SCHEMA_REDDIT_POSTS_SQLITE",
    "_SCHEMA_REDDIT_POSTS_PG",
    # Functions
    "_init_audit_tables",
    "init_db",
]
