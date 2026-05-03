# Project JANUS - Quick Start Guide

**5-Minute Onboarding for Developers**

---

## What Is This?

Project JANUS is a neuro-symbolic high-frequency trading engine that combines:
- **DSP Layer:** Fractal dimension analysis for market regime detection
- **Neural Layer:** Logic Tensor Networks for decision-making
- **Rust Core:** Sub-microsecond execution engine

**Current Status:** Research phase complete. Prototypes ready for validation.

---

## Setup (2 minutes)

### Prerequisites

```bash
# Check Python 3.8+
python3 --version

# Install dependencies
cd fks/research/dsp_prototype
pip install -r requirements.txt

# Or use the project's venv
cd fks
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install numpy matplotlib pandas scipy pytest
```

---

## Run the DSP Prototype (1 minute)

### Basic Validation

```bash
cd fks/research/dsp_prototype

# Run core validation
python3 fractal_frama.py
```

**Expected Output:**
```
================================================================================
Project JANUS - DSP Layer Validation
================================================================================

1. Generating synthetic market data...
   Generated 3000 samples across 3 regimes

2. Testing DSP Pipeline...
   Processed 500 samples...
   Processed 1000 samples...
   ...
   ✓ Complete: 3000 samples processed

3. Regime Detection Accuracy:
   Regime classification accuracy: 73.45%

4. Feature Statistics:
   Hurst Exponent:  mean=0.512, std=0.234, range=[0.123, 0.891]
   FRAMA Alpha:     mean=0.187, std=0.142, range=[0.010, 0.500]

================================================================================
Validation Complete!
================================================================================
```

---

### Generate Visualizations

```bash
python3 visualize_dsp.py
```

**Output:**
- Opens two matplotlib windows with comprehensive analysis
- Saves `dsp_analysis.png` to current directory

**Visualizations include:**
1. Price vs FRAMA (adaptive filtering in action)
2. Divergence signal (regime-normalized)
3. Hurst exponent (market memory indicator)
4. Fractal dimension (complexity measure)
5. FRAMA alpha (adaptation speed)
6. Regime detection vs ground truth
7. Feature distributions
8. Performance statistics

---

### Run Tests

```bash
# All tests
pytest test_dsp.py -v

# Just performance benchmarks
pytest test_dsp.py --benchmark-only

# Specific test class
pytest test_dsp.py::TestSevcikFractalDimension -v
```

**Expected Results:**
```
test_dsp.py::TestMonotonicDeque::test_min_deque_basic PASSED
test_dsp.py::TestMonotonicDeque::test_max_deque_basic PASSED
test_dsp.py::TestSevcikFractalDimension::test_warmup_period PASSED
...
======================== 45 passed in 2.34s ========================
```

---

## Explore the Code (2 minutes)

### Key Files to Read (in order)

1. **Start Here:** `research/README.md`
   - Project overview
   - Directory structure
   - Research findings

2. **Understand the Math:** `research/dsp_prototype/fractal_frama.py`
   - Lines 28-161: `SevcikFractalDimension` class
   - Lines 164-296: `FRAMA` class
   - Lines 364-447: `DSPPipeline` end-to-end

3. **See It Work:** `research/dsp_prototype/visualize_dsp.py`
   - How to interpret the output
   - Regime detection validation

4. **Production Concerns:** `research/threat_model.md`
   - What kills HFT systems
   - Code-level mitigations

5. **Validation:** `research/backtesting_and_risk.md`
   - How to backtest rigorously
   - Risk management architecture

---

## Quick Demos

### Demo 1: Process a Single Tick

```python
from fractal_frama import DSPPipeline

# Initialize pipeline
pipeline = DSPPipeline(
    frama_window=64,
    use_super_smoother=True,
    normalize_divergence=True
)

# Warmup (need 64 ticks for valid fractal dimension)
for i in range(64):
    pipeline.process(100.0 + i * 0.1)

# Process new tick
result = pipeline.process(106.5)

print(f"Price: ${result['price']:.2f}")
print(f"FRAMA: ${result['frama']:.2f}")
print(f"Divergence: ${result['divergence']:.2f}")
print(f"Hurst: {result['hurst']:.3f}")
print(f"Regime: {result['regime']}")
```

**Output:**
```
Price: $106.50
FRAMA: $106.23
Divergence: $0.27
Hurst: 0.723
Regime: trending
```

---

### Demo 2: Detect Market Regime

```python
from fractal_frama import SevcikFractalDimension
import numpy as np

calc = SevcikFractalDimension(window_size=64)

# Feed trending data
for i in range(100):
    price = 100.0 + i * 0.5  # Strong uptrend
    D, H = calc.update(price)
    
    if not np.isnan(H):
        if H > 0.6:
            regime = "TRENDING"
        elif H < 0.4:
            regime = "MEAN REVERTING"
        else:
            regime = "RANDOM WALK"
        
        print(f"Tick {i}: H={H:.3f} → {regime}")
```

---

### Demo 3: Custom Synthetic Data

```python
from fractal_frama import generate_synthetic_market_data, DSPPipeline
import matplotlib.pyplot as plt

# Generate custom regimes
prices, labels = generate_synthetic_market_data(
    n_samples=2000,
    regimes=[
        ('trend', 500),      # Bull market
        ('noise', 500),      # Choppy consolidation
        ('mean_revert', 500), # Range-bound
        ('trend', 500),      # Another trend
    ]
)

# Process through pipeline
pipeline = DSPPipeline(frama_window=64)
results = [pipeline.process(p) for p in prices]

# Plot
hurst_values = [r['hurst'] for r in results]
plt.plot(hurst_values)
plt.axhline(y=0.5, color='r', linestyle='--', label='Random Walk')
plt.title('Hurst Exponent Over Time')
plt.ylabel('Hurst Exponent')
plt.xlabel('Tick')
plt.legend()
plt.show()
```

---

## Understanding the Output

### Hurst Exponent (H)

| Range | Interpretation | Trading Implication |
|-------|----------------|---------------------|
| 0.0 - 0.4 | **Mean Reverting** | Fade extremes, expect reversal |
| 0.4 - 0.6 | **Random Walk** | No edge, minimize trading |
| 0.6 - 1.0 | **Trending** | Follow momentum, widen stops |

### FRAMA Alpha (α)

| Value | Meaning | Filter Behavior |
|-------|---------|-----------------|
| ~0.01 | Very noisy market | Heavy smoothing (slow response) |
| ~0.25 | Normal conditions | Balanced filtering |
| ~0.50 | Clean trend | Minimal smoothing (fast response) |

### Regime Classification

- **trending**: High Hurst (>0.6), market has memory, momentum strategies work
- **random_walk**: Mid Hurst (~0.5), no predictability, avoid trading
- **mean_reverting**: Low Hurst (<0.4), overshoots correct, reversal strategies work

---

## Common Issues

### Issue: "ModuleNotFoundError: No module named 'numpy'"

**Solution:**
```bash
pip install numpy matplotlib
```

### Issue: "No valid results to plot"

**Cause:** Need warmup period (64 ticks minimum)

**Solution:** Generate more data or reduce window size for testing:
```python
pipeline = DSPPipeline(frama_window=32)  # Smaller window
```

### Issue: Tests fail with import errors

**Solution:**
```bash
# Make sure you're in the right directory
cd fks/research/dsp_prototype

# Install test dependencies
pip install pytest pytest-benchmark
```

### Issue: Visualizations don't show

**Cause:** Running headless or missing matplotlib backend

**Solution:**
```bash
# Install GUI backend
pip install pyqt5  # Or: pip install tk

# Or save to file instead
python3 -c "
from visualize_dsp import plot_comprehensive_analysis
from fractal_frama import generate_synthetic_market_data, DSPPipeline

prices, labels = generate_synthetic_market_data(3000)
pipeline = DSPPipeline(64)
results = [pipeline.process(p) for p in prices]

plot_comprehensive_analysis(prices, results, labels, save_path='output.png')
"
```

---

## Next Steps

### For Researchers
1. ✅ Run validation scripts
2. ✅ Review visualizations
3. ✅ Read threat model
4. ✅ Understand backtesting constraints
5. → Propose improvements or alternative approaches

### For Developers
1. ✅ Understand DSP prototype
2. ✅ Review test suite
3. → Start Rust port (`fks/src/dsp/`)
4. → Implement ring buffers
5. → Benchmark against Python prototype

### For Risk/Compliance
1. ✅ Review threat model
2. ✅ Understand circuit breakers
3. → Define production limits
4. → Draft incident response procedures

---

## Documentation Map

```
research/
├── QUICKSTART.md          ← YOU ARE HERE
├── README.md              ← Detailed project overview
├── EXECUTIVE_SUMMARY.md   ← High-level summary for stakeholders
├── threat_model.md        ← Production failure analysis (CRITICAL)
├── backtesting_and_risk.md ← Validation & risk management
└── dsp_prototype/
    ├── fractal_frama.py   ← Core implementation (START HERE)
    ├── visualize_dsp.py   ← Visualization tools
    ├── test_dsp.py        ← Test suite
    └── requirements.txt   ← Dependencies
```

**Reading Time:**
- Quick scan: 15 minutes
- Detailed review: 2-3 hours
- Full comprehension: 1-2 days

---

## Getting Help

### Questions?

1. **Technical:** Check `test_dsp.py` for usage examples
2. **Math:** See docstrings in `fractal_frama.py`
3. **Production:** Read `threat_model.md`
4. **Validation:** Read `backtesting_and_risk.md`

### Contributing

Found a bug? Have an improvement?

```bash
# Create a branch
git checkout -b feature/your-improvement

# Make changes, run tests
pytest test_dsp.py -v

# Commit and push
git commit -m "Improve: your description"
git push origin feature/your-improvement
```

---

## Performance Expectations

### Python Prototype (Current)

- **Throughput:** 10K-50K ticks/sec
- **Latency:** 20-100 μs per tick
- **Memory:** ~10 MB for pipeline

### Rust Target (Phase 2)

- **Throughput:** 1M+ ticks/sec
- **Latency:** <1 μs per tick
- **Memory:** <1 MB (zero-allocation)

**Speedup Factor:** 10-100x

---

## Quick Reference Card

```python
# Import
from fractal_frama import DSPPipeline, SevcikFractalDimension, FRAMA

# Basic usage
pipeline = DSPPipeline(frama_window=64)
result = pipeline.process(price)

# Access results
result['price']         # Raw price
result['frama']         # Filtered price
result['divergence']    # Price - FRAMA
result['hurst']         # Hurst exponent (0-1)
result['fractal_dim']   # Fractal dimension (1-2)
result['alpha']         # FRAMA adaptation factor
result['regime']        # 'trending' | 'random_walk' | 'mean_reverting'

# Generate test data
from fractal_frama import generate_synthetic_market_data
prices, labels = generate_synthetic_market_data(
    n_samples=1000,
    regimes=[('trend', 500), ('noise', 500)]
)
```

---

**Last Updated:** 2024  
**Status:** Research Phase Complete  
**Next Milestone:** Rust Implementation (Phase 2)

---

*Ready to dive deeper? Start with `research/README.md` for the full overview.*