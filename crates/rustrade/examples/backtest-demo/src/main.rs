//! Demo: backtest a 5/20 EMA-cross brain over 500 synthetic sine-wave candles.
//!
//! Demonstrates that:
//!   - The same `Brain` trait used in production runs in the backtest with no changes.
//!   - The `SimExchange` fills market orders at the next bar's open.
//!   - `BacktestMetrics` reports total return, win rate, drawdown, Sharpe.
//!
//! Run: `cargo run -p backtest-demo`

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use async_trait::async_trait;
use parking_lot::Mutex;

use rustrade_backtest::{BacktestConfig, BacktestEngine, SimExchange, SimExchangeConfig};
use rustrade_core::{
    Brain, BrainHealth, Candle, Decision, MarketDataEvent, Position, Result, SizeHint, Volume,
};

// ── A 5/20 EMA-cross brain ──────────────────────────────────────────────────

struct EmaCrossBrain {
    name: String,
    fast: Mutex<Ema>,
    slow: Mutex<Ema>,
    last_signal: Mutex<i8>,
    events: AtomicU64,
}

impl EmaCrossBrain {
    fn new(fast_len: usize, slow_len: usize) -> Self {
        Self {
            name: format!("ema-cross[{fast_len}/{slow_len}]"),
            fast: Mutex::new(Ema::new(fast_len)),
            slow: Mutex::new(Ema::new(slow_len)),
            last_signal: Mutex::new(0),
            events: AtomicU64::new(0),
        }
    }
}

struct Ema {
    alpha: f64,
    value: Option<f64>,
}

impl Ema {
    fn new(period: usize) -> Self {
        let alpha = 2.0 / (period as f64 + 1.0);
        Self { alpha, value: None }
    }
    fn update(&mut self, x: f64) -> f64 {
        let new = match self.value {
            Some(v) => v + self.alpha * (x - v),
            None => x,
        };
        self.value = Some(new);
        new
    }
}

#[async_trait]
impl Brain for EmaCrossBrain {
    fn name(&self) -> &str {
        &self.name
    }

    async fn on_event(&self, event: &MarketDataEvent, _position: &Position) -> Result<Decision> {
        let MarketDataEvent::Candle { candle, .. } = event else {
            return Ok(Decision::hold());
        };
        self.events.fetch_add(1, Ordering::Relaxed);

        let fast = self.fast.lock().update(candle.close);
        let slow = self.slow.lock().update(candle.close);

        let raw: i8 = if fast > slow {
            1
        } else if fast < slow {
            -1
        } else {
            0
        };

        let mut last = self.last_signal.lock();
        if raw == 0 || raw == *last {
            return Ok(Decision::hold());
        }
        *last = raw;

        let decision = match raw {
            1 => Decision::buy(1.0).with_size_hint(SizeHint::Quantity(Volume(1.0))),
            -1 => Decision::sell(1.0).with_size_hint(SizeHint::Quantity(Volume(1.0))),
            _ => Decision::hold(),
        };
        Ok(decision)
    }

    async fn health(&self) -> BrainHealth {
        BrainHealth {
            healthy: true,
            events_processed: self.events.load(Ordering::Relaxed),
            non_hold_decisions: 0,
            details: serde_json::Value::Null,
        }
    }
}

// ── Synthetic candles ────────────────────────────────────────────────────────

fn synthetic_candles(n: usize) -> Vec<Candle> {
    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        let t = i as f64;
        let mid = 100.0 + 10.0 * (t * 0.07).sin() + 5.0 * (t * 0.013).cos();
        let high = mid + 0.5;
        let low = mid - 0.5;
        out.push(Candle {
            time: (i as i64) * 60_000, // 1-minute bars in ms
            open: mid,
            high,
            low,
            close: mid,
            volume: 100.0,
        });
    }
    out
}

// ── main ─────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    rustrade::logging::init();

    let candles = synthetic_candles(500);
    let brain = Arc::new(EmaCrossBrain::new(5, 20));

    let sim = SimExchange::new(
        SimExchangeConfig::default()
            .with_initial_balance(10_000.0)
            .with_slippage_bps(2.0)
            .with_commission_bps(5.0),
    );

    let engine = BacktestEngine::new(BacktestConfig::default(), sim, brain);
    let run = engine.run("BTCUSDT", candles).await?;

    let m = &run.metrics;
    println!();
    println!("─── Backtest summary ───");
    println!("trades         : {}", m.trades);
    println!("win rate       : {:.1}%", m.win_rate * 100.0);
    println!("winners/losers : {}/{}", m.winners, m.losers);
    println!("gross profit   : {:>10.2}", m.gross_profit);
    println!("gross loss     : {:>10.2}", m.gross_loss);
    println!("profit factor  : {:>10.2}", m.profit_factor);
    println!("total fees     : {:>10.2}", m.total_fees);
    println!();
    println!("initial equity : {:>10.2}", m.initial_equity);
    println!("final equity   : {:>10.2}", m.final_equity);
    println!("total return   : {:>10.2} ({:+.2}%)", m.total_return, m.total_return_pct);
    println!("max drawdown   : {:>10.2} ({:+.2}%)", m.max_drawdown, m.max_drawdown_pct);
    println!("sharpe         : {:>10.2}", m.sharpe);
    println!("sortino        : {:>10.2}", m.sortino);
    println!();
    println!("equity curve  : {} points", run.equity_curve.len());

    Ok(())
}
