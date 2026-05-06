# rustrade

Open-source trading-bot framework in Rust. Ships the scaffolding —
service lifecycle, supervision, risk primitives, buses, traits — that
every trading bot rewrites from scratch. Plug in your own exchange
adapter and strategy (`Brain`) and you get a production-ready bot.

> **Status: 0.1.0.** The framework is feature-complete: supervisor,
> facade, risk primitives, and backtest replay engine all merged with
> tests. One concrete adapter is shipped (`rustrade-kucoin`).
> Crates.io publishing is gated on the eventual standalone-repo move.

---

## Design in one diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOUR SERVICE                            │
│  (kucoin-v2, binance-bot, janus-bin, …)                         │
│                                                                 │
│  fn main() {                                                    │
│    let exchange = Arc::new(KucoinExchangeAdapter::new(..));     │
│    let brains   = vec![Arc::new(MySarBrain::new(..))];          │
│    Bot::new(config, exchange, brains)                           │
│       .run_until_shutdown().await                               │
│  }                                                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     rustrade  (facade)                          │
│   Bot builder · BotConfigBuilder · ExecutionService · logging   │
└──┬────────────┬────────────┬────────────┬───────────────────────┘
   │            │            │            │
┌──▼─────┐ ┌────▼──────┐ ┌───▼─────┐ ┌────▼────────┐
│  -core │ │-supervisor│ │  -risk  │ │  -backtest  │
│        │ │           │ │         │ │             │
│ Types, │ │ Service   │ │ Position│ │ Replay      │
│ Brain, │ │ lifecycle,│ │ sizer,  │ │ engine,     │
│ Buses, │ │ backoff,  │ │ breaker,│ │ SimExchange,│
│ Traits │ │ circuit   │ │ session │ │ metrics     │
│        │ │ breaker   │ │ PnL     │ │             │
└────────┘ └───────────┘ └─────────┘ └─────────────┘
   ▲                                     ▲
   │  (your brain consumes these)        │
   │                                     │
┌──┴──────────┐  ┌──────────────┐        │
│ exchange-   │  │ indicators-  │        │
│ apiws       │  │ ta           │────────┤
│ (published) │  │ (published)  │        │
└─────────────┘  └──────────────┘        │
        ▲                                │
        │                                │
┌───────┴───────────┐         ┌──────────▼──────────┐
│ rustrade-kucoin   │         │   janus / your IP   │
│  (published)      │         │ neuromorphic, ML,   │
│                   │         │ proprietary brains  │
└───────────────────┘         └─────────────────────┘
```

---

## What's in this workspace

| Crate                  | Role                                                              |
|------------------------|-------------------------------------------------------------------|
| `rustrade-core`        | Types, traits, buses — zero runtime, no I/O                       |
| `rustrade-supervisor`  | Service lifecycle, backoff, circuit breaker, lifecycle state machine |
| `rustrade-risk`        | Generic risk primitives — sizing, breakers, session PnL           |
| `rustrade-backtest`    | Replay engine, sim exchange, metrics                              |
| `rustrade`             | Facade — `Bot` builder, `ExecutionService`, logging               |
| `rustrade-kucoin`      | KuCoin Futures `ExchangeClient` adapter (built on `exchange-apiws`) |

### Examples (in `examples/`)

| Example          | Demonstrates                                                          |
|------------------|-----------------------------------------------------------------------|
| `noop-bot`       | Smallest possible bot — `NoopBrain` + `MockExchange`, 5 ticker events |
| `kucoin-stub-bot`| Real `KuCoinClient` + `KucoinExchangeAdapter`, stub brain, 1s shutdown |
| `kucoin-v2`      | Production-shaped binary: SAR brain + REST candle poller + framework |
| `backtest-demo`  | 5/20 EMA-cross brain over 500 synthetic candles, prints metrics       |

---

## Quick start

```rust,ignore
use std::sync::Arc;
use rustrade::{Bot, BotConfig, Brain, ExchangeClient};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    rustrade::logging::init();

    let exchange: Arc<dyn ExchangeClient> = Arc::new(my_exchange_adapter());
    let brains:   Vec<Arc<dyn Brain>>     = vec![Arc::new(my_brain())];

    let config = BotConfig::builder()
        .name("my-bot")
        .session_symbol("BTCUSDT")
        .close_positions_on_shutdown(true)
        .flatten_symbols(["BTCUSDT"])
        .build();

    Bot::new(config, exchange, brains)
        .run_until_shutdown()
        .await
}
```

---

## Backtest the same brain

The headline guarantee: **any brain that runs in production runs in a
backtest with zero code changes.** Same `Brain` trait, same `Decision`,
same `ExchangeClient` — `SimExchange` just implements that trait
in-memory.

```rust,ignore
use rustrade_backtest::{BacktestEngine, BacktestConfig, SimExchange, SimExchangeConfig};

let candles: Vec<Candle> = load_history();
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

---

## Build & test

```bash
cargo check  --workspace      # all crates + examples
cargo test   --workspace      # 50+ unit tests, 2 doctests
cargo run -p backtest-demo    # quick end-to-end sanity check
```

---

## Design principles

1. **`Brain` is the only abstraction that matters.** Everything else
   (supervisor, exchange, risk, execution, backtest) is plumbing around
   the brain. Get the trait right and the rest follows.
2. **Live and backtest share the same code path.** `Bot` and
   `BacktestEngine` both call `brain.on_event(&event, &position)`. No
   "is this live or sim?" branching inside the brain.
3. **Trait surfaces are narrow on purpose.** `ExchangeClient` exposes
   five methods. Adapter authors can grow exchange-specific surface
   on the concrete type for service code that needs it
   (`adapter.client()` on `KucoinExchangeAdapter`).
4. **Risk gates run before the network.** `CircuitBreaker.is_tripped()`
   and `SessionPnl.is_session_halted()` are checked in
   `ExecutionService` before any `place_order()` call goes out. No
   degenerate inputs reach the exchange.
5. **The framework deletes code.** Every line that lives here is a
   line a future bot doesn't have to write — supervisor backoff,
   sizing math, sim fills, equity curves, drawdown. The kucoin v2 port
   removed ~3000 lines of v1 service plumbing for this reason.

---

## Status of each crate

| Crate                  | Tests | Public API stable for 0.1 | Notes                                    |
|------------------------|-------|---------------------------|------------------------------------------|
| `rustrade-core`        | 0     | yes                       | Pure types/traits, no functions to test  |
| `rustrade-supervisor`  | 27    | yes                       | Includes chaos tests                     |
| `rustrade-risk`        | 13    | yes                       | Three primitives: breaker, session, sizer |
| `rustrade-backtest`    | 6     | yes                       | Single-symbol, market orders only        |
| `rustrade`             | 0     | yes                       | Facade — re-exports + Bot                |
| `rustrade-kucoin`      | 4     | yes                       | Holds for shadow-run before publish      |

---

## License

MIT. See `LICENSE`.

---

## What's not here

- **Data loaders** (parquet/CSV) — write your own `Vec<Candle>` for now.
- **Vectorized indicators** — `indicators-ta` already covers this.
- **WS tick aggregation** — REST polling only in `kucoin-v2`. Sub-bar
  latency can land as a second `TradingService` if a strategy needs it.
- **`MarginFraction` sizing** — needs a balance + leverage model the
  framework doesn't yet own.
- **Multi-symbol portfolio backtests** — run multiple `BacktestEngine`s
  in parallel for now.
