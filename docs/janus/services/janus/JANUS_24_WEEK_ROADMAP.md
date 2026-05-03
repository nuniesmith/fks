# JANUS 24-Week Development Roadmap
## Complete Neuromorphic Trading System: Research to Production

**Version:** 2.0  
**Created:** 2024  
**Target:** Full end-to-end autonomous trading system with real data sources, production deployment, and operational excellence

---

## Executive Summary

This roadmap extends the original 12-week plan to a full 24-week production deployment. It addresses critical gaps identified in the research review and incorporates lessons learned from the current ML pipeline implementation (Week 4, Day 3 complete with 99.2% test pass rate).

### Key Additions Beyond Original 12-Week Plan

1. **Real Data Integration** (Weeks 13-15): Live exchange connections, news APIs, alternative data sources
2. **Production ML Pipeline** (Weeks 16-18): Full training infrastructure, model registry, A/B testing
3. **Execution Engine** (Weeks 19-21): Order routing, position management, real PnL tracking
4. **Operations & Monitoring** (Weeks 22-24): Production deployment, disaster recovery, live trading

### Success Metrics

- **Week 12:** Research system complete, backtest-validated neuromorphic pipeline
- **Week 18:** Production ML system with automated retraining and model versioning
- **Week 24:** Live trading system processing real orders with full observability

---

## Table of Contents

1. [Architectural Principles](#architectural-principles)
2. [Phase 1: Foundation (Weeks 1-4)](#phase-1-foundation-weeks-1-4)
3. [Phase 2: ML Pipeline (Weeks 5-8)](#phase-2-ml-pipeline-weeks-5-8)
4. [Phase 3: Signal Generation (Weeks 9-12)](#phase-3-signal-generation-weeks-9-12)
5. [Phase 4: Data Integration (Weeks 13-15)](#phase-4-data-integration-weeks-13-15)
6. [Phase 5: Production ML (Weeks 16-18)](#phase-5-production-ml-weeks-16-18)
7. [Phase 6: Execution (Weeks 19-21)](#phase-6-execution-weeks-19-21)
8. [Phase 7: Production Ops (Weeks 22-24)](#phase-7-production-ops-weeks-22-24)
9. [Appendices](#appendices)

---

## Architectural Principles

### 1. Biology-Inspired Modularity

Each component maps to a brain region with clear responsibilities:

```
┌─────────────────────────────────────────────────────────────┐
│                    JANUS Neuromorphic Architecture           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Data Streams (Retina/LGN)                                  │
│       │                                                      │
│       ▼                                                      │
│  Visual Cortex (GAF → ViViT) ────────┐                     │
│       │                                │                     │
│       ▼                                ▼                     │
│  Hippocampus (Memory) ─────→  Prefrontal Cortex (Logic)    │
│       │                                │                     │
│       ▼                                ▼                     │
│  Neocortex (Schemas) ──────→  Basal Ganglia (Actions)      │
│       │                                │                     │
│       └──────────┬─────────────────────┘                     │
│                  │                                           │
│                  ▼                                           │
│            Amygdala (Risk) ──→ Hypothalamus (Homeostasis)   │
│                  │                                           │
│                  ▼                                           │
│            Motor Cortex (Execution)                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2. Dual-Service Model (Validated in Week 4)

**Forward Service (Janus Bifrons):**
- Real-time inference (<50ms p99 latency)
- Read-only model weights
- Stateless signal generation
- Event-driven architecture (tokio)

**Backward Service (Janus Consivius):**
- Offline training (nightly or on-demand)
- Experience replay and consolidation
- Model weight updates
- Batch processing (rayon)

### 3. Burn 0.19+ Integration (Current Status)

**Implemented (Week 4, Day 3):**
- ✅ Backend abstraction (CPU/GPU)
- ✅ LSTM & MLP models with Burn
- ✅ Feature extraction pipeline
- ✅ Model save/load (config + metadata)
- ✅ 123/124 tests passing (99.2%)

**In Progress (Week 4, Day 4-5):**
- 🔄 Training loop with autodiff
- 🔄 Dataset abstraction
- 🔄 Gradient clipping (adaptive LR scaling)
- 🔄 Checkpointing with Burn Record API

**Planned (Weeks 5-8):**
- 📅 DiffGAF implementation
- 📅 ViViT (Video Vision Transformer)
- 📅 Logic Tensor Networks (LTN)
- 📅 Prioritized Experience Replay (PER)

### 4. Critical Gaps Addressed

Based on research review feedback:

1. **Gradient Clipping:** Implemented in Week 4 with adaptive LR scaling (Burn 0.19 limitation workaround)
2. **Catastrophic Forgetting:** Elastic Weight Consolidation (EWC) added in Week 8
3. **Backtest Infrastructure:** Comprehensive replay engine in Week 9
4. **Conformal Prediction:** Amygdala outlier detection in Week 10
5. **Shared Memory Model Sync:** IPC optimization in Week 17
6. **Production Alerting:** Full Prometheus/Grafana in Week 11-12

---

## Phase 1: Foundation (Weeks 1-4)

### Current Status (Week 4, Day 3 Complete)

**Completed:**
- ✅ Data quality pipeline (31/31 tests)
- ✅ SQLite dependency conflict resolved
- ✅ Feature extraction (35/35 tests)
- ✅ LSTM & MLP models (57/58 tests)
- ✅ Backend abstraction layer
- ✅ Error handling framework
- ✅ Documentation (3,500+ lines)

**Next Steps (Week 4, Day 4-5):**
- Training infrastructure
- Dataset abstraction
- Optimizer integration
- Checkpoint management

### Week 1: Data Ingestion Enhancement ✅

**Status:** COMPLETE  
**Test Coverage:** 31/31 passing

#### Deliverables
- [x] Exchange websocket connectors (Binance, Bybit, Coinbase)
- [x] Market data normalization
- [x] Gap detection and backfill
- [x] QuestDB integration
- [x] Data quality metrics

#### Crate Structure
```
crates/exchanges/
├── src/
│   ├── binance.rs       # Binance websocket
│   ├── bybit.rs         # Bybit websocket
│   ├── coinbase.rs      # Coinbase websocket
│   ├── connector.rs     # Trait abstraction
│   └── normalizer.rs    # Event normalization
└── Cargo.toml

crates/gap-detection/
└── src/
    ├── detector.rs      # Sequence gap detection
    ├── backfill.rs      # Historical data fill
    └── scheduler.rs     # Backfill priority queue
```

#### Key Metrics (CNS)
```rust
// Already implemented in crates/cns
janus_data_websocket_connections{exchange="binance"}
janus_data_sequence_gaps_total{symbol="BTCUSD"}
janus_data_backfill_requests_total
janus_data_messages_received_total
```

### Week 2: News & Alternative Data ✅

**Status:** COMPLETE (sentiment crate exists)  
**Test Coverage:** 35/35 passing

#### Deliverables
- [x] RSS feed aggregation
- [x] Sentiment analysis (crates/sentiment)
- [x] Entity extraction (crypto mentions)
- [x] Fear & Greed index integration
- [x] Whale alert monitoring

#### Crate Structure
```
crates/sentiment/
├── src/
│   ├── analyzer.rs      # Sentiment scoring
│   ├── entities.rs      # NER (crypto, exchanges)
│   ├── sources/         # Data sources
│   │   ├── rss.rs
│   │   ├── twitter.rs   # Via API v2
│   │   └── alternative.rs
│   └── models/
│       └── distilbert.rs # HuggingFace model
└── Cargo.toml
```

#### Data Structures
```rust
pub struct NewsArticle {
    pub id: Uuid,
    pub source: String,
    pub title: String,
    pub content: String,
    pub published_at: DateTime<Utc>,
    pub sentiment: SentimentScore,
    pub entities: Vec<Entity>,
    pub relevance: f32,  // 0.0-1.0
}

pub struct SentimentScore {
    pub compound: f32,    // -1.0 to 1.0
    pub positive: f32,
    pub negative: f32,
    pub neutral: f32,
    pub confidence: f32,
}

pub enum Entity {
    Cryptocurrency { symbol: String, confidence: f32 },
    Exchange { name: String, confidence: f32 },
    Person { name: String, confidence: f32 },
    Amount { value: f64, currency: String },
}
```

### Week 3: Storage & Configuration ✅

**Status:** COMPLETE  
**QuestDB Schema:** Deployed

#### Deliverables
- [x] QuestDB schema optimization
- [x] Asset configuration system
- [x] Per-asset data collection rules
- [x] Retention policies
- [x] Storage API abstraction

#### Asset Configuration
```rust
// config/assets/btcusdt.toml
[asset]
symbol = "BTCUSD"
enabled = true
exchanges = ["binance", "bybit", "coinbase"]

[data]
collect_trades = true
collect_orderbook = true
orderbook_depth = 20
collect_funding = true
collect_liquidations = true
news_keywords = ["bitcoin", "btc", "crypto"]
retention_days = 365

[model]
vision_enabled = true
ltn_enabled = true
gaf_window_size = 60
gaf_num_frames = 10
custom_indicators = ["rsi", "macd", "bollinger"]

[risk]
max_position_size = 1.0  # BTC
max_drawdown_pct = 0.15
volatility_lookback = 30
circuit_breaker_threshold = 0.05
```

### Week 4: Data Quality Pipeline ✅

**Status:** COMPLETE (99.2% test coverage)  
**Crate:** `crates/data-quality`

#### Current Implementation

**Validators:**
- TimestampValidator: Chronological ordering
- RangeValidator: Price/volume bounds
- DuplicateDetector: Exact and fuzzy matching
- SequenceValidator: Gap detection

**Anomaly Detectors:**
- ZScoreDetector: Statistical outliers
- PriceSpikeDetector: Sudden price movements
- VolumeAnomalyDetector: Unusual volume
- CrossExchangeDetector: Arbitrage anomalies

**Quality Metrics:**
```rust
pub struct QualityReport {
    pub quality_score: f32,      // 0.0-1.0
    pub total_records: usize,
    pub valid_records: usize,
    pub anomalies_detected: usize,
    pub issues: Vec<QualityIssue>,
}
```

#### Next Steps (Week 4, Day 4-5) 👈 CURRENT

**Priority 1: Training Infrastructure**
- [ ] Dataset trait with batch iterator
- [ ] Training loop with autodiff
- [ ] Optimizer integration (Adam/AdamW)
- [ ] Loss functions (MSE, CrossEntropy)
- [ ] Gradient clipping (implemented, needs integration)
- [ ] Checkpoint management
- [ ] Learning rate scheduling
- [ ] Early stopping

**Estimated:** 8-12 hours  
**Test Target:** 70+ tests passing  
**Blocker:** None (all dependencies resolved)

**Code Skeleton:**
```rust
// crates/ml/src/dataset.rs
pub trait Dataset {
    fn len(&self) -> usize;
    fn get(&self, idx: usize) -> Result<DataBatch>;
    fn split(&self, ratio: f32) -> (Self, Self);
}

pub struct TimeSeriesDataset {
    features: Tensor<CpuBackend, 3>,  // [samples, seq_len, features]
    targets: Tensor<CpuBackend, 1>,   // [samples]
    window_size: usize,
}

// crates/ml/src/training/mod.rs
pub struct TrainingConfig {
    pub epochs: usize,
    pub batch_size: usize,
    pub learning_rate: f64,
    pub grad_clip: Option<GradientClipping>,
    pub early_stopping_patience: usize,
}

pub struct Trainer<B: Backend, M: Model<B>> {
    model: M,
    optimizer: OptimizerAdaptor<Adam, M, B>,
    config: TrainingConfig,
}

impl<B: Backend, M: Model<B>> Trainer<B, M> {
    pub fn fit(
        &mut self,
        train_data: &impl Dataset,
        val_data: &impl Dataset,
    ) -> Result<TrainingHistory> {
        // Training loop implementation
    }
}
```

---

## Phase 2: ML Pipeline with Burn (Weeks 5-8)

### Week 5: Burn Framework Deep Integration

**Goal:** Full migration to Burn 0.19+ with GPU support

#### Tasks

**Priority 1: DiffGAF Implementation** (2-3 days)
- [ ] Implement learnable normalization (tanh clipping)
- [ ] Fix arccos boundary conditions (epsilon clamping)
- [ ] Gramian matrix broadcasting optimization
- [ ] Kernel fusion verification
- [ ] Gradient flow validation
- [ ] Benchmark GAF generation latency

**Critical Fix (from research review):**
```rust
// WRONG (gradient explosion at boundaries):
let phi = x_norm.acos();

// CORRECT (epsilon clamping):
let phi = x_norm.clamp(-0.999, 0.999).acos();

// ALTERNATIVE (differentiable everywhere):
let phi = (x_norm + 1.0) * (PI / 2.0 - 2.0 * EPS) + EPS;
```

**Priority 2: Backend Configuration** (1-2 days)
- [ ] CUDA backend integration (Burn 0.20+)
- [ ] WGPU fallback (for development)
- [ ] CPU backend for inference
- [ ] Mixed precision support (FP16/BF16)
- [ ] Memory pool management

**Priority 3: Training Loop Enhancements** (2 days)
- [ ] Distributed training (multi-GPU)
- [ ] Gradient accumulation
- [ ] Automatic Mixed Precision (AMP)
- [ ] Training interruption/resumption
- [ ] TensorBoard logging integration

#### Crate Structure
```
crates/ml/
├── src/
│   ├── backend.rs           # Enhanced backend abstraction
│   ├── training/
│   │   ├── mod.rs           # Trainer implementation ✅
│   │   ├── config.rs        # TrainingConfig ✅
│   │   ├── callbacks.rs     # Checkpoint, EarlyStopping
│   │   ├── distributed.rs   # Multi-GPU support
│   │   └── logger.rs        # TensorBoard integration
│   ├── vision/
│   │   ├── gaf.rs           # DiffGAF (NEW)
│   │   ├── vivit.rs         # ViViT (NEW)
│   │   └── transforms.rs    # Data augmentation
│   └── ...
```

#### Deliverables
- [ ] DiffGAF with validated gradients
- [ ] Multi-backend support (CUDA/WGPU/CPU)
- [ ] Distributed training ready
- [ ] Performance benchmarks (<10ms GAF generation)
- [ ] 80+ tests passing

#### CNS Metrics
```rust
janus_ml_backend{type="cuda|wgpu|cpu"}
janus_ml_gaf_generation_duration_seconds
janus_ml_gaf_boundary_clamps_total
janus_ml_training_gpu_count
janus_ml_mixed_precision_enabled
```

### Week 6: Vision Pipeline (GAF + ViViT)

**Goal:** Complete visual perception system

#### Tasks

**Priority 1: ViViT Implementation** (3-4 days)
- [ ] Tubelet embedding (3D convolution)
- [ ] Factorized spacetime attention
- [ ] Spatial transformer encoder
- [ ] Temporal transformer encoder
- [ ] Tensor choreography optimization
- [ ] Memory efficiency profiling

**Critical Implementation:**
```rust
pub struct ViViT<B: Backend> {
    tubelet_embed: Conv3d<B>,
    spatial_blocks: Vec<TransformerEncoder<B>>,
    temporal_blocks: Vec<TransformerEncoder<B>>,
    cls_token: Param<Tensor<B, 1>>,
}

impl<B: Backend> ViViT<B> {
    pub fn forward(&self, video: Tensor<B, 5>) -> Tensor<B, 2> {
        // Input: [batch, time, channels, height, width]
        let [B, T, C, H, W] = video.dims();
        
        // 1. Tubelet embedding
        let tokens = self.tubelet_embed.forward(video);
        let [_, num_tokens, embed_dim] = tokens.dims();
        
        // 2. Spatial attention (per frame)
        let spatial_out = self.process_spatial(tokens, B, T);
        
        // 3. Temporal attention (across frames)
        let temporal_out = self.process_temporal(spatial_out, B, T);
        
        // 4. Classification head
        temporal_out.slice([0..B, 0..1, 0..embed_dim]).squeeze::<2>()
    }
    
    fn process_spatial(&self, tokens: Tensor<B, 3>, batch: usize, time: usize) -> Tensor<B, 3> {
        // Reshape to [B*T, num_patches, embed_dim]
        let merged = tokens.reshape([batch * time, num_patches, embed_dim]);
        
        // Apply spatial transformer
        let processed = self.spatial_blocks
            .iter()
            .fold(merged, |acc, block| block.forward(acc));
        
        // Reshape back to [B, T, num_patches, embed_dim]
        processed.reshape([batch, time, num_patches, embed_dim])
    }
}
```

**Priority 2: Visual Preprocessing** (1-2 days)
- [ ] Data augmentation (rotation, flip, crop)
- [ ] Normalization strategies
- [ ] Caching for training speedup
- [ ] Multi-scale GAF inputs

**Priority 3: Integration Testing** (1 day)
- [ ] End-to-end: OHLCV → GAF → ViViT → Embeddings
- [ ] Benchmark inference latency (target: <20ms)
- [ ] Memory profiling
- [ ] Gradient checking

#### Deliverables
- [ ] Full vision pipeline (GAF + ViViT)
- [ ] <20ms inference latency (p95)
- [ ] Visual embedding quality tests
- [ ] 100+ tests passing

#### CNS Metrics
```rust
janus_vision_gaf_frames_generated_total
janus_vision_vivit_inference_duration_seconds
janus_vision_embedding_dimension{layer="spatial|temporal"}
janus_vision_attention_weights_mean
```

### Week 7: Logic Tensor Networks (LTN)

**Goal:** Neuro-symbolic constraint satisfaction

#### Tasks

**Priority 1: Łukasiewicz Logic** (2-3 days)
- [ ] T-norm operators (and, or, not, implies)
- [ ] Smooth aggregation (product T-norm for gradients)
- [ ] Predicate networks
- [ ] Grounding mechanism
- [ ] Satisfiability loss

**Critical Fix (from research review):**
```rust
// WRONG (min has zero gradient for non-minimal inputs):
let satisfaction = rules.iter()
    .fold(Tensor::ones(.into()), |acc, rule| acc.min_pair(rule));

// CORRECT (product T-norm for smooth gradients):
pub struct ProductTNorm;

impl<B: Backend> TNorm<B> for ProductTNorm {
    fn and(&self, a: Tensor<B, 1>, b: Tensor<B, 1>) -> Tensor<B, 1> {
        a * b  // Smooth, always has gradient
    }
    
    fn or(&self, a: Tensor<B, 1>, b: Tensor<B, 1>) -> Tensor<B, 1> {
        a + b - (a * b)
    }
    
    fn implies(&self, a: Tensor<B, 1>, b: Tensor<B, 1>) -> Tensor<B, 1> {
        let not_a = Tensor::ones_like(&a) - a;
        self.or(not_a, b)
    }
}

// ALTERNATIVE (smooth min with LogSumExp):
fn smooth_min<B: Backend>(tensors: Vec<Tensor<B, 1>>, beta: f32) -> Tensor<B, 1> {
    let neg_tensors: Vec<_> = tensors.iter()
        .map(|t| -t * beta)
        .collect();
    -logsumexp(neg_tensors) / beta
}
```

**Priority 2: Trading Axioms** (2 days)
- [ ] Bullish/bearish predicates
- [ ] Risk limit constraints
- [ ] Liquidity requirements
- [ ] Regulatory compliance (wash sale, pattern day trader)
- [ ] Multi-axiom composition

**Priority 3: Gated Cross-Attention Fusion** (1-2 days)
- [ ] Vision-logic fusion mechanism
- [ ] Learned gating for constraint importance
- [ ] Multi-head attention
- [ ] Residual connections

#### Trading Axioms Example
```rust
pub struct TradingAxioms<B: Backend> {
    is_bullish: Predicate<B>,
    sufficient_liquidity: Predicate<B>,
    within_risk_limits: Predicate<B>,
    wash_sale_compliant: Predicate<B>,
}

impl<B: Backend> TradingAxioms<B> {
    pub fn buy_axiom(&self, state: &MarketState<B>) -> Tensor<B, 1> {
        let tnorm = ProductTNorm;
        
        // IF bullish AND sufficient_liquidity THEN within_risk_limits
        let bullish = self.is_bullish.forward(&state.features);
        let liquidity = self.sufficient_liquidity.forward(&state.orderbook);
        let risk_ok = self.within_risk_limits.forward(&state.position);
        
        let premise = tnorm.and(bullish, liquidity);
        tnorm.implies(premise, risk_ok)
    }
    
    pub fn compliance_axiom(&self, state: &MarketState<B>) -> Tensor<B, 1> {
        // MUST be wash-sale compliant (hard constraint)
        self.wash_sale_compliant.forward(&state.history)
    }
}
```

#### Deliverables
- [ ] Full LTN implementation
- [ ] 5+ trading axioms defined
- [ ] Differentiable constraint satisfaction
- [ ] Logic loss integration
- [ ] 120+ tests passing

#### CNS Metrics
```rust
janus_ltn_axiom_satisfaction{axiom="buy|sell|compliance"}
janus_ltn_predicate_confidence{predicate="bullish|liquidity|risk"}
janus_ltn_constraint_violations_total
janus_ltn_logic_loss
```

### Week 8: Training Pipeline & Memory

**Goal:** Complete learning system with experience replay

#### Tasks

**Priority 1: Prioritized Experience Replay** (2-3 days)
- [ ] SumTree data structure (cache-aligned)
- [ ] Priority-based sampling
- [ ] Importance sampling weights
- [ ] TD-error updates
- [ ] Concurrent access (lock-free)

**Lock-Free SumTree:**
```rust
use std::sync::atomic::{AtomicU64, Ordering};

#[repr(align(64))]  // Cache line alignment
struct CacheAligned<T>(T);

pub struct AtomicSumTree {
    capacity: usize,
    nodes: Vec<CacheAligned<AtomicU64>>,  // f64 as u64 bit pattern
}

impl AtomicSumTree {
    pub fn update(&self, idx: usize, priority: f64) {
        let bits = priority.to_bits();
        let tree_idx = self.capacity - 1 + idx;
        
        // Atomic update with CAS
        self.nodes[tree_idx].0.store(bits, Ordering::Release);
        
        // Propagate to root
        let mut current = tree_idx;
        while current > 0 {
            let parent = (current - 1) / 2;
            let left = 2 * parent + 1;
            let right = 2 * parent + 2;
            
            let left_val = f64::from_bits(self.nodes[left].0.load(Ordering::Acquire));
            let right_val = f64::from_bits(self.nodes.get(right)
                .map(|n| n.0.load(Ordering::Acquire))
                .unwrap_or(0));
            
            let sum = left_val + right_val;
            self.nodes[parent].0.store(sum.to_bits(), Ordering::Release);
            
            current = parent;
        }
    }
}
```

**Priority 2: Elastic Weight Consolidation (EWC)** (2 days)
- [ ] Fisher Information Matrix computation
- [ ] Importance weighting for parameters
- [ ] Continual learning loss term
- [ ] Catastrophic forgetting tests

**EWC Implementation:**
```rust
pub struct EWCRegularizer<B: Backend> {
    fisher: HashMap<String, Tensor<B, 1>>,
    optimal_params: HashMap<String, Tensor<B, 1>>,
    lambda: f32,
}

impl<B: Backend> EWCRegularizer<B> {
    pub fn compute_loss<M: Module<B>>(&self, model: &M) -> Tensor<B, 1> {
        let params = model.into_record();
        
        let mut ewc_loss = Tensor::zeros([1], &self.device);
        
        for (name, param) in params.iter() {
            if let (Some(fisher), Some(optimal)) = (
                self.fisher.get(name),
                self.optimal_params.get(name)
            ) {
                let diff = param - optimal;
                let weighted = fisher * diff.powf(2.0);
                ewc_loss = ewc_loss + weighted.sum();
            }
        }
        
        ewc_loss * self.lambda
    }
}
```

**Priority 3: Parametric UMAP Integration** (2-3 days)
- [ ] Integrate `fast-umap` crate (Rust-native, Burn-based)
- [ ] Neural network encoder for UMAP
- [ ] Manifold projection for live data
- [ ] Schema clustering (DBSCAN)
- [ ] Qdrant vector storage

**Priority 4: Backward Service Foundation** (1 day)
- [ ] Async consolidation scheduler
- [ ] Nightly training trigger
- [ ] Model versioning
- [ ] Experience buffer management

#### Deliverables
- [ ] Full PER implementation
- [ ] EWC for continual learning
- [ ] UMAP-based schema consolidation
- [ ] Backward service scaffolding
- [ ] 140+ tests passing

#### CNS Metrics
```rust
janus_memory_replay_buffer_size
janus_memory_replay_priority_mean
janus_memory_td_error_mean
janus_memory_schemas_total
janus_memory_ewc_loss
janus_backward_consolidation_duration_seconds
```

---

## Phase 3: Signal Generation & Integration (Weeks 9-12)

### Week 9: Neuromorphic Core Integration

**Goal:** Connect all brain modules via BrainBus

#### Tasks

**Priority 1: Basal Ganglia Implementation** (2-3 days)
- [ ] Direct pathway (D1 receptor model)
- [ ] Indirect pathway (D2 receptor model)
- [ ] Dopamine gating mechanism
- [ ] Action selection head
- [ ] Competitive dynamics

**Basal Ganglia:**
```rust
pub struct BasalGanglia<B: Backend> {
    direct: DirectPathway<B>,
    indirect: IndirectPathway<B>,
    dopamine_modulator: Linear<B>,
    action_head: Linear<B>,
}

impl<B: Backend> BasalGanglia<B> {
    pub fn forward(&self, 
        context: Tensor<B, 2>,
        dopamine: f32  // From Hypothalamus
    ) -> ActionOutput<B> {
        // Direct pathway: facilitates action
        let go_signal = self.direct.forward(context.clone());
        
        // Indirect pathway: inhibits action
        let nogo_signal = self.indirect.forward(context.clone());
        
        // Dopamine modulates the balance
        let modulated_go = go_signal * dopamine;
        let modulated_nogo = nogo_signal * (2.0 - dopamine);
        
        // Net action propensity
        let action_value = modulated_go - modulated_nogo;
        
        // Action probabilities
        let action_probs = self.action_head
            .forward(action_value)
            .softmax::<1>();
        
        ActionOutput {
            action_probs,
            go_strength: modulated_go.mean().into_scalar(),
            nogo_strength: modulated_nogo.mean().into_scalar(),
        }
    }
}
```

**Priority 2: Hypothalamus (Homeostasis)** (1-2 days)
- [ ] Risk state tracking (cortisol)
- [ ] Energy reserves (capital)
- [ ] PID controller for risk modulation
- [ ] Threat response (circuit breaker)

**Priority 3: Amygdala (Threat Detection)** (1-2 days)
- [ ] Conformal prediction for outliers
- [ ] Mahalanobis distance anomaly detection
- [ ] Fast-path circuit breaker
- [ ] Threat level quantification

**Amygdala with Conformal Prediction:**
```rust
pub struct Amygdala<B: Backend> {
    historical_embeddings: Tensor<B, 2>,  // [n_samples, embed_dim]
    quantiles: Tensor<B, 2>,              // [embed_dim, n_quantiles]
    alpha: f32,  // Significance level (e.g., 0.05 for 95% confidence)
}

impl<B: Backend> Amygdala<B> {
    pub fn detect_threat(&self, embedding: Tensor<B, 1>) -> ThreatLevel {
        // Compute Mahalanobis distance
        let mean = self.historical_embeddings.mean_dim(0);
        let diff = embedding - mean;
        let cov_inv = self.compute_covariance_inverse();
        let mahal_dist = (diff.clone().matmul(cov_inv).matmul(diff.transpose())).sqrt();
        
        // Conformal prediction set
        let distances = self.historical_embeddings
            .sub(embedding.unsqueeze())
            .norm(2, 1);
        let calibrated_threshold = distances.quantile(1.0 - self.alpha);
        
        // Threat classification
        let distance = mahal_dist.into_scalar();
        let threshold = calibrated_threshold.into_scalar();
        
        if distance > threshold * 3.0 {
            ThreatLevel::Critical  // Immediate circuit breaker
        } else if distance > threshold * 2.0 {
            ThreatLevel::High      // Reduce positions
        } else if distance > threshold {
            ThreatLevel::Moderate  // Increase caution
        } else {
            ThreatLevel::Normal
        }
    }
}
```

**Priority 4: BrainBus Message Passing** (1 day)
- [ ] Async channel architecture (flume)
- [ ] Signal routing
- [ ] Backpressure handling
- [ ] Observability hooks

#### Deliverables
- [ ] Complete Basal Ganglia
- [ ] Hypothalamus + Amygdala
- [ ] BrainBus integration
- [ ] Action selection validated
- [ ] 160+ tests passing

### Week 10: Backtest Infrastructure

**Goal:** Historical replay with realistic simulation

**Critical Addition (from research review):**

#### Tasks

**Priority 1: Order Book Simulator** (2-3 days)
- [ ] L2 order book replay from historical data
- [ ] Market/limit order simulation
- [ ] Slippage modeling
- [ ] Latency injection (realistic delays)

**Order Book Simulation:**
```rust
pub struct OrderBookSimulator {
    historical_books: VecDeque<OrderBookSnapshot>,
    current_time: DateTime<Utc>,
    latency_model: LatencyModel,
}

pub struct LatencyModel {
    pub exchange_processing: Duration,  // e.g., 5-15ms
    pub network_rtt: Duration,           // e.g., 20-100ms
    pub jitter_std: Duration,            // e.g., 5ms
}

impl OrderBookSimulator {
    pub fn simulate_order(&mut self, order: Order) -> SimulationResult {
        // 1. Add latency
        let execution_time = self.current_time + self.latency_model.sample();
        
        // 2. Find order book state at execution time
        let book = self.get_book_at(execution_time);
        
        // 3. Match against book
        let fills = match order.order_type {
            OrderType::Market => self.match_market_order(&order, &book),
            OrderType::Limit => self.match_limit_order(&order, &book),
        };
        
        // 4. Compute slippage
        let avg_fill_price = fills.iter()
            .map(|f| f.price * f.quantity)
            .sum::<f64>() / fills.iter().map(|f| f.quantity).sum::<f64>();
        
        let slippage = (avg_fill_price - order.expected_price).abs();
        
        SimulationResult {
            fills,
            slippage,
            execution_time,
            total_fees: self.compute_fees(&fills),
        }
    }
}
```

**Priority 2: PnL Tracking** (1-2 days)
- [ ] Realized PnL calculation
- [ ] Unrealized PnL mark-to-market
- [ ] Fee accounting
- [ ] Funding rate simulation (perpetual futures)
- [ ] Performance metrics (Sharpe, Sortino, max drawdown)

**Priority 3: Backtest Engine** (2 days)
- [ ] Event-driven simulation loop
- [ ] Multi-asset support
- [ ] Position management
- [ ] Risk limit enforcement
- [ ] Detailed execution log

**Priority 4: Validation & Metrics** (1 day)
- [ ] Backtest report generation
- [ ] Equity curve plotting
- [ ] Trade analysis
- [ ] Comparison with baselines

#### Deliverables
- [ ] Full backtest engine
- [ ] Realistic order simulation
- [ ] PnL tracking
- [ ] Performance analytics
- [ ] 180+ tests passing

### Week 11: Forward Service (Signal Generation)

**Goal:** Real-time inference service

#### Tasks

**Priority 1: Forward Service Core** (2-3 days)
- [ ] Async event loop (tokio)
- [ ] Market data subscription
- [ ] Inference pipeline orchestration
- [ ] Signal emission
- [ ] Latency optimization

**Forward Service Architecture:**
```rust
pub struct ForwardService<B: Backend> {
    // Models (read-only, loaded from checkpoints)
    vision: Arc<VisionPipeline<B>>,
    ltn: Arc<LtnEngine<B>>,
    basal_ganglia: Arc<BasalGanglia<B>>,
    
    // State
    market_state: DashMap<Symbol, MarketState>,
    schemas: Arc<SchemaCache>,
    
    // Communication
    market_rx: Receiver<MarketDataEvent>,
    signal_tx: Sender<TradingSignal>,
    
    // Metrics
    metrics: Arc<MetricsRegistry>,
}

impl<B: Backend> ForwardService<B> {
    pub async fn run(mut self) -> Result<()> {
        loop {
            tokio::select! {
                // Market data updates
                Some(event) = self.market_rx.recv() => {
                    self.handle_market_data(event).await?;
                }
                
                // Periodic inference trigger
                _ = tokio::time::sleep(self.config.inference_interval) => {
                    self.run_inference().await?;
                }
                
                // Graceful shutdown
                _ = self.shutdown_rx.recv() => {
                    info!("Shutting down forward service");
                    break;
                }
            }
        }
        Ok(())
    }
    
    async fn run_inference(&self) -> Result<()> {
        let start = Instant::now();
        
        for (symbol, state) in self.market_state.iter() {
            // 1. Vision: GAF + ViViT
            let visual_embedding = self.vision.process(state.history())?;
            
            // 2. LTN: Constraint satisfaction
            let axiom_sat = self.ltn.evaluate(&state, &visual_embedding)?;
            
            // 3. Schema retrieval
            let similar_schemas = self.schemas.search(&visual_embedding).await?;
            
            // 4. Basal Ganglia: Action selection
            let dopamine = self.hypothalamus.get_dopamine_level();
            let action = self.basal_ganglia.forward(visual_embedding, dopamine)?;
            
            // 5. Amygdala: Threat check
            let threat = self.amygdala.detect_threat(&visual_embedding)?;
            
            // 6. Generate signal
            if threat == ThreatLevel::Critical {
                // Circuit breaker override
                self.emit_signal(TradingSignal::emergency_stop(symbol))?;
            } else if axiom_sat > self.config.min_constraint_satisfaction {
                self.emit_signal(TradingSignal::from_action(symbol, action))?;
            }
        }
        
        // Record latency
        self.metrics.forward_inference_duration.observe(start.elapsed());
        
        Ok(())
    }
}
```

**Priority 2: Model Loading & Caching** (1-2 days)
- [ ] Checkpoint loading at startup
- [ ] Hot model reload (zero downtime)
- [ ] GPU memory management
- [ ] Model warmup routine

**Priority 3: Latency Optimization** (1-2 days)
- [ ] Batch inference across symbols
- [ ] Tensor pre-allocation
- [ ] Async I/O decoupling
- [ ] Profiling and flamegraphs

**Priority 4: Signal Output Format** (1 day)
- [ ] TradingSignal schema
- [ ] Kafka/Redis publication
- [ ] Signal history logging
- [ ] API endpoint for retrieval

#### Deliverables
- [ ] Production-ready Forward Service
- [ ] <50ms p99 inference latency
- [ ] Hot reload capability
- [ ] 200+ tests passing

### Week 12: Backward Service & CNS Expansion

**Goal:** Complete CNS observability and nightly consolidation

#### Tasks

**Priority 1: Backward Service** (2-3 days)
- [ ] Cron-based scheduling
- [ ] Experience buffer ingestion
- [ ] Schema consolidation (UMAP clustering)
- [ ] Model retraining
- [ ] Checkpoint versioning

**Backward Service:**
```rust
pub struct BackwardService<B: Backend> {
    config: BackwardConfig,
    replay_buffer: Arc<PrioritizedReplayBuffer<B>>,
    consolidator: SchemaConsolidator<B>,
    trainer: Trainer<B>,
}

impl<B: Backend> BackwardService<B> {
    pub async fn run(self) -> Result<()> {
        let consolidation_schedule = cron::Schedule::from_str(&self.config.consolidation_cron)?;
        let retraining_schedule = cron::Schedule::from_str(&self.config.retraining_cron)?;
        
        loop {
            tokio::select! {
                // Schema consolidation (e.g., every 4 hours)
                _ = self.wait_for_next(consolidation_schedule) => {
                    self.run_consolidation().await?;
                }
                
                // Model retraining (e.g., nightly at 2am)
                _ = self.wait_for_next(retraining_schedule) => {
                    self.run_retraining().await?;
                }
                
                _ = self.shutdown_rx.recv() => break,
            }
        }
        Ok(())
    }
    
    async fn run_consolidation(&self) -> Result<()> {
        let start = Instant::now();
        
        // 1. Sample experiences
        let experiences = self.replay_buffer.sample(10000)?;
        
        // 2. Extract embeddings
        let embeddings = self.extract_embeddings(&experiences)?;
        
        // 3. UMAP projection
        let projected = self.consolidator.project(embeddings).await?;
        
        // 4. Cluster into schemas
        let schemas = self.consolidator.cluster(&projected)?;
        
        // 5. Upload to Qdrant
        for schema in schemas {
            self.consolidator.upsert_schema(schema).await?;
        }
        
        self.metrics.backward_consolidation_duration.observe(start.elapsed());
        
        Ok(())
    }
    
    async fn run_retraining(&self) -> Result<()> {
        let start = Instant::now();
        
        // 1. Check if enough new experiences
        if self.replay_buffer.len() < self.config.min_experiences {
            info!("Insufficient experiences for retraining");
            return Ok(());
        }
        
        // 2. Create training datasets
        let (train_data, val_data) = self.create_datasets()?;
        
        // 3. Train model (with EWC to prevent forgetting)
        let history = self.trainer.fit_with_ewc(train_data, val_data)?;
        
        // 4. Evaluate on validation set
        let val_loss = history.best_val_loss;
        
        // 5. If improved, save checkpoint
        if val_loss < self.current_best_loss {
            let checkpoint_path = format!("checkpoints/model_v{}.bin", self.version);
            self.trainer.save_checkpoint(&checkpoint_path)?;
            
            // Signal Forward Service to reload
            self.model_update_tx.send(checkpoint_path).await?;
        }
        
        self.metrics.backward_training_duration.observe(start.elapsed());
        
        Ok(())
    }
}
```

**Priority 2: Full CNS Metrics** (2 days)
- [ ] 100+ Prometheus metrics
- [ ] Grafana dashboards (5+ dashboards)
- [ ] Alerting rules
- [ ] Health score computation

**Priority 3: Prometheus Alerting** (1 day)
- [ ] Critical alerts (system down, circuit breaker)
- [ ] Warning alerts (high latency, low satisfaction)
- [ ] Performance alerts (memory, GPU)

**Priority 4: Integration Testing** (1-2 days)
- [ ] Full pipeline test (data → signal → backtest)
- [ ] Performance benchmarks
- [ ] Stress testing
- [ ] Documentation updates

#### Deliverables
- [ ] Production Backward Service
- [ ] Complete CNS metrics (100+)
- [ ] Grafana dashboards
- [ ] Full integration tests
- [ ] 220+ tests passing

---

## Phase 4: Real Data Integration (Weeks 13-15)

**NEW PHASE:** Production data sources and operational data management

### Week 13: Live Exchange Integration

**Goal:** Real-time market data from production exchanges

#### Tasks

**Priority 1: Production Websocket Clients** (2-3 days)
- [ ] Binance production API
- [ ] Bybit production API
- [ ] Coinbase Pro API
- [ ] Authentication & API keys (from env/secrets)
- [ ] Rate limiting enforcement
- [ ] Connection health monitoring

**Production Exchange Client:**
```rust
pub struct ProductionExchangeClient {
    exchange: Exchange,
    api_key: String,
    api_secret: String,
    ws_url: String,
    subscriptions: Vec<Subscription>,
    
    // Connection management
    connection: Option<WebSocketStream>,
    reconnect_policy: ExponentialBackoff,
    heartbeat_interval: Duration,
    
    // Metrics
    metrics: Arc<MetricsRegistry>,
}

impl ProductionExchangeClient {
    pub async fn connect(&mut self) -> Result<()> {
        let start = Instant::now();
        
        // 1. Establish websocket connection
        let ws_stream = tokio_tungstenite::connect_async(&self.ws_url).await?;
        
        // 2. Authenticate (if required)
        if self.requires_auth() {
            self.send_auth_message(&ws_stream).await?;
        }
        
        // 3. Subscribe to channels
        for sub in &self.subscriptions {
            self.subscribe(&ws_stream, sub).await?;
        }
        
        // 4. Start heartbeat task
        self.spawn_heartbeat();
        
        self.connection = Some(ws_stream);
        self.metrics.data_websocket_connections.inc();
        self.metrics.data_websocket_connect_duration.observe(start.elapsed());
        
        Ok(())
    }
    
    pub async fn run(&mut self) -> Result<()> {
        loop {
            tokio::select! {
                // Incoming message
                Some(msg) = self.connection.as_mut().unwrap().next() => {
                    match msg? {
                        Message::Text(text) => self.handle_message(text).await?,
                        Message::Ping(_) => self.send_pong().await?,
                        Message::Close(_) => {
                            warn!("Connection closed by server");
                            self.reconnect().await?;
                        }
                        _ => {}
                    }
                }
                
                // Heartbeat timeout
                _ = tokio::time::sleep(self.heartbeat_interval * 2) => {
                    error!("Heartbeat timeout");
                    self.metrics.data_websocket_timeouts.inc();
                    self.reconnect().await?;
                }
            }
        }
    }
    
    async fn reconnect(&mut self) -> Result<()> {
        self.metrics.data_websocket_reconnects.inc();
        
        for attempt in self.reconnect_policy.iter() {
            warn!("Reconnecting in {:?} (attempt {})", attempt.duration, attempt.count);
            tokio::time::sleep(attempt.duration).await;
            
            match self.connect().await {
                Ok(_) => {
                    info!("Reconnected successfully");
                    return Ok(());
                }
                Err(e) => {
                    error!("Reconnect failed: {}", e);
                    continue;
                }
            }
        }
        
        Err(anyhow!("Failed to reconnect after max attempts"))
    }
}
```

**Priority 2: Historical Data Backfill** (2 days)
- [ ] REST API for historical data
- [ ] Bulk download orchestration
- [ ] Incremental updates
- [ ] Data validation on ingestion

**Priority 3: API Key Management** (1 day)
- [ ] Environment variable loading
- [ ] Secrets manager integration (AWS Secrets Manager / HashiCorp Vault)
- [ ] Key rotation support
- [ ] Audit logging

**Priority 4: Rate Limiting** (1 day)
- [ ] Token bucket algorithm
- [ ] Per-exchange limits
- [ ] Request queuing
- [ ] Backoff on 429 errors

#### Deliverables
- [ ] 3+ live exchange connections
- [ ] Historical data backfill
- [ ] Production-grade error handling
- [ ] 240+ tests passing

#### CNS Metrics
```rust
janus_exchange_websocket_connected{exchange="binance"}
janus_exchange_messages_received_total{exchange="binance",type="trade"}
janus_exchange_api_rate_limit_remaining{exchange="binance"}
janus_exchange_reconnects_total{exchange="binance"}
janus_exchange_latency_ms{exchange="binance",p="50|95|99"}
```

### Week 14: News & Alternative Data Production

**Goal:** Real-time news ingestion and sentiment analysis

#### Tasks

**Priority 1: RSS Feed Production Pipeline** (1-2 days)
- [ ] 20+ crypto news sources
- [ ] Feed polling scheduler
- [ ] Deduplication (content fingerprinting)
- [ ] Parallelized fetching

**RSS Sources:**
```toml
# config/news_sources.toml
[[rss]]
name = "CoinDesk"
url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
poll_interval = "5m"

[[rss]]
name = "CryptoSlate"
url = "https://cryptoslate.com/feed/"
poll_interval = "5m"

[[rss]]
name = "Decrypt"
url = "https://decrypt.co/feed"
poll_interval = "10m"

[[rss]]
name = "TheBlock"
url = "https://www.theblock.co/rss.xml"
poll_interval = "5m"

# ... 16 more sources
```

**Priority 2: Twitter/X API Integration** (2 days)
- [ ] Twitter API v2 client
- [ ] Account monitoring (key influencers)
- [ ] Keyword tracking (#Bitcoin, $BTC, etc.)
- [ ] Rate limit handling
- [ ] Real-time streaming

**Priority 3: Sentiment Model Deployment** (2-3 days)
- [ ] DistilBERT model loading
- [ ] GPU inference optimization
- [ ] Batch processing
- [ ] Caching for duplicate content

**Production Sentiment Pipeline:**
```rust
pub struct SentimentAnalyzer {
    model: DistilBertModel,
    tokenizer: Tokenizer,
    batch_size: usize,
    device: Device,
}

impl SentimentAnalyzer {
    pub async fn analyze_batch(&self, articles: Vec<String>) -> Result<Vec<SentimentScore>> {
        // 1. Tokenize
        let inputs = self.tokenizer.encode_batch(&articles)?;
        
        // 2. Create tensors
        let input_ids = Tensor::from_data(inputs.ids(), &self.device);
        let attention_mask = Tensor::from_data(inputs.attention_mask(), &self.device);
        
        // 3. Forward pass (no gradients needed)
        let outputs = self.model.forward_no_grad(input_ids, attention_mask)?;
        
        // 4. Extract scores
        let logits = outputs.logits;
        let probs = logits.softmax::<1>();
        
        // 5. Parse to sentiment scores
        let scores = probs.into_data()
            .to_vec()?
            .chunks(3)  // [negative, neutral, positive]
            .map(|chunk| SentimentScore {
                negative: chunk[0],
                neutral: chunk[1],
                positive: chunk[2],
                compound: chunk[2] - chunk[0],
                confidence: chunk.iter().max().unwrap(),
            })
            .collect();
        
        Ok(scores)
    }
}
```

**Priority 4: Alternative Data Sources** (1-2 days)
- [ ] Fear & Greed Index API
- [ ] Whale Alert integration
- [ ] ETF flow data
- [ ] On-chain metrics (Glassnode/CryptoQuant APIs)

#### Deliverables
- [ ] 20+ news sources ingesting
- [ ] Twitter real-time streaming
- [ ] Production sentiment analysis
- [ ] Alternative data integrated
- [ ] 260+ tests passing

### Week 15: Data Management & Governance

**Goal:** Production-grade data infrastructure

#### Tasks

**Priority 1: QuestDB Production Setup** (1-2 days)
- [ ] Cluster deployment
- [ ] Replication configuration
- [ ] Backup strategy
- [ ] Query optimization

**QuestDB Schema (Optimized):**
```sql
-- Market data (partitioned by day)
CREATE TABLE market_data (
    timestamp TIMESTAMP,
    symbol SYMBOL CAPACITY 500 CACHE,
    exchange SYMBOL CAPACITY 50 CACHE,
    price DOUBLE,
    quantity DOUBLE,
    side SYMBOL CAPACITY 2 CACHE,
    trade_id LONG
) TIMESTAMP(timestamp) PARTITION BY DAY;

-- Indexed for fast queries
CREATE INDEX idx_symbol_timestamp ON market_data (symbol, timestamp);

-- Order book snapshots (partitioned by hour due to volume)
CREATE TABLE order_book (
    timestamp TIMESTAMP,
    symbol SYMBOL CAPACITY 500 CACHE,
    exchange SYMBOL CAPACITY 50 CACHE,
    sequence LONG,
    bids STRING,  -- JSON array
    asks STRING   -- JSON array
) TIMESTAMP(timestamp) PARTITION BY HOUR;

-- News articles
CREATE TABLE news_articles (
    timestamp TIMESTAMP,
    id SYMBOL CAPACITY 1000000 CACHE,
    source SYMBOL CAPACITY 100 CACHE,
    title STRING,
    content STRING,
    sentiment_compound DOUBLE,
    sentiment_positive DOUBLE,
    sentiment_negative DOUBLE,
    relevance DOUBLE,
    entities STRING  -- JSON array
) TIMESTAMP(timestamp) PARTITION BY DAY;

-- Quality metrics
CREATE TABLE data_quality (
    timestamp TIMESTAMP,
    symbol SYMBOL CAPACITY 500 CACHE,
    exchange SYMBOL CAPACITY 50 CACHE,
    quality_score DOUBLE,
    anomalies_detected INT,
    records_cleaned INT,
    issues STRING  -- JSON array
) TIMESTAMP(timestamp) PARTITION BY DAY;
```

**Priority 2: Data Retention & Archival** (1-2 days)
- [ ] Automated retention policies
- [ ] S3/GCS archival
- [ ] Restoration procedures
- [ ] Compliance logging

**Priority 3: Data Quality Automation** (2 days)
- [ ] Continuous quality monitoring
- [ ] Automated backfill on gaps
- [ ] Anomaly alerting
- [ ] Quality dashboard

**Priority 4: Data Governance** (1 day)
- [ ] Data catalog
- [ ] Lineage tracking
- [ ] Access controls
- [ ] Audit trails

#### Deliverables
- [ ] Production QuestDB cluster
- [ ] Automated retention/archival
- [ ] Quality monitoring dashboard
- [ ] 280+ tests passing

---

## Phase 5: Production ML Pipeline (Weeks 16-18)

**NEW PHASE:** MLOps, model registry, and automated retraining

### Week 16: MLOps Infrastructure

**Goal:** Production-grade ML lifecycle management

#### Tasks

**Priority 1: Model Registry** (2-3 days)
- [ ] Versioned model storage
- [ ] Metadata tracking (metrics, hyperparameters)
- [ ] Checkpoint management
- [ ] Model promotion workflow (dev → staging → prod)

**Model Registry:**
```rust
pub struct ModelRegistry {
    storage: S3Client,
    metadata_db: PostgresPool,
}

pub struct ModelVersion {
    pub id: Uuid,
    pub name: String,
    pub version: String,
    pub created_at: DateTime<Utc>,
    pub metrics: HashMap<String, f64>,
    pub hyperparameters: serde_json::Value,
    pub artifact_uri: String,
    pub stage: ModelStage,
}

pub enum ModelStage {
    Development,
    Staging,
    Production,
    Archived,
}

impl ModelRegistry {
    pub async fn register_model(
        &self,
        name: &str,
        checkpoint_path: &Path,
        metrics: HashMap<String, f64>,
        hyperparameters: serde_json::Value,
    ) -> Result<ModelVersion> {
        // 1. Generate version ID
        let version = format!("v{}", Utc::now().timestamp());
        
        // 2. Upload checkpoint to S3
        let artifact_uri = format!("s3://janus-models/{}/{}/model.bin", name, version);
        self.upload_checkpoint(checkpoint_path, &artifact_uri).await?;
        
        // 3. Store metadata
        let model_version = ModelVersion {
            id: Uuid::new_v4(),
            name: name.to_string(),
            version,
            created_at: Utc::now(),
            metrics,
            hyperparameters,
            artifact_uri,
            stage: ModelStage::Development,
        };
        
        self.save_metadata(&model_version).await?;
        
        Ok(model_version)
    }
    
    pub async fn promote_model(&self, id: Uuid, stage: ModelStage) -> Result<()> {
        // Validation checks before promotion
        if stage == ModelStage::Production {
            self.validate_production_readiness(id).await?;
        }
        
        // Update stage
        self.update_stage(id, stage).await?;
        
        Ok(())
    }
}
```

**Priority 2: Experiment Tracking** (1-2 days)
- [ ] Integration with MLflow or custom tracker
- [ ] Hyperparameter logging
- [ ] Metrics visualization
- [ ] Comparison tooling

**Priority 3: Automated Retraining** (2-3 days)
- [ ] Trigger conditions (performance degradation, data drift)
- [ ] Hyperparameter search (Optuna)
- [ ] Distributed training (multi-GPU)
- [ ] Automatic model selection

**Automated Retraining:**
```rust
pub struct RetrainingOrchestrator {
    registry: Arc<ModelRegistry>,
    trainer: Arc<Trainer>,
    drift_detector: DriftDetector,
}

impl RetrainingOrchestrator {
    pub async fn check_and_retrain(&self) -> Result<()> {
        // 1. Check if retraining needed
        let needs_retraining = self.should_retrain().await?;
        
        if !needs_retraining {
            info!("No retraining needed");
            return Ok(());
        }
        
        info!("Starting automated retraining");
        
        // 2. Hyperparameter search with Optuna
        let best_hparams = self.hyperparameter_search().await?;
        
        // 3. Train model with best hyperparameters
        let checkpoint = self.trainer.train(best_hparams).await?;
        
        // 4. Evaluate on validation set
        let metrics = self.trainer.evaluate(&checkpoint).await?;
        
        // 5. Register new model version
        let model_version = self.registry.register_model(
            "janus_lstm",
            &checkpoint,
            metrics,
            serde_json::to_value(&best_hparams)?,
        ).await?;
        
        // 6. If metrics improved, promote to staging
        if metrics["val_loss"] < self.current_best_loss {
            self.registry.promote_model(model_version.id, ModelStage::Staging).await?;
            
            // Trigger staging deployment for A/B testing
            self.deploy_to_staging(model_version).await?;
        }
        
        Ok(())
    }
    
    async fn should_retrain(&self) -> Result<bool> {
        // Check multiple conditions
        let performance_degraded = self.check_performance_degradation().await?;
        let data_drift = self.drift_detector.detect_drift().await?;
        let scheduled_time = self.is_scheduled_retrain_time();
        
        Ok(performance_degraded || data_drift || scheduled_time)
    }
}
```

**Priority 4: Data Drift Detection** (1-2 days)
- [ ] Feature distribution monitoring
- [ ] KS test for drift
- [ ] Alerting on significant drift
- [ ] Automatic dataset refresh

#### Deliverables
- [ ] Model registry operational
- [ ] Automated retraining pipeline
- [ ] Drift detection
- [ ] 300+ tests passing

### Week 17: A/B Testing & Canary Deployments

**Goal:** Safe model rollout with performance validation

#### Tasks

**Priority 1: A/B Testing Framework** (2-3 days)
- [ ] Traffic splitting (Champion vs. Challenger)
- [ ] Metrics collection per model
- [ ] Statistical significance testing
- [ ] Automatic rollback on degradation

**A/B Testing:**
```rust
pub struct ABTestConfig {
    pub name: String,
    pub champion_model: ModelVersion,
    pub challenger_model: ModelVersion,
    pub traffic_split: f32,  // 0.0-1.0, % to challenger
    pub metrics: Vec<String>,
    pub min_samples: usize,
    pub confidence_level: f32,  // e.g., 0.95
}

pub struct ABTestManager {
    tests: DashMap<String, ABTestConfig>,
    metrics_collector: Arc<MetricsCollector>,
}

impl ABTestManager {
    pub async fn route_inference(
        &self,
        test_name: &str,
        input: Tensor,
    ) -> Result<Tensor> {
        let test = self.tests.get(test_name).unwrap();
        
        // Deterministic routing based on input hash
        let hash = self.hash_input(&input);
        let use_challenger = (hash % 100)