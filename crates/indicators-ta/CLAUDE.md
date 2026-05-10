# indicators-ta — Claude Code Project Instructions

> **Repo (future):** `github.com/nuniesmith/indicators-ta`
> **Today's path:** `fks-full/crates/indicators-ta/`
> **Status:** standalone publishable crate. Will move to its own repo and crates.io.

## What this is

Technical-analysis indicators in pure Rust. EMA, RSI, MACD, Bollinger,
ATR, CVD, regime classifier, confluence engine, market-structure
tracker, signal-streak counter — everything a trading bot's brain
needs to compute, with no I/O.

Library name: `indicators` (consumed as `use indicators::*`).

## Stack

| | |
|--|--|
| Edition | Rust 2024 |
| Async | None — pure compute |
| Deps | `chrono`, `serde`, minimal numeric crates |
| Lib name | `indicators` (the package name `indicators-ta` is the crates.io headline) |

## Build & test

```bash
cargo check
cargo test
cargo clippy -- -D warnings
cargo fmt --check
cargo doc --open                # API docs
```

## Code conventions

- **No allocations in hot paths.** Indicators are pushed per tick / per bar; allocating on every update kills throughput.
- **Pure compute, no I/O.** This crate doesn't talk to exchanges, files, or network — that's `exchange-apiws`'s job.
- **Stateful types use `&mut self`.** Streaming indicators (EMA, RSI, …) hold state and mutate; one-shot helpers (`compute_signal`) take a slice.
- **Test with `proptest`** where the math has invariants (monotonicity, range bounds).

## Pre-split / pre-publish gotchas

- **No path deps.** This crate is already standalone — verify with `cargo check` from a fresh clone of just this directory.
- **`Cargo.toml` audit before `cargo publish`:**
  - `description`, `license`, `repository`, `keywords`, `categories` populated
  - `readme = "README.md"` resolves
  - `publish = true` (or no `publish` line)
- **Consumers today:** `crates/rustrade/` (some examples) and `crates/janus/crates/indicators/` (which duplicates a lot of this and will be deleted per `JANUS_EXTRACTION_PLAN.md` Phase 1).
