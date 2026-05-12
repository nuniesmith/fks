# rustrade

Facade crate for the [rustrade](https://github.com/nuniesmith/rustrade)
trading-bot framework. Re-exports the building blocks of the workspace
and ships the top-level `Bot` builder + `ExecutionService` that wires
them together.

```toml
[dependencies]
rustrade = "0.1"
```

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

## What this crate gives you

Builds on the rustrade family:

- [`rustrade-core`](https://crates.io/crates/rustrade-core) — types, traits, buses
- [`rustrade-supervisor`](https://crates.io/crates/rustrade-supervisor) — service lifecycle
- [`rustrade-risk`](https://crates.io/crates/rustrade-risk) — circuit breaker, session PnL, sizer

Plus its own contribution:

- **`Bot`** — wires brains + exchange + supervisor into a runnable system
- **`BotConfig` / `BotConfigBuilder`** — fluent config
- **`ExecutionService`** — the `TradingService` that calls `brain.on_event()`
  and translates `Decision`s to `place_order()` calls, gated by the risk
  primitives
- **`logging`** — `init()` / `init_json()` for tracing subscriber setup

## Companion crates

- [`rustrade-backtest`](https://crates.io/crates/rustrade-backtest) — replay
  the same brain against historical data with zero code changes
- [`rustrade-kucoin`](https://crates.io/crates/rustrade-kucoin) — concrete
  exchange adapter (built on `exchange-apiws`)
- [`rustrade-notify`](https://crates.io/crates/rustrade-notify) — Discord
  heartbeats as a supervised service

See the [workspace README](https://github.com/nuniesmith/rustrade) for the
architecture diagram, design principles, and the full crate layout.

## License

MIT — see `LICENSE`.
