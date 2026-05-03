# JANUS Brain-Inspired Trading Architecture

> Reference architecture document for the JANUS neuromorphic trading pipeline.
> Consolidated from the pre-production sprint (Phases 1–7, completed February 2026).

---

## System Overview

JANUS is a brain-inspired algorithmic trading engine where each component mirrors a brain region. The Central Nervous System (CNS) orchestrates boot, runtime monitoring, and emergency shutdown. All trading decisions flow through a 6-stage `TradingPipeline` that is auditable end-to-end.

```
╔═══════════════════════════════════════════════════════════════════════╗
║         FKS BRAIN-INSPIRED TRADING SYSTEM ARCHITECTURE               ║
╚═══════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────┐
│                     CNS (Central Nervous System)                     │
│                         The Brain Stem                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────────────────────────────────────────────────┐       │
│  │  PRE-FLIGHT CHECKS                                        │       │
│  │  ✓ Infrastructure   ✓ Sensory   ✓ Regulatory             │       │
│  │  ✓ Strategy         ✓ Executive                           │       │
│  └───────────────────────────────────────────────────────────┘       │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────┐       │
│  │  WATCHDOG                                                  │       │
│  │  Monitors: Data Feed | Regime | Kill Switch | Execution   │       │
│  │  Action: Emergency Kill if failure detected                │       │
│  └───────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ orchestrates
┌─────────────────────────────────────────────────────────────────────┐
│                      BRAIN REGIONS                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │  THALAMUS    │   │  VISUAL      │   │  REGIME      │            │
│  │  (Sensory)   │   │  CORTEX      │   │  DETECTOR    │            │
│  │              │   │  (ViViT)     │   │              │            │
│  │ WebSocket ←──┼───┼─ Optional    │   │ Market State │            │
│  │ Bybit Ticks  │   │              │   │ Classification│           │
│  └──────┬───────┘   └──────────────┘   └──────┬───────┘            │
│         │                                       │                    │
│         ↓                                       ↓                    │
│  ┌─────────────────────────────────────────────────────┐            │
│  │          PREFRONTAL CORTEX (Strategy Engine)        │            │
│  │                                                      │            │
│  │  ┌────────────────────────────────────────┐         │            │
│  │  │  STRATEGY AFFINITY                     │         │            │
│  │  │  Tracks performance per asset          │         │            │
│  │  │  Enables/disables strategies           │         │            │
│  │  └────────────────────────────────────────┘         │            │
│  │                                                      │            │
│  │  ┌────────────────────────────────────────┐         │            │
│  │  │  STRATEGY GATING                       │         │            │
│  │  │  Filters by regime & affinity          │         │            │
│  │  └────────────────────────────────────────┘         │            │
│  │                                                      │            │
│  │  Active Strategies:                                 │            │
│  │  • EMAFlip  • TrendPullback  • MomentumSurge        │            │
│  │  • MeanReversion  • BollingerSqueeze  • +4 more     │            │
│  │                                                      │            │
│  └──────────────────────────┬───────────────────────────┘            │
│                             │ signals                                │
│                             ↓                                        │
│  ┌─────────────────────────────────────────────────────┐            │
│  │          HYPOTHALAMUS (Position Sizing)             │            │
│  │                                                      │            │
│  │  Scales position size based on:                     │            │
│  │  • Market regime (from Regime Bridge)               │            │
│  │  • Account balance                                  │            │
│  │  • Risk limits                                      │            │
│  │                                                      │            │
│  │  Crisis → 25% size | Trending → 100% size           │            │
│  │                                                      │            │
│  └──────────────────────────┬───────────────────────────┘            │
│                             │ sized orders                           │
│                             ↓                                        │
│  ┌─────────────────────────────────────────────────────┐            │
│  │          AMYGDALA (Risk Manager)                    │            │
│  │                                                      │            │
│  │  ┌────────────────────────────────────────┐         │            │
│  │  │  CORRELATION TRACKER                   │         │            │
│  │  │  Prevents over-concentration           │         │            │
│  │  │  BTC-ETH: 0.85  ETH-SOL: 0.70          │         │            │
│  │  └────────────────────────────────────────┘         │            │
│  │                                                      │            │
│  │  • Kill Switch (emergency stop)                     │            │
│  │  • Circuit Breakers (drawdown limits)               │            │
│  │  • Max correlated positions                         │            │
│  │                                                      │            │
│  └──────────────────────────┬───────────────────────────┘            │
│                             │ validated orders                       │
│                             ↓                                        │
└─────────────────────────────┼───────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   MOTOR CORTEX (Execution)                           │
│                                                                      │
│  Bybit API ← gRPC → Order Router → Fill Tracker                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   MEMORY SYSTEMS (Storage)                           │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Redis      │  │  PostgreSQL  │  │   QuestDB    │              │
│  │              │  │              │  │              │              │
│  │ • Real-time  │  │ • Positions  │  │ • Time-series│              │
│  │ • Pub/Sub    │  │ • Trades     │  │ • Ticks      │              │
│  │ • Cache      │  │ • Analytics  │  │ • Fast write │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Brain Region Reference

| Brain Region | Crate / Module | Function | Key Structures |
|---|---|---|---|
| **CNS** | `crates/cns` | Boot orchestration, pre-flight, watchdog, shutdown coordination | `PreFlightRunner`, `CnsWatchdog`, `BrainRuntime` |
| **Thalamus** | `services/data` | Sensory input — WebSocket feeds, market data ingestion | WebSocket client, tick normalization |
| **Prefrontal Cortex** | `crates/strategies` | Strategy engine — signal generation, affinity tracking, gating | `StrategyAffinityTracker`, `StrategyGate` |
| **Hypothalamus** | `neuromorphic/hypothalamus` | Position sizing — regime-adaptive scaling | Regime-based scale factors (0.2–1.25) |
| **Amygdala** | `neuromorphic/amygdala` | Risk management — kill switch, circuit breakers, threat detection | `KillSwitch`, `EmergencyOrderManager` |
| **Hippocampus** | `neuromorphic/hippocampus` | Memory — pattern replay, experience buffer | Episode storage, consolidation |
| **Cerebellum** | `neuromorphic/cerebellum` | Precision timing, motor execution coordination | Timing calibration |
| **Basal Ganglia** | `neuromorphic/basal_ganglia` | Action selection, habit formation, reward learning | Reinforcement signals |
| **Visual Cortex** | `neuromorphic/visual_cortex` | GAF image processing, ViViT pattern recognition (optional) | `VisualCortex::try_load()` |
| **Regime Detector** | `crates/regime` | Market state classification and regime bridge | `RegimeBridge`, Redis pub/sub |
| **Motor Cortex** | `services/execution` | Order execution — gRPC to exchange APIs | `ExecutionClient`, fill tracking |

---

## TradingPipeline — 6-Stage Evaluation

Every trading decision passes through all six stages in order. Each stage can block or modify the signal. The pipeline is implemented in `forward/src/brain_wiring.rs`.

```
┌──────────────────────────────────────────────────────────────────┐
│                     TradingPipeline.evaluate()                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Stage 0: KILL SWITCH                                             │
│  ├─ Check atomic flag                                             │
│  └─ If active → Block ALL signals immediately                    │
│                                                                    │
│  Stage 1: REGIME BRIDGE                                           │
│  ├─ Map market state to hypothalamus/amygdala regimes            │
│  ├─ Check minimum confidence threshold                           │
│  └─ If below confidence → Block                                  │
│                                                                    │
│  Stage 2: HYPOTHALAMUS (Position Scaling)                        │
│  ├─ Apply regime-based scale factor:                             │
│  │   Crisis       → 0.20                                         │
│  │   Uncertain    → 0.50                                         │
│  │   Mean-Revert  → 0.75                                         │
│  │   Trending     → 1.00                                         │
│  │   Strong Bull  → 1.25                                         │
│  └─ Respect account and risk limits                              │
│                                                                    │
│  Stage 3: AMYGDALA (Threat Detection)                            │
│  ├─ Run threat assessment                                        │
│  ├─ ReduceOnly in Crisis regime                                  │
│  └─ Apply high-risk scaling                                      │
│                                                                    │
│  Stage 4: STRATEGY GATE                                          │
│  ├─ Check explicit deny/allow lists                              │
│  ├─ Check regime compatibility                                   │
│  └─ Check affinity weight ≥ threshold                            │
│                                                                    │
│  Stage 5: CORRELATION FILTER                                     │
│  ├─ Check correlated exposure across open positions              │
│  └─ Block if exceeds max_correlated_positions                    │
│                                                                    │
│  ✅ All Passed → Proceed { scale_factor }                        │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Tick to Trade

```
1. TICK arrives from Bybit WebSocket
   ↓
2. THALAMUS processes raw tick data
   ↓
3. REGIME DETECTOR classifies market state
   ↓ (publishes via Redis pub/sub)
4. REGIME BRIDGE distributes to subscribers
   ↓
5. PREFRONTAL CORTEX evaluates strategies
   • Strategy Gating filters by regime & affinity
   • Only enabled strategies generate signals
   ↓
6. HYPOTHALAMUS sizes position
   • Adjusts for regime (crisis = small, trend = large)
   ↓
7. AMYGDALA validates risk
   • Checks correlation limits
   • Checks kill switch status
   • Checks circuit breakers
   ↓
8. MOTOR CORTEX executes
   • Sends order to Bybit via gRPC
   • Tracks fill
   ↓
9. FEEDBACK LOOP
   • Record trade result in Affinity Tracker
   • Update correlation matrix
   • Log metrics to Prometheus
```

---

## Safety Mechanisms

### Kill Switch (Amygdala — Stage 0)

| Property | Value |
|---|---|
| Manual trigger | HTTP API (auth-gated) |
| Auto trigger | Max drawdown, system health failure, watchdog |
| Target response time | < 100 ms |
| Action | Close all positions, halt new signals, alert team |
| Implementation | `neuromorphic/amygdala/kill_switch.rs` — `KillSwitch`, `EmergencyOrderManager` trait |

### Circuit Breakers

- Daily loss limit
- Per-position loss limit
- Consecutive loss threshold
- Action: Pause trading, alert team

### Pre-Flight Checks (CNS)

Run before system start. All critical checks must pass for trading to begin.

| Phase | Checks | Criticality |
|---|---|---|
| **Infrastructure** | Redis ping, PostgreSQL query, QuestDB HTTP, Prometheus registry | Critical |
| **Sensory** | Exchange WebSocket connect, data feed latency, ViViT model | Critical (ViViT is Optional) |
| **Regulatory** | Kill switch armed, circuit breakers initialized, hypothalamus scaling | Critical |
| **Strategy** | Regime detector warmup, strategy instantiation, correlation tracker | Critical |
| **Executive** | Execution service gRPC, Bybit API connectivity, order path integrity | Critical |

Environment controls:
- `BRAIN_PREFLIGHT_ONLY=true` — dry-run mode (check but don't start trading)
- `BRAIN_ENFORCE_PREFLIGHT=true` — abort on critical failure (default)
- `BRAIN_PREFLIGHT_TIMEOUT_SECS=30` — global timeout

### Watchdog (CNS)

| Property | Value |
|---|---|
| Interval | Configurable (default 5 s) |
| Component states | Alive → Degraded → Dead |
| Criticality levels | Critical (triggers kill), Important (degrade), NonEssential (warn) |
| Auto-restart | Configurable per component |
| Kill time target | < 100 ms |

### Correlation Limits (Amygdala — Stage 5)

| Property | Default |
|---|---|
| Max correlated positions | 3 |
| Correlation threshold | 0.75 |
| Window | 100 observations |
| Min observations before trusted | 20 |
| Monitored pairs | 9 (see `config/correlation_pairs.toml`) |

---

## Strategy Affinity System

The Strategy Affinity Tracker learns which strategies perform best on which assets over time.

**Decision pipeline** (`StrategyGate.should_run()`):

1. **Deny list** — If strategy is explicitly disabled for asset → block
2. **Allow list** — If non-empty and strategy not in list → block
3. **Regime compatibility** — Check preferred strategies for current regime
4. **Affinity weight** — Block if historical performance below threshold

**Persistence**: Redis via `AffinityRedisStore` with configurable auto-save interval.

**Configuration**: `config/strategy_affinity.toml` — per-asset strategy preferences, per-regime preferred strategies.

**HTTP API**:
- `GET /api/v1/brain/affinity` — export current affinities
- `POST /api/v1/brain/affinity/reset` — reset affinity data

---

## Observability

### Prometheus Metrics

| Metric | Type | Purpose |
|---|---|---|
| `janus_brain_pipeline_evaluations_total` | Counter | Total pipeline runs |
| `janus_brain_pipeline_proceeds_total` | Counter | Trades approved |
| `janus_brain_pipeline_blocks_total` | CounterVec | Blocks by stage |
| `janus_brain_pipeline_evaluation_duration_us` | Histogram | Pipeline latency (µs) |
| `janus_brain_pipeline_scale` | Histogram | Position scale factors |
| `janus_brain_pipeline_kill_switch_active` | Gauge | Kill switch state |
| `janus_brain_pipeline_regime` | GaugeVec | Regime distribution |
| `janus_brain_pipeline_confidence` | Histogram | Regime confidence values |
| `janus_brain_pipeline_amygdala_high_risk_total` | Counter | Threat detections |
| `janus_brain_pipeline_gate_rejections_total` | Counter | Strategy gate blocks |
| `janus_brain_pipeline_correlation_blocks_total` | Counter | Correlation blocks |
| `janus_brain_boot_passed` | Gauge | Boot status |
| `janus_per_strategy_pnl_cumulative` | GaugeVec | Per-strategy P&L |
| `janus_signal_generation_duration_seconds` | Histogram | Signal latency |
| `janus_signal_validation_duration_seconds` | Histogram | Validation latency |

### Grafana Dashboards

| Dashboard | File | Content |
|---|---|---|
| Brain Pipeline | `brain-dashboard.json` | Pipeline overview, kill switch, regime, scaling, blocks by stage |
| Strategy P&L | `janus_strategy_dashboard.json` | Per-strategy P&L, confidence distributions |
| Regime Detection | `janus_regime_dashboard.json` | Regime transitions, ensemble agreement |
| CNS Health | `janus_cns_dashboard.json` | Watchdog status, component health |
| Main Overview | `janus_dashboard.json` | System-wide overview |

---

## Key File Locations

### Brain Wiring & Pipeline
| File | Purpose |
|---|---|
| `services/forward/src/brain_wiring.rs` | `TradingPipeline` — 6-stage evaluation |
| `neuromorphic/amygdala/kill_switch.rs` | `KillSwitch`, `EmergencyOrderManager` |
| `crates/strategies/src/affinity.rs` | `StrategyAffinityTracker` |
| `crates/strategies/src/gating.rs` | `StrategyGate` — 4-step decision pipeline |
| `crates/risk/src/correlation.rs` | `CorrelationTracker` — rolling Pearson correlation |

### CNS (Boot & Runtime)
| File | Purpose |
|---|---|
| `crates/cns/src/preflight/mod.rs` | `PreFlightRunner`, `BootPhase`, `BootReport` |
| `crates/cns/src/preflight/infra.rs` | Redis, PostgreSQL, QuestDB, Prometheus checks |
| `crates/cns/src/preflight/sensory.rs` | WebSocket, latency, ViViT checks |
| `crates/cns/src/preflight/regulatory.rs` | Kill switch, circuit breaker, hypothalamus checks |
| `crates/cns/src/preflight/strategy.rs` | Regime detector, strategy instantiation, correlation checks |
| `crates/cns/src/preflight/executive.rs` | Execution service, order path checks |
| `crates/cns/src/watchdog.rs` | `CnsWatchdog` — runtime health monitoring |

### Configuration
| File | Purpose |
|---|---|
| `config/strategy_affinity.toml` | Per-asset strategy preferences (5 assets configured) |
| `config/correlation_pairs.toml` | Correlation pair monitoring (9 pairs, 5 assets) |

### Integration Tests
| File | Purpose |
|---|---|
| `brain_wiring_integration.rs` | Pipeline stage-by-stage verification |
| `brain_runtime_integration.rs` | Full boot → evaluate → shutdown lifecycle |

---

## Neuro-Symbolic Integration

JANUS combines two AI paradigms:

1. **Neural (Vision)**: DiffGAF-LSTM / ViViT processes market data as Gramian Angular Field images for visual pattern recognition.
2. **Symbolic (Logic)**: Logic Tensor Networks (LTN) with Łukasiewicz t-norms apply trading rules and constraints.
3. **Integration**: Neural outputs are gated by symbolic reasoning for explainable, auditable decisions.

The Visual Cortex (ViViT) is optional — the system boots and trades normally without it, logging a warning during pre-flight.

---

*See also: [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) for deployment topology, [NEUROMORPHIC_ARCHITECTURE.md](NEUROMORPHIC_ARCHITECTURE.md) for brain region theory.*