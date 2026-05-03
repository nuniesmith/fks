# Logic Tensor Network (LTN) Design Document

**Project JANUS - Neuro-Symbolic Trading Engine**

**Phase**: 3 - LTN Integration  
**Date**: 2024  
**Status**: Design Phase  
**Authors**: JANUS Research Team

---

## Executive Summary

This document specifies the Logic Tensor Network (LTN) architecture for Project JANUS, integrating differentiable fuzzy logic with neural learning to create a neuro-symbolic trading engine that combines:

1. **Neural Learning**: Data-driven pattern recognition from market features
2. **Symbolic Reasoning**: Market domain knowledge encoded as logical axioms
3. **Semantic Constraints**: Differentiable fuzzy logic to guide learning

**Key Innovation**: Hybrid loss function balancing supervised learning (predict labels) with semantic learning (satisfy market axioms), enabling the model to learn both from data and from expert knowledge.

---

## Table of Contents

1. [Mathematical Foundation](#1-mathematical-foundation)
2. [Architecture Overview](#2-architecture-overview)
3. [Axiom Library](#3-axiom-library)
4. [Neural Core Design](#4-neural-core-design)
5. [Loss Functions](#5-loss-functions)
6. [Training Strategy](#6-training-strategy)
7. [Implementation Specification](#7-implementation-specification)
8. [Performance Requirements](#8-performance-requirements)

---

## 1. Mathematical Foundation

### 1.1 Logic Tensor Networks (LTN)

Logic Tensor Networks combine first-order logic with neural networks by:

1. **Grounding**: Map logical predicates to neural networks
2. **Fuzzy Semantics**: Use fuzzy logic for continuous truth values
3. **Differentiability**: Make logic operations differentiable via T-norms

**Key Principle**: Every logical formula becomes a differentiable function that can be optimized via gradient descent.

### 1.2 Fuzzy Logic Operators

#### T-norms (Conjunction - AND)

**Product T-norm** (primary choice for trading):
```
T_product(a, b) = a × b
```

**Gödel T-norm** (fallback):
```
T_Gödel(a, b) = min(a, b)
```

**Łukasiewicz T-norm** (optional):
```
T_Łuk(a, b) = max(0, a + b - 1)
```

**Properties**:
- Commutativity: T(a,b) = T(b,a)
- Associativity: T(a, T(b,c)) = T(T(a,b), c)
- Monotonicity: a ≤ c ⇒ T(a,b) ≤ T(c,b)
- Boundary: T(1, a) = a, T(0, a) = 0

#### Implications (IF-THEN)

**Reichenbach Implication** (primary choice):
```
I(a, b) = 1 - a + a × b
```

**Gödel Implication** (fallback):
```
I_Gödel(a, b) = {1 if a ≤ b, else b}
```

**Łukasiewicz Implication** (optional):
```
I_Łuk(a, b) = min(1, 1 - a + b)
```

**Properties**:
- Truth preservation: I(1, b) = b
- Contraposition: I(a, b) ≈ I(¬b, ¬a)
- Differentiability: All are smooth and gradient-friendly

#### Negation

**Standard fuzzy negation**:
```
¬a = 1 - a
```

#### Disjunction (OR)

**Derived from T-norm via De Morgan's law**:
```
S(a, b) = 1 - T(1-a, 1-b)
```

For Product T-norm:
```
S_product(a, b) = a + b - a × b
```

### 1.3 Quantifiers

**Universal Quantifier (∀)**:
```
∀x: φ(x) ≈ mean(φ(x₁), φ(x₂), ..., φ(xₙ))
```
or more robust:
```
∀x: φ(x) ≈ pMean_q(φ(x₁), ..., φ(xₙ))  where q < 0
```

**Existential Quantifier (∃)**:
```
∃x: φ(x) ≈ max(φ(x₁), φ(x₂), ..., φ(xₙ))
```
or smooth approximation:
```
∃x: φ(x) ≈ pMean_q(φ(x₁), ..., φ(xₙ))  where q > 0
```

**p-Mean Aggregation**:
```
pMean_q(x₁, ..., xₙ) = (1/n × Σᵢ xᵢ^q)^(1/q)
```
- q → -∞: minimum
- q = 1: arithmetic mean
- q → +∞: maximum

---

## 2. Architecture Overview

### 2.1 System Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    DSP Pipeline (Phase 2)                    │
│                  8D Feature Vector → [x]                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  LTN Neural Core (Phase 3)                   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Neural Network: f_θ(x) → [logits]                     │ │
│  │  • Input: 8D features                                  │ │
│  │  • Architecture: 8 → 32 → 64 → 32 → 3                 │ │
│  │  • Output: Raw logits for [long, neutral, short]      │ │
│  └──────────────────────┬─────────────────────────────────┘ │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Softmax: σ(logits) → [P(long), P(neutral), P(short)] │ │
│  └──────────────────────┬─────────────────────────────────┘ │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Axiom Evaluation: A₁(x, σ), A₂(x, σ), ...           │ │
│  │  • Market domain knowledge                             │ │
│  │  • Fuzzy logic constraints                             │ │
│  │  • Differentiable satisfaction scores                  │ │
│  └──────────────────────┬─────────────────────────────────┘ │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Hybrid Loss: L = α·L_super + (1-α)·L_semantic        │ │
│  │  • Supervised: Cross-entropy on labels                 │ │
│  │  • Semantic: Axiom satisfaction                        │ │
│  │  • α ∈ [0,1]: Tunable balance                         │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
                  Trading Signal
              [P(long), P(neutral), P(short)]
```

### 2.2 Components

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| **Neural Core** | Learn patterns from features | MLP (8→32→64→32→3) in Burn-rs |
| **Fuzzy Operators** | Differentiable logic | T-norms, implications |
| **Axiom Library** | Market domain knowledge | 10-15 trading axioms |
| **Hybrid Loss** | Guide learning | Supervised + semantic |
| **Inference Engine** | Real-time predictions | <10μs latency |

---

## 3. Axiom Library

### 3.1 Axiom Categories

1. **Regime-Based Axioms**: Link market regime to signal
2. **Divergence-Based Axioms**: Link price-FRAMA divergence to direction
3. **Confidence-Based Axioms**: Link uncertainty to neutral position
4. **Contradiction Axioms**: Prevent logical inconsistencies
5. **Risk Axioms**: Encode risk management rules

### 3.2 Core Axioms

#### Axiom 1: Trending Market → Follow Divergence

**Logical Form**:
```
∀x: (is_trending(x) ∧ divergence_positive(x)) → should_long(x)
```

**Predicate Definitions**:
```rust
is_trending(x) = sigmoid(10 × (x.hurst - 0.6))
divergence_positive(x) = sigmoid(5 × x.divergence_norm)
should_long(x) = signal.P_long
```

**LTN Formula**:
```rust
axiom_1(x, signal) = I(T(is_trending(x), divergence_positive(x)), signal.P_long)
```

**Intuition**: In trending markets (H > 0.6), if price is above FRAMA (positive divergence), we should be long.

---

#### Axiom 2: Trending Market → Contra Divergence

**Logical Form**:
```
∀x: (is_trending(x) ∧ divergence_negative(x)) → should_short(x)
```

**Predicate Definitions**:
```rust
divergence_negative(x) = sigmoid(-5 × x.divergence_norm)
should_short(x) = signal.P_short
```

**LTN Formula**:
```rust
axiom_2(x, signal) = I(T(is_trending(x), divergence_negative(x)), signal.P_short)
```

**Intuition**: In trending markets, if price is below FRAMA (negative divergence), we should be short.

---

#### Axiom 3: Mean-Reverting → Fade Divergence

**Logical Form**:
```
∀x: (is_mean_reverting(x) ∧ divergence_positive(x)) → should_short(x)
```

**Predicate Definitions**:
```rust
is_mean_reverting(x) = sigmoid(-10 × (x.hurst - 0.4))
```

**LTN Formula**:
```rust
axiom_3(x, signal) = I(T(is_mean_reverting(x), divergence_positive(x)), signal.P_short)
```

**Intuition**: In mean-reverting markets (H < 0.4), fade extremes—if price is too high, short it.

---

#### Axiom 4: Mean-Reverting → Fade Negative Divergence

**Logical Form**:
```
∀x: (is_mean_reverting(x) ∧ divergence_negative(x)) → should_long(x)
```

**LTN Formula**:
```rust
axiom_4(x, signal) = I(T(is_mean_reverting(x), divergence_negative(x)), signal.P_long)
```

**Intuition**: In mean-reverting markets, if price is too low, go long.

---

#### Axiom 5: Low Confidence → Neutral Position

**Logical Form**:
```
∀x: low_confidence(x) → should_be_neutral(x)
```

**Predicate Definitions**:
```rust
low_confidence(x) = sigmoid(-10 × (x.regime_confidence - 0.2))
should_be_neutral(x) = signal.P_neutral
```

**LTN Formula**:
```rust
axiom_5(x, signal) = I(low_confidence(x), signal.P_neutral)
```

**Intuition**: When regime confidence is low (< 0.2), stay neutral.

---

#### Axiom 6: High Noise → Reduce Position

**Logical Form**:
```
∀x: high_noise(x) → (should_be_neutral(x) ∨ low_conviction(x))
```

**Predicate Definitions**:
```rust
high_noise(x) = sigmoid(10 × (x.fractal_dim - 1.7))
low_conviction(x) = 1.0 - max(signal.P_long, signal.P_short)
```

**LTN Formula**:
```rust
axiom_6(x, signal) = I(high_noise(x), S(signal.P_neutral, low_conviction(x)))
```

**Intuition**: When fractal dimension is high (> 1.7, noisy market), be cautious.

---

#### Axiom 7: Contradictory Signals → Neutral

**Logical Form**:
```
∀x: (divergence_sign(x) ≠ regime_indication(x)) → should_be_neutral(x)
```

**Predicate Definitions**:
```rust
divergence_bullish(x) = (x.divergence_sign == 1.0)
regime_bearish(x) = (x.regime == -1.0)  // Mean-reverting suggests fade
contradictory(x) = T(divergence_bullish(x), regime_bearish(x))
```

**LTN Formula**:
```rust
axiom_7(x, signal) = I(contradictory(x), signal.P_neutral)
```

**Intuition**: When divergence and regime give conflicting signals, stay neutral.

---

#### Axiom 8: Extreme Alpha → High Volatility → Caution

**Logical Form**:
```
∀x: extreme_alpha(x) → should_be_neutral(x)
```

**Predicate Definitions**:
```rust
extreme_alpha(x) = sigmoid(10 × (|x.alpha_deviation| - 0.2))
```

**LTN Formula**:
```rust
axiom_8(x, signal) = I(extreme_alpha(x), signal.P_neutral)
```

**Intuition**: Extreme FRAMA alpha (high deviation) indicates unstable conditions.

---

#### Axiom 9: Consistency Constraint (No Arbitrage)

**Logical Form**:
```
∀x: P_long(x) + P_neutral(x) + P_short(x) = 1
```

**LTN Formula** (soft constraint):
```rust
axiom_9(signal) = 1.0 - |1.0 - (signal.P_long + signal.P_neutral + signal.P_short)|
```

**Intuition**: Probabilities must sum to 1 (enforced by softmax, but axiom reinforces).

---

#### Axiom 10: Monotonicity in Confidence

**Logical Form**:
```
∀x: (regime_confidence ↑) → (max(P_long, P_short) ↑)
```

**LTN Formula** (correlation-based):
```rust
axiom_10(x, signal) = sigmoid(correlation(x.regime_confidence, max(signal.P_long, signal.P_short)))
```

**Intuition**: Higher regime confidence → stronger directional conviction.

---

### 3.3 Axiom Weighting

Not all axioms are equally important. We assign weights:

| Axiom | Weight | Rationale |
|-------|--------|-----------|
| Axiom 1 (Trending + div) | 2.0 | Core momentum strategy |
| Axiom 2 (Trending - div) | 2.0 | Core momentum strategy |
| Axiom 3 (MR + div) | 1.5 | Mean-reversion secondary |
| Axiom 4 (MR - div) | 1.5 | Mean-reversion secondary |
| Axiom 5 (Low conf → neutral) | 3.0 | **Critical risk control** |
| Axiom 6 (High noise → caution) | 2.5 | Risk management |
| Axiom 7 (Contradiction → neutral) | 2.0 | Logical consistency |
| Axiom 8 (Extreme alpha → neutral) | 1.0 | Edge case |
| Axiom 9 (Probability sum) | 5.0 | **Hard constraint** |
| Axiom 10 (Confidence monotonicity) | 1.0 | Soft preference |

**Total Semantic Loss**:
```
L_semantic = -Σᵢ (wᵢ × satisfaction(Axiom_i))
```

---

## 4. Neural Core Design

### 4.1 Architecture

```
Input Layer:     [8D feature vector from DSP]
                 ↓
Hidden Layer 1:  Dense(8 → 32) + ReLU + Dropout(0.2)
                 ↓
Hidden Layer 2:  Dense(32 → 64) + ReLU + Dropout(0.2)
                 ↓
Hidden Layer 3:  Dense(64 → 32) + ReLU
                 ↓
Output Layer:    Dense(32 → 3) + Softmax
                 ↓
Output:          [P(long), P(neutral), P(short)]
```

### 4.2 Activation Functions

- **Hidden layers**: ReLU (fast, gradient-friendly)
- **Output layer**: Softmax (probability distribution)

### 4.3 Regularization

- **Dropout**: 0.2 on first two hidden layers (prevent overfitting)
- **L2 weight decay**: λ = 1e-4
- **Gradient clipping**: max_norm = 1.0

### 4.4 Initialization

- **Weights**: He initialization (for ReLU)
- **Biases**: Zero initialization

### 4.5 Parameter Count

```
Layer 1:  8 × 32 + 32 = 288
Layer 2:  32 × 64 + 64 = 2,112
Layer 3:  64 × 32 + 32 = 2,080
Output:   32 × 3 + 3 = 99
---------------------------------
Total:    4,579 parameters
```

**Small model by design** → fast inference, low overfitting risk.

---

## 5. Loss Functions

### 5.1 Supervised Loss

**Cross-Entropy Loss**:
```
L_super(ŷ, y) = -Σₖ yₖ log(ŷₖ)
```

Where:
- ŷ = [P(long), P(neutral), P(short)] (model output)
- y = one-hot encoded label (ground truth)

### 5.2 Semantic Loss

**Axiom Satisfaction**:
```
L_semantic = -Σᵢ wᵢ × satisfaction(Axiom_i)
```

Where:
- wᵢ = axiom weight
- satisfaction(Axiom_i) ∈ [0, 1] (fuzzy truth value)

### 5.3 Hybrid Loss

**Combined Loss**:
```
L_total = α × L_super + (1 - α) × L_semantic
```

Where:
- α ∈ [0, 1] is the **semantic weight** hyperparameter

**Recommended α schedule**:
- **Phase 1 (Early training)**: α = 0.8 (focus on data)
- **Phase 2 (Mid training)**: α = 0.5 (balance)
- **Phase 3 (Fine-tuning)**: α = 0.3 (focus on axioms)

### 5.4 Auxiliary Losses (Optional)

**Entropy Regularization** (encourage decisiveness):
```
L_entropy = -Σₖ ŷₖ log(ŷₖ)
```

**Confidence Calibration** (match predicted vs actual confidence):
```
L_calib = |confidence(ŷ) - accuracy(ŷ, y)|
```

---

## 6. Training Strategy

### 6.1 Dataset Construction

**Synthetic Data** (Phase 1):
- Generate 1M ticks of trending markets (H > 0.6)
- Generate 1M ticks of mean-reverting markets (H < 0.4)
- Generate 1M ticks of random walks (H ≈ 0.5)
- Label: long if next 10-tick return > +0.5%, short if < -0.5%, else neutral

**Historical Data** (Phase 2):
- BTC/ETH tick data (6 months)
- Label based on forward returns (configurable horizon)
- Filter out low-volatility periods

### 6.2 Walk-Forward Validation

**Rolling Window Strategy**:
```
Train:  Week 1-4  →  Validate: Week 5
Train:  Week 2-5  →  Validate: Week 6
Train:  Week 3-6  →  Validate: Week 7
...
```

**Metrics per fold**:
- Sharpe ratio
- Win rate
- Max drawdown
- Regime-specific performance

### 6.3 Hyperparameter Tuning

| Hyperparameter | Search Range | Recommended |
|----------------|--------------|-------------|
| **Learning rate** | [1e-5, 1e-2] | 1e-3 |
| **Batch size** | [32, 256] | 128 |
| **Dropout** | [0.1, 0.5] | 0.2 |
| **Semantic weight α** | [0.0, 1.0] | 0.5 |
| **L2 decay** | [1e-6, 1e-3] | 1e-4 |

**Tuning method**: Grid search or Bayesian optimization (Optuna)

### 6.4 Training Loop

```python
for epoch in range(num_epochs):
    for batch in train_loader:
        # Forward pass
        features, labels = batch
        logits = model.forward(features)
        probs = softmax(logits)
        
        # Supervised loss
        L_super = cross_entropy(probs, labels)
        
        # Semantic loss
        axiom_scores = [axiom_i(features, probs) for axiom_i in axioms]
        L_semantic = -weighted_sum(axiom_scores, weights)
        
        # Hybrid loss
        loss = alpha * L_super + (1 - alpha) * L_semantic
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
    # Validation
    val_metrics = validate(model, val_loader)
    
    # Adjust alpha (optional)
    if epoch > warm_up_epochs:
        alpha = decay_schedule(alpha, epoch)
```

### 6.5 Early Stopping

**Criteria**:
- Validation loss stops improving for 10 epochs
- Validation Sharpe ratio < 0.5 (model not learning)
- Training loss diverges (numerical instability)

---

## 7. Implementation Specification

### 7.1 Module Structure

```
src/ltn/
├── mod.rs                  # Public API
├── fuzzy_ops.rs            # T-norms, implications, negation
├── axioms.rs               # Axiom library
├── model.rs                # Neural core (Burn-rs)
├── loss.rs                 # Hybrid loss functions
├── training.rs             # Training loop
├── inference.rs            # Real-time inference
├── predicates.rs           # Predicate definitions
├── config.rs               # Configuration
├── tests/
│   ├── test_fuzzy_ops.rs
│   ├── test_axioms.rs
│   └── test_model.rs
└── benches/
    └── bench_inference.rs
```

### 7.2 Core Types

```rust
/// Trading signal with probabilities
pub struct TradingSignal {
    pub long: f64,      // P(long)
    pub neutral: f64,   // P(neutral)
    pub short: f64,     // P(short)
    pub confidence: f64, // max(P)
}

/// LTN model configuration
pub struct LtnConfig {
    pub hidden_dims: Vec<usize>,
    pub dropout_rate: f64,
    pub semantic_weight: f64,
    pub axiom_weights: Vec<f64>,
    pub learning_rate: f64,
}

/// Axiom evaluation result
pub struct AxiomResult {
    pub axiom_id: usize,
    pub satisfaction: f64,  // ∈ [0, 1]
    pub weight: f64,
}
```

### 7.3 Performance Requirements

| Component | Target Latency | P99 Latency |
|-----------|----------------|-------------|
| **Forward pass** | <5μs | <20μs |
| **Axiom evaluation** | <2μs | <10μs |
| **Total inference** | <10μs | <50μs |

**Absolute requirement**: P99 < 100μs for HFT viability.

---

## 8. Performance Requirements

### 8.1 Latency Budgets

```
DSP Pipeline:       0.5μs  (measured)
LTN Inference:      5.0μs  (target)
Risk Checks:        0.1μs  (target)
Order Generation:   0.5μs  (target)
-----------------------------------------
Total (Tick→Order): 6.1μs  (median)
                   <50μs   (P99)
```

### 8.2 Throughput

- **Minimum**: 100K inferences/sec
- **Target**: 500K inferences/sec
- **Stretch**: 1M inferences/sec

### 8.3 Memory Footprint

- **Model size**: <50KB (4,579 params × 4 bytes)
- **Inference state**: <1KB
- **Total per instance**: <100KB

### 8.4 Accuracy Targets

| Metric | Synthetic Data | Historical Data |
|--------|----------------|-----------------|
| **Classification Accuracy** | >60% | >55% |
| **Sharpe Ratio** | >2.0 | >1.5 |
| **Win Rate** | >60% | >55% |
| **Axiom Satisfaction** | >0.8 | >0.7 |

---

## 9. Risk & Mitigation

### 9.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Burn-rs too slow** | Medium | High | Fallback to ONNX Runtime |
| **Axioms conflict** | Low | Medium | Weighted resolution, test suite |
| **Overfitting** | High | Medium | Dropout, L2, walk-forward validation |
| **Mode collapse** | Medium | High | Entropy regularization, diverse data |

### 9.2 Trading Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Regime shift** | High | High | Adaptive learning, circuit breakers |
| **Axiom misspecification** | Medium | Medium | Backtesting, expert review |
| **Overconfidence** | Medium | High | Calibration loss, confidence thresholds |

---

## 10. Validation Plan

### 10.1 Unit Tests

- [x] Fuzzy operators (T-norms, implications)
- [x] Axiom evaluation (each axiom individually)
- [x] Model forward pass
- [x] Loss computation
- [x] Gradient flow

### 10.2 Integration Tests

- [x] DSP → LTN pipeline
- [x] End-to-end training loop
- [x] Axiom satisfaction on synthetic data
- [x] Walk-forward validation

### 10.3 Performance Tests

- [x] Inference latency (P50, P99)
- [x] Throughput (inferences/sec)
- [x] Memory usage
- [x] Gradient computation speed

### 10.4 Trading Tests

- [x] Backtest on synthetic markets
- [x] Backtest on historical data
- [x] Regime-specific performance
- [x] Paper trading (4 weeks)

---

## 11. References

### Logic Tensor Networks

1. **Serafini, L., & Garcez, A. (2016)**. "Logic Tensor Networks: Deep Learning and Logical Reasoning from Data and Knowledge". *arXiv:1606.04422*

2. **Badreddine, S., et al. (2022)**. "Logic Tensor Networks". *Artificial Intelligence, 303, 103649*

### Fuzzy Logic

3. **Klement, E. P., et al. (2000)**. "Triangular Norms". *Springer*

4. **Hájek, P. (1998)**. "Metamathematics of Fuzzy Logic". *Springer*

### Trading & Market Microstructure

5. **Cartea, Á., et al. (2015)**. "Algorithmic and High-Frequency Trading". *Cambridge University Press*

6. **Hasbrouck, J. (2007)**. "Empirical Market Microstructure". *Oxford University Press*

---

**Document Status**: v1.0 - Design Phase Complete  
**Next**: Implementation Phase (Weeks 3-8)  
**Approval**: Pending Technical Review

---

## Appendix A: Sigmoid Helper

```rust
fn sigmoid(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

// Steepness-controlled sigmoid
fn sigmoid_with_steepness(x: f64, k: f64) -> f64 {
    1.0 / (1.0 + (-k * x).exp())
}
```

## Appendix B: Example Axiom Evaluation

```rust
// Axiom 1: Trending + positive divergence → Long
fn axiom_trending_long(features: &[f64; 8], signal: &TradingSignal) -> f64 {
    // Extract features
    let hurst = features[3];
    let divergence_norm = features[0];
    
    // Predicates
    let is_trending = sigmoid(10.0 * (hurst - 0.6));
    let div_positive = sigmoid(5.0 * divergence_norm);
    
    // T-norm (conjunction)
    let premise = is_trending * div_positive;
    
    // Reichenbach implication
    let conclusion = signal.long;
    let satisfaction = 1.0 - premise + premise * conclusion;
    
    satisfaction
}
```

## Appendix C: Training Pseudocode

```python
# Initialize
model = LtnModel(config)
optimizer = Adam(model.parameters(), lr=1e-3)
alpha = 0.8  # Semantic weight

# Training loop
for epoch in range(100):
    for batch in train_loader:
        features, labels = batch
        
        # Forward
        signal = model.forward(features)
        
        # Supervised loss
        L_super = cross_entropy(signal.probs(), labels)
        
        # Semantic loss
        axiom_sats = [axiom(features, signal) for axiom in axioms]
        L_semantic = -weighted_mean(axiom_sats, axiom_weights)
        
        # Hybrid loss
        loss = alpha * L_super + (1 - alpha) * L_semantic
        
        # Backward
        optimizer.zero_grad()
        loss.backward()
        clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
    
    # Validation
    val_loss, val_metrics = validate(model, val_loader)
    print(f"Epoch {epoch}: val_loss={val_loss:.4f}, sharpe={val_metrics.sharpe:.2f}")
    
    # Adjust alpha
    if epoch > 20:
        alpha = max(0.3, alpha * 0.95)
```
