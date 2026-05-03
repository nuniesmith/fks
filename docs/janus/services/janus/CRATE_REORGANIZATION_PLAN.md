# JANUS Crate Reorganization Plan

**Version:** 1.0  
**Date:** January 2025  
**Purpose:** Restructure JANUS codebase to align with neuromorphic brain architecture

---

## Executive Summary

This document outlines the reorganization of the JANUS codebase from a flat crate structure to a hierarchical neuromorphic brain architecture. The reorganization will:

1. **Improve Code Organization** - Group related functionality by brain region
2. **Enable Modular Development** - Each brain region is independently testable
3. **Facilitate Understanding** - Code structure mirrors biological architecture
4. **Support Scalability** - Easy to add new regions or enhance existing ones

---

## Current State

### Existing Crate Structure

```
src/janus/crates/
├── backtest/           # Backtesting engine
├── bybit-client/       # Exchange client
├── cns/                # Centralized notification system
├── common/             # Shared utilities
├── compliance/         # Compliance checking
├── data-quality/       # Data validation
├── dsp/                # Digital signal processing
├── exchanges/          # Exchange integrations
├── gap-detection/      # Data gap detection
├── health/             # Health monitoring
├── indicators/         # Technical indicators
├── logic/              # Logic tensor networks (partial)
├── ltn/                # LTN implementation
├── memory/             # Memory systems (basic)
├── ml/                 # ML models (LSTM, MLP)
├── models/             # Trading models
├── proto/              # Protocol buffers
├── questdb-writer/     # Database writer
├── rate-limiter/       # API rate limiting
├── risk/               # Risk management
├── sentiment/          # Sentiment analysis
├── strategies/         # Trading strategies
├── training/           # Training infrastructure (basic)
└── vision/             # DiffGAF + ViViT (partial)
```

**Issues:**
- Flat structure - hard to navigate
- No clear brain region mapping
- Mixing infrastructure and intelligence
- Duplicate functionality across crates
- Unclear dependencies

---

## Target State

### Neuromorphic Brain Structure

```
src/janus/
├── crates/
│   ├── brain/                      # 🧠 BRAIN REGIONS
│   │   ├── visual-cortex/          # Vision processing
│   │   ├── thalamus/               # Multi-modal fusion
│   │   ├── basal-ganglia/          # Hierarchical RL
│   │   ├── hippocampus/            # Memory & learning
│   │   ├── prefrontal/             # Symbolic reasoning
│   │   ├── amygdala/               # Risk & fear
│   │   ├── hypothalamus/           # Capital allocation
│   │   ├── cerebellum/             # Optimal execution
│   │   └── common/                 # Shared brain utilities
│   │
│   ├── infrastructure/             # 🔧 INFRASTRUCTURE
│   │   ├── data-pipeline/          # Data ingestion & quality
│   │   ├── exchanges/              # Exchange integrations
│   │   ├── database/               # QuestDB, Redis clients
│   │   ├── messaging/              # CNS, notifications
│   │   ├── monitoring/             # Health, metrics
│   │   └── compliance/             # Regulatory compliance
│   │
│   ├── training/                   # 🎓 TRAINING SYSTEM
│   │   ├── orchestrator/           # Multi-region training
│   │   ├── model-registry/         # Versioning & selection
│   │   ├── metrics/                # TensorBoard integration
│   │   ├── cuda/                   # CUDA optimizations
│   │   └── datasets/               # Data loading & augmentation
│   │
│   ├── inference/                  # ⚡ INFERENCE SYSTEM
│   │   ├── runtime/                # ONNX Runtime integration
│   │   ├── quantization/           # FP16/INT8 quantization
│   │   ├── batching/               # Dynamic batching
│   │   └── caching/                # Model caching
│   │
│   ├── integration/                # 🔗 SERVICES
│   │   ├── forward-service/        # Wake state (inference)
│   │   ├── backward-service/       # Sleep state (training)
│   │   └── bridge/                 # Shared memory + gRPC
│   │
│   └── common/                     # 📦 SHARED
│       ├── types/                  # Common types
│       ├── utils/                  # Utilities
│       ├── proto/                  # Protocol buffers
│       └── config/                 # Configuration
│
├── lib/
│   ├── janus-core/                 # Core library
│   └── janus-api/                  # Public API
│
└── services/
    ├── forward/                    # Forward service binary
    ├── backward/                   # Backward service binary
    ├── data/                       # Data service
    ├── cns/                        # CNS service
    └── registry/                   # Model registry service
```

---

## Migration Plan

### Phase 1: Brain Regions (Weeks 1-3)

#### Create New Brain Region Crates

```bash
# Visual Cortex
cargo new --lib crates/brain/visual-cortex
mv crates/vision/* crates/brain/visual-cortex/src/
# Refactor to use Burn 0.19, remove legacy code

# Thalamus (NEW)
cargo new --lib crates/brain/thalamus

# Basal Ganglia (NEW)
cargo new --lib crates/brain/basal-ganglia

# Hippocampus
cargo new --lib crates/brain/hippocampus
mv crates/memory/* crates/brain/hippocampus/src/
# Enhance with prioritized replay

# Prefrontal Cortex
cargo new --lib crates/brain/prefrontal
mv crates/logic/* crates/brain/prefrontal/src/
mv crates/ltn/* crates/brain/prefrontal/src/ltn/
# Merge and refactor

# Amygdala
cargo new --lib crates/brain/amygdala
mv crates/risk/* crates/brain/amygdala/src/
# Add fear network

# Hypothalamus (NEW)
cargo new --lib crates/brain/hypothalamus

# Cerebellum (NEW)
cargo new --lib crates/brain/cerebellum

# Brain Common
cargo new --lib crates/brain/common
```

#### Migration Checklist per Region

- [ ] Create crate structure
- [ ] Move existing code
- [ ] Refactor to Burn 0.19
- [ ] Add region-specific traits
- [ ] Write comprehensive tests
- [ ] Benchmark performance
- [ ] Document API
- [ ] Update workspace Cargo.toml

---

### Phase 2: Infrastructure (Week 4)

#### Consolidate Infrastructure Crates

```bash
# Data Pipeline
cargo new --lib crates/infrastructure/data-pipeline
mv crates/data-quality/* crates/infrastructure/data-pipeline/src/quality/
mv crates/gap-detection/* crates/infrastructure/data-pipeline/src/gap_detection/
mv crates/indicators/* crates/infrastructure/data-pipeline/src/indicators/
mv crates/dsp/* crates/infrastructure/data-pipeline/src/dsp/

# Exchanges
cargo new --lib crates/infrastructure/exchanges
mv crates/exchanges/* crates/infrastructure/exchanges/src/
mv crates/bybit-client/* crates/infrastructure/exchanges/src/bybit/
# Add other exchanges: Binance, Coinbase, etc.

# Database
cargo new --lib crates/infrastructure/database
mv crates/questdb-writer/* crates/infrastructure/database/src/questdb/
# Add Redis, PostgreSQL clients

# Messaging
cargo new --lib crates/infrastructure/messaging
mv crates/cns/* crates/infrastructure/messaging/src/

# Monitoring
cargo new --lib crates/infrastructure/config/monitoring
mv crates/health/* crates/infrastructure/config/src/health/
# Add metrics, tracing

# Compliance
mv crates/compliance crates/infrastructure/compliance
# Keep as-is, just move
```

---

### Phase 3: Training System (Weeks 5-6)

#### Build Training Infrastructure

```bash
# Orchestrator (NEW)
cargo new --lib crates/training/orchestrator

# Model Registry (NEW)
cargo new --lib crates/training/model-registry

# Metrics (NEW)
cargo new --lib crates/training/metrics

# CUDA (NEW)
cargo new --lib crates/training/cuda

# Datasets (NEW)
cargo new --lib crates/training/datasets
mv crates/backtest/* crates/training/datasets/src/backtest/
```

---

### Phase 4: Inference System (Week 7)

#### Create Inference Pipeline

```bash
# Runtime (NEW)
cargo new --lib crates/inference/runtime

# Quantization (NEW)
cargo new --lib crates/inference/quantization

# Batching (NEW)
cargo new --lib crates/inference/batching

# Caching (NEW)
cargo new --lib crates/inference/caching
```

---

### Phase 5: Integration (Weeks 8-9)

#### Service Integration

```bash
# Forward Service
cargo new --bin crates/integration/forward-service

# Backward Service  
cargo new --bin crates/integration/backward-service

# Bridge
cargo new --lib crates/integration/bridge
```

---

### Phase 6: Common & Cleanup (Week 10)

#### Consolidate Common Code

```bash
# Types
cargo new --lib crates/common/types

# Utils
cargo new --lib crates/common/utils
mv crates/common/* crates/common/utils/src/

# Proto
mv crates/proto crates/common/proto

# Config
cargo new --lib crates/common/config
```

---

## Detailed Crate Specifications

### Brain Region: Visual Cortex

**Path:** `crates/brain/visual-cortex/`

**Purpose:** Transform market time series into spatiotemporal embeddings

**Components:**
- `diffgaf.rs` - Differentiable Gramian Angular Fields
- `vivit.rs` - Video Vision Transformer
- `pipeline.rs` - End-to-end visual processing
- `config.rs` - Configuration
- `train.rs` - Training loop

**Dependencies:**
```toml
[dependencies]
burn-core = "0.19"
burn-nn = "0.19"
burn-autodiff = "0.19"
burn = { version = "0.19", features = ["ndarray", "train"] }
brain-common = { path = "../common" }
janus-core = { path = "../../../lib/janus-core" }
```

**Public API:**
```rust
pub struct VisualCortex<B: Backend> {
    diffgaf_gasf: DiffGAF<B>,
    diffgaf_gadf: DiffGAF<B>,
    vivit: ViViT<B>,
}

impl<B: Backend> VisualCortex<B> {
    pub fn new(config: VisualCortexConfig, device: &B::Device) -> Self;
    pub fn forward(&self, price_history: Tensor<B, 2>) -> Tensor<B, 2>;
    pub fn train(&mut self, data: &DataLoader) -> TrainingMetrics;
}
```

---

### Brain Region: Thalamus

**Path:** `crates/brain/thalamus/`

**Purpose:** Multi-modal sensory fusion and attention

**Components:**
- `attention.rs` - Cross-modal attention
- `fusion.rs` - Feature fusion
- `state.rs` - Unified state representation

**Public API:**
```rust
pub struct Thalamus<B: Backend> {
    visual_projection: Linear<B>,
    orderbook_projection: Linear<B>,
    sentiment_projection: Linear<B>,
    cross_attention: MultiHeadAttention<B>,
}

pub struct MarketState<B: Backend> {
    pub visual_embedding: Tensor<B, 2>,
    pub orderbook_features: Tensor<B, 2>,
    pub sentiment_features: Tensor<B, 2>,
}

impl<B: Backend> Thalamus<B> {
    pub fn forward(&self, state: MarketState<B>) -> Tensor<B, 2>;
}
```

---

### Brain Region: Basal Ganglia

**Path:** `crates/brain/basal-ganglia/`

**Purpose:** Hierarchical reinforcement learning (Manager-Worker)

**Components:**
- `manager.rs` - Strategic policy (high-level goals)
- `worker.rs` - Tactical policy (low-level actions)
- `actor_critic.rs` - A2C/PPO implementation
- `train.rs` - RL training loop

**Public API:**
```rust
pub struct BasalGanglia<B: Backend> {
    manager: ManagerNetwork<B>,
    worker: WorkerNetwork<B>,
}

pub struct Goal {
    pub target_position: f64,
    pub horizon: usize,
    pub risk_budget: f64,
}

pub struct Action {
    pub trade_signal: TradeSignal,
    pub urgency: f64,
}

impl<B: Backend> BasalGanglia<B> {
    pub fn forward(&self, state: Tensor<B, 2>) -> (Goal, Action);
}
```

---

### Brain Region: Hippocampus

**Path:** `crates/brain/hippocampus/`

**Purpose:** Memory consolidation and experience replay

**Components:**
- `replay.rs` - Prioritized experience replay buffer
- `consolidation.rs` - Memory consolidation (STM → LTM)
- `retrieval.rs` - Memory retrieval and sampling

**Public API:**
```rust
pub struct Hippocampus {
    replay_buffer: PrioritizedReplayBuffer,
    short_term: Vec<Experience>,
    long_term: Vec<Experience>,
}

impl Hippocampus {
    pub fn store(&mut self, experience: Experience);
    pub fn sample(&self, batch_size: usize) -> (Vec<Experience>, Vec<f64>);
    pub fn consolidate(&mut self);
}
```

---

### Brain Region: Prefrontal Cortex

**Path:** `crates/brain/prefrontal/`

**Purpose:** Symbolic reasoning and compliance checking

**Components:**
- `ltn/` - Logic Tensor Networks implementation
- `rules.rs` - Trading rules and constraints
- `compliance.rs` - FTMO/HyroTrader compliance
- `symbolic.rs` - Symbolic reasoning engine

**Public API:**
```rust
pub struct PrefrontalCortex<B: Backend> {
    ltn: LTN<B>,
    rules: Vec<Rule>,
}

pub struct ComplianceResult<B: Backend> {
    pub approved: bool,
    pub confidence: Tensor<B, 1>,
    pub violations: Vec<String>,
}

impl<B: Backend> PrefrontalCortex<B> {
    pub fn check_compliance(
        &self,
        state: &MarketState<B>,
        action: &Action,
    ) -> ComplianceResult<B>;
}
```

---

### Brain Region: Amygdala

**Path:** `crates/brain/amygdala/`

**Purpose:** Risk assessment and fear response

**Components:**
- `fear.rs` - Fear network (threat detection)
- `circuit_breaker.rs` - Circuit breaker logic
- `risk.rs` - Risk metrics and monitoring

**Public API:**
```rust
pub struct Amygdala<B: Backend> {
    fear_network: FearNetwork<B>,
    circuit_breaker: CircuitBreaker,
}

pub struct ThreatLevel {
    pub score: f64,
    pub category: ThreatCategory,
}

impl<B: Backend> Amygdala<B> {
    pub fn assess_threat(&mut self, state: &MarketState<B>) -> ThreatLevel;
    pub fn can_trade(&mut self) -> bool;
}
```

---

### Brain Region: Hypothalamus

**Path:** `crates/brain/hypothalamus/`

**Purpose:** Capital allocation and homeostasis

**Components:**
- `kelly.rs` - Kelly Criterion position sizing
- `homeostasis.rs` - Portfolio balance maintenance
- `allocation.rs` - Capital allocation strategies

**Public API:**
```rust
pub struct Hypothalamus<B: Backend> {
    kelly_allocator: KellyAllocator<B>,
    max_position_pct: f64,
}

pub struct PositionSize {
    pub fraction: f64,
    pub notional: f64,
}

impl<B: Backend> Hypothalamus<B> {
    pub fn compute_position_size(
        &self,
        state: &MarketState<B>,
        account_equity: f64,
    ) -> PositionSize;
}
```

---

### Brain Region: Cerebellum

**Path:** `crates/brain/cerebellum/`

**Purpose:** Optimal execution and order slicing

**Components:**
- `vwap.rs` - StaticVWAP execution
- `slicing.rs` - Order slicing algorithms
- `execution.rs` - Execution optimization

**Public API:**
```rust
pub struct Cerebellum<B: Backend> {
    vwap: StaticVWAP<B>,
}

pub struct OrderSlice {
    pub quantity: f64,
    pub time_index: usize,
    pub limit_price: Option<f64>,
}

impl<B: Backend> Cerebellum<B> {
    pub fn compute_slices(
        &self,
        total_quantity: f64,
        time_horizon: usize,
        state: &MarketState<B>,
    ) -> Vec<OrderSlice>;
}
```

---

## Workspace Configuration

### Root Cargo.toml

```toml
[workspace]
members = [
    # Brain regions
    "crates/brain/visual-cortex",
    "crates/brain/thalamus",
    "crates/brain/basal-ganglia",
    "crates/brain/hippocampus",
    "crates/brain/prefrontal",
    "crates/brain/amygdala",
    "crates/brain/hypothalamus",
    "crates/brain/cerebellum",
    "crates/brain/common",
    
    # Infrastructure
    "crates/infrastructure/data-pipeline",
    "crates/infrastructure/exchanges",
    "crates/infrastructure/database",
    "crates/infrastructure/messaging",
    "crates/infrastructure/config/monitoring",
    "crates/infrastructure/compliance",
    
    # Training
    "crates/training/orchestrator",
    "crates/training/model-registry",
    "crates/training/metrics",
    "crates/training/cuda",
    "crates/training/datasets",
    
    # Inference
    "crates/inference/runtime",
    "crates/inference/quantization",
    "crates/inference/batching",
    "crates/inference/caching",
    
    # Integration
    "crates/integration/forward-service",
    "crates/integration/backward-service",
    "crates/integration/bridge",
    
    # Common
    "crates/common/types",
    "crates/common/utils",
    "crates/common/proto",
    "crates/common/config",
    
    # Libs
    "lib/janus-core",
    "lib/janus-api",
    
    # Services
    "services/forward",
    "services/backward",
    "services/data",
    "services/cns",
    "services/registry",
]

resolver = "2"

[workspace.dependencies]
# Brain regions
visual-cortex = { path = "crates/brain/visual-cortex" }
thalamus = { path = "crates/brain/thalamus" }
basal-ganglia = { path = "crates/brain/basal-ganglia" }
hippocampus = { path = "crates/brain/hippocampus" }
prefrontal = { path = "crates/brain/prefrontal" }
amygdala = { path = "crates/brain/amygdala" }
hypothalamus = { path = "crates/brain/hypothalamus" }
cerebellum = { path = "crates/brain/cerebellum" }
brain-common = { path = "crates/brain/common" }

# Infrastructure
data-pipeline = { path = "crates/infrastructure/data-pipeline" }
exchanges = { path = "crates/infrastructure/exchanges" }
database = { path = "crates/infrastructure/database" }
messaging = { path = "crates/infrastructure/messaging" }
monitoring = { path = "crates/infrastructure/config/monitoring" }
compliance = { path = "crates/infrastructure/compliance" }

# Training
training-orchestrator = { path = "crates/training/orchestrator" }
model-registry = { path = "crates/training/model-registry" }
training-metrics = { path = "crates/training/metrics" }
cuda-kernels = { path = "crates/training/cuda" }
datasets = { path = "crates/training/datasets" }

# Inference
inference-runtime = { path = "crates/inference/runtime" }
quantization = { path = "crates/inference/quantization" }
batching = { path = "crates/inference/batching" }
caching = { path = "crates/inference/caching" }

# Core
janus-core = { path = "lib/janus-core" }
janus-api = { path = "lib/janus-api" }

# Burn ML framework
burn-core = { version = "0.19", default-features = false }
burn-nn = { version = "0.19", default-features = false }
burn-autodiff = { version = "0.19", default-features = false }
burn = { version = "0.19", default-features = false }
burn-cuda = { version = "0.19", optional = true }
burn-wgpu = { version = "0.19", optional = true }

# Standard dependencies
tokio = { version = "1.48", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
anyhow = "1.0"
thiserror = "2.0"
tracing = "0.1"
```

---

## Migration Workflow

### Step-by-Step Process

1. **Create New Crate**
   ```bash
   cargo new --lib crates/brain/visual-cortex
   ```

2. **Copy Existing Code**
   ```bash
   cp -r crates/vision/src/* crates/brain/visual-cortex/src/
   ```

3. **Update Cargo.toml**
   ```toml
   [package]
   name = "visual-cortex"
   version = "0.1.0"
   edition = "2021"
   
   [dependencies]
   burn = { workspace = true, features = ["ndarray", "train"] }
   brain-common = { workspace = true }
   janus-core = { workspace = true }
   ```

4. **Refactor Code**
   - Update imports
   - Use Burn 0.19 APIs
   - Remove deprecated code
   - Add documentation

5. **Add Tests**
   ```bash
   cargo test --package visual-cortex
   ```

6. **Update Workspace**
   - Add to workspace members
   - Update dependent crates

7. **Deprecate Old Crate**
   - Mark as deprecated
   - Add migration guide
   - Remove after grace period

---

## Testing Strategy

### Unit Tests
- Each brain region has comprehensive unit tests
- Target: >90% code coverage

### Integration Tests
- Test inter-region communication
- End-to-end inference pipeline
- Training loop validation

### Benchmark Tests
- Inference latency
- Training throughput
- Memory usage

### Example Test Structure
```rust
// crates/brain/visual-cortex/tests/integration.rs
#[test]
fn test_end_to_end_visual_processing() {
    let device = NdArray::default();
    let config = VisualCortexConfig::default();
    let model = VisualCortex::new(config, &device);
    
    let price_history = generate_test_data();
    let embedding = model.forward(price_history);
    
    assert_eq!(embedding.dims(), [32, 64]);
}
```

---

## Documentation Standards

### Each Crate Must Have:

1. **README.md**
   - Purpose and overview
   - Quick start example
   - API documentation
   - Links to related crates

2. **CHANGELOG.md**
   - Version history
   - Breaking changes
   - Migration guides

3. **Inline Documentation**
   - All public APIs documented
   - Examples in doc comments
   - Link to relevant papers

4. **Examples**
   - Standalone examples in `examples/`
   - Integration examples
   - Benchmark examples

---

## Success Criteria

### Completion Checklist

- [ ] All brain regions migrated to new structure
- [ ] Infrastructure crates consolidated
- [ ] Training system fully functional
- [ ] All tests passing (>90% coverage)
- [ ] Documentation complete
- [ ] Benchmarks show no regression
- [ ] CI/CD updated
- [ ] Old crates deprecated
- [ ] Migration guide published

### Performance Targets

| Metric | Before | After | Notes |
|--------|--------|-------|-------|
| Build time | Baseline | <10% increase | Acceptable overhead |
| Test time | Baseline | <20% increase | More comprehensive tests |
| Binary size | Baseline | Similar | Better optimization |
| Inference latency | Baseline | No regression | Must maintain <40ms |

---

## Timeline

| Week | Milestone | Status |
|------|-----------|--------|
| 1 | Brain regions created | 🔄 In Progress |
| 2 | Visual cortex migrated | ⏳ Pending |
| 3 | Decision regions migrated | ⏳ Pending |
| 4 | Infrastructure consolidated | ⏳ Pending |
| 5-6 | Training system built | ⏳ Pending |
| 7 | Inference system built | ⏳ Pending |
| 8-9 | Integration complete | ⏳ Pending |
| 10 | Testing & documentation | ⏳ Pending |
| 11-12 | Production deployment | ⏳ Pending |

---

## Rollback Plan

If migration encounters critical issues:

1. **Immediate Rollback**
   - Revert to previous workspace structure
   - Keep old crates functional
   - Fix issues in new structure

2. **Gradual Migration**
   - Migrate one brain region at a time
   - Run old and new in parallel
   - Switch after validation

3. **Feature Flags**
   ```toml
   [features]
   default = ["new-structure"]
   new-structure = []
   legacy-structure = []
   ```

---

## Appendix: Crate Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                     Forward Service                          │
└─────────┬───────────────────────────────────────────────────┘
          │
          ├──► Visual Cortex ──► Brain Common
          ├──► Thalamus      ──► Brain Common
          ├──► Basal Ganglia ──► Brain Common
          ├──► Hippocampus   ──► Brain Common
          ├──► Prefrontal    ──► Brain Common
          ├──► Amygdala      ──► Brain Common
          ├──► Hypothalamus  ──► Brain Common
          ├──► Cerebellum    ──► Brain Common
          │
          └──► JANUS Core ────► Common Types
                               ► Common Utils
                               ► Common Proto

┌─────────────────────────────────────────────────────────────┐
│                    Backward Service                          │
└─────────┬───────────────────────────────────────────────────┘
          │
          ├──► Training Orchestrator ──► All Brain Regions
          ├──► Model Registry
          ├──► Training Metrics
          └──► CUDA Kernels

┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                        │
└─────────┬───────────────────────────────────────────────────┘
          │
          ├──► Data Pipeline
          ├──► Exchanges
          ├──► Database
          ├──► Messaging
          ├──► Monitoring
          └──► Compliance
```

---

**Next Steps:**
1. Review and approve this reorganization plan
2. Create feature branch: `feat/neuromorphic-structure`
3. Begin Week 1 migration (brain region scaffolding)
4. Update CI/CD to support new structure
5. Start documentation updates

**Questions/Concerns:**
- Coordinate with team on migration timing
- Identify any blocking dependencies
- Review resource requirements (dev time, testing)