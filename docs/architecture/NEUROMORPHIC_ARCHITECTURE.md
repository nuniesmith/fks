# JANUS Neuromorphic Architecture

**A Brain-Inspired Algorithmic Trading System**

Version: 1.0  
Last Updated: 2025-01-XX  
Author: Jordan Smith

---

## Table of Contents

1. [Overview](#overview)
2. [Design Philosophy](#design-philosophy)
3. [Brain Region Mapping](#brain-region-mapping)
4. [Directory Structure](#directory-structure)
5. [Information Flow](#information-flow)
6. [Implementation Guide](#implementation-guide)
7. [Architectural Invariants](#architectural-invariants)
8. [Integration with Services](#integration-with-services)

---

## Overview

JANUS implements a **neuromorphic architecture** that maps cognitive neuroscience principles to algorithmic trading. Each brain region's computational role is replicated in the system architecture, creating a biologically-inspired trading intelligence.

### Why Neuromorphic?

Traditional trading systems follow rigid, hierarchical designs. The neuromorphic approach provides:

- **Parallel Processing**: Multiple brain regions process different aspects simultaneously
- **Hierarchical Abstraction**: Low-level patterns → Mid-level tactics → High-level strategy
- **Homeostatic Regulation**: Self-balancing mechanisms maintain system health
- **Emotional Override**: Fear systems can immediately halt trading when threats detected
- **Memory Consolidation**: Wake-sleep cycles transfer episodic experiences to long-term schemas
- **Adaptive Learning**: Continuous learning at multiple timescales

### Core Principle

> "If it works in the brain after millions of years of evolution, it might work in trading."

---

## Design Philosophy

### 1. Biological Inspiration

Each component maps to a specific brain region with analogous function:

| Brain Region | Biological Function | Trading Function |
|--------------|---------------------|------------------|
| **Cortex** | Executive function, strategic planning | Manager agent, portfolio strategy |
| **Hippocampus** | Episodic memory, spatial navigation | Worker agent, experience replay |
| **Basal Ganglia** | Action selection, reward learning | Actor-Critic RL, action gating |
| **Thalamus** | Sensory relay, attention gating | Data fusion, signal filtering |
| **Prefrontal** | Logic, impulse control, ethics | LTN constraints, compliance |
| **Amygdala** | Fear, threat detection | Circuit breakers, kill switch |
| **Hypothalamus** | Homeostasis, energy balance | Risk appetite, position sizing |
| **Cerebellum** | Motor coordination, error correction | Order execution, PID control |
| **Visual Cortex** | Visual processing, pattern recognition | GAF/ViViT, pattern detection |
| **Brainstem** | Basic life functions, arousal/sleep | System orchestration, wake/sleep |

### 2. Hierarchical Processing

```
Low-Level (Fast, Reactive)
├── Visual Cortex: Pattern recognition (GAF/ViViT)
├── Thalamus: Attention and fusion
└── Cerebellum: Execution control

Mid-Level (Tactical)
├── Hippocampus: Worker agent (tactical policy)
├── Basal Ganglia: Actor-Critic (action selection)
└── Hypothalamus: Position sizing

High-Level (Strategic, Slow)
├── Cortex: Manager agent (strategic policy)
├── Prefrontal: Logic and compliance (LTN)
└── Amygdala: Fear and safety (circuit breakers)
```

### 3. Dual Timescale Learning

- **Fast (Hippocampus)**: Rapid episodic encoding during trading
- **Slow (Cortex)**: Gradual schema consolidation during sleep

### 4. Fail-Safe Design

- **Amygdala overrides everything**: Safety first
- **Prefrontal veto**: Compliance is non-negotiable
- **Homeostatic bounds**: Automatic risk scaling

---

## Brain Region Mapping

### Cortex: Strategic Planning & Long-term Memory

**Location**: `src/janus/neuromorphic/cortex/`

**Neuroscience**: Executive function, strategic planning, declarative memory

**Components**:
- `manager/`: Feudal RL manager agent
- `memory/`: Long-term consolidation and schemas
- `planning/`: Scenario analysis, Monte Carlo, optimization

**Key Files**:
- `strategic_policy.rs`: High-level trading strategy
- `goal_setting.rs`: Portfolio objectives
- `hierarchical_rl.rs`: Manager agent implementation
- `schemas.rs`: Market regime schemas
- `consolidation.rs`: Memory consolidation (links to Backward)

**Responsibilities**:
1. Set strategic goals ("maximize Sharpe, drawdown <15%")
2. Generate subgoals for Worker ("accumulate AAPL over 2h")
3. Consolidate episodic → abstract schemas
4. Store declarative knowledge ("FOMC increases volatility")

**Mathematical Foundation**:

Manager policy:
```
g_t = π_Manager(s_t^high)
```

Value function:
```
V_Manager(s) = E[Σ γ^t r_t^high | s_0 = s]
```

---

### Hippocampus: Episodic Memory & Experience Replay

**Location**: `src/janus/neuromorphic/hippocampus/`

**Neuroscience**: Memory formation, spatial navigation, replay during sleep

**Components**:
- `worker/`: Feudal RL worker agent (tactical execution)
- `replay/`: Prioritized Experience Replay buffer
- `episodes/`: Trade sequences and market events
- `swr/`: Sharp Wave Ripple simulator (compressed replay)

**Key Files**:
- `tactical_policy.rs`: Low-level execution tactics
- `worker_agent.rs`: Worker implementation
- `replay_buffer.rs`: PER storage
- `priority.rs`: TD-error + logic violation priority
- `compressed_replay.rs`: 10-20x speed replay

**Responsibilities**:
1. Execute subgoals from Manager
2. Store trade experiences in episodic buffer
3. Prioritize replay: TD-error + logic violations + reward
4. Compress replay 10-20x during sleep

**Mathematical Foundation**:

Worker policy conditioned on subgoal:
```
a_t = π_Worker(s_t^low, g_t)
```

Intrinsic reward:
```
r_t^intrinsic = -||s_t - g_t||²
```

Priority:
```
p_i = |δ_i| + λ_logic * v_i + λ_reward * |r_i|
```

Sampling probability:
```
P(i) = p_i^α / Σ_j p_j^α
```

---

### Basal Ganglia: Action Selection & Reinforcement Learning

**Location**: `src/janus/neuromorphic/basal_ganglia/`

**Neuroscience**: Action selection via dual pathways (Go/No-Go)

**Components**:
- `actor/`: Policy network for action distribution
- `critic/`: Value network for advantage estimation
- `praxeological/`: Go/No-Go signal computation
- `selection/`: Competitive action selection

**Key Files**:
- `policy_network.rs`: Neural policy
- `value_network.rs`: State value estimation
- `go_signal.rs`: Direct pathway (action initiation)
- `no_go_signal.rs`: Indirect pathway (action inhibition)
- `advantage.rs`: Advantage function A = Q - V

**Responsibilities**:
1. Generate action proposals (BUY/SELL/HOLD)
2. Compute action values (Q-values)
3. Gate actions through dual pathways
4. Maintain habit cache for frequent patterns

**Mathematical Foundation**:

Actor policy:
```
π_θ(a|s) = softmax(W_π h(s) + b_π)
```

Critic value:
```
V_ω(s) = W_V h(s) + b_V
```

Advantage:
```
A(s,a) = Q(s,a) - V(s)
```

Go signal (direct pathway):
```
Go(a) = max(W_direct h(s))_a
```

No-Go signal (indirect pathway):
```
NoGo(a) = σ(W_indirect [h(s); risk; VPIN])
```

Final action:
```
a_final = {
  a_proposed  if NoGo(a) < τ_veto
  HOLD        otherwise
}
```

---

### Thalamus: Attention & Multimodal Fusion

**Location**: `src/janus/neuromorphic/thalamus/`

**Neuroscience**: Sensory relay, attention gating, arousal regulation

**Components**:
- `attention/`: Cross-attention mechanisms
- `gating/`: Sensory gating and filtering
- `routing/`: Dynamic information routing
- `fusion/`: Price, volume, orderbook, sentiment fusion

**Key Files**:
- `cross_attention.rs`: Multi-head cross-attention
- `gate.rs`: Attention gating
- `sensory_gate.rs`: Noise filtering
- `price_fusion.rs`, `volume_fusion.rs`, etc.

**Responsibilities**:
1. Gate incoming market data (filter noise)
2. Fuse multiple modalities (price, volume, text)
3. Route relevant information to brain regions
4. Implement attention for saliency

**Mathematical Foundation**:

Gated cross-attention:
```
Attention(Q, K, V) = softmax(QK^T / √d_k) V
```

Gating scalar:
```
λ_gate = σ(W_g [h_m; h_n] + b_g)
```

Fused representation:
```
h_fused = h_m + λ_gate * Attention(h_m, h_n, h_n)
```

---

### Prefrontal Cortex: Logic, Planning & Compliance

**Location**: `src/janus/neuromorphic/prefrontal/`

**Neuroscience**: Logical reasoning, impulse control, ethics

**Components**:
- `ltn/`: Logic Tensor Networks
- `conscience/`: Compliance constraints
- `planning/`: Goal decomposition
- `goals/`: Goal hierarchy management

**Key Files**:
- `predicates.rs`: Trading rule predicates
- `fuzzy_logic.rs`: Łukasiewicz T-norms
- `wash_sale.rs`: Wash sale prevention
- `risk_limits.rs`: Internal risk limits
- `goal_decomposition.rs`: Break down goals

**Responsibilities**:
1. Encode trading rules as differentiable logic
2. Enforce regulatory compliance (wash sale, limits)
3. Block non-compliant actions
4. Decompose high-level goals

**Mathematical Foundation**:

LTN predicate grounding:
```
G(P)(x) = σ(W_P x + b_P) ∈ [0,1]
```

Łukasiewicz conjunction:
```
G(A ∧ B) = max(0, G(A) + G(B) - 1)
```

Wash sale constraint:
```
∀t, k∈[1,30]: ¬(SaleAtLoss(t) ∧ Buy(t+k))
```

Satisfiability:
```
SatAgg(K) = (1/m Σ G(φ_i)^p)^(1/p)
```

---

### Amygdala: Fear, Threat Detection & Circuit Breakers

**Location**: `src/janus/neuromorphic/amygdala/`

**Neuroscience**: Fear conditioning, threat detection

**Components**:
- `fear/`: Fear-conditioned inhibition network
- `vpin/`: VPIN toxicity detection
- `circuit_breakers/`: Kill switch, emergency halt
- `threat_detection/`: Anomaly, flash crash detection

**Key Files**:
- `fear_network.rs`: FNI-RL implementation
- `vpin_calculator.rs`: Volume-synchronized toxicity
- `kill_switch.rs`: Emergency kill switch (fail-safe)
- `anomaly_detector.rs`: Statistical anomaly detection

**Responsibilities**:
1. Detect market panic and flash crashes
2. Trigger emergency circuit breakers
3. Override ALL other systems in extreme conditions
4. Learn fear-conditioned responses

**Mathematical Foundation**:

VPIN (toxicity):
```
VPIN_t = Σ|V_buy,i - V_sell,i| / ΣV_i
```

Fear activation:
```
f_fear(s) = σ(W_f [VPIN; σ_vol; Δp_max] + b_f)
```

Circuit breaker:
```
KillSwitch = {
  ACTIVATE  if f_fear > τ_fear OR VPIN > τ_VPIN
  STANDBY   otherwise
}
```

---

### Hypothalamus: Homeostasis & Risk Appetite

**Location**: `src/janus/neuromorphic/hypothalamus/`

**Neuroscience**: Homeostatic regulation, motivation, energy balance

**Components**:
- `homeostasis/`: Balance tracking and deviation correction
- `position_sizing/`: Kelly criterion, volatility scaling
- `risk_appetite/`: Dynamic risk tolerance
- `energy/`: Capital allocation, cash reserves

**Key Files**:
- `balance_tracker.rs`: Portfolio balance tracking
- `kelly_criterion.rs`: Kelly position sizing
- `volatility_scaling.rs`: Vol-adjusted sizing
- `drawdown_scaling.rs`: Reduce size during drawdown

**Responsibilities**:
1. Maintain target portfolio balance (setpoints)
2. Adjust position sizes based on volatility/drawdown
3. Regulate risk appetite (fear vs. greed)
4. Ensure cash reserves (minimum 20%)

**Mathematical Foundation**:

Kelly criterion (fractional):
```
f* = (p(b+1) - 1) / b
position_size = (f*/2) * capital  // Kelly halving
```

Volatility scaling:
```
size_adjusted = size_base * (σ_target / σ_current)
```

Drawdown scaling:
```
size_DD = size_base * max(0.1, 1 - DD_current/DD_max)
```

Homeostatic correction (PID):
```
Δallocation = K_p(target - current) + K_d d(target - current)/dt
```

---

### Cerebellum: Motor Control & Execution

**Location**: `src/janus/neuromorphic/cerebellum/`

**Neuroscience**: Motor coordination, procedural learning, forward models

**Components**:
- `execution/`: Order routing, TWAP/VWAP
- `impact/`: Almgren-Chriss optimal execution
- `forward_models/`: Latency compensation, fill prediction
- `error_correction/`: PID control, adaptive feedback

**Key Files**:
- `order_router.rs`: Route orders to exchanges
- `almgren_chriss.rs`: Optimal execution
- `smith_predictor.rs`: Latency compensation
- `pid_controller.rs`: PID control

**Responsibilities**:
1. Route orders with minimal slippage
2. Predict and minimize market impact
3. Compensate for execution latency
4. Learn from execution errors

**Mathematical Foundation**:

Almgren-Chriss trajectory:
```
x_t = X * sinh(κ(T-t)) / sinh(κT)
κ = √(ησ/τ)
```

Market impact:
```
Impact = η * σ * √(v / V_avg)
```

Smith predictor:
```
u(t) = K_c[e(t) + 1/τ_I ∫e(τ)dτ + τ_D de/dt] + p̂(t + Δt)
```

---

### Visual Cortex: Pattern Recognition & Vision

**Location**: `src/janus/neuromorphic/visual_cortex/`

**Neuroscience**: Hierarchical visual processing

**Components**:
- `eyes/`: Data ingestion, preprocessing
- `gaf/`: Gramian Angular Fields (GASF, GADF)
- `vivit/`: Video Vision Transformer
- `visualization/`: UMAP, GradCAM, saliency

**Key Files**:
- `data_ingestion.rs`: Raw market data
- `gasf.rs`, `gadf.rs`: GAF transformation
- `differentiable.rs`: DiffGAF (learnable)
- `vivit_model.rs`: ViViT architecture
- `umap.rs`: Dimensionality reduction

**Responsibilities**:
1. Ingest and preprocess market data
2. Transform time series to visual manifolds
3. Extract spatiotemporal patterns
4. Visualize learned representations

**Mathematical Foundation**:

GAF normalization:
```
x̃_i = tanh((x_i - min(X))/(max(X) - min(X) + ε) * α + β)
```

GASF:
```
GASF_ij = cos(φ_i + φ_j), φ_i = arccos(x̃_i)
```

GADF:
```
GADF_ij = sin(φ_i - φ_j)
```

ViViT patch embedding:
```
z_f,i,j^(0) = E · flatten(V_f,i:i+P,j:j+P) + p_f,i,j
```

---

### Integration: Brainstem & Global Coordination

**Location**: `src/janus/neuromorphic/integration/`

**Neuroscience**: Basic life functions, arousal/sleep cycles

**Components**:
- `workflow/`: State machine orchestration
- `state/`: Global state management
- `api/`: REST, gRPC, WebSocket interfaces
- `engine/`: Wake-sleep cycle coordination

**Key Files**:
- `orchestrator.rs`: Main orchestration loop
- `wake_sleep.rs`: Wake-sleep coordination
- `forward_backward.rs`: Forward/Backward sync
- `message_bus.rs`: Inter-region messaging

**Responsibilities**:
1. Coordinate wake (Forward) and sleep (Backward) cycles
2. Manage global system state
3. Route messages between brain regions
4. Expose external APIs

---

## Directory Structure

```
src/janus/neuromorphic/
├── lib.rs                          # Main library entry
├── Cargo.toml                      # Package manifest
├── README.md                       # Module overview
│
├── cortex/                         # Strategic planning
│   ├── mod.rs
│   ├── manager/                    # Feudal RL manager
│   ├── memory/                     # Long-term consolidation
│   └── planning/                   # Scenario analysis
│
├── hippocampus/                    # Episodic memory
│   ├── mod.rs
│   ├── worker/                     # Feudal RL worker
│   ├── replay/                     # PER buffer
│   ├── episodes/                   # Trade sequences
│   └── swr/                        # Sharp wave ripples
│
├── basal_ganglia/                  # Action selection
│   ├── mod.rs
│   ├── actor/                      # Policy network
│   ├── critic/                     # Value network
│   ├── praxeological/              # Go/No-Go
│   └── selection/                  # Action selection
│
├── thalamus/                       # Attention & fusion
│   ├── mod.rs
│   ├── attention/                  # Cross-attention
│   ├── gating/                     # Sensory gates
│   ├── routing/                    # Info routing
│   └── fusion/                     # Multimodal fusion
│
├── prefrontal/                     # Logic & compliance
│   ├── mod.rs
│   ├── ltn/                        # Logic Tensor Networks
│   ├── conscience/                 # Compliance rules
│   ├── planning/                   # Goal decomposition
│   └── goals/                      # Goal management
│
├── amygdala/                       # Fear & safety
│   ├── mod.rs
│   ├── fear/                       # FNI-RL
│   ├── vpin/                       # Toxicity detection
│   ├── circuit_breakers/           # Kill switch
│   └── threat_detection/           # Anomaly detection
│
├── hypothalamus/                   # Homeostasis
│   ├── mod.rs
│   ├── homeostasis/                # Balance tracking
│   ├── position_sizing/            # Kelly, vol scaling
│   ├── risk_appetite/              # Dynamic tolerance
│   └── energy/                     # Capital allocation
│
├── cerebellum/                     # Execution
│   ├── mod.rs
│   ├── execution/                  # Order routing
│   ├── impact/                     # Almgren-Chriss
│   ├── forward_models/             # Latency compensation
│   └── error_correction/           # PID control
│
├── visual_cortex/                  # Pattern recognition
│   ├── mod.rs
│   ├── eyes/                       # Data ingestion
│   ├── gaf/                        # GAF transformation
│   ├── vivit/                      # ViViT model
│   └── visualization/              # UMAP, GradCAM
│
└── integration/                    # System coordination
    ├── mod.rs
    ├── workflow/                   # State machines
    ├── state/                      # Global state
    ├── api/                        # External APIs
    └── engine/                     # Orchestration
```

---

## Information Flow

### Wake State (Forward Service)

```
Market Data
    ↓
Visual Cortex (GAF/ViViT encoding)
    ↓
Thalamus (Multimodal fusion, attention gating)
    ↓
Cortex (Manager: "What's the strategic goal?")
    ↓
Hippocampus (Worker: "How do I achieve this subgoal?")
    ↓
Basal Ganglia (Actor-Critic: "Which action maximizes reward?")
    ↓
Prefrontal (LTN: "Does this violate compliance rules?") ──→ VETO if violated
    ↓
Amygdala (Fear: "Is this dangerous?") ──→ KILL SWITCH if threat
    ↓
Hypothalamus (Homeostasis: "What position size maintains balance?")
    ↓
Cerebellum (Execution: "Route order with minimal impact")
    ↓
Exchange
```

### Sleep State (Backward Service)

```
Hippocampus (Episodic buffer with today's experiences)
    ↓
SWR Simulator (Replay at 10-20x speed)
    ↓
Prioritized Sampling (TD-error + logic violations + reward)
    ↓
Basal Ganglia (Update Critic values)
    ↓
Prefrontal (Update LTN predicates based on violations)
    ↓
Cortex (Consolidate episodes → abstract schemas)
    ↓
Long-term Memory (Qdrant vector DB)
    ↓
UMAP Visualization (Detect new clusters)
```

---

## Implementation Guide

### Phase 1: Foundation (Weeks 1-2)

**Goal**: Set up infrastructure and common types

```bash
# 1. Create neuromorphic module (already done via script)
python3 create_neuromorphic_structure.py --base-path src/janus/neuromorphic

# 2. Add to workspace
# Edit src/janus/Cargo.toml:
#   members = ["neuromorphic", ...]

# 3. Implement common types
# Edit src/janus/neuromorphic/lib.rs
```

**Checklist**:
- [ ] Common error types (`Error`, `Result`)
- [ ] Common data structures (`MarketState`, `Action`, `Transition`)
- [ ] Message bus for inter-region communication
- [ ] Integration/engine orchestrator skeleton

### Phase 2: Visual Processing (Weeks 3-4)

**Goal**: Implement visual cortex for pattern recognition

**Checklist**:
- [ ] Data ingestion (`eyes/data_ingestion.rs`)
- [ ] GAF transformation (`gaf/gasf.rs`, `gaf/gadf.rs`)
- [ ] DiffGAF with learnable params (`gaf/differentiable.rs`)
- [ ] ViViT model integration (ONNX or tch-rs)
- [ ] UMAP visualization (`visualization/umap.rs`)

**Example**:

```rust
// visual_cortex/gaf/differentiable.rs
pub struct DiffGAF {
    alpha: f32,  // Learnable
    beta: f32,   // Learnable
}

impl DiffGAF {
    pub fn transform(&self, series: &Array1<f32>) -> (Array2<f32>, Array2<f32>) {
        // Normalize
        let normalized = series.mapv(|x| {
            let norm = (x - series.min()) / (series.max() - series.min() + 1e-8);
            (norm * self.alpha + self.beta).tanh()
        });
        
        // Polar coordinates
        let phi = normalized.mapv(|x| x.acos());
        
        // GASF and GADF
        let n = series.len();
        let mut gasf = Array2::zeros((n, n));
        let mut gadf = Array2::zeros((n, n));
        
        for i in 0..n {
            for j in 0..n {
                gasf[[i,j]] = (phi[i] + phi[j]).cos();
                gadf[[i,j]] = (phi[i] - phi[j]).sin();
            }
        }
        
        (gasf, gadf)
    }
}
```

### Phase 3: Decision Making (Weeks 5-7)

**Goal**: Implement actor-critic and logic constraints

**Checklist**:
- [ ] Basal Ganglia actor (`basal_ganglia/actor/policy_network.rs`)
- [ ] Basal Ganglia critic (`basal_ganglia/critic/value_network.rs`)
- [ ] Go/No-Go signals (`basal_ganglia/praxeological/`)
- [ ] Prefrontal LTN (`prefrontal/ltn/`)
- [ ] Thalamus fusion (`thalamus/fusion/`)

### Phase 4: Memory Systems (Weeks 8-10)

**Goal**: Implement episodic memory and consolidation

**Checklist**:
- [ ] Hippocampus episodic buffer (`hippocampus/replay/replay_buffer.rs`)
- [ ] Prioritized replay (`hippocampus/replay/priority.rs`)
- [ ] SWR compressed replay (`hippocampus/swr/compressed_replay.rs`)
- [ ] Cortex schema consolidation (`cortex/memory/consolidation.rs`)
- [ ] Qdrant integration for long-term storage

### Phase 5: Safety & Control (Weeks 11-12)

**Goal**: Implement safety systems and execution

**Checklist**:
- [ ] Amygdala fear network (`amygdala/fear/fear_network.rs`)
- [ ] VPIN calculator (`amygdala/vpin/vpin_calculator.rs`)
- [ ] Circuit breakers (`amygdala/circuit_breakers/kill_switch.rs`)
- [ ] Hypothalamus homeostasis (`hypothalamus/homeostasis/`)
- [ ] Position sizing (`hypothalamus/position_sizing/kelly_criterion.rs`)
- [ ] Cerebellum execution (`cerebellum/execution/order_router.rs`)
- [ ] Almgren-Chriss (`cerebellum/impact/almgren_chriss.rs`)

### Phase 6: Integration (Weeks 13-14)

**Goal**: Connect all regions and test end-to-end

**Checklist**:
- [ ] Integration engine (`integration/engine/orchestrator.rs`)
- [ ] Wake-sleep coordination (`integration/engine/wake_sleep.rs`)
- [ ] Message bus implementation (`integration/state/message_bus.rs`)
- [ ] Global state management (`integration/state/global_state.rs`)
- [ ] API layer (`integration/api/`)
- [ ] End-to-end integration tests
- [ ] Performance benchmarking

---

## Architectural Invariants

### Safety-Critical (MUST NOT VIOLATE)

1. **Amygdala Override**: Fear system ALWAYS overrides all other regions
2. **Prefrontal Veto**: LTN constraints MUST block non-compliant actions
3. **No Panic**: ZERO `panic!()`, `unwrap()`, or `expect()` in production code
4. **Fail-Safe Circuit Breakers**: Default to HALT on error
5. **Homeostatic Bounds**: Cash reserves ≥ 20%, leverage ≤ 2x

### Performance Requirements

1. **Forward Latency**: Visual Cortex → Decision < 100ms (target: 50ms)
2. **Backward Throughput**: Process > 10k experiences per sleep cycle
3. **Memory Efficiency**: Hippocampal buffer ≤ 10k transitions (FIFO)
4. **Parallel Processing**: Brain regions process concurrently (no GIL)

### Learning Requirements

1. **Dual Timescale**: Fast hippocampal learning, slow cortical consolidation
2. **Recall Gating**: Cortical updates gated by recall strength AND logic validity
3. **Priority Replay**: Replay prioritized by TD-error + logic violations + reward
4. **Schema Formation**: Clusters detected via UMAP + DBSCAN

---

## Integration with Services

### Mapping to Existing Services

The neuromorphic architecture integrates with the existing service architecture:

#### Forward Service (Wake State)
**Uses regions**:
- Visual Cortex (pattern recognition)
- Thalamus (multimodal fusion)
- Cortex (manager agent)
- Hippocampus (worker agent)
- Basal Ganglia (actor-critic)
- Prefrontal (LTN constraints)
- Amygdala (fear detection)
- Hypothalamus (position sizing)
- Cerebellum (execution)

#### Backward Service (Sleep State)
**Uses regions**:
- Hippocampus (episodic replay, SWR)
- Cortex (schema consolidation)
- Basal Ganglia (update critic)
- Prefrontal (update LTN)
- Visual Cortex (UMAP visualization)

#### Gateway Service
**Uses regions**:
- Integration (API layer, orchestration)

### Shared Crates Mapping

| Crate | Primary Brain Region | Secondary Regions |
|-------|---------------------|-------------------|
| `janus-core` | Integration (common types) | All |
| `janus-vision` | Visual Cortex | Thalamus |
| `janus-logic` | Prefrontal | Cortex |
| `janus-memory` | Hippocampus, Cortex | - |
| `janus-execution` | Cerebellum | Hypothalamus |
| `janus-proto` | Integration | All |

---

## Testing Strategy

### Unit Tests

Each component has its own tests:

```rust
// hippocampus/replay/tests/test_replay.rs
#[test]
fn test_prioritized_sampling() {
    let buffer = PrioritizedReplayBuffer::new(1000);
    // Add transitions with different priorities
    // Sample and verify priority distribution
}
```

### Integration Tests

Test inter-region communication:

```rust
// tests/integration/test_wake_cycle.rs
#[tokio::test]
async fn test_full_wake_cycle() {
    // Market data → Visual → Thalamus → Cortex → ... → Execution
    // Verify each region processes correctly
}
```

### Property-Based Tests

Use `proptest` or `quickcheck`:

```rust
#[proptest]
fn test_ltn_satisfiability_bounds(
    #[strategy(any::<Vec<f32>>()] predicates: Vec<f32>
) {
    let sat = SatAgg(&predicates);
    assert!(sat >= 0.0 && sat <= 1.0);
}
```

---

## Deployment

### Docker Compose

```yaml
services:
  forward:
    build: ./services/forward
    depends_on:
      - neuromorphic
    environment:
      - BRAIN_REGIONS=visual,thalamus,cortex,hippocampus,basal_ganglia,prefrontal,amygdala,hypothalamus,cerebellum
  
  backward:
    build: ./services/backward
    depends_on:
      - neuromorphic
    environment:
      - BRAIN_REGIONS=hippocampus,cortex,basal_ganglia,prefrontal
```

### Monitoring

Track each brain region separately:

- **Visual Cortex**: GAF transformation latency, ViViT inference time
- **Hippocampus**: Replay buffer size, priority distribution
- **Basal Ganglia**: Actor entropy, critic MSE
- **Prefrontal**: LTN satisfaction rate, constraint violations
- **Amygdala**: VPIN levels, fear activation frequency
- **Hypothalamus**: Position sizes, cash reserve levels
- **Cerebellum**: Execution slippage, market impact

---

## References

### Neuroscience Papers

1. Dayan, Hinton. "Feudal Reinforcement Learning." NIPS 1992.
2. Foster, Wilson. "Reverse Replay of Behavioural Sequences in Hippocampal Place Cells." Nature 2006.
3. Kandel et al. "Principles of Neural Science." 6th Ed., 2021.

### ML/RL Papers

1. Badreddine et al. "Logic Tensor Networks." Artificial Intelligence, 2022.
2. Schaul et al. "Prioritized Experience Replay." ICLR 2016.
3. Sutton, Barto. "Reinforcement Learning: An Introduction." 2nd Ed., 2018.

### Trading/Finance

1. Almgren, Chriss. "Optimal Execution of Portfolio Transactions." Journal of Risk, 2000.
2. Easley et al. "Flow Toxicity and Liquidity in a High-frequency World." Review of Financial Studies, 2012.

### Pattern Recognition

1. Wang, Oates. "Encoding Time Series as Images for Visual Inspection and Classification." AAAI 2015.
2. Arnab et al. "ViViT: A Video Vision Transformer." ICCV 2021.

---

## FAQ

**Q: Why map brain regions to trading?**  
A: Biological brains solve similar problems: process multimodal sensory input, make decisions under uncertainty, learn from experience, maintain homeostasis. These are exactly the challenges in algorithmic trading.

**Q: Isn't this over-engineered?**  
A: The complexity emerges naturally from neuroscience principles. Each region has a clear, focused responsibility. The modularity makes the system easier to understand and maintain.

**Q: Can I use only some brain regions?**  
A: Yes! Start with Visual Cortex + Basal Ganglia (perception + action selection). Add others as needed.

**Q: How does this relate to Forward/Backward services?**  
A: Forward = Wake state (uses most regions). Backward = Sleep state (memory consolidation). The neuromorphic structure is the implementation layer underneath.

**Q: What if a brain region fails?**  
A: Fail-safe design: Amygdala circuit breaker activates, system halts trading, enters safe mode.

---

## Next Steps

1. **Review generated structure**: `src/janus/neuromorphic/`
2. **Compile LaTeX docs**: See `scripts/audit/janus_neuromorphic_architecture.tex`
3. **Start implementing**: Follow Phase 1 of implementation guide
4. **Run tests**: `cargo test -p janus-neuromorphic`
5. **Integrate with services**: Connect to Forward/Backward services

---

**Last Updated**: 2025-01-XX  
**Version**: 1.0  
**Author**: Jordan Smith  
**License**: MIT