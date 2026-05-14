# janus — Claude Code Project Instructions

> **Repo (future):** TBD — `github.com/nuniesmith/janus` and/or
> `github.com/nuniesmith/janus-private`. The split between public siblings
> and private brain IP is mapped out in `JANUS_EXTRACTION_PLAN.md`.
> **Today's path:** lives inside `fks-full` under `crates/janus/`.

## What this is

The Janus ML / neuromorphic trading engine. 28 sub-crates + 8 service
binaries inside a nested workspace. Brain-region modules under
`neuromorphic/` (amygdala, hippocampus, cerebellum, prefrontal, basal
ganglia, thalamus, hypothalamus, visual_cortex) wrap the strategy stack;
service binaries (forward, backward, cns, data, execution, optimizer,
api, registry) bridge to Ruby and the external world.

## Stack

| Layer | Tech |
|-------|------|
| Workspace root | `crates/janus/Cargo.toml` (nested under `fks-full`'s root) |
| Async runtime | Tokio |
| Supervision | `rustrade-supervisor` via cross-workspace path dep (see `bin/janus/`) |
| Data | Postgres (sqlx, offline mode), Redis, QuestDB |
| Wire | gRPC (tonic), HTTP (axum), Arrow / postcard / serde_json |
| ML | tch (PyTorch), ndarray, polars, custom DSP + LTN |

## Build & test commands

```bash
# From inside crates/janus/
cargo check --workspace                    # fast type-check
cargo build -p janus                       # main binary
cargo build -p janus-forward               # one service
cargo test --workspace                     # all tests

# Lint / format
cargo clippy --workspace
cargo fmt --all

# Generate sqlx offline query cache (required before building services
# that talk to Postgres without a live DB)
cargo sqlx prepare --workspace
```

## Repository layout

```
crates/janus/
├── Cargo.toml                # nested workspace root
├── README.md
├── TODO.md
├── JANUS_EXTRACTION_PLAN.md  # where each sub-crate goes post-split
├── bin/
│   ├── janus/                # main binary — uses rustrade-supervisor
│   │   ├── src/main.rs
│   │   └── src/adapter.rs    # ModuleService bridging to TradingService
│   └── backtest-cli/         # CLI tool (deletable per the extraction plan)
├── lib/
│   ├── janus-core/           # types, traits, JanusState, Config
│   └── janus-api/            # HTTP API layer
├── crates/                   # 23+ feature crates (indicators, regime, ml, lob, dsp, …)
├── services/                 # 8 service binaries (forward, backward, data, execution, …)
└── neuromorphic/             # brain-region modules
```

## Code conventions

- **Edition:** Rust 2024
- **Edition:** `edition = "2024"`, `rust-version = "1.94.1"`
- **Error handling:** `anyhow` in binaries, `thiserror` in libraries
- **Lints:** Most crates set workspace-wide clippy levels in the root `Cargo.toml`. Fix warnings before committing.
- **sqlx:** Service crates use `SQLX_OFFLINE=true` in CI. Run `cargo sqlx prepare --workspace` after any SQL change.
- **Internal deps:** Sub-crates declare `janus-X = { path = "..." }` inside the workspace. The workspace root re-exports common deps via `[workspace.dependencies]`.

## Architecture (high level)

```
external feeds      ┌─────────────────┐
   │                │      Ruby       │  Python data service —
   ▼                │  (data + ML)    │  single source of truth
┌──────────────┐    └────────┬────────┘  for market data.
│  exchanges   │             │
│  Massive S3  │             │ HTTP
│  Kraken / …  │             ▼
└──────────────┘    ┌─────────────────┐
                    │   janus-data    │  Pulls bars from Ruby.
                    └────────┬────────┘
                             │ bars
                             ▼
                    ┌─────────────────┐
                    │ janus-forward   │  Generates signals via the
                    │   (strategies + │  neuromorphic brain stack.
                    │  neuromorphic)  │
                    └────────┬────────┘
                             │ signals
                             ▼
                    ┌─────────────────┐
                    │ Ruby execution  │  Manual approval gate.
                    │     gate        │  *Never* auto-executes.
                    └─────────────────┘
```

> ⚠️  **No autonomous execution.** Every signal terminates at a human
> decision point in the Ruby execution gate. `EXECUTION_MODE=paper_trading`
> is the default; flipping to `live` requires explicit operator confirmation.

## Brain-region modules (`neuromorphic/`)

| Module          | Brain region    | Role |
|-----------------|-----------------|------|
| `amygdala`      | fear response   | Circuit breakers, kill switch |
| `hippocampus`   | memory          | Pattern consolidation, replay |
| `cerebellum`    | timing          | Precision coordination |
| `prefrontal`    | decision        | Strategy selection |
| `basal_ganglia` | action          | Reward learning |
| `thalamus`      | routing         | Attention gating |
| `hypothalamus`  | homeostasis     | Resource management |
| `visual_cortex` | vision          | GAF image processing, pattern recognition |

## Common workflows

### Adding a new feature crate
Create `crates/<name>/`, add it to the `members` list, add a workspace dep entry. See existing crates for the pattern.

### Adding a new service
Create `services/<name>/`, register it in the supervisor in `bin/janus/src/main.rs` via `ModuleService`. Restart policy goes in the supervisor config.

### Updating SQL queries
Edit the SQL, then `cargo sqlx prepare --workspace`. Check in the resulting `.sqlx/` cache changes.

## Pre-split gotchas

- **`bin/janus/` uses `rustrade-supervisor` via a cross-workspace path dep**: `path = "../../../rustrade/crates/rustrade-supervisor"`. After the split, replace with `rustrade-supervisor = "x.y"` from crates.io.
- **Tonic version split**: workspace pins `0.14.2` but `apalis` (vendored under `crates/apalis-redis/`) drags in `0.10.2` transitively. Track and resolve when `apalis` ships 1.0.
- **318 `#[allow(dead_code)]` annotations** across the workspace — most are benign serde deserialization fields, but a clean-up pass is in `TODO.md`.
- **`fks-proto` dep**: today via the root `fks-full` workspace (path). After split, becomes a crates.io dep on `fks-proto = "x.y"`.

## Status & history

- The big refactor that built the Janus side of the FKS arc lives in `fks-full` history (the rustrade port + the supervisor consolidation PR #19).
- The deliberate split plan is `JANUS_EXTRACTION_PLAN.md`. Phase 1 sub-tasks 1a + 1d are the cheapest next moves.
- `TODO.md` tracks per-crate work; the big-picture extraction is in the extraction plan.
