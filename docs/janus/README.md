---
title: "Janus — Rust Trading Engine"
category: "janus"
tags: ["rust", "ml", "inference", "grpc", "neuromorphic"]
---

# Project JANUS Documentation

**Neuro-Symbolic Trading Intelligence System**

Project JANUS is the next-generation trading intelligence system built on neuromorphic architecture principles, combining deep learning with symbolic reasoning for robust, interpretable trading decisions.

---

## 🎯 **NEW: Week 4 ML Pipeline** (Current Focus)

**Status:** Models Complete, Training Infrastructure Next

👉 **[START HERE - Complete Overview](START_HERE.md)** 👈

**Quick Links:**
- **[Quick Reference](QUICK_REFERENCE.md)** - Commands and code snippets
- **[Week 4 Day 3 Complete](WEEK4_DAY3_COMPLETE.md)** - Latest implementation details
- **[Models README](../crates/ml/src/models/README.md)** - Model usage guide

**Week 4 Progress:**
- ✅ Day 1: SQLite conflict resolved ([details](WEEK4_SQLITE_FIX.md))
- ✅ Day 2: Feature extraction complete ([details](WEEK4_DAY2_PROGRESS.md))
- ✅ Day 3: LSTM & MLP models complete ([details](WEEK4_DAY3_COMPLETE.md))
- 🔨 Day 4-5: Training infrastructure (in progress)
- 📅 Day 6-7: Inference engine (planned)

**Test Status:** 123/124 tests passing (99.2%)

---

## 📚 Documentation Index

### 🚀 Quick Start Guides

Get up and running quickly with JANUS components:

- **[API Quickstart](quickstart/API_QUICKSTART.md)** - REST and gRPC API usage
- **[Database Quickstart](quickstart/DATABASE_QUICKSTART.md)** - QuestDB integration
- **[Metrics Quickstart](quickstart/METRICS_QUICKSTART.md)** - Prometheus metrics
- **[Risk Management Quickstart](quickstart/RISK_MANAGEMENT_QUICKSTART.md)** - Risk controls
- **[gRPC & NCCL Quickstart](quickstart/GRPC_NCCL_QUICK_REF.md)** - Service communication
- **[Quick Reference](quickstart/QUICK_REFERENCE.md)** - Command cheat sheet
- **[WebSocket Messages](quickstart/WEBSOCKET_MESSAGES.rs.txt)** - WebSocket protocol

### 📖 Core Documentation

Essential reading for understanding JANUS:

- **[Project Summary](PROJECT_SUMMARY.md)** - High-level overview and goals
- **[Service Migration Guide](SERVICE_MIGRATION.md)** - Migration from Python to Rust

### 🎯 Development Phases

JANUS is developed in phases, each building on the previous:

#### **Week 3: Data Quality Pipeline** ✅ COMPLETE
- **[Week 3 Delivery](WEEK3_DELIVERY.md)** - Data quality implementation
- Comprehensive quality checks (completeness, timeliness, consistency, validity)
- Quality metrics and scoring
- Event processing pipeline
- 31/31 tests passing

#### **Week 4: ML Pipeline** 🚧 IN PROGRESS
- **[START HERE](START_HERE.md)** - Complete overview
- **[Day 1: SQLite Fix](WEEK4_DAY1_COMPLETE.md)** - Dependency conflict resolution
- **[Day 2: Features](WEEK4_DAY2_PROGRESS.md)** - Technical indicators + normalization
- **[Day 3: Models](WEEK4_DAY3_COMPLETE.md)** - LSTM & MLP implementation
- 57/58 model tests passing
- Feature extraction: 35/35 tests passing
- Ready for training infrastructure

#### **Phase 1-3: Foundation (Legacy)** ✅ COMPLETE
- Fuzzy logic and symbolic reasoning
- Non-differentiable Logic Tensor Networks
- Vision pipeline (GAF encoding)

#### **Phase 4: Training Infrastructure** ✅ COMPLETE
- **[Phase 4 Completion Summary](phases/PHASE4_COMPLETION.md)** - Full details
- End-to-end training loop coordinator
- Vision + LTN integration
- Prioritized replay buffer with SWR sampling
- AdamW optimizer with warmup + cosine scheduling
- Automatic checkpointing and model versioning
- Extensible callback system

**Key Achievements:**
- ✅ 839-line training coordinator (`TrainingLoop`)
- ✅ Complete Vision (DiffGAF + ViViT) + LTN integration
- ✅ Working end-to-end example
- ✅ 33/33 tests passing
- ✅ GPU acceleration ready (CUDA/Metal)

**Next Steps:**
1. CUDA testing on RTX 3080
2. Integration with Backward service
3. Prometheus metrics export
4. Wake/Sleep coordination for GPU scheduling

#### **Phase 5: Deployment & Orchestration** 🚧 IN PROGRESS
- Service integration
- Production deployment
- Monitoring and observability
- Wake/Sleep GPU coordination

### 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        JANUS System                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Forward    │  │   Backward   │  │    Memory    │         │
│  │  (Inference) │  │  (Training)  │  │   (Vector)   │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                     │
│                   ┌────────▼────────┐                            │
│                   │  Vision Pipeline │                           │
│                   │ DiffGAF + ViViT  │                           │
│                   └────────┬────────┘                            │
│                            │                                     │
│                   ┌────────▼────────┐                            │
│                   │  Logic Tensor    │                           │
│                   │    Networks      │                           │
│                   └─────────────────┘                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 📦 Crates

JANUS is organized into focused Rust crates:

**Current Development (Week 4):**
- **`ml`** - ML models and inference (LSTM, MLP) - [README](../crates/ml/README.md)
- **`data-quality`** - Data quality pipeline and checks

**Legacy (Phase 1-4):**
- **`vision`** - DiffGAF + ViViT for spatiotemporal encoding - [README](../crates/vision/README.md)
- **`logic`** - Differentiable Logic Tensor Networks - [README](../crates/logic/README.md)
- **`training`** - Training infrastructure (optimizers, replay, schedulers) - [README](../crates/training/README.md)
- **`memory`** - Vector storage and retrieval
- **`common`** - Shared utilities and types
- **`proto`** - gRPC protocol definitions

### 🧪 Examples

Working examples demonstrating JANUS capabilities:

**Week 4 ML Pipeline:**
```bash
cd src/janus

# Run all ML tests
cargo test --package janus-ml

# Test specific components
cargo test --package janus-ml --lib models
cargo test --package janus-ml --lib features
cargo test --package janus-data-quality

# Build and check
cargo build --package janus-ml
```

**Legacy Training:**
```bash
# Run Vision + LTN training example
cd src/janus
cargo run --example vision_ltn_training

# With GPU acceleration
cargo run --example vision_ltn_training --features cuda
```

See [examples directory](../crates/training/examples/) for legacy examples.

### 🧪 Testing

**Week 4 ML Pipeline:**
```bash
cd src/janus

# All ML tests (123 tests)
cargo test --package janus-ml
cargo test --package janus-data-quality

# Specific modules
cargo test --package janus-ml --lib models::lstm
cargo test --package janus-ml --lib features
```

**Legacy Crates:**
```bash
# Test all JANUS crates
cd src/janus
cargo test --workspace

# Test specific crate
cargo test --package vision
cargo test --package logic
cargo test --package training

# With GPU support
cargo test --package training --features cuda
```

### 📊 Current Status

**Week 4 ML Pipeline (Active Development):**
- ✅ Data Quality Pipeline: 31/31 tests passing
- ✅ Feature Extraction: 35/35 tests passing (technical indicators + normalization)
- ✅ LSTM Price Predictor: 9/9 tests passing
- ✅ MLP Signal Classifier: 11/11 tests passing
- ✅ Model trait abstraction and persistence
- 🔨 Training infrastructure: In progress (Day 4-5)
- 📅 Inference engine: Planned (Day 6-7)
- **Total:** 123/124 tests passing (99.2%)

**Legacy Systems (Phase 1-4):**

**Training Infrastructure:**
- ✅ TrainingLoop coordinator (839 lines)
- ✅ Optimizers: AdamW, Adam, SGD
- ✅ Schedulers: Warmup+Cosine, StepLR, Exponential
- ✅ Replay: Prioritized + SWR sampling
- ✅ Checkpointing with versioning
- ✅ Callback system for metrics
- ✅ 33/33 tests passing

**Vision Pipeline:**
- ✅ DiffGAF (differentiable Gramian Angular Field)
- ✅ ViViT (Video Vision Transformer)
- ✅ End-to-end OHLCV → Embedding pipeline
- ✅ GPU acceleration support

**Logic Tensor Networks:**
- ✅ Differentiable t-norms (Łukasiewicz, Product, Gödel)
- ✅ Learnable predicates
- ✅ Formula composition (AND, OR, IMPLIES, NOT)
- ✅ Satisfaction loss for gradient descent
- ✅ Trading-specific rule builders

### 🗂️ Archive

Historical documents and completed milestones:

- **[Weekly Summaries](archive/)** - Week 1-9 progress reports
- **[Legacy Documentation](legacy/)** - Old format documentation
- **[Migration Guides](archive/)** - Historical migration docs

These are kept for reference but are no longer actively maintained.

---

## 🚀 Getting Started with JANUS

### Week 4 ML Pipeline (Current)

**👉 Start Here:** [START_HERE.md](START_HERE.md) - Complete overview and guide

**Quick Start:**
```bash
cd fks/src/janus

# Build and test
cargo build --package janus-ml
cargo test --package janus-ml

# Expected: 57/58 tests pass (1 ignored)
```

**Basic Usage:**
```rust
use janus_ml::models::{LstmConfig, LstmPredictor, Model};
use janus_ml::backend::BackendDevice;

// Create LSTM model
let config = LstmConfig::new(50, 64, 1)
    .with_num_layers(2)
    .with_dropout(0.2);

let model = LstmPredictor::new(config, BackendDevice::cpu());

// Forward pass
let predictions = model.forward(input_tensor)?;

// Save/load
model.save("model.bin")?;
```

**Next Steps:**
1. Read [START_HERE.md](START_HERE.md) for complete overview
2. Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for commands
3. See [WEEK4_DAY3_COMPLETE.md](WEEK4_DAY3_COMPLETE.md) for implementation details
4. Review [Models README](../crates/ml/src/models/README.md) for API reference

### Legacy Systems (Phase 1-4)

**Prerequisites:**
```bash
# Rust 1.70+ with GPU support
rustup update

# CUDA toolkit (optional, for GPU training)
# See: https://developer.nvidia.com/cuda-downloads
```

**Basic Usage:**
```rust
use training::{TrainingLoop, TrainingConfig, OptimizerConfig, 
               LRSchedulerConfig, ReplayBufferConfig};
use vision::{VisionPipeline, VisionPipelineConfig};
use logic::{DiffLTN, TNormType};

// 1. Configure training
let config = TrainingConfig::default()
    .device(Device::cuda_if_available(0)?);

// 2. Create training loop
let mut training = TrainingLoop::new(
    config,
    OptimizerConfig::adamw().learning_rate(1e-4).build(),
    LRSchedulerConfig::warmup_cosine()
        .warmup_steps(1000)
        .total_steps(100_000)
        .build(),
    ReplayBufferConfig::default(),
)?;

// 3. Build models
let vb = VarBuilder::from_varmap(training.var_map(), DType::F32, &device);
let vision = VisionPipeline::from_vb(vision_config, vb.pp("vision"))?;
let ltn = DiffLTN::new(TNormType::Lukasiewicz);

// 4. Define loss functions and train
let metrics = training.run(task_loss_fn, logic_loss_fn, None, None, None)?;
```

**Legacy Next Steps:**
1. Read [Phase 4 Completion Summary](phases/PHASE4_COMPLETION.md) for training details
2. Explore [Training Crate README](../crates/training/README.md) for API reference
3. Run the [Vision + LTN example](../crates/training/examples/vision_ltn_training.rs)
4. Review [Vision](../crates/vision/README.md) and [Logic](../crates/logic/README.md) crate docs

---

## 📝 Contributing

When contributing to JANUS:

1. **Write tests** - All new features must have tests
2. **Update docs** - Keep READMEs and phase docs current
3. **Follow conventions** - Match existing code style
4. **Add examples** - Demonstrate new features with working examples

## 🔗 Related Documentation

- **[Root README](../../../README.md)** - Platform overview
- **[Platform Docs](../../../docs/)** - Infrastructure and operations
- **[Forward Service](../../forward/)** - Inference service
- **[Backward Service](../../backward/)** - Training service

---

**Last Updated:** January 2025  
**Current Focus:** Week 4 ML Pipeline - Models Complete, Training Infrastructure Next  
**Legacy Status:** Phase 4 Complete (Training infrastructure ready)  
**Overall Progress:** ~60% of core ML pipeline complete