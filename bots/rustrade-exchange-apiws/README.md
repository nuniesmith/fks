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

## Real fills — `KucoinFillSource`

A `rustrade::FillSource` that streams the exchange's actual executions into the
bot, replacing paper-simulated fills. Because the framework gates bracket/OCO
handling on a fill source being present, wiring it also turns on real SL/TP
management.

```rust
use rustrade_exchange_apiws::KucoinFillSource;
use exchange_apiws::KucoinEnv;
use std::sync::Arc;

let fills = Arc::new(KucoinFillSource::connect(
    adapter.client().clone(),
    KucoinEnv::LiveFutures,
    vec!["XBTUSDTM".into(), "ETHUSDTM".into()],
    std::time::Duration::from_secs(5),
));
// bot.with_fill_source(fills)
```

It uses the private `tradeOrders` WS as a **low-latency trigger** and reads the
authoritative price/size/fee from `/recentFills` (exchange-apiws's `OrderUpdate`
omits the per-execution match price — and reports `0.0` for market orders), so
fills carry true prices. Deduped by trade id; baselined at startup so history
isn't replayed; degrades to poll-only if the private WS token is unavailable.

## Status & roadmap

- ✅ KuCoin Futures `ExchangeClient` (orders, brackets, positions, balance, order tracking).
- ✅ `KucoinFillSource` — real fills via the private `tradeOrders` WS trigger + `/recentFills`.
- ⏳ Expose per-execution `matchPrice`/`matchSize` on exchange-apiws's `OrderUpdate`
  so the WS feed can carry fill prices directly (drop the `/recentFills` hydration).
- ⏳ Kraken **spot** adapter over `exchange-apiws`'s `KrakenPrivateClient` (spot
  semantics: long-only, `position` = base-asset balance, `AssetClass::CryptoSpot`).
  KuCoin (futures) + Kraken (spot) are the target venues; Bybit is unused (N/A in Canada).

## License

MIT OR Apache-2.0.
