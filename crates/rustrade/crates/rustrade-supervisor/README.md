# rustrade-supervisor

Structured service lifecycle management for the
[rustrade](https://github.com/nuniesmith/rustrade) trading-bot framework
(also usable standalone).

Every long-running task in a trading bot — WS feeds, candle pollers, the
brain itself, heartbeats — implements [`TradingService`] and is spawned
through a [`Supervisor`] that handles:

- Graceful shutdown via `CancellationToken` propagation
- Exponential-backoff restart with full jitter
- Per-service circuit breaker (stop retrying after N failures in window T)
- Service lifecycle state machine (`Starting → Running → BackingOff → Stopping → Terminated`)
- Atomic metrics for restarts, active services, circuit-breaker trips

```toml
[dependencies]
rustrade-supervisor = "0.1"
```

```rust,no_run
use rustrade_supervisor::{Supervisor, SupervisorConfig, BackoffConfig};
use std::time::Duration;

# async fn run() -> anyhow::Result<()> {
let config = SupervisorConfig::default()
    .with_shutdown_timeout(Duration::from_secs(30))
    .with_default_backoff(
        BackoffConfig::new(Duration::from_millis(100), Duration::from_secs(60))
            .with_cooldown(Duration::from_secs(300))
            .with_circuit_breaker(10, Duration::from_secs(600)),
    );

let supervisor = Supervisor::new(config);
// supervisor.spawn_service(Box::new(my_service));
supervisor.run_until_shutdown().await
# }
```

## Design notes

- Deps are pinned explicitly (not `workspace = true`) so this crate can be
  consumed as a path dep from foreign workspaces without each consumer having
  to mirror every transitive dep.
- The `prometheus` feature is **off** by default — atomic counters in
  `SupervisorMetrics` are the source of truth; downstream binaries opt into
  the Prometheus export if they want it.
- Tested with the chaos suite (`test_chaos_mixed_fleet`, etc.) — restart
  storms, circuit breaker trips, and supervised hangs all covered.

See the [workspace README](https://github.com/nuniesmith/rustrade) for how
this slots into the full framework.

## License

MIT — see `LICENSE`.
