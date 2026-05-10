# rustrade — Claude Code Project Instructions

> **Repo (future):** `github.com/nuniesmith/rustrade`
> **Today's path:** lives inside `fks-full` under `crates/rustrade/`.
> Will become its own public repo before the v0.1 crates.io publish.

## What this is

Open-source trading-bot framework. Ships the scaffolding — service
lifecycle, supervision, risk primitives, buses, traits — that every
trading bot rewrites from scratch. Plug in your own exchange adapter
and strategy (`Brain`) and you get a production-ready bot.

**Status:** 0.1.0. Feature-complete; not yet on crates.io.

## Crate map (this workspace)

| Crate                  | Role                                                              |
|------------------------|-------------------------------------------------------------------|
| `rustrade-core`        | Types, traits, buses — zero runtime, no I/O                       |
| `rustrade-supervisor`  | Service lifecycle, backoff, circuit breaker                       |
| `rustrade-risk`        | Generic risk primitives — sizing, breakers, session PnL           |
| `rustrade-backtest`    | Replay engine, sim exchange, metrics                              |
| `rustrade`             | Facade — `Bot` builder, `ExecutionService`, logging               |
| `rustrade-kucoin`      | KuCoin Futures `ExchangeClient` adapter (built on `exchange-apiws`) |
| `rustrade-notify`      | Discord webhook notifications as supervised `TradingService`s     |

### Examples

| Example          | Demonstrates                                                          |
|------------------|-----------------------------------------------------------------------|
| `noop-bot`       | Smallest possible bot — `NoopBrain` + `MockExchange`                  |
| `kucoin-stub-bot`| Real `KuCoinClient` + adapter, stub brain                             |
| `kucoin-v2`      | Production-shaped binary: SAR brain + REST candle poller              |
| `backtest-demo`  | EMA-cross over synthetic candles                                      |
| `fks-bot-example`| Reference image consumed by the FKS spawner (`fks_bot_*` metrics)     |

## Build & test commands

```bash
# Type-check everything
cargo check --workspace

# Build one crate
cargo build -p rustrade-supervisor

# Test
cargo test --workspace                # all unit tests
cargo test -p rustrade-risk           # one crate

# Lint / format
cargo clippy --workspace
cargo fmt --all

# Run an example
cargo run -p noop-bot
cargo run -p fks-bot-example
```

## Code conventions

- **Edition:** Rust 2024 (`edition = "2024"`)
- **Rust version:** Minimum 1.94.1
- **Error handling:** `anyhow` in binaries, `thiserror` in library crates
- **Async runtime:** Tokio with the minimum features each crate needs
- **Lints:** `#![warn(missing_docs)]` enforced on every framework crate
- **Workspace deps:** All internal sharing goes through `[workspace.dependencies]` in the root `Cargo.toml`. **Exception:** `rustrade-supervisor` uses explicit version pins (not `workspace = true`) so it can be consumed as a path dep from foreign workspaces (e.g. `crates/janus/bin/janus/`). When publishing other crates to crates.io, do the same conversion.

## Design invariants (don't break these)

1. **`Brain` is the only abstraction that matters.** Everything else is plumbing. Push back twice before growing the trait.
2. **Live and backtest share one code path.** `Bot::run_until_shutdown` and `BacktestEngine::run` both call `brain.on_event(&event, &position)`. No `cfg(backtest)` branches in a brain.
3. **Trait surfaces stay narrow.** `ExchangeClient` is six methods. `Brain` is four. `Notifier` is one. New methods that only one adapter needs go on the concrete adapter type, not the trait.
4. **Risk gates run before the network.** `ExecutionService` checks `CircuitBreaker.is_tripped()` and `SessionPnl.is_session_halted()` *before* any `place_order()`.
5. **The framework deletes code.** Every line in `rustrade-*` is a line a future bot doesn't have to write. If a PR adds 200 lines but a future bot saves 2000, ship it. If only one consumer benefits, that addition belongs in the consumer.

See `CONTRIBUTING.md` for the long-form versions and the "add a new exchange / brain / service" recipes.

## Architecture overview

```
your-binary (e.g. kucoin-v2, fks-bot-example, janus)
   │
   ▼
rustrade  (facade)
   ├── Bot::new(config, exchange, brains)
   └── ExecutionService
        │
        ├── rustrade-core        ← types, traits, buses
        ├── rustrade-supervisor  ← lifecycle, backoff, restart
        ├── rustrade-risk        ← sizing, circuit breakers
        └── rustrade-backtest    ← replay (live + backtest share one Brain)
```

## Common workflows

### Add a new exchange adapter
Pattern: `rustrade-kucoin`. See `CONTRIBUTING.md` "Adding a new exchange adapter (recipe)".

### Add a new brain (strategy)
Implement `Brain` on your struct. Live + backtest both work without changes.

### Add a supervised service (heartbeat, custom poller, etc.)
Implement `TradingService` from `rustrade-supervisor`. Spawn via `bot.supervisor().spawn_service(...)`.

## Status & history

See `NEXT_STEPS.md` for the original phased build plan (mostly
historical now). Open work tracked in `TODO.md`. The PR arc that built
this framework lives in `fks-full` history (PRs #1–#10).

## Gotchas

- **`rustrade-supervisor` deps are pinned explicitly**, not via `workspace = true`. This is intentional — it lets foreign workspaces consume it as a path dep without mirroring deps into their own `[workspace.dependencies]`. Other crates can stay `workspace = true` until they need cross-workspace consumption or crates.io publishing.
- **`rustrade-kucoin` requires `exchange-apiws`** (currently a path dep to `../../../exchange-apiws/`). When this workspace becomes its own repo, switch to `exchange-apiws = "x.y"` from crates.io.
- **Don't add path deps into `fks-full`-only crates.** This workspace must be standalone before its repo split.
