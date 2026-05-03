# JANUS Week 1: Completion Status & Next Steps

**Current Status:** Day 3+ (In Progress)  
**Phase:** Data Foundation  
**Goal:** Unified Market Data Schema & Exchange Adapters  
**Progress:** ~65% Complete

---

## ✅ Completed Tasks

### 1. Unified Market Data Types (janus-core)
- ✅ Created `lib/janus-core/src/market.rs`
- ✅ Implemented `MarketDataEvent` enum with variants:
  - `TradeEvent` - Individual trades with price, volume, side
  - `TickerEvent` - 24h ticker data (high, low, volume, change)
  - `OrderBookEvent` - L2 order book snapshots/deltas
  - `LiquidationEvent` - Forced liquidations (futures/perp)
  - `FundingRateEvent` - Perpetual funding rates
  - `KlineEvent` - OHLCV candlestick data
- ✅ Core types: `Symbol`, `Exchange`, `Side`
- ✅ Exported from `janus-core` for workspace-wide use
- ✅ Added `rust_decimal` dependency for precise price handling

### 2. Exchange Adapters Crate
- ✅ Created `crates/exchanges/` with module structure:
  ```
  crates/exchanges/
  ├── src/
  │   ├── lib.rs
  │   ├── adapters/
  │   │   ├── mod.rs
  │   │   ├── coinbase.rs   (Coinbase Advanced Trade)
  │   │   ├── kraken.rs     (Kraken WebSocket v2)
  │   │   └── okx.rs        (OKX v5 API)
  │   ├── health.rs         (Health monitoring)
  │   ├── normalizer.rs     (Price/volume normalization)
  │   └── types.rs          (Common adapter types)
  ├── Cargo.toml
  └── README.md
  ```

### 3. Coinbase Adapter (adapters/coinbase.rs)
- ✅ Coinbase Advanced Trade WebSocket parser
- ✅ Channels: `ticker`, `ticker_batch`, `market_trades`
- ✅ Parse trades with microsecond timestamps
- ✅ Parse ticker events (24h stats)
- ✅ Subscribe message builder
- ✅ Unit tests for parsing logic

### 4. Kraken Adapter (adapters/kraken.rs)
- ✅ Kraken WebSocket v2 parser
- ✅ Channels: `trade`, `ticker`, `book`
- ✅ XBT → BTC symbol normalization (Kraken quirk)
- ✅ Parse trades and ticker events
- ✅ Quote currency detection (USD, USDT, EUR)
- ✅ Subscribe message builder
- ✅ Unit tests with XBT conversion

### 5. OKX Adapter (adapters/okx.rs)
- ✅ OKX v5 WebSocket parser
- ✅ Channels: `trades`, `tickers`, `funding-rate`, `liquidation-orders`
- ✅ Support for SPOT, FUTURES, SWAP, OPTION instrument types
- ✅ Parse trades, tickers, funding rates, liquidations
- ✅ Subscribe message builder with channel + instId
- ✅ Unit tests for all event types

### 6. Health Monitoring (health.rs)
- ✅ `ExchangeHealth` struct: status, last_message, latency, error_count
- ✅ `HealthChecker` for tracking exchange connection health
- ✅ Methods: `record_message()`, `record_error()`, `is_healthy()`
- ✅ Configurable error threshold for health status
- ✅ Unit tests for health tracking

### 7. Normalization Utilities (normalizer.rs)
- ✅ `PriceNormalizer` for price scaling/rounding
- ✅ `VolumeNormalizer` for volume standardization
- ✅ Per-symbol precision configuration
- ✅ Unit tests for normalization logic

### 8. Common Adapter Types (types.rs)
- ✅ `ConnectionConfig` - WebSocket connection settings
- ✅ `SubscriptionRequest` - Channel subscription abstraction
- ✅ `ChannelType` enum - Unified channel types (trades, ticker, orderbook, etc.)
- ✅ `ReconnectStrategy` - Constant, exponential backoff, linear backoff
- ✅ Unit tests for type conversions

### 9. Workspace Integration
- ✅ Added `janus-exchanges` to workspace `Cargo.toml`
- ✅ Dependencies: `tokio`, `serde`, `serde_json`, `anyhow`, `janus-core`
- ✅ Cargo features: `coinbase`, `kraken`, `okx` (all enabled by default)
- ✅ Fixed compilation errors (f64 Eq trait, string conversions)
- ✅ Removed placeholder references to unimplemented adapters (Binance, Bybit, Kucoin)

### 10. Documentation
- ✅ README for `crates/exchanges`
- ✅ Module-level documentation with examples
- ✅ Inline doc comments for all public APIs

---

## 🔴 Remaining Tasks (High Priority)

### 1. Order Book Parsing (L2) - **3-4 hours**

**Why:** Order book depth is critical for:
- Volume-weighted signals
- Support/resistance detection
- Liquidity analysis
- Market maker detection

**Tasks:**
- [ ] Implement `parse_level2()` in `adapters/coinbase.rs`
  - Parse `level2` channel messages
  - Handle snapshots (full book state)
  - Handle updates (bids/asks deltas)
  - Reconstruct order book state
  
- [ ] Implement `parse_book_data()` in `adapters/kraken.rs`
  - Parse `book` channel (L2 depth)
  - Snapshot format: `[[price, volume, timestamp], ...]`
  - Update format: incremental changes
  
- [ ] Implement `parse_books()` in `adapters/okx.rs`
  - Parse `books` and `books5` channels
  - `books5`: top 5 levels (fast updates)
  - `books`: full depth (400 levels)
  - Checksum validation for integrity

- [ ] Add `OrderBookEvent` to unified schema
  - Fields: `bids: Vec<(price, volume)>`, `asks: Vec<(price, volume)>`
  - `is_snapshot: bool` (vs delta update)
  - `checksum: Option<String>` (for validation)

- [ ] Unit tests for order book parsing
  - Test snapshot parsing
  - Test delta updates
  - Test checksum validation (OKX)

**Files to modify:**
- `crates/exchanges/src/adapters/coinbase.rs` (lines 150-250)
- `crates/exchanges/src/adapters/kraken.rs` (lines 200-300)
- `crates/exchanges/src/adapters/okx.rs` (lines 250-350)
- `lib/janus-core/src/market.rs` (add OrderBook fields)

---

### 2. CNS Integration (Exchange Metrics) - **2-3 hours**

**Why:** Observability is critical for production monitoring and debugging.

**Tasks:**
- [ ] Add exchange metrics to `crates/cns/src/metrics.rs`:
  ```rust
  // Message processing
  pub static EXCHANGE_MESSAGE_TOTAL: LazyLock<IntCounterVec> = ...
  // Labels: exchange, channel, symbol
  
  pub static EXCHANGE_MESSAGE_PARSE_ERRORS: LazyLock<IntCounterVec> = ...
  // Labels: exchange, reason (invalid_json, unknown_type, missing_field)
  
  pub static EXCHANGE_HEALTH_STATUS: LazyLock<GaugeVec> = ...
  // Labels: exchange
  // Value: 1 (healthy), 0 (degraded), -1 (down)
  
  pub static EXCHANGE_LATENCY_SECONDS: LazyLock<HistogramVec> = ...
  // Labels: exchange, channel
  // Buckets: [0.001, 0.01, 0.05, 0.1, 0.5, 1.0]
  ```

- [ ] Create `crates/exchanges/src/cns.rs`:
  ```rust
  pub struct CNSReporter {
      exchange: String,
  }
  
  impl CNSReporter {
      pub fn new(exchange: &str) -> Self { ... }
      
      pub fn record_message(&self, channel: &str, symbol: &str) { ... }
      pub fn record_parse_error(&self, reason: &str) { ... }
      pub fn record_latency(&self, channel: &str, duration: Duration) { ... }
      pub fn update_health(&self, status: ExchangeHealth) { ... }
  }
  ```

- [ ] Wire `HealthChecker` to CNS:
  - Call `CNSReporter::update_health()` on status changes
  - Emit metrics when errors exceed threshold
  
- [ ] Integration with adapters:
  - Add `CNSReporter` to adapter constructors
  - Call `record_message()` on successful parse
  - Call `record_parse_error()` on failures
  - Call `record_latency()` after parsing

- [ ] Unit tests for CNS reporter

**Files to create/modify:**
- `crates/cns/src/metrics.rs` (add exchange metrics)
- `crates/exchanges/src/cns.rs` (new file)
- `crates/exchanges/src/lib.rs` (export CNSReporter)
- `crates/exchanges/src/adapters/*.rs` (integrate reporter)

---

### 3. Integrate with services/data - **4-5 hours**

**Why:** Connect new adapters to production data ingestion pipeline.

**Tasks:**
- [ ] Analyze existing `services/data/src/connector.rs`:
  - Understand `ConnectorManager` architecture
  - Identify where exchange adapters are instantiated
  - Map WebSocket message flow: receive → parse → route
  
- [ ] Refactor `ConnectorManager`:
  - Add adapter selection based on exchange type
  - Use `janus-exchanges` adapters for Coinbase, Kraken, OKX
  - Keep existing adapters for Binance, Bybit, Kucoin (migration later)
  
- [ ] Update `WebSocketActor`:
  - Accept unified `MarketDataEvent` instead of raw JSON
  - Route events to appropriate handlers (trades → trade_handler, etc.)
  - Maintain backward compatibility with old format
  
- [ ] Add feature flags:
  - `Cargo.toml`: `use-new-exchanges = ["janus-exchanges"]`
  - Conditional compilation for adapter selection
  - Allow gradual rollout (test new adapters in parallel)
  
- [ ] Testing:
  - Mock WebSocket server for integration tests
  - Verify Coinbase adapter with live testnet
  - Verify Kraken adapter with live testnet
  - Verify OKX adapter with live testnet
  - Ensure no regressions in existing Binance/Bybit/Kucoin flows

**Files to modify:**
- `services/data/src/connector.rs` (ConnectorManager)
- `services/data/src/websocket.rs` (WebSocketActor)
- `services/data/Cargo.toml` (add janus-exchanges dependency)
- `services/data/tests/integration_test.rs` (add tests)

---

### 4. Testing & Documentation Wrap-up - **3-4 hours**

**Tasks:**
- [ ] Integration tests:
  - Create mock WebSocket server (use `tokio-tungstenite`)
  - Test full flow: connect → subscribe → receive → parse → emit
  - Test reconnection logic (disconnect → exponential backoff → reconnect)
  - Test error handling (invalid JSON, unknown message types)
  
- [ ] Benchmarks (using `criterion`):
  - Parse 10,000 trade messages (measure throughput)
  - Parse 1,000 order book snapshots (large messages)
  - Normalize 100,000 prices (normalization overhead)
  - Target: >50K msg/sec parsing throughput
  
- [ ] Documentation:
  - Update `crates/exchanges/README.md` with order book examples
  - Create `docs/janus/EXCHANGE_MIGRATION.md`:
    - Guide for migrating Binance, Bybit, Kucoin adapters
    - Pattern for adding new exchanges
    - Testing checklist
  - Update `JANUS_12_WEEK_ROADMAP.md` with Week 1 completion status
  
- [ ] Code cleanup:
  - Remove unused imports (fix warnings)
  - Add `#[allow(dead_code)]` for intentionally unused fields
  - Run `cargo fmt --all` and `cargo clippy --workspace`

**Files to create/modify:**
- `crates/exchanges/tests/integration.rs` (new file)
- `crates/exchanges/benches/parse_bench.rs` (new file)
- `docs/janus/EXCHANGE_MIGRATION.md` (new file)
- `crates/exchanges/README.md` (update with order book section)

---

## 📊 Week 1 Progress Tracker

| Task | Estimated | Completed | Remaining | Priority |
|------|-----------|-----------|-----------|----------|
| Unified market types | 2h | ✅ 2h | 0h | - |
| Coinbase adapter | 3h | ✅ 3h | 0h | - |
| Kraken adapter | 3h | ✅ 3h | 0h | - |
| OKX adapter | 4h | ✅ 4h | 0h | - |
| Health & normalizer | 2h | ✅ 2h | 0h | - |
| Types & common | 2h | ✅ 2h | 0h | - |
| Workspace integration | 1h | ✅ 1h | 0h | - |
| Basic documentation | 2h | ✅ 2h | 0h | - |
| **Order book parsing** | 4h | ⏳ 0h | **4h** | 🔴 HIGH |
| **CNS integration** | 3h | ⏳ 0h | **3h** | 🔴 HIGH |
| **services/data integration** | 5h | ⏳ 0h | **5h** | 🔴 HIGH |
| **Testing & docs** | 4h | ⏳ 0h | **4h** | 🟡 MEDIUM |
| **TOTAL** | **35h** | **19h** | **16h** | **46% → 100%** |

---

## 🎯 Immediate Next Steps

### Option A: Finish Order Book Parsing First (Recommended)
Order book data is foundational for many strategies. Completing this first ensures Week 2 can leverage depth data.

```bash
# 1. Implement Coinbase L2 parsing
cd src/janus/crates/exchanges
# Edit: src/adapters/coinbase.rs (add parse_level2)

# 2. Implement Kraken book parsing
# Edit: src/adapters/kraken.rs (add parse_book_data)

# 3. Implement OKX books parsing
# Edit: src/adapters/okx.rs (add parse_books)

# 4. Test
cargo test --package janus-exchanges -- orderbook

# Estimated: 3-4 hours
```

### Option B: CNS Integration (Observability First)
If you prefer observability early, start with CNS metrics to monitor adapter health.

```bash
# 1. Add metrics to CNS
cd src/janus/crates/cns
# Edit: src/metrics.rs (add exchange metrics)

# 2. Create CNSReporter
cd ../exchanges
# Create: src/cns.rs

# 3. Wire to adapters
# Edit: src/adapters/*.rs (add reporter calls)

# 4. Test
cargo test --package janus-exchanges -- cns

# Estimated: 2-3 hours
```

### Option C: Full Integration (End-to-End)
Integrate with `services/data` to see adapters working in production context.

```bash
# 1. Refactor ConnectorManager
cd src/janus/services/data
# Edit: src/connector.rs

# 2. Update WebSocketActor
# Edit: src/websocket.rs

# 3. Integration test
cargo test --package janus-data -- integration

# Estimated: 4-5 hours
```

---

## 🐛 Known Issues & Warnings

### Compilation Warnings (Non-blocking)
```
warning: unused import: `std::sync::Arc`
 --> lib/janus-core/src/state.rs:5:5

warning: fields `channel`, `client_id` are never read
 --> crates/exchanges/src/adapters/coinbase.rs:317:5
```

**Action:** Will be fixed in cleanup phase (Task 4).

### Missing Adapters
Binance, Bybit, Kucoin adapters are referenced in old code but not yet migrated to `crates/exchanges`. They remain in legacy locations.

**Action:** Migration planned for Week 2-3 (non-blocking for Week 1).

---

## 📝 Documentation Status

- ✅ `crates/exchanges/README.md` - Basic overview, usage examples
- ✅ `docs/janus/JANUS_12_WEEK_ROADMAP.md` - Full 12-week plan
- ✅ `docs/janus/JANUS_12_WEEK_QUICKREF.md` - Quick reference
- ✅ `docs/janus/WEEK1_NEXT_STEPS.md` - This document
- ⏳ `docs/janus/EXCHANGE_MIGRATION.md` - To be created (Task 4)
- ⏳ `docs/janus/WEEK1_COMPLETE.md` - To be created after completion

---

## 🚀 Week 2 Preview

Once Week 1 is complete, Week 2 focuses on **News Ingestion & Sentiment Analysis**:

1. Create `services/news` (Rust service)
   - CoinTelegraph, CryptoNews, Reddit/Twitter APIs
   - Real-time news WebSocket feeds
   - News deduplication and storage (PostgreSQL)

2. Create `crates/sentiment` (Rust library)
   - Sentiment scoring (positive/neutral/negative)
   - Entity extraction (coin mentions)
   - Event classification (regulatory, technical, market)
   - LTN integration for logical reasoning

3. CNS metrics for news pipeline
   - `news_articles_ingested_total{source, asset}`
   - `news_sentiment_score{asset}` (gauge)

**Estimated:** 40 hours (Week 2 full-time)

---

## 🔗 Related Documents

- **Roadmap:** `docs/janus/JANUS_12_WEEK_ROADMAP.md`
- **Quick Ref:** `docs/janus/JANUS_12_WEEK_QUICKREF.md`
- **Exchanges README:** `crates/exchanges/README.md`
- **Core Types:** `lib/janus-core/src/market.rs`

---

## ✅ Success Criteria for Week 1 Completion

- [ ] All 6 exchange adapters compile and pass tests (Coinbase, Kraken, OKX + legacy)
- [ ] Order book parsing implemented for all 3 new adapters
- [ ] CNS metrics reporting exchange health and message counts
- [ ] New adapters integrated with `services/data` (feature-flagged)
- [ ] Integration tests pass (mock WebSocket server)
- [ ] Benchmarks show >50K msg/sec parsing throughput
- [ ] Documentation complete (README, migration guide)
- [ ] No compilation errors or blocking warnings

**When all criteria met:** Update `docs/janus/WEEK1_COMPLETE.md` and proceed to Week 2.

---

**Last Updated:** 2025-01-XX (Week 1 Day 3+)  
**Next Review:** After completing order book parsing or CNS integration