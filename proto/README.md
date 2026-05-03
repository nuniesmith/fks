# FKS Protocol Buffer Definitions

Centralized Protocol Buffer definitions for all FKS trading system services.

## Overview

This directory contains the single source of truth for all gRPC service definitions and message types used across the FKS trading platform. By centralizing proto files, we ensure consistency between services and eliminate type duplication.

## Directory Structure

```
proto/
├── buf.yaml                           # Buf linting & breaking change config
├── buf.gen.yaml                       # Code generation configuration
├── README.md                          # This file
├── validate.sh                        # Proto validation script
└── fks/
    ├── common/v1/
    │   └── common.proto               # Shared types (TradingSignal, etc.)
    ├── janus/v1/
    │   └── janus.proto                # JANUS orchestration services
    ├── forward/v1/
    │   └── forward.proto              # Forward (Wake) trading service
    ├── execution/v1/
    │   └── execution.proto            # Order execution service
    ├── data/v1/
    │   └── data.proto                 # Market data service
    ├── cns/v1/
    │   └── cns.proto                  # Central Nervous System service
    ├── signals/v1/
    │   └── signals.proto              # Inference & signal bus service
    ├── paper_trading/v1/
    │   └── paper_trading.proto        # Paper trading management service
    └── neuromorphic/
        └── distributed/v1/
            └── distributed.proto      # Distributed training service
```

## Service Reference

| Package | Proto File | Description | gRPC Port |
|---------|------------|-------------|-----------|
| `fks.common.v1` | `common.proto` | Shared types used across all services | N/A |
| `fks.janus.v1` | `janus.proto` | JANUS orchestration (Forward/Backward) | 50051 |
| `fks.forward.v1` | `forward.proto` | Real-time trading engine (Wake state) | 50051 |
| `fks.execution.v1` | `execution.proto` | Order execution service | 50054 |
| `fks.data.v1` | `data.proto` | Market data service | 50053 |
| `fks.cns.v1` | `cns.proto` | Health monitoring & auto-recovery | 50055 |
| `fks.signals.v1` | `signals.proto` | ML inference & signal pub/sub bus | 50056 |
| `fks.paper_trading.v1` | `paper_trading.proto` | Paper trading session management | 50057 |
| `fks.neuromorphic.distributed.v1` | `distributed.proto` | Distributed ML training | 50060 |

## Common Types (fks.common.v1)

The `common.proto` file contains shared types used across multiple services:

### Core Messages

- **TradingSignal** - Trading decision from JANUS strategies
- **ExecutionResult** - Result of executing a trading signal
- **Candle** - OHLCV market data
- **Position** - Open trading position
- **HealthCheckRequest/Response** - Standard health check
- **ErrorResponse** - Standard error format
- **PageRequest/Response** - Pagination helpers
- **TimeRange** - Time range filter

### Key Enums

- **SignalAction** - BUY, SELL, CLOSE, CLOSE_LONG, CLOSE_SHORT
- **ExecutionMode** - SIMULATED, PAPER, LIVE
- **ExecutionStatus** - PENDING, ACCEPTED, REJECTED, FILLED, etc.
- **PositionSide** - FLAT, LONG, SHORT
- **OrderType** - MARKET, LIMIT, STOP_MARKET, STOP_LIMIT, TRAILING_STOP
- **TimeInForce** - GTC, IOC, FOK, GTD
- **Timeframe** - 1M, 5M, 15M, 30M, 1H, 4H, 1D, 1W

## Signals Service (fks.signals.v1)

ML inference and real-time signal pub/sub bus:

- **InferenceService** - Point-in-time ML inference (single, batch, regime detection, module health)
- **SignalBusService** - Publish/subscribe live signals via Redis-backed bus

### Key Messages

- **FeatureVector** - 250+ field ML feature vector (price, trend, volume, ICT, regime, MTF)
- **TradingSignal** - Canonical signal output with confidence, strength, quality scoring
- **SignalEvent** - Streaming signal event wrapper

### Key Enums

- **SignalDirection** - LONG, SHORT, NEUTRAL, EXIT
- **MarketRegime** - TRENDING, VOLATILE, CHOPPY, UNKNOWN
- **SignalQuality** - LOW, MEDIUM, HIGH, ELITE

## Paper Trading Service (fks.paper_trading.v1)

Session-based paper trading management with execution routing and Redis sim state:

- **PaperTradingService** - 22 RPCs covering session lifecycle, account config, routing, metrics, Janus AI, and Redis sim environment

### Key Messages

- **PaperTradingSession** - Top-level session entity (accounts, config, symbols, state)
- **ExecutionAccount** - Exchange account with policy, credentials ref, fee simulation
- **SessionConfig** - Composites JanusAIConfig + RiskConfig + RedisSimConfig
- **JanusAIConfig** - Model selection, confidence thresholds, regime detection, ensemble mode
- **RiskConfig** - Position limits, drawdown caps, daily loss limits, auto-sizing
- **RedisSimConfig** - Redis URI, key prefix, TTL, pub/sub channel, memory budget
- **SessionMetrics** - P&L, win rate, Sharpe/Sortino/Calmar, equity tracking, per-account breakdown
- **SignalRecord** - Full signal audit trail with outcome tracking
- **RoutingRule/RoutingConfig** - Priority-ordered symbol-pattern rules for execution routing

### Key Enums

- **SessionState** - CREATED, STARTING, RUNNING, PAUSED, STOPPING, STOPPED, ERROR
- **AccountType** - CRYPTO_SPOT, CRYPTO_FUTURES, RITHMIC_FUTURES
- **ExecutionPolicy** - AUTO_EXECUTE, SIGNALS_ONLY, CONFIRMATION_REQUIRED
- **ExchangeName** - KRAKEN, BYBIT, BINANCE, RITHMIC, CRYPTO_COM, NETCOINS
- **SignalOutcome** - PENDING, EXECUTED, CONFIRMED, REJECTED, EXPIRED, SKIPPED, FAILED

## Usage

### In Rust Services

Use the `fks-proto` crate which compiles all proto definitions:

```rust
use fks_proto::common::{TradingSignal, SignalAction, ExecutionMode};
use fks_proto::execution::execution_service_client::ExecutionServiceClient;
use fks_proto::paper_trading::paper_trading_service_client::PaperTradingServiceClient;

// Create a trading signal
let signal = TradingSignal::buy("BTCUSD", 0.1)
    .with_confidence(0.85)
    .with_strategy("momentum_v1")
    .with_mode(ExecutionMode::Paper);

// Connect to execution service
let mut client = ExecutionServiceClient::connect("http://localhost:50054").await?;

// Connect to paper trading service
let mut pt_client = PaperTradingServiceClient::connect("http://localhost:50057").await?;
```

### In Go Services

```go
import (
    commonpb "github.com/nuniesmith/fks/gen/go/fks/common/v1"
    executionpb "github.com/nuniesmith/fks/gen/go/fks/execution/v1"
)

signal := &commonpb.TradingSignal{
    SignalId:  "sig_123",
    Symbol:    "BTCUSD",
    Action:    commonpb.SignalAction_SIGNAL_ACTION_BUY,
    Quantity:  0.1,
    Mode:      commonpb.ExecutionMode_EXECUTION_MODE_PAPER,
}
```

### In Python Services

```python
# Using the flat proto_gen stubs (generated by scripts/gen-proto.sh)
import common_pb2
import paper_trading_pb2
import signals_pb2

signal = common_pb2.TradingSignal(
    signal_id="sig_123",
    symbol="BTCUSD",
    action=common_pb2.SIGNAL_ACTION_BUY,
    quantity=0.1,
    mode=common_pb2.EXECUTION_MODE_PAPER
)

# Paper trading session
session = paper_trading_pb2.PaperTradingSession(
    name="BTC Momentum Test",
    state=paper_trading_pb2.SESSION_STATE_CREATED,
)
```

## Code Generation

### Rust

Proto code for Rust is generated automatically during `cargo build` via the `fks-proto` crate's `build.rs`:

```bash
# Build from repository root
cargo build -p fks-proto

# Or build all services
cargo build
```

### Python (grpcio-tools)

Generate all Python stubs from proto definitions:

```bash
# Generate all 9 proto stubs for Python
bash scripts/gen-proto.sh

# Python only (skip buf/Go)
bash scripts/gen-proto.sh --python
```

Output goes to `src/ruby/src/lib/integrations/proto_gen/` with flat imports:
- `common_pb2.py` / `common_pb2_grpc.py`
- `signals_pb2.py` / `signals_pb2_grpc.py`
- `paper_trading_pb2.py` / `paper_trading_pb2_grpc.py`
- ... (all 9 protos)

### Using Buf (Go, Python, TypeScript)

Install buf CLI:

```bash
# macOS
brew install bufbuild/buf/buf

# Linux
curl -sSL "https://github.com/bufbuild/buf/releases/latest/download/buf-Linux-x86_64" -o /usr/local/bin/buf
chmod +x /usr/local/bin/buf
```

Generate code:

```bash
cd proto
buf generate
```

This generates code in the `gen/` directory based on `buf.gen.yaml` configuration.

## Validation

### Lint Proto Files

```bash
cd proto
buf lint
```

### Check for Breaking Changes

```bash
cd proto
buf breaking --against '.git#branch=main'
```

### Validate Proto Syntax

```bash
./validate.sh
```

## Adding New Proto Files

1. **Create the proto file** in the appropriate directory:
   ```
   proto/fks/<service>/v1/<service>.proto
   ```

2. **Define the package** following the convention:
   ```protobuf
   syntax = "proto3";
   package fks.<service>.v1;
   ```

3. **Import common types** if needed:
   ```protobuf
   import "fks/common/v1/common.proto";
   ```

4. **Update `fks-proto/build.rs`** to include the new file:
   ```rust
   let proto_files = [
       // ... existing files ...
       "fks/newservice/v1/newservice.proto",
   ];
   ```

5. **Update `fks-proto/src/lib.rs`** to export the module:
   ```rust
   pub mod newservice {
       tonic::include_proto!("fks.newservice.v1");
   }
   ```

6. **Update this README** with the new service documentation.

## Proto Style Guide

Follow these conventions for consistency:

### Naming

- **Packages**: `fks.<service>.v1` (lowercase, versioned)
- **Services**: `PascalCase` (e.g., `ExecutionService`)
- **Messages**: `PascalCase` (e.g., `TradingSignal`)
- **Fields**: `snake_case` (e.g., `signal_id`)
- **Enums**: `SCREAMING_SNAKE_CASE` with prefix (e.g., `SIGNAL_ACTION_BUY`)

### Enum Zero Values

Always define an `UNSPECIFIED` zero value:

```protobuf
enum SignalAction {
  SIGNAL_ACTION_UNSPECIFIED = 0;
  SIGNAL_ACTION_BUY = 1;
  SIGNAL_ACTION_SELL = 2;
}
```

### Comments

Document all messages and fields:

```protobuf
// TradingSignal represents a trading decision from JANUS strategies.
message TradingSignal {
  // Unique signal identifier (UUID format).
  string signal_id = 1;
  
  // Trading symbol (e.g., "BTCUSD").
  string symbol = 2;
}
```

### Versioning

- Use `v1`, `v2`, etc. in package names
- Never modify existing field numbers
- Mark deprecated fields with `[deprecated = true]`
- Add new fields at the end of messages

## Migration from Old Structure

The proto files were previously scattered across service directories:

| Old Location | New Location |
|--------------|--------------|
| `src/execution/proto/fks/execution/v1/` | `proto/fks/execution/v1/` |
| `src/janus/proto/fks/janus/v1/` | `proto/fks/janus/v1/` |
| `src/janus/services/data/proto/fks/data/v1/` | `proto/fks/data/v1/` |
| `src/janus/services/forward/proto/fks/forward/v1/` | `proto/fks/forward/v1/` |
| `src/janus/services/cns/proto/fks/cns/v1/` | `proto/fks/cns/v1/` |

The old locations are kept for backward compatibility but should be considered deprecated.

## Service Communication

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         FKS Service Architecture                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐     TradingSignal      ┌──────────────────┐            │
│  │   Forward   │ ────────────────────► │    Execution     │            │
│  │   Service   │    fks.common.v1       │     Service      │            │
│  │  (50051)    │ ◄──────────────────── │    (50054)       │            │
│  └──────┬──────┘     ExecutionResult    └────────┬─────────┘            │
│         │                                        │                       │
│         │ HealthSignal                           │ OrderUpdate           │
│         ▼                                        ▼                       │
│  ┌─────────────┐                       ┌──────────────────┐             │
│  │    CNS      │                       │    Exchange      │             │
│  │  Service    │                       │    (Bybit)       │             │
│  │  (50055)    │                       └──────────────────┘             │
│  └─────────────┘                                                        │
│                                                                          │
│  ┌─────────────┐      Candle           ┌──────────────────┐             │
│  │    Data     │ ────────────────────► │   All Services   │             │
│  │   Service   │    fks.data.v1        │                  │             │
│  │  (50053)    │                       └──────────────────┘             │
│  └─────────────┘                                                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Proto compilation fails

1. Ensure all imported files exist
2. Check package names match directory structure
3. Run `buf lint` to find issues

### Generated code doesn't match proto

1. Clean build artifacts: `cargo clean`
2. Rebuild: `cargo build -p fks-proto`
3. Check `build.rs` includes your proto file

### Import not found

Ensure the import path matches the directory structure:
```protobuf
// Correct
import "fks/common/v1/common.proto";

// Wrong
import "common.proto";
import "proto/fks/common/v1/common.proto";
```

## Resources

- [Protocol Buffers Documentation](https://developers.google.com/protocol-buffers)
- [gRPC Documentation](https://grpc.io/docs/)
- [Buf Documentation](https://docs.buf.build/)
- [Tonic (Rust gRPC)](https://github.com/hyperium/tonic)

## License

MIT License - see repository root for details.