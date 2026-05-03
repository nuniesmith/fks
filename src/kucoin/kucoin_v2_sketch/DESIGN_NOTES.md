# kucoin-v2 — Design Notes

This is a *thought experiment*, not running code. It's the kucoin service
rewritten against the `rustrade-core::Brain` trait sketched in
`/home/claude/rustrade/`. The point is to surface friction in the trait
design *before* the framework is built around it.

## Line-count comparison

| File              | v1                    | v2                       |
|-------------------|-----------------------|--------------------------|
| `main.rs`         | 1239 lines            | ~120 lines               |
| `bot/strategy.rs` | 808 lines             | (lifted into `brain.rs`, ~280 lines) |
| `bot/state.rs`    | 65 lines              | (folded into the Brain) |
| `bot/execute.rs`  | 427 lines             | **deleted** — framework owns this |
| `bot/sizing.rs`   | 250 lines             | **deleted** — `rustrade-risk::PositionSizer` |
| `bot/circuit_breaker.rs` | 200 lines      | **deleted** — `rustrade-risk::CircuitBreaker` |
| `bot/pnl.rs`      | 335 lines             | **deleted** — `rustrade-risk::SessionPnl` |
| `bot/candle_poller.rs` | 120 lines        | **deleted** — framework owns this |
| `notify/discord.rs` | 27000+ chars        | (configured via `BotConfig`, no service code) |
| `notify/redis_store.rs` | 21000+ chars    | (configured via `BotConfig`, no service code) |
| **adapter.rs** (new) | 0                  | ~120 lines — bridges `exchange-apiws` to framework trait |

Net: **~3500 lines of service code → ~520 lines.** The deleted code didn't
disappear — it moved into the framework where it can be reused by every
service. The new ~120 lines in `adapter.rs` is the cost of swapping
exchanges later.

## What the design actually got right

1. **`Brain` taking `&self` works.** `SarBrain::on_event` mutates indicator
   state, but that's fine via `parking_lot::Mutex`. The trait stays
   object-safe and brains can be shared as `Arc<dyn Brain>`. No regrets.

2. **`Decision` separates intent from execution.** The brain says "buy with
   confidence 1.0, suggested stop here, suggested size $2500 notional" —
   the framework decides whether to honour the size hint, whether the
   circuit breaker blocks the entry, what limit-vs-market order to use,
   and how to actually place it. This is the right division.

3. **`size_hint: SizeHint` as an enum** beats a numeric field. The kucoin
   strategy uses `NotionalUsd(margin × leverage)` natively; a future VWAP
   scalper might use `MarginFraction(0.1)`; an ML-based brain might use
   `Quantity(predicted_size)`. One trait, three different sizing models,
   no breaking changes.

4. **`on_position_change` is the right hook for reconciliation.** When the
   exchange-side hard stop fires, the framework's private WS task sees the
   position go to zero and pushes that through `on_position_change`. The
   brain clears `last_signal` and is ready for the next entry. v1 had
   this exact logic scattered across `private_ws_task` and
   `candle_poll_task`'s phase-3 write-back; in v2 it's one function.

## What the design got wrong (or wrong-ish)

### 1. Leverage doesn't fit anywhere clean

`Order` in `rustrade-core` doesn't have a `leverage` field, but KuCoin
Futures requires one on every order placement. In `adapter.rs` I had to
hardcode `let leverage = 5u32; // TODO: thread from BotConfig`. That's a
real design hole.

**Options:**

- (a) Put `leverage: Option<u32>` on `Order`. Spot exchanges ignore it;
  futures exchanges require it.
- (b) Put leverage on the `ExchangeClient` adapter at construction time
  (`KucoinExchangeAdapter::with_leverage(5)`). This means leverage is
  per-adapter, not per-order — fine for most strategies but blocks per-trade
  leverage adjustment.
- (c) Add a `derivatives_metadata: Option<DerivativesMeta>` field on `Order`
  with leverage, margin mode, etc. More extensible but more complex.

I'd pick **(b)** for the v0 trait. Per-order leverage is exotic; per-account
leverage covers 95% of cases. Revisit if a real strategy needs it.

### 2. Stop orders are exchange-side state the framework can't model

The v1 bot places a separate exchange-side stop order after every entry,
and explicitly cancels it before any close. This logic doesn't fit into
`ExchangeClient::place_order` because stops live on a different KuCoin
endpoint (`/api/v1/stopOrders`) with different cancellation semantics.

**Options:**

- (a) Add `place_stop` and `cancel_all_stops` to the trait. Works for KuCoin
  Futures, awkward for spot exchanges that don't separate stop endpoints.
- (b) Make stops *part* of `Order` (`Order { stop: Option<StopAttachment>, ... }`)
  and let the adapter decide how to honour it (separate endpoint on KuCoin,
  bracketed limit on Bybit, etc.). More work for adapter authors.
- (c) Don't model stops in the framework at all — let services attach a
  trailing "place stop" call via the adapter's escape hatch (the
  `kucoin_client()` accessor on the wrapper). Pragmatic; couples the
  service to the specific exchange.

For the v0 trait I'd go with **(c)** — keep the framework trait small.
Adapters can grow exchange-specific surface that services use directly when
needed. This trades framework purity for shipping speed, which is the right
trade for a 0.x crate.

### 3. Where does `BotSettings` live?

In v1, `BotSettings` is a 100-field struct that bundles strategy params
(EMA lengths, ATR multipliers, signal-confirm bars), risk params (loss
limit, cooldown), session params (drawdown cap), and execution params
(`use_market_orders`, fees, leverage, max contracts).

In v2 these have natural homes:

- Strategy params → owned by the brain, no framework concern
- Risk params → `rustrade-risk` config structs
- Session params → `rustrade-risk` `SessionPnlConfig`
- Execution params → `BotConfig` in the facade crate

But the kucoin Optuna tuning loads them all from one JSON file. **The
framework needs a way to let one config file populate multiple subsystems.**
Easy answer: `BotConfig::with_overrides_from_json(path)` on the facade
crate, which dispatches to each subsystem's `apply_overrides`. Each
subsystem owns its own `Overrides` struct.

This isn't a trait-design issue — it's a facade-crate API issue. Worth
noting but not blocking.

### 4. The `NotionalUsd` hint hides the contract-multiplier problem

The brain says `NotionalUsd(2500.0)`. The framework's `PositionSizer`
needs to convert that into contracts:

```text
contracts = floor(notional / (price × contract_value))
```

…where `contract_value` is **exchange-and-symbol-specific** (0.001 BTC for
XBTUSDTM, 0.01 ETH for ETHUSDTM, 1.0 SOL for SOLUSDTM). The framework
needs to know these multipliers somehow.

**Options:**

- (a) `ExchangeClient::contract_value(symbol) -> f64` trait method.
  Adapter implements it from a hardcoded match. Clean; one source of truth.
- (b) `PositionSizer` takes a `Box<dyn Fn(&str) -> f64>` lookup at
  construction. More flexible but easier to misuse.
- (c) Brain returns `SizeHint::Quantity(volume)` and does its own
  contract-value math. Pushes the problem onto every brain author.

**(a)** is the right answer. It also lets the framework's backtest engine
compute realistic PnL without the brain knowing it's being backtested.

## What this exercise actually proved

1. **The `Brain` trait is the right shape.** The SAR strategy, which has
   eight gates and three different exit conditions, fits cleanly into one
   `on_event` method that returns one enum. If this strategy fits, simpler
   strategies definitely fit, and more complex ones (neuromorphic) can use
   the metadata field for whatever extra context they need.

2. **The framework's value is in deletion, not in addition.** The 3000+
   lines that disappear are the part the user shouldn't have to think
   about: WS reconnection, candle polling, fill confirmation, Discord
   wiring, Redis persistence, signal handling, graceful shutdown. Every
   service writing those again from scratch (as v1 does) is the failure
   mode the framework eliminates.

3. **There are 2-3 real design holes (leverage, stop orders, contract
   values) but none of them are showstoppers.** All have viable answers
   for v0 that can be revised in v1 once a second exchange is added.
   That's the right time to relitigate them — not now, not before
   anything is built.

## What I'd do next

Given a fresh session and a few hours:

1. Run `cargo check` on the `rustrade-core` crate I drafted earlier —
   verify it actually compiles.
2. Pick one of the design holes above (I'd start with **contract values
   on `ExchangeClient`**) and update the trait + the kucoin v2 adapter.
3. Lift `janus-core/supervisor/{backoff,lifecycle,mod}.rs` verbatim into
   `rustrade-supervisor` and write the framework's `Bot::run_until_shutdown`
   on top of it. That's the minimum viable framework — once it works for
   kucoin v2, every other service can follow the same pattern.

The kucoin-v2 sketch in this directory is *not* meant to compile as-is.
It references `crate::rolling_indicators` and `crate::settings` which
would need to be lifted from the v1 crate, and the framework crates it
depends on (`rustrade`, `rustrade-core`) are still partly skeletons. Its
purpose is to be a code-shaped argument that the trait design works.
