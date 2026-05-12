# Pre-publish audit (Phase 2 of `SPLIT_PLAN.md`)

> Generated 2026-05-12 from the state of `main` after PR #24.
>
> **What this is:** a per-crate inventory of what's blocking each
> crates.io publish. Each crate is rated **READY**, **NEEDS WORK**, or
> **DO NOT PUBLISH**. Action items are concrete and small.
>
> **What this is NOT:** an execution log. Nothing is published here —
> this is the gating list for the actual publish PR.

---

## TL;DR

| Crate | Status | Blockers |
|---|---|---|
| `indicators-ta` | ✅ READY | none — verify version 0.1.3 isn't already on crates.io under different ownership |
| `exchange-apiws` | ✅ READY | same caveat for version 0.1.10 |
| `rustrade-core` | 🟡 NEEDS WORK | per-crate README + LICENSE |
| `rustrade-supervisor` | 🟡 NEEDS WORK | per-crate README + LICENSE; also add `readme = "README.md"` to Cargo.toml |
| `rustrade-risk` | 🟡 NEEDS WORK | per-crate README + LICENSE; also add `readme = ...` |
| `rustrade-backtest` | 🟡 NEEDS WORK | per-crate README + LICENSE; also add `readme = ...` |
| `rustrade-notify` | 🟡 NEEDS WORK | per-crate README + LICENSE; also add `readme = ...` |
| `rustrade-kucoin` | 🟡 NEEDS WORK | per-crate README + LICENSE; drop `path = ` from exchange-apiws dep before publish |
| `rustrade` (facade) | 🟡 NEEDS WORK | per-crate README + LICENSE; same workspace defaults |
| `spawner` | 🟥 NOT READY | name almost certainly taken on crates.io (consider `fks-spawner`); no license/repository/keywords/categories metadata; edition still 2021 |

**Recommended publish order** (smallest blast radius first):

1. `indicators-ta` (READY — publish first to validate the pipeline)
2. `exchange-apiws` (READY)
3. `rustrade-core` (after README/LICENSE)
4. `rustrade-supervisor`
5. `rustrade-risk`
6. `rustrade-backtest`
7. `rustrade-notify`
8. `rustrade-kucoin` (last among rustrade-*, since it depends on `exchange-apiws` being published)
9. `rustrade` facade (depends on all rustrade-* siblings being published)
10. `spawner` — defer until rename + metadata cleanup

The order matters because each crate's `version = ...` dep references its siblings; siblings must hit crates.io in dependency order.

---

## Per-crate findings

### `indicators-ta` — ✅ READY

```
version       = "0.1.3"
description   = "Technical analysis indicators and market regime detection for algorithmic trading"
license       = "MIT"
repository    = "https://github.com/nuniesmith/indicators-ta"
documentation = "https://docs.rs/indicators-ta"
readme        = "README.md"
keywords      = ["trading", "technical-analysis", "indicators", "finance", "regime"]
categories    = ["algorithms", "mathematics", "science"]
```

- ✅ All metadata fields populated
- ✅ `README.md` and `LICENSE` files present in the crate directory
- ✅ Zero path deps — fully standalone
- ✅ Standalone workspace (`[workspace]` at top of Cargo.toml — fixed in PR #22)
- ⚠️  Version is `0.1.3` — verify it's not already claimed on crates.io by a previous unrelated upload. `cargo search indicators-ta` will tell.

**Action:** none — run `cargo publish --dry-run` from `crates/indicators-ta/` to confirm, then publish.

---

### `exchange-apiws` — ✅ READY

```
version       = "0.1.10"
description   = "Exchange REST and WebSocket clients — spot trading, futures, account management, and live data streams"
license       = "MIT"
repository    = "https://github.com/nuniesmith/exchange-apiws"
documentation = "https://docs.rs/exchange-apiws"
readme        = "README.md"
keywords      = ["kucoin", "crypto", "trading", "websocket", "futures"]
categories    = ["api-bindings", "network-programming", "asynchronous"]
```

- ✅ All metadata fields populated
- ✅ `README.md` and `LICENSE` files present
- ✅ Zero path deps — fully standalone
- ✅ Standalone workspace (fixed in PR #22)
- ⚠️  Version `0.1.10` — same crates.io ownership check as above

**Action:** none — `cargo publish --dry-run` then publish.

---

### `rustrade-core` — 🟡 NEEDS WORK

Inherits from `crates/rustrade/Cargo.toml` `[workspace.package]`:

```
version    = "0.1.0"
license    = "MIT"
repository = "https://github.com/nuniesmith/rustrade"
authors    = ["nuniesmith"]
edition    = "2024"
```

Crate-local metadata:

```
description = "Core types and traits for the rustrade trading bot framework"
readme      = "README.md"
keywords    = ["trading", "crypto", "bot", "framework"]
categories  = ["api-bindings", "asynchronous"]
```

- ✅ All Cargo.toml metadata fields populated
- ❌ `README.md` file at `crates/rustrade/crates/rustrade-core/` is **MISSING**
- ❌ `LICENSE` file at `crates/rustrade/crates/rustrade-core/` is **MISSING**
- ✅ Zero path deps — fully standalone

**Action (4 lines of effort):**

1. Add `crates/rustrade/crates/rustrade-core/README.md` — can be 5 lines: one-paragraph description + `cargo add rustrade-core` + link back to the workspace `crates/rustrade/README.md` for the full architecture.
2. Add `crates/rustrade/crates/rustrade-core/LICENSE` — symlink or copy of the root `LICENSE`.

Same fix applies to **every other `rustrade-*` crate** below.

---

### `rustrade-supervisor` — 🟡 NEEDS WORK

```
description = "Service lifecycle supervisor with backoff and circuit breakers for rustrade"
keywords    = ["supervisor", "tokio", "trading", "lifecycle"]
categories  = ["asynchronous", "concurrency"]
```

- ❌ **No `readme = ...` line in Cargo.toml.** Without it, crates.io won't render the README even if the file exists.
- ❌ Missing per-crate `README.md`
- ❌ Missing per-crate `LICENSE`
- ✅ Deps pinned explicitly (not `workspace = true`) — already cross-workspace-publishable (this was the de-inheritance work earlier in this PR arc)

**Action:** add `readme = "README.md"` to Cargo.toml + create the README + LICENSE files.

---

### `rustrade-risk` — 🟡 NEEDS WORK

```
description = "Generic risk primitives (position sizing, circuit breakers, session PnL) for rustrade trading bots"
keywords    = ["trading", "risk", "bot", "position-sizing"]
categories  = ["algorithms", "finance"]
```

Same gaps as `rustrade-supervisor`: missing `readme` line, missing README + LICENSE files.

---

### `rustrade-backtest` — 🟡 NEEDS WORK

```
description = "Replay engine + simulated exchange for the rustrade trading framework — any Brain that runs live runs in a backtest with zero changes"
keywords    = ["trading", "backtest", "framework", "rustrade", "replay"]
categories  = ["asynchronous", "finance", "science"]
```

Same gaps.

---

### `rustrade-notify` — 🟡 NEEDS WORK

```
description = "Webhook notifications (Discord, Slack, generic HTTP) as supervised TradingServices for the rustrade framework"
keywords    = ["trading", "rustrade", "discord", "webhook", "notifications"]
categories  = ["asynchronous", "web-programming::http-client"]
```

Same gaps.

---

### `rustrade-kucoin` — 🟡 NEEDS WORK

```
description = "rustrade ExchangeClient adapter for KuCoin Futures (built on exchange-apiws)"
keywords    = ["kucoin", "trading", "exchange", "rustrade", "futures"]
categories  = ["api-bindings", "asynchronous", "finance"]
```

Same per-crate README + LICENSE gaps. **Plus one additional blocker:**

- ⚠️  Path-based dep on `exchange-apiws`:

  ```toml
  exchange-apiws = { path = "../../../exchange-apiws", version = "0.1.10" }
  ```

  This works for `cargo publish` (cargo uses `version` when publishing and ignores `path`), but only if `exchange-apiws` 0.1.10 is already on crates.io. **Publish exchange-apiws first.**

---

### `rustrade` (facade) — 🟡 NEEDS WORK

```
description = "Open-source trading bot framework — facade crate that wires core types, supervisor, and risk into a runnable Bot"
keywords    = ["trading", "framework", "bot", "tokio", "supervised"]
categories  = ["asynchronous", "concurrency"]
```

Same per-crate README + LICENSE gaps. The facade depends on `rustrade-core`, `rustrade-supervisor`, `rustrade-risk`, `rustrade-backtest`, `rustrade-notify`, `rustrade-kucoin` — **publish all of those first** so the facade's `version = "0.1.0"` deps can resolve from crates.io.

Note the workspace-level `crates/rustrade/README.md` IS present (the architecture overview added in PR #6). The facade crate's directory `crates/rustrade/crates/rustrade/` is the one that needs its own.

---

### `spawner` — 🟥 NOT READY

```
name        = "spawner"
version     = "0.1.0"
edition     = "2021"
description = "FKS Bot Spawner — Docker container lifecycle manager for isolated bot workloads"
```

Missing **every other** metadata field:

- ❌ `license` — not set in Cargo.toml
- ❌ `repository` — not set
- ❌ `documentation` — not set
- ❌ `readme` — not set in Cargo.toml (README.md file exists)
- ❌ `keywords` — not set
- ❌ `categories` — not set
- ❌ `LICENSE` file at `crates/spawner/` is **missing**
- ❌ `edition = "2021"` (other publishable crates are on `2024`)
- ❌ **`name = "spawner"` is almost certainly taken on crates.io.** A search would confirm; if so, rename to one of:
  - `fks-spawner` (matches the description's "FKS Bot Spawner")
  - `bot-spawner`
  - `docker-bot-spawner`

**Action (substantial):** treat as a separate pre-publish PR. Set `license = "MIT"`, `repository = "https://github.com/nuniesmith/spawner"` (or whatever the eventual repo name is), add keywords + categories, add LICENSE, rename if `spawner` is taken.

**Recommendation:** defer publishing `spawner` to crates.io entirely if it's primarily a Docker-image-shipped service. crates.io makes sense if downstream users want it as a library; less useful for a binary-only deployment.

---

## Workspace-level cleanups

Two cross-cutting cleanups that benefit multiple crates:

### 1. Add `LICENSE` to the `crates/rustrade/` workspace root

There's no `crates/rustrade/LICENSE` today. The root `fks-full/LICENSE` exists but each crate's directory needs its own (or a symlink). Easiest fix: copy `fks-full/LICENSE` into `crates/rustrade/LICENSE` once, then symlink it into each crate subdir (`ln -s ../../LICENSE crates/rustrade-core/LICENSE`, etc.).

Cargo includes the file referenced in `[package].license-file` (or the standard `LICENSE` / `LICENSE.md` / `LICENSE-*` in the crate root) when packaging. Symlinks resolve at package time.

### 2. Add the `readme` line to the `rustrade-*` Cargo.tomls

Only `rustrade-core` has `readme = "README.md"`. The others rely on cargo's default behaviour of including `README.md` if it exists, but **only if the field is set or the workspace `[package]` defaults it**. Adding `readme = "README.md"` explicitly to each `rustrade-*` Cargo.toml is the safe move.

---

## Suggested execution PR

Single PR titled something like `Pre-publish polish: add per-crate README + LICENSE`:

1. Create `crates/rustrade/LICENSE` (copy of root LICENSE).
2. Symlink (or copy) `LICENSE` into each `crates/rustrade/crates/<crate>/` directory.
3. Create a minimal `crates/rustrade/crates/<crate>/README.md` for each: 5–10 lines, one-paragraph blurb + `cargo add` snippet + link back to the workspace README.
4. Add `readme = "README.md"` to each `rustrade-*/Cargo.toml` that's missing it.
5. Run `cargo package --no-verify` per crate to confirm cargo includes the README.
6. (Optional) Run `cargo publish --dry-run` per crate as the final smoke test.

After that PR lands, the actual `cargo publish` execution is a separate PR — one per crate, in the dependency order listed in TL;DR above. Each publish is irreversible (version numbers can't be re-used), so I'd recommend doing it manually rather than scripted, especially for the first few.

---

## Open questions

1. **Should `spawner` publish to crates.io at all?** It's a binary-style service primarily consumed as a Docker image. If yes, decide the renamed package name. If no, drop it from the publish checklist entirely.

2. **`indicators-ta` 0.1.3 and `exchange-apiws` 0.1.10** — were these previously published by you? If yes, just bump to the next patch version (`0.1.4` / `0.1.11`) and continue. If no, verify the names are available before claiming.

3. **`rustrade-kucoin` publish position.** It depends on `exchange-apiws`. The current path dep makes it un-publishable until exchange-apiws is on crates.io. Confirm we publish exchange-apiws first (the TL;DR order has this).

4. **Yank policy.** If a publish goes out with a metadata typo, the standard remedy is to publish a patched version, not yank. Get the metadata right before the first publish.
