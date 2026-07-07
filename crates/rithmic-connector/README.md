# rithmic-connector

**Foundation / skeleton** of the credential-gated, **READ-ONLY** Rithmic
futures market-data connector for the FKS platform (roadmap **P12**). Design:
[`docs/architecture/RITHMIC_INTEGRATION_SPIKE.md`](../../docs/architecture/RITHMIC_INTEGRATION_SPIKE.md).

> **Doctrine, non-negotiable:** read-only by construction. This crate opens
> **only** the Ticker plant of Rithmic's R|Protocol API. The **order plant
> (execution) is never opened** — there is no order-entry code path here or
> anywhere in this crate. See root `CLAUDE.md` "no autonomous execution" and
> spike §4 "Phase ∞ — Autonomous execution: NEVER".

## What this is (and is not)

This is a **compiling, connectable, gated foundation** — not the full DOM /
positions integration (that is follow-on, spike Phases 2–3).

| Area | Status in this PR |
|------|-------------------|
| `rithmic-rs` dependency (R\|Protocol client) | **Real.** v2.0.0, compiled against its actual API. |
| Config from env + capability gate | **Real + unit-tested.** |
| Connect + login + subscribe **one** instrument (Ticker plant) | **Real** (`live-connect` feature) — untested against a live gateway (needs paid creds). |
| `/health` + `/status` server (:9091) | **Real.** |
| Trade → 1-minute candle bucketing | **Minimal but real** — wires the read path to the sink. |
| Persistence to `candles_futures` (QuestDB ILP) | **STUB** — logs what it would write; see `src/persistence.rs` TODOs. |
| DOM / `book_events_futures`, positions/PnL, order history | **Out of scope** (follow-on). |
| Reconnect/resubscribe loop | **Not yet** — `rithmic-rs` leaves reconnection to the caller; the loop exits on a connection issue. Follow-on. |

## The capability gate

The connector touches Rithmic **only** when it is BOTH enabled AND credentialed.
`RithmicConfig::gate()` returns:

- `Disabled` — `RITHMIC_ENABLED` is false (the **default**). Clean no-op.
- `MissingCredentials { missing }` — enabled but URL/user/password absent. Clean
  no-op, logs exactly which fields are missing (never their values).
- `Ready` — the **only** state that permits a network connection.

The `/health` + `/status` server runs regardless, so the platform always sees
the connector's state (including `read_only: true`, `order_plant_open: false`).

## Environment variables

| Var | Default | Meaning |
|-----|---------|---------|
| `RITHMIC_ENABLED` | `false` | Master runtime gate. Nothing connects unless true. |
| `RITHMIC_ENV` | `demo` | `demo` \| `test` \| `live`. |
| `RITHMIC_GATEWAY_URL` | *(empty)* | Primary `wss://…` gateway (issued by Rithmic after onboarding). |
| `RITHMIC_GATEWAY_ALT_URL` | = primary | Beta/alt URL for the vendor crate's alternating reconnect. |
| `RITHMIC_SYSTEM_NAME` | per-env default | e.g. `Rithmic Test`. Third secret slot. |
| `RITHMIC_USER` | *(empty)* | Login user — **injected by the spawner secret store** (broker slot 1 / `api_key`). |
| `RITHMIC_PASSWORD` | *(empty)* | Login password — spawner slot 2 / `api_secret`. |
| `RITHMIC_APP_NAME` | `fks-rithmic-connector` | App name registered with Rithmic. |
| `RITHMIC_APP_VERSION` | crate version | App version string. |
| `RITHMIC_INSTRUMENT` | `MES` | The single instrument to subscribe. |
| `RITHMIC_EXCHANGE` | `CME` | Its exchange. |
| `RITHMIC_HEALTH_HOST` / `RITHMIC_HEALTH_PORT` | `0.0.0.0` / `9091` | Health/status bind. |

Credentials map onto the existing spawner 3-slot **broker** secret exactly as
crypto bots receive exchange keys: `user → api_key`, `password → api_secret`,
`system → api_passphrase` (spike §2.1).

## Build & test

```bash
cargo fmt
cargo clippy --all-targets --all-features -- -D warnings
cargo test                       # default (live-connect) — compiles rithmic-rs
cargo test --no-default-features # skeleton only (no native-tls toolchain needed)
cargo check --workspace --locked
```

The `live-connect` feature (default on) pulls in `rithmic-rs` + `native-tls`
(openssl). Turn it off to build the gate/config/health skeleton on a minimal
image. Tests **never** open a live Rithmic connection — that requires a paid
account (spike §5.2).

## rithmic-rs viability (the spike's #1 risk, resolved)

`rithmic-rs` **2.0.0** (crates.io, MIT OR Apache-2.0, published 2026-04-21, rust
1.85, not yanked) is **viable and was adopted**. It compiles cleanly and its
real API is a close match to the spike's assumptions: actor-per-plant with
`RithmicTickerPlant` / `HistoryPlant` / `PnlPlant` / `OrderPlant`, a
`RithmicConfig` builder, `connect(&config, ConnectStrategy)` → `get_handle()` →
`login()` / `subscribe(symbol, exchange)`, and a `broadcast::Receiver` of typed
`RithmicMessage` updates (`LastTrade`, `BestBidOffer`, …). One adaptation: the
crate's own `RithmicConfig::from_env` uses a different env scheme
(`RITHMIC_DEMO_USER`, …) than the spawner-injected `RITHMIC_USER`/`RITHMIC_PASSWORD`,
so we build its config via the **builder** instead. Documented, not a blocker.

The residual risk is unchanged from the spike and is **not** about the crate:
**access + conformance** (a paid Rithmic account, dev-kit credentials, and
Rithmic's certification for production URLs) gate everything downstream, on
Rithmic's timeline.
