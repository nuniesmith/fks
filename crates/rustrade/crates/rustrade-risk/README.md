# rustrade-risk

Generic risk primitives for the
[rustrade](https://github.com/nuniesmith/rustrade) trading-bot framework.
Nothing here is strategy- or exchange-specific.

Three primitives:

- **`CircuitBreaker`** — sliding-window loss breaker. Trips when N losses
  occur within a rolling window T; stays open for the configured cooldown
  regardless of intervening wins.
- **`SessionPnl`** — realised PnL tracker with optional drawdown cap and
  automatic 00:00 UTC rollover. Classifies trades W/L/B on **net** PnL so
  fee-flipped trades count correctly.
- **`PositionSizer`** — notional-based sizing from `margin × leverage ÷
  (price × contract_value)`, with `max_contracts` cap and bailout-on-zero
  guard for degenerate inputs.

```toml
[dependencies]
rustrade-risk = "0.1"
```

```rust
use rustrade_risk::{CircuitBreaker, CircuitBreakerConfig};
use std::time::Duration;

let mut cb = CircuitBreaker::new(CircuitBreakerConfig {
    loss_limit: 4,
    window_secs: 14_400,
    cooldown_secs: 3_600,
});

cb.record_loss();
cb.record_loss();
assert!(!cb.is_tripped());
```

If you find yourself needing to special-case a particular strategy, the
logic belongs in the `Brain` implementation, not here.

See the [workspace README](https://github.com/nuniesmith/rustrade) for how
this slots into the full framework.

## License

MIT — see `LICENSE`.
