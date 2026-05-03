# JANUS - Neuro-Symbolic Trading Intelligence

**Project JANUS** is the next-generation trading intelligence system built on neuromorphic architecture principles, combining deep learning with symbolic reasoning for robust, interpretable trading decisions.

---

## 🚀 Quick Start

👉 **[Start Here](START_HERE.md)** - Complete overview and orientation

**Essential Planning Documents:**
- 📋 **[12-Week Implementation Plan](JANUS_BURN_12_WEEK_PLAN.md)** - Complete Burn framework roadmap
- 🏗️ **[Crate Reorganization Plan](CRATE_REORGANIZATION_PLAN.md)** - Neuromorphic structure guide
- ⚡ **[Development Quick Reference](DEVELOPMENT_QUICK_REF.md)** - Commands and workflows
- 📖 **[Architectural Specification](../research/JANUS_ARCHITECTURAL_SPECIFICATION.md)** - Complete whitepaper

**Getting Started:**
- **[Quick Start Guide](quickstart/QUICK_START.md)** - Get started with JANUS
- **[Quick Reference](quickstart/QUICK_REFERENCE.md)** - Commands and code snippets
- **[Project Summary](PROJECT_SUMMARY.md)** - High-level overview
- **[Todo List](todo.md)** - Current development tasks

---

## 🏗️ JANUS Architecture

### Overview

JANUS implements a complete neuromorphic brain with 9 specialized regions, trained using Rust + Burn ML framework with CUDA acceleration.

**📋 [See 12-Week Implementation Plan →](JANUS_BURN_12_WEEK_PLAN.md)**

### Neuromorphic Brain Architecture

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

JANUS is built with a modular architecture using focused Rust crates:

### Core Crates

**Machine Learning:**
- **`ml`** - ML models and inference (LSTM, MLP) - [README](../../src/janus/crates/ml/README.md)
- **`vision`** - DiffGAF + ViViT spatiotemporal encoding - [README](../../src/janus/crates/vision/README.md)
- **`logic`** - Differentiable Logic Tensor Networks - [README](../../src/janus/crates/logic/README.md)
- **`training`** - Training infrastructure (optimizers, replay, schedulers) - [README](../../src/janus/crates/training/README.md)

**Data & Infrastructure:**
- **`data-quality`** - Data quality pipeline and validation
- **`memory`** - Vector storage and retrieval
- **`common`** - Shared utilities and types
- **`proto`** - gRPC protocol definitions

---

## 🧪 Testing & Development

### Running Tests

```bash
cd src/janus

# Test all JANUS crates
cargo test --workspace

# Test specific crates
cargo test --package janus-ml
cargo test --package janus-vision
cargo test --package janus-logic
cargo test --package janus-training

# Run with GPU support
cargo test --package janus-training --features cuda
```

### Building & Running

```bash
cd src/janus

# Build all crates
cargo build --workspace

# Build with release optimizations
cargo build --workspace --release

# Run training example
cargo run --example vision_ltn_training --features cuda
```

See crate-specific READMEs for detailed usage and examples.

---

## 📊 Current Status

**Overall Status:** Phase 4 Complete - Production Ready  
**Last Updated:** January 2025

### Component Status

**✅ Phase 4: Training Infrastructure** (Complete)
- TrainingLoop coordinator (839 lines)
- Optimizers: AdamW, Adam, SGD
- Schedulers: Warmup+Cosine, StepLR, Exponential
- Replay: Prioritized + SWR sampling
- Checkpointing with versioning
- Callback system for metrics
- **Tests:** 33/33 passing

**✅ Vision Pipeline** (Complete)
- DiffGAF (differentiable Gramian Angular Field)
- ViViT (Video Vision Transformer)
- End-to-end OHLCV → Embedding pipeline
- GPU acceleration support

**✅ Logic Tensor Networks** (Complete)
- Differentiable t-norms (Łukasiewicz, Product, Gödel)
- Learnable predicates
- Formula composition (AND, OR, IMPLIES, NOT)
- Satisfaction loss for gradient descent
- Trading-specific rule builders

**✅ ML Pipeline** (Complete)
- Data Quality: 31/31 tests passing
- Feature Extraction: 35/35 tests passing
- LSTM Price Predictor: 9/9 tests passing
- MLP Signal Classifier: 11/11 tests passing
- Model persistence and loading

**🔄 Next Phase: Neuromorphic Implementation**

Following the **[12-Week Burn Implementation Plan](JANUS_BURN_12_WEEK_PLAN.md)**:
- Weeks 1-3: Visual Cortex (DiffGAF + ViViT)
- Weeks 4-6: Decision regions (Thalamus, Basal Ganglia, Hippocampus)
- Weeks 7-9: Safety & execution (Prefrontal, Amygdala, Hypothalamus, Cerebellum)
- Weeks 10-12: Integration, CUDA training, production deployment

**Key Features:**
- ✅ CUDA-accelerated training with model versioning
- ✅ Automated model selection and replacement
- ✅ Continuous retraining loop (Wake/Sleep cycle)
- ✅ <40ms inference latency target
- ✅ Production-ready with hot-swapping

---

## 📚 Documentation Structure

### Planning & Implementation
- **[12-Week Burn Plan](JANUS_BURN_12_WEEK_PLAN.md)** - Complete implementation roadmap
- **[Crate Reorganization](CRATE_REORGANIZATION_PLAN.md)** - Neuromorphic code structure
- **[Development Quick Ref](DEVELOPMENT_QUICK_REF.md)** - Daily development guide

### Architecture & Research
- **[Architectural Specification](../research/JANUS_ARCHITECTURAL_SPECIFICATION.md)** - Complete whitepaper
- **[Implementation Status](../research/JANUS_IMPLEMENTATION_STATUS.md)** - Current progress
- **[Implementation Gap Analysis](../research/JANUS_IMPLEMENTATION_GAP_ANALYSIS.md)** - Roadmap details

### Guides & References
- **[Quick Start Guide](quickstart/QUICK_START.md)** - Get started quickly
- **[API Quickstart](quickstart/API_QUICKSTART.md)** - gRPC & REST APIs
- **[Database Quickstart](quickstart/DATABASE_QUICKSTART.md)** - QuestDB integration
- **[Metrics Quickstart](quickstart/METRICS_QUICKSTART.md)** - Prometheus metrics
- **[Risk Management](quickstart/RISK_MANAGEMENT_QUICKSTART.md)** - Risk controls

---

## 🚀 Getting Started

### Quick Start

1. **Read the Overview:**
   - Start with [START_HERE.md](START_HERE.md) for complete orientation
   - Review [Project Summary](PROJECT_SUMMARY.md) for high-level goals

2. **Build and Test:**
   ```bash
   cd src/janus
   cargo build --workspace
   cargo test --workspace
   ```

3. **Explore Components:**
   - [ML Models](../../src/janus/crates/ml/README.md) - LSTM & MLP implementations
   - [Vision Pipeline](../../src/janus/crates/vision/README.md) - Spatiotemporal encoding
   - [Logic](../../src/janus/crates/logic/README.md) - Logic Tensor Networks
   - [Training](../../src/janus/crates/training/README.md) - Training infrastructure

4. **Check Quick References:**
   - [Quick Start](quickstart/QUICK_START.md)
   - [Quick Reference](quickstart/QUICK_REFERENCE.md)
   - [API Quickstart](quickstart/API_QUICKSTART.md)

### Prerequisites

- **Rust:** 1.75+ (`rustup update`)
- **CUDA:** Optional, for GPU acceleration ([download](https://developer.nvidia.com/cuda-downloads))
- **Dependencies:** See individual crate READMEs

---

## 📝 Contributing & Development

### Contributing Guidelines

1. **Write Tests:** All new features must have comprehensive tests
2. **Update Documentation:** Keep READMEs and docs synchronized with code
3. **Follow Conventions:** Match existing code style and architecture patterns
4. **Add Examples:** Demonstrate new features with working examples
5. **Review Checklist:** See [Commit Checklist](../guides/COMMIT_CHECKLIST.md)

### Development Workflow

1. Create feature branch
2. Implement changes with tests
3. Update relevant documentation
4. Run full test suite
5. Submit pull request with clear description


---

## 🛠️ Development Workflow

### Setting Up Development Environment

```bash
# Clone and setup
cd fks/src/janus
cargo build --workspace
cargo test --workspace

# CUDA setup (for training)
docker build -f Dockerfile.training -t janus-training .
docker run --runtime=nvidia --gpus all janus-training
```

**👉 See [Development Quick Reference](DEVELOPMENT_QUICK_REF.md) for complete setup**

### Current Development Focus

**Phase 1: Crate Reorganization (In Progress)**
- Restructuring code to match neuromorphic brain architecture
- See **[Crate Reorganization Plan](CRATE_REORGANIZATION_PLAN.md)**

**Next: Brain Region Implementation**
- Following **[12-Week Burn Plan](JANUS_BURN_12_WEEK_PLAN.md)**
- Starting with Visual Cortex (DiffGAF + ViViT)

---

## 🔗 Related Documentation

### Platform Documentation
- **[Root README](../../README.md)** - Platform overview
- **[Platform Docs](../README.md)** - Complete documentation hub
- **[Architecture](../architecture/)** - System design
- **[Operations](../operations/)** - Deployment and operations

### Service Documentation
- **[Forward Service](../../src/forward/)** - Real-time inference service
- **[Backward Service](../../src/backward/)** - Training and backtesting service
- **[Data Service](../services/data-service/)** - Market data ingestion
- **[Execution Service](../../src/execution/)** - Order management

### Quick References
- **[Quick Commands](../reference/QUICK_COMMANDS.md)** - Essential commands
- **[Technical Indicators](../reference/TECHNICAL_INDICATORS.md)** - Trading indicators
- **[ML Quick Reference](../reference/ML_QUICK_REFERENCE.md)** - ML framework reference

---

## 📊 Project Status

**Last Updated:** January 2025  
**Status:** Planning Complete - Implementation Starting  
**Documentation:** Consolidated into `/docs/janus/`

**Planning Milestones:**
- ✅ Complete architectural specification (whitepaper)
- ✅ 12-week Burn implementation plan
- ✅ Crate reorganization plan
- ✅ Development workflows documented
- ✅ ML Pipeline Complete (Data Quality, Features, Models)
- ✅ 150+ Tests Passing Across All Crates

**Implementation Roadmap:**
- 🔄 **Week 1-3:** Foundation & Visual Cortex (DiffGAF + ViViT)
- 📅 **Week 4-6:** Decision regions (Thalamus, Basal Ganglia, Hippocampus)
- 📅 **Week 7-9:** Safety & execution (Prefrontal, Amygdala, Hypothalamus, Cerebellum)
- 📅 **Week 10-12:** Integration, CUDA training, production deployment

**Target Metrics (Week 12):**
- ⚡ <40ms end-to-end inference latency
- 🎯 >2.0 Sharpe ratio on validation
- 🔥 10x+ training speedup with CUDA
- 🤖 Automated model selection & deployment

---

## 📖 Key Documents to Read

1. **[12-Week Burn Plan](JANUS_BURN_12_WEEK_PLAN.md)** - Start here for implementation
2. **[Architectural Specification](../research/JANUS_ARCHITECTURAL_SPECIFICATION.md)** - Understand the design
3. **[Crate Reorganization](CRATE_REORGANIZATION_PLAN.md)** - Code structure guide
4. **[Development Quick Ref](DEVELOPMENT_QUICK_REF.md)** - Daily development commands

---

*For historical progress and archived documentation, see [Archive](archive/)*