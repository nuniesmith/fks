# rustrade-exchange-apiws

A [`rustrade`](https://crates.io/crates/rustrade-framework) `ExchangeClient`
backed by [`exchange-apiws`](https://crates.io/crates/exchange-apiws)'s signed
**KuCoin Futures** REST surface.

The framework speaks `Order` / `Position` / `Capability`; `exchange-apiws`
speaks KuCoin's signed HTTP API. This crate is the adapter between them — the
first thing in the FKS bots that turns a framework `Order` into a **real**
order on a real exchange. Point it at sandbox credentials and the exact same
code path paper-trades.

It is **Track 1** of
[`docs/MULTI_ASSET_BRAIN_ROADMAP.md`](../../docs/MULTI_ASSET_BRAIN_ROADMAP.md):
until now every bot under `bots/` traded against `MockExchange`, so nothing
actually executed through the framework.

## Mapping

| framework call | KuCoin (via exchange-apiws) |
|---|---|
| `place_order(Order)` plain | `place_order` (market / limit / IOC / FOK) |
| `place_order(Order)` with `stop` + `reduce_only` | `place_stop_order` — a bracket leg |
| `place_order(Order)` with `stop`, not reduce-only | `place_order` (entry) **+** a reduce-only `place_stop_order` (protection) |
| `close_position` | `close_position` (market, signed qty) |
| `get_position` / `get_balance` | `get_position` / `get_balance` |
| `cancel_all` | `cancel_all_orders` + `cancel_all_stop_orders` |
| `get_open_orders` / `cancel_order` | `get_open_orders` / `cancel_order` |
| `contract_value` | cached `get_contract().multiplier` |

Stop-trigger direction (`"up"` / `"down"`) is derived purely from the closing
side and stop kind — a stop-loss sits the correct side of the market and a
take-profit the other — so no mark-price lookup is needed to place a bracket.

## Capabilities (advertised truthfully)

| capability | supported | why |
|---|---|---|
| `StopOrders` | ✅ | `place_stop_order` |
| `ReduceOnly` | ✅ | `reduce_only` order field |
| `Ioc` / `Fok` | ✅ | `TimeInForce::IOC` / `FOK` |
| `OrderTracking` | ✅ | `get_open_orders` + `cancel_order` |
| `PostOnly` | ❌ | the `place_order` surface exposes no post-only flag |
| `PublicFeed` / `PrivateFeed` | ❌ | trading-only; a bot wires its own feeds |

## Usage

```rust
use rustrade_exchange_apiws::KucoinExchangeAdapter;
use std::sync::Arc;

// KC_KEY / KC_SECRET / KC_PASSPHRASE from the environment, 5× leverage,
// pre-fetching contract multipliers for the symbols we'll trade.
let exchange = Arc::new(
    KucoinExchangeAdapter::from_env(5, &["XBTUSDTM", "ETHUSDTM"]).await?
);

// `exchange` is a `dyn ExchangeClient` — hand it to `Bot::new(config, exchange, brains)`.
```

For tests or hard-coded multipliers, build it without touching the network:

```rust
use rustrade_exchange_apiws::KucoinExchangeAdapter;
use exchange_apiws::{Credentials, KuCoinClient, KucoinEnv};

let client = KuCoinClient::new(Credentials::from_env()?, KucoinEnv::LiveFutures)?;
let exchange = KucoinExchangeAdapter::new(client, 5)
    .with_contract_value("XBTUSDTM", 0.001);
```

## Safety

Placing orders through this adapter is **live trading** when pointed at live
credentials. The FKS stack defaults to paper everywhere for a reason — see the
"no autonomous execution" principle in the root `CLAUDE.md`. The `crypto-demo`
bot keeps `MockExchange` as its default and only constructs this adapter behind
an explicit `DEMO_EXCHANGE=kucoin` opt-in.

## Status & roadmap

- ✅ KuCoin Futures `ExchangeClient` (orders, brackets, positions, balance, order tracking).
- ⏳ `MarketSource` / `FillSource` over the KuCoin private WS feed (so the same
  adapter can advertise `PrivateFeed` and route real fills) — see the bot TODO.
- ⏳ Bybit / other-exchange variants over `exchange-apiws`'s `BybitPrivateClient`.

## License

MIT OR Apache-2.0.
