//! Backtest performance metrics.
//!
//! Computed from the equity curve and the fill log at the end of a run.
//! Same formulas as standard practice — Sharpe is annualised assuming the
//! [`MetricsConfig::periods_per_year`] hint, Sortino uses downside deviation
//! only, max drawdown is peak-to-trough equity.

use chrono::{DateTime, Utc};
use rustrade_core::{Fill, Side};
use serde::{Deserialize, Serialize};

/// One point on the equity curve, recorded once per processed bar.
#[allow(missing_docs)] // self-evident timestamp_ms / equity fields
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct EquityPoint {
    pub timestamp_ms: i64,
    pub equity: f64,
}

/// One round-trip trade reconstructed from the fill log. The MVP assumes a
/// single open position at a time per symbol — when a fill flips the
/// position to flat, the previous open block is closed.
#[allow(missing_docs)] // self-evident trade-record fields
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradeRecord {
    pub symbol: String,
    pub side: Side,
    pub entry_price: f64,
    pub exit_price: f64,
    pub size: f64,
    pub pnl: f64,
    pub fees: f64,
    pub entry_ts: Option<DateTime<Utc>>,
    pub exit_ts: Option<DateTime<Utc>>,
}

impl TradeRecord {
    /// `true` when net PnL is strictly positive.
    pub fn is_winner(&self) -> bool {
        self.pnl > 0.0
    }
}

/// Knobs for the metric computation.
#[allow(missing_docs)] // each field has its own /// doc above
#[derive(Debug, Clone, Copy)]
pub struct MetricsConfig {
    /// How many sample points are in one trading year. For minute bars, 60 *
    /// 24 * 365 ≈ 525_600 if the market never closes (crypto), or
    /// 252 * 6.5 * 60 ≈ 98_280 for stocks. Use whatever matches your bars.
    /// Sharpe and Sortino multiply by `sqrt(periods_per_year)` to annualise.
    pub periods_per_year: f64,
    /// Risk-free rate per period (default 0.0 — fine for short backtests).
    pub risk_free_rate: f64,
}

impl Default for MetricsConfig {
    fn default() -> Self {
        // Crypto-friendly default — 1m bars, 24/7 market.
        Self {
            periods_per_year: 525_600.0,
            risk_free_rate: 0.0,
        }
    }
}

/// Aggregated backtest performance metrics produced at the end of a run.
#[allow(missing_docs)] // standard performance metric names; see [`Self::compute`]
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BacktestMetrics {
    pub initial_equity: f64,
    pub final_equity: f64,
    pub total_return: f64,
    pub total_return_pct: f64,
    pub max_drawdown: f64,
    pub max_drawdown_pct: f64,
    pub sharpe: f64,
    pub sortino: f64,
    pub trades: usize,
    pub winners: usize,
    pub losers: usize,
    pub win_rate: f64,
    pub gross_profit: f64,
    pub gross_loss: f64,
    pub profit_factor: f64,
    pub total_fees: f64,
}

impl BacktestMetrics {
    /// Compute metrics from an equity curve and a list of completed trades.
    pub fn compute(
        equity: &[EquityPoint],
        trades: &[TradeRecord],
        cfg: MetricsConfig,
    ) -> Self {
        if equity.is_empty() {
            return Self::default();
        }

        let initial = equity.first().unwrap().equity;
        let final_eq = equity.last().unwrap().equity;
        let total_return = final_eq - initial;
        let total_return_pct = if initial.abs() > f64::EPSILON {
            (total_return / initial) * 100.0
        } else {
            0.0
        };

        // Max drawdown: peak-to-trough on the equity curve.
        let mut peak = initial;
        let mut max_dd = 0.0;
        for p in equity {
            if p.equity > peak {
                peak = p.equity;
            }
            let dd = peak - p.equity;
            if dd > max_dd {
                max_dd = dd;
            }
        }
        let max_drawdown_pct = if peak.abs() > f64::EPSILON {
            (max_dd / peak) * 100.0
        } else {
            0.0
        };

        // Per-period returns from the equity curve.
        let returns: Vec<f64> = equity
            .windows(2)
            .map(|w| {
                let prev = w[0].equity;
                if prev.abs() > f64::EPSILON {
                    (w[1].equity - prev) / prev
                } else {
                    0.0
                }
            })
            .collect();

        let sharpe = annualised_sharpe(&returns, cfg);
        let sortino = annualised_sortino(&returns, cfg);

        // Trade statistics.
        let winners = trades.iter().filter(|t| t.is_winner()).count();
        let losers = trades.iter().filter(|t| t.pnl < 0.0).count();
        let win_rate = if !trades.is_empty() {
            winners as f64 / trades.len() as f64
        } else {
            0.0
        };
        let gross_profit: f64 = trades.iter().filter(|t| t.pnl > 0.0).map(|t| t.pnl).sum();
        let gross_loss: f64 = trades.iter().filter(|t| t.pnl < 0.0).map(|t| t.pnl).sum();
        let profit_factor = if gross_loss.abs() > f64::EPSILON {
            gross_profit / gross_loss.abs()
        } else if gross_profit > 0.0 {
            f64::INFINITY
        } else {
            0.0
        };
        let total_fees: f64 = trades.iter().map(|t| t.fees).sum();

        Self {
            initial_equity: initial,
            final_equity: final_eq,
            total_return,
            total_return_pct,
            max_drawdown: max_dd,
            max_drawdown_pct,
            sharpe,
            sortino,
            trades: trades.len(),
            winners,
            losers,
            win_rate,
            gross_profit,
            gross_loss,
            profit_factor,
            total_fees,
        }
    }
}

fn annualised_sharpe(returns: &[f64], cfg: MetricsConfig) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }
    let mean_ret = mean(returns);
    let std = std_dev(returns, mean_ret);
    if std.abs() < f64::EPSILON {
        return 0.0;
    }
    ((mean_ret - cfg.risk_free_rate) / std) * cfg.periods_per_year.sqrt()
}

fn annualised_sortino(returns: &[f64], cfg: MetricsConfig) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }
    let mean_ret = mean(returns);
    let downside: Vec<f64> = returns.iter().copied().filter(|r| *r < 0.0).collect();
    if downside.is_empty() {
        return 0.0;
    }
    let downside_mean = mean(&downside);
    let downside_std = std_dev(&downside, downside_mean);
    if downside_std.abs() < f64::EPSILON {
        return 0.0;
    }
    ((mean_ret - cfg.risk_free_rate) / downside_std) * cfg.periods_per_year.sqrt()
}

fn mean(xs: &[f64]) -> f64 {
    xs.iter().sum::<f64>() / xs.len() as f64
}

fn std_dev(xs: &[f64], mean: f64) -> f64 {
    let var = xs.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (xs.len() as f64 - 1.0).max(1.0);
    var.sqrt()
}

/// Reconstruct round-trip trades from the chronological fill log.
///
/// The MVP assumes a single open position at a time per symbol. When fills
/// flip the position through zero (or arrive at exactly zero), the open
/// block closes and a [`TradeRecord`] is emitted.
pub fn build_trade_log(fills: &[Fill]) -> Vec<TradeRecord> {
    use std::collections::HashMap;

    #[derive(Default)]
    struct Open {
        side: Option<Side>,
        size: f64,        // signed: + long, - short
        entry_price: f64, // weighted average
        fees: f64,
        ts: Option<DateTime<Utc>>,
    }

    let mut open: HashMap<String, Open> = HashMap::new();
    let mut out = Vec::new();

    for f in fills {
        let signed_size = match f.side {
            Side::Buy => f.size.value(),
            Side::Sell => -f.size.value(),
        };
        let entry_price = f.price.value();
        let st = open.entry(f.symbol.clone()).or_default();
        st.fees += f.fee;

        if st.size == 0.0 {
            // Opening a fresh position.
            st.side = Some(f.side);
            st.size = signed_size;
            st.entry_price = entry_price;
            st.ts = Some(f.timestamp);
        } else if st.size.signum() == signed_size.signum() {
            // Adding to the position — weighted-average entry.
            let total_notional = st.entry_price * st.size.abs() + entry_price * signed_size.abs();
            st.size += signed_size;
            st.entry_price = total_notional / st.size.abs();
        } else {
            // Reducing or flipping. Close out the matched portion.
            let closed = signed_size.abs().min(st.size.abs());
            let direction = st.size.signum();
            let pnl = direction * (entry_price - st.entry_price) * closed;
            out.push(TradeRecord {
                symbol: f.symbol.clone(),
                side: st.side.unwrap_or(Side::Buy),
                entry_price: st.entry_price,
                exit_price: entry_price,
                size: closed,
                pnl,
                fees: st.fees,
                entry_ts: st.ts,
                exit_ts: Some(f.timestamp),
            });

            st.size += signed_size;
            if st.size == 0.0 {
                *st = Open::default();
            } else {
                // Flipped — the remainder is a new open in the opposite direction.
                st.side = Some(f.side);
                st.entry_price = entry_price;
                st.ts = Some(f.timestamp);
                st.fees = 0.0;
            }
        }
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn metrics_with_no_data_are_zero() {
        let m = BacktestMetrics::compute(&[], &[], MetricsConfig::default());
        assert_eq!(m.total_return, 0.0);
        assert_eq!(m.sharpe, 0.0);
    }

    #[test]
    fn drawdown_captured_on_dip_then_recovery() {
        let curve = vec![
            EquityPoint { timestamp_ms: 0, equity: 100.0 },
            EquityPoint { timestamp_ms: 1, equity: 120.0 },
            EquityPoint { timestamp_ms: 2, equity: 90.0 },
            EquityPoint { timestamp_ms: 3, equity: 110.0 },
        ];
        let m = BacktestMetrics::compute(&curve, &[], MetricsConfig::default());
        // peak = 120, trough = 90 → max drawdown = 30
        assert!((m.max_drawdown - 30.0).abs() < 1e-9);
        assert!((m.max_drawdown_pct - 25.0).abs() < 1e-9); // 30 / 120
    }

    #[test]
    fn build_trade_log_pairs_open_and_close() {
        let now = Utc::now();
        let fills = vec![
            Fill {
                symbol: "BTCUSDT".to_string(),
                order_id: "1".to_string(),
                client_id: None,
                side: Side::Buy,
                price: rustrade_core::Price(100.0),
                size: rustrade_core::Volume(1.0),
                fee: 0.5,
                fee_currency: "USDT".to_string(),
                timestamp: now,
            },
            Fill {
                symbol: "BTCUSDT".to_string(),
                order_id: "2".to_string(),
                client_id: None,
                side: Side::Sell,
                price: rustrade_core::Price(110.0),
                size: rustrade_core::Volume(1.0),
                fee: 0.5,
                fee_currency: "USDT".to_string(),
                timestamp: now,
            },
        ];
        let trades = build_trade_log(&fills);
        assert_eq!(trades.len(), 1);
        assert!((trades[0].pnl - 10.0).abs() < 1e-9);
        assert!((trades[0].fees - 1.0).abs() < 1e-9);
        assert!(trades[0].is_winner());
    }
}
