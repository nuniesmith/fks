# rustrade-backtest

Replay engine + simulated exchange for the
[rustrade](https://github.com/nuniesmith/rustrade) trading-bot framework.

The headline guarantee: **any `Brain` that runs in production runs in a
backtest with zero code changes.** Same trait, same `Decision`, same
`ExchangeClient` — `SimExchange` just implements that trait in-memory.

```toml
[dependencies]
rustrade-backtest = "0.1"
```

## What's in this crate

- **`BacktestEngine`** — replay loop that consumes a `Vec<Candle>` and
  dispatches events to the brain, mirroring `rustrade::ExecutionService`'s
  decision-to-order translation.
- **`SimExchange`** — in-memory `ExchangeClient` impl. Fills market orders
  at the next bar's open with configurable slippage + commission, tracks
  position, balance, and a fill log.
- **`BacktestMetrics`** — total return, win rate, max drawdown, profit
  factor, annualised Sharpe + Sortino, computed from the equity curve.

## Quick start

```rust,ignore
use std::sync::Arc;
use rustrade_backtest::{BacktestEngine, BacktestConfig, SimExchange, SimExchangeConfig};

let candles: Vec<rustrade_core::Candle> = load_history();
let brain  = Arc::new(my_brain());

let sim = SimExchange::new(
    SimExchangeConfig::default()
        .with_initial_balance(10_000.0)
        .with_slippage_bps(2.0)
        .with_commission_bps(5.0),
);

let run = BacktestEngine::new(BacktestConfig::default(), sim, brain)
    .run("BTCUSDT", candles)
    .await?;

println!("Sharpe: {:.2}, max DD: {:.2}%", run.metrics.sharpe, run.metrics.max_drawdown_pct);
```

## What's not in this crate

- **Data loaders** (parquet, CSV) — write your own `Vec<Candle>` from
  whatever storage you use. A future feature-gated `loader` module can
  add polars-based adapters.
- **Vectorized indicators** — see [`indicators-ta`](https://crates.io/crates/indicators-ta).
- **Multi-asset / multi-strategy orchestration** — for now, one brain,
  one symbol, one stream. Run multiple engines in parallel for ensembles.

See the [workspace README](https://github.com/nuniesmith/rustrade) for how
this slots into the full framework.

## License

MIT — see `LICENSE`.
