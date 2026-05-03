# Burn LTN Implementation Quick Start Guide

**Project JANUS - Rust Migration**  
**Framework**: Burn 0.20+  
**Target**: Logic Tensor Networks in Pure Rust

---

## Table of Contents

1. [Setup](#setup)
2. [Step-by-Step Implementation](#step-by-step-implementation)
3. [Code Examples](#code-examples)
4. [Testing](#testing)
5. [Integration](#integration)

---

## Setup

### 1. Update Dependencies

Add to `src/janus/crates/ltn/Cargo.toml`:

```toml
[package]
name = "janus-ltn"
version.workspace = true
edition.workspace = true

[dependencies]
# Existing
serde = { workspace = true }
serde_json = { workspace = true }

# NEW: Burn framework
burn = { version = "0.20", features = ["train", "ndarray"] }
burn-ndarray = "0.20"

# Optional: GPU support
# burn-wgpu = "0.20"     # WebGPU (cross-platform)
# burn-cuda = "0.20"     # NVIDIA CUDA

[dev-dependencies]
burn = { version = "0.20", features = ["test-util"] }
```

### 2. Install Dependencies

```bash
cd src/janus/crates/ltn
cargo build
```

---

## Step-by-Step Implementation

### Phase 1: Basic Neural Network

#### File 1: `src/janus/crates/ltn/network.rs`

```rust
//! LTN Neural Network Implementation
//!
//! This module implements the neural component of the Logic Tensor Network.
//! Architecture: 8 → 32 → 64 → 32 → 3 (DSP features → trading signals)

use burn::{
    config::Config,
    module::Module,
    nn::{
        loss::CrossEntropyLossConfig, Dropout, DropoutConfig, Linear, LinearConfig, Relu,
    },
    tensor::{
        backend::{AutodiffBackend, Backend},
        Int, Tensor,
    },
    train::{ClassificationOutput, TrainOutput, TrainStep, ValidStep},
};

/// Configuration for LTN network architecture
#[derive(Config, Debug)]
pub struct LtnNetworkConfig {
    /// Input dimension (DSP features)
    #[config(default = 8)]
    pub input_dim: usize,

    /// Hidden layer dimensions
    #[config(default = "[32, 64, 32]")]
    pub hidden_dims: Vec<usize>,

    /// Output dimension (long, neutral, short)
    #[config(default = 3)]
    pub output_dim: usize,

    /// Dropout probability
    #[config(default = 0.2)]
    pub dropout: f64,
}

impl LtnNetworkConfig {
    /// Initialize the network from this config
    pub fn init<B: Backend>(&self, device: &B::Device) -> LtnNetwork<B> {
        LtnNetwork {
            fc1: LinearConfig::new(self.input_dim, self.hidden_dims[0]).init(device),
            fc2: LinearConfig::new(self.hidden_dims[0], self.hidden_dims[1]).init(device),
            fc3: LinearConfig::new(self.hidden_dims[1], self.hidden_dims[2]).init(device),
            fc_out: LinearConfig::new(self.hidden_dims[2], self.output_dim).init(device),
            dropout: DropoutConfig::new(self.dropout).init(),
            activation: Relu::new(),
        }
    }
}

/// LTN Neural Network
///
/// This network processes DSP features and outputs trading signal probabilities.
/// It's designed to work with the existing fuzzy logic axiom system.
#[derive(Module, Debug)]
pub struct LtnNetwork<B: Backend> {
    fc1: Linear<B>,
    fc2: Linear<B>,
    fc3: Linear<B>,
    fc_out: Linear<B>,
    dropout: Dropout,
    activation: Relu,
}

impl<B: Backend> LtnNetwork<B> {
    /// Forward pass through the network
    ///
    /// # Arguments
    /// * `input` - Tensor of shape [batch, 8] containing DSP features
    ///
    /// # Returns
    /// * Tensor of shape [batch, 3] containing [P(long), P(neutral), P(short)]
    pub fn forward(&self, input: Tensor<B, 2>) -> Tensor<B, 2> {
        let x = self.fc1.forward(input);
        let x = self.activation.forward(x);

        let x = self.fc2.forward(x);
        let x = self.activation.forward(x);
        let x = self.dropout.forward(x);

        let x = self.fc3.forward(x);
        let x = self.activation.forward(x);

        let logits = self.fc_out.forward(x);

        // Apply softmax to get probabilities
        logits.softmax(1)
    }

    /// Forward pass for a single sample (inference)
    ///
    /// # Arguments
    /// * `features` - Array of 8 DSP features
    ///
    /// # Returns
    /// * Array of 3 probabilities [P(long), P(neutral), P(short)]
    pub fn infer(&self, features: [f64; 8], device: &B::Device) -> [f64; 3] {
        // Convert to tensor [1, 8]
        let input = Tensor::<B, 2>::from_floats(
            [features.map(|x| x as f32)],
            device,
        );

        // Forward pass
        let output = self.forward(input);

        // Convert back to array
        let data = output.into_data();
        let values = data.as_slice::<f32>().unwrap();

        [
            values[0] as f64,
            values[1] as f64,
            values[2] as f64,
        ]
    }
}

/// Training implementation for the LTN network
impl<B: AutodiffBackend> TrainStep<LtnBatch<B>, ClassificationOutput<B>> for LtnNetwork<B> {
    fn step(&self, batch: LtnBatch<B>) -> TrainOutput<ClassificationOutput<B>> {
        let output = self.forward(batch.features);
        let loss = CrossEntropyLossConfig::new()
            .init(&output.device())
            .forward(output.clone(), batch.targets.clone());

        TrainOutput::new(
            self,
            loss.backward(),
            ClassificationOutput::new(loss, output, batch.targets),
        )
    }
}

/// Validation implementation
impl<B: Backend> ValidStep<LtnBatch<B>, ClassificationOutput<B>> for LtnNetwork<B> {
    fn step(&self, batch: LtnBatch<B>) -> ClassificationOutput<B> {
        let output = self.forward(batch.features);
        let loss = CrossEntropyLossConfig::new()
            .init(&output.device())
            .forward(output.clone(), batch.targets.clone());

        ClassificationOutput::new(loss, output, batch.targets)
    }
}

/// Training batch structure
#[derive(Clone, Debug)]
pub struct LtnBatch<B: Backend> {
    /// DSP features [batch, 8]
    pub features: Tensor<B, 2>,
    /// Target labels [batch] (0=long, 1=neutral, 2=short)
    pub targets: Tensor<B, 1, Int>,
}

impl<B: Backend> LtnBatch<B> {
    /// Create a new batch
    pub fn new(features: Tensor<B, 2>, targets: Tensor<B, 1, Int>) -> Self {
        Self { features, targets }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use burn::backend::NdArray;

    type TestBackend = NdArray;

    #[test]
    fn test_network_creation() {
        let device = Default::default();
        let config = LtnNetworkConfig::new();
        let model = config.init::<TestBackend>(&device);

        // Verify network was created
        assert_eq!(std::mem::size_of_val(&model) > 0, true);
    }

    #[test]
    fn test_forward_pass() {
        let device = Default::default();
        let config = LtnNetworkConfig::new();
        let model = config.init::<TestBackend>(&device);

        // Create dummy input [batch=2, features=8]
        let input = Tensor::<TestBackend, 2>::zeros([2, 8], &device);

        // Forward pass
        let output = model.forward(input);

        // Check output shape [batch=2, classes=3]
        assert_eq!(output.dims(), [2, 3]);

        // Check probabilities sum to 1 (softmax property)
        let sums = output.clone().sum_dim(1);
        let sum_values = sums.into_data().as_slice::<f32>().unwrap().to_vec();
        for sum in sum_values {
            assert!((sum - 1.0).abs() < 1e-5, "Probabilities should sum to 1");
        }
    }

    #[test]
    fn test_infer_single_sample() {
        let device = Default::default();
        let config = LtnNetworkConfig::new();
        let model = config.init::<TestBackend>(&device);

        // Test features (trending market with positive divergence)
        let features = [
            1.5,  // divergence_norm
            0.0,  // alpha_norm
            1.5,  // fractal_dim
            0.75, // hurst
            1.0,  // regime
            1.0,  // divergence_sign
            0.0,  // alpha_deviation
            0.4,  // regime_confidence
        ];

        let probs = model.infer(features, &device);

        // Check probabilities are valid
        assert_eq!(probs.len(), 3);
        let sum: f64 = probs.iter().sum();
        assert!((sum - 1.0).abs() < 1e-5);
        for p in probs {
            assert!(p >= 0.0 && p <= 1.0);
        }
    }
}
```

---

#### File 2: `src/janus/crates/ltn/hybrid_loss.rs`

```rust
//! Hybrid Loss Function (Supervised + Semantic)
//!
//! Combines cross-entropy loss (learning from data) with
//! semantic loss (learning from axioms).

use burn::tensor::{backend::Backend, Tensor};
use crate::{axioms::AxiomLibrary, predicates::TradingSignal};

/// Configuration for hybrid loss
#[derive(Debug, Clone)]
pub struct HybridLossConfig {
    /// Weight for supervised loss (α)
    /// α ∈ [0, 1], where α=1 means pure supervised, α=0 means pure semantic
    pub supervised_weight: f64,

    /// Axiom library for semantic loss
    pub axiom_library: AxiomLibrary,
}

impl Default for HybridLossConfig {
    fn default() -> Self {
        Self {
            supervised_weight: 0.5,
            axiom_library: AxiomLibrary::default(),
        }
    }
}

impl HybridLossConfig {
    /// Create config with custom supervised weight
    pub fn with_supervised_weight(mut self, weight: f64) -> Self {
        assert!((0.0..=1.0).contains(&weight), "Weight must be in [0, 1]");
        self.supervised_weight = weight;
        self
    }

    /// Compute hybrid loss for a batch
    ///
    /// # Arguments
    /// * `supervised_loss` - Cross-entropy loss from network output
    /// * `features` - Batch of DSP features [batch, 8]
    /// * `predictions` - Network output probabilities [batch, 3]
    ///
    /// # Returns
    /// * Total loss scalar
    pub fn compute_loss<B: Backend>(
        &self,
        supervised_loss: Tensor<B, 1>,
        features: &[[f64; 8]],
        predictions: &[[f64; 3]],
    ) -> f64 {
        // Supervised component (already computed)
        let supervised_component = supervised_loss.into_scalar() * self.supervised_weight;

        // Semantic component (axiom satisfaction)
        let semantic_component = self.compute_semantic_loss(features, predictions)
            * (1.0 - self.supervised_weight);

        supervised_component + semantic_component
    }

    /// Compute semantic loss (negative axiom satisfaction)
    fn compute_semantic_loss(
        &self,
        features: &[[f64; 8]],
        predictions: &[[f64; 3]],
    ) -> f64 {
        let mut total_loss = 0.0;

        for (feat, pred) in features.iter().zip(predictions.iter()) {
            let signal = TradingSignal::new(pred[0], pred[1], pred[2]);
            let results = self.axiom_library.evaluate_all(feat, &signal);
            let loss = self.axiom_library.compute_semantic_loss(&results);
            total_loss += loss;
        }

        // Average over batch
        total_loss / features.len() as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hybrid_loss_config() {
        let config = HybridLossConfig::default();
        assert_eq!(config.supervised_weight, 0.5);
    }

    #[test]
    fn test_semantic_loss_computation() {
        let config = HybridLossConfig::default();

        // Test features (trending + positive divergence)
        let features = vec![[1.5, 0.0, 1.5, 0.75, 1.0, 1.0, 0.0, 0.4]];

        // Predictions that align with axioms (high long probability)
        let predictions = vec![[0.8, 0.15, 0.05]];

        let loss = config.compute_semantic_loss(&features, &predictions);

        // Loss should be negative (we want to maximize satisfaction)
        assert!(loss < 0.0);
    }

    #[test]
    fn test_hybrid_loss_balance() {
        let config = HybridLossConfig::default()
            .with_supervised_weight(0.7);

        assert_eq!(config.supervised_weight, 0.7);
    }
}
```

---

#### File 3: Update `src/janus/crates/ltn/mod.rs`

```rust
//! Logic Tensor Network (LTN) Module for Project JANUS
//!
//! Now with pure Rust neural network implementation using Burn!

// Re-export public API
pub mod axioms;
pub mod config;
pub mod fuzzy_ops;
pub mod predicates;

// NEW: Neural network components
pub mod network;
pub mod hybrid_loss;

// Convenience re-exports
pub use axioms::{AxiomLibrary, AxiomResult, AxiomStats};
pub use config::{AxiomConfig, InferenceConfig, LtnConfig, ModelConfig, TrainingConfig};
pub use predicates::{Action, TradingSignal};

// NEW: Network exports
pub use network::{LtnNetwork, LtnNetworkConfig, LtnBatch};
pub use hybrid_loss::HybridLossConfig;

/// LTN module version
pub const VERSION: &str = "0.2.0";  // Bumped for Burn integration

/// Number of input features (from DSP pipeline)
pub const INPUT_DIM: usize = 8;

/// Number of output classes (long, neutral, short)
pub const OUTPUT_DIM: usize = 3;

/// Number of core axioms
pub const NUM_AXIOMS: usize = 10;

/// Default semantic weight (α in hybrid loss)
pub const DEFAULT_SEMANTIC_WEIGHT: f64 = 0.5;

#[cfg(test)]
mod tests {
    use super::*;
    use burn::backend::NdArray;

    type TestBackend = NdArray;

    #[test]
    fn test_end_to_end_inference() {
        // Create network
        let device = Default::default();
        let config = LtnNetworkConfig::new();
        let model = config.init::<TestBackend>(&device);

        // Test features
        let features = [1.5, 0.0, 1.5, 0.75, 1.0, 1.0, 0.0, 0.4];

        // Infer
        let probs = model.infer(features, &device);

        // Evaluate axioms with predictions
        let signal = TradingSignal::new(probs[0], probs[1], probs[2]);
        let axioms = AxiomLibrary::default();
        let results = axioms.evaluate_all(&features, &signal);

        // Verify we got axiom evaluations
        assert_eq!(results.len(), NUM_AXIOMS);

        // All satisfactions should be in [0, 1]
        for result in results {
            assert!(result.satisfaction >= 0.0 && result.satisfaction <= 1.0);
        }
    }
}
```

---

### Phase 2: Training Infrastructure

#### File 4: `src/janus/crates/ltn/trainer.rs`

```rust
//! Training infrastructure for LTN network

use burn::{
    optim::{Adam, AdamConfig, GradientsParams, Optimizer},
    tensor::{
        backend::{AutodiffBackend, Backend},
        Int, Tensor,
    },
    lr_scheduler::{LrScheduler, exponential::ExponentialLrSchedulerConfig},
    record::{FullPrecisionSettings, NamedMpkFileRecorder, Recorder},
};
use std::path::PathBuf;

use crate::{
    network::{LtnNetwork, LtnNetworkConfig, LtnBatch},
    hybrid_loss::HybridLossConfig,
    predicates::TradingSignal,
};

/// Training configuration
#[derive(Debug, Clone)]
pub struct TrainingConfig {
    /// Learning rate
    pub learning_rate: f64,

    /// Number of epochs
    pub num_epochs: usize,

    /// Batch size
    pub batch_size: usize,

    /// Supervised weight schedule
    /// Maps epoch -> supervised_weight
    pub supervised_schedule: Vec<(usize, f64)>,

    /// Model save directory
    pub checkpoint_dir: PathBuf,
}

impl Default for TrainingConfig {
    fn default() -> Self {
        Self {
            learning_rate: 0.001,
            num_epochs: 100,
            batch_size: 32,
            // Schedule: Start data-focused, end axiom-focused
            supervised_schedule: vec![
                (0, 0.8),    // First 1/3: 80% supervised
                (33, 0.5),   // Middle 1/3: 50/50
                (66, 0.3),   // Last 1/3: 30% supervised (70% axioms)
            ],
            checkpoint_dir: PathBuf::from("./checkpoints"),
        }
    }
}

/// LTN Trainer
pub struct LtnTrainer<B: AutodiffBackend> {
    model: LtnNetwork<B>,
    optimizer: Adam<B>,
    config: TrainingConfig,
    hybrid_loss_config: HybridLossConfig,
    device: B::Device,
}

impl<B: AutodiffBackend> LtnTrainer<B> {
    /// Create a new trainer
    pub fn new(
        model_config: LtnNetworkConfig,
        training_config: TrainingConfig,
        device: B::Device,
    ) -> Self {
        let model = model_config.init(&device);
        
        let optimizer = AdamConfig::new()
            .with_learning_rate(training_config.learning_rate)
            .init();

        let hybrid_loss_config = HybridLossConfig::default();

        Self {
            model,
            optimizer,
            config: training_config,
            hybrid_loss_config,
            device,
        }
    }

    /// Train for one epoch
    pub fn train_epoch(&mut self, batches: Vec<LtnBatch<B>>) -> f64 {
        let mut total_loss = 0.0;

        for batch in batches {
            let loss = self.train_step(batch);
            total_loss += loss;
        }

        total_loss / self.config.batch_size as f64
    }

    /// Single training step
    fn train_step(&mut self, batch: LtnBatch<B>) -> f64 {
        // Forward pass
        let output = self.model.forward(batch.features.clone());

        // Compute supervised loss (cross-entropy)
        let supervised_loss = output.clone()
            .cross_entropy_with_logits(batch.targets.clone());

        // For semantic loss, we need to convert tensors to f64 arrays
        // This is the bridge between neural network and fuzzy logic
        let features_data = self.tensor_to_features_batch(&batch.features);
        let predictions_data = self.tensor_to_predictions_batch(&output);

        // Compute hybrid loss
        let total_loss_value = self.hybrid_loss_config.compute_loss(
            supervised_loss.clone(),
            &features_data,
            &predictions_data,
        );

        // Backward pass (only on supervised loss tensor for now)
        // TODO: Make semantic loss differentiable
        let grads = supervised_loss.backward();

        // Update model
        let grads = GradientsParams::from_grads(grads, &self.model);
        self.model = self.optimizer.step(self.config.learning_rate, self.model, grads);

        total_loss_value
    }

    /// Save model checkpoint
    pub fn save_checkpoint(&self, epoch: usize) -> Result<(), Box<dyn std::error::Error>> {
        std::fs::create_dir_all(&self.config.checkpoint_dir)?;
        
        let path = self.config.checkpoint_dir.join(format!("model_epoch_{}.mpk", epoch));
        
        let recorder = NamedMpkFileRecorder::<FullPrecisionSettings>::new();
        recorder.record(self.model.clone().into_record(), path)?;

        Ok(())
    }

    /// Helper: Convert tensor batch to feature arrays
    fn tensor_to_features_batch(&self, tensor: &Tensor<B, 2>) -> Vec<[f64; 8]> {
        let data = tensor.clone().into_data();
        let values = data.as_slice::<f32>().unwrap();
        
        values.chunks(8)
            .map(|chunk| {
                let mut arr = [0.0f64; 8];
                for (i, &v) in chunk.iter().enumerate() {
                    arr[i] = v as f64;
                }
                arr
            })
            .collect()
    }

    /// Helper: Convert prediction tensor to probability arrays
    fn tensor_to_predictions_batch(&self, tensor: &Tensor<B, 2>) -> Vec<[f64; 3]> {
        let data = tensor.clone().into_data();
        let values = data.as_slice::<f32>().unwrap();
        
        values.chunks(3)
            .map(|chunk| [chunk[0] as f64, chunk[1] as f64, chunk[2] as f64])
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use burn::backend::NdArray;

    type TestBackend = NdArray;

    #[test]
    fn test_trainer_creation() {
        let device = Default::default();
        let model_config = LtnNetworkConfig::new();
        let training_config = TrainingConfig::default();

        let trainer = LtnTrainer::<TestBackend>::new(
            model_config,
            training_config,
            device,
        );

        // Just verify it compiles and creates
        assert_eq!(std::mem::size_of_val(&trainer) > 0, true);
    }
}
```

---

## Testing

### Run Tests

```bash
# Test LTN crate
cd src/janus/crates/ltn
cargo test

# Test with output
cargo test -- --nocapture

# Specific test
cargo test test_forward_pass
```

### Benchmark

Create `benches/ltn_bench.rs`:

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use janus_ltn::{LtnNetwork, LtnNetworkConfig};
use burn::backend::NdArray;

type Backend = NdArray;

fn benchmark_inference(c: &mut Criterion) {
    let device = Default::default();
    let config = LtnNetworkConfig::new();
    let model = config.init::<Backend>(&device);

    let features = [1.5, 0.0, 1.5, 0.75, 1.0, 1.0, 0.0, 0.4];

    c.bench_function("ltn_inference", |b| {
        b.iter(|| {
            model.infer(black_box(features), &device)
        })
    });
}

criterion_group!(benches, benchmark_inference);
criterion_main!(benches);
```

Run:
```bash
cargo bench
```

---

## Integration

### Using LTN in Janus Main Binary

```rust
// src/janus/bin/janus/src/main.rs

use janus_ltn::{LtnNetwork, LtnNetworkConfig};
use burn::backend::NdArray;

type Backend = NdArray;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize LTN
    let device = Default::default();
    let config = LtnNetworkConfig::new();
    let ltn_model = config.init::<Backend>(&device);

    // In trading loop:
    loop {
        // Get DSP features from market data
        let features = get_dsp_features().await;

        // LTN inference
        let probs = ltn_model.infer(features, &device);

        // probs = [P(long), P(neutral), P(short)]
        let action = if probs[0] > 0.6 {
            Action::Long
        } else if probs[2] > 0.6 {
            Action::Short
        } else {
            Action::Neutral
        };

        // Pass to execution engine
        execute_trade(action).await?;
    }
}
```

---

## Next Steps

1. **Implement DiffGAF in Burn** - Port GAF transformation
2. **Add GPU Support** - Use `burn-wgpu` or `burn-cuda`
3. **Training Pipeline** - Build data loader from QuestDB
4. **ONNX Export** - Save models for deployment

---

## Performance Expectations

| Operation | Target | Notes |
|-----------|--------|-------|
| Single inference | < 50µs | On CPU (NdArray backend) |
| Batch inference (32) | < 500µs | Amortized per sample: ~15µs |
| Training step | < 10ms | Including backward pass |
| Model loading | < 100ms | From checkpoint |

---

## Troubleshooting

### Issue: Compilation errors with recursion limit

**Solution**: Add to `lib.rs`:
```rust
#![recursion_limit = "256"]
```

### Issue: Slow inference on CPU

**Solution**: Switch to GPU backend:
```toml
burn-wgpu = "0.20"
```

```rust
use burn::backend::Wgpu;
type Backend = Wgpu;
```

### Issue: Tensor shape mismatches

**Solution**: Always verify shapes:
```rust
let x = tensor.clone();
println!("Shape: {:?}", x.dims());
```

---

## Resources

- **Burn Book**: https://burn.dev/book/
- **Burn Examples**: https://github.com/tracel-ai/burn/tree/main/examples
- **Burn Discord**: https://discord.gg/uPEBbYYDB6

---

**Status**: ✅ Ready to implement

**Estimated Time**: 2-3 days for basic implementation

**Next**: Create `network.rs` and run first tests!