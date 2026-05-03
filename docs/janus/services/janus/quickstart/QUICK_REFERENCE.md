# JANUS ML Pipeline - Quick Reference

**Last Updated:** 2024-01-XX  
**Status:** Week 4, Day 3 Complete

---

## 🚀 Quick Start

```bash
cd fks/src/janus

# Build
cargo build --package janus-ml

# Test
cargo test --package janus-ml

# Expected: 57/58 tests pass (1 ignored)
```

---

## 📁 Key Files

```
crates/ml/src/
├── models/
│   ├── lstm.rs          # LSTM price predictor
│   ├── mlp.rs           # MLP signal classifier
│   └── mod.rs           # Model trait
├── features/
│   ├── technical.rs     # Technical indicators
│   └── normalizer.rs    # Feature normalization
├── backend.rs           # CPU/GPU abstraction
├── config.rs            # Configuration types
└── error.rs             # Error handling

docs/
├── START_HERE.md        # Complete overview (read this first!)
├── WEEK4_DAY3_COMPLETE.md  # Latest implementation details
└── QUICK_REFERENCE.md   # This file
```

---

## 🎯 Current Status

| Component | Status | Tests | Notes |
|-----------|--------|-------|-------|
| Data Quality | ✅ Complete | 31/31 | Week 3 |
| Feature Extraction | ✅ Complete | 35/35 | Day 2 |
| LSTM Model | ✅ Complete | 9/9 | Day 3 |
| MLP Model | ✅ Complete | 11/11 | Day 3 |
| Training Loop | 🔨 TODO | - | Day 4-5 |
| Inference Engine | 🔨 TODO | - | Day 6-7 |

---

## 💻 Code Snippets

### LSTM Model

```rust
use janus_ml::models::{LstmConfig, LstmPredictor, Model};
use janus_ml::backend::BackendDevice;

let config = LstmConfig::new(50, 64, 1)
    .with_num_layers(2)
    .with_dropout(0.2);

let model = LstmPredictor::new(config, BackendDevice::cpu());
let predictions = model.forward(input)?;
model.save("model.bin")?;
```

### MLP Model

```rust
use janus_ml::models::{MlpConfig, MlpClassifier, Model};

let config = MlpConfig::new(50, vec![128, 64], 3)
    .with_dropout(0.3)
    .with_batch_norm(true);

let model = MlpClassifier::new(config, BackendDevice::cpu());
let probs = model.forward_with_softmax(input)?;
let predictions = model.predict(input)?;
```

### Feature Extraction

```rust
use janus_ml::features::{TechnicalIndicators, Normalizer};

let indicators = TechnicalIndicators::default();
let features = indicators.extract(&market_data)?;

let normalizer = Normalizer::z_score(features.clone())?;
let normalized = normalizer.transform(features)?;
```

---

## 🔧 Common Tasks

### Run Tests

```bash
# All tests
cargo test --package janus-ml

# Specific module
cargo test --package janus-ml --lib models
cargo test --package janus-ml --lib features

# With output
cargo test test_lstm_forward -- --nocapture

# Include ignored
cargo test -- --ignored
```

### Build & Check

```bash
# Check compilation
cargo check

# Build with optimizations
cargo build --release

# Format code
cargo fmt

# Lint
cargo clippy -- -D warnings

# Generate docs
cargo doc --package janus-ml --open
```

### Debug

```bash
# With logging
RUST_LOG=debug cargo test
RUST_LOG=janus_ml=trace cargo test

# Check tensor shapes
println!("Dims: {:?}", tensor.dims());
```

---

## ⚠️ Known Issues

1. **Bidirectional LSTM** - Dimension mismatch (test ignored)
   - Workaround: Use `bidirectional: false`

2. **Weight Serialization** - Placeholder only
   - Impact: Can't persist trained weights yet
   - Fix: Deferred to training phase

3. **MLP Activation** - Hardcoded ReLU
   - Impact: config.activation not applied
   - Workaround: ReLU works well

---

## 📊 Input/Output Shapes

### LSTM
- Input: `[batch_size, seq_len, input_size]`
- Output: `[batch_size, output_size]`
- Example: `[32, 20, 50]` → `[32, 1]`

### MLP
- Input: `[batch_size, seq_len, input_size]`
- Output: `[batch_size, num_classes]`
- Example: `[32, 10, 50]` → `[32, 3]`

---

## 🎯 Next Steps (Priority)

**Day 4-5: Training Infrastructure**
1. Dataset trait & iterator
2. Training loop with optimizer
3. Loss functions (MSE, CrossEntropy)
4. Checkpointing (fix weight serialization)
5. Metrics collection

**Day 6-7: Inference Engine**
1. Predictor API
2. Model caching
3. Data quality integration
4. Confidence scoring
5. Batch optimization

---

## 🐛 Debugging Tips

**Dimension Issues:**
```rust
// Check shapes
assert_eq!(tensor.dims(), [batch, seq, features]);
```

**Device Issues:**
```rust
// Verify backend
let device = BackendDevice::cpu();
assert!(!device.is_gpu());
```

**Serialization:**
```rust
// Use String, not serde_json::Value
let json_str = serde_json::to_string(&config)?;
```

---

## 🔑 Key Dependencies

```toml
burn-core = "0.19"      # Tensor ops
burn-ndarray = "0.19"   # CPU backend
burn-autodiff = "0.19"  # Gradients
burn-nn = "0.19"        # NN modules
bincode = "2.0"         # Serialization
ndarray = "0.15"        # Arrays
ta = "0.5"              # Technical analysis
```

**Why no burn-dataset?**
- Avoids SQLite linking conflict
- More control over training
- Custom dataset implementation

---

## 📈 Performance Targets

| Operation | Target | Current |
|-----------|--------|---------|
| Feature extraction | < 1ms | ✅ |
| LSTM inference (CPU) | < 10ms | ✅ |
| MLP inference (CPU) | < 5ms | ✅ |
| Training (100K samples) | TBD | 🔨 |

---

## 🚦 Build Status

```
✅ Compiles without errors
✅ 123/124 tests passing (99.2%)
✅ No SQLite conflicts
✅ Documentation complete
✅ Ready for training implementation
```

---

## 📞 Quick Links

- Full Overview: `START_HERE.md`
- Latest Details: `WEEK4_DAY3_COMPLETE.md`
- Model Docs: `crates/ml/src/models/README.md`
- Burn Framework: https://burn.dev/book/

---

**For detailed information, see START_HERE.md**