"""
Trade CRUD operations, query helpers, daily P&L, and risk helpers.

All trade-related database operations that were previously in
``models.py`` now live here.  Functions import their dependencies
from the sibling ``db_layer`` and ``contracts`` modules.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from core.contracts import (
    ACCOUNT_PROFILES,
    CONTRACT_MODE,
    CONTRACT_SPECS,
)
from core.db_layer import (
    _USE_POSTGRES,
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_OPEN,
    _get_conn,
    _insert_returning_id,
    _row_to_dict,
)
from core.logging_config import get_logger

_EST = ZoneInfo("America/New_York")

logger = get_logger("models")


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def create_trade(
    account_size: int,
    asset: str,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    contracts: int,
    strategy: str = "",
    notes: str = "",
) -> int:
    """Insert a new OPEN trade. Returns the new trade id."""
    conn = _get_conn()
    now = datetime.now(tz=_EST).strftime("%Y-%m-%d %H:%M:%S")

    sql = """INSERT INTO trades_v2
           (created_at, account_size, asset, direction, entry, sl, tp,
            contracts, status, strategy, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    params = (
        now,
        account_size,
        asset,
        direction,
        entry,
        sl,
        tp,
        contracts,
        STATUS_OPEN,
        strategy,
        notes,
    )

    trade_id = _insert_returning_id(conn, sql, params, "trades_v2")
    conn.commit()
    conn.close()
    return trade_id


def upsert_trade_from_fill(
    account_key: str,
    symbol: str,
    direction: str,
    entry_price: float,
    close_price: float | None,
    contracts: int,
    pnl: float | None,
    fill_time: str,
    strategy: str = "rithmic_sync",
    notes: str = "",
    source: str = "rithmic_sync",
) -> int:
    """Insert or update a trade record from a Rithmic fill.

    Uses fill_time + symbol + account_key as a natural dedup key:
      - created_at matches fill_time (date prefix)
      - asset matches symbol
      - notes contains account_key

    Returns the trade id (int).
    """
    conn = _get_conn()

    # Build the notes field so it embeds the account key for dedup/filtering
    full_notes = notes or f"rithmic_sync:{account_key}"
    if account_key and account_key not in full_notes:
        full_notes = f"{full_notes} [{account_key}]"

    # Normalise fill_time to "YYYY-MM-DD HH:MM:SS" if possible
    created_at = fill_time
    try:
        # Accept ISO strings, epoch strings, or already-formatted timestamps
        if fill_time and fill_time.strip():
            # Try parsing common formats
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    created_at = datetime.strptime(fill_time.strip()[:19], fmt).strftime("%Y-%m-%d %H:%M:%S")
                    break
                except ValueError:
                    continue
    except Exception:
        pass
    if not created_at:
        created_at = datetime.now(tz=_EST).strftime("%Y-%m-%d %H:%M:%S")

    # Determine status: if we have a close_price it's already closed
    status = STATUS_CLOSED if close_price is not None else STATUS_OPEN

    # Check for an existing record with matching fill_time prefix + symbol + account_key in notes
    date_prefix = created_at[:10]  # "YYYY-MM-DD"
    existing = conn.execute(
        """SELECT id FROM trades_v2
           WHERE created_at LIKE ?
             AND asset = ?
             AND notes LIKE ?
           LIMIT 1""",
        (f"{date_prefix}%", symbol, f"%{account_key}%"),
    ).fetchone()

    if existing is not None:
        trade_id = int(_row_to_dict(existing).get("id") or 0)
        # Update the existing record with latest fill data
        conn.execute(
            """UPDATE trades_v2
               SET entry      = ?,
                   close_price = ?,
                   pnl         = ?,
                   status      = ?,
                   contracts   = ?,
                   direction   = ?,
                   strategy    = ?,
                   notes       = ?,
                   source      = ?,
                   close_time  = CASE WHEN ? IS NOT NULL THEN ? ELSE close_time END
               WHERE id = ?""",
            (
                entry_price,
                close_price,
                pnl,
                status,
                contracts,
                direction.upper(),
                strategy,
                full_notes,
                source,
                close_price,
                created_at if close_price is not None else None,
                trade_id,
            ),
        )
        conn.commit()
        conn.close()
        logger.debug(
            "upsert_trade_from_fill: updated existing trade id=%d symbol=%s account=%s",
            trade_id,
            symbol,
            account_key,
        )
        return trade_id

    # No existing record — insert a new one
    sql = """INSERT INTO trades_v2
           (created_at, account_size, asset, direction, entry, sl, tp,
            contracts, status, close_price, close_time, pnl,
            strategy, notes, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    params = (
        created_at,
        150_000,  # default account_size — callers can patch if needed
        symbol,
        direction.upper(),
        entry_price,
        None,  # sl — not available from fill data
        None,  # tp — not available from fill data
        contracts,
        status,
        close_price,
        created_at if close_price is not None else None,
        pnl,
        strategy,
        full_notes,
        source,
    )
    trade_id = _insert_returning_id(conn, sql, params, "trades_v2")
    conn.commit()
    conn.close()
    logger.debug(
        "upsert_trade_from_fill: inserted new trade id=%d symbol=%s account=%s",
        trade_id,
        symbol,
        account_key,
    )
    return trade_id


def close_trade(trade_id: int, close_price: float) -> dict:
    """Close an open trade and calculate realised P&L.

    Returns a dict with the trade details including pnl.
    """
    conn = _get_conn()
    row = conn.execute("SELECT * FROM trades_v2 WHERE id = ?", (trade_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Trade {trade_id} not found")
    if row["status"] != STATUS_OPEN:
        conn.close()
        raise ValueError(f"Trade {trade_id} is already {row['status']}")

    asset = row["asset"]
    direction = row["direction"]
    entry = row["entry"]
    contracts = row["contracts"]

    spec = CONTRACT_SPECS.get(asset)
    point_value = float(spec["point"]) if spec else 1.0

    if direction.upper() == "LONG":
        pnl = (close_price - entry) * point_value * contracts
        rr = abs((close_price - entry) / (entry - row["sl"])) if row["sl"] and row["sl"] != entry else 0.0
    else:
        pnl = (entry - close_price) * point_value * contracts
        rr = abs((entry - close_price) / (row["sl"] - entry)) if row["sl"] and row["sl"] != entry else 0.0

    close_time = datetime.now(tz=_EST).strftime("%Y-%m-%d %H:%M:%S")

    conn.execute(
        """UPDATE trades_v2
           SET status = ?, close_price = ?, close_time = ?, pnl = ?, rr = ?
           WHERE id = ?""",
        (STATUS_CLOSED, close_price, close_time, round(pnl, 2), round(rr, 2), trade_id),
    )
    conn.commit()

    result = _row_to_dict(row)
    result.update(
        status=STATUS_CLOSED,
        close_price=close_price,
        close_time=close_time,
        pnl=round(pnl, 2),
        rr=round(rr, 2),
    )
    conn.close()
    return result


def cancel_trade(trade_id: int) -> None:
    """Cancel an open trade (never filled)."""
    conn = _get_conn()
    conn.execute(
        "UPDATE trades_v2 SET status = ? WHERE id = ? AND status = ?",
        (STATUS_CANCELLED, trade_id, STATUS_OPEN),
    )
    conn.commit()
    conn.close()


def _query_to_list(conn, sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT and return a list of dicts.

    Works with both SQLite and Postgres backends.  For SQLite, we use
    pd.read_sql for convenience.  For Postgres, we fetch rows directly
    and convert to dicts, avoiding pd.read_sql connection issues.
    """
    if _USE_POSTGRES:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    else:
        df = pd.read_sql(sql, conn, params=params)
        return df.to_dict(orient="records")


def get_open_trades(account_size: int | None = None) -> list[dict]:
    """Return all OPEN trades, optionally filtered by account size."""
    conn = _get_conn()
    if account_size:
        results = _query_to_list(
            conn,
            "SELECT * FROM trades_v2 WHERE status = ? AND account_size = ? ORDER BY created_at DESC",
            (STATUS_OPEN, account_size),
        )
    else:
        results = _query_to_list(
            conn,
            "SELECT * FROM trades_v2 WHERE status = ? ORDER BY created_at DESC",
            (STATUS_OPEN,),
        )
    conn.close()
    return results


def get_closed_trades(account_size: int | None = None) -> list[dict]:
    """Return all CLOSED trades for the journal."""
    conn = _get_conn()
    if account_size:
        results = _query_to_list(
            conn,
            "SELECT * FROM trades_v2 WHERE status = ? AND account_size = ? ORDER BY close_time DESC",
            (STATUS_CLOSED, account_size),
        )
    else:
        results = _query_to_list(
            conn,
            "SELECT * FROM trades_v2 WHERE status = ? ORDER BY close_time DESC",
            (STATUS_CLOSED,),
        )
    conn.close()
    return results


def get_all_trades(account_size: int | None = None) -> list[dict]:
    """Return all trades regardless of status."""
    conn = _get_conn()
    if account_size:
        results = _query_to_list(
            conn,
            "SELECT * FROM trades_v2 WHERE account_size = ? ORDER BY created_at DESC",
            (account_size,),
        )
    else:
        results = _query_to_list(
            conn,
            "SELECT * FROM trades_v2 ORDER BY created_at DESC",
        )
    conn.close()
    return results


def get_today_pnl(account_size: int | None = None) -> float:
    """Sum of realised P&L for trades closed today."""
    today = datetime.now(tz=_EST).strftime("%Y-%m-%d")
    conn = _get_conn()
    if account_size:
        row = conn.execute(
            "SELECT COALESCE(SUM(pnl), 0) FROM trades_v2 WHERE status = ? AND close_time LIKE ? AND account_size = ?",
            (STATUS_CLOSED, f"{today}%", account_size),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(SUM(pnl), 0) FROM trades_v2 WHERE status = ? AND close_time LIKE ?",
            (STATUS_CLOSED, f"{today}%"),
        ).fetchone()
    conn.close()
    # For Postgres _RowProxy, access by index via values; for SQLite Row, use index
    if row is None:
        return 0.0
    if hasattr(row, "values"):
        vals = list(row.values())
        return float(vals[0]) if vals else 0.0
    return float(row[0]) if row else 0.0  # type: ignore[index]


def get_today_trades(account_size: int | None = None) -> list[dict]:
    """Return all trades created or closed today."""
    today = datetime.now(tz=_EST).strftime("%Y-%m-%d")
    conn = _get_conn()
    if account_size:
        results = _query_to_list(
            conn,
            """SELECT * FROM trades_v2
               WHERE (created_at LIKE ? OR close_time LIKE ?)
                 AND account_size = ?
               ORDER BY created_at DESC""",
            (f"{today}%", f"{today}%", account_size),
        )
    else:
        results = _query_to_list(
            conn,
            """SELECT * FROM trades_v2
               WHERE created_at LIKE ? OR close_time LIKE ?
               ORDER BY created_at DESC""",
            (f"{today}%", f"{today}%"),
        )
    conn.close()
    return results


# ---------------------------------------------------------------------------
# Risk helpers
# ---------------------------------------------------------------------------


def calc_max_contracts(
    entry: float,
    sl: float,
    asset: str,
    risk_dollars: float,
    hard_max: int,
) -> int:
    """Calculate max contracts respecting risk-per-trade and account cap.

    Uses the currently active CONTRACT_SPECS (micro or full).
    The hard_max should come from account profile's max_contracts_micro
    when trading micros, or max_contracts when trading full-size.
    """
    spec = CONTRACT_SPECS.get(asset)
    if spec is None:
        return 1
    risk_per_contract = abs(entry - sl) * float(spec["point"])
    if risk_per_contract <= 0:
        return 1
    raw = int(risk_dollars // risk_per_contract)
    return max(1, min(raw, hard_max))


def get_max_contracts_for_profile(profile_key: str) -> int:
    """Return the appropriate max contracts limit for the active contract mode."""
    profile = ACCOUNT_PROFILES.get(profile_key)
    if profile is None:
        return 4
    if CONTRACT_MODE == "micro":
        return int(profile.get("max_contracts_micro", profile["max_contracts"]))
    return int(profile["max_contracts"])


def calc_pnl(
    asset: str,
    direction: str,
    entry: float,
    close_price: float,
    contracts: int,
) -> float:
    """Calculate P&L for a given trade."""
    spec = CONTRACT_SPECS.get(asset)
    point_value = float(spec["point"]) if spec else 1.0
    if direction.upper() == "LONG":
        return (close_price - entry) * point_value * contracts
    else:
        return (entry - close_price) * point_value * contracts


# ---------------------------------------------------------------------------
# __all__ — public API for wildcard imports
# ---------------------------------------------------------------------------
__all__ = [
    "create_trade",
    "upsert_trade_from_fill",
    "close_trade",
    "cancel_trade",
    "_query_to_list",
    "get_open_trades",
    "get_closed_trades",
    "get_all_trades",
    "get_today_pnl",
    "get_today_trades",
    "calc_max_contracts",
    "get_max_contracts_for_profile",
    "calc_pnl",
]
