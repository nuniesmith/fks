# kucoin (legacy) — scheduled for deletion

> 🪦 **This directory is on its way out.** Listed under "Removal
> candidates" in `SPLIT_PLAN.md`. Don't add new code here.

## Why it exists

The pre-`rustrade` KuCoin Futures bot. It bundled supervisor logic,
position sizing, circuit breaker, SAR strategy, and Discord
notifications into ~3000 lines of hand-rolled infrastructure.

## Why it's leaving

Every piece of it has a better home now:

| Legacy concern in `crates/kucoin/` | Replacement                                      |
|------------------------------------|--------------------------------------------------|
| Supervisor / restart loop          | `rustrade-supervisor` (PR #1 in `fks-full`)      |
| Position sizing / session PnL      | `rustrade-risk`                                  |
| Order execution                    | `rustrade::ExecutionService` + `rustrade-kucoin` |
| KuCoin REST / WS client            | `exchange-apiws`                                 |
| SAR strategy                       | `rustrade/examples/kucoin-v2/src/brain.rs`       |
| Discord heartbeats                 | `rustrade-notify`                                |
| Reference for "how to use rustrade"| `rustrade/examples/kucoin-v2/` (~115-line main.rs vs the 1310 we had here) |

## When it leaves

Phase 1 of `SPLIT_PLAN.md`. After the in-flight reorganization commits
land and the workspace is verified clean, this directory and its
docker-compose / nginx references (none today — already not wired into
the runtime) get removed in a focused PR.
