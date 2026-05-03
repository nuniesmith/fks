# JANUS Development Quick Reference

**Last Updated:** January 2025  
**Version:** 1.0

---

## 🚀 Quick Start

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/fks.git
cd fks/src/janus

# Install Rust (if needed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install CUDA toolkit (for GPU training)
# Ubuntu/WSL2:
wget https://developer.download.nvidia.com/compute/cuda/12.2.0/local_installers/cuda_12.2.0_535.54.03_linux.run
sudo sh cuda_12.2.0_535.54.03_linux.run

# Build all crates
cargo build --workspace

# Run tests
cargo test --workspace

# Run with CUDA support
cargo test --workspace --features cuda
```

### Docker Setup (Recommended for Training)

```bash
# Build training image
docker build -f Dockerfile.training -t janus-training .

# Run training with GPU
docker run --runtime=nvidia --gpus all \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/checkpoints:/app/checkpoints \
  janus-training

# Run TensorBoard
docker run -p 6006:6006 \
  -v $(pwd)/logs:/logs \
  tensorflow/tensorflow:latest \
  tensorboard --logdir=/logs --bind_all
```

---

## 📁 Project Structure

```
src/janus/
├── crates/
│   ├── brain/                      # 🧠 Neuromorphic Brain Regions
│   │   ├── visual-cortex/          # DiffGAF + ViViT
│   │   ├── thalamus/               # Multi-modal fusion
│   │   ├── basal-ganglia/          # Hierarchical RL
│   │   ├── hippocampus/            # Memory & replay
│   │   ├── prefrontal/             # LTN compliance
│   │   ├── amygdala/               # Risk management
│   │   ├── hypothalamus/           # Capital allocation
│   │   └── cerebellum/             # Optimal execution
│   │
│   ├── training/                   # 🎓 Training Infrastructure
│   │   ├── orchestrator/           # Multi-region coordinator
│   │   ├── model-registry/         # Version management
│   │   ├── metrics/                # TensorBoard integration
│   │   └── cuda/                   # GPU optimizations
│   │
│   └── integration/                # 🔗 Services
│       ├── forward-service/        # Inference (Wake)
│       └── backward-service/       # Training (Sleep)
│
├── lib/
│   ├── janus-core/                 # Core library
│   └── janus-api/                  # Public API
│
└── services/                       # Deployed services
    ├── forward/
    └── backward/
```

---

## 🧠 Brain Regions Cheat Sheet

| Region | Purpose | Input | Output | Latency |
|--------|---------|-------|--------|---------|
| **Visual Cortex** | Pattern recognition | OHLCV prices | Visual embedding | 5ms |
| **Thalamus** | Multi-modal fusion | Multi-sensor data | Unified state | 2ms |
| **Basal Ganglia** | Decision making | State | Goal + Action | 13ms |
| **Hippocampus** | Memory | Experience | Replay batch | N/A |
| **Prefrontal** | Compliance | State + Action | Approve/Veto | 3ms |
| **Amygdala** | Risk assessment | State | Threat level | 1ms |
| **Hypothalamus** | Position sizing | State + Equity | Position size | 2ms |
| **Cerebellum** | Execution | Order + State | Order slices | 5ms |

**Total Inference:** ~40ms (end-to-end)

---

## 💻 Common Commands

### Building

```bash
# Build all crates
cargo build --workspace

# Build with release optimizations
cargo build --workspace --release

# Build specific brain region
cargo build --package visual-cortex

# Build with CUDA support
cargo build --workspace --features cuda
```

### Testing

```bash
# Run all tests
cargo test --workspace

# Run specific crate tests
cargo test --package visual-cortex

# Run with output
cargo test --workspace -- --nocapture

# Run specific test
cargo test --package basal-ganglia test_ppo_training

# Run benchmarks
cargo bench --package visual-cortex
```

### Training

```bash
# Train visual cortex
cd crates/brain/visual-cortex
cargo run --release --features cuda --example train

# Train with backward service
cd services/backward
cargo run --release --features cuda

# View training metrics
tensorboard --logdir=./logs
```

### Model Management

```bash
# List available models
cargo run --bin model-registry -- list

# Select best model for region
cargo run --bin model-registry -- select visual-cortex --metric sharpe

# Deploy new model
cargo run --bin model-registry -- deploy visual-cortex v5

# Rollback to previous version
cargo run --bin model-registry -- rollback visual-cortex
```

---

## 🔥 Burn Framework Essentials

### Creating a Model

```rust
use burn::prelude::*;

#[derive(Module, Debug)]
pub struct MyModel<B: Backend> {
    linear1: Linear<B>,
    linear2: Linear<B>,
}

impl<B: Backend> MyModel<B> {
    pub fn new(device: &B::Device) -> Self {
        let linear1 = LinearConfig::new(128, 256).init(device);
        let linear2 = LinearConfig::new(256, 10).init(device);
        
        Self { linear1, linear2 }
    }
    
    pub fn forward(&self, x: Tensor<B, 2>) -> Tensor<B, 2> {
        let x = self.linear1.forward(x);
        let x = x.relu();
        self.linear2.forward(x)
    }
}
```

### Training Loop

```rust
use burn::optim::{AdamConfig, GradientsParams, Optimizer};

// Create model and optimizer
let device = CudaDevice::default();
let model = MyModel::new(&device);
let mut optimizer = AdamConfig::new().init();

// Training loop
for epoch in 0..100 {
    for (inputs, targets) in dataloader {
        // Forward pass
        let outputs = model.forward(inputs);
        let loss = MseLoss::new().forward(outputs, targets);
        
        // Backward pass
        let grads = loss.backward();
        
        // Update parameters
        model = optimizer.step(1e-3, model, grads);
    }
}
```

### Saving/Loading Models

```rust
// Save
model.save_file("model.bin", &CompactRecorder::new())?;

// Load
let model = MyModel::load_file(
    "model.bin",
    &CompactRecorder::new(),
    &device,
)?;

// Export to ONNX
model.export_onnx("model.onnx")?;
```

### Backend Selection

```rust
// CPU (development)
type Backend = burn::backend::NdArray;

// CUDA (training)
type Backend = burn::backend::Cuda;

// With autodiff (training)
type AutodiffBackend = burn::backend::Autodiff<burn::backend::Cuda>;
```

---

## 🎯 Development Workflows

### Adding a New Brain Region

1. **Create crate structure**
   ```bash
   cargo new --lib crates/brain/new-region
   cd crates/brain/new-region
   ```

2. **Define module trait**
   ```rust
   pub trait BrainRegion<B: Backend> {
       fn forward(&self, input: Tensor<B, 2>) -> Tensor<B, 2>;
       fn train(&mut self, data: &DataLoader) -> TrainingMetrics;
       fn save(&self, path: &str) -> Result<(), Error>;
       fn load(path: &str, device: &B::Device) -> Result<Self, Error>;
   }
   ```

3. **Implement the region**
   ```rust
   #[derive(Module, Debug)]
   pub struct NewRegion<B: Backend> {
       network: MLP<B>,
   }
   
   impl<B: Backend> BrainRegion<B> for NewRegion<B> {
       // Implementation
   }
   ```

4. **Add tests**
   ```rust
   #[cfg(test)]
   mod tests {
       use super::*;
       
       #[test]
       fn test_forward_pass() {
           let device = NdArray::default();
           let model = NewRegion::new(&device);
           let input = Tensor::random([32, 128], Distribution::Normal(0.0, 1.0), &device);
           let output = model.forward(input);
           assert_eq!(output.dims(), [32, 64]);
       }
   }
   ```

5. **Update workspace**
   ```toml
   # Cargo.toml
   [workspace]
   members = [
       # ...
       "crates/brain/new-region",
   ]
   ```

6. **Document**
   - Write README.md
   - Add inline documentation
   - Create examples

### Training a New Model

1. **Prepare dataset**
   ```rust
   let dataset = MarketDataset::from_csv("data/train.csv")?;
   let dataloader = DataLoaderBuilder::new()
       .batch_size(32)
       .shuffle(true)
       .build(dataset);
   ```

2. **Configure training**
   ```rust
   let config = TrainingConfig {
       learning_rate: 1e-4,
       epochs: 100,
       early_stopping: true,
       checkpoint_dir: "checkpoints/visual-cortex",
   };
   ```

3. **Train**
   ```rust
   let trainer = Trainer::new(config, device);
   let trained_model = trainer.train(model, dataloader)?;
   ```

4. **Evaluate**
   ```rust
   let metrics = evaluate(trained_model, val_dataloader)?;
   println!("Sharpe Ratio: {}", metrics.sharpe_ratio);
   ```

5. **Register model**
   ```rust
   let registry = ModelRegistry::new("models/");
   registry.register_model(
       BrainRegion::VisualCortex,
       ModelMetadata {
           version: 5,
           metrics: metrics,
           timestamp: Utc::now().timestamp(),
       },
       "checkpoints/visual-cortex/v5.bin",
   )?;
   ```

### Deploying a Model

1. **Select best model**
   ```bash
   cargo run --bin model-registry -- select visual-cortex --metric sharpe
   ```

2. **Export to ONNX**
   ```rust
   model.export_onnx("models/visual-cortex/v5.onnx")?;
   ```

3. **Update forward service**
   ```bash
   # Hot-swap without downtime
   cargo run --bin forward-service -- update visual-cortex v5
   ```

4. **Monitor performance**
   ```bash
   # Check metrics
   curl http://localhost:8080/metrics
   
   # View in Grafana
   open http://localhost:3000
   ```

---

## 🐛 Debugging Tips

### Enable Detailed Logging

```bash
# Set log level
export RUST_LOG=debug

# Filter by crate
export RUST_LOG=visual_cortex=debug,thalamus=info

# Run with logging
cargo run
```

### CUDA Debugging

```bash
# Check CUDA availability
nvidia-smi

# Set CUDA device
export CUDA_VISIBLE_DEVICES=0

# Enable CUDA error checking
export CUDA_LAUNCH_BLOCKING=1
```

### Performance Profiling

```bash
# Install perf
sudo apt-get install linux-tools-generic

# Profile inference
perf record --call-graph dwarf cargo run --release --example inference
perf report

# Memory profiling with valgrind
valgrind --tool=massif cargo run --example inference
```

### Tensor Debugging

```rust
// Print tensor shape
println!("Shape: {:?}", tensor.dims());

// Print tensor values
println!("Values: {:?}", tensor.to_data());

// Check for NaN/Inf
assert!(!tensor.any_nan());
assert!(!tensor.any_inf());

// Visualize as image (for GAF)
tensor.save_image("debug/gaf.png")?;
```

---

## 📊 Metrics & Monitoring

### Key Metrics to Track

**Training Metrics:**
- Loss (per epoch)
- Validation accuracy
- Sharpe ratio (backtest)
- Win rate
- Max drawdown

**Inference Metrics:**
- Latency (p50, p95, p99)
- Throughput (inferences/sec)
- Memory usage
- GPU utilization

**Trading Metrics:**
- PnL
- Sharpe ratio (live)
- Win rate (live)
- Slippage
- Compliance violations

### TensorBoard

```bash
# Start TensorBoard
tensorboard --logdir=logs --port=6006

# Log metrics in code
use training_metrics::MetricsWriter;

let mut writer = MetricsWriter::new("logs/visual-cortex");
writer.log_scalar("loss", loss_value, step);
writer.log_histogram("weights", weight_values, step);
writer.log_image("gaf", gaf_image, step);
```

### Prometheus

```rust
use prometheus::{Counter, Histogram, Registry};

lazy_static! {
    static ref INFERENCE_LATENCY: Histogram = Histogram::new(
        "inference_latency_ms",
        "Inference latency in milliseconds",
    ).unwrap();
    
    static ref TRADES_EXECUTED: Counter = Counter::new(
        "trades_executed_total",
        "Total trades executed",
    ).unwrap();
}

// Record metrics
let start = Instant::now();
let result = model.forward(input);
INFERENCE_LATENCY.observe(start.elapsed().as_millis() as f64);
```

---

## 🔒 Security & Compliance

### FTMO Rules Implementation

```rust
// Check daily loss limit (5%)
let daily_loss_ok = ltn.evaluate_rule(
    &Rule::Predicate("daily_loss_below_5pct".to_string()),
    &state,
);

// Check total loss limit (10%)
let total_loss_ok = ltn.evaluate_rule(
    &Rule::Predicate("total_loss_below_10pct".to_string()),
    &state,
);

// No news trading
let no_news_trading = ltn.evaluate_rule(
    &Rule::Not(Box::new(Rule::Predicate("near_news_event".to_string()))),
    &state,
);

// Combined compliance check
let compliance = ltn.t_norm(&daily_loss_ok, &total_loss_ok);
let compliance = ltn.t_norm(&compliance, &no_news_trading);
```

### Circuit Breakers

```rust
// Implement kill switch
if amygdala.assess_threat(&state).score > 0.9 {
    emergency_shutdown();
}

// Drawdown circuit breaker
if current_drawdown > 0.08 {
    halt_trading();
    notify_admin("Circuit breaker triggered: 8% drawdown");
}
```

---

## 📚 Resources

### Documentation
- [Burn Book](https://burn.dev/book/) - Official Burn framework guide
- [JANUS Whitepaper](../research/JANUS_ARCHITECTURAL_SPECIFICATION.md) - Architecture spec
- [12-Week Plan](JANUS_BURN_12_WEEK_PLAN.md) - Implementation roadmap
- [Crate Reorganization](CRATE_REORGANIZATION_PLAN.md) - Structure guide

### Papers
- [Gramian Angular Fields](https://arxiv.org/abs/1506.00327) - Wang & Oates, 2015
- [ViViT](https://arxiv.org/abs/2103.15691) - Arnab et al., 2021
- [Logic Tensor Networks](https://arxiv.org/abs/2012.13635) - Badreddine et al., 2022
- [Hierarchical RL](https://arxiv.org/abs/1604.06057) - Vezhnevets et al., 2016

### Tools
- [TensorBoard](https://www.tensorflow.org/tensorboard) - Metrics visualization
- [ONNX Runtime](https://onnxruntime.ai/) - Inference optimization
- [Grafana](https://grafana.com/) - Monitoring dashboards
- [Prometheus](https://prometheus.io/) - Metrics collection

---

## 🆘 Common Issues & Solutions

### Issue: CUDA out of memory
**Solution:**
```rust
// Reduce batch size
let config = TrainingConfig {
    batch_size: 16, // Instead of 32
    // ...
};

// Enable gradient checkpointing
#[checkpoint]
encoder: LargeEncoder<B>,

// Use mixed precision
config.with_mixed_precision(true)
```

### Issue: Slow training
**Solution:**
```bash
# Use CUDA instead of CPU
cargo run --features cuda

# Enable optimizations
cargo run --release

# Use multiple GPUs (future)
export CUDA_VISIBLE_DEVICES=0,1
```

### Issue: Model not converging
**Solution:**
```rust
// Adjust learning rate
optimizer = AdamConfig::new()
    .with_learning_rate(1e-5) // Lower
    .init();

// Add learning rate scheduler
scheduler = CosineAnnealingLR::new(1e-4, 1e-6, 1000);

// Check for NaN gradients
if grads.has_nan() {
    panic!("NaN gradient detected!");
}
```

### Issue: High inference latency
**Solution:**
```rust
// Export to ONNX
model.export_onnx("model.onnx")?;

// Use ONNX Runtime
let session = ort::Session::builder()?
    .with_optimization_level(OptimizationLevel::All)?
    .with_model_from_file("model.onnx")?;

// Enable quantization
let quantized = quantize_model(&model, QuantizationType::FP16);
```

---

## 🎯 Next Steps

1. **Start Development**
   ```bash
   cd fks/src/janus
   cargo build --workspace
   cargo test --workspace
   ```

2. **Follow 12-Week Plan**
   - Week 1: Setup & infrastructure
   - Weeks 2-3: Visual cortex
   - Weeks 4-6: Decision regions
   - Weeks 7-9: Safety & execution
   - Weeks 10-12: Integration & production

3. **Join the Community**
   - Read the whitepaper
   - Review existing PRs
   - Ask questions in Discord

4. **Contribute**
   - Pick an issue from GitHub
   - Follow coding standards
   - Submit PR with tests

---

**Happy Building! 🚀**

For questions or issues, refer to:
- [Main Documentation](../README.md)
- [Troubleshooting Guide](../operations/TROUBLESHOOTING.md)
- [Architecture Spec](../research/JANUS_ARCHITECTURAL_SPECIFICATION.md)