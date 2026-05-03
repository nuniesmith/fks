# Rust Migration Plan: 100% Rust Production Codebase

**Project JANUS - Neuro-Symbolic Trading System**  
**Date**: February 2026  
**Status**: Research & Planning Phase

---

## Executive Summary

This document outlines the migration strategy to move Project JANUS from a Python/Rust hybrid architecture to a **100% Rust production codebase**. The primary goals are:

1. **Eliminate Python from the hot path** - Remove all Python-induced latency (GC pauses, async blocking)
2. **Consolidate services** - Merge execution/muscle into the main Janus binary
3. **Re-implement LTN in Rust** - Build Logic Tensor Networks using Burn or alternatives
4. **Prepare for modular extraction** - Structure code for future repo splits

---

## Table of Contents

1. [Current Architecture Analysis](#current-architecture-analysis)
2. [Rust ML/DL Framework Research](#rust-mldl-framework-research)
3. [LTN Implementation in Rust](#ltn-implementation-in-rust)
4. [Service Consolidation Strategy](#service-consolidation-strategy)
5. [Migration Roadmap](#migration-roadmap)
6. [Future Repository Structure](#future-repository-structure)
7. [Performance Targets](#performance-targets)

---

## 1. Current Architecture Analysis

### Current State (Phase 3)

```
┌─────────────────────────────────────────────────────────────┐
│                    Python "Brain" Service                    │
│  - DiffGAF (Gramian Angular Fields)                         │
│  - ViViT (Video Vision Transformer)                         │
│  - LTN (Logic Tensor Networks) - PyTorch                    │
│  - Regime Classification                                     │
│  - HTTP blocking calls ⚠️                                    │
│  - GC pauses causing jitter ⚠️                               │
│  - P99 latency: 45ms (DiffGAF) ⚠️                            │
└─────────────────────────────────────────────────────────────┘
                            ▼
                    Redis Pub/Sub / ZeroMQ
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Rust "Muscle" Service                    │
│  - Order Execution (Bybit WebSocket)                        │
│  - Risk Engine (Sheriff) ✅                                  │
│  - Compliance Checks ✅                                      │
│  - Position Management                                       │
│  - P99 latency: 15µs ✅                                      │
└─────────────────────────────────────────────────────────────┘
```

### Issues to Resolve

| Issue | Severity | Impact |
|-------|----------|--------|
| Blocking HTTP in regime_classifier.py | **CRITICAL** | Event loop stalls |
| DiffGAF async blocking (torch ops) | **HIGH** | P99 latency 45ms |
| Split-brain volatility estimators | **MEDIUM** | Race conditions |
| Python GC pauses | **MEDIUM** | Latency jitter |
| Inter-service communication overhead | **LOW** | Redis/ZeroMQ latency |

### Components to Migrate

1. **DiffGAF** (Differentiable Gramian Angular Fields)
2. **LTN** (Logic Tensor Networks) - Already started in `src/janus/crates/ltn`
3. **ViViT** (Video Vision Transformer) - Excluded from workspace
4. **Regime Classifier**
5. **All Python services** (forward, backward, CNS if Python-based)

---

## 2. Rust ML/DL Framework Research

### Framework Comparison

#### **Burn** ⭐ RECOMMENDED

**Repository**: [tracel-ai/burn](https://github.com/tracel-ai/burn)  
**Stars**: 14.2k  
**License**: MIT/Apache-2.0  
**Version**: 0.20.1 (Jan 2026)

**Pros**:
- ✅ **Native Rust** - No Python dependencies
- ✅ **Backend agnostic** - CUDA, ROCm, Metal, Vulkan, WebGPU, CPU
- ✅ **Autodiff decorator** - Automatic differentiation for any backend
- ✅ **Kernel fusion** - Automatic optimization
- ✅ **ONNX import** - Can load PyTorch models
- ✅ **no_std support** - Can run on embedded devices
- ✅ **WebAssembly** - Browser inference
- ✅ **Active development** - Large community, frequent updates

**Cons**:
- ⚠️ Newer framework (less mature than PyTorch/TensorFlow)
- ⚠️ Ecosystem still developing
- ⚠️ Some advanced operations may need custom kernels

**Code Example**:
```rust
use burn::nn;
use burn::module::Module;
use burn::tensor::backend::Backend;

#[derive(Module, Debug)]
pub struct LtnNetwork<B: Backend> {
    fc1: nn::Linear<B>,
    fc2: nn::Linear<B>,
    fc3: nn::Linear<B>,
    dropout: nn::Dropout,
}

impl<B: Backend> LtnNetwork<B> {
    pub fn forward<const D: usize>(&self, input: Tensor<B, D>) -> Tensor<B, D> {
        let x = self.fc1.forward(input);
        let x = self.dropout.forward(x);
        let x = self.fc2.forward(x);
        self.fc3.forward(x)
    }
}
```

#### **Candle** (Alternative)

**Repository**: [huggingface/candle](https://github.com/huggingface/candle)  
**Stars**: ~16k  
**Maintainer**: Hugging Face

**Pros**:
- ✅ Minimalist design
- ✅ Fast inference
- ✅ Good for transformer models

**Cons**:
- ⚠️ Less comprehensive than Burn
- ⚠️ Focused on inference, training less mature
- ⚠️ Smaller ecosystem

**Verdict**: Burn is better for training + inference

#### **Tract** (ONNX Runtime)

**Repository**: [sonos/tract](https://github.com/sonos/tract)  
**Use Case**: ONNX model inference only

**Pros**:
- ✅ Already in workspace dependencies
- ✅ Fast inference
- ✅ Supports ONNX, TensorFlow formats

**Cons**:
- ❌ **No training support**
- ❌ Inference only

**Verdict**: Good for loading pre-trained models, not for training LTN

#### **ndarray + ndarray-linalg**

**Use Case**: Basic linear algebra

**Pros**:
- ✅ Lightweight
- ✅ Already used in workspace

**Cons**:
- ❌ No autodiff
- ❌ No GPU support (without external libraries)
- ❌ Manual gradient implementation required

**Verdict**: Too low-level for neural networks

---

## 3. LTN Implementation in Rust

### Current LTN Status

**Good News**: You already have a solid foundation!

**Existing Implementation**: `src/janus/crates/ltn/`
- ✅ `fuzzy_ops.rs` - T-norms, implications, quantifiers (pure Rust)
- ✅ `predicates.rs` - Market predicates
- ✅ `axioms.rs` - 10 trading axioms
- ✅ `config.rs` - Configuration structures
- ✅ **No dependencies on PyTorch** - Already pure Rust logic!

**What's Missing**: Neural network component (currently in Python)

### Strategy: Hybrid LTN Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     LTN Neural Network                        │
│                  (Burn Framework - Rust)                      │
│                                                               │
│   Input (8D DSP Features)                                    │
│      ▼                                                        │
│   Linear(8 → 32) + ReLU                                      │
│      ▼                                                        │
│   Linear(32 → 64) + ReLU + Dropout                           │
│      ▼                                                        │
│   Linear(64 → 32) + ReLU                                     │
│      ▼                                                        │
│   Linear(32 → 3)  // [P(long), P(neutral), P(short)]        │
│      ▼                                                        │
│   Softmax                                                     │
└──────────────────────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  Fuzzy Logic Layer                            │
│             (Already Pure Rust! ✅)                           │
│                                                               │
│   - 10 Axiom Evaluation (axioms.rs)                          │
│   - T-norm operations (fuzzy_ops.rs)                         │
│   - Predicate evaluation (predicates.rs)                     │
│   - Semantic loss computation                                │
└──────────────────────────────────────────────────────────────┘
                           ▼
                  Hybrid Loss Function
         α·L_supervised + (1-α)·L_semantic
```

### Implementation Plan

#### Phase 1: Neural Network with Burn

**File**: `src/janus/crates/ltn/network.rs`

```rust
use burn::{
    module::Module,
    nn::{Linear, LinearConfig, Dropout, DropoutConfig},
    tensor::{backend::Backend, Tensor},
};

#[derive(Module, Debug)]
pub struct LtnNetwork<B: Backend> {
    fc1: Linear<B>,
    fc2: Linear<B>,
    fc3: Linear<B>,
    fc_out: Linear<B>,
    dropout: Dropout,
}

impl<B: Backend> LtnNetwork<B> {
    pub fn new(device: &B::Device) -> Self {
        let fc1 = LinearConfig::new(8, 32).init(device);
        let fc2 = LinearConfig::new(32, 64).init(device);
        let fc3 = LinearConfig::new(64, 32).init(device);
        let fc_out = LinearConfig::new(32, 3).init(device);
        let dropout = DropoutConfig::new(0.2).init();

        Self { fc1, fc2, fc3, fc_out, dropout }
    }

    pub fn forward(&self, input: Tensor<B, 2>) -> Tensor<B, 2> {
        let x = self.fc1.forward(input).relu();
        let x = self.fc2.forward(x).relu();
        let x = self.dropout.forward(x);
        let x = self.fc3.forward(x).relu();
        let logits = self.fc_out.forward(x);
        
        // Softmax for probabilities
        logits.softmax(1)
    }
}
```

**Dependencies to Add**:
```toml
[dependencies]
burn = { version = "0.20", features = ["train", "ndarray"] }
burn-ndarray = "0.20"  # CPU backend
# Optional GPU backends:
# burn-wgpu = "0.20"      # For WebGPU (cross-platform GPU)
# burn-cuda = "0.20"      # For NVIDIA GPUs
```

#### Phase 2: Training Loop

**File**: `src/janus/crates/ltn/training.rs`

```rust
use burn::{
    optim::{AdamConfig, GradientsParams, Optimizer},
    tensor::{backend::AutodiffBackend, Tensor},
    train::{ClassificationOutput, TrainOutput, TrainStep, ValidStep},
};

pub struct LtnTrainer<B: AutodiffBackend> {
    model: LtnNetwork<B>,
    optimizer: Adam<B>,
}

impl<B: AutodiffBackend> LtnTrainer<B> {
    pub fn train_step(
        &mut self,
        features: Tensor<B, 2>,  // [batch, 8]
        labels: Tensor<B, 1, Int>,  // [batch]
    ) -> f64 {
        // Forward pass
        let output = self.model.forward(features);
        
        // Supervised loss (cross-entropy)
        let supervised_loss = output.loss_cross_entropy(&labels);
        
        // Semantic loss (axiom satisfaction)
        // Convert to f64 for fuzzy logic evaluation
        let probs = output.to_data().convert::<f64>();
        let features_data = features.to_data().convert::<f64>();
        
        let semantic_loss = self.compute_semantic_loss(
            &features_data,
            &probs,
        );
        
        // Hybrid loss
        let alpha = 0.5;
        let total_loss = supervised_loss.mul_scalar(alpha)
            .add(semantic_loss.mul_scalar(1.0 - alpha));
        
        // Backward pass
        let grads = total_loss.backward();
        let grads = GradientsParams::from_grads(grads, &self.model);
        
        // Update weights
        self.model = self.optimizer.step(1.0, self.model, grads);
        
        total_loss.into_scalar()
    }
    
    fn compute_semantic_loss(
        &self,
        features: &[f64],  // [8]
        signal: &[f64],    // [3]
    ) -> Tensor<B, 1> {
        use crate::axioms::AxiomLibrary;
        use crate::predicates::TradingSignal;
        
        let signal = TradingSignal::new(signal[0], signal[1], signal[2]);
        let axioms = AxiomLibrary::default();
        let results = axioms.evaluate_all(features, &signal);
        let loss = axioms.compute_semantic_loss(&results);
        
        // Convert f64 loss to tensor
        Tensor::from_floats([loss as f32], &self.device)
    }
}
```

#### Phase 3: Integration with Existing Fuzzy Logic

The beauty of this approach:
- ✅ **Fuzzy logic layer already implemented** in pure Rust
- ✅ **No changes needed** to `fuzzy_ops.rs`, `predicates.rs`, `axioms.rs`
- ✅ **Just add neural network** on top using Burn

**Bridge Interface**:
```rust
// src/janus/crates/ltn/bridge.rs

use burn::tensor::Tensor;
use crate::axioms::AxiomLibrary;
use crate::predicates::TradingSignal;

pub fn tensor_to_features(tensor: &Tensor<B, 1>) -> [f64; 8] {
    let data = tensor.to_data().convert::<f64>();
    data.as_slice::<f64>().unwrap().try_into().unwrap()
}

pub fn tensor_to_signal(tensor: &Tensor<B, 1>) -> TradingSignal {
    let data = tensor.to_data().convert::<f64>();
    let slice = data.as_slice::<f64>().unwrap();
    TradingSignal::new(slice[0], slice[1], slice[2])
}
```

---

## 4. Service Consolidation Strategy

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      JANUS (Single Binary)                   │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │               Data Ingestion Layer                      │  │
│  │  - Bybit WebSocket (janus-bybit-client)                │  │
│  │  - Market data normalization                           │  │
│  │  - Gap detection (janus-gap-detection)                 │  │
│  │  - Rate limiting (janus-rate-limiter)                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                            ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Feature Engineering (DSP)                  │  │
│  │  - 8D feature extraction (janus-dsp)                   │  │
│  │  - DiffGAF transformation (NEW: Burn-based)            │  │
│  │  - Regime detection                                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                            ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           Intelligence Layer (LTN + RL)                 │  │
│  │  - LTN Network (Burn)                                  │  │
│  │  - Axiom evaluation (existing Rust)                    │  │
│  │  - Feudal RL (Manager + Worker)                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                            ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Risk & Compliance (Sheriff)                │  │
│  │  - Risk engine (janus-risk)                            │  │
│  │  - Compliance checks (janus-compliance)                │  │
│  │  - HyroTrader rules enforcement                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                            ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Execution Layer (MERGED)                   │  │
│  │  - Order management (from fks-execution)               │  │
│  │  - Position tracking                                    │  │
│  │  - Exchange connectivity                                │  │
│  └────────────────────────────────────────────────────────┘  │
│                            ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                 Persistence Layer                       │  │
│  │  - QuestDB writer (janus-questdb-writer)               │  │
│  │  - Redis state cache                                    │  │
│  │  - Checkpoint saving                                    │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Merge Strategy

#### Step 1: Create Execution Module in Janus

```
src/janus/
├── crates/
│   ├── execution/           # NEW: Merged from src/execution
│   │   ├── mod.rs
│   │   ├── engine.rs        # Order execution engine
│   │   ├── orders.rs        # Order management
│   │   ├── positions.rs     # Position tracking
│   │   └── exchange.rs      # Exchange adapters
│   ├── ltn/
│   ├── risk/
│   └── ...
```

#### Step 2: Update Janus Binary Dependencies

```toml
# src/janus/bin/janus/Cargo.toml

[dependencies]
janus-execution = { path = "../../crates/execution" }
janus-risk = { workspace = true }
janus-compliance = { workspace = true }
janus-ltn = { workspace = true }
janus-dsp = { workspace = true }
# ... all other crates
```

#### Step 3: Single Main Entry Point

```rust
// src/janus/bin/janus/src/main.rs

use tokio;
use janus_core::JanusCore;
use janus_execution::ExecutionEngine;
use janus_risk::RiskEngine;
use janus_ltn::LtnNetwork;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();
    
    // Initialize components
    let risk_engine = RiskEngine::new(/* config */);
    let execution_engine = ExecutionEngine::new(/* config */);
    let ltn_network = LtnNetwork::new(/* config */);
    
    // Build unified Janus system
    let janus = JanusCore::builder()
        .with_risk(risk_engine)
        .with_execution(execution_engine)
        .with_intelligence(ltn_network)
        .build()?;
    
    // Run forever
    janus.run().await
}
```

---

## 5. Migration Roadmap

### Phase 1: Foundation (Week 1-2)

**Goal**: Set up Burn infrastructure and implement basic LTN network

- [ ] Add Burn dependencies to `janus-ltn` crate
- [ ] Implement `LtnNetwork` struct with Burn
- [ ] Create training loop with hybrid loss
- [ ] Port DiffGAF to Burn (replace PyTorch version)
- [ ] Write unit tests for parity with Python version

**Deliverables**:
- `src/janus/crates/ltn/network.rs`
- `src/janus/crates/ltn/training.rs`
- `src/janus/crates/vision/diffgaf.rs` (Burn-based)

**Success Criteria**:
- ✅ LTN network trains on synthetic data
- ✅ Axiom satisfaction matches Python implementation
- ✅ DiffGAF output matches Python within 1e-6 tolerance

### Phase 2: Service Integration (Week 3-4)

**Goal**: Merge execution service into Janus

- [ ] Create `janus-execution` crate
- [ ] Move order management from `src/execution`
- [ ] Move position tracking from `src/execution`
- [ ] Integrate with existing `janus-risk` and `janus-compliance`
- [ ] Update `janus` binary to include execution

**Deliverables**:
- `src/janus/crates/execution/`
- Updated `src/janus/bin/janus/src/main.rs`

**Success Criteria**:
- ✅ Single binary runs all components
- ✅ No inter-service HTTP/Redis communication
- ✅ Latency < 50µs for full pipeline (DSP → LTN → Risk → Execution)

### Phase 3: Vision Models (Week 5-6)

**Goal**: Implement ViViT (Video Vision Transformer) in Burn

- [ ] Research Burn's transformer implementations
- [ ] Port ViViT architecture to Burn
- [ ] Integrate with DiffGAF pipeline
- [ ] Load pre-trained weights (if available via ONNX)

**Deliverables**:
- `src/janus/crates/vision/vivit.rs`

**Success Criteria**:
- ✅ ViViT processes GAF sequences
- ✅ Inference latency < 10ms (P99)

### Phase 4: Training Infrastructure (Week 7-8)

**Goal**: Build end-to-end training pipeline in Rust

- [ ] Implement data loaders for QuestDB historical data
- [ ] Create Hindsight Experience Replay (HER) in Rust
- [ ] Build feudal RL (Manager/Worker) with Burn
- [ ] Implement Sharp-Wave Ripple (SWR) memory consolidation

**Deliverables**:
- `src/janus/crates/training/`
- `src/janus/services/backward/` (rewritten in Rust)

**Success Criteria**:
- ✅ Full training loop runs in Rust
- ✅ No Python dependencies in production code

### Phase 5: Validation & Optimization (Week 9-10)

**Goal**: Ensure performance and correctness

- [ ] Run 168-hour soak test with 100% Rust
- [ ] Benchmark against Python baseline
- [ ] Profile and optimize hot paths
- [ ] Implement SIMD optimizations for fuzzy logic

**Deliverables**:
- Performance report
- Latency distribution charts

**Success Criteria**:
- ✅ Total tick-to-trade latency < 20ms (P99)
- ✅ Zero Python processes running
- ✅ Memory usage < 500MB

---

## 6. Future Repository Structure

Once everything is working, split into modular repos:

### Repository 1: `fks-janus`

**Purpose**: Core trading intelligence and execution

```
fks-janus/
├── Cargo.toml
├── crates/
│   ├── execution/
│   ├── ltn/
│   ├── dsp/
│   ├── vision/
│   ├── risk/
│   ├── compliance/
│   ├── training/
│   └── ...
├── bin/
│   └── janus/
└── README.md
```

**Container**: `ghcr.io/yourusername/fks-janus:latest`

### Repository 2: `fks-clients`

**Purpose**: Multi-platform UI (KMP)

```
fks-clients/
├── shared/           # Kotlin Multiplatform
├── androidApp/
├── iosApp/
├── desktopApp/
└── webApp/
```

**Artifact**: Desktop/Mobile apps

### Repository 3: `fks-deploy` (Main orchestrator)

**Purpose**: Deployment configuration

```
fks-deploy/
├── docker-compose.yml
├── config/
│   ├── janus.toml
│   ├── redis.conf
│   └── questdb.conf
├── infrastructure/
│   ├── linode/
│   └── terraform/
└── .github/
    └── workflows/
        └── deploy.yml
```

**Dependencies**: 
- Pulls `ghcr.io/yourusername/fks-janus:latest`
- Pulls `ghcr.io/yourusername/fks-clients:latest`

---

## 7. Performance Targets

### Current Baseline (Python + Rust)

| Component | P50 | P99 | Status |
|-----------|-----|-----|--------|
| Tick Ingest (Rust) | 2µs | 15µs | ✅ |
| Risk Check (Rust) | 1µs | 3µs | ✅ |
| **DiffGAF (Python)** | **8ms** | **45ms** | ⚠️ |
| LTN Check (Python) | 2ms | 4ms | ⚠️ |
| **Total** | **18ms** | **82ms** | ⚠️ |

### Target (100% Rust with Burn)

| Component | P50 | P99 | Improvement |
|-----------|-----|-----|-------------|
| Tick Ingest | 2µs | 10µs | ✅ Same |
| Risk Check | 1µs | 3µs | ✅ Same |
| **DiffGAF (Rust/Burn)** | **100µs** | **500µs** | 🚀 **90x faster** |
| **LTN (Rust/Burn)** | **10µs** | **50µs** | 🚀 **80x faster** |
| **Total** | **150µs** | **1ms** | 🚀 **82x faster** |

### Expected Benefits

1. **Latency**: 18ms → **150µs** median (120x improvement)
2. **Jitter**: No GC pauses, deterministic latency
3. **Memory**: Stable, no sawtooth pattern
4. **Deployment**: Single binary, easier ops
5. **Scalability**: Can run on embedded/edge devices

---

## 8. Risks & Mitigations

### Risk 1: Burn Ecosystem Maturity

**Risk**: Burn is newer, may lack some PyTorch features

**Mitigation**:
- Start with simple networks (LTN is small: 8→32→64→32→3)
- Use ONNX import for complex models
- Write custom kernels if needed (Burn supports this)
- Fall back to tract-onnx for inference-only models

### Risk 2: Training Performance

**Risk**: Training in Rust might be slower than PyTorch

**Mitigation**:
- Use GPU backends (burn-wgpu, burn-cuda)
- Leverage kernel fusion (automatic in Burn)
- Train on powerful machines, deploy anywhere
- Worst case: Train in PyTorch, export to ONNX, run in Rust

### Risk 3: Development Velocity

**Risk**: Rust learning curve slows development

**Mitigation**:
- Start with simple components
- Leverage existing pure-Rust LTN code (already done!)
- Use Burn's high-level APIs (similar to PyTorch)
- Document everything, build incrementally

### Risk 4: Data Science Tooling

**Risk**: Losing Python's data science ecosystem

**Mitigation**:
- **Keep Python for analysis/visualization** (not production)
- Use Polars (Rust) for data processing (already in workspace)
- Export data to Python notebooks when needed
- Build Rust-based metrics dashboard (Ratatui TUI planned)

---

## 9. Immediate Next Steps

### This Week

1. **Add Burn to janus-ltn**
   ```bash
   cd src/janus/crates/ltn
   cargo add burn --features train,ndarray
   cargo add burn-ndarray
   ```

2. **Create network.rs**
   - Implement `LtnNetwork` struct
   - Simple forward pass
   - Test with dummy data

3. **Benchmark existing fuzzy logic**
   - Ensure it's fast enough (should be ~1µs)
   - Profile with `cargo flamegraph`

### Next Week

4. **Implement DiffGAF in Burn**
   - Port PyTorch logic to Burn tensors
   - Validate numerical accuracy
   - Benchmark performance

5. **Create prototype consolidation**
   - Copy execution crate structure
   - Wire up basic integration
   - Test end-to-end flow

---

## 10. References & Resources

### Burn Resources

- **Official Docs**: https://burn.dev/
- **GitHub**: https://github.com/tracel-ai/burn
- **Examples**: https://github.com/tracel-ai/burn/tree/main/examples
- **Book**: https://burn.dev/book/ (comprehensive guide)

### Rust ML Ecosystem

- **Linfa**: Traditional ML algorithms in Rust
- **SmartCore**: Alternative ML library
- **ndarray**: NumPy-like arrays

### Learning Materials

- **Burn Book**: Start here for Burn fundamentals
- **PyTorch → Burn Migration**: Community guides on GitHub discussions
- **Rust Performance Book**: https://nnethercote.github.io/perf-book/

---

## Conclusion

Moving to 100% Rust is **highly achievable** and will deliver massive performance improvements. The key insights:

1. ✅ **LTN fuzzy logic already in Rust** - Half the work is done!
2. ✅ **Burn is mature enough** - 14k+ stars, active development, production-ready
3. ✅ **Clear migration path** - Incremental, testable, reversible
4. ✅ **Massive performance gains** - 82x latency improvement expected

**Recommendation**: Proceed with Burn-based migration. Start small (LTN network), validate, then expand to full system.

**Timeline**: 10 weeks to full migration (conservative estimate)

**Risk Level**: **LOW** - Incremental approach with clear rollback points

---

**Status**: ✅ Ready to begin Phase 1

**Next Action**: Add Burn dependency and implement `LtnNetwork`

**Questions?** Review this doc and adjust timeline/approach as needed.