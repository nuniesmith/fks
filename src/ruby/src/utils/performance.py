"""
Performance metrics for trading strategy evaluation.

Adapted from ruby/lib/core/journal.py — pure-function implementations
with no database dependencies. Useful for A/B testing, daily summaries,
and Grok report enrichment.

Usage:
    from utils.performance import compute_performance_metrics

    daily_pnls = [12.50, -8.20, 5.30, -3.10, 7.80, ...]
    metrics = compute_performance_metrics(daily_pnls)
    print(metrics["sharpe_ratio"], metrics["max_drawdown"])
"""

from __future__ import annotations

import math


def compute_performance_metrics(
    pnls: list[float],
    annualization_factor: float = 365.0,
) -> dict[str, float]:
    """Compute comprehensive trading performance metrics from a PnL series.

    Parameters
    ----------
    pnls : list[float]
        Ordered list of period PnL values (e.g., daily PnL in USDT).
    annualization_factor : float
        Factor for annualizing Sharpe ratio.  365 for daily crypto,
        252 for daily equities.

    Returns
    -------
    dict with keys:
        total_pnl, win_count, loss_count, win_rate, avg_pnl,
        avg_win, avg_loss, expectancy, profit_factor,
        sharpe_ratio, sortino_ratio, max_drawdown, max_drawdown_pct,
        current_streak, best_period, worst_period, calmar_ratio
    """
    if not pnls:
        return _empty_metrics()

    n = len(pnls)
    total = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / n if n > 0 else 0.0
    avg_pnl = total / n if n > 0 else 0.0
    avg_win = sum(wins) / win_count if win_count > 0 else 0.0
    avg_loss = sum(losses) / loss_count if loss_count > 0 else 0.0

    # Expectancy = win_rate * avg_win + loss_rate * avg_loss
    loss_rate = 1.0 - win_rate
    expectancy = win_rate * avg_win + loss_rate * avg_loss

    # Profit factor = gross_wins / gross_losses
    gross_wins = sum(wins) if wins else 0.0
    gross_losses = abs(sum(losses)) if losses else 0.0
    profit_factor = (
        gross_wins / gross_losses if gross_losses > 0 else float("inf") if gross_wins > 0 else 0.0
    )

    # Sharpe ratio (annualized)
    if n >= 5:
        mean = avg_pnl
        variance = sum((p - mean) ** 2 for p in pnls) / (n - 1)
        std = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean / std * math.sqrt(annualization_factor)) if std > 0 else 0.0
    else:
        sharpe = 0.0

    # Sortino ratio (annualized, using downside deviation)
    if n >= 5:
        downside = [min(0.0, p - 0.0) ** 2 for p in pnls]  # target = 0
        downside_var = sum(downside) / (n - 1)
        downside_std = math.sqrt(downside_var) if downside_var > 0 else 0.0
        sortino = (
            (avg_pnl / downside_std * math.sqrt(annualization_factor)) if downside_std > 0 else 0.0
        )
    else:
        sortino = 0.0

    # Max drawdown
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    # Max drawdown as percentage of peak
    max_dd_pct = (max_dd / peak * 100) if peak > 0 else 0.0

    # Calmar ratio = annualized return / max drawdown
    annualized_return = avg_pnl * annualization_factor
    calmar = annualized_return / max_dd if max_dd > 0 else 0.0

    # Current streak
    streak = 0
    for p in reversed(pnls):
        if p > 0:
            if streak >= 0:
                streak += 1
            else:
                break
        elif p < 0:
            if streak <= 0:
                streak -= 1
            else:
                break
        else:
            break

    return {
        "total_pnl": round(total, 4),
        "periods": n,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate * 100, 1),
        "avg_pnl": round(avg_pnl, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "expectancy": round(expectancy, 4),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown": round(max_dd, 4),
        "max_drawdown_pct": round(max_dd_pct, 1),
        "calmar_ratio": round(calmar, 2),
        "current_streak": streak,
        "best_period": round(max(pnls), 4),
        "worst_period": round(min(pnls), 4),
    }


def _empty_metrics() -> dict[str, float]:
    """Return a zeroed metrics dict."""
    return {
        "total_pnl": 0.0,
        "periods": 0,
        "win_count": 0,
        "loss_count": 0,
        "win_rate": 0.0,
        "avg_pnl": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "expectancy": 0.0,
        "profit_factor": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown": 0.0,
        "max_drawdown_pct": 0.0,
        "calmar_ratio": 0.0,
        "current_streak": 0,
        "best_period": 0.0,
        "worst_period": 0.0,
    }
