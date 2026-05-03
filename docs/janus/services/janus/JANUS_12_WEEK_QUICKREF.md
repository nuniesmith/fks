# JANUS 12-Week Development Plan - Quick Reference

## Overview

Transform JANUS into a complete, Rust-only neuromorphic trading signal generation system using Burn for ML.

**Key Principle**: JANUS generates signals only. Execution is handled separately.

---

## Phase 1: Data Foundation (Weeks 1-4)

### Week 1: Data Ingestion Enhancement
- Add Coinbase, Kraken, OKX exchange adapters
- Create unified `MarketDataEvent` types
- Implement order book depth, liquidations, funding rates
- New crate: `janus-exchanges`

### Week 2: News & Alternative Data
- Create news aggregation service (`services/news`)
- Implement RSS/Atom parser, Twitter API
- Add sentiment scoring with VADER
- New crate: `janus-sentiment`

### Week 3: Storage Layer
- Design asset configuration schema
- QuestDB schema migrations
- Parquet export for training data
- Create asset registry service

### Week 4: Data Quality Pipeline
- Create validation framework
- Implement outlier/anomaly detection (Z-score, IQR)
- Build gap detection & backfill
- New crate: `janus-data-quality`

---

## Phase 2: ML Pipeline with Burn (Weeks 5-8)

### Week 5: Burn Framework Migration
- Add Burn dependencies to workspace
- Create `janus-burn-core` foundation
- Port training loop from Candle to Burn
- Implement checkpointing

### Week 6: Vision Pipeline (GAF + ViViT)
- Port DiffGAF to Burn (learnable normalization)
- Implement GAF video generation
- Port ViViT with factorized attention
- Benchmark vs Candle implementation

### Week 7: LTN & Neuro-Symbolic Fusion
- Port LTN predicates to Burn tensors
- Implement trading axioms (wash sale, risk limits)
- Create Gated Cross-Attention fusion
- New crate: `janus-fusion`

### Week 8: Training Pipeline & Memory
- Implement SWR (Sharp Wave Ripple) sampling
- Add importance sampling correction
- Schema consolidation with Qdrant
- Model versioning system

---

## Phase 3: Signal Generation (Weeks 9-12)

### Week 9: Neuromorphic Core Integration
- Wire brain regions to BrainBus
- Implement Basal Ganglia dual-pathway action selection
- Add Amygdala circuit breakers
- Cerebellum execution planning

### Week 10: Forward Service
- Real-time GAF generation
- ViViT inference pipeline
- LTN constraint checking
- Signal output format & validation

### Week 11: Backward Service & CNS Expansion
- Nightly consolidation job
- Weekly retraining pipeline
- Expand CNS to 101 metrics
- Grafana dashboards & alerting

### Week 12: Integration & Documentation
- End-to-end integration tests
- Performance benchmarking
- API documentation
- Operator runbook

---

## New Crates Summary

| Crate | Purpose |
|-------|---------|
| `janus-exchanges` | Unified exchange adapters |
| `janus-sentiment` | News & sentiment analysis |
| `janus-storage` | Storage abstraction |
| `janus-data-quality` | Validation & cleaning |
| `janus-burn-core` | Burn ML foundation |
| `janus-fusion` | Multimodal fusion |

---

## CNS Metrics by Category

| Category | Count |
|----------|-------|
| System | 4 |
| Data Ingestion | 9 |
| News & Sentiment | 6 |
| Storage | 5 |
| Data Quality | 8 |
| ML Training | 10 |
| Vision Pipeline | 5 |
| LTN & Symbolic | 5 |
| Memory & Replay | 9 |
| Neuromorphic | 9 |
| Forward Service | 7 |
| Backward Service | 7 |
| Dependencies | 9 |
| Circuit Breakers | 3 |
| Resources | 5 |
| **Total** | **101** |

---

## Performance Targets

| Metric | Target |
|--------|--------|
| GAF Generation (32x32) | < 1ms |
| ViViT Inference | < 5ms |
| Full Pipeline p50 | < 8ms |
| Full Pipeline p99 | < 15ms |
| Throughput | > 1000 signals/sec |
| Memory (active) | < 2GB |

---

## Key Dependencies to Add

```toml
# Burn ML Framework
burn = { version = "0.14", features = ["train", "autodiff", "metrics"] }
burn-core = "0.14"
burn-tensor = "0.14"
burn-autodiff = "0.14"
burn-train = "0.14"
burn-ndarray = "0.14"
burn-wgpu = { version = "0.14", optional = true }
```

---

## Architecture Principles

1. **Signal Generation Only** - No direct execution
2. **Rust-Only** - All components in Rust with Burn
3. **Neuromorphic Design** - Brain-inspired architecture
4. **Neuro-Symbolic** - Neural + LTN constraints
5. **Observable** - Comprehensive CNS metrics
6. **Modular** - Independent deployment

---

## Success Criteria

- [ ] 6 exchanges streaming reliably
- [ ] Data quality > 95%
- [ ] Inference p99 < 30ms
- [ ] LTN satisfaction > 90%
- [ ] System health > 0.9
- [ ] Zero critical alerts in normal operation

---

## Quick Start After Implementation

```bash
# Build
cargo build --workspace --release

# Run unified JANUS
./target/release/janus

# Check health
curl http://localhost:8080/health

# View metrics
curl http://localhost:9090/metrics

# Grafana dashboards
open http://localhost:3000
```

---

*Full details in: `JANUS_12_WEEK_ROADMAP.md`*