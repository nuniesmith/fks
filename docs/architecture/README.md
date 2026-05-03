---
title: "Architecture Documentation"
category: "architecture"
tags: ["architecture", "system-design", "janus", "neuromorphic"]
---

# Architecture Documentation

This directory contains permanent, high-level architectural documentation for Project JANUS/FKS.

## Core Documents

- **[Brain Architecture](./BRAIN_ARCHITECTURE.md)** - Complete brain-inspired system architecture, 6-stage TradingPipeline, safety mechanisms, and observability reference
- **[System Architecture](./SYSTEM_ARCHITECTURE.md)** - Deployment topology (home cluster + cloud)
- **[Neuromorphic Architecture](./NEUROMORPHIC_ARCHITECTURE.md)** - Brain-inspired system design theory
- **[Implementation Guide](./NEUROMORPHIC_IMPLEMENTATION_GUIDE.md)** - How theory maps to code
- **[3-Phase Plan](./NEUROMORPHIC_3PHASE_PLAN.md)** - Development roadmap
- **[CI/CD Architecture](./CI_CD_ARCHITECTURE.md)** - Build and deployment pipeline
- **[Startup Flow](./STARTUP_FLOW.md)** - CNS boot sequence and pre-flight checks
- **[Refactoring Notes](./REFACTORING_NOTES.md)** - Architectural refactoring history

## Brain Region → Code Mapping

| Brain Region | Role | Code Location |
|---|---|---|
| **CNS** | Boot orchestration, pre-flight, watchdog, shutdown | `src/janus/crates/cns` |
| **Thalamus** | Sensory input — WebSocket feeds, market data | `src/janus/services/data` |
| **Prefrontal Cortex** | Strategy engine — signal generation, affinity, gating | `src/janus/crates/strategies` |
| **Hypothalamus** | Position sizing — regime-adaptive scaling | `src/janus/neuromorphic/hypothalamus` |
| **Amygdala** | Risk management — kill switch, circuit breakers | `src/janus/neuromorphic/amygdala` |
| **Hippocampus** | Memory — pattern replay, experience buffer | `src/janus/neuromorphic/hippocampus` |
| **Cerebellum** | Precision timing, motor execution coordination | `src/janus/neuromorphic/cerebellum` |
| **Basal Ganglia** | Action selection, habit formation, reward learning | `src/janus/neuromorphic/basal_ganglia` |
| **Visual Cortex** | GAF image processing, ViViT pattern recognition | `src/janus/neuromorphic/visual_cortex` |
| **Regime Detector** | Market state classification, regime bridge | `src/janus/crates/regime` |
| **Motor Cortex** | Order execution — gRPC to exchange APIs | `src/janus/services/execution` |

## TradingPipeline (6-Stage Evaluation)

Every trading decision passes through all six stages in `forward/src/brain_wiring.rs`:

| Stage | Component | Action |
|-------|-----------|--------|
| 0 | Kill Switch | Block ALL if active |
| 1 | Regime Bridge | Map market state, check confidence |
| 2 | Hypothalamus | Apply regime-based position scaling |
| 3 | Amygdala | Threat detection, crisis mode |
| 4 | Strategy Gate | Per-asset, per-regime filtering |
| 5 | Correlation | Block over-concentrated exposure |

See [BRAIN_ARCHITECTURE.md](./BRAIN_ARCHITECTURE.md) for the complete reference.

## Research Foundation

For the detailed mathematical specifications, see [`../research/`](../research/).

---

**Note**: For implementation details, refer to code docstrings and generated API docs at `/docs/api/`.