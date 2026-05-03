# Service Consolidation Plan: Merging Execution into Janus

**Project JANUS - Architecture Simplification**  
**Goal**: Single Rust binary for all production services  
**Status**: Planning Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture](#current-architecture)
3. [Target Architecture](#target-architecture)
4. [Migration Strategy](#migration-strategy)
5. [Implementation Steps](#implementation-steps)
6. [Code Structure](#code-structure)
7. [Performance Impact](#performance-impact)
8. [Rollback Plan](#rollback-plan)

---

## Executive Summary

### Current Problem

Project JANUS currently runs as **multiple separate services**:
- `janus` - Main trading intelligence (Python + Rust)
- `execution-service` - Order execution (Rust)
- Communication overhead via Redis/ZeroMQ
- Deployment complexity (multiple containers)

### Proposed Solution

**Consolidate into a single Rust binary** that contains:
- Data ingestion & processing
- Feature engineering (DSP, DiffGAF)
- Intelligence (LTN, RL)
- Risk & compliance (Sheriff)
- Order execution
- Persistence

### Benefits

| Benefit | Impact |
|---------|--------|
| **Latency** | Eliminate inter-service communication (Redis overhead) |
| **Memory** | Shared state, no serialization between processes |
| **Deployment** | Single container, simpler ops |
| **Debugging** | Single process, easier to trace |
| **Type Safety** | No protobuf marshalling errors |

### Risks

- ⚠️ Larger binary size (acceptable trade-off)
- ⚠️ Longer compile times (use incremental builds)
- ⚠️ Less flexible scaling (not needed for solo dev)

---

## Current Architecture

### Service Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│                     janus (Main Service)                     │
│  Port: 50051 (gRPC)                                          │
│  - Forward service (real-time inference)                     │
│  - Backward service (training/memory consolidation)          │
│  - CNS service (neuro-symbolic reasoning)                    │
│  - Data service (ingestion)                                  │
└─────────────────────────────────────────────────────────────┘
                            ▼ Redis/gRPC
┌─────────────────────────────────────────────────────────────┐
│               execution-service (Rust)                       │
│  Port: 8080 (REST), 50052 (gRPC)                            │
│  - Order management                                          │
│  - Position tracking                                         │
│  - Risk engine                                               │
│  - Exchange connectors (Bybit WebSocket)                     │
└─────────────────────────────────────────────────────────────┘
                            ▼ HTTP/WS
┌─────────────────────────────────────────────────────────────┐
│                    Exchange (Bybit)                          │
└─────────────────────────────────────────────────────────────┘
```

### Communication Overhead

**Current flow for a single trade**:

1. Bybit → execution-service (WebSocket)
2. execution-service → Redis (`market.ticks` channel)
3. janus → Redis (subscribe to ticks)
4. janus → DiffGAF + LTN (inference)
5. janus → Redis (`trading.signals` channel)
6. execution-service → Redis (subscribe to signals)
7. execution-service → Risk check
8. execution-service → Bybit (place order)

**Total latency**: ~5-10ms overhead just for serialization + Redis

---

## Target Architecture

### Unified Janus Binary

```
┌─────────────────────────────────────────────────────────────┐
│                      JANUS (Single Binary)                   │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  Main Event Loop                        │  │
│  │  (Tokio runtime - single process)                      │  │
│  └────────────────────────────────────────────────────────┘  │
│                            │                                  │
│  ┌─────────────┬──────────┼──────────┬──────────────────┐   │
│  │             │           │          │                  │   │
│  ▼             ▼           ▼          ▼                  ▼   │
│ ┌───────┐ ┌───────┐ ┌──────────┐ ┌──────┐ ┌────────────┐   │
│ │ Data  │ │  DSP  │ │   LTN    │ │ Risk │ │ Execution  │   │
│ │Ingest │ │Feature│ │ Neuro-   │ │Sheriff│ │  Engine    │   │
│ │       │ │  Eng  │ │ Symbolic │ │      │ │            │   │
│ └───────┘ └───────┘ └──────────┘ └──────┘ └────────────┘   │
│     │         │           │          │            │          │
│     └─────────┴───────────┴──────────┴────────────┘          │
│                     Shared Memory                             │
│              (No serialization overhead!)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ WebSocket (direct)
                    ┌──────────────┐
                    │    Bybit     │
                    └──────────────┘
```

### New Flow (Consolidated)

1. Bybit → Janus (WebSocket - single hop)
2. Janus internal: Tick → DSP → LTN → Risk → Execution (in-memory)
3. Janus → Bybit (place order)

**Total latency**: <1ms overhead (function calls, no serialization)

---

## Migration Strategy

### Phase 1: Copy Execution Crate (Week 1)

Create new crate under Janus workspace:

```
src/janus/crates/execution/
├── Cargo.toml
├── mod.rs
├── engine.rs          # Order execution engine
├── orders.rs          # Order book management
├── positions.rs       # Position tracking
├── exchange/
│   ├── mod.rs
│   ├── bybit.rs       # Bybit connector
│   └── traits.rs      # Exchange abstraction
└── state.rs           # Execution state machine
```

**Action**: Copy from `src/execution/src/` and adapt imports

### Phase 2: Remove gRPC/Redis Dependencies (Week 1)

**Before** (execution-service):
```rust
// Receives signals via gRPC
#[tonic::async_trait]
impl TradingService for ExecutionService {
    async fn submit_signal(&self, request: Request<Signal>) 
        -> Result<Response<Ack>, Status> {
        // ...
    }
}
```

**After** (janus integrated):
```rust
// Direct function call
pub struct ExecutionEngine {
    orders: OrderBook,
    positions: PositionTracker,
    exchange: BybitConnector,
}

impl ExecutionEngine {
    pub async fn submit_signal(&mut self, signal: TradingSignal) 
        -> Result<OrderId, ExecutionError> {
        // No serialization, direct call
        let order = self.create_order(signal)?;
        self.submit_order(order).await
    }
}
```

### Phase 3: Integrate into Main Loop (Week 2)

```rust
// src/janus/bin/janus/src/main.rs

use janus_core::JanusCore;
use janus_execution::ExecutionEngine;
use janus_risk::RiskEngine;
use janus_ltn::LtnNetwork;
use janus_dsp::DspPipeline;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();
    
    // Load configuration
    let config = load_config()?;
    
    // Initialize all components
    let mut components = JanusComponents::new(&config).await?;
    
    // Main event loop
    loop {
        tokio::select! {
            // Market data from exchange
            Some(tick) = components.exchange.recv_tick() => {
                handle_tick(&mut components, tick).await?;
            }
            
            // Training/sleep cycles
            _ = components.sleep_timer.tick() => {
                handle_sleep_cycle(&mut components).await?;
            }
            
            // Graceful shutdown
            _ = tokio::signal::ctrl_c() => {
                tracing::info!("Shutting down gracefully...");
                components.shutdown().await?;
                break;
            }
        }
    }
    
    Ok(())
}

async fn handle_tick(
    components: &mut JanusComponents,
    tick: MarketTick,
) -> Result<()> {
    // 1. Feature engineering (DSP)
    let features = components.dsp.process_tick(&tick)?;
    
    // 2. Intelligence (LTN)
    let signal = components.ltn.infer(&features)?;
    
    // 3. Risk check (Sheriff)
    if !components.risk.validate_signal(&signal)? {
        return Ok(()); // Vetoed by risk engine
    }
    
    // 4. Execute (direct call - no IPC!)
    let order_id = components.execution.submit_signal(signal).await?;
    
    // 5. Persist to QuestDB
    components.persistence.log_trade(order_id, &tick).await?;
    
    Ok(())
}

struct JanusComponents {
    exchange: BybitConnector,
    dsp: DspPipeline,
    ltn: LtnNetwork<Wgpu>,
    risk: RiskEngine,
    execution: ExecutionEngine,
    persistence: QuestDbWriter,
    sleep_timer: SleepTimer,
}
```

### Phase 4: Remove Old Services (Week 2)

Once validated:

1. Delete `src/execution/` directory
2. Remove `execution-service` from workspace members
3. Remove Redis pub/sub channels
4. Update Docker Compose (single container)

---

## Implementation Steps

### Step 1: Create Execution Crate

```bash
# Create new crate under janus
mkdir -p src/janus/crates/execution
cd src/janus/crates/execution
```

**Cargo.toml**:
```toml
[package]
name = "janus-execution"
version.workspace = true
edition.workspace = true

[dependencies]
# Async
tokio = { workspace = true }
tokio-tungstenite = { workspace = true }
async-trait = { workspace = true }

# Serialization
serde = { workspace = true }
serde_json = { workspace = true }

# Error handling
anyhow = { workspace = true }
thiserror = { workspace = true }

# Logging
tracing = { workspace = true }

# Crypto (for API signing)
hmac = { workspace = true }
sha2 = { workspace = true }
base64 = { workspace = true }

# Time
chrono = { workspace = true }

# Numbers
rust_decimal = { workspace = true }

# Internal crates
janus-risk = { workspace = true }
janus-compliance = { workspace = true }
janus-models = { workspace = true }
janus-questdb-writer = { workspace = true }
```

### Step 2: Port Core Types

**File**: `src/janus/crates/execution/mod.rs`

```rust
//! Execution Engine for Project JANUS
//!
//! Handles order lifecycle, position management, and exchange connectivity.

pub mod engine;
pub mod orders;
pub mod positions;
pub mod exchange;
pub mod state;

// Re-exports
pub use engine::ExecutionEngine;
pub use orders::{Order, OrderType, OrderSide, OrderStatus};
pub use positions::{Position, PositionTracker};
pub use exchange::Exchange;

use thiserror::Error;

#[derive(Error, Debug)]
pub enum ExecutionError {
    #[error("Exchange connection error: {0}")]
    ExchangeError(String),
    
    #[error("Order rejected: {0}")]
    OrderRejected(String),
    
    #[error("Risk check failed: {0}")]
    RiskCheckFailed(String),
    
    #[error("Invalid order parameters: {0}")]
    InvalidOrder(String),
    
    #[error("Position not found: {0}")]
    PositionNotFound(String),
}

pub type Result<T> = std::result::Result<T, ExecutionError>;
```

### Step 3: Implement Engine

**File**: `src/janus/crates/execution/engine.rs`

```rust
use tokio::sync::mpsc;
use std::collections::HashMap;

use crate::{
    orders::{Order, OrderBook, OrderId},
    positions::PositionTracker,
    exchange::{Exchange, ExchangeConnector},
    Result, ExecutionError,
};
use janus_risk::RiskEngine;
use janus_models::TradingSignal;

pub struct ExecutionEngine {
    /// Order book (active orders)
    order_book: OrderBook,
    
    /// Position tracker
    positions: PositionTracker,
    
    /// Risk engine (Sheriff)
    risk_engine: RiskEngine,
    
    /// Exchange connector
    exchange: Box<dyn Exchange>,
    
    /// Event channel for fills/updates
    event_tx: mpsc::UnboundedSender<ExecutionEvent>,
}

impl ExecutionEngine {
    pub fn new(
        risk_engine: RiskEngine,
        exchange: Box<dyn Exchange>,
    ) -> (Self, mpsc::UnboundedReceiver<ExecutionEvent>) {
        let (event_tx, event_rx) = mpsc::unbounded_channel();
        
        let engine = Self {
            order_book: OrderBook::new(),
            positions: PositionTracker::new(),
            risk_engine,
            exchange,
            event_tx,
        };
        
        (engine, event_rx)
    }
    
    /// Submit a trading signal (main entry point)
    pub async fn submit_signal(&mut self, signal: TradingSignal) 
        -> Result<OrderId> {
        // 1. Convert signal to order
        let order = self.signal_to_order(signal)?;
        
        // 2. Risk check (Sheriff veto)
        self.risk_engine.validate_order(&order)
            .map_err(|e| ExecutionError::RiskCheckFailed(e.to_string()))?;
        
        // 3. Submit to exchange
        let order_id = self.exchange.submit_order(order.clone()).await?;
        
        // 4. Track in order book
        self.order_book.add_order(order_id.clone(), order);
        
        // 5. Emit event
        self.event_tx.send(ExecutionEvent::OrderSubmitted { 
            order_id: order_id.clone() 
        }).ok();
        
        Ok(order_id)
    }
    
    /// Handle order fill from exchange
    pub async fn handle_fill(&mut self, fill: OrderFill) -> Result<()> {
        // Update order status
        self.order_book.update_fill(&fill)?;
        
        // Update positions
        self.positions.apply_fill(&fill)?;
        
        // Notify risk engine of position change
        self.risk_engine.update_position(&self.positions.current())?;
        
        // Emit event
        self.event_tx.send(ExecutionEvent::OrderFilled { 
            order_id: fill.order_id,
            price: fill.price,
            quantity: fill.quantity,
        }).ok();
        
        Ok(())
    }
    
    /// Cancel all orders (panic hook)
    pub async fn cancel_all(&mut self) -> Result<()> {
        let order_ids: Vec<_> = self.order_book.active_orders().collect();
        
        for order_id in order_ids {
            self.exchange.cancel_order(order_id).await?;
        }
        
        Ok(())
    }
    
    fn signal_to_order(&self, signal: TradingSignal) -> Result<Order> {
        // Convert LTN signal to exchange order
        // This is where position sizing logic lives
        todo!("Implement signal to order conversion")
    }
}

pub enum ExecutionEvent {
    OrderSubmitted { order_id: OrderId },
    OrderFilled { order_id: OrderId, price: f64, quantity: f64 },
    OrderCancelled { order_id: OrderId },
    OrderRejected { order_id: OrderId, reason: String },
}

pub struct OrderFill {
    pub order_id: OrderId,
    pub price: f64,
    pub quantity: f64,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}
```

### Step 4: Update Main Binary

Add to `src/janus/bin/janus/Cargo.toml`:

```toml
[dependencies]
janus-execution = { path = "../../crates/execution" }
```

### Step 5: Wire Everything Together

**File**: `src/janus/bin/janus/src/main.rs`

```rust
use janus_execution::ExecutionEngine;
use janus_risk::RiskEngine;
use janus_ltn::LtnNetwork;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize all components in a single process
    let (execution_engine, execution_events) = ExecutionEngine::new(
        RiskEngine::new()?,
        Box::new(BybitConnector::new()?),
    );
    
    // Now everything runs in the same process!
    // No more gRPC, no more Redis, just function calls
    
    Ok(())
}
```

---

## Code Structure

### Final Directory Layout

```
src/janus/
├── bin/
│   └── janus/                    # Single binary entry point
│       ├── Cargo.toml
│       └── src/
│           └── main.rs           # Main event loop
├── crates/
│   ├── execution/                # NEW: Merged from src/execution
│   │   ├── engine.rs
│   │   ├── orders.rs
│   │   ├── positions.rs
│   │   └── exchange/
│   ├── ltn/                      # Logic Tensor Networks
│   ├── dsp/                      # Feature engineering
│   ├── risk/                     # Risk engine (Sheriff)
│   ├── compliance/               # Compliance rules
│   └── ...
└── services/                     # Optional: separate processes
    └── api/                      # REST API (if needed)
```

---

## Performance Impact

### Latency Improvements

| Component | Before | After | Improvement |
|-----------|--------|-------|-------------|
| IPC overhead | 5-10ms | 0µs | **∞** |
| Serialization | 2-3ms | 0µs | **∞** |
| Redis latency | 1-2ms | 0µs | **∞** |
| **Total pipeline** | **18ms** | **150µs** | **120x faster** |

### Memory Improvements

- No duplicate state across services
- No serialization buffers
- Shared data structures
- **Estimated savings**: 200-300MB

---

## Rollback Plan

If consolidation causes issues:

1. **Keep old execution-service** in a branch
2. **Feature flag** to switch between modes
3. **Gradual rollout**: Run both in parallel initially
4. **Monitoring**: Compare latency distributions

```rust
// Feature flag approach
#[cfg(feature = "consolidated")]
fn execute_signal(signal: TradingSignal) {
    // Direct call
    execution_engine.submit_signal(signal).await
}

#[cfg(not(feature = "consolidated"))]
fn execute_signal(signal: TradingSignal) {
    // gRPC call to execution-service
    grpc_client.submit_signal(signal).await
}
```

---

## Timeline

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **1** | Create execution crate, port core types | Compiling crate |
| **2** | Integrate into main binary, test with paper trading | Working prototype |
| **3** | 72-hour soak test, performance validation | Stability report |
| **4** | Remove old services, update deployment | Production ready |

---

## Success Criteria

- ✅ Single binary runs all components
- ✅ Latency < 1ms for full pipeline (internal)
- ✅ Memory usage < 500MB
- ✅ No inter-process communication overhead
- ✅ Simplified deployment (one container)
- ✅ All tests passing

---

## Open Questions

1. **Do we need separate API service?**
   - Option 1: Embed REST API in main binary
   - Option 2: Keep as separate service (read-only)
   - **Recommendation**: Embed for simplicity

2. **How to handle service discovery for clients?**
   - Clients currently connect to multiple services
   - **Solution**: Single gRPC endpoint in main binary

3. **Backwards compatibility with old clients?**
   - **Solution**: Maintain API compatibility, just merge implementation

---

## Next Steps

1. ✅ Review this plan
2. Create `janus-execution` crate
3. Port order management logic
4. Test in isolation
5. Integrate into main binary
6. Run soak test
7. Deploy!

---

**Status**: ✅ Ready to begin

**Estimated completion**: 4 weeks

**Risk level**: LOW (incremental migration)