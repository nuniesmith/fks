# The JANUS Protocol: Architectural Specification of a Neuromorphic Algorithmic Trading System

**Version**: 2.0 (Architectural Specification)  
**Date**: January 2025  
**Status**: Design Specification & Implementation Roadmap  
**Author**: Jordan Smith

---

## Document Purpose

This document provides a **complete architectural specification** for Project JANUS, a neuromorphic algorithmic trading system. It describes the **intended design**, **theoretical foundations**, and **implementation roadmap** for building a brain-inspired trading intelligence system.

**This is a design document.** Implementation status is tracked separately in the companion document: `JANUS_IMPLEMENTATION_STATUS.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Introduction: The Neuromorphic Paradigm](#2-introduction-the-neuromorphic-paradigm)
3. [System Architecture](#3-system-architecture)
4. [Visual Cortex: Spatiotemporal Pattern Recognition](#4-visual-cortex-spatiotemporal-pattern-recognition)
5. [Prefrontal Cortex: Symbolic Reasoning](#5-prefrontal-cortex-symbolic-reasoning)
6. [Amygdala: Risk Management & Compliance](#6-amygdala-risk-management--compliance)
7. [Hypothalamus: Capital Allocation](#7-hypothalamus-capital-allocation)
8. [Basal Ganglia: Hierarchical Decision Making](#8-basal-ganglia-hierarchical-decision-making)
9. [Cerebellum: Optimal Execution](#9-cerebellum-optimal-execution)
10. [Hippocampus: Memory & Learning](#10-hippocampus-memory--learning)
11. [Thalamus: Attention & Fusion](#11-thalamus-attention--fusion)
12. [Integration & Orchestration](#12-integration--orchestration)
13. [Theoretical Validation](#13-theoretical-validation)
14. [Performance Specifications](#14-performance-specifications)
15. [Security & Compliance](#15-security--compliance)
16. [Deployment Architecture](#16-deployment-architecture)
17. [Future Extensions](#17-future-extensions)
18. [References](#18-references)

---

## 1. Executive Summary

### 1.1 Vision

Project JANUS represents a paradigm shift in algorithmic trading, moving from rigid heuristic pipelines to adaptive neuromorphic intelligence. By mapping distinct market functions to specific brain regions—the Amygdala for risk, the Hippocampus for memory, and the Prefrontal Cortex for symbolic logic—the system achieves both adaptability and reliability in volatile cryptocurrency markets.

### 1.2 Core Innovation

The fundamental innovation is a **bicameral architecture** that mirrors biological circadian rhythms:

- **Forward Service (Wake State)**: High-frequency decision-making with <10ms latency
- **Backward Service (Sleep State)**: Memory consolidation and model refinement

This separation allows integration of computationally intensive tasks (Video Vision Transformers, Logic Tensor Networks) without compromising execution speed.

### 1.3 Key Differentiators

| Feature | Traditional Systems | JANUS |
|---------|-------------------|-------|
| **Architecture** | Linear pipeline | Parallel neuromorphic regions |
| **Learning** | Offline only | Continuous wake/sleep cycles |
| **Market Perception** | 1D time series | 3D spatiotemporal manifolds (GAF/ViViT) |
| **Compliance** | Hard-coded rules | Differentiable logic constraints (LTN) |
| **Execution** | Fixed algorithms | Deep learning allocation (StaticVWAP) |
| **Adaptability** | Regime detection heuristics | Hierarchical RL (M3T) |

### 1.4 Target Use Cases

1. **Proprietary Trading Firms**: HyroTrader, FTMO, MyForexFunds compliance
2. **High-Frequency Market Making**: Crypto spot and derivatives
3. **Institutional Execution**: Large order slicing with minimal impact
4. **Research Platform**: Testing cognitive architectures in finance

---

## 2. Introduction: The Neuromorphic Paradigm

### 2.1 The Problem with Traditional Systems

Prevailing algorithmic trading systems suffer from:

1. **Rigidity**: Linear α → Risk → Execution pipelines break during phase transitions
2. **Lookahead Bias**: Backtests use future information, invalidating results
3. **Execution Slippage**: Fixed VWAP curves fail in volatile crypto markets
4. **Compliance Fragility**: Hard-coded rules can be bypassed by bugs
5. **Catastrophic Forgetting**: Retraining destroys previous knowledge

### 2.2 Why Neuromorphic?

The biological brain solves analogous problems:

| Trading Challenge | Brain Solution | JANUS Implementation |
|------------------|----------------|---------------------|
| Real-time + Learning | Wake/Sleep cycles | Forward/Backward services |
| Pattern Recognition | Visual cortex | GAF → ViViT pipeline |
| Safety Overrides | Amygdala fear response | Circuit breakers, kill switch |
| Logical Constraints | Prefrontal executive control | Logic Tensor Networks |
| Memory Without Forgetting | Hippocampal consolidation | Prioritized Experience Replay |
| Adaptive Positioning | Hypothalamic homeostasis | Kelly Criterion with drawdown constraints |

### 2.3 Theoretical Foundations

JANUS synthesizes research from:

1. **Cognitive Neuroscience**: O'Reilly et al. (2012) - Hierarchical RL in the brain
2. **Computer Vision**: Wang et al. (2015) - Gramian Angular Fields for time series imaging
3. **Deep Learning**: Arnab et al. (2021) - Video Vision Transformers (ViViT)
4. **Symbolic AI**: Badreddine et al. (2022) - Logic Tensor Networks
5. **Quantitative Finance**: Ning et al. (2021) - Deep learning for VWAP execution
6. **Trading Psychology**: Lo et al. (2017) - Adaptive Markets Hypothesis

---

## 3. System Architecture

### 3.1 The Bicameral Design

```
┌─────────────────────────────────────────────────────────────────┐
│                      JANUS SYSTEM                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────┐      ┌─────────────────────────┐   │
│  │   FORWARD SERVICE      │      │   BACKWARD SERVICE      │   │
│  │   (Wake State)         │◄────►│   (Sleep State)         │   │
│  │                        │ SHM  │                         │   │
│  │  - Rust (tokio)        │gRPC  │  - Python (PyTorch)     │   │
│  │  - <10ms latency       │      │  - Heavy ML training    │   │
│  │  - Real-time trading   │      │  - Memory consolidation │   │
│  └────────────────────────┘      │  - Model refinement     │   │
│           │                       └─────────────────────────┘   │
│           │                                  │                  │
│           ▼                                  ▼                  │
│  ┌─────────────────┐                ┌──────────────────┐       │
│  │  Market Data    │                │  QuestDB         │       │
│  │  (WebSocket)    │                │  (Time Series)   │       │
│  └─────────────────┘                └──────────────────┘       │
│           │                                  │                  │
│           ▼                                  ▼                  │
│  ┌─────────────────────────────────────────────────────┐       │
│  │           NEUROMORPHIC BRAIN REGIONS                │       │
│  ├─────────────────────────────────────────────────────┤       │
│  │  Visual Cortex → Thalamus → Cortex → Prefrontal    │       │
│  │       ↓              ↓          ↓         ↓         │       │
│  │  Hippocampus ← Basal Ganglia ← Amygdala            │       │
│  │       ↓              ↓                              │       │
│  │  Hypothalamus → Cerebellum → Execution             │       │
│  └─────────────────────────────────────────────────────┘       │
│                          │                                     │
│                          ▼                                     │
│                  ┌──────────────┐                              │
│                  │   Exchange   │                              │
│                  │  (Bybit API) │                              │
│                  └──────────────┘                              │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Communication Protocols

#### 3.2.1 Forward ↔ Backward

**Method 1: Shared Memory (Ultra-low latency)**
- Apache Arrow IPC format
- Zero-copy tensor transfer
- Used for: GAF images, state embeddings
- Latency: <100μs

**Method 2: gRPC (Structured messages)**
- Protocol Buffers schema (`janus.proto`)
- Used for: Control signals, training requests
- Latency: <5ms

#### 3.2.2 Forward ↔ Exchange

- WebSocket (market data): Bybit, Binance streams
- REST API (execution): Order placement, cancellation
- FIX Protocol (future): For institutional venues

### 3.3 Brain Region Responsibilities

| Region | Input | Processing | Output | Latency |
|--------|-------|------------|--------|---------|
| **Visual Cortex** | OHLCV ticks | GAF encoding, ViViT inference | Pattern embeddings | 5ms |
| **Thalamus** | Multi-source data | Attention weighting, fusion | Unified state | 2ms |
| **Cortex** | Fused state | Strategic policy (Manager) | Sub-goals | 10ms |
| **Hippocampus** | Sub-goals | Tactical policy (Worker) | Action proposals | 8ms |
| **Basal Ganglia** | Action proposals | Actor-Critic RL | Action selection | 5ms |
| **Prefrontal** | Selected action | LTN compliance check | Veto/Approve | 3ms |
| **Amygdala** | Market state | Fear network, threat detection | Circuit breaker signal | 1ms |
| **Hypothalamus** | Account state | Homeostasis, position sizing | Risk allocation | 2ms |
| **Cerebellum** | Approved order | StaticVWAP execution | Order slices | 5ms |

**Total Inference Latency**: ~40ms (Forward path)  
**Total Training Time**: 10-300s (Backward service, async)

---

## 4. Visual Cortex: Spatiotemporal Pattern Recognition

### 4.1 Design Rationale

Traditional technical analysis treats market data as 1D sequences (price[t]). This representation:
- Discards temporal correlation structure
- Cannot leverage powerful computer vision architectures
- Misses geometric invariants (e.g., Head & Shoulders pattern at any price scale)

**Solution**: Transform time series into 2D/3D images using Gramian Angular Fields, then apply Vision Transformers.

### 4.2 Gramian Angular Field (GAF) Transformation

#### 4.2.1 Mathematical Specification

Given a price time series $X = \{x_1, \ldots, x_n\}$:

**Step 1: Learnable Normalization**

$$\tilde{x}_t = \gamma \odot \frac{x_t - \mu}{\sigma} + \beta$$

Where:
- $\mu, \sigma$: Running mean/std of the series
- $\gamma, \beta$: Learnable affine parameters (allows adaptation to volatility regimes)
- Output range: $[-1, 1]$ (suitable for arccos domain)

**Step 2: Polar Encoding**

$$\phi_t = \arccos(\tilde{x}_t), \quad \tilde{x}_t \in [-1, 1]$$

This maps the price magnitude to angular space, preserving order relationships.

**Step 3: Gramian Matrix Construction**

**GASF (Gramian Angular Summation Field):**
$$G_{i,j}^{GASF} = \cos(\phi_i + \phi_j) = \tilde{x}_i \tilde{x}_j - \sqrt{1-\tilde{x}_i^2}\sqrt{1-\tilde{x}_j^2}$$

**GADF (Gramian Angular Difference Field):**
$$G_{i,j}^{GADF} = \sin(\phi_i - \phi_j) = \sqrt{1-\tilde{x}_i^2}\tilde{x}_j - \tilde{x}_i\sqrt{1-\tilde{x}_j^2}$$

**Properties**:
- Diagonal $G_{i,i}$ recovers original time series
- Off-diagonals encode temporal correlations
- GASF emphasizes smoothness, GADF emphasizes changes

#### 4.2.2 DiffGAF: Differentiable Implementation

```python
class DiffGAF(nn.Module):
    def __init__(self, method='GASF'):
        super().__init__()
        self.method = method
        self.gamma = nn.Parameter(torch.ones(1))   # Learnable scale
        self.beta = nn.Parameter(torch.zeros(1))   # Learnable shift
        
    def forward(self, x):
        # x: (batch, sequence_length)
        mu = x.mean(dim=1, keepdim=True)
        sigma = x.std(dim=1, keepdim=True) + 1e-8
        
        # Learnable normalization
        x_norm = self.gamma * (x - mu) / sigma + self.beta
        x_norm = torch.clamp(x_norm, -1 + 1e-6, 1 - 1e-6)
        
        # Polar encoding
        phi = torch.acos(x_norm)  # (batch, seq_len)
        
        # Gramian matrix
        if self.method == 'GASF':
            # cos(φi + φj) = cos(φi)cos(φj) - sin(φi)sin(φj)
            cos_phi = torch.cos(phi)
            sin_phi = torch.sin(phi)
            G = torch.matmul(cos_phi.unsqueeze(2), cos_phi.unsqueeze(1)) - \
                torch.matmul(sin_phi.unsqueeze(2), sin_phi.unsqueeze(1))
        else:  # GADF
            # sin(φi - φj) = sin(φi)cos(φj) - cos(φi)sin(φj)
            cos_phi = torch.cos(phi)
            sin_phi = torch.sin(phi)
            G = torch.matmul(sin_phi.unsqueeze(2), cos_phi.unsqueeze(1)) - \
                torch.matmul(cos_phi.unsqueeze(2), sin_phi.unsqueeze(1))
        
        return G  # (batch, seq_len, seq_len)
```

**Gradient Flow**: 
- Normalization parameters $\gamma, \beta$ learn optimal scaling for different volatility regimes
- End-to-end training with ViViT allows the GAF encoding to optimize for trading objectives

### 4.3 Video Vision Transformer (ViViT)

#### 4.3.1 Architecture Specification

**Input**: Sequence of GAF images forming a "market video"
- Shape: `(batch, T_video, H_img, W_img, C)`
- Example: `(32, 16, 64, 64, 3)` 
  - 32 samples, 16 frames (time windows), 64×64 GAF images, 3 channels (GASF/GADF/Volume)

**Model Variant**: Factorized Encoder (Model 2 from Arnab et al.)

```python
class ViViT(nn.Module):
    def __init__(self, 
                 img_size=64, 
                 patch_size=8, 
                 num_frames=16,
                 dim=512, 
                 depth=8, 
                 heads=8):
        super().__init__()
        
        # Tubelet embedding: (T, H, W) → patches
        self.patch_embed = TubeletEmbedding(
            img_size=img_size,
            patch_size=patch_size,
            tubelet_size=2,  # Temporal patches
            in_channels=3,
            embed_dim=dim
        )
        
        # Factorized attention: Spatial → Temporal
        self.spatial_blocks = nn.ModuleList([
            TransformerBlock(dim, heads, spatial_only=True)
            for _ in range(depth // 2)
        ])
        
        self.temporal_blocks = nn.ModuleList([
            TransformerBlock(dim, heads, temporal_only=True)
            for _ in range(depth // 2)
        ])
        
        # Trading-specific head
        self.market_head = nn.Sequential(
            nn.LayerNorm(dim),
            nn.Linear(dim, 256),
            nn.GELU(),
            nn.Linear(256, 64)  # Market state embedding
        )
        
    def forward(self, video):
        # video: (B, T, H, W, C)
        x = self.patch_embed(video)  # (B, N_patches, D)
        
        # Spatial attention: Attend within each frame
        for block in self.spatial_blocks:
            x = block(x)
        
        # Temporal attention: Attend across frames
        for block in self.temporal_blocks:
            x = block(x)
        
        # Global pool + market embedding
        x = x.mean(dim=1)  # (B, D)
        embedding = self.market_head(x)  # (B, 64)
        
        return embedding
```

#### 4.3.2 Training Objective

The ViViT is trained end-to-end with the trading policy:

$$\mathcal{L}_{ViViT} = \mathcal{L}_{policy} + \lambda_{reg} \mathcal{L}_{reconstruction}$$

Where:
- $\mathcal{L}_{policy}$: RL reward (Sharpe ratio, PnL)
- $\mathcal{L}_{reconstruction}$: Auxiliary task to predict next GAF frame (prevents overfitting)
- $\lambda_{reg} = 0.1$

#### 4.3.3 Inference Pipeline

```
Market Ticks → Buffer (128 ticks)
              ↓
        DiffGAF encoder
              ↓
     GAF Image (64×64)
              ↓
   Stack 16 frames (sliding window)
              ↓
        ViViT forward pass
              ↓
    Market Embedding (64-dim) → Thalamus
```

**Latency Budget**:
- GAF encoding: ~2ms (GPU kernel)
- ViViT inference: ~3ms (ONNX Runtime, FP16)
- **Total**: ~5ms

### 4.4 Perceptual Advantages

| Pattern | 1D Representation | GAF/ViViT Representation |
|---------|------------------|-------------------------|
| **Head & Shoulders** | Requires template matching at every scale | Invariant geometric shape in GAF space |
| **Volume Spike** | Separate channel, no correlation | Encoded as intensity change in image |
| **Volatility Expansion** | Requires manual indicator (ATR) | Visible as texture change in GADF |
| **Support/Resistance** | Horizontal line detection | Horizontal edge detection (CNN filter) |
| **Trend Acceleration** | Second derivative calculation | Visible as curvature in temporal axis |

---

## 5. Prefrontal Cortex: Symbolic Reasoning

### 5.1 The Compliance Problem

Neural networks can learn to trade profitably but often violate constraints:
- Trade during news blackouts
- Exceed position limits
- Ignore stop-loss rules

Traditional solutions:
- **Hard-coded if-then checks**: Brittle, can be bypassed by bugs
- **Reward shaping**: Adds penalty terms, but NN may still violate constraints if penalty is too small

**JANUS Solution**: Logic Tensor Networks (LTN) - differentiable logic that enforces constraints during training.

### 5.2 Logic Tensor Network (LTN) Theory

#### 5.2.1 Grounding Function

LTNs define a grounding function $\mathcal{G}$ that maps logical concepts to neural representations:

**Constants**: Objects (e.g., specific ticker symbols)
$$\mathcal{G}(\text{BTCUSD}) = \mathbf{v} \in \mathbb{R}^d$$

**Variables**: Placeholders for objects
$$\mathcal{G}(x) = \text{SampleFrom}(\mathcal{D})$$

**Predicates**: Neural networks that output truth values in $[0,1]$
$$\mathcal{G}(\text{IsVolatile})(x) = \sigma(\text{MLP}(\mathbf{v}_x)) \in [0, 1]$$

**Functions**: Neural networks that map objects to objects
$$\mathcal{G}(\text{Position})(x) = \text{NN}(\mathbf{v}_x) \in \mathbb{R}$$

#### 5.2.2 Fuzzy Logic Operators

LTNs use fuzzy logic to make logical formulas differentiable:

**Łukasiewicz t-norms** (for inference):
- **AND**: $\min(a, b)$
- **OR**: $\max(a, b)$
- **NOT**: $1 - a$
- **IMPLIES**: $\min(1, 1 - a + b)$

**Product t-norms** (for training):
- **AND**: $a \cdot b$
- **OR**: $a + b - a \cdot b$
- **NOT**: $1 - a$
- **IMPLIES**: $1 - a + a \cdot b$

**Why both?**
- Łukasiewicz is more interpretable (sharp boundaries)
- Product provides smoother gradients for backpropagation

#### 5.2.3 Satisfiability Loss

Given a knowledge base of logical formulas $\mathcal{KB}$:

$$\text{Sat}(\mathcal{KB}) = \frac{1}{|\mathcal{KB}|} \sum_{\phi \in \mathcal{KB}} \mathbb{E}_{x \sim \mathcal{D}} [\mathcal{G}(\phi)(x)]$$

**Training objective**:
$$\mathcal{L}_{LTN} = 1 - \text{Sat}(\mathcal{KB})$$

The network learns to maximize satisfiability, thereby adhering to logical constraints.

### 5.3 Trading Rules as Logic

#### 5.3.1 Example Knowledge Base

```python
# Predicate definitions
IsVolatile(x) := σ(MLP_vol(x))
IsTrending(x) := σ(MLP_trend(x))
IsOverbought(x) := σ(MLP_ob(x))
IsNewsEvent(t) := LookupCalendar(t)
BelowMaxPosition(x, pos) := pos < MaxPositionSize
LongSignal(x) := σ(MLP_signal(x))

# Knowledge base (constraints)
KB = [
    # Rule 1: Only go long if trending and not overbought
    ∀x ( LongSignal(x) → (IsTrending(x) ∧ ¬IsOverbought(x)) ),
    
    # Rule 2: Never trade during news events
    ∀x,t ( Trade(x,t) → ¬IsNewsEvent(t) ),
    
    # Rule 3: Position size must respect limits
    ∀x,pos ( LongSignal(x) → BelowMaxPosition(x, pos) ),
    
    # Rule 4: Must have stop loss
    ∀x ( Trade(x) → HasStopLoss(x) ),
    
    # Rule 5: Daily loss limit
    ∀t ( DailyLoss(t) < MaxDailyLoss )
]
```

#### 5.3.2 Implementation Architecture

```python
class TradingLTN(nn.Module):
    def __init__(self):
        super().__init__()
        
        # Predicate networks
        self.is_volatile = PredicateNN(input_dim=64, hidden=128)
        self.is_trending = PredicateNN(input_dim=64, hidden=128)
        self.is_overbought = PredicateNN(input_dim=64, hidden=128)
        self.long_signal = PredicateNN(input_dim=64, hidden=128)
        
        # Fuzzy logic engine
        self.logic = LukasiewiczLogic()  # For inference
        self.logic_train = ProductLogic()  # For training
        
    def forward(self, market_state, training=False):
        # Ground predicates
        volatile = self.is_volatile(market_state)
        trending = self.is_trending(market_state)
        overbought = self.is_overbought(market_state)
        signal = self.long_signal(market_state)
        
        # Select logic engine
        logic = self.logic_train if training else self.logic
        
        # Evaluate constraints
        # Rule 1: Signal → (Trending ∧ ¬Overbought)
        rule1 = logic.implies(
            signal,
            logic.and_op(trending, logic.not_op(overbought))
        )
        
        # Aggregate satisfiability
        sat = (rule1 + rule2 + rule3 + rule4 + rule5) / 5
        
        # During inference, veto signal if satisfaction < threshold
        if not training:
            signal = signal * (sat > 0.9).float()
        
        return signal, sat
```

### 5.4 HyroTrader Compliance Rules

#### 5.4.1 Formalization

```python
# HyroTrader-specific predicates
DailyLoss(t) := SOD_Balance(t) - Current_Equity(t)
MaxDailyLoss(t) := SOD_Balance(t) * 0.05  # 5% rule
TotalLoss(t) := Initial_Balance - Current_Equity(t)
MaxTotalLoss := Initial_Balance * 0.10  # 10% rule
HasStopLoss(order) := order.stop_loss is not None
StopLossPlacedWithin5Min(order) := (now() - order.time) < 300s

# Knowledge base
HyroTrader_KB = [
    # Hard constraints (must always be true)
    ∀t ( DailyLoss(t) < MaxDailyLoss(t) ),
    ∀t ( TotalLoss(t) < MaxTotalLoss ),
    ∀order ( HasStopLoss(order) ),
    ∀order ( StopLossPlacedWithin5Min(order) ),
    
    # Soft constraints (should be true, but can be relaxed)
    ∀x ( Trade(x) → ¬IsWeekend() ),  # Avoid weekend gaps
]
```

#### 5.4.2 Conscience Module

The "conscience" is the enforcement layer:

```rust
pub struct Conscience {
    ltn: TradingLTN,
    threshold: f32,  // Minimum satisfiability (default: 0.95)
}

impl Conscience {
    pub fn evaluate(&self, signal: Signal, state: MarketState) -> Decision {
        let (signal_strength, satisfiability) = self.ltn.forward(state, false);
        
        if satisfiability < self.threshold {
            Decision::Veto {
                reason: format!("LTN satisfaction {:.2} < {:.2}", 
                               satisfiability, self.threshold),
                violated_rules: self.ltn.diagnose_violations(),
            }
        } else {
            Decision::Approve(signal_strength)
        }
    }
}
```

**Key Advantage**: Unlike hard-coded checks, the LTN can interpolate between rules. If a signal is 95% compliant but slightly violates a soft constraint, the satisfiability score reflects this nuance.

---

## 6. Amygdala: Risk Management & Compliance

### 6.1 Biological Inspiration

The amygdala processes fear and threat detection, capable of overriding rational decision-making during imminent danger. In trading:
- Rational system: "This is a good setup, enter long"
- Fear system: "Liquidity is evaporating, DO NOT TRADE"

**Design principle**: The Amygdala has veto power over all signals.

### 6.2 Threat Detection

#### 6.2.1 Volume-Synchronized Probability of Informed Trading (VPIN)

VPIN detects toxic flow and predicts flash crashes.

**Algorithm**:
1. **Volume Buckets**: Partition trades into fixed-volume buckets (e.g., 10 BTC per bucket)
2. **Buy/Sell Imbalance**: For each bucket $i$, compute:
   $$|V_i^{buy} - V_i^{sell}| / V_i^{total}$$
3. **VPIN**: Rolling average over $n$ buckets:
   $$\text{VPIN}_t = \frac{1}{n} \sum_{i=t-n+1}^{t} \frac{|V_i^{buy} - V_i^{sell}|}{V_i^{total}}$$

**Interpretation**:
- VPIN > 0.8: High informed trading, likely adverse selection
- VPIN > 0.9: Flash crash risk (historical threshold from Easley et al.)

**Action**:
```rust
if vpin > 0.85 {
    amygdala.trigger_circuit_breaker(CircuitBreakerType::LiquidityEvaporation);
}
```

#### 6.2.2 Fear Network

A neural network trained to predict regime changes:

**Input Features**:
- Realized volatility (5min, 1h, 4h windows)
- Bid-ask spread (normalized)
- Order book imbalance at levels 1-5
- VPIN
- Funding rate (for perpetuals)
- Open interest change rate

**Output**:
- Fear score ∈ [0, 1]
- Regime classification: {Normal, Elevated, Panic}

**Training Data**:
- Labeled historical crashes: May 2021, Nov 2021, Luna collapse, FTX collapse
- Features extracted pre-crash (1h, 6h, 24h before)

**Architecture**:
```python
class FearNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(input_size=16, hidden_size=64, num_layers=2)
        self.attention = nn.MultiheadAttention(embed_dim=64, num_heads=4)
        self.classifier = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 3)  # Normal/Elevated/Panic
        )
        
    def forward(self, features):
        # features: (seq_len, batch, 16)
        lstm_out, _ = self.lstm(features)
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        fear_logits = self.classifier(attn_out[-1])  # Last timestep
        return F.softmax(fear_logits, dim=-1)
```

### 6.3 Circuit Breakers

#### 6.3.1 Hierarchy of Responses

| Threat Level | Response | Description |
|--------------|----------|-------------|
| **Level 1: Caution** | Reduce position size by 50% | VPIN ∈ [0.7, 0.8] or Fear = Elevated |
| **Level 2: Warning** | Freeze new positions | VPIN ∈ [0.8, 0.9] or Spread > 3σ |
| **Level 3: Danger** | Close all positions (market orders) | VPIN > 0.9 or Fear = Panic |
| **Level 4: Kill Switch** | Close positions + disconnect API | Exchange connectivity < 3s heartbeat |

#### 6.3.2 Kill Switch Implementation

```rust
pub struct KillSwitch {
    state: Arc<RwLock<KillSwitchState>>,
    exchange_client: Arc<ExchangeClient>,
}

impl KillSwitch {
    pub async fn activate(&self, reason: &str) {
        // Log critical event
        error!("🚨 KILL SWITCH ACTIVATED: {}", reason);
        
        // Update state (prevents new orders)
        {
            let mut state = self.state.write().await;
            state.active = true;
            state.reason = reason.to_string();
            state.timestamp = Utc::now();
        }
        
        // Cancel all open orders
        let orders = self.exchange_client.get_open_orders().await?;
        for order in orders {
            self.exchange_client.cancel_order(order.id).await?;
        }
        
        // Close all positions (market orders)
        let positions = self.exchange_client.get_positions().await?;
        for position in positions {
            let close_order = Order {
                symbol: position.symbol,
                side: opposite_side(position.side),
                qty: position.qty,
                order_type: OrderType::Market,
            };
            self.exchange_client.submit_order(close_order).await?;
        }
        
        // Disconnect WebSocket
        self.exchange_client.disconnect().await?;
        
        // Send alert
        self.send_alert(reason).await?;
    }
}
```

### 6.4 HyroTrader Prop Firm Compliance

#### 6.4.1 Daily Drawdown Monitoring

**Specification**:
- Limit: 5% of account balance at 00:00 UTC
- Calculation: `Daily_Loss = Balance_00:00 - Current_Equity`
- Breach consequence: Immediate account failure

**Implementation**:

```rust
pub struct PropFirmValidator {
    rules: HyroTraderRules,
    sod_snapshot: Snapshot,  // Start-of-day
    midnight_utc_reset: bool,
}

impl PropFirmValidator {
    pub async fn check_daily_drawdown(&self, current_equity: f64) -> Result<()> {
        let daily_loss = self.sod_snapshot.balance - current_equity;
        let max_daily_loss = self.sod_snapshot.balance * (self.rules.daily_loss_limit_pct / 100.0);
        
        let buffer = max_daily_loss * 0.90;  // Stop at 90% of limit for safety
        
        if daily_loss >= buffer {
            warn!("⚠️ Approaching daily loss limit: {:.2}% of {:.2}%",
                  (daily_loss / self.sod_snapshot.balance) * 100.0,
                  self.rules.daily_loss_limit_pct);
            
            // Trigger defensive mode
            self.amygdala.set_defensive_mode(true).await?;
        }
        
        if daily_loss >= max_daily_loss {
            bail!("🚨 HARD BREACH: Daily drawdown {:.2} exceeds limit {:.2}",
                  daily_loss, max_daily_loss);
        }
        
        Ok(())
    }
    
    pub async fn midnight_reset(&mut self) {
        // Snapshot balance at 00:00 UTC
        self.sod_snapshot = Snapshot {
            balance: self.get_current_balance().await,
            equity: self.get_current_equity().await,
            timestamp: Utc::now(),
        };
        
        info!("📅 Daily reset: New baseline = ${:.2}", self.sod_snapshot.balance);
    }
}
```

**Cron Job**:
```bash
# In production deployment
0 0 * * * curl -X POST http://localhost:8080/compliance/midnight-reset
```

#### 6.4.2 5-Minute Stop Loss Timer

**Specification**:
- Every trade MUST have a stop loss placed within 5 minutes
- Soft Breach: Close the trade, keep account active
- Implementation: Async timer per position

```rust
pub struct StopLossEnforcer {
    open_positions: Arc<RwLock<HashMap<OrderId, Position>>>,
    timers: Arc<RwLock<HashMap<OrderId, JoinHandle<()>>>>,
}

impl StopLossEnforcer {
    pub async fn on_trade_execution(&self, order_id: OrderId, position: Position) {
        let positions = self.open_positions.clone();
        let timers = self.timers.clone();
        let exchange_client = self.exchange_client.clone();
        
        // Store position
        {
            let mut pos = positions.write().await;
            pos.insert(order_id, position.clone());
        }
        
        // Start 5-minute timer
        let timer_handle = tokio::spawn(async move {
            tokio::time::sleep(Duration::from_secs(300)).await;  // 5 minutes
            
            // Check if stop loss exists
            let pos = positions.read().await;
            if let Some(position) = pos.get(&order_id) {
                if position.stop_loss.is_none() {
                    error!("🚨 SOFT BREACH: No stop loss after 5 minutes for {:?}", order_id);
                    
                    // Force close the position
                    let close_order = Order {
                        symbol: position.symbol.clone(),
                        side: opposite_side(position.side),
                        qty: position.qty,
                        order_type: OrderType::Market,
                    };
                    
                    exchange_client.submit_order(close_order).await.unwrap();
                    
                    // Remove from tracking
                    drop(pos);
                    let mut pos_mut = positions.write().await;
                    pos_mut.remove(&order_id);
                }
            }
        });
        
        // Store timer handle
        {
            let mut t = timers.write().await;
            t.insert(order_id, timer_handle);
        }
    }
    
    pub async fn on_stop_loss_placed(&self, order_id: OrderId) {
        // Cancel the timer
        let mut timers = self.timers.write().await;
        if let Some(handle) = timers.remove(&order_id) {
            handle.abort();
            info!("✅ Stop loss placed for {:?} - timer cancelled", order_id);
        }
    }
}
```

#### 6.4.3 Maximum Trailing Drawdown

**Specification**:
- Trails the highest account balance (High Water Mark)
- Typically 10% from HWM
- Once account grows 10% above initial, the drawdown floor locks at initial balance

```rust
pub struct TrailingDrawdownMonitor {
    initial_balance: f64,
    high_water_mark: f64,
    max_drawdown_pct: f64,
    locked: bool,
}

impl TrailingDrawdownMonitor {
    pub fn update(&mut self, current_equity: f64) -> Result<()> {
        // Update HWM if new high
        if current_equity > self.high_water_mark {
            self.high_water_mark = current_equity;
        }
        
        // Check if we should lock the drawdown floor
        if !self.locked && self.high_water_mark >= self.initial_balance * 1.10 {
            self.locked = true;
            info!("🔒 Drawdown floor LOCKED at initial balance ${:.2}", self.initial_balance);
        }
        
        // Calculate drawdown level
        let drawdown_level = if self.locked {
            self.initial_balance  // Floor locked
        } else {
            self.high_water_mark * (1.0 - self.max_drawdown_pct / 100.0)
        };
        
        if current_equity <= drawdown_level {
            bail!("🚨 HARD BREACH: Equity ${:.2} below drawdown level ${:.2}",
                  current_equity, drawdown_level);
        }
        
        Ok(())
    }
}
```

---

## 7. Hypothalamus: Capital Allocation

### 7.1 Homeostasis Principle

The hypothalamus maintains internal equilibrium despite external volatility. In trading:
- **Goal**: Maintain stable risk exposure regardless of market conditions
- **Mechanism**: Dynamic position sizing based on account state

### 7.2 Kelly Criterion with Drawdown Constraints

#### 7.2.1 Classical Kelly

$$f^* = \frac{p(b+1) - 1}{b}$$

Where:
- $f^*$: Fraction of bankroll to risk
- $p$: Probability of winning
- $b$: Odds received (reward/risk ratio)

**Problem**: Kelly optimizes for long-term growth, not short-term survival. A string of losses can breach prop firm limits.

#### 7.2.2 Constrained Kelly for Prop Firms

**Modification 1: Fractional Kelly**
$$f_{trade} = \frac{1}{4} \cdot f^*$$

Reduces variance at the cost of growth rate (optimal for risk-averse contexts).

**Modification 2: Drawdown-Aware Bankroll**

Instead of using total account balance as "bankroll", use distance to drawdown limit:

$$B_{effective} = \text{Current Equity} - \text{Drawdown Floor}$$

Example:
- Account: $10,000
- Daily drawdown limit: 5% = $500
- Current equity: $10,000
- Drawdown floor: $9,500
- **Effective bankroll**: $10,000 - $9,500 = $500

This ensures that even max Kelly bet cannot breach the limit in one trade.

#### 7.2.3 Implementation

```rust
pub struct KellyCriterion {
    fraction: f64,  // e.g., 0.25 for quarter-Kelly
}

impl KellyCriterion {
    pub fn calculate_position_size(
        &self,
        win_prob: f64,
        reward_risk_ratio: f64,
        effective_bankroll: f64,
        max_position_usd: f64,
    ) -> f64 {
        // Classical Kelly
        let b = reward_risk_ratio;
        let p = win_prob;
        let kelly = (p * (b + 1.0) - 1.0) / b;
        
        // Apply fraction
        let fractional_kelly = self.fraction * kelly;
        
        // Convert to USD risk
        let kelly_risk = fractional_kelly * effective_bankroll;
        
        // Cap at maximum position size
        let final_risk = kelly_risk.min(max_position_usd);
        
        // Floor at minimum (avoid dust trades)
        final_risk.max(10.0)
    }
}
```

### 7.3 Dynamic Risk Appetite

The "Drive" system modulates risk-taking based on recent performance:

```rust
pub struct DriveSystem {
    hunger: f64,     // Desire to trade (0 = satisfied, 1 = starving)
    satiety: f64,    // Risk capacity (0 = full, 1 = can take more risk)
}

impl DriveSystem {
    pub fn update(&mut self, recent_pnl: f64, time_since_last_trade: Duration) {
        // Hunger increases with time (max 1.0)
        self.hunger = (time_since_last_trade.as_secs() as f64 / 3600.0).min(1.0);
        
        // Satiety decreases with losses, increases with wins
        if recent_pnl < 0.0 {
            self.satiety *= 0.8;  // Loss reduces risk appetite
        } else {
            self.satiety = (self.satiety + 0.1).min(1.0);
        }
    }
    
    pub fn get_risk_multiplier(&self) -> f64 {
        // High hunger + high satiety = aggressive
        // Low hunger + low satiety = conservative
        (self.hunger * self.satiety).max(0.1).min(1.0)
    }
}
```

**Effect on position sizing**:
```rust
let base_size = kelly.calculate_position_size(...);
let adjusted_size = base_size * drive.get_risk_multiplier();
```

---

## 8. Basal Ganglia: Hierarchical Decision Making

### 8.1 Actor-Critic Architecture

The basal ganglia implements reinforcement learning via the Actor-Critic pattern:

**Actor**: Policy network that selects actions
$$\pi_\theta(a|s) = P(\text{action } a | \text{state } s)$$

**Critic**: Value network that evaluates states
$$V_\phi(s) = \mathbb{E}[R_t | s_t = s]$$

**Training**: Advantage Actor-Critic (A2C)
$$\nabla_\theta J = \mathbb{E}[A(s,a) \nabla_\theta \log \pi_\theta(a|s)]$$
$$A(s,a) = Q(s,a) - V(s) = r + \gamma V(s') - V(s)$$

### 8.2 Dual Pathway Gating

Inspired by biological basal ganglia:

**Direct Pathway (Go)**:
- Promotes action selection
- Driven by expected reward
- Implements: "Execute this trade"

**Indirect Pathway (No-Go)**:
- Inhibits action selection
- Driven by risk/uncertainty
- Implements: "Do NOT trade"

**Gating Mechanism**:
```python
class BasalGanglia(nn.Module):
    def __init__(self):
        super().__init__()
        self.direct_pathway = DirectPathway()
        self.indirect_pathway = IndirectPathway()
        
    def forward(self, state, proposed_action):
        # Direct pathway: Excitation
        go_signal = self.direct_pathway(state, proposed_action)
        
        # Indirect pathway: Inhibition
        nogo_signal = self.indirect_pathway(state, proposed_action)
        
        # Gating: Action executes only if Go > NoGo
        gate = torch.sigmoid(go_signal - nogo_signal)
        
        return gate
```

### 8.3 M3T: Macro-Meta-Micro Trader (Hierarchical RL)

#### 8.3.1 Motivation

Trading involves multiple timescales:
- **Strategy** (hours to days): "Buy 100 BTC over the next 4 hours"
- **Tactics** (minutes): "Buy 5 BTC in the next 15 minutes given current liquidity"
- **Execution** (seconds): "Place limit order at $43,521.50"

Learning a single policy for all scales is intractable (state space explosion).

**Solution**: Hierarchical Reinforcement Learning (HRL) with 3 levels.

#### 8.3.2 Architecture

```
┌────────────────────────────────────────────────────┐
│                 MACRO TRADER                        │
│  Timeframe: 4h-1D                                   │
│  Input: Market regime, volatility, volume profile   │
│  Output: Parent order (e.g., "Buy 100 BTC in 4h")  │
│  Policy: Strategic allocation                       │
└────────────────────────────────────────────────────┘
                       ↓ Sub-goal
┌────────────────────────────────────────────────────┐
│                  META TRADER                        │
│  Timeframe: 15min-1h                                │
│  Input: Parent order, current liquidity, spread     │
│  Output: Sub-goals (e.g., "Buy 5 BTC in 15min")    │
│  Policy: Tactical decomposition                     │
└────────────────────────────────────────────────────┘
                       ↓ Sub-goal
┌────────────────────────────────────────────────────┐
│                 MICRO TRADER                        │
│  Timeframe: 1s-1min                                 │
│  Input: Sub-goal, order book (L2 data)              │
│  Output: Limit orders at specific price levels      │
│  Policy: Execution optimization (StaticVWAP)        │
└────────────────────────────────────────────────────┘
```

#### 8.3.3 Reward Structure

Each level has its own reward function:

**Macro Trader**:
$$R_{macro} = \frac{\text{Portfolio PnL}}{\text{Portfolio Volatility}} \quad \text{(Sharpe Ratio)}$$

**Meta Trader**:
$$R_{meta} = -|\text{Executed Quantity} - \text{Target Quantity}| - \lambda \cdot \text{Time Penalty}$$

**Micro Trader**:
$$R_{micro} = -(\text{Execution Price} - \text{VWAP})^2 - \mu \cdot \text{Market Impact}$$

#### 8.3.4 Training Protocol

**Phase 1: Bottom-Up**
1. Train Micro Trader on historical LOB data (supervised learning from optimal execution)
2. Freeze Micro Trader

**Phase 2: Middle-Out**
1. Train Meta Trader using Micro as a black-box executor
2. Reward: Deviation from target quantity + slippage cost
3. Freeze Meta Trader

**Phase 3: Top-Down**
1. Train Macro Trader using Meta as a black-box executor
2. Reward: Portfolio-level Sharpe ratio

**Phase 4: Joint Fine-Tuning**
1. Unfreeze all levels
2. Train end-to-end with mixed replay buffer

#### 8.3.5 Implementation

```python
class M3TAgent:
    def __init__(self):
        self.macro = MacroTrader(obs_dim=128, action_dim=64)
        self.meta = MetaTrader(obs_dim=64, action_dim=32)
        self.micro = MicroTrader(obs_dim=32, action_dim=10)
        
    def step(self, market_state):
        # Macro: Strategic decision
        parent_order = self.macro.policy(market_state)
        
        # Meta: Decompose into sub-goals
        sub_goals = self.meta.decompose(parent_order, market_state)
        
        # Micro: Execute each sub-goal
        orders = []
        for sub_goal in sub_goals:
            lob_snapshot = get_order_book()
            limit_orders = self.micro.execute(sub_goal, lob_snapshot)
            orders.extend(limit_orders)
        
        return orders
```

---

## 9. Cerebellum: Optimal Execution

### 9.1 The Execution Problem

**Scenario**: You want to buy 100 BTC. Options:
1. **Market order**: Instant execution, but slippage and market impact
2. **Limit orders**: Better price, but risk non-execution
3. **VWAP execution**: Spread over time to minimize impact

**Goal**: Minimize slippage while ensuring completion.

### 9.2 Traditional Approach: Almgren-Chriss

Classical mean-variance optimization:

$$\min_{\mathbf{n}} \quad \mathbb{E}[\text{Cost}] + \lambda \cdot \text{Var}[\text{Cost}]$$

Where:
- $\mathbf{n} = (n_1, \ldots, n_T)$: Shares to trade in each period
- Cost includes temporary impact (spread) + permanent impact (price movement)

**Solution**: Closed-form trajectory:
$$n_t = \frac{\sinh(\kappa(T-t))}{\sinh(\kappa T)} \cdot N$$

Where $\kappa$ depends on volatility and risk-aversion parameter $\lambda$.

**Limitations**:
- Assumes linear market impact (unrealistic)
- Requires accurate volatility forecasts (hard in crypto)
- Fixed trajectory (cannot adapt to changing liquidity)

### 9.3 Deep Learning Approach: StaticVWAP

#### 9.3.1 Motivation

Instead of predicting volume curves (noisy), directly optimize the execution objective.

**Objective**: Minimize VWAP slippage
$$\mathcal{L} = (P_{exec} - P_{VWAP})^2$$

**Approach**: Neural network learns to output allocation weights.

#### 9.3.2 Model Architecture

```python
class StaticVWAP(nn.Module):
    def __init__(self, feature_dim=10, num_slices=20):
        super().__init__()
        self.num_slices = num_slices
        
        # Feature encoder
        self.encoder = nn.Sequential(
            nn.Linear(feature_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
        )
        
        # Allocation head
        self.allocation = nn.Sequential(
            nn.Linear(128, num_slices),
            nn.Softmax(dim=-1)  # Ensures weights sum to 1
        )
        
    def forward(self, features):
        # features: (batch, feature_dim)
        # - historical volatility
        # - avg spread
        # - order book depth
        # - time of day
        # - urgency (time remaining)
        
        encoded = self.encoder(features)
        weights = self.allocation(encoded)  # (batch, num_slices)
        
        return weights
```

#### 9.3.3 Feature Engineering

| Feature | Description | Calculation |
|---------|-------------|-------------|
| `hist_vol_5m` | 5-minute realized volatility | $\sqrt{\sum_{i=1}^{n} r_i^2}$ |
| `hist_vol_1h` | 1-hour realized volatility | Same, longer window |
| `avg_spread` | Average bid-ask spread | $(ask - bid) / mid$ |
| `book_imbalance` | Order book pressure | $(bid\_vol - ask\_vol) / total$ |
| `time_of_day` | Cyclical encoding | $\sin(2\pi \cdot hour / 24)$ |
| `urgency` | Remaining time ratio | $t_{remaining} / t_{total}$ |
| `parent_size` | Total order size | Normalized by avg volume |
| `market_impact` | Expected impact | $\sigma \cdot \sqrt{Q / V}$ |

#### 9.3.4 Training Procedure

**Dataset**: Historical tick data from QuestDB
- Sample parent orders of various sizes (10 BTC, 50 BTC, 100 BTC)
- Extract features at order submission time
- Simulate execution using actual market data
- Compute realized VWAP slippage

**Loss Function**:
$$\mathcal{L} = \text{MSE}(P_{exec}, P_{VWAP}) + \lambda_{reg} \cdot \text{Entropy}(weights)$$

The entropy term encourages diversity (prevents all weight on one slice).

**Optimizer**: Adam with learning rate decay
**Training Time**: ~20 seconds per epoch (CPU), ~5 seconds (GPU)

#### 9.3.5 Inference

```python
def execute_parent_order(parent_order, market_data):
    # Extract features
    features = extract_features(market_data, parent_order)
    
    # Get allocation weights
    with torch.no_grad():
        weights = static_vwap_model(features)
    
    # Convert to quantities
    total_qty = parent_order.quantity
    slices = (weights * total_qty).numpy()
    
    # Generate time schedule
    total_time = parent_order.duration  # e.g., 3600 seconds
    time_per_slice = total_time / len(slices)
    
    # Submit slices
    for i, qty in enumerate(slices):
        delay = i * time_per_slice
        schedule_order_submission(delay, qty, parent_order.symbol)
```

#### 9.3.6 Comparison: Almgren-Chriss vs StaticVWAP

| Metric | Almgren-Chriss | StaticVWAP |
|--------|---------------|------------|
| **VWAP Slippage** (bps) | 8.2 ± 3.1 | **5.4 ± 2.0** |
| **Completion Rate** | 94% | **98%** |
| **Training Time** | N/A (analytical) | 20s/epoch |
| **Adaptation** | Manual recalibration | Automatic (retraining) |
| **Market Regime Robustness** | Poor (assumes stationarity) | **Good (learned from diverse regimes)** |

(Hypothetical numbers based on literature; actual performance TBD)

---

## 10. Hippocampus: Memory & Learning

### 10.1 Episodic Memory

The hippocampus stores **episodes**: sequences of (state, action, reward, next_state).

**Replay Buffer**:
```python
class EpisodicBuffer:
    def __init__(self, capacity=100000):
        self.buffer = deque(maxlen=capacity)
        
    def store(self, episode):
        # episode: (s, a, r, s', done)
        self.buffer.append(episode)
        
    def sample(self, batch_size):
        return random.sample(self.buffer, batch_size)
```

### 10.2 Prioritized Experience Replay (PER)

Not all memories are equal. PER prioritizes learning from surprising events.

**Priority Calculation**:
$$p_i = |\delta_i| + \epsilon$$

Where:
- $\delta_i = r + \gamma V(s') - V(s)$: TD error (prediction error)
- $\epsilon = 10^{-6}$: Small constant to ensure all transitions have non-zero probability

**Sampling Probability**:
$$P(i) = \frac{p_i^\alpha}{\sum_k p_k^\alpha}$$

Where $\alpha$ controls prioritization strength (0 = uniform, 1 = full prioritization).

**Importance Sampling Correction**:
To avoid bias, weight gradients by:
$$w_i = \left( \frac{1}{N \cdot P(i)} \right)^\beta$$

Where $\beta$ anneals from 0.4 to 1.0 during training.

**Implementation**:
```python
class PrioritizedReplayBuffer:
    def __init__(self, capacity, alpha=0.6):
        self.capacity = capacity
        self.alpha = alpha
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.position = 0
        
    def add(self, transition, td_error):
        priority = (abs(td_error) + 1e-6) ** self.alpha
        
        if len(self.buffer) < self.capacity:
            self.buffer.append(transition)
        else:
            self.buffer[self.position] = transition
        
        self.priorities[self.position] = priority
        self.position = (self.position + 1) % self.capacity
        
    def sample(self, batch_size, beta=0.4):
        # Normalize priorities
        probs = self.priorities[:len(self.buffer)]
        probs /= probs.sum()
        
        # Sample indices
        indices = np.random.choice(len(self.buffer), batch_size, p=probs)
        
        # Importance sampling weights
        weights = (len(self.buffer) * probs[indices]) ** (-beta)
        weights /= weights.max()  # Normalize
        
        transitions = [self.buffer[i] for i in indices]
        return transitions, weights, indices
    
    def update_priorities(self, indices, td_errors):
        for idx, td_error in zip(indices, td_errors):
            self.priorities[idx] = (abs(td_error) + 1e-6) ** self.alpha
```

### 10.3 Sharp Wave Ripples (SWR)

Biological hippocampus replays memories during sleep at 10-20x speed.

**JANUS Implementation**:
- Backward Service performs rapid replay of stored episodes
- Prioritizes high-loss episodes (learning from mistakes)
- Consolidates patterns into the Cortex (strategic policy)

```python
async def sleep_cycle(hippocampus, cortex, duration_hours=8):
    """Simulated sleep: Replay and consolidation"""
    
    replay_buffer = hippocampus.get_priority_buffer()
    
    for _ in range(1000):  # 1000 replay iterations
        # Sample high-priority episodes
        batch, weights, indices = replay_buffer.sample(batch_size=256, beta=0.8)
        
        # Compute TD errors
        td_errors = cortex.compute_td_errors(batch)
        
        # Update priorities
        replay_buffer.update_priorities(indices, td_errors)
        
        # Train Cortex (strategic policy)
        loss = cortex.train_step(batch, weights)
        
        # Consolidate: Transfer knowledge to long-term schemas
        if _ % 100 == 0:
            cortex.consolidate_schemas()
```

### 10.4 Associative Memory (Qdrant)

Store GAF embeddings in a vector database for regime matching.

**Workflow**:
1. Generate GAF image from recent market data
2. Encode with ViViT → 64-dim embedding
3. Query Qdrant: "Find similar historical regimes"
4. Retrieve outcomes of those regimes
5. Use as context for current decision

**Example**:
```python
# Store memory
def store_regime(embedding, outcome):
    qdrant_client.upsert(
        collection_name="market_regimes",
        points=[{
            "id": uuid4(),
            "vector": embedding.tolist(),
            "payload": {
                "timestamp": datetime.now().isoformat(),
                "pnl": outcome["pnl"],
                "volatility": outcome["volatility"],
                "regime": outcome["regime"],
            }
        }])

    # Query similar regimes
    def query_similar_regimes(current_embedding, top_k=5):
        results = qdrant_client.search(
            collection_name="market_regimes",
            query_vector=current_embedding.tolist(),
            limit=top_k
        )
    
        return [result.payload for result in results]
    ```

    ### 10.5 Temporal Fortress (Zero-Lookahead Backtesting)

    **Problem**: Most backtests leak future information, invalidating results.

    **Solution**: Strict temporal gatekeeper that enforces causality.

    ```rust
    pub struct TemporalFortress {
        current_time: DateTime<Utc>,
        data_store: HashMap<String, TimeSeries>,
    }

    impl TemporalFortress {
        pub fn get_data(&self, symbol: &str, lookback: usize) -> Result<Vec<Candle>> {
            let series = self.data_store.get(symbol)
                .ok_or_else(|| anyhow!("Symbol {} not found", symbol))?;
        
            // CRITICAL: Only return data with timestamp <= current_time
            let valid_data: Vec<Candle> = series.data
                .iter()
                .filter(|candle| candle.timestamp <= self.current_time)
                .take(lookback)
                .cloned()
                .collect();
        
            // ERROR if strategy tries to peek ahead
            if valid_data.len() < lookback {
                bail!("🚨 TEMPORAL VIOLATION: Requested {} candles, only {} available at time {}",
                      lookback, valid_data.len(), self.current_time);
            }
        
            Ok(valid_data)
        }
    
        pub fn advance_time(&mut self, new_time: DateTime<Utc>) {
            assert!(new_time >= self.current_time, "Time cannot go backwards!");
            self.current_time = new_time;
        }
    }
    ```

    This ensures backtest results are reproducible in live trading.

    ---

    ## 11. Thalamus: Attention & Fusion

    ### 11.1 Multimodal Data Fusion

    The thalamus receives data from multiple sources:
    - Visual Cortex: Pattern embeddings (64-dim)
    - Market data: Price, volume, spread (10-dim)
    - Sentiment: News/Twitter sentiment (8-dim)
    - On-chain: Whale movements, exchange flows (12-dim)

    **Goal**: Fuse into a unified state representation.

    ### 11.2 Attention Mechanism

    ```python
    class ThalamicFusion(nn.Module):
        def __init__(self):
            super().__init__()
            self.attention = nn.MultiheadAttention(embed_dim=64, num_heads=8)
        
            # Modality-specific encoders
            self.visual_encoder = nn.Linear(64, 64)
            self.market_encoder = nn.Linear(10, 64)
            self.sentiment_encoder = nn.Linear(8, 64)
            self.onchain_encoder = nn.Linear(12, 64)
        
            # Output projection
            self.fusion = nn.Linear(64, 64)
        
        def forward(self, visual, market, sentiment, onchain):
            # Encode each modality to common dimensionality
            v = self.visual_encoder(visual)
            m = self.market_encoder(market)
            s = self.sentiment_encoder(sentiment)
            o = self.onchain_encoder(onchain)
        
            # Stack as sequence (4 modalities)
            inputs = torch.stack([v, m, s, o], dim=0)  # (4, batch, 64)
        
            # Self-attention: Each modality attends to others
            fused, attn_weights = self.attention(inputs, inputs, inputs)
        
            # Pool and project
            pooled = fused.mean(dim=0)  # (batch, 64)
            output = self.fusion(pooled)
        
            return output, attn_weights
    ```

    **Benefit**: The attention weights reveal which modalities are most relevant for current decision.

    ---

    ## 12. Integration & Orchestration

    ### 12.1 Event Loop (Forward Service)

    ```rust
    #[tokio::main]
    async fn main() -> Result<()> {
        // Initialize brain regions
        let visual_cortex = VisualCortex::new().await?;
        let thalamus = Thalamus::new();
        let amygdala = Amygdala::new();
        let basal_ganglia = BasalGanglia::new();
        let cerebellum = Cerebellum::new();
        let exchange = ExchangeClient::new();
    
        // Market data stream
        let mut market_stream = exchange.subscribe_market_data("BTCUSD").await?;
    
        loop {
            tokio::select! {
                // Market tick received
                Some(tick) = market_stream.next() => {
                    // 1. Visual perception
                    let pattern = visual_cortex.process(tick).await?;
                
                    // 2. Multimodal fusion
                    let state = thalamus.fuse(pattern, tick.market_data).await?;
                
                    // 3. Action selection
                    let action = basal_ganglia.select_action(state).await?;
                
                    // 4. Fear check
                    if amygdala.detect_threat(state).await? {
                        warn!("⚠️ Amygdala veto: Threat detected");
                        continue;
                    }
                
                    // 5. Compliance check
                    if !prefrontal.validate(action).await? {
                        warn!("⚠️ Prefrontal veto: Rule violation");
                        continue;
                    }
                
                    // 6. Execute
                    cerebellum.execute(action).await?;
                
                    // 7. Store episode
                    hippocampus.store_episode(state, action, reward).await?;
                }
            
                // Periodic health check
                _ = tokio::time::sleep(Duration::from_secs(60)) => {
                    check_system_health().await?;
                }
            
                // Graceful shutdown
                _ = shutdown_signal.recv() => {
                    info!("Shutting down...");
                    break;
                }
            }
        }
    
        Ok(())
    }
    ```

    ### 12.2 Backward Service Training Loop

    ```python
    async def backward_service():
        """Memory consolidation and model training"""
    
        while True:
            # Wait for sleep signal (market close or manual trigger)
            await wait_for_sleep_signal()
        
            # 1. Load episodes from Hippocampus
            episodes = hippocampus.load_episodes()
        
            # 2. Prioritized replay
            replay_buffer = PrioritizedReplayBuffer(capacity=100000)
            for ep in episodes:
                td_error = compute_td_error(ep)
                replay_buffer.add(ep, td_error)
        
            # 3. Train ViViT (Visual Cortex)
            for epoch in range(10):
                batch = replay_buffer.sample(batch_size=64)
                loss = train_vivit(batch)
                log_metric("vivit_loss", loss)
        
            # 4. Train LTN (Prefrontal Cortex)
            for epoch in range(5):
                batch = replay_buffer.sample(batch_size=32)
                sat_loss = train_ltn(batch)
                log_metric("ltn_satisfaction", sat_loss)
        
            # 5. Train StaticVWAP (Cerebellum)
            execution_data = load_execution_history()
            train_static_vwap(execution_data)
        
            # 6. Update Actor-Critic (Basal Ganglia)
            for epoch in range(20):
                batch, weights, indices = replay_buffer.sample(256, beta=0.8)
                td_errors = update_actor_critic(batch, weights)
                replay_buffer.update_priorities(indices, td_errors)
        
            # 7. Consolidate to Cortex (strategic policy)
            cortex.consolidate_knowledge(replay_buffer)
        
            # 8. Export models to Forward Service
            export_onnx_models()
        
            # 9. Signal wake-up
            await signal_wake_state()
    ```

    ---

    ## 13. Theoretical Validation

    ### 13.1 Neuromorphic Plausibility

    | Component | Biological Analog | Computational Justification |
    |-----------|------------------|---------------------------|
    | **GAF/ViViT** | Primary visual cortex (V1) processes edges/textures | CNNs replicate hierarchical feature extraction |
    | **LTN** | Prefrontal cortex (PFC) rule enforcement | Differentiable logic ensures constraint satisfaction |
    | **PER** | Hippocampal replay prioritizes novel events | Surprise-driven learning accelerates convergence |
    | **Direct/Indirect Pathways** | Basal ganglia Go/NoGo circuits | Action gating prevents impulsive decisions |
    | **Homeostasis** | Hypothalamus regulates energy balance | Kelly Criterion maintains risk equilibrium |
    | **Fear Response** | Amygdala overrides cortical processing | Circuit breakers prevent catastrophic losses |

    ### 13.2 Trading-Specific Validation

    **Claim**: GAF+ViViT outperforms 1D LSTM for pattern recognition.

    **Expected Results** (based on literature):
    - LSTM Sharpe: 1.2 ± 0.3
    - GAF+ViViT Sharpe: 1.6 ± 0.2
    - Reason: Geometric invariance to price scaling

    **Claim**: StaticVWAP reduces slippage vs. Almgren-Chriss.

    **Expected Results**:
    - Almgren-Chriss: 8.2 bps slippage
    - StaticVWAP: 5.4 bps slippage
    - Reason: Direct objective optimization

    **Claim**: LTN ensures 100% compliance without reward shaping.

    **Expected Results**:
    - Standard RL with penalties: 92% compliance
    - LTN: 99.8% compliance
    - Reason: Hard constraints enforced during training

    ---

    ## 14. Performance Specifications

    ### 14.1 Latency Requirements

    | Component | Target Latency | Maximum Latency |
    |-----------|---------------|-----------------|
    | Market data ingestion | <1ms | 5ms |
    | Visual Cortex (GAF+ViViT) | 3ms | 10ms |
    | Thalamus fusion | 1ms | 5ms |
    | Basal Ganglia decision | 2ms | 10ms |
    | Prefrontal LTN check | 1ms | 5ms |
    | Amygdala threat detection | 0.5ms | 2ms |
    | Cerebellum order construction | 1ms | 5ms |
    | **Total (P50)** | **10ms** | **40ms** |

    ### 14.2 Throughput

    - Market data processing: 10,000 ticks/second
    - Order submissions: 100 orders/second
    - Concurrent symbols: 10 (extensible to 50)

    ### 14.3 Resource Requirements

    **Forward Service**:
    - CPU: 4 cores (Rust async runtime)
    - RAM: 4GB
    - GPU: Optional (ONNX can use CPU inference)

    **Backward Service**:
    - CPU: 8 cores
    - RAM: 16GB
    - GPU: NVIDIA RTX 3090 or better (for ViViT training)

    ---

    ## 15. Security & Compliance

    ### 15.1 API Key Management

    ```bash
    # Environment variables (never commit to Git)
    export BYBIT_API_KEY="your_key_here"
    export BYBIT_API_SECRET="your_secret_here"

    # Or use secrets manager
    aws secretsmanager get-secret-value --secret-id janus/prod/bybit
    ```

    ### 15.2 Network Security

    - TLS 1.3 for all external connections
    - Firewall: Only allow outbound to exchange IPs
    - VPN: Tailscale for secure remote access

    ### 15.3 Audit Logging

    Every trade logged to immutable storage:
    ```rust
    struct TradeLog {
        timestamp: DateTime<Utc>,
        symbol: String,
        side: Side,
        quantity: f64,
        price: f64,
        reason: String,  // Which brain region triggered this
        ltn_satisfaction: f64,
        fear_score: f64,
    }
    ```

    ---

    ## 16. Deployment Architecture

    ### 16.1 Docker Compose

    ```yaml
    

    services:
      janus-forward:
        build: ./docker/Dockerfile.forward
        environment:
          - RUST_LOG=info
          - EXCHANGE_API_KEY=${BYBIT_API_KEY}
        depends_on:
          - questdb
          - qdrant
          - redis
        restart: unless-stopped
    
      janus-backward:
        build: ./docker/Dockerfile.backward
        environment:
          - PYTHONUNBUFFERED=1
        volumes:
          - ./models:/app/models
        depends_on:
          - questdb
          - qdrant
        deploy:
          resources:
            reservations:
              devices:
                - driver: nvidia
                  count: 1
                  capabilities: [gpu]
    
      questdb:
        image: questdb/questdb:latest
        ports:
          - "9000:9000"
          - "8812:8812"
        volumes:
          - questdb-data:/root/.questdb
      
      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - "6333:6333"
        volumes:
          - qdrant-data:/qdrant/storage
      
      prometheus:
        image: prom/prometheus:latest
        volumes:
          - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
        ports:
          - "9090:9090"
      
      grafana:
        image: grafana/grafana:latest
        ports:
          - "3000:3000"
        volumes:
          - grafana-data:/var/lib/grafana

    volumes:
      questdb-data:
      qdrant-data:
      grafana-data:
    ```

    ### 16.2 Kubernetes (Production)

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: janus-forward
    spec:
      replicas: 3  # High availability
      selector:
        matchLabels:
          app: janus-forward
      template:
        metadata:
          labels:
            app: janus-forward
        spec:
          containers:
          - name: forward
            image: janus/forward:latest
            resources:
              requests:
                memory: "4Gi"
                cpu: "2"
              limits:
                memory: "8Gi"
                cpu: "4"
            env:
            - name: EXCHANGE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: janus-secrets
                  key: api-key
    ```

    ---

    ## 17. Future Extensions

    ### 17.1 Multi-Asset Portfolio

    Extend from single-symbol to portfolio optimization:
    - Cortex manages asset allocation
    - Each asset has its own Hippocampus (worker)
    - Shared Amygdala for portfolio-level risk

    ### 17.2 Reinforcement Learning from Human Feedback (RLHF)

    Allow expert traders to rate decisions:
    - LTN knowledge base updated with human preferences
    - Reward model trained on expert judgments

    ### 17.3 Explainable AI

    Generate natural language explanations:
    ```
    "Rejected long signal because:
     - LTN satisfaction: 0.87 < 0.90
     - Violated rule: 'Do not trade during high VPIN'
     - VPIN score: 0.91 (threshold: 0.85)
     - Attention weights: 0.6 on-chain, 0.3 visual, 0.1 sentiment"
    ```

    ### 17.4 Meta-Learning

    Train the system to learn how to learn:
    - Inner loop: Adapt to new market regime
    - Outer loop: Learn optimal adaptation strategy

    ---

    ## 18. References

    ### Core Research

    1. **Wang, Z., & Oates, T. (2015).** "Imaging time-series to improve classification and imputation." *IJCAI*.

    2. **Arnab, A., Dehghani, M., Heigold, G., et al. (2021).** "ViViT: A Video Vision Transformer." *ICCV*.

    3. **Badreddine, S., d'Avila Garcez, A., Serafini, L., & Spranger, M. (2022).** "Logic Tensor Networks." *Artificial Intelligence*.

    4. **Ning, B., Ling, J., & Xu, Y. (2021).** "Deep Learning for VWAP Trading." *Journal of Financial Markets*.

    5. **Easley, D., López de Prado, M., & O'Hara, M. (2012).** "Flow toxicity and liquidity in a high-frequency world." *Review of Financial Studies*.

    6. **O'Reilly, R. C., & Frank, M. J. (2006).** "Making working memory work: A computational model of learning in the prefrontal cortex and basal ganglia." *Neural Computation*.

    ### Prop Trading Compliance

    7. **HyroTrader Rules**: https://hyrotrader.com/challenge-rules
    8. **FTMO Evaluation**: https://ftmo.com/en/trading-objectives/

    ### Algorithmic Trading

    9. **Almgren, R., & Chriss, N. (2001).** "Optimal execution of portfolio transactions." *Journal of Risk*.

    10. **Lo, A. W. (2017).** "Adaptive Markets: Financial Evolution at the Speed of Thought." *Princeton University Press*.

    ---

    ## Appendix A: Glossary

    - **GAF**: Gramian Angular Field
    - **ViViT**: Video Vision Transformer
    - **LTN**: Logic Tensor Network
    - **PER**: Prioritized Experience Replay
    - **M3T**: Macro-Meta-Micro Trader
    - **VPIN**: Volume-Synchronized Probability of Informed Trading
    - **HWM**: High Water Mark
    - **SWR**: Sharp Wave Ripples
    - **VWAP**: Volume-Weighted Average Price

    ---

    ## Appendix B: Code Repository Structure

    ```
    janus/
    ├── src/
    │   └── janus/
    │       ├── neuromorphic/
    │       │   ├── visual_cortex/    # GAF, ViViT
    │       │   ├── prefrontal/       # LTN, compliance
    │       │   ├── amygdala/         # Risk, circuit breakers
    │       │   ├── basal_ganglia/    # Actor-Critic, M3T
    │       │   ├── cerebellum/       # Execution, StaticVWAP
    │       │   ├── hippocampus/      # Memory, PER
    │       │   ├── hypothalamus/     # Position sizing, Kelly
    │       │   ├── thalamus/         # Attention, fusion
    │       │   └── cortex/           # Strategic policy
    │       ├── services/
    │       │   ├── forward/          # Rust execution service
    │       │   ├── backward/         # Python training service
    │       │   └── gateway/          # API orchestration
    │       └── crates/
    │           ├── compliance/       # HyroTrader rules
    │           ├── backtest/         # Temporal Fortress
    │           └── execution/        # Exchange clients
    ├── config/
    │   ├── forward.toml
    │   ├── backward.toml
    │   └── rules/
    │       └── prop_firm_rules.json
    ├── docs/
    │   └── research/
    │       ├── JANUS_ARCHITECTURAL_SPECIFICATION.md  # This document
    │       └── JANUS_IMPLEMENTATION_STATUS.md        # Companion doc
    └── docker/
        ├── Dockerfile.forward
        └── Dockerfile.backward
    ```

    ---

    ## Document Status

    - **Version**: 2.0
    - **Type**: Architectural Specification
    - **Implementation Status**: See `JANUS_IMPLEMENTATION_STATUS.md`
    - **Last Updated**: January 2025
    - **Next Review**: Q2 2025

    ---

    **End of Architectural Specification**
