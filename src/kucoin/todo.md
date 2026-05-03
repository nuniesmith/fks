Now I have a thorough picture of the codebase. Let me write up the full review.Here's the full picture. Click any finding to expand the details and fix suggestions.

**The one thing to fix first** is the mutex held across the Discord notify in `private_ws_task` — that's a real lock contention bug that will cause the heartbeat and candle-poll tasks to stall when Discord is slow. The fix is two lines: snapshot what you need from the locked context, drop the guard, then do the async call.

**The five medium findings** are all correctness or maintainability issues with clear fixes:
- Discord flags should be env-configurable (they're already plumbed through, just hardcoded to `true`)
- Heartbeat interval ignores hot-reloaded settings (read it inside the loop)
- No tests for PnL/fee math (the sizing test pattern already exists — copy it)
- Params files without a `score` field silently fail with a misleading error
- `main.rs` at 460 lines is overdue for a task-per-file split

**The five low findings** are polish items — `Position::size()` returning `i32`, the undocumented 1-second sleep, missing pre-shutdown cancel, dead code, and the `BotError::Other` anyhow escape hatch.

The **architecture is genuinely solid** — the phase 1/2/3 lock discipline, the WS+REST hybrid fill confirmation, and the startup reconciliation are all patterns worth keeping as-is.



In the DataMessage::OrderUpdate branch, the context lock guard g is acquired and then discord.notify_order_filled(...).await is called while g is still held. A slow or rate-limited Discord webhook can hold this lock for hundreds of milliseconds, stalling the heartbeat task and the candle-poll task for every symbol that shares this context. This is the most dangerous concurrency bug in the codebase.

// CURRENT (bad): lock held across network I/O
let g = ctx.lock().await;
if is_filled {
    tracing::info!(target: "pnl", ...);  // fine
}
if let Some(d) = &discord && d.notify_on_fill() {
    let _ = d.notify_order_filled(...).await;  // ← network call while locked!
}
drop(g);  // released too late

// FIX: snapshot what you need, drop the lock, then do I/O
let (should_notify, bot_order, bot_fill) = {
    let g = ctx.lock().await;
    // build BotOrder/BotFill from state + order `o`...
    (discord.as_ref().map(|d| d.notify_on_fill()).unwrap_or(false), order, fill)
    // g dropped here
};
if should_notify {
    if let Some(d) = &discord {
        let _ = d.notify_order_filled(&bot_order, &bot_fill, None).await;
    }
}

Fix: extract all needed data from the locked context into a local snapshot, drop the guard immediately, then do the async Discord call outside the lock. Applies to the pnl log emission too — that's cheap, but keeping it inside the lock is an unnecessarily long hold.
Medium severity

The fields discord_notify_signal, discord_notify_fill, and discord_notify_error exist on RuntimeConfig and are threaded all the way through to DiscordNotifier::new(...) — but they're hardcoded to true in from_env(). Operators can't suppress noisy fill notifications without a code change.

// FIX in from_env():
let flag = |key: &str| std::env::var(key)
    .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
    .unwrap_or(true);

Ok(Self {
    // ...
    discord_notify_signal: flag("DISCORD_NOTIFY_SIGNAL"),
    discord_notify_fill:   flag("DISCORD_NOTIFY_FILL"),
    discord_notify_error:  flag("DISCORD_NOTIFY_ERROR"),
})

Fix: read each flag from an env var with true as the default (backwards-compatible). Document the vars in your .env.example.

heartbeat_task reads interval_secs once at startup: let interval_secs = ctx.lock().await.state.settings.heartbeat_interval_sec;. If param_watch_task hot-reloads new settings with a different interval, the heartbeat loop never picks it up. This is inconsistent with the rest of the hot-reload design.

// FIX: read the interval inside the loop from current settings
loop {
    let interval_secs = ctx.lock().await
        .state.settings.heartbeat_interval_sec;
    tokio::time::sleep(Duration::from_secs(interval_secs)).await;
    // ... rest of heartbeat logic
}

The extra lock acquisition per iteration is negligible. This is a one-line change that makes hot-reload fully consistent across all tasks.

sizing.rs has excellent property-based tests. But the highest-risk functions — PnlTracker::record_close, estimate_fee / estimate_fee_one_leg, realised_pnl, should_skip_entry, and the SAR flip fee-accounting logic — have zero test coverage. A subtle sign error in realised_pnl would silently misreport P&L for every trade.

// Example: test the SAR flip double-counts the fee
#[test]
fn sar_flip_charges_round_trip_fee() {
    let cv = 0.001;
    let fee_rate = 0.0006;
    let price = 50_000.0;
    let contracts = 10u32;
    let round_trip = estimate_fee(price, contracts, cv, fee_rate);
    // SAR flip = 2× one-leg
    assert!((round_trip - 2.0 * estimate_fee_one_leg(price, contracts, cv, fee_rate)).abs() < 1e-9);
}

// Example: short position PnL is positive when price falls
#[test]
fn short_pnl_positive_on_price_drop() {
    let state = make_short_state(entry_price: 50_000.0, qty: -10);
    let pnl = realised_pnl(&state, 49_000.0, 0.001);
    assert!(pnl > 0.0, "short should profit when price falls");
}

Add unit tests for all functions in pnl.rs and the fee helpers in strategy.rs. Focus on edge cases: short P&L sign, SAR vs speed-exit fee counting, session halt triggering at exactly the limit.

When a params file has no "score" field, parsed.get("score").and_then(...).unwrap_or(f64::NEG_INFINITY) defaults to negative infinity — which is always below MIN_SCORE = 0.0. The function returns Ok(false) and the caller logs "best params score too low — skipped". A manually crafted params file (e.g. from a grid search tool that doesn't emit a score) will silently be rejected with a misleading message.

// FIX: distinguish "no score field" from "score too low"
let score = parsed.get("score").and_then(serde_json::Value::as_f64);
match score {
    None => {
        warn!(path, "params file has no 'score' field — applying unconditionally");
        // proceed to apply
    }
    Some(s) if s < MIN_SCORE => return Ok(false),
    Some(_) => {}
}

Treat a missing score as "apply unconditionally" (or error, if you want strict validation). Either way the log message should be unambiguous.

main.rs holds startup orchestration, signal handling, 5 task functions, and utility helpers. The run() function has a #[allow(clippy::too_many_lines)] suppression, which is a sign that the Clippy lint is correct. As the bot adds more symbols or task types, this file will become hard to navigate.

// Suggested split:
src/
  main.rs          // main() + run() shell only (~80 lines)
  tasks/
    mod.rs
    candle_poll.rs  // candle_poll_task
    heartbeat.rs    // heartbeat_task
    ws_ticker.rs    // ws_ticker_task
    ws_private.rs   // private_ws_task
    param_watch.rs  // param_watch_task

Each task function is already self-contained — moving them to their own files is a mechanical refactor with zero behaviour change, but pays dividends in readability and git blame clarity.
Low / minor

size() is defined as pub const fn size(self) -> i32 { self.0.abs() }. It always returns a non-negative value but lies about the type. This forces callers to cast: the fee helpers take size: u32 but receive the result of state.position.size() as u32. An i32::abs() on i32::MIN overflows in debug mode.

// FIX:
pub const fn size(self) -> u32 {
    self.0.unsigned_abs()  // safe, no overflow
}

Using unsigned_abs() eliminates the overflow edge case and removes the need for the as u32 casts at call sites.

tokio::time::sleep(std::time::Duration::from_secs(1)).await; is inserted between close and reopen in a SAR flip with a single comment "propagate on the exchange side". The magic value is not configurable and isn't mentioned in any settings struct.

// FIX: name it and make it configurable
const SAR_FLIP_SETTLE_MS: u64 = 1_000;
// ... or read from settings:
tokio::time::sleep(Duration::from_millis(s.sar_flip_settle_ms)).await;

Add a named constant (or a settings field) so the value is findable, documentable, and tunable without a code change.

On SIGTERM/Ctrl-C the shutdown loop calls execute::close_position, but any resting limit order from the last candle cycle is not cancelled first. If close_position uses a reduce-only market order and a resting limit is still active, there could be a brief moment of over-hedging or unexpected fills depending on exchange-side STP settings.

// FIX: cancel all orders first, then close
if let Some((qty, leverage)) = close_args {
    info!(symbol = %sym, "shutdown: cancelling open orders");
    execute::cancel_all_stop_orders(&client, sym).await;
    let _ = execute::cancel_all(&client, sym).await;
    info!(symbol = %sym, "shutdown: closing open position");
    // ... existing close_position call
}

A defensive cancel-all before the market close ensures a clean slate. The calls are already available in the execute module.

fn make_default_settings(sym: &str) -> BotSettings { BotSettings::by_symbol(sym) } is defined at the bottom of main.rs but never called. It's a thin wrapper around a public constructor.
Delete it. If BotSettings::by_symbol is ever inconvenient to call at a new site, inline it there.

BotError has #[error(transparent)] Other(#[from] anyhow::Error), which means any anyhow::Error can be converted into a BotError automatically. This defeats the purpose of a typed error enum — errors that should be a distinct variant can silently fall through to Other. It also makes matching exhaustive arms harder.

// Option A: Remove Other and use anyhow at the call-site boundary only
// (in main.rs and task functions that return anyhow::Result)

// Option B: Keep Other but require an explicit .map_err conversion
// so "slippage" through Other is intentional, not accidental
.map_err(|e| BotError::Other(e.into()))

Reserve anyhow for main.rs and the top-level task functions. Inside the bot and notify modules, use BotError variants exclusively so error paths stay auditable.
Strong patterns worth keeping

The explicit three-phase design — (1) sync indicator math under the mutex, (2) async order execution without the lock, (3) brief write-back under the lock — is exactly right. The comment explaining why sim-mode and live-mode differ in Phase 3 is especially clear. This pattern should be treated as the canonical template for any new tasks added later.

The oneshot-channel design in poll_for_fill — where the WS task fires the signal immediately on a confirmed fill and REST polling is the fallback — is a textbook hybrid approach. The tokio::select! on the WS signal vs. the REST poll timer is clean and correct. The cleanup logic (always removing the map entry regardless of outcome) is also right.

Aborting the entire startup if reconciliation fails is the correct safety decision — trading on stale position state is far worse than not starting at all. The orphaned-stop cancellation at startup is also a thoughtful defensive measure that most bots skip.

The proptest suite for contracts_for_signal covers monotonicity, cap enforcement, and degenerate inputs. This is exactly the right testing approach for financial math — unit tests on known values plus property tests to catch edge cases you didn't think of. Extend this pattern to PnL and fee helpers (see medium finding above).

Now let me read the actual runner source to audit it:Good — I can see the full README and the log patterns tell me everything I need to know about the runner's internals. Let me give you concrete fixes for all three issues across both codebases.

---

**What the logs reveal about the runner:**

- Reconnect backoff: 5 → 10 → 20 → 40 → 80 → 80×5s (10 attempts max), then `WS feed terminated — re-negotiating token delay=30s`
- `WS read error` fires at WARN for every reset — even the single-attempt ones that recover immediately
- April 16's 97 errors included a full exhaustion cycle at 08:28 AND a prolonged HTTP outage from ~13:45–14:32 where all three symbols' candle fetches were failing together — likely a brief KuCoin-side incident

---

**Fix 1 — `exchange-apiws`: reduce log noise from transient resets**

Right now every `Connection reset by peer` hits WARN immediately. Single-attempt recoveries should be DEBUG:

```rust
// In src/ws/runner.rs — wherever the read error arm is handled
Err(e) => {
    attempt += 1;
    if attempt == 1 {
        // Transient reset — KuCoin does this regularly, don't alarm on first hit
        tracing::debug!(exchange = %self.exchange_name(), error = %e, "WS read error (transient)");
    } else {
        tracing::warn!(exchange = %self.exchange_name(), error = %e, attempt, max = config.max_reconnects, "WS read error");
    }
    // ... existing backoff logic
}
```

This alone would have cut Apr 16's log entries from 97 down to maybe 10–15 — just the ones that actually needed multiple retries.

---

**Fix 2 — `exchange-apiws`: make `WsRunnerConfig` fields configurable**

The README shows `WsRunnerConfig::default()` but doesn't expose the fields. Based on the log output (max=10, delays 5/10/20/40/80) you want to at least expose:

```rust
#[derive(Debug, Clone)]
pub struct WsRunnerConfig {
    pub max_reconnects: u32,       // default: 10
    pub base_delay_secs: u64,      // default: 5
    pub max_delay_secs: u64,       // default: 80
    pub ping_interval_secs: u64,   // default: 18
    pub token_renegotiate_delay_secs: u64,  // default: 30 — this is the blind window after exhaustion
}
```

The `token_renegotiate_delay_secs` is the most important one for a trading context. 30s of total blindness after exhaustion is a long time. You could drop it to 5s for futures trading since you're not at risk of hammering the token endpoint.

---

**Fix 3 — bot `main.rs`: one-shot drawdown cap log + daily reset**

This is the noisiest issue — the WARN fires every candle tick (~once/min) for the entire run after the Apr 16 halt:

```rust
// In strategy.rs or wherever the drawdown cap guard lives
// Add a per-symbol atomic flag (or timestamp) to track whether you've already logged

use std::sync::atomic::{AtomicBool, Ordering};

struct SymbolState {
    // ... existing fields
    drawdown_halted: AtomicBool,
    drawdown_halted_at: Option<Instant>,
}

// In the entry check:
if session_net < -self.config.session_loss_limit {
    if !self.state.drawdown_halted.swap(true, Ordering::Relaxed) {
        // Only log ONCE when first tripped
        tracing::warn!(
            symbol = %symbol,
            net_pnl = %format!("{:.4} USDT", session_net),
            limit = %format!("{:.4} USDT", self.config.session_loss_limit),
            "session drawdown cap reached — entry blocked"
        );
        self.state.drawdown_halted_at = Some(Instant::now());
    }
    // Silently skip — no repeated WARN
    return;
}
```

For the daily reset, if your session boundary is midnight UTC:

```rust
// In the candle handler or a daily reset task
fn maybe_reset_session(&mut self, now: DateTime<Utc>) {
    if let Some(last_reset) = self.last_session_reset {
        if now.date_naive() > last_reset.date_naive() {
            self.session_net_pnl = 0.0;
            self.state.drawdown_halted.store(false, Ordering::Relaxed);
            self.state.drawdown_halted_at = None;
            self.last_session_reset = Some(now);
            tracing::info!(symbol = %self.symbol, "session reset — drawdown cap cleared");
        }
    }
}
```

Call this at the top of each candle handler before the entry guard.

---

**Fix 4 — bot: WS health counter for alerting**

Since you're using Redis already, a simple reconnect-rate check you can add in `main.rs` where you handle the `WsDisconnected` / re-negotiation path:

```rust
// Track reconnects per hour in Redis with an expiring key
async fn record_ws_reconnect(redis: &mut redis::aio::Connection, symbol: &str) -> bool {
    let key = format!("sar:{}:ws_reconnects:{}", symbol, 
        chrono::Utc::now().format("%Y%m%d%H"));
    let count: u32 = redis::cmd("INCR").arg(&key).query_async(redis).await.unwrap_or(0);
    redis::cmd("EXPIRE").arg(&key).arg(3600u32).query_async(redis).await.ok();
    
    if count >= 5 {
        tracing::warn!(symbol, reconnects_this_hour = count, 
            "high WS reconnect rate — consider checking network or KuCoin status");
    }
    count >= 5
}
```

This gives you a WARN when any symbol hits 5+ reconnects in a rolling hour window — which would have fired on Apr 16 well before the outage became a full halt.

---

**Summary of what to do, in priority order:**

1. **Bot** — fix the `drawdown cap` WARN to fire once, not every candle tick. This is a 5-minute fix and makes your logs readable immediately.
2. **Bot** — add a midnight UTC session reset that clears `drawdown_halted` and `session_net_pnl`. The SOL halt should have cleared itself at the next day boundary.
3. **`exchange-apiws`** — demote single-attempt WS resets from WARN to DEBUG. Publish as `0.1.9`, update the bot's `Cargo.toml`.
4. **`exchange-apiws`** — expose `token_renegotiate_delay_secs` in `WsRunnerConfig` and drop it to 5s in your bot's config for the futures context.
5. **Bot** — add the hourly reconnect counter to Redis so you get early warning of connectivity trouble before it degrades into a full exhaustion cycle.

The runner's actual reconnect logic looks correct from the logs — it recovered every time, including the nasty Apr 16 outage. The problems are noise and the missing session-boundary reset, not structural failures.

# KuCoin Bot — Apr 21 2026 Patch

Four files to drop into the `kucoin/` crate. All paths are relative to the crate root.

| Downloaded file | Drop in at |
|---|---|
| `settings.rs`            | `src/settings.rs` |
| `circuit_breaker.rs`     | `src/bot/circuit_breaker.rs` |
| `rolling_indicators.rs`  | `src/bot/rolling_indicators.rs` |
| `strategy.rs`            | `src/bot/strategy.rs` |

No other files need changes. `main.rs`, `execute.rs`, `pnl.rs`, `state.rs`, `sizing.rs`, `candle_poller.rs`, and the `notify/` tree are untouched.

## What changed

### 1. New `BotSettings` fields (defaults in `base()`)
- `max_hold_candles: 120` (was `0` — disabled). Forces a time-based exit after 2h on 1-min bars.
- `breaker_window_sec: 14400` (new). Sliding 4-hour lookback for the circuit breaker.
- `breaker_cooldown_sec: 3600` (was `1200`). Longer cooldown after a trip.
- `stc_long_max: 90.0` (new). Block LONG entries when STC ≥ 90 (overbought).
- `stc_short_min: 10.0` (new). Block SHORT entries when STC ≤ 10 (oversold).

All five are in `ParamOverrides` so Optuna can tune them.

### 2. `CircuitBreaker` — sliding-window rewrite
Same public API (`new`, `tick`, `is_tripped`, `record_loss`, `record_win`, `reset`, plus a new `recent_loss_count()` for observability). Internally now counts losses within a rolling window instead of consecutive losses, so losses spaced hours apart still trip the breaker.

### 3. `RollingIndicators::stc_value()`
New getter exposing the current STC reading to the strategy. Returns `None` until the indicator is warm.

### 4. `strategy.rs` — STC extreme-entry gate
- `CandlePlan` gains an `stc: Option<f64>` field.
- `execute_plan` → `execute_sar` → `should_skip_entry` all thread `stc` through.
- New gate after the Elder gate and before the min-hold gate: blocks LONG entries when `STC ≥ stc_long_max` and SHORT entries when `STC ≤ stc_short_min`. Gate logs at INFO (one line per blocked entry — useful for tuning; demote to DEBUG later if noisy).

## Backwards compatibility

- Existing `data/best_params_*.json` files deserialize fine — the new fields appear as `None` in `ParamOverrides` and fall back to `base()` defaults.
- `btc()`, `eth()`, `sol()` symbol presets all use `..Self::base()`, so they inherit the new defaults automatically.
- External public API of `CircuitBreaker` is preserved; no callers in `main.rs` or `strategy.rs` need changes beyond what's in these 4 files.

## Verification before deploy

```
cargo build --release
cargo test --lib   # picks up new circuit_breaker tests + all existing pnl/sizing tests
```

If you want to re-run the STC gate impact analysis on the Apr 20–21 logs, the 22/26 entries that had STC in the extreme zone should all now log `"stc gate: overbought — long entry blocked"` or `"stc gate: oversold — short entry blocked"` instead of entering.

## Rollback

If anything misbehaves, the circuit-breaker change is the only behavior shift that's hard to undo surgically — keep a backup of your old 4 files before overwriting. The STC gate can be disabled at runtime by setting `stc_long_max: 100.0` and `stc_short_min: 0.0` in a hot-reloadable params file.

## First-day monitoring checklist

1. Are STC-gate INFO lines appearing in `bot.log`? If zero, indicators aren't warm or thresholds are too loose.
2. Compare entry count vs prior days. Target: 3–8 entries/symbol/day (down from 4–6 losing entries/symbol/day).
3. Check the max_hold exit fires if any position reaches 120 bars. Look for `"max hold exceeded — closing position at market"`.
4. The circuit breaker should now trip after 4 losses within any rolling 4h window (was: 4 *consecutive* losses). Expect it to trip at least once on a bad day.
