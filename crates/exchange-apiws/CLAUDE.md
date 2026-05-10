# exchange-apiws — Claude Code Project Instructions

> **Repo (future):** `github.com/nuniesmith/exchange-apiws`
> **Today's path:** `fks-full/crates/exchange-apiws/`
> **Status:** standalone publishable crate. Will move to its own repo and crates.io.

## What this is

Exchange REST + WebSocket client library. The I/O half that pairs with
`indicators-ta`'s pure-compute half. Today it ships a KuCoin Futures
client; the structure is designed for additional venues (Binance, Bybit,
…) to be added as sibling modules.

Library name: `exchange_apiws` (consumed as `use exchange_apiws::*`).

## Stack

| | |
|--|--|
| Edition | Rust 2024 |
| Async | Tokio |
| HTTP | reqwest |
| WS | tokio-tungstenite |
| Wire | serde / serde_json |

## Build & test

```bash
cargo check
cargo test
cargo clippy -- -D warnings
cargo fmt --check
```

## Code conventions

- **One module per venue.** `kucoin/`, `binance/`, … each with their own `Client`, `Endpoint`, `Credentials`, `MarketData`, `Account` types.
- **`Credentials::new(key, secret, passphrase)`** — passphrase is optional via `Default`. Empty credentials mean "public-only mode" (allowed for market data, panics for account ops).
- **No retries inside the client.** Single attempt with structured errors via `thiserror`. Higher layers (e.g. `rustrade-supervisor`, `rustrade-kucoin`) own retry policy.
- **Test offline.** Use `mockito` / `wiremock` for HTTP, in-memory channels for WS. No live-API tests in `cargo test`.

## Pre-split / pre-publish gotchas

- **No path deps.** Already standalone.
- **Consumers today:** `crates/rustrade/crates/rustrade-kucoin/` and `crates/janus/crates/bybit-client/` (a sibling that should eventually merge here or graduate to its own venue module).
- **README is long (~655 lines)** — it doubles as the API reference for the KuCoin client. Consider splitting into `README.md` (overview) + `docs/KUCOIN.md` (full API) before the repo split so the headline isn't intimidating.

## Future venue modules

Pattern when adding a new exchange:
1. New module under `src/<venue>/` mirroring `src/kucoin/`.
2. New top-level type `<Venue>::new(creds, env) -> Self`.
3. Re-export from `lib.rs`.
4. Tests under `tests/<venue>_<area>.rs`.
