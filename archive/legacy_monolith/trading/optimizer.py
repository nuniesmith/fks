# src/optimizer.py

from trading.backtest import run_backtest


def objective(trial, df_prices):
    M = trial.suggest_int("M", 5, 200)
    atr_period = trial.suggest_int("atr_period", 5, 30)
    sl_multiplier = trial.suggest_float("sl_multiplier", 1.0, 5.0)
    tp_multiplier = trial.suggest_float("tp_multiplier", 1.0, 10.0)
    metrics, _, _, _ = run_backtest(
        df_prices, M, atr_period, sl_multiplier, tp_multiplier
    )
    return metrics["Sharpe"]
