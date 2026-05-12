# rustrade-core

Core types, traits, and in-process buses for the
[rustrade](https://github.com/nuniesmith/rustrade) trading-bot framework.

This crate is the **type-layer foundation**: every other `rustrade-*` crate
depends on it, and it depends on nothing internal. No I/O, no async-runtime
state, no exchange-specific logic — just the abstractions the rest of the
framework is built on.

```toml
[dependencies]
rustrade-core = "0.1"
```

## What's in this crate

- **Domain types** — `Price`, `Volume`, `Candle`, `Tick`, `Order`, `Fill`, `Position`
- **Market primitives** — `Side`, `Symbol`, `Exchange`, `MarketDataEvent`
- **The `Brain` trait** — the single abstraction every strategy implements
- **`Decision` + `SizeHint`** — intent-vs-execution separation
- **Trait contracts** — `ExchangeClient`, `MarketSource`, `FillSource`, `EventSource`
- **Broadcast buses** — `MarketDataBus`, `SignalBus`
- **Error types** — `Error`, `Result`

## What's not in this crate

- Service lifecycle / supervision → [`rustrade-supervisor`](https://crates.io/crates/rustrade-supervisor)
- Risk primitives → [`rustrade-risk`](https://crates.io/crates/rustrade-risk)
- Backtest replay → [`rustrade-backtest`](https://crates.io/crates/rustrade-backtest)
- Concrete exchange adapters → e.g. [`rustrade-kucoin`](https://crates.io/crates/rustrade-kucoin)

See the [workspace README](https://github.com/nuniesmith/rustrade) for the full
architecture diagram, design principles, and quick-start.

## License

MIT — see `LICENSE`.
