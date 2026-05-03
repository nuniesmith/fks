# FKS Proto

Centralized Protocol Buffer definitions for all FKS trading system services.

## Overview

This crate provides a single source of truth for gRPC types across the FKS trading system, ensuring consistency between services and eliminating type duplication.

## Available Modules

| Module | Package | Description |
|--------|---------|-------------|
| `common` | `fks.common.v1` | Shared types (TradingSignal, ExecutionResult, Position, etc.) |
| `janus` | `fks.janus.v1` | JANUS orchestration (Forward/Backward services) |
| `forward` | `fks.forward.v1` | Real-time trading engine (Wake state) |
| `execution` | `fks.execution.v1` | Order execution service |
| `data` | `fks.data.v1` | Market data service |
| `cns` | `fks.cns.v1` | Central Nervous System monitoring |
| `neuromorphic` | `fks.neuromorphic.distributed.v1` | Distributed training |
| `signals` | `fks.signals.v1` | Signals bus and inference (ML inference, publish/subscribe live signals) |
| `paper_trading` | `fks.paper_trading.v1` | Paper trading management (session management, execution accounts, routing, metrics) |

## Usage

Add to your `Cargo.toml`:

```toml
[dependencies]
fks-proto = { path = "../fks-proto" }
# Or from workspace
fks-proto = { workspace = true }
```

### Creating Trading Signals

```rust
use fks_proto::common::{TradingSignal, SignalAction, ExecutionMode};

// Using builder pattern
let signal = TradingSignal::buy("BTCUSD", 0.1)
    .with_confidence(0.85)
    .with_strategy("momentum_v1")
    .with_mode(ExecutionMode::Paper)
    .with_stop_loss(42000.0)
    .with_take_profit(48000.0);

// Manual construction
let signal = TradingSignal {
    signal_id: "sig_123".to_string(),
    symbol: "BTCUSD".to_string(),
    action: SignalAction::Buy as i32,
    quantity: 0.1,
    confidence: 0.85,
    mode: ExecutionMode::Live as i32,
    ..Default::default()
};
```

### Connecting to Services

```rust
use fks_proto::execution::execution_service_client::ExecutionServiceClient;
use fks_proto::forward::forward_service_client::ForwardServiceClient;
use fks_proto::data::data_service_client::DataServiceClient;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Connect to execution service
    let mut execution = ExecutionServiceClient::connect("http://localhost:50054").await?;
    
    // Connect to forward service
    let mut forward = ForwardServiceClient::connect("http://localhost:50051").await?;
    
    // Connect to data service
    let mut data = DataServiceClient::connect("http://localhost:50053").await?;
    
    Ok(())
}
```

### Implementing a Service

```rust
use fks_proto::common::{HealthCheckRequest, HealthCheckResponse};
use fks_proto::execution::execution_service_server::{ExecutionService, ExecutionServiceServer};
use tonic::{Request, Response, Status};

#[derive(Default)]
pub struct MyExecutionService;

#[tonic::async_trait]
impl ExecutionService for MyExecutionService {
    async fn health_check(
        &self,
        _request: Request<HealthCheckRequest>,
    ) -> Result<Response<HealthCheckResponse>, Status> {
        Ok(Response::new(HealthCheckResponse::healthy("1.0.0")))
    }
    
    // ... implement other methods
}

// In your server setup
let service = ExecutionServiceServer::new(MyExecutionService::default());
```

### Using the Prelude

For convenience, commonly used types are re-exported in the prelude:

```rust
use fks_proto::prelude::*;

// Now you have access to:
// - TradingSignal, ExecutionResult, Position, Candle
// - SignalAction, ExecutionMode, ExecutionStatus
// - Service clients and servers
```

## Feature Flags

| Feature | Description |
|---------|-------------|
| `serde` | Enable serde serialization/deserialization for proto types |

```toml
[dependencies]
fks-proto = { workspace = true, features = ["serde"] }
```

## Proto File Structure

All proto files are located in the centralized `proto/` directory at the repository root:

```
fks/proto/
├── buf.yaml                    # Buf configuration
├── buf.gen.yaml               # Code generation config
└── fks/
    ├── common/v1/
    │   └── common.proto       # Shared types
    ├── janus/v1/
    │   └── janus.proto        # JANUS orchestration
    ├── forward/v1/
    │   └── forward.proto      # Forward service
    ├── execution/v1/
    │   └── execution.proto    # Execution service
    ├── data/v1/
    │   └── data.proto         # Data service
    ├── cns/v1/
    │   └── cns.proto          # CNS service
    └── neuromorphic/
        └── distributed/v1/
            └── distributed.proto  # Distributed training
```

## Regenerating Proto Code

Proto code is automatically regenerated during `cargo build`. To manually trigger:

```bash
# From the fks-proto directory
cargo build

# Or to clean and rebuild
cargo clean && cargo build
```

## Common Types Reference

### TradingSignal

The core signal type used to communicate trading decisions:

```rust
pub struct TradingSignal {
    pub signal_id: String,        // Unique identifier (UUID)
    pub symbol: String,           // Trading pair (e.g., "BTCUSD")
    pub action: i32,              // SignalAction enum
    pub quantity: f64,            // Trade quantity
    pub price_limit: f64,         // Limit price (0 = market)
    pub stop_loss: f64,           // Stop loss price
    pub take_profit: f64,         // Take profit price
    pub timestamp: i64,           // Unix ms timestamp
    pub strategy_id: String,      // Strategy that generated signal
    pub confidence: f64,          // Confidence score (0.0-1.0)
    pub max_slippage: f64,        // Max acceptable slippage
    pub expiry_timestamp: i64,    // Signal expiry (0 = no expiry)
    pub mode: i32,                // ExecutionMode enum
    pub exchange: String,         // Target exchange
    pub metadata: HashMap<String, String>,  // Additional metadata
}
```

### ExecutionResult

Result of executing a trading signal:

```rust
pub struct ExecutionResult {
    pub signal_id: String,        // Reference to original signal
    pub status: i32,              // ExecutionStatus enum
    pub message: String,          // Status message
    pub order_id: String,         // Exchange order ID
    pub internal_order_id: String,// Internal tracking ID
    pub executed_price: f64,      // Actual execution price
    pub executed_quantity: f64,   // Actual quantity filled
    pub execution_timestamp: i64, // When executed
    pub error_code: String,       // Error code (if failed)
    pub error_details: String,    // Error details
    pub fee: f64,                 // Fees paid
    pub fee_currency: String,     // Fee currency
    pub slippage: f64,            // Actual slippage %
}
```

### Key Enums

```rust
// Signal actions
enum SignalAction {
    Unspecified = 0,
    Buy = 1,
    Sell = 2,
    Close = 3,
    CloseLong = 4,
    CloseShort = 5,
}

// Execution modes
enum ExecutionMode {
    Unspecified = 0,
    Simulated = 1,  // Backtesting
    Paper = 2,      // Paper trading
    Live = 3,       // Real trading
}

// Execution status
enum ExecutionStatus {
    Unspecified = 0,
    Pending = 1,
    Accepted = 2,
    Rejected = 3,
    PartiallyFilled = 4,
    Filled = 5,
    Cancelled = 6,
    Failed = 7,
    Expired = 8,
}
```

## Service Ports (Default)

| Service | gRPC Port | Description |
|---------|-----------|-------------|
| Forward | 50051 | Real-time trading engine |
| Backward | 50052 | Memory consolidation |
| Data | 50053 | Market data |
| Execution | 50054 | Order execution |
| CNS | 50055 | Health monitoring |

## Contributing

When adding new proto definitions:

1. Add the `.proto` file to the appropriate directory under `proto/fks/`
2. Update `build.rs` to include the new file
3. Add the module to `lib.rs`
4. Update this README with the new module documentation

## License

MIT License - see repository root for details.