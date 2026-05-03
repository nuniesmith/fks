# Burn Framework Quick Fixes for JANUS

**Priority fixes to implement immediately for better Burn usage**

---

## 🔴 CRITICAL FIXES (Do These First)

### 1. Add Recursion Limit (Required for WGPU)

```rust
// Add at the TOP of src/janus/crates/ml/src/lib.rs
#![recursion_limit = "256"]
```

**Why:** WGPU backend will fail to compile without this.

---

### 2. Update Cargo.toml Features

```toml
[dependencies.burn]
version = "0.19"
default-features = false
features = ["std", "ndarray", "train", "fusion"]

[dependencies.burn-wgpu]
version = "0.19"
optional = true
features = ["fusion"]
```

**Why:** Enables kernel fusion optimization for 20-30% performance boost.

---

### 3. Use Module Derive

**BEFORE:**
```rust
pub struct LstmPredictor<B: Backend> {
    lstm_layers: Vec<Lstm<B>>,
    output: Linear<B>,
    config: LstmConfig,
}
```

**AFTER:**
```rust
#[derive(Module, Debug)]
pub struct LstmPredictor<B: Backend> {
    lstm_layers: Vec<Lstm<B>>,
    output: Linear<B>,
    // Config stored separately or use #[module(skip)]
}

#[derive(Config, Debug)]
pub struct LstmPredictorConfig {
    pub input_size: usize,
    pub hidden_size: usize,
    #[config(default = "0.2")]
    pub dropout: f64,
}

impl LstmPredictorConfig {
    pub fn init<B: Backend>(&self, device: &B::Device) -> LstmPredictor<B> {
        // Initialize model here
    }
}
```

---

## 🟡 HIGH PRIORITY (Week 1)

### 4. Fix Inference Mode

**PROBLEM:** Running autodiff during inference wastes 30-50% memory.

**SOLUTION:**
```rust
// For inference/validation
pub fn predict<B: AutodiffBackend>(
    model: &LstmPredictor<B>,
    input: Tensor<B, 3>,
) -> Tensor<B::InnerBackend, 2> {
    let input_inner = input.inner();
    model.valid().forward(input_inner)
}
```

---

### 5. Use Burn's Record System

**BEFORE:**
```rust
// Custom serialization
bincode::serialize(&model)?;
```

**AFTER:**
```rust
use burn::record::CompactRecorder;

// Save
model.save_file("model.mpk", &CompactRecorder::new())?;

// Load
let record = CompactRecorder::new()
    .load("model.mpk".into(), &device)?;
let model = config.init(&device).load_record(record);
```

**Benefits:** 50% smaller files (uses f16), works with any backend.

---

### 6. Implement Batcher Trait

```rust
use burn::data::dataloader::batcher::Batcher;

#[derive(Clone, Default)]
pub struct MarketBatcher;

impl<B: Backend> Batcher<B, MarketDataSample, MarketBatch<B>> 
    for MarketBatcher 
{
    fn batch(&self, items: Vec<MarketDataSample>, device: &B::Device) -> MarketBatch<B> {
        let features = items.iter()
            .map(|item| Tensor::<B, 2>::from_data(item.features, device))
            .map(|t| t.unsqueeze_dim(0))
            .collect();
        
        let features = Tensor::cat(features, 0);
        
        let targets = items.iter()
            .map(|item| Tensor::<B, 1>::from_data([item.target], device))
            .collect();
        
        let targets = Tensor::cat(targets, 0).unsqueeze_dim(1);
        
        MarketBatch { features, targets }
    }
}
```

---

## 🟢 MEDIUM PRIORITY (Week 2-3)

### 7. Use TrainStep and ValidStep

```rust
use burn::train::{TrainStep, ValidStep, TrainOutput};

impl<B: AutodiffBackend> TrainStep<MarketBatch<B>, PredictionOutput<B>> 
    for LstmPredictor<B> 
{
    fn step(&self, batch: MarketBatch<B>) -> TrainOutput<PredictionOutput<B>> {
        let predictions = self.forward(batch.features);
        let loss = MseLoss::new().forward(
            predictions.clone(),
            batch.targets.clone(),
            Reduction::Mean,
        );
        
        let output = PredictionOutput {
            loss: loss.clone(),
            predictions,
            targets: batch.targets,
        };
        
        TrainOutput::new(self, loss.backward(), output)
    }
}

impl<B: Backend> ValidStep<MarketBatch<B>, PredictionOutput<B>> 
    for LstmPredictor<B> 
{
    fn step(&self, batch: MarketBatch<B>) -> PredictionOutput<B> {
        let predictions = self.forward(batch.features);
        let loss = MseLoss::new().forward(
            predictions.clone(),
            batch.targets.clone(),
            Reduction::Mean,
        );
        
        PredictionOutput { loss, predictions, targets: batch.targets }
    }
}
```

---

### 8. Use Learner Instead of Custom Training Loop

```rust
use burn::train::{LearnerBuilder, LearningStrategy};
use burn::train::metric::LossMetric;
use burn::record::CompactRecorder;

let learner = LearnerBuilder::new(artifact_dir)
    .metric_train_numeric(LossMetric::new())
    .metric_valid_numeric(LossMetric::new())
    .with_file_checkpointer(CompactRecorder::new())
    .learning_strategy(LearningStrategy::SingleDevice(device))
    .num_epochs(config.epochs)
    .summary()
    .build(model, optimizer, learning_rate);

let result = learner.fit(train_loader, val_loader);
```

**Benefits:**
- Automatic checkpointing
- Built-in TUI dashboard
- Metrics tracking
- Less code to maintain

---

## ⚡ PERFORMANCE TIPS

### Reduce Tensor Clones

**BEFORE:**
```rust
let mean = input.clone().mean();
let std = input.clone().std();
let normalized = (input.clone() - mean) / std;
```

**AFTER:**
```rust
let mean = input.clone().mean();
let std = input.clone().std();
let normalized = (input - mean) / std;  // Last use, no clone needed
```

---

### Use DataLoader Multi-threading

```rust
let dataloader = DataLoaderBuilder::new(batcher)
    .batch_size(32)
    .shuffle(seed)
    .num_workers(4)  // Parallel data loading
    .build(dataset);
```

---

### Normalize Data in Batcher

```rust
impl<B: Backend> Batcher<B, MarketDataSample, MarketBatch<B>> 
    for MarketBatcher 
{
    fn batch(&self, items: Vec<MarketDataSample>, device: &B::Device) -> MarketBatch<B> {
        // ... create features tensor ...
        
        // Z-score normalization
        let mean = features.clone().mean();
        let std = features.clone().var(0).sqrt();
        let features = (features - mean) / (std + 1e-8);
        
        MarketBatch { features, targets }
    }
}
```

---

## 📊 DEBUGGING HELPERS

### Print Tensor Details

```rust
// Basic print
println!("{}", tensor);

// Precision control
println!("{:.4}", tensor);

// Global print options
use burn::tensor::{set_print_options, PrintOptions};

set_print_options(PrintOptions {
    precision: Some(4),
    threshold: 1000,
    edge_items: 3,
    ..Default::default()
});
```

---

### Check Model Closeness (Import Validation)

```rust
use burn::tensor::check_closeness;

// Compare two model outputs
check_closeness(&output1, &output2);

// Shows percentage of elements within different epsilon values
// Useful for verifying PyTorch -> Burn conversions
```

---

### Display Module Structure

```rust
// Just print the model
println!("{}", model);

// Or implement custom display
#[derive(Module, Debug)]
#[module(custom_display)]
pub struct MyModel<B: Backend> { /* ... */ }

impl<B: Backend> ModuleDisplay for MyModel<B> {
    fn custom_settings(&self) -> Option<DisplaySettings> {
        DisplaySettings::new()
            .with_show_num_parameters(true)
            .optional()
    }
}
```

---

## 🧪 TESTING HELPERS

### Test Model Forward Pass

```rust
#[test]
fn test_forward_pass() {
    let device = Default::default();
    let config = LstmConfig::new(10, 64, 1);
    let model = config.init::<NdArray<f32>>(&device);
    
    let input = Tensor::<NdArray<f32>, 3>::random(
        [2, 5, 10],  // [batch, seq_len, features]
        Distribution::Normal(0.0, 1.0),
        &device,
    );
    
    let output = model.forward(input);
    assert_eq!(output.dims(), [2, 1]);
}
```

---

### Test Save/Load

```rust
#[test]
fn test_save_load() {
    let device = Default::default();
    let config = LstmConfig::new(10, 64, 1);
    let model1 = config.init::<NdArray<f32>>(&device);
    
    // Save
    model1.save_file("test_model.mpk", &CompactRecorder::new()).unwrap();
    
    // Load
    let record = CompactRecorder::new()
        .load("test_model.mpk".into(), &device)
        .unwrap();
    let model2 = config.init(&device).load_record(record);
    
    // Compare outputs
    let input = Tensor::random([1, 5, 10], Distribution::Normal(0.0, 1.0), &device);
    let out1 = model1.forward(input.clone());
    let out2 = model2.forward(input);
    
    check_closeness(&out1, &out2);
}
```

---

## 📝 QUICK REFERENCE

### Essential Imports

```rust
use burn::prelude::*;  // Gets most common types
use burn::module::{Module, Param};
use burn::config::Config;
use burn::train::{TrainStep, ValidStep, TrainOutput};
use burn::data::dataloader::batcher::Batcher;
use burn::record::CompactRecorder;
```

### Common Backend Types

```rust
type CpuBackend = NdArray<f32>;
type AutodiffCpuBackend = Autodiff<NdArray<f32>>;

#[cfg(feature = "gpu")]
type GpuBackend = Wgpu<f32, i32>;

#[cfg(feature = "gpu")]
type AutodiffGpuBackend = Autodiff<Wgpu<f32, i32>>;
```

---

## 🎯 MIGRATION PRIORITY

1. ✅ Add recursion limit
2. ✅ Update Cargo.toml features
3. ✅ Use `#[derive(Module)]`
4. ✅ Use `#[derive(Config)]`
5. ✅ Fix inference mode (`.inner()`, `.valid()`)
6. ✅ Switch to CompactRecorder
7. ⏭️ Implement Batcher trait
8. ⏭️ Implement TrainStep/ValidStep
9. ⏭️ Migrate to Learner
10. ⏭️ Add custom metrics

---

**Time Estimate:**
- Critical fixes: 1-2 hours
- High priority: 1 week
- Medium priority: 2-3 weeks

**Expected Improvements:**
- 30-50% memory reduction (inference mode)
- 20-30% speed boost (fusion)
- 50% smaller model files (CompactRecorder)
- 40% less training code (Learner)

---

**Last Updated:** 2025-01-07  
**See Also:** `BURN_IMPROVEMENTS.md` for detailed explanations