# JANUS 24-Week Quick Reference Guide

**Version:** 2.0  
**Last Updated:** 2024  
**Status:** Week 4 Day 3 Complete (99.2% tests passing)

---

## 📍 Current Position

**Week 4, Day 3:** ML Models Complete ✅  
**Next:** Training Infrastructure (Day 4-5)  
**Tests:** 123/124 passing (99.2%)  
**Blockers:** None

---

## Phase Overview

| Phase | Weeks | Focus | Status |
|-------|-------|-------|--------|
| **Phase 1** | 1-4 | Data Foundation | 🟢 75% Complete |
| **Phase 2** | 5-8 | ML Pipeline (Burn) | 🟡 25% Complete |
| **Phase 3** | 9-12 | Signal Generation | ⚪ Not Started |
| **Phase 4** | 13-15 | Real Data Integration | ⚪ Not Started |
| **Phase 5** | 16-18 | Production ML | ⚪ Not Started |
| **Phase 6** | 19-21 | Execution Engine | ⚪ Not Started |
| **Phase 7** | 22-24 | Production Ops | ⚪ Not Started |

---

## Week-by-Week Objectives

### Phase 1: Foundation (Weeks 1-4) 🟢

#### Week 1: Data Ingestion ✅ COMPLETE
**Deliverables:**
- [x] Exchange websockets (Binance, Bybit, Coinbase)
- [x] Market data normalization
- [x] Gap detection & backfill
- [x] QuestDB integration
- [x] Data quality metrics

**Tests:** 31/31 passing  
**Key Crates:** `exchanges`, `gap-detection`, `questdb-writer`

---

#### Week 2: News & Alternative Data ✅ COMPLETE
**Deliverables:**
- [x] RSS feed aggregation (20+ sources)
- [x] Sentiment analysis (DistilBERT)
- [x] Entity extraction (crypto, exchanges)
- [x] Fear & Greed index
- [x] Whale alerts

**Tests:** 35/35 passing  
**Key Crates:** `sentiment`

---

#### Week 3: Storage & Configuration ✅ COMPLETE
**Deliverables:**
- [x] QuestDB schema optimization
- [x] Asset configuration system
- [x] Per-asset data rules
- [x] Retention policies
- [x] Storage API

**Key Files:** `config/assets/*.toml`, QuestDB schemas

---

#### Week 4: Data Quality Pipeline 🟡 IN PROGRESS
**Deliverables:**
- [x] Validators (timestamp, range, duplicate, sequence)
- [x] Anomaly detectors (z-score, spike, cross-exchange)
- [x] Quality metrics & reporting
- [x] LSTM & MLP models (57/58 tests)
- [ ] Training infrastructure 👈 CURRENT TASK
- [ ] Dataset abstraction
- [ ] Checkpoint management

**Tests:** 123/124 passing (99.2%)  
**Key Crates:** `data-quality`, `ml`  
**Estimate:** 8-12 hours remaining

**Next Steps:**
1. Implement `Dataset` trait with batch iterator
2. Build training loop with autodiff
3. Fix weight serialization (Burn Record API)
4. Add gradient clipping integration
5. Learning rate scheduling + early stopping

---

### Phase 2: ML Pipeline (Weeks 5-8) 🟡

#### Week 5: Burn Framework Deep Integration
**Deliverables:**
- [ ] DiffGAF with learnable normalization
- [ ] Fix arccos boundary conditions (epsilon clamping)
- [ ] CUDA backend integration (Burn 0.20+)
- [ ] WGPU fallback for development
- [ ] Mixed precision support (FP16/BF16)
- [ ] Distributed training (multi-GPU)

**Key Implementation:**
```rust
// Fix gradient explosion at arccos boundaries
let phi = x_norm.clamp(-0.999, 0.999).acos();
```

**Tests Target:** 80+  
**Performance Target:** <10ms GAF generation

---

#### Week 6: Vision Pipeline (GAF + ViViT)
**Deliverables:**
- [ ] Tubelet embedding (3D convolution)
- [ ] Factorized spacetime attention
- [ ] Spatial & temporal transformers
- [ ] Tensor choreography optimization
- [ ] Data augmentation pipeline

**Tests Target:** 100+  
**Performance Target:** <20ms ViViT inference (p95)

---

#### Week 7: Logic Tensor Networks (LTN)
**Deliverables:**
- [ ] Łukasiewicz T-norm operators
- [ ] Product T-norm (smooth gradients)
- [ ] Predicate networks
- [ ] 5+ trading axioms
- [ ] Gated cross-attention fusion

**Key Fix:**
```rust
// Use product T-norm for smooth gradients
impl<B: Backend> TNorm<B> for ProductTNorm {
    fn and(&self, a: Tensor<B, 1>, b: Tensor<B, 1>) -> Tensor<B, 1> {
        a * b  // Always has gradient
    }
}
```

**Tests Target:** 120+

---

#### Week 8: Training Pipeline & Memory
**Deliverables:**
- [ ] Prioritized Experience Replay (lock-free SumTree)
- [ ] Elastic Weight Consolidation (EWC)
- [ ] Parametric UMAP (fast-umap crate)
- [ ] Schema clustering (DBSCAN)
- [ ] Qdrant integration
- [ ] Backward service scaffolding

**Tests Target:** 140+  
**Key Addition:** Catastrophic forgetting prevention via EWC

---

### Phase 3: Signal Generation (Weeks 9-12) ⚪

#### Week 9: Neuromorphic Core Integration
**Deliverables:**
- [ ] Basal Ganglia (direct/indirect pathways)
- [ ] Hypothalamus (PID controller for risk)
- [ ] Amygdala (conformal prediction outlier detection)
- [ ] BrainBus message passing (flume channels)
- [ ] Action selection validated

**Tests Target:** 160+

---

#### Week 10: Backtest Infrastructure
**Deliverables:**
- [ ] L2 order book simulator
- [ ] Slippage & latency modeling
- [ ] PnL tracking (realized/unrealized)
- [ ] Performance analytics (Sharpe, Sortino, max DD)
- [ ] Backtest report generation

**Tests Target:** 180+  
**Key Addition:** Realistic execution simulation

---

#### Week 11: Forward Service
**Deliverables:**
- [ ] Async inference service (tokio)
- [ ] Model loading & hot reload
- [ ] Batch inference optimization
- [ ] Signal emission (Kafka/Redis)
- [ ] Latency optimization

**Tests Target:** 200+  
**Performance Target:** <50ms p99 inference latency

---

#### Week 12: Backward Service & CNS
**Deliverables:**
- [ ] Cron-based consolidation & retraining
- [ ] Schema UMAP clustering
- [ ] Model checkpoint versioning
- [ ] 100+ Prometheus metrics
- [ ] 5+ Grafana dashboards
- [ ] Alerting rules

**Tests Target:** 220+  
**Milestone:** Research system complete, backtest-validated

---

### Phase 4: Real Data Integration (Weeks 13-15) ⚪

#### Week 13: Live Exchange Integration
**Deliverables:**
- [ ] Production websocket clients (auth, rate limiting)
- [ ] Exponential backoff reconnection
- [ ] Historical data backfill (REST APIs)
- [ ] API key management (secrets manager)
- [ ] Connection health monitoring

**Tests Target:** 240+  
**Key Metric:** `janus_exchange_websocket_connected{exchange}`

---

#### Week 14: News & Alternative Data Production
**Deliverables:**
- [ ] 20+ RSS sources (CoinDesk, CryptoSlate, etc.)
- [ ] Twitter API v2 streaming
- [ ] Production sentiment analysis (GPU batching)
- [ ] Fear & Greed API
- [ ] Whale Alert integration
- [ ] On-chain metrics (Glassnode/CryptoQuant)

**Tests Target:** 260+

---

#### Week 15: Data Management & Governance
**Deliverables:**
- [ ] QuestDB cluster deployment
- [ ] Automated retention & archival (S3/GCS)
- [ ] Continuous quality monitoring
- [ ] Data catalog & lineage
- [ ] Quality dashboard

**Tests Target:** 280+  
**Milestone:** Production data pipeline operational

---

### Phase 5: Production ML (Weeks 16-18) ⚪

#### Week 16: MLOps Infrastructure
**Deliverables:**
- [ ] Model registry (S3 + PostgreSQL)
- [ ] Versioned checkpoints
- [ ] Model promotion workflow (dev→staging→prod)
- [ ] Experiment tracking (MLflow)
- [ ] Automated retraining triggers
- [ ] Hyperparameter search (Optuna)
- [ ] Data drift detection (KS test)

**Tests Target:** 300+

---

#### Week 17: A/B Testing & Canary Deployments
**Deliverables:**
- [ ] Traffic splitting (champion vs. challenger)
- [ ] Statistical significance testing
- [ ] Automatic rollback on degradation
- [ ] Shadow mode (parallel inference)
- [ ] Shared memory model sync (IPC optimization)
- [ ] Performance comparison dashboard

**Tests Target:** 320+

---

#### Week 18: Model Optimization
**Deliverables:**
- [ ] Model quantization (INT8)
- [ ] ONNX export
- [ ] TensorRT optimization (CUDA)
- [ ] Kernel fusion validation
- [ ] Batch size tuning
- [ ] Memory profiling & optimization

**Tests Target:** 340+  
**Performance Target:** <20ms p95 inference  
**Milestone:** Production ML system complete

---

### Phase 6: Execution Engine (Weeks 19-21) ⚪

#### Week 19: Order Management System (OMS)
**Deliverables:**
- [ ] Order state machine
- [ ] Position tracking
- [ ] Fill management
- [ ] Order routing logic
- [ ] Reconciliation engine
- [ ] Cancel-on-disconnect

**Tests Target:** 360+

---

#### Week 20: Risk Management
**Deliverables:**
- [ ] Position limits (per-asset, portfolio)
- [ ] Drawdown protection
- [ ] Volatility-based sizing
- [ ] Correlation limits
- [ ] Circuit breakers (multi-level)
- [ ] Risk dashboard

**Tests Target:** 380+

---

#### Week 21: Execution Algorithms
**Deliverables:**
- [ ] TWAP (Time-Weighted Average Price)
- [ ] VWAP (Volume-Weighted Average Price)
- [ ] Iceberg orders
- [ ] Smart order routing (SOR)
- [ ] Execution analytics
- [ ] Slippage tracking

**Tests Target:** 400+  
**Milestone:** Execution engine ready for paper trading

---

### Phase 7: Production Ops (Weeks 22-24) ⚪

#### Week 22: Deployment & Infrastructure
**Deliverables:**
- [ ] Kubernetes manifests
- [ ] Helm charts
- [ ] Auto-scaling policies
- [ ] Service mesh (Istio/Linkerd)
- [ ] Secrets management
- [ ] Blue-green deployment
- [ ] Disaster recovery procedures

**Tests Target:** 420+

---

#### Week 23: Monitoring & Alerting
**Deliverables:**
- [ ] Full observability stack
- [ ] Distributed tracing (Jaeger)
- [ ] Log aggregation (Loki)
- [ ] Custom SLIs/SLOs
- [ ] PagerDuty integration
- [ ] Incident response runbooks
- [ ] Performance dashboards

**Tests Target:** 440+

---

#### Week 24: Production Launch
**Deliverables:**
- [ ] Paper trading validation (1 week minimum)
- [ ] Live trading (small capital)
- [ ] Real-time PnL tracking
- [ ] Trade reconciliation
- [ ] Performance reporting
- [ ] Compliance logging
- [ ] Post-mortem analysis tools

**Tests Target:** 460+  
**Milestone:** 🎉 LIVE TRADING SYSTEM OPERATIONAL

---

## Critical Path Milestones

| Week | Milestone | Success Criteria |
|------|-----------|------------------|
| **4** | Training infrastructure complete | Loss decreasing over epochs, 70+ tests |
| **8** | ML pipeline with memory | Full learning system, 140+ tests |
| **12** | Research system validated | Positive backtest results, 220+ tests |
| **15** | Production data flowing | Live market data + news, 280+ tests |
| **18** | Production ML operational | Automated retraining, 340+ tests |
| **21** | Execution engine ready | Paper trading capable, 400+ tests |
| **24** | **LIVE TRADING** | 🚀 Real capital deployed, 460+ tests |

---

## Key Performance Indicators (KPIs)

### Technical KPIs

| Metric | Target | Phase |
|--------|--------|-------|
| Test Coverage | >95% | All |
| GAF Generation | <10ms | Week 5 |
| ViViT Inference | <20ms p95 | Week 6 |
| Forward Service Latency | <50ms p99 | Week 11 |
| Model Training Time | <4 hours | Week 8 |
| Data Ingestion Lag | <100ms | Week 13 |
| Order Execution | <200ms | Week 19 |

### Business KPIs (Post-Launch)

| Metric | Target | Week |
|--------|--------|------|
| Sharpe Ratio | >1.5 | 24+ |
| Max Drawdown | <15% | 24+ |
| Win Rate | >55% | 24+ |
| Uptime | >99.9% | 24+ |
| Data Quality Score | >0.95 | 15+ |

---

## Technology Stack Summary

### Core Languages & Frameworks
- **Rust 1.75+** - Primary language
- **Burn 0.19+** - Deep learning (migrating to 0.20 for CUDA)
- **Tokio** - Async runtime
- **Rayon** - Data parallelism

### ML & Data
- **burn-core, burn-ndarray, burn-autodiff** - Tensor operations
- **burn-wgpu** (dev) / **burn-cuda** (prod) - GPU acceleration
- **fast-umap** - Manifold learning
- **statrs** - Statistics

### Data Storage
- **QuestDB** - Time-series database
- **PostgreSQL** - Relational data (metadata, configs)
- **Qdrant** - Vector database (schemas)
- **Redis** - Caching & pub/sub
- **S3/GCS** - Object storage (models, archives)

### Infrastructure
- **Docker** - Containerization
- **Kubernetes** - Orchestration
- **Prometheus** - Metrics
- **Grafana** - Visualization
- **Jaeger** - Distributed tracing

### External APIs
- **Binance API** - Market data
- **Bybit API** - Market data
- **Coinbase Pro API** - Market data
- **Twitter API v2** - Social sentiment
- **NewsAPI/RSS** - News aggregation
- **Glassnode/CryptoQuant** - On-chain metrics

---

## Crate Structure (Final State)

```
crates/
├── backtest/          # Backtest engine (Week 10)
├── bybit-client/      # Bybit API client (Week 1) ✅
├── cns/               # CNS metrics registry (Week 12)
├── common/            # Shared utilities ✅
├── compliance/        # Regulatory compliance (Week 20)
├── data-quality/      # Quality pipeline (Week 4) ✅
├── dsp/               # Digital signal processing
├── exchanges/         # Exchange connectors (Week 1) ✅
├── gap-detection/     # Sequence gap detection (Week 1) ✅
├── health/            # Health checks ✅
├── indicators/        # Technical indicators ✅
├── logic/             # Logic tensor networks (Week 7)
├── ltn/               # LTN implementation (Week 7)
├── memory/            # Experience replay (Week 8)
├── ml/                # ML models & training (Week 4-6) 🟡
├── models/            # Domain models ✅
├── proto/             # Protocol buffers
├── questdb-writer/    # QuestDB client (Week 1) ✅
├── rate-limiter/      # API rate limiting ✅
├── risk/              # Risk management (Week 20)
├── sentiment/         # Sentiment analysis (Week 2) ✅
├── strategies/        # Trading strategies
├── training/          # Training orchestration (Week 8)
└── vision/            # Vision pipeline (Week 6)

services/
├── forward/           # Janus Bifrons (Week 11)
├── backward/          # Janus Consivius (Week 12)
├── data-ingestion/    # Data pipeline (Week 1) ✅
├── news/              # News service (Week 2) ✅
├── execution/         # Order execution (Week 19-21)
└── monitoring/        # Observability (Week 23)
```

**Legend:**
- ✅ Complete
- 🟡 In Progress
- (No marker) = Planned

---

## Resource Requirements

### Development Environment
- **CPU:** 8+ cores recommended
- **RAM:** 32GB minimum, 64GB recommended
- **GPU:** NVIDIA GPU with 8GB+ VRAM (RTX 2070 or better)
- **Storage:** 500GB+ SSD
- **OS:** Linux (Ubuntu 22.04+) or WSL2

### Production Environment
- **Compute:** 4x GPU instances (A100 or V100)
- **Memory:** 256GB+ RAM per node
- **Storage:** 10TB+ for historical data
- **Network:** 10Gbps low-latency
- **Database:** QuestDB cluster (3 nodes)

### External Services
- **Exchange APIs:** API keys for 3+ exchanges
- **News APIs:** NewsAPI, Twitter API v2
- **Cloud Storage:** AWS S3 or GCS (1TB+)
- **Monitoring:** Grafana Cloud or self-hosted

---

## Risk Mitigation

### Technical Risks

| Risk | Mitigation | Week |
|------|------------|------|
| Gradient explosion in DiffGAF | Epsilon clamping on arccos | 5 |
| Catastrophic forgetting | Elastic Weight Consolidation | 8 |
| Burn 0.19 gradient API limits | Adaptive LR scaling workaround | 4 ✅ |
| WGPU driver issues in WSL2 | Migrate to Burn CUDA backend | 5 |
| Model deployment downtime | Hot reload + canary deployments | 17 |
| Exchange API rate limits | Token bucket + exponential backoff | 13 |

### Operational Risks

| Risk | Mitigation | Week |
|------|------------|------|
| Data quality degradation | Continuous monitoring + alerting | 15 |
| Model performance drift | Automated retraining triggers | 16 |
| System downtime | Blue-green deployment + DR | 22 |
| Capital loss | Multi-level circuit breakers | 20 |
| Compliance violations | Audit logging + automated checks | 20 |

---

## Success Criteria

### Phase 1 (Week 4)
- ✅ 99%+ test coverage on data pipeline
- ✅ Models implemented and validated
- [ ] Training loop functional with decreasing loss

### Phase 2 (Week 8)
- [ ] DiffGAF + ViViT operational
- [ ] LTN constraints enforced
- [ ] EWC preventing forgetting
- [ ] 140+ tests passing

### Phase 3 (Week 12)
- [ ] End-to-end signal generation
- [ ] Positive backtest results (Sharpe >1.0)
- [ ] Full CNS observability
- [ ] 220+ tests passing

### Phase 4 (Week 15)
- [ ] Live data from 3+ exchanges
- [ ] News sentiment integrated
- [ ] Data quality score >0.95
- [ ] 280+ tests passing

### Phase 5 (Week 18)
- [ ] Automated retraining operational
- [ ] A/B testing validated
- [ ] <20ms inference latency
- [ ] 340+ tests passing

### Phase 6 (Week 21)
- [ ] Paper trading successful (1 week+)
- [ ] Risk limits enforced
- [ ] Execution analytics complete
- [ ] 400+ tests passing

### Phase 7 (Week 24)
- [ ] 🎉 Live trading operational
- [ ] 99.9%+ uptime
- [ ] Real PnL tracking
- [ ] Compliance validated
- [ ] 460+ tests passing

---

## Quick Commands

### Development
```bash
# Build workspace
cargo build

# Run ML crate tests
cargo test --package janus-ml

# Run specific example
cargo run --example gradient_clipping_demo

# Format + lint
cargo fmt && cargo clippy -- -D warnings

# Run with GPU backend
cargo run --features gpu

# Generate documentation
cargo doc --open
```

### Testing
```bash
# All tests
cargo test

# Specific crate
cargo test --package janus-data-quality

# With logging
RUST_LOG=debug cargo test

# Integration tests
cargo test --test integration

# Benchmarks
cargo bench
```

### Deployment
```bash
# Build release
cargo build --release

# Docker build
docker build -t janus-forward:latest .

# Deploy to Kubernetes
kubectl apply -f k8s/

# Check pod status
kubectl get pods -n janus

# View logs
kubectl logs -f deployment/janus-forward -n janus
```

### Operations
```bash
# Access metrics
curl http://localhost:9090/metrics

# Grafana dashboard
open http://localhost:3000

# QuestDB console
open http://localhost:9000

# Qdrant UI
open http://localhost:6333/dashboard
```

---

## Support & Documentation

### Essential Docs
- 📖 **[START_HERE.md](START_HERE.md)** - Project overview
- 📝 **[JANUS_24_WEEK_ROADMAP.md](JANUS_24_WEEK_ROADMAP.md)** - Full roadmap
- 🔍 **[WEEK4_DAY3_COMPLETE.md](WEEK4_DAY3_COMPLETE.md)** - Latest progress
- 💡 **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Commands & snippets
- 🧠 **[Research Review](research_review.md)** - Technical analysis

### API References
- **[Burn Book](https://burn.dev/)** - Burn framework docs
- **[ML Crate README](../crates/ml/README.md)** - Model API
- **[CNS Metrics](../crates/cns/README.md)** - Observability

### Community
- **Issues:** GitHub Issues (bug reports, features)
- **Discussions:** GitHub Discussions (questions, ideas)
- **Contributions:** See CONTRIBUTING.md

---

## Next Session Checklist

Before starting work:

- [ ] Read current week's objectives
- [ ] Review previous week's deliverables
- [ ] Check test status (`cargo test`)
- [ ] Pull latest changes (`git pull`)
- [ ] Create feature branch
- [ ] Set timer for focused work blocks
- [ ] Have documentation open

After finishing:

- [ ] Run all tests
- [ ] Update progress tracking
- [ ] Document blockers/learnings
- [ ] Commit with descriptive message
- [ ] Push to remote
- [ ] Update RESUME_HERE.md

---

**Current Status:** Week 4, Day 3 Complete  
**Next Task:** Training Infrastructure (Dataset + Training Loop)  
**Estimated Time:** 8-12 hours  
**Target:** 70+ tests passing, loss decreasing

**Let's build the future of autonomous trading! 🚀**