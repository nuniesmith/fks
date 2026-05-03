# Rust Migration Cheat Sheet

**Quick reference for migrating Project JANUS to 100% Rust**

---

## Quick Start Commands

### Setup Burn
```bash
cd src/janus/crates/ltn
cargo add burn --features train,ndarray
cargo add burn-ndarray
cargo build
```

### Run Tests
```bash
cargo test                    # All tests
cargo test --package janus-ltn  # Specific crate
cargo test -- --nocapture      # Show output
```

### Benchmark
```bash
cargo bench
cargo flamegraph --bench ltn_bench  # Profiling
```

---

## Burn Basics

### Create a Network
```rust
use burn::{
    module::Module,
    nn::{Linear, LinearConfig, Dropout, DropoutConfig},
    tensor::{backend::Backend, Tensor},
};

#[derive(Module, Debug)]
pub struct MyNetwork<B: Backend> {
    fc1: Linear<B>,
    fc2: Linear<B>,
    dropout: Dropout,
}

impl<B: Backend> MyNetwork<B> {
    pub fn new(device: &B::Device) -> Self {
        Self {
            fc1: LinearConfig::new(8, 32).init(device),
            fc2: LinearConfig::new(32, 3).init(device),
            dropout: DropoutConfig::new(0.2).init(),
        }
    }
    
    pub fn forward(&self, input: Tensor<B, 2>) -> Tensor<B, 2> {
        let x = self.fc1.forward(input).relu();
        let x = self.dropout.forward(x);
        self.fc2.forward(x).softmax(1)
    }
}
```

### Backend Selection
```rust
// CPU (fastest to compile)
use burn::backend::NdArray;
type Backend = NdArray;

// GPU - WebGPU (cross-platform)
use burn::backend::Wgpu;
type Backend = Wgpu;

// GPU - CUDA (NVIDIA)
use burn::backend::Cuda;
type Backend = Cuda;

// With Autodiff
use burn::backend::{Autodiff, Wgpu};
type Backend = Autodiff<Wgpu>;
```

### Tensor Operations
```rust
// Create tensor
let x = Tensor::<B, 2>::zeros([32, 8], &device);
let x = Tensor::<B, 2>::from_floats([[1.0, 2.0]], &device);

// Operations
let y = x.clone() + 1.0;
let y = x.matmul(weights);
let y = x.relu();
let y = x.softmax(1);

// Convert to array
let data = y.into_data();
let values = data.as_slice::<f32>().unwrap();
```

---

## LTN Integration

### Neural Network + Fuzzy Logic
```rust
use janus_ltn::{LtnNetwork, LtnNetworkConfig};
use janus_ltn::{AxiomLibrary, TradingSignal};
use burn::backend::NdArray;

let device = Default::default();
let config = LtnNetworkConfig::new();
let model = config.init::<NdArray>(&device);

// Inference
let features = [1.5, 0.0, 1.5, 0.75, 1.0, 1.0, 0.0, 0.4];
let probs = model.infer(features, &device);

// Evaluate axioms
let signal = TradingSignal::new(probs[0], probs[1], probs[2]);
let axioms = AxiomLibrary::default();
let results = axioms.evaluate_all(&features, &signal);
```

---

## Service Consolidation

### Before (Multi-Service)
```rust
// execution-service listening on gRPC
let signal = receive_signal_from_grpc().await?;
execute_order(signal).await?;
```

### After (Consolidated)
```rust
// Direct function call
let signal = ltn.infer(features, &device);
execution_engine.submit_signal(signal).await?;
```

### Main Loop
```rust
#[tokio::main]
async fn main() -> Result<()> {
    let mut janus = JanusCore::new().await?;
    
    loop {
        tokio::select! {
            Some(tick) = janus.exchange.recv() => {
                let features = janus.dsp.process(tick)?;
                let signal = janus.ltn.infer(features)?;
                if janus.risk.validate(&signal)? {
                    janus.execution.submit(signal).await?;
                }
            }
            _ = tokio::signal::ctrl_c() => break,
        }
    }
    
    janus.shutdown().await
}
```

---

## Training

### Basic Training Loop
```rust
use burn::optim::{Adam, AdamConfig};
use burn::train::{TrainStep, TrainOutput};

let mut optimizer = AdamConfig::new().init();

for epoch in 0..100 {
    for batch in train_data {
        // Forward
        let output = model.forward(batch.features);
        let loss = output.cross_entropy_with_logits(batch.labels);
        
        // Backward
        let grads = loss.backward();
        
        // Update
        model = optimizer.step(learning_rate, model, grads);
    }
}
```

### Save/Load Model
```rust
use burn::record::{NamedMpkFileRecorder, Recorder};

// Save
let recorder = NamedMpkFileRecorder::new();
recorder.record(model.into_record(), "model.mpk")?;

// Load
let record = recorder.load("model.mpk")?;
let model = config.init(&device).load_record(record);
```

---

## Common Patterns

### Batch Processing
```rust
impl<B: Backend> MyModel<B> {
    // Single sample
    pub fn infer_one(&self, input: [f64; 8]) -> [f64; 3] {
        let tensor = Tensor::from_floats([input.map(|x| x as f32)], &self.device);
        let output = self.forward(tensor);
        let data = output.into_data();
        let values = data.as_slice::<f32>().unwrap();
        [values[0] as f64, values[1] as f64, values[2] as f64]
    }
    
    // Batch
    pub fn infer_batch(&self, inputs: Vec<[f64; 8]>) -> Vec<[f64; 3]> {
        let batch: Vec<_> = inputs.iter()
            .flat_map(|x| x.iter().map(|&v| v as f32))
            .collect();
        let tensor = Tensor::from_floats(batch, &self.device)
            .reshape([inputs.len(), 8]);
        let output = self.forward(tensor);
        // Convert back to Vec<[f64; 3]>
        todo!()
    }
}
```

### Error Handling
```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum LtnError {
    #[error("Invalid input shape: expected {expected}, got {actual}")]
    InvalidShape { expected: String, actual: String },
    
    #[error("Model not loaded")]
    ModelNotLoaded,
    
    #[error("Inference failed: {0}")]
    InferenceFailed(String),
}

pub type Result<T> = std::result::Result<T, LtnError>;
```

---

## Performance Tips

### Optimize Inference
```rust
// 1. Use no-grad mode
let output = model.forward(input).no_grad();

// 2. Batch multiple inputs
let batch = stack_inputs(vec![input1, input2, input3]);
let outputs = model.forward(batch);

// 3. Use GPU backend
type Backend = Wgpu; // or Cuda

// 4. Enable kernel fusion
use burn::backend::Fusion;
type Backend = Fusion<Wgpu>;
```

### Profile
```bash
# Install flamegraph
cargo install flamegraph

# Profile
cargo flamegraph --bin janus

# Criterion benchmarks
cargo bench --bench ltn_bench
```

---

## Testing Strategies

### Unit Tests
```rust
#[cfg(test)]
mod tests {
    use super::*;
    use burn::backend::NdArray;
    
    type TestBackend = NdArray;
    
    #[test]
    fn test_forward_pass() {
        let device = Default::default();
        let model = MyNetwork::<TestBackend>::new(&device);
        let input = Tensor::zeros([1, 8], &device);
        let output = model.forward(input);
        assert_eq!(output.dims(), [1, 3]);
    }
}
```

### Integration Tests
```rust
#[tokio::test]
async fn test_end_to_end() {
    let janus = JanusCore::new().await.unwrap();
    let features = [1.5, 0.0, 1.5, 0.75, 1.0, 1.0, 0.0, 0.4];
    let signal = janus.ltn.infer(features).unwrap();
    assert!(signal[0] >= 0.0 && signal[0] <= 1.0);
}
```

---

## Debugging

### Print Tensor Shapes
```rust
let x = some_tensor();
println!("Shape: {:?}", x.dims());
println!("Values: {:?}", x.clone().into_data());
```

### Conditional Compilation
```rust
#[cfg(debug_assertions)]
{
    println!("Debug: tensor shape = {:?}", x.dims());
}
```

### Logging
```rust
use tracing::{info, warn, error};

info!("Starting inference");
warn!("Latency spike: {}ms", latency);
error!("Model failed: {}", err);
```

---

## Migration Checklist

### Phase 1: LTN Network
- [ ] Add Burn dependencies
- [ ] Create `network.rs`
- [ ] Implement forward pass
- [ ] Write unit tests
- [ ] Benchmark inference

### Phase 2: Training
- [ ] Implement `trainer.rs`
- [ ] Add hybrid loss
- [ ] Test on synthetic data
- [ ] Save/load checkpoints

### Phase 3: Integration
- [ ] Create `janus-execution` crate
- [ ] Merge order management
- [ ] Update main binary
- [ ] Remove gRPC/Redis

### Phase 4: Validation
- [ ] Run 72-hour soak test
- [ ] Compare vs Python baseline
- [ ] Profile performance
- [ ] Fix bottlenecks

---

## Common Issues

### Issue: Recursion limit
```rust
// Add to lib.rs or main.rs
#![recursion_limit = "256"]
```

### Issue: Tensor device mismatch
```rust
// Ensure all tensors on same device
let x = x.to_device(&device);
let y = y.to_device(&device);
let z = x + y; // Now works
```

### Issue: Shape mismatch
```rust
// Always check shapes
assert_eq!(x.dims(), [batch_size, features]);
let x = x.reshape([new_batch, new_features]);
```

---

## Useful Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias ct='cargo test'
alias cb='cargo build --release'
alias cr='cargo run --release'
alias cbench='cargo bench'
alias ccheck='cargo clippy -- -W clippy::all'
```

---

## Resources

- **Burn Docs**: https://burn.dev/
- **Burn Discord**: https://discord.gg/uPEBbYYDB6
- **Burn Examples**: https://github.com/tracel-ai/burn/tree/main/examples
- **Internal Docs**: `fks/docs/research/`

---

**Last Updated**: February 2026
**Version**: 1.0