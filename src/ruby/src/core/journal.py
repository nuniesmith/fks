"""
Daily journal CRUD operations — save, retrieve, and compute stats.

All daily-journal-related database operations that were previously in
``models.py`` now live here.  Functions import their dependencies
from the sibling ``db_layer`` module.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from core.db_layer import (
    _USE_POSTGRES,
    _get_conn,
    _insert_returning_id,
)
from core.logging_config import get_logger

_EST = ZoneInfo("America/New_York")

logger = get_logger("models")


# ---------------------------------------------------------------------------
# Daily Journal CRUD
# ---------------------------------------------------------------------------


def save_daily_journal(
    trade_date: str,
    account_size: int,
    gross_pnl: float,
    net_pnl: float,
    num_contracts: int = 0,
    instruments: str = "",
    notes: str = "",
) -> int:
    """Save or update a daily journal entry.

    Commissions are auto-calculated as gross_pnl - net_pnl.
    If an entry already exists for the given date, it is updated.
    Returns the row id.
    """
    commissions = round(gross_pnl - net_pnl, 2)
    now = datetime.now(tz=_EST).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()

    # Check if entry exists for this date
    existing = conn.execute("SELECT id FROM daily_journal WHERE trade_date = ?", (trade_date,)).fetchone()

    if existing:
        conn.execute(
            """UPDATE daily_journal
               SET account_size = ?, gross_pnl = ?, net_pnl = ?,
                   commissions = ?, num_contracts = ?, instruments = ?,
                   notes = ?, created_at = ?
               WHERE trade_date = ?""",
            (
                account_size,
                round(gross_pnl, 2),
                round(net_pnl, 2),
                commissions,
                num_contracts,
                instruments,
                notes,
                now,
                trade_date,
            ),
        )
        row_id = existing["id"]
    else:
        insert_sql = """INSERT INTO daily_journal
               (trade_date, account_size, gross_pnl, net_pnl, commissions,
                num_contracts, instruments, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        insert_params = (
            trade_date,
            account_size,
            round(gross_pnl, 2),
            round(net_pnl, 2),
            commissions,
            num_contracts,
            instruments,
            notes,
            now,
        )
        row_id = _insert_returning_id(conn, insert_sql, insert_params, "daily_journal")

    conn.commit()
    conn.close()
    return row_id  # type: ignore[return-value]


def get_daily_journal(
    limit: int = 30,
    account_size: int | None = None,
) -> pd.DataFrame:
    """Return recent daily journal entries as a DataFrame."""
    conn = _get_conn()

    if _USE_POSTGRES:
        # For Postgres, query and convert to DataFrame manually
        from core.trades import _query_to_list

        if account_size:
            rows = _query_to_list(
                conn,
                """SELECT * FROM daily_journal
                   WHERE account_size = ?
                   ORDER BY trade_date DESC LIMIT ?""",
                (account_size, limit),
            )
        else:
            rows = _query_to_list(
                conn,
                "SELECT * FROM daily_journal ORDER BY trade_date DESC LIMIT ?",
                (limit,),
            )
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    else:
        # SQLite: use pd.read_sql directly
        if account_size:
            df = pd.read_sql(
                """SELECT * FROM daily_journal
                   WHERE account_size = ?
                   ORDER BY trade_date DESC LIMIT ?""",
                conn,
                params=(account_size, limit),
            )
        else:
            df = pd.read_sql(
                "SELECT * FROM daily_journal ORDER BY trade_date DESC LIMIT ?",
                conn,
                params=(limit,),
            )
        conn.close()
        return df


def get_journal_stats(account_size: int | None = None) -> dict:
    """Compute aggregate stats from the daily journal.

    Returns dict with total_days, total_gross, total_net, total_commissions,
    win_days, loss_days, win_rate, avg_daily_pnl, best_day, worst_day,
    current_streak.
    """
    df = get_daily_journal(limit=9999, account_size=account_size)
    if df.empty:
        return {
            "total_days": 0,
            "total_gross": 0.0,
            "total_net": 0.0,
            "total_commissions": 0.0,
            "win_days": 0,
            "loss_days": 0,
            "break_even_days": 0,
            "win_rate": 0.0,
            "avg_daily_net": 0.0,
            "best_day": 0.0,
            "worst_day": 0.0,
            "current_streak": 0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
        }

    total_days = len(df)
    total_gross = float(df["gross_pnl"].sum())  # type: ignore[arg-type]
    total_net = float(df["net_pnl"].sum())  # type: ignore[arg-type]
    total_commissions = float(df["commissions"].sum())  # type: ignore[arg-type]
    win_days = int((df["net_pnl"] > 0).sum())
    loss_days = int((df["net_pnl"] < 0).sum())
    break_even_days = int((df["net_pnl"] == 0).sum())
    win_rate = win_days / total_days * 100 if total_days > 0 else 0.0
    avg_daily_net = total_net / total_days if total_days > 0 else 0.0
    best_day = float(df["net_pnl"].max())  # type: ignore[arg-type]
    worst_day = float(df["net_pnl"].min())  # type: ignore[arg-type]

    # Current streak (sorted by date ascending for streak calc)
    sorted_df = df.sort_values("trade_date", ascending=True)
    streak = 0
    for pnl in reversed(sorted_df["net_pnl"].tolist()):
        if pnl > 0:
            if streak >= 0:
                streak += 1
            else:
                break
        elif pnl < 0:
            if streak <= 0:
                streak -= 1
            else:
                break
        else:
            break

    # ── Advanced performance metrics ─────────────────────────────────────────
    win_pnls = df[df["net_pnl"] > 0]["net_pnl"]
    loss_pnls = df[df["net_pnl"] < 0]["net_pnl"]
    avg_win = float(win_pnls.mean()) if len(win_pnls) > 0 else 0.0
    avg_loss = float(loss_pnls.mean()) if len(loss_pnls) > 0 else 0.0  # negative value

    win_rate_dec = win_rate / 100.0
    loss_rate_dec = 1.0 - win_rate_dec
    expectancy = (win_rate_dec * avg_win) + (loss_rate_dec * avg_loss)

    gross_wins = float(win_pnls.sum()) if len(win_pnls) > 0 else 0.0
    gross_losses = abs(float(loss_pnls.sum())) if len(loss_pnls) > 0 else 0.0
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0.0

    if total_days >= 5:
        pnl_std = float(df["net_pnl"].std())
        sharpe = (avg_daily_net / pnl_std * (252**0.5)) if pnl_std > 0 else 0.0
    else:
        sharpe = 0.0

    sorted_df_dd = df.sort_values("trade_date", ascending=True)
    cumulative = sorted_df_dd["net_pnl"].cumsum()
    rolling_max = cumulative.cummax()
    drawdown = rolling_max - cumulative
    max_drawdown = float(drawdown.max()) if len(drawdown) > 0 else 0.0

    return {
        "total_days": total_days,
        "total_gross": round(total_gross, 2),
        "total_net": round(total_net, 2),
        "total_commissions": round(total_commissions, 2),
        "win_days": win_days,
        "loss_days": loss_days,
        "break_even_days": break_even_days,
        "win_rate": round(win_rate, 1),
        "avg_daily_net": round(avg_daily_net, 2),
        "best_day": round(best_day, 2),
        "worst_day": round(worst_day, 2),
        "current_streak": streak,
        "expectancy": round(expectancy, 2),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown": round(max_drawdown, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
    }


# ---------------------------------------------------------------------------
# __all__ — public API for wildcard imports
# ---------------------------------------------------------------------------
__all__ = [
    "save_daily_journal",
    "get_daily_journal",
    "get_journal_stats",
]
