# Contributing to rustrade

Thanks for considering a contribution. This document captures the
patterns that emerged across the 0.1 framework so anyone adding a new
exchange adapter, brain, or service has a known-good reference.

If something in this document conflicts with what makes sense, the
*pattern* is more important than the *rule*. File an issue.

---

## Repository layout

```
crates/rustrade/
├── Cargo.toml                workspace manifest
├── README.md                 architecture, quick-start, status
├── NEXT_STEPS.md             phased build plan (mostly historical)
├── CONTRIBUTING.md           ← you are here
└── crates/
    ├── rustrade-core/        types, traits, buses (no I/O)
    ├── rustrade-supervisor/  service lifecycle + backoff + chaos tests
    ├── rustrade-risk/        circuit breaker + session PnL + sizer
    ├── rustrade-backtest/    replay engine + sim exchange + metrics
    ├── rustrade/             facade — Bot, ExecutionService, logging
    ├── rustrade-kucoin/      KuCoin adapter (built on exchange-apiws)
    └── rustrade-notify/      Discord webhooks + heartbeat service
└── examples/
    ├── noop-bot/             smallest end-to-end (NoopBrain + MockExchange)
    ├── kucoin-stub-bot/      real adapter, stub brain
    ├── kucoin-v2/            production-shaped binary
    └── backtest-demo/        EMA-cross over synthetic candles
```

---

## Design principles

These have held through every PR. Treat them as constraints, not
suggestions.

### 1. `Brain` is the only abstraction that matters

Everything else (`Supervisor`, `ExchangeClient`, `Risk*`, `ExecutionService`,
`BacktestEngine`) is plumbing. If the `Brain` trait has to grow to
accommodate something, push back twice before adding the field —
strategy variation belongs *inside* the brain implementation, not in
the trait.

### 2. Live and backtest share one code path

`Bot::run_until_shutdown` and `BacktestEngine::run` both call
`brain.on_event(&event, &position)` with the same types. If you find
yourself adding a `cfg(backtest)` branch in a brain, stop — figure
out why the abstraction failed.

### 3. Trait surfaces stay narrow

`ExchangeClient` is six methods. `Brain` is four. `Notifier` is one.
If a new method "could fit" but only one adapter would use it, it
goes on the concrete adapter type, not the trait. Adapters expose
escape-hatch accessors (`KucoinExchangeAdapter::client()`) for the
exchange-specific surface.

### 4. Risk gates run before the network

`ExecutionService` checks `CircuitBreaker.is_tripped()` and
`SessionPnl.is_session_halted()` *before* any `place_order()`. If you
add a new risk primitive, slot it in at the same point. Never put a
risk check inside the exchange adapter — adapters are dumb pipes.

### 5. The framework deletes code

Every line that lives in `rustrade-*` is a line a future bot doesn't
have to write. The kucoin v2 port removed ~3000 lines of v1 service
plumbing for this reason. If a PR adds 200 lines but a future bot
saves 2000, ship it. If it adds 200 lines and only kucoin uses it,
that's a kucoin-private addition, not a framework change.

---

## Adding a new exchange adapter (recipe)

Pattern: `rustrade-kucoin`. ~270 lines including tests + docs.

### 1. Pick a publishable client

You need a Rust crate that already speaks the exchange's API
(`exchange-apiws` for KuCoin, `bybit-rs` or similar for Bybit, …).
The adapter wraps that client; it doesn't re-implement REST.

### 2. Scaffold the crate

```
crates/rustrade-<exchange>/
├── Cargo.toml
└── src/
    └── lib.rs
```

`Cargo.toml` should:
- Depend on `rustrade-core` and the underlying client crate.
- Export `keywords`, `categories`, a `description`.
- Have its own per-crate publish flag (likely `false` until ready).

### 3. Implement `ExchangeClient`

Six methods, all `async`:

```rust
async fn place_order(&self, order: &Order) -> Result<String>
async fn cancel_all(&self, symbol: &str) -> Result<usize>
async fn close_position(&self, symbol: &str, position: &Position) -> Result<String>
async fn get_position(&self, symbol: &str) -> Result<Position>
async fn get_balance(&self, currency: &str) -> Result<f64>
async fn contract_value(&self, symbol: &str) -> Result<f64>  // override only for futures
fn name(&self) -> &str
```

The default `contract_value` is `1.0`, correct for spot and
base-quoted futures. Override only when one contract represents a
fractional base-asset unit (e.g. KuCoin `XBTUSDTM` = 0.001 BTC).

### 4. Convert types at the boundary

The framework has its own `Side`, `OrderKind`, `Volume`, `Price`. The
exchange client has its own. Do the conversion in tiny private
functions:

```rust
fn to_kc_side(s: rustrade_core::Side) -> exchange_apiws::Side {
    match s {
        rustrade_core::Side::Buy => exchange_apiws::Side::Buy,
        rustrade_core::Side::Sell => exchange_apiws::Side::Sell,
    }
}
```

Avoid `From`/`Into` — both crates are external to your adapter, so
you can't add trait impls to either side.

### 5. Decide where leverage lives

Per-adapter at construction (`KucoinExchangeAdapter::new(client, leverage: u32)`)
covers 95% of strategies. Per-order leverage requires the framework's
`Order` type to grow a field, which it deliberately doesn't. Build a
second adapter instance with different leverage if you need both at once.

### 6. Add a contract-value table for futures

```rust
pub fn contract_value_for(symbol: &str) -> f64 {
    match symbol {
        "XBTUSDTM" => 0.001,
        "ETHUSDTM" => 0.01,
        // …
        _ => {
            tracing::warn!(symbol, "unknown contract — using 1.0");
            1.0
        }
    }
}
```

The `tracing::warn!` is important — it surfaces missing entries in
dev rather than silently producing wrong sizes.

### 7. Tests

Write unit tests for:
- Side / OrderKind conversion (compile-time + runtime correctness)
- Known contract values
- Unknown-symbol fallback

Don't write tests that hit the network — that's an integration
concern, not a unit concern.

### 8. Add an example

Drop a `examples/<exchange>-stub-bot/` that constructs the adapter
and runs `Bot` for ~1 second with a `StubBrain` (always `Hold`). This
proves the wiring without placing real orders.

---

## Adding a new brain

Pattern: `crates/rustrade/examples/kucoin-v2/src/brain.rs`. The brain
is whatever you want it to be — neuromorphic, ML, rule-based, ensemble.
The framework only insists on the trait.

### Trait

```rust
#[async_trait]
pub trait Brain: Send + Sync + 'static {
    fn name(&self) -> &str;
    async fn on_event(&self, event: &MarketDataEvent, position: &Position) -> Result<Decision>;
    async fn on_fill(&self, _fill: &Fill) -> Result<()> { Ok(()) }
    async fn on_position_change(&self, _symbol: &str, _position: &Position) -> Result<()> { Ok(()) }
    async fn health(&self) -> BrainHealth { BrainHealth::ok() }
}
```

`on_event` is the only method you must implement.

### Mutable state

`on_event` takes `&self`, so all mutable state goes through interior
mutability. The kucoin-v2 SAR brain uses `parking_lot::Mutex<IndicatorStack>`
for a few hundred lines of state and per-tick updates with no contention
overhead. Don't reach for `tokio::sync::Mutex` unless the lock spans
an `await` point — `parking_lot` is faster for synchronous critical
sections.

### Decision construction

Build decisions through the helpers:

```rust
Decision::buy(0.85)
    .with_size_hint(SizeHint::NotionalUsd(2_500.0))
    .with_stop(Price(stop_price))
    .with_take_profit(Price(tp_price))
```

`SizeHint::NotionalUsd` translates to contracts via the exchange
adapter's `contract_value`. `SizeHint::Quantity` is for brains that
already know contracts. `SizeHint::MarginFraction` isn't yet
supported by the framework — it's logged and skipped.

### Health

Override `health()` to return useful diagnostics. The supervisor's
`/health` endpoint surfaces this.

```rust
async fn health(&self) -> BrainHealth {
    let stack = self.indicators.lock();
    BrainHealth {
        healthy: stack.ind.atr.is_some(),  // ATR readiness == warmed up
        events_processed: self.events_processed.load(Ordering::Relaxed),
        non_hold_decisions: self.non_hold_decisions.load(Ordering::Relaxed),
        details: serde_json::json!({
            "last_candle_ts_ms": stack.last_candle_ts_ms,
            "bars_since_entry": stack.bars_since_entry,
        }),
    }
}
```

---

## Adding a new TradingService

`TradingService` is anything the supervisor should manage with
backoff + restart + graceful shutdown. Examples in the tree:

- `ExecutionService` (rustrade) — drives a brain
- `KucoinCandlePoller` (kucoin-v2) — REST polling → bus
- `WebhookHeartbeatService` (rustrade-notify) — periodic ping

### Trait

```rust
#[async_trait]
pub trait TradingService: Send + Sync + 'static {
    fn name(&self) -> &str;
    fn restart_policy(&self) -> RestartPolicy { RestartPolicy::OnFailure }
    async fn run(&self, cancel: CancellationToken) -> anyhow::Result<()>;
}
```

### Cancellation contract

`run` MUST select on `cancel.cancelled()`. A service that hangs on
shutdown will hold the supervisor open until the drain timeout,
producing a noisy warning log and probably a SIGKILL from the OS.

```rust
loop {
    tokio::select! {
        _ = cancel.cancelled() => return Ok(()),
        _ = ticker.tick() => self.do_work().await?,
    }
}
```

### Restart policy

- `OnFailure` (default) — restart only if `run` returns `Err`. Use
  for brains, pollers, anything that should keep going on errors.
- `Always` — restart even on `Ok(())`. Use for one-shot tasks that
  should immediately re-fire (rare).
- `Never` — single shot. Use for init tasks.

### Errors

`run` returns `anyhow::Result<()>`. The supervisor logs the error
with the service name and applies the restart policy. Make errors
descriptive — they end up in the failure metrics:

```rust
async fn run(&self, cancel: CancellationToken) -> anyhow::Result<()> {
    let conn = self.connect().await
        .with_context(|| format!("connecting to {}", self.endpoint))?;
    // ...
}
```

### Spawning

```rust
bot.supervisor().spawn_service(Box::new(my_service));
// or with a per-service backoff override:
bot.supervisor().spawn_service_with_options(
    Box::new(my_service),
    SpawnOptions::with_backoff(custom_backoff),
);
```

---

## Testing patterns

### Unit tests

Co-located with the source under `#[cfg(test)] mod tests`. Test the
narrow API surface, not internals. Examples:

- `rustrade-risk/src/circuit_breaker.rs` — 4 tests covering trip /
  reset / win-doesn't-untrip / starts-untripped
- `rustrade-backtest/src/sim_exchange.rs` — 3 tests covering fill
  semantics, realised PnL, limit-order rejection

### Async tests

Use `#[tokio::test]`. Avoid `tokio::time::sleep` for timing-sensitive
asserts — use `tokio::time::pause()` + manual `advance(...)` if you
need deterministic time.

### Float comparisons

`assert!((actual - expected).abs() < 1e-6)`, never `assert_eq!` on
floats. Lesson learned the hard way in PR #5.

### Service tests

For `TradingService` impls, drive them with a `CancellationToken`
manually:

```rust
let cancel = CancellationToken::new();
let cancel_clone = cancel.clone();
let handle = tokio::spawn(async move { svc.run(cancel_clone).await });

tokio::time::sleep(Duration::from_millis(50)).await;
cancel.cancel();
handle.await.unwrap().unwrap();
```

The supervisor itself has chaos tests in
`rustrade-supervisor/src/supervisor.rs::tests::test_chaos_mixed_fleet`
that cover restart-on-failure + circuit breaker trips end-to-end.
Mirror that pattern for any new lifecycle behaviour.

---

## Documentation patterns

- Crate-level `//!` doc covers what the crate is, why it exists, and
  what's NOT in it. The "what's NOT" section saves more grief than
  the "what is" section.
- `pub` items get `///` doc on the type. Self-evident fields can hide
  behind `#[allow(missing_docs)]` on the parent struct (see
  `EquityPoint`, `SupervisorMetrics`). The `#![warn(missing_docs)]`
  on the crate keeps the lint loud for new items.
- Code examples in doc comments are `ignore`d unless they actually
  compile. `cargo test --doc` validates the rest.

---

## Workspace + cargo conventions

- Internal crates use `workspace = true` for shared deps.
- External path-deps (across workspaces) need pinned versions —
  `workspace = true` doesn't cross workspace boundaries cleanly.
  This is why `kucoin-v2` lives under `crates/rustrade/examples/`
  rather than at the repo top level.
- `publish = false` everywhere until the standalone-repo + URL
  decisions are made (see `JANUS_EXTRACTION_PLAN.md`).
- Every framework crate runs with `#![warn(missing_docs)]`.

---

## Commit + PR conventions

These developed organically across PRs #1–#9. They aren't enforced
but they help reviewers.

- **Commit body explains the why**, not the what. The diff shows what.
- **PR description has a Test plan checklist** with what was actually
  validated. `cargo test --workspace` is the bare minimum.
- **Drafts mean drafts** — CodeRabbit auto-skips draft reviews. Mark
  ready-for-review when you want a real review.
- **Follow-up work goes in the PR body**, not in TODO comments. The
  doc gets merged with the code; comments rot.

---

## What's NOT documented here

- How to add a new framework crate. Not enough examples yet — wait
  for two more crates to land before extracting the pattern.
- How to publish to crates.io. Gated on the URL/repo decisions in
  `JANUS_EXTRACTION_PLAN.md`.
- How to write a backtest data loader. The MVP defers parquet/CSV;
  the recipe will land alongside the first real loader.
