# 🧠 JANUS Neuromorphic Trading System - 3-Phase Implementation Plan

**Project:** FKS Trading Platform - JANUS Neuromorphic Architecture  
**Created:** 2024  
**Status:** 🚧 In Progress (~30% Complete)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Phase 1: Foundation](#phase-1-foundation)
3. [Phase 2: Core Features](#phase-2-core-features)
4. [Phase 3: Production Readiness](#phase-3-production-readiness)
5. [Timeline & Milestones](#timeline--milestones)
6. [Success Criteria](#success-criteria)
7. [Risk Mitigation](#risk-mitigation)

---

## 🎯 Overview

### Current State

**What Exists:**
- ✅ Rust workspace structure with Cargo
- ✅ 10 brain region directories created
- ✅ Core dependencies configured (Tokio, Candle, ndarray)
- ✅ Basic service skeleton (forward, backward, gateway)
- ✅ Partial LTN (Logic Tensor Network) implementation
- ✅ Basic ReplayBuffer structure
- ✅ DiffGAF module structure
- ✅ Qdrant integration points defined

**What's Missing:**
- ❌ ONNX inference pipeline
- ❌ Complete DiffGAF transformation
- ❌ Full LTN constraint engine
- ❌ Prioritized replay buffer
- ❌ Qdrant schema storage implementation
- ❌ Production-grade testing & monitoring

### Architecture Principles

1. **Safety First** - Kill switches before features
2. **Incremental Development** - Each phase is independently deployable
3. **Test-Driven** - Write tests before implementation
4. **Brain-Inspired Organization** - Clear separation of concerns
5. **Production Ready** - Performance, monitoring, and documentation from day one

---

## 🏗️ Phase 1: Foundation

**Duration:** 2-3 weeks  
**Goal:** Establish robust foundation with core infrastructure

### 1.1 Set Up Rust Workspace with Cargo

**Status:** ✅ Partially Complete

#### Tasks:

- [x] **1.1.1** Create workspace structure in `src/janus/Cargo.toml`
- [x] **1.1.2** Define workspace members (crates + services)
- [ ] **1.1.3** Configure workspace dependencies
  ```toml
  [workspace.dependencies]
  # ML/AI
  candle-core = "0.3"
  candle-nn = "0.3"
  ort = "1.16"  # ONNX Runtime for Rust
  ndarray = "0.15"
  
  # Async Runtime
  tokio = { version = "1.35", features = ["full"] }
  
  # Vector Database
  qdrant-client = "1.7"
  
  # Serialization
  serde = { version = "1.0", features = ["derive"] }
  serde_json = "1.0"
  bincode = "1.3"
  
  # Error Handling
  anyhow = "1.0"
  thiserror = "1.0"
  ```

- [ ] **1.1.4** Add neuromorphic crate to workspace
  ```bash
  cd src/janus
  cargo add --package janus-neuromorphic ort ndarray qdrant-client
  ```

- [ ] **1.1.5** Verify workspace builds
  ```bash
  cargo check --workspace
  cargo build --workspace --all-features
  ```

**Deliverables:**
- ✅ Clean workspace build
- ✅ All dependencies resolved
- ✅ CI/CD pipeline validates workspace

---

### 1.2 Implement Core Data Structures

**Status:** 🟡 In Progress

#### Tasks:

- [ ] **1.2.1** Define shared types in `crates/common/src/types.rs`
  ```rust
  // Market data structures
  pub struct Tick {
      pub symbol: String,
      pub price: Price,
      pub volume: Volume,
      pub timestamp: DateTime<Utc>,
      pub bid: Option<Price>,
      pub ask: Option<Price>,
  }
  
  pub struct OrderBook {
      pub symbol: String,
      pub bids: Vec<(Price, Volume)>,
      pub asks: Vec<(Price, Volume)>,
      pub timestamp: DateTime<Utc>,
  }
  
  pub struct Trade {
      pub symbol: String,
      pub price: Price,
      pub volume: Volume,
      pub side: OrderSide,
      pub timestamp: DateTime<Utc>,
  }
  ```

- [ ] **1.2.2** Create experience structure for replay buffer
  ```rust
  // neuromorphic/hippocampus/buffer.rs
  #[derive(Clone, Debug, Serialize, Deserialize)]
  pub struct Experience {
      pub state: State,           // Market state (GAF-encoded)
      pub action: Action,          // Order/position action
      pub reward: f32,             // PnL or shaped reward
      pub next_state: State,       // Next market state
      pub done: bool,              // Episode termination
      pub priority: f32,           // For prioritized replay
      pub timestamp: DateTime<Utc>,
  }
  
  #[derive(Clone, Debug, Serialize, Deserialize)]
  pub struct State {
      pub gaf_features: Array2<f32>,  // 2D GAF image
      pub raw_features: Vec<f32>,      // Supplementary features
      pub metadata: StateMetadata,
  }
  
  #[derive(Clone, Debug, Serialize, Deserialize)]
  pub struct Action {
      pub action_type: ActionType,
      pub symbol: String,
      pub quantity: f32,
      pub price: Option<f32>,
  }
  
  #[derive(Clone, Debug, Serialize, Deserialize)]
  pub enum ActionType {
      Buy,
      Sell,
      Hold,
      Close,
  }
  ```

- [ ] **1.2.3** Define schema types for Qdrant storage
  ```rust
  // neuromorphic/integration/schema.rs
  use qdrant_client::qdrant::{PointStruct, Vector};
  
  pub struct MarketPatternSchema {
      pub id: String,
      pub embedding: Vec<f32>,      // GAF or learned embedding
      pub metadata: PatternMetadata,
  }
  
  pub struct StrategySchema {
      pub id: String,
      pub parameters: Vec<f32>,
      pub performance_metrics: PerformanceMetrics,
      pub conditions: Vec<String>,
  }
  ```

- [ ] **1.2.4** Create signal and order structures
  ```rust
  // Already exists in crates/common, verify completeness
  pub struct Signal {
      pub symbol: String,
      pub direction: SignalDirection,
      pub strength: f32,           // [0.0, 1.0]
      pub confidence: f32,         // [0.0, 1.0]
      pub timestamp: DateTime<Utc>,
      pub metadata: HashMap<String, Value>,
  }
  ```

**Deliverables:**
- ✅ Common types compile without errors
- ✅ Serialization/deserialization tests pass
- ✅ Type conversions implemented

---

### 1.3 Create ONNX Inference Pipeline

**Status:** ❌ Not Started

#### Tasks:

- [ ] **1.3.1** Add ONNX Runtime dependency
  ```toml
  # neuromorphic/Cargo.toml
  [dependencies]
  ort = { version = "1.16", features = ["load-dynamic"] }
  ```

- [ ] **1.3.2** Create ONNX model loader
  ```rust
  // neuromorphic/basal_ganglia/onnx_inference.rs
  use ort::{Environment, Session, SessionBuilder, Value};
  use ndarray::{Array, ArrayD, IxDyn};
  
  pub struct ONNXInferenceEngine {
      environment: Environment,
      session: Session,
      input_name: String,
      output_name: String,
  }
  
  impl ONNXInferenceEngine {
      pub fn new(model_path: &str) -> Result<Self> {
          let environment = Environment::builder()
              .with_name("janus")
              .with_log_level(ort::LoggingLevel::Warning)
              .build()?;
          
          let session = SessionBuilder::new(&environment)?
              .with_optimization_level(ort::GraphOptimizationLevel::Level3)?
              .with_intra_threads(4)?
              .with_model_from_file(model_path)?;
          
          // Get input/output names from model
          let input_name = session.inputs[0].name.clone();
          let output_name = session.outputs[0].name.clone();
          
          Ok(Self {
              environment,
              session,
              input_name,
              output_name,
          })
      }
      
      pub fn infer(&self, input: &Array2<f32>) -> Result<Array1<f32>> {
          // Prepare input tensor
          let shape = input.shape();
          let input_tensor = Value::from_array(
              self.session.allocator(),
              &input.clone().into_dyn()
          )?;
          
          // Run inference
          let outputs = self.session.run(vec![input_tensor])?;
          
          // Extract output
          let output_tensor = outputs[0].try_extract()?;
          let output_array: ArrayD<f32> = output_tensor.view().to_owned();
          
          Ok(output_array.into_dimensionality::<Ix1>()?)
      }
  }
  ```

- [ ] **1.3.3** Integrate with Basal Ganglia (action selection)
  ```rust
  // neuromorphic/basal_ganglia/actor_critic.rs
  pub struct ActorCritic {
      policy_network: ONNXInferenceEngine,
      value_network: ONNXInferenceEngine,
  }
  
  impl ActorCritic {
      pub async fn select_action(&self, state: &State) -> Result<Action> {
          // Get action probabilities from policy network
          let action_logits = self.policy_network.infer(&state.gaf_features)?;
          let action_probs = softmax(&action_logits);
          
          // Sample action
          let action_idx = sample_categorical(&action_probs);
          
          // Convert to Action struct
          let action = self.index_to_action(action_idx, state)?;
          
          Ok(action)
      }
      
      pub async fn evaluate_state(&self, state: &State) -> Result<f32> {
          // Get state value from value network
          let value = self.value_network.infer(&state.gaf_features)?;
          Ok(value[0])
      }
  }
  ```

- [ ] **1.3.4** Add model versioning and hot-reloading
  ```rust
  pub struct ModelRegistry {
      models: Arc<RwLock<HashMap<String, ONNXInferenceEngine>>>,
      model_dir: PathBuf,
  }
  
  impl ModelRegistry {
      pub async fn reload_model(&self, model_name: &str) -> Result<()> {
          let model_path = self.model_dir.join(format!("{}.onnx", model_name));
          let new_model = ONNXInferenceEngine::new(model_path.to_str().unwrap())?;
          
          let mut models = self.models.write().await;
          models.insert(model_name.to_string(), new_model);
          
          info!("Reloaded model: {}", model_name);
          Ok(())
      }
  }
  ```

- [ ] **1.3.5** Write inference benchmarks
  ```rust
  #[cfg(test)]
  mod benches {
      use super::*;
      use std::time::Instant;
      
      #[test]
      fn bench_inference_latency() {
          let engine = ONNXInferenceEngine::new("models/policy.onnx").unwrap();
          let input = Array2::zeros((1, 64));
          
          let start = Instant::now();
          for _ in 0..1000 {
              let _ = engine.infer(&input).unwrap();
          }
          let elapsed = start.elapsed();
          
          let avg_latency = elapsed.as_micros() / 1000;
          println!("Average inference latency: {} μs", avg_latency);
          assert!(avg_latency < 1000); // < 1ms per inference
      }
  }
  ```

**Deliverables:**
- ✅ ONNX models load successfully
- ✅ Inference latency < 1ms (p99)
- ✅ GPU acceleration enabled (if available)
- ✅ Model hot-reloading works

---

### 1.4 Build Basic Async Service Skeleton

**Status:** 🟡 Partially Complete

#### Tasks:

- [x] **1.4.1** Create service directories (forward, backward, gateway)

- [ ] **1.4.2** Implement async event loop for forward service
  ```rust
  // services/forward/src/main.rs
  #[tokio::main]
  async fn main() -> Result<()> {
      // Initialize tracing
      tracing_subscriber::fmt()
          .with_env_filter("forward=debug,janus=info")
          .init();
      
      info!("Starting Forward Service (Wake Cycle)");
      
      // Load configuration
      let config = Config::load()?;
      
      // Initialize neuromorphic engine
      let engine = TradingEngine::new(config.clone()).await?;
      
      // Start market data receiver
      let (market_tx, market_rx) = mpsc::channel(1000);
      tokio::spawn(market_data_loop(config.clone(), market_tx));
      
      // Start signal receiver (from gateway)
      let (signal_tx, signal_rx) = mpsc::channel(100);
      tokio::spawn(signal_receiver_loop(config.clone(), signal_tx));
      
      // Main event loop
      engine.run(market_rx, signal_rx).await?;
      
      Ok(())
  }
  
  async fn market_data_loop(
      config: Config,
      tx: mpsc::Sender<Tick>
  ) -> Result<()> {
      // Connect to market data source
      let mut stream = connect_market_stream(&config).await?;
      
      while let Some(tick) = stream.next().await {
          tx.send(tick?).await?;
      }
      
      Ok(())
  }
  ```

- [ ] **1.4.3** Implement backward service skeleton (sleep cycle)
  ```rust
  // services/backward/src/main.rs
  #[tokio::main]
  async fn main() -> Result<()> {
      info!("Starting Backward Service (Sleep Cycle)");
      
      let config = Config::load()?;
      let trainer = TrainingOrchestrator::new(config).await?;
      
      // Run training loop
      loop {
          // Load recent experiences from Qdrant
          let experiences = trainer.load_recent_experiences(1000).await?;
          
          if experiences.len() >= 256 {
              // Train model
              trainer.train_step(&experiences).await?;
              
              // Save updated model
              trainer.save_checkpoint().await?;
          }
          
          // Sleep for training interval
          tokio::time::sleep(Duration::from_secs(300)).await;
      }
  }
  ```

- [ ] **1.4.4** Add health check endpoints
  ```rust
  // services/forward/src/health.rs
  use axum::{Router, routing::get, Json};
  
  pub fn health_routes() -> Router {
      Router::new()
          .route("/health", get(health_check))
          .route("/ready", get(readiness_check))
  }
  
  async fn health_check() -> Json<HealthStatus> {
      Json(HealthStatus {
          status: "healthy".to_string(),
          service: "forward".to_string(),
          timestamp: Utc::now(),
      })
  }
  
  async fn readiness_check() -> Json<ReadinessStatus> {
      // Check all dependencies
      let qdrant_ok = check_qdrant().await;
      let redis_ok = check_redis().await;
      let model_loaded = check_model().await;
      
      Json(ReadinessStatus {
          ready: qdrant_ok && redis_ok && model_loaded,
          checks: vec![
              ("qdrant", qdrant_ok),
              ("redis", redis_ok),
              ("model", model_loaded),
          ],
      })
  }
  ```

- [ ] **1.4.5** Add graceful shutdown
  ```rust
  // services/forward/src/main.rs
  async fn shutdown_signal() {
      let ctrl_c = async {
          signal::ctrl_c()
              .await
              .expect("failed to install Ctrl+C handler");
      };
      
      #[cfg(unix)]
      let terminate = async {
          signal::unix::signal(signal::unix::SignalKind::terminate())
              .expect("failed to install signal handler")
              .recv()
              .await;
      };
      
      #[cfg(not(unix))]
      let terminate = std::future::pending::<()>();
      
      tokio::select! {
          _ = ctrl_c => {},
          _ = terminate => {},
      }
      
      info!("Shutdown signal received, cleaning up...");
  }
  ```

**Deliverables:**
- ✅ Services start and respond to health checks
- ✅ Graceful shutdown works
- ✅ Services can be deployed independently

---

## 🎨 Phase 2: Core Features

**Duration:** 3-4 weeks  
**Goal:** Implement brain-inspired intelligence components

### 2.1 Implement DiffGAF Transformation

**Status:** 🟡 Structure exists, needs implementation

**Location:** `neuromorphic/visual_cortex/gaf/`

#### Tasks:

- [ ] **2.1.1** Complete Gramian Angular Field implementation
  ```rust
  // neuromorphic/visual_cortex/gaf/differentiable.rs
  use ndarray::{Array1, Array2, Axis};
  use std::f32::consts::PI;
  
  pub struct DiffGAF {
      pub image_size: usize,
      pub method: GafMethod,
      pub sample_range: (f32, f32),
  }
  
  #[derive(Clone, Copy, Debug)]
  pub enum GafMethod {
      Summation,    // GASF
      Difference,   // GADF
  }
  
  impl DiffGAF {
      pub fn new(image_size: usize, method: GafMethod) -> Self {
          Self {
              image_size,
              method,
              sample_range: (-1.0, 1.0),
          }
      }
      
      /// Encode time series to GAF image
      pub fn encode(&self, timeseries: &Array1<f32>) -> Result<Array2<f32>> {
          // 1. Normalize to [-1, 1]
          let normalized = self.normalize(timeseries)?;
          
          // 2. Piecewise Aggregation Approximation (PAA)
          let paa = self.paa(&normalized)?;
          
          // 3. Convert to polar coordinates
          let phi = paa.mapv(|x| x.acos());
          
          // 4. Compute Gramian matrix
          let gaf = match self.method {
              GafMethod::Summation => self.gasf(&phi)?,
              GafMethod::Difference => self.gadf(&phi)?,
          };
          
          Ok(gaf)
      }
      
      fn normalize(&self, data: &Array1<f32>) -> Result<Array1<f32>> {
          let min = data.iter().cloned().fold(f32::INFINITY, f32::min);
          let max = data.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
          
          if (max - min).abs() < 1e-6 {
              return Ok(Array1::zeros(data.len()));
          }
          
          let (r_min, r_max) = self.sample_range;
          let normalized = data.mapv(|x| {
              ((x - min) / (max - min)) * (r_max - r_min) + r_min
          });
          
          Ok(normalized)
      }
      
      fn paa(&self, data: &Array1<f32>) -> Result<Array1<f32>> {
          let n = data.len();
          let m = self.image_size;
          let segment_size = n as f32 / m as f32;
          
          let mut paa = Array1::zeros(m);
          
          for i in 0..m {
              let start = (i as f32 * segment_size) as usize;
              let end = ((i + 1) as f32 * segment_size).min(n as f32) as usize;
              
              let segment = data.slice(s![start..end]);
              paa[i] = segment.mean().unwrap_or(0.0);
          }
          
          Ok(paa)
      }
      
      fn gasf(&self, phi: &Array1<f32>) -> Result<Array2<f32>> {
          let n = phi.len();
          let mut gasf = Array2::zeros((n, n));
          
          for i in 0..n {
              for j in 0..n {
                  gasf[[i, j]] = (phi[i] + phi[j]).cos();
              }
          }
          
          Ok(gasf)
      }
      
      fn gadf(&self, phi: &Array1<f32>) -> Result<Array2<f32>> {
          let n = phi.len();
          let mut gadf = Array2::zeros((n, n));
          
          for i in 0..n {
              for j in 0..n {
                  gadf[[i, j]] = (phi[i] - phi[j]).sin();
              }
          }
          
          Ok(gadf)
      }
  }
  ```

- [ ] **2.1.2** Add gradient computation for backpropagation
  ```rust
  impl DiffGAF {
      /// Compute gradients for end-to-end training
      pub fn backward(&self, grad_output: &Array2<f32>) -> Result<Array1<f32>> {
          // Implement reverse-mode autodiff
          // This allows GAF encoding to be part of trainable pipeline
          todo!("Implement gradient computation")
      }
  }
  ```

- [ ] **2.1.3** Create multivariate GAF (for multi-feature encoding)
  ```rust
  pub struct MultivariateDiffGAF {
      encoders: Vec<DiffGAF>,
  }
  
  impl MultivariateDiffGAF {
      pub fn encode_multi(&self, data: &Array2<f32>) -> Result<Array3<f32>> {
          let n_features = data.ncols();
          let mut encoded = Vec::new();
          
          for i in 0..n_features {
              let feature = data.column(i).to_owned();
              let gaf = self.encoders[i].encode(&feature)?;
              encoded.push(gaf);
          }
          
          // Stack into 3D tensor [features, height, width]
          Ok(stack_arrays(encoded)?)
      }
  }
  ```

- [ ] **2.1.4** Optimize with SIMD/parallel processing
  ```rust
  use rayon::prelude::*;
  
  impl DiffGAF {
      pub fn encode_batch(&self, batch: &[Array1<f32>]) -> Result<Vec<Array2<f32>>> {
          batch.par_iter()
              .map(|ts| self.encode(ts))
              .collect()
      }
  }
  ```

- [ ] **2.1.5** Write comprehensive tests
  ```rust
  #[cfg(test)]
  mod tests {
      use super::*;
      use approx::assert_relative_eq;
      
      #[test]
      fn test_encode_sine_wave() {
          let gaf = DiffGAF::new(32, GafMethod::Summation);
          let t: Array1<f32> = Array1::linspace(0.0, 2.0 * PI, 100);
          let signal = t.mapv(|x| x.sin());
          
          let encoded = gaf.encode(&signal).unwrap();
          
          assert_eq!(encoded.shape(), &[32, 32]);
          assert!(encoded.iter().all(|&x| x >= -1.0 && x <= 1.0));
      }
      
      #[test]
      fn test_gasf_vs_gadf() {
          let signal = Array1::from_vec(vec![1.0, 2.0, 3.0, 4.0, 5.0]);
          
          let gasf_encoder = DiffGAF::new(5, GafMethod::Summation);
          let gadf_encoder = DiffGAF::new(5, GafMethod::Difference);
          
          let gasf = gasf_encoder.encode(&signal).unwrap();
          let gadf = gadf_encoder.encode(&signal).unwrap();
          
          // GASF and GADF should be different
          assert!(!gasf.iter().zip(gadf.iter()).all(|(a, b)| (a - b).abs() < 1e-6));
      }
  }
  ```

**Deliverables:**
- ✅ DiffGAF encodes time series correctly
- ✅ Performance: > 1000 encodings/sec
- ✅ Tests validate against known patterns

---

### 2.2 Build LTN Constraint Engine

**Status:** 🟡 Basic structure exists, needs completion

**Location:** `neuromorphic/prefrontal/ltn/`

#### Tasks:

- [ ] **2.2.1** Implement Łukasiewicz logic operators
  ```rust
  // neuromorphic/prefrontal/ltn/fuzzy_logic.rs
  
  /// Łukasiewicz T-Norm (fuzzy AND)
  pub fn lukasiewicz_and(a: f32, b: f32) -> f32 {
      (a + b - 1.0).max(0.0)
  }
  
  /// Łukasiewicz T-Conorm (fuzzy OR)
  pub fn lukasiewicz_or(a: f32, b: f32) -> f32 {
      (a + b).min(1.0)
  }
  
  /// Fuzzy NOT
  pub fn fuzzy_not(a: f32) -> f32 {
      1.0 - a
  }
  
  /// Fuzzy IMPLIES
  pub fn fuzzy_implies(a: f32, b: f32) -> f32 {
      (1.0 - a + b).min(1.0)
  }
  
  /// Universal quantifier (forall)
  pub fn forall(values: &[f32]) -> f32 {
      values.iter().cloned().fold(1.0, |acc, x| acc.min(x))
  }
  
  /// Existential quantifier (exists)
  pub fn exists(values: &[f32]) -> f32 {
      values.iter().cloned().fold(0.0, |acc, x| acc.max(x))
  }
  ```

- [ ] **2.2.2** Create trading predicates
  ```rust
  // neuromorphic/prefrontal/ltn/predicates.rs
  
  pub trait Predicate: Send + Sync {
      fn evaluate(&self, order: &Order, state: &MarketState) -> f32;
      fn name(&self) -> &str;
  }
  
  /// Predicate: Position size is reasonable
  pub struct ReasonablePositionSize {
      max_position: f32,
  }
  
  impl Predicate for ReasonablePositionSize {
      fn evaluate(&self, order: &Order, state: &MarketState) -> f32 {
          let size = order.quantity;
          let ratio = size / self.max_position;
          
          // Returns 1.0 if size <= max, linearly decreases to 0.0 at 2x max
          (1.0 - ratio).max(0.0)
      }
      
      fn name(&self) -> &str {
          "reasonable_position_size"
      }
  }
  
  /// Predicate: No wash sale
  pub struct NoWashSale {
      lookback_window: Duration,
  }
  
  impl Predicate for NoWashSale {
      fn evaluate(&self, order: &Order, state: &MarketState) -> f32 {
          let recent_trades = state.get_recent_trades(
              &order.symbol,
              self.lookback_window
          );
          
          let has_wash_sale = recent_trades.iter().any(|trade| {
              trade.side != order.side && 
              (trade.timestamp - order.timestamp).abs() < self.lookback_window
          });
          
          if has_wash_sale { 0.0 } else { 1.0 }
      }
      
      fn name(&self) -> &str {
          "no_wash_sale"
      }
  }
  
  /// Predicate: Spread is reasonable (not executing in thin market)
  pub struct ReasonableSpread {
      max_spread_bps: f32,
  }
  
  impl Predicate for ReasonableSpread {
      fn evaluate(&self, order: &Order, state: &MarketState) -> f32 {
          let orderbook = state.get_orderbook(&order.symbol);
          let spread_bps = orderbook.spread_bps();
          
          if spread_bps > self.max_spread_bps {
              0.0
          } else {
              1.0 - (spread_bps / self.max_spread_bps)
          }
      }
      
      fn name(&self) -> &str {
          "reasonable_spread"
      }
  }
  ```

- [ ] **2.2.3** Build constraint solver
  ```rust
  // neuromorphic/prefrontal/ltn/constraint_solver.rs
  
  pub struct LTNConstraintEngine {
      predicates: Vec<Box<dyn Predicate>>,
      rules: Vec<LogicalRule>,
      threshold: f32,  // Minimum satisfaction score
  }
  
  pub struct LogicalRule {
      pub name: String,
      pub formula: RuleFormula,
      pub weight: f32,
  }
  
  pub enum RuleFormula {
      And(Vec<String>),           // All predicates must be true
      Or(Vec<String>),            // At least one predicate true
      Implies(String, String),    // If P then Q
      Not(String),                // Negation
      ForAll(String, Vec<String>), // All instances satisfy predicate
  }
  
  impl LTNConstraintEngine {
      pub fn new(threshold: f32) -> Self {
          let mut engine = Self {
              predicates: Vec::new(),
              rules: Vec::new(),
              threshold,
          };
          
          engine.add_default_predicates();
          engine.add_default_rules();
          engine
      }
      
      fn add_default_predicates(&mut self) {
          self.add_predicate(Box::new(ReasonablePositionSize {
              max_position: 100.0
          }));
          self.add_predicate(Box::new(NoWashSale {
              lookback_window: Duration::from_secs(3600)
          }));
          self.add_predicate(Box::new(ReasonableSpread {
              max_spread_bps: 50.0
          }));
      }
      
      fn add_default_rules(&mut self) {
          // Rule: All orders must have reasonable position size AND no wash sale
          self.add_rule(LogicalRule {
              name: "safe_order".to_string(),
              formula: RuleFormula::And(vec![
                  "reasonable_position_size".to_string(),
                  "no_wash_sale".to_string(),
              ]),
              weight: 1.0,
          });
          
          // Rule: If spread is wide, position size should be smaller
          self.add_rule(LogicalRule {
              name: "careful_in_thin_market".to_string(),
              formula: RuleFormula::Implies(
                  "reasonable_spread".to_string(),
                  "reasonable_position_size".to_string(),
              ),
              weight: 0.8,
          });
      }
      
      pub fn validate(&self, order: &Order, state: &MarketState) -> LTNResult {
          // Evaluate all predicates
          let mut predicate_scores = HashMap::new();
          for predicate in &self.predicates {
              let score = predicate.evaluate(order, state);
              predicate_scores.insert(predicate.name().to_string(), score);
          }
          
          // Evaluate all rules
          let mut rule_scores = HashMap::new();
          for rule in &self.rules {
              let score = self.evaluate_rule(&rule.formula, &predicate_scores);
              rule_scores.insert(rule.name.clone(), score * rule.weight);
          }
          
          // Aggregate scores
          let total_score: f32 = rule_scores.values().sum();
          let avg_score = total_score / rule_scores.len() as f32;
          
          LTNResult {
              passed: avg_score >= self.threshold,
              score: avg_score,
              predicate_scores,
              rule_scores,
          }
      }
      
      fn evaluate_rule(
          &self,
          formula: &RuleFormula,
          scores: &HashMap<String, f32>
      ) -> f32 {
          match formula {
              RuleFormula::And(predicates) => {
                  let values: Vec<f32> = predicates.iter()
                      .map(|p| scores.get(p).copied().unwrap_or(0.0))
                      .collect();
                  forall(&values)
              }
              RuleFormula::Or(predicates) => {
                  let values: Vec<f32> = predicates.iter()
                      .map(|p| scores.get(p).copied().unwrap_or(0.0))
                      .collect();
                  exists(&values)
              }
              RuleFormula::Implies(p, q) => {
                  let p_score = scores.get(p).copied().unwrap_or(0.0);
                  let q_score = scores.get(q).copied().unwrap_or(0.0);
                  fuzzy_implies(p_score, q_score)
              }
              RuleFormula::Not(p) => {
                  let p_score = scores.get(p).copied().unwrap_or(0.0);
                  fuzzy_not(p_score)
              }
              RuleFormula::ForAll(_, predicates) => {
                  let values: Vec<f32> = predicates.iter()
                      .map(|p| scores.get(p).copied().unwrap_or(0.0))
                      .collect();
                  forall(&values)
              }
          }
      }
  }
  
  pub struct LTNResult {
      pub passed: bool,
      pub score: f32,
      pub predicate_scores: HashMap<String, f32>,
      pub rule_scores: HashMap<String, f32>,
  }
  ```

- [ ] **2.2.4** Integrate with forward service
  ```rust
  // services/forward/src/engine.rs
  impl TradingEngine {
      pub async fn process_signal(&self, signal: Signal) -> Result<()> {
          // Convert signal to order
          let order = self.signal_to_order(signal)?;
          
          // Validate with LTN
          let market_state = self.get_market_state().await?;
          let ltn_result = self.logic.validate(&order, &market_state);
          
          if !ltn_result.passed {
              warn!(
                  "Order rejected by LTN: score={:.3}, predicates={:?}",
                  ltn_result.score,
                  ltn_result.predicate_scores
              );
              return Ok(());
          }
          
          info!("Order passed LTN validation: score={:.3}", ltn_result.score);
          
          // Execute order
          self.execute_order(order).await?;
          
          Ok(())
      }
  }
  ```

- [ ] **2.2.5** Add compliance scoring
  ```rust
  // neuromorphic/prefrontal/ltn/compliance_score.rs
  
  pub struct ComplianceScorer {
      ltn: LTNConstraintEngine,
      history: VecDeque<(Order, LTNResult)>,
  }
  
  impl ComplianceScorer {
      pub fn get_compliance_metrics(&self) -> ComplianceMetrics {
          let total = self.history.len();
          let passed = self.history.iter()
              .filter(|(_, result)| result.passed)
              .count();
          
          let avg_score = self.history.iter()
              .map(|(_, result)| result.score)
              .sum::<f32>() / total as f32;
          
          ComplianceMetrics {
              total_orders: total,
              passed_orders: passed,
              pass_rate: passed as f32 / total as f32,
              avg_score,
          }
      }
  }
  ```

**Deliverables:**
- ✅ LTN validates orders correctly
- ✅ Custom predicates can be added
- ✅ Compliance metrics tracked
- ✅ Integration tests pass

---

### 2.3 Create Prioritized Replay Buffer

**Status:** 🟡 Basic ReplayBuffer exists, needs prioritization

**Location:** `neuromorphic/hippocampus/replay/`

#### Tasks:

- [ ] **2.3.1** Implement SumTree data structure
  ```rust
  // neuromorphic/hippocampus/replay/sum_tree.rs
  
  pub struct SumTree {
      tree: Vec<f32>,      // Binary tree of priorities
      data: Vec<Experience>, // Actual experiences
      capacity: usize,
      write_idx: usize,
  }
  
  impl SumTree {
      pub fn new(capacity: usize) -> Self {
          let tree_size = 2 * capacity - 1;
          Self {
              tree: vec![0.0; tree_size],
              data: Vec::with_capacity(capacity),
              capacity,
              write_idx: 0,
          }
      }
      
      fn update(&mut self, idx: usize, priority: f32) {
          let tree_idx = idx + self.capacity - 1;
          let change = priority - self.tree[tree_idx];
          self.tree[tree_idx] = priority;
          
          // Propagate change up the tree
          self.propagate(tree_idx, change);
      }
      
      fn propagate(&mut self, idx: usize, change: f32) {
          let mut current = idx;
          while current > 0 {
              current = (current - 1) / 2;
              self.tree[current] += change;
          }
      }
      
      pub fn add(&mut self, experience: Experience, priority: f32) {
          let idx = self.write_idx;
          
          if self.data.len() < self.capacity {
              self.data.push(experience);
          } else {
              self.data[idx] = experience;
          }
          
          self.update(idx, priority);
          self.write_idx = (self.write_idx + 1) % self.capacity;
      }
      
      pub fn sample(&self, value: f32) -> Option<(usize, &Experience, f32)> {
          let idx = self.retrieve(0, value);
          let data_idx = idx - self.capacity + 1;
          
          if data_idx < self.data.len() {
              let priority = self.tree[idx];
              Some((data_idx, &self.data[data_idx], priority))
          } else {
              None
          }
      }
      
      fn retrieve(&self, idx: usize, value: f32) -> usize {
          let left = 2 * idx + 1;
          let right = left + 1;
          
          if left >= self.tree.len() {
              return idx;
          }
          
          if value <= self.tree[left] {
              self.retrieve(left, value)
          } else {
              self.retrieve(right, value - self.tree[left])
          }
      }
      
      pub fn total_priority(&self) -> f32 {
          self.tree[0]
      }
  }
  ```

- [ ] **2.3.2** Build PrioritizedReplayBuffer
  ```rust
  // neuromorphic/hippocampus/replay/prioritized.rs
  
  pub struct PrioritizedReplayBuffer {
      sum_tree: SumTree,
      alpha: f32,  // Priority exponent
      beta: f32,   // Importance sampling weight
      beta_increment: f32,
      max_priority: f32,
      epsilon: f32,  // Small constant to ensure non-zero priorities
  }
  
  impl PrioritizedReplayBuffer {
      pub fn new(capacity: usize, alpha: f32, beta: f32) -> Self {
          Self {
              sum_tree: SumTree::new(capacity),
              alpha,
              beta,
              beta_increment: 0.001,
              max_priority: 1.0,
              epsilon: 1e-6,
          }
      }
      
      pub fn push(&mut self, experience: Experience) {
          // New experiences get max priority
          let priority = self.max_priority.powf(self.alpha);
          self.sum_tree.add(experience, priority);
      }
      
      pub fn sample(&mut self, batch_size: usize) -> Result<SampledBatch> {
          let total_priority = self.sum_tree.total_priority();
          let segment_size = total_priority / batch_size as f32;
          
          let mut batch = Vec::with_capacity(batch_size);
          let mut indices = Vec::with_capacity(batch_size);
          let mut weights = Vec::with_capacity(batch_size);
          
          // Sample from each segment
          for i in 0..batch_size {
              let lower = i as f32 * segment_size;
              let upper = (i + 1) as f32 * segment_size;
              let value = lower + rand::random::<f32>() * (upper - lower);
              
              if let Some((idx, exp, priority)) = self.sum_tree.sample(value) {
                  batch.push(exp.clone());
                  indices.push(idx);
                  
                  // Calculate importance sampling weight
                  let prob = priority / total_priority;
                  let weight = (1.0 / (prob * self.sum_tree.len() as f32))
                      .powf(self.beta);
                  weights.push(weight);
              }
          }
          
          // Normalize weights
          let max_weight = weights.iter().cloned().fold(0.0f32, f32::max);
          weights.iter_mut().for_each(|w| *w /= max_weight);
          
          // Anneal beta
          self.beta = (self.beta + self.beta_increment).min(1.0);
          
          Ok(SampledBatch {
              experiences: batch,
              indices,
              weights,
          })
      }
      
      pub fn update_priorities(&mut self, indices: &[usize], td_errors: &[f32]) {
          for (&idx, &td_error) in indices.iter().zip(td_errors.iter()) {
              let priority = (td_error.abs() + self.epsilon).powf(self.alpha);
              self.sum_tree.update(idx, priority);
              self.max_priority = self.max_priority.max(priority);
          }
      }
  }
  
  pub struct SampledBatch {
      pub experiences: Vec<Experience>,
      pub indices: Vec<usize>,
      pub weights: Vec<f32>,  // Importance sampling weights
  }
  ```

- [ ] **2.3.3** Integrate with backward service
  ```rust
  // services/backward/src/trainer.rs
  
  pub struct TrainingOrchestrator {
      replay_buffer: Arc<Mutex<PrioritizedReplayBuffer>>,
      actor_critic: ActorCritic,
      optimizer: Adam,
  }
  
  impl TrainingOrchestrator {
      pub async fn train_step(&mut self) -> Result<TrainingMetrics> {
          let batch = self.replay_buffer.lock().await.sample(256)?;
          
          // Compute TD errors
          let td_errors = self.compute_td_errors(&batch)?;
          
          // Update priorities in replay buffer
          self.replay_buffer.lock().await
              .update_priorities(&batch.indices, &td_errors);
          
          // Perform gradient update (weighted by importance sampling)
          let loss = self.actor_critic.train_batch(
              &batch.experiences,
              &batch.weights
          )?;
          
          Ok(TrainingMetrics {
              loss,
              avg_td_error: td_errors.iter().sum::<f32>() / td_errors.len() as f32,
              batch_size: batch.experiences.len(),
          })
      }
  }
  ```

- [ ] **2.3.4** Add experience recording in forward service
  ```rust
  // services/forward/src/engine.rs
  impl TradingEngine {
      pub async fn record_experience(&self, experience: Experience) -> Result<()> {
          // Store in Qdrant for persistence
          self.qdrant_client.store_experience(&experience).await?;
          
          // Also add to local replay buffer for immediate training
          if let Some(buffer) = &self.local_replay_buffer {
              buffer.lock().await.push(experience);
          }
          
          Ok(())
      }
      
      async fn create_experience(
          &self,
          state_before: State,
          action: Action,
          state_after: State,
          reward: f32,
      ) -> Experience {
          Experience {
              state: state_before,
              action,
              reward,
              next_state: state_after,
              done: false,  // Episode termination logic
              priority: 1.0,  // Will be updated by replay buffer
              timestamp: Utc::now(),
          }
      }
  }
  ```

**Deliverables:**
- ✅ Prioritized sampling works correctly
- ✅ High TD-error experiences sampled more often
- ✅ Importance sampling weights computed
- ✅ Integration tests with backward service

---

### 2.4 Integrate Qdrant for Schema Storage

**Status:** 🟡 Infrastructure exists, needs implementation

**Location:** `neuromorphic/integration/storage/`

#### Tasks:

- [ ] **2.4.1** Set up Qdrant client
  ```rust
  // neuromorphic/integration/storage/qdrant.rs
  use qdrant_client::{
      prelude::*,
      qdrant::{
          CreateCollection, Distance, PointStruct, SearchPoints,
          VectorParams, VectorsConfig,
      },
  };
  
  pub struct QdrantStorage {
      client: QdrantClient,
      collection_name: String,
  }
  
  impl QdrantStorage {
      pub async fn new(url: &str, collection_name: &str) -> Result<Self> {
          let client = QdrantClient::from_url(url).build()?;
          
          let storage = Self {
              client,
              collection_name: collection_name.to_string(),
          };
          
          storage.ensure_collection().await?;
          
          Ok(storage)
      }
      
      async fn ensure_collection(&self) -> Result<()> {
          // Check if collection exists
          let collections = self.client.list_collections().await?;
          
          if !collections.collections.iter()
              .any(|c| c.name == self.collection_name) {
              // Create collection
              self.client.create_collection(&CreateCollection {
                  collection_name: self.collection_name.clone(),
                  vectors_config: Some(VectorsConfig {
                      config: Some(qdrant_client::qdrant::vectors_config::Config::Params(
                          VectorParams {
                              size: 64,  // GAF embedding size
                              distance: Distance::Cosine.into(),
                              ..Default::default()
                          }
                      )),
                  }),
                  ..Default::default()
              }).await?;
              
              info!("Created Qdrant collection: {}", self.collection_name);
          }
          
          Ok(())
      }
  }
  ```

- [ ] **2.4.2** Store experiences with embeddings
  ```rust
  impl QdrantStorage {
      pub async fn store_experience(&self, experience: &Experience) -> Result<String> {
          // Flatten GAF to 1D vector
          let embedding = experience.state.gaf_features
              .iter()
              .cloned()
              .collect::<Vec<f32>>();
          
          let id = Uuid::new_v4().to_string();
          
          // Create payload with metadata
          let mut payload = Payload::new();
          payload.insert("symbol", experience.state.metadata.symbol.clone());
          payload.insert("action_type", format!("{:?}", experience.action.action_type));
          payload.insert("reward", experience.reward);
          payload.insert("timestamp", experience.timestamp.to_rfc3339());
          
          // Serialize full experience as JSON
          let experience_json = serde_json::to_string(experience)?;
          payload.insert("data", experience_json);
          
          let point = PointStruct::new(
              id.clone(),
              embedding,
              payload,
          );
          
          self.client.upsert_points_blocking(
              self.collection_name.clone(),
              vec![point],
              None,
          ).await?;
          
          Ok(id)
      }
      
      pub async fn search_similar_experiences(
          &self,
          state: &State,
          limit: usize,
      ) -> Result<Vec<Experience>> {
          let query_vector = state.gaf_features
              .iter()
              .cloned()
              .collect::<Vec<f32>>();
          
          let search_result = self.client.search_points(&SearchPoints {
              collection_name: self.collection_name.clone(),
              vector: query_vector,
              limit: limit as u64,
              with_payload: Some(true.into()),
              ..Default::default()
          }).await?;
          
          let mut experiences = Vec::new();
          for scored_point in search_result.result {
              if let Some(payload) = scored_point.payload.get("data") {
                  if let Some(json_str) = payload.as_str() {
                      let exp: Experience = serde_json::from_str(json_str)?;
                      experiences.push(exp);
                  }
              }
          }
          
          Ok(experiences)
      }
  }
  ```

- [ ] **2.4.3** Store learned strategies
  ```rust
  pub struct StrategyStorage {
      client: QdrantClient,
      collection_name: String,
  }
  
  impl StrategyStorage {
      pub async fn store_strategy(
          &self,
          strategy: &Strategy,
          performance: &PerformanceMetrics,
      ) -> Result<String> {
          let embedding = strategy.parameters.clone();
          let id = strategy.id.clone();
          
          let mut payload = Payload::new();
          payload.insert("name", strategy.name.clone());
          payload.insert("sharpe_ratio", performance.sharpe_ratio);
          payload.insert("total_return", performance.total_return);
          payload.insert("max_drawdown", performance.max_drawdown);
          payload.insert("win_rate", performance.win_rate);
          
          let point = PointStruct::new(id.clone(), embedding, payload);
          
          self.client.upsert_points_blocking(
              self.collection_name.clone(),
              vec![point],
              None,
          ).await?;
          
          Ok(id)
      }
      
      pub async fn get_best_strategies(&self, limit: usize) -> Result<Vec<Strategy>> {
          // Scroll through collection and sort by Sharpe ratio
          let scroll_result = self.client.scroll(&ScrollPoints {
              collection_name: self.collection_name.clone(),
              limit: Some(limit as u32),
              with_payload: Some(true.into()),
              with_vectors: Some(true.into()),
              ..Default::default()
          }).await?;
          
          let mut strategies = Vec::new();
          for point in scroll_result.result {
              // Parse strategy from point
              if let Some(vectors) = point.vectors {
                  if let Some(sharpe) = point.payload.get("sharpe_ratio") {
                      // Reconstruct strategy
                      let strategy = Strategy::from_point(point)?;
                      strategies.push(strategy);
                  }
              }
          }
          
          // Sort by performance
          strategies.sort_by(|a, b| {
              b.performance.sharpe_ratio
                  .partial_cmp(&a.performance.sharpe_ratio)
                  .unwrap_or(std::cmp::Ordering::Equal)
          });
          
          Ok(strategies.into_iter().take(limit).collect())
      }
  }
  ```

- [ ] **2.4.4** Implement pattern retrieval
  ```rust
  pub struct PatternRetrieval {
      storage: QdrantStorage,
  }
  
  impl PatternRetrieval {
      /// Find similar historical patterns
      pub async fn find_similar_patterns(
          &self,
          current_state: &State,
          k: usize,
      ) -> Result<Vec<(Experience, f32)>> {
          let experiences = self.storage
              .search_similar_experiences(current_state, k)
              .await?;
          
          // Calculate similarity scores
          let mut results = Vec::new();
          for exp in experiences {
              let similarity = cosine_similarity(
                  &current_state.gaf_features,
                  &exp.state.gaf_features,
              );
              results.push((exp, similarity));
          }
          
          results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
          
          Ok(results)
      }
      
      /// Analyze outcomes of similar past patterns
      pub async fn analyze_pattern_outcomes(
          &self,
          current_state: &State,
      ) -> Result<PatternAnalysis> {
          let similar = self.find_similar_patterns(current_state, 50).await?;
          
          let rewards: Vec<f32> = similar.iter().map(|(e, _)| e.reward).collect();
          let avg_reward = rewards.iter().sum::<f32>() / rewards.len() as f32;
          let std_reward = calculate_std(&rewards);
          
          let actions: HashMap<ActionType, usize> = similar.iter()
              .map(|(e, _)| e.action.action_type)
              .fold(HashMap::new(), |mut acc, action| {
                  *acc.entry(action).or_insert(0) += 1;
                  acc
              });
          
          Ok(PatternAnalysis {
              num_similar: similar.len(),
              avg_reward,
              std_reward,
              most_common_action: actions.iter()
                  .max_by_key(|(_, count)| *count)
                  .map(|(action, _)| *action),
              similarity_threshold: similar.last().map(|(_, sim)| *sim).unwrap_or(0.0),
          })
      }
  }
  ```

- [ ] **2.4.5** Add batch operations
  ```rust
  impl QdrantStorage {
      pub async fn batch_store_experiences(
          &self,
          experiences: &[Experience],
      ) -> Result<Vec<String>> {
          let points: Vec<PointStruct> = experiences.iter()
              .map(|exp| {
                  let id = Uuid::new_v4().to_string();
                  let embedding = exp.state.gaf_features.iter().cloned().collect();
                  
                  let mut payload = Payload::new();
                  payload.insert("data", serde_json::to_string(exp).unwrap());
                  
                  PointStruct::new(id.clone(), embedding, payload)
              })
              .collect();
          
          let ids: Vec<String> = points.iter()
              .map(|p| p.id.to_string())
              .collect();
          
          self.client.upsert_points_batch_blocking(
              self.collection_name.clone(),
              points,
              None,
              100,  // Batch size
          ).await?;
          
          Ok(ids)
      }
  }
  ```

**Deliverables:**
- ✅ Qdrant collections created
- ✅ Experiences stored with embeddings
- ✅ Similar pattern retrieval works
- ✅ Batch operations efficient (>1000 ops/sec)

---

## 🚀 Phase 3: Production Readiness

**Duration:** 2-3 weeks  
**Goal:** Optimize, test, monitor, and document for production deployment

### 3.1 Performance Optimization

#### Tasks:

- [ ] **3.1.1** Profile hot paths
  ```bash
  # Install profiling tools
  cargo install flamegraph
  cargo install cargo-instruments
  
  # Profile forward service
  cargo flamegraph --bin forward -- --test-mode
  
  # Profile inference pipeline
  cargo bench --bench inference_bench
  ```

- [ ] **3.1.2** Optimize GAF encoding
  ```rust
  // Use SIMD for matrix operations
  use std::arch::x86_64::*;
  
  impl DiffGAF {
      #[target_feature(enable = "avx2")]
      unsafe fn gasf_simd(&self, phi: &Array1<f32>) -> Array2<f32> {
          // Vectorized computation
          // Expected speedup: 4-8x
          todo!("Implement SIMD version")
      }
  }
  ```

- [ ] **3.1.3** Add caching layer
  ```rust
  use moka::future::Cache;
  
  pub struct CachedGAFEncoder {
      encoder: DiffGAF,
      cache: Cache<String, Array2<f32>>,
  }
  
  impl CachedGAFEncoder {
      pub async fn encode_cached(&self, key: String, data: &Array1<f32>) -> Array2<f32> {
          self.cache.get_or_insert_with(key, async {
              self.encoder.encode(data).unwrap()
          }).await
      }
  }
  ```

- [ ] **3.1.4** Optimize Qdrant queries
  ```rust
  // Use HNSW index for faster retrieval
  impl QdrantStorage {
      async fn optimize_index(&self) -> Result<()> {
          self.client.update_collection(&UpdateCollection {
              collection_name: self.collection_name.clone(),
              optimizers_config: Some(OptimizersConfig {
                  indexing_threshold: Some(10000),
                  ..Default::default()
              }),
              hnsw_config: Some(HnswConfig {
                  m: Some(16),
                  ef_construct: Some(200),
                  ..Default::default()
              }),
              ..Default::default()
          }).await?;
          
          Ok(())
      }
  }
  ```

- [ ] **3.1.5** Benchmark end-to-end latency
  ```rust
  #[tokio::test]
  async fn bench_tick_to_action_latency() {
      let engine = TradingEngine::new(Config::test()).await.unwrap();
      
      let mut latencies = Vec::new();
      for _ in 0..1000 {
          let tick = generate_test_tick();
          let start = Instant::now();
          
          engine.process_tick(tick).await.unwrap();
          
          latencies.push(start.elapsed().as_micros());
      }
      
      let p50 = percentile(&latencies, 0.50);
      let p99 = percentile(&latencies, 0.99);
      
      println!("Latency p50: {} μs, p99: {} μs", p50, p99);
      assert!(p99 < 10_000);  // < 10ms
  }
  ```

**Performance Targets:**
- ✅ GAF encoding: < 1ms per timeseries
- ✅ ONNX inference: < 1ms per forward pass
- ✅ Qdrant search: < 10ms for 100 nearest neighbors
- ✅ End-to-end tick→action: < 10ms (p99)

---

### 3.2 Comprehensive Testing

#### Tasks:

- [ ] **3.2.1** Unit tests (>80% coverage)
  ```bash
  # Run all unit tests with coverage
  cargo tarpaulin --workspace --out Html --output-dir coverage/
  ```

- [ ] **3.2.2** Integration tests
  ```rust
  // tests/integration/test_full_pipeline.rs
  
  #[tokio::test]
  async fn test_tick_to_action_pipeline() {
      // Setup
      let config = Config::test();
      let engine = TradingEngine::new(config).await.unwrap();
      
      //