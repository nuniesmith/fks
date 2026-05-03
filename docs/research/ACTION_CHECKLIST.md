# JANUS Project - Immediate Action Checklist

**Date**: January 2025  
**Purpose**: Prioritized tasks for Weeks 3-6 (Research Phase 1)  
**Goal**: ICAIF 2025 paper submission with honest minimal approach

---

## 🚨 CRITICAL DECISIONS NEEDED (This Week)

### Decision 1: Research Paper Strategy
**Owner**: Research Lead  
**Deadline**: End of Week 3

- [ ] **Option A: Minimal Honest Approach** (RECOMMENDED)
  - Timeline: 6 weeks → ICAIF 2025 (July)
  - Implementation: Basic GAF + simple RL
  - Risk: Lower, achievable
  - Acceptance probability: 60-70%

- [ ] **Option B: Full Neuromorphic**
  - Timeline: 16 weeks → AAAI 2026 (August)
  - Implementation: DiffGAF + ViViT + LTN + OpAL
  - Risk: Higher, integration challenges
  - Acceptance probability: 70-80% (if successful)

**DECISION**: ___________________________

---

### Decision 2: Budget Approval
**Owner**: Project Sponsor  
**Deadline**: Immediately

- [ ] Approve **$500** for Binance historical data (BTC/ETH/SOL 2022-2024)
- [ ] Approve **$400** for GPU cluster (4× A100, 2 weeks)
- [ ] Approve **$100** for cloud services backup
- [ ] Confirm engineer availability (ML, Quant, Systems)

**APPROVED**: YES / NO  
**DATE**: ___________________________

---

## 📋 WEEK 3: Data Acquisition & Setup

### Data Team (40 hours)
**Owner**: Quant Researcher  
**Deadline**: Friday Week 3

- [ ] **Purchase Binance API Credits** ($500)
  - Account: ___________________________
  - Confirmation: ___________________________

- [ ] **Download Historical Data**
  - [ ] BTC/USDT (1-minute candles, 2022-01-01 to 2024-12-31)
  - [ ] ETH/USDT (1-minute candles, 2022-01-01 to 2024-12-31)
  - [ ] SOL/USDT (1-minute candles, 2022-01-01 to 2024-12-31)
  - Expected size: ~450 MB per pair (compressed)
  - Download time: ~30 minutes per pair (rate limited)

- [ ] **Data Quality Validation**
  - [ ] Check for missing timestamps (gaps)
  - [ ] Identify outliers (price spikes, zero volumes)
  - [ ] Validate OHLC consistency (H≥O,C; L≤O,C)
  - [ ] Remove duplicates
  - [ ] Document quality metrics

- [ ] **Create Train/Val/Test Splits**
  - [ ] Training: 2022-01-01 to 2023-06-30 (60%, 18 months)
  - [ ] Validation: 2023-07-01 to 2023-12-31 (20%, 6 months)
  - [ ] Test: 2024-01-01 to 2024-12-31 (20%, 12 months)
  - Save as: `data/btcusdt_train.parquet`, etc.

- [ ] **Feature Engineering Pipeline**
  - [ ] Returns (log, simple)
  - [ ] SMA (20, 50, 200)
  - [ ] Bollinger Bands (20, 2σ)
  - [ ] RSI (14)
  - [ ] Volume features (VWAP, OBV)
  - Save as: `data/btcusdt_features.parquet`

**Deliverable**: Clean data files ready for backtesting

---

### Infrastructure Team (20 hours)
**Owner**: Systems Engineer  
**Deadline**: Friday Week 3

- [ ] **Reserve GPU Cluster**
  - Platform: ___________________________ (Internal/AWS/GCP)
  - Configuration: 4× NVIDIA A100 (80GB VRAM)
  - Duration: 2 weeks (Week 3-4)
  - Cost: $400 (~200 GPU-hours @ $2/hr)
  - Reservation ID: ___________________________

- [ ] **Setup Experiment Tracking**
  - [ ] Install Weights & Biases (or MLflow)
  - [ ] Create project: `janus-research`
  - [ ] Configure logging (metrics, artifacts, code)
  - [ ] Test run with dummy data

- [ ] **Configure Distributed Training**
  - [ ] PyTorch DistributedDataParallel setup
  - [ ] Multi-GPU data loading
  - [ ] Gradient accumulation config
  - [ ] Mixed precision (AMP) enabled

- [ ] **Cloud Backup (AWS)**
  - [ ] Reserve p4d.24xlarge instance (if cluster fails)
  - [ ] Estimate cost: $32/hr × 48 hours = $1,536
  - [ ] Budget approval for backup: YES / NO

**Deliverable**: GPU infrastructure ready, experiment tracking operational

---

## 📋 WEEK 4: Baseline Implementations

### ML Team (60 hours)
**Owner**: ML Engineer  
**Deadline**: Friday Week 4

- [ ] **Baseline 1: Buy-and-Hold**
  - [ ] Implement in `experiments/baselines/strategies.py`
  - [ ] Buy at start, hold until end
  - [ ] Expected Sharpe: ~1.0 (crypto historical)
  - Test on: BTC 2022-2024

- [ ] **Baseline 2: SMA Crossover**
  - [ ] Fast SMA: 20 periods
  - [ ] Slow SMA: 50 periods
  - [ ] Buy: fast > slow, Sell: fast < slow
  - [ ] Expected Sharpe: 0.8-1.2
  - Test on: BTC 2022-2024

- [ ] **Baseline 3: Bollinger Bands Mean Reversion**
  - [ ] Period: 20, Num Std: 2.0
  - [ ] Buy: price < lower band
  - [ ] Sell: price > middle band
  - [ ] Expected Sharpe: 0.6-1.0
  - Test on: BTC 2022-2024

- [ ] **Baseline 4: Deep Q-Network (DQN)**
  - [ ] Architecture: 3-layer MLP (256-128-64)
  - [ ] Input: 10 features (price, returns, volume, position, cash)
  - [ ] Actions: BUY (0), HOLD (1), SELL (2)
  - [ ] Training: Experience replay, epsilon-greedy (ε=0.1→0.01)
  - [ ] Expected Sharpe: 1.0-1.5
  - Test on: BTC 2022-2024

- [ ] **Backtesting Framework Validation**
  - [ ] Test on small data sample (1 week)
  - [ ] Verify zero-lookahead (Temporal Fortress)
  - [ ] Check commission/slippage calculation
  - [ ] Confirm position tracking accuracy

- [ ] **Run Full Backtests**
  - [ ] All 4 strategies × 3 pairs (BTC, ETH, SOL)
  - [ ] Save results: `experiments/results/baselines_v1/`
  - [ ] Generate equity curves (CSV)
  - [ ] Calculate performance metrics (JSON)

**Deliverable**: 4 baseline strategies backtested, results ready for comparison

---

### Analysis Team (20 hours)
**Owner**: Quant Researcher  
**Deadline**: Friday Week 4

- [ ] **Performance Metrics Calculation**
  - [ ] Total return, Annualized return
  - [ ] Sharpe ratio, Sortino ratio
  - [ ] Maximum drawdown
  - [ ] Win rate, Profit factor
  - [ ] Average win/loss
  - [ ] Skewness, Kurtosis, VaR, CVaR

- [ ] **Statistical Significance Tests**
  - [ ] Paired t-test (all strategy pairs)
  - [ ] Null hypothesis: No difference in returns
  - [ ] Alternative: Strategy A > Strategy B
  - [ ] Calculate p-values (target: p < 0.05)
  - [ ] Bootstrap confidence intervals (95%)

- [ ] **Regime Analysis**
  - [ ] Bull market: 2023 Q3-Q4, 2024 Q3-Q4
  - [ ] Bear market: 2022 Q1-Q4
  - [ ] Sideways: 2024 Q1-Q2
  - [ ] Performance breakdown per regime

- [ ] **Comparison Table Generation**
  - [ ] All strategies side-by-side
  - [ ] Highlight best performer (bold)
  - [ ] Statistical significance markers (*, **, ***)

**Deliverable**: Statistical analysis complete, comparison table ready

---

## 📋 WEEK 5: Minimal JANUS Implementation

### ML Team (40 hours)
**Owner**: ML Engineer  
**Deadline**: Friday Week 5

**NOTE**: If Option A chosen, implement MINIMAL version only

- [ ] **Basic GAF Encoding** (Non-Differentiable)
  - [ ] Use existing `src/janus/crates/vision/src/gaf.rs`
  - [ ] Window size: 60 (as per HYPERPARAMETERS.md)
  - [ ] Resolution: 224×224
  - [ ] No learnable parameters (fixed normalization)
  - Test: Encode 1-minute BTC data

- [ ] **Feature Extraction** (Simple)
  - [ ] Skip ViViT transformer (not in minimal version)
  - [ ] Use simple CNN or flatten GAF to 1D
  - [ ] Output: 128-dim embedding
  - Compare to: Raw price features

- [ ] **Simple RL Integration**
  - [ ] Reuse DQN from Baseline 4
  - [ ] Replace raw features with GAF embeddings
  - [ ] Keep same architecture (256-128-64)
  - [ ] Train on same data

- [ ] **JANUS-Minimal Backtest**
  - [ ] Run on BTC/ETH/SOL (2022-2024)
  - [ ] Compare to all 4 baselines
  - [ ] Target: Beat Buy-and-Hold (Sharpe > 1.0)
  - [ ] Statistical test vs. DQN baseline

**Deliverable**: JANUS-Minimal results ready for paper

---

## 📋 WEEK 6: Paper Drafting & Visualization

### Writing Team (30 hours)
**Owner**: Research Lead + ML Engineer  
**Deadline**: Friday Week 6

- [ ] **Populate EMPIRICAL_VALIDATION_TEMPLATE.md**
  - [ ] Section 3: Baseline Strategies (copy results)
  - [ ] Section 4: Performance Metrics (all 15 metrics)
  - [ ] Section 5: Results by Regime (bull/bear/sideways)
  - [ ] Section 7: Statistical Significance (p-values, t-tests)
  - [ ] Section 8: Failure Cases (worst drawdowns)
  - [ ] Section 9: Computational Performance (latency, costs)

- [ ] **Generate Visualizations** (20 figures total)
  - [ ] Fig 1-4: Equity curves (all strategies)
  - [ ] Fig 5-7: Return distributions (histograms)
  - [ ] Fig 8-10: Drawdown charts (underwater plots)
  - [ ] Fig 11-13: Rolling Sharpe (90-day window)
  - [ ] Fig 14-16: Performance bars (multi-metric)
  - [ ] Fig 17-19: Regime analysis (bull/bear/sideways)
  - [ ] Fig 20: Architecture diagram (neuromorphic brain)

- [ ] **Code Repository Cleanup**
  - [ ] Create `experiments/` README
  - [ ] Add Jupyter notebooks (minimal examples)
  - [ ] Document reproduction steps
  - [ ] Setup CI/CD (GitHub Actions)
  - [ ] Tag release: `v0.1.0-research`

- [ ] **Write Paper Sections**
  - [ ] Abstract (200 words)
  - [ ] Introduction (1-2 pages)
  - [ ] Related Work (1 page)
  - [ ] Methodology (2-3 pages) - Copy from EMPIRICAL template
  - [ ] Results (3-4 pages) - Populated with real data
  - [ ] Discussion (1-2 pages) - Limitations, future work
  - [ ] Conclusion (0.5 page)
  - [ ] References (52 from BIBLIOGRAPHY.md)

- [ ] **Honesty Section** (CRITICAL)
  - [ ] "Implementation Status" subsection
  - [ ] Clearly state: "This work validates the GAF+RL approach. Full neuromorphic components (ViViT, LTN, OpAL) are under development."
  - [ ] Future Work: Detail Phase 2-3 roadmap
  - [ ] Code Availability: "Infrastructure code public, neuromorphic modules in progress"

**Deliverable**: ICAIF 2025 paper draft ready for review

---

## 📋 Post-Week 6: Submission & Iteration

### Final Steps
**Owner**: Research Lead  
**Deadline**: ICAIF Deadline (July 2025)

- [ ] **Internal Review**
  - [ ] Co-author feedback (if applicable)
  - [ ] Proofreading (grammar, typos)
  - [ ] Figure quality check (300 DPI minimum)
  - [ ] Citation format validation (IEEE)

- [ ] **ICAIF Submission**
  - [ ] Create camera-ready PDF
  - [ ] Upload to submission portal
  - [ ] Submit supplementary materials (code, data)
  - [ ] Confirm receipt

- [ ] **Backup Plans**
  - [ ] If rejected: Revise for AAAI 2026 (August deadline)
  - [ ] ArXiv preprint (immediate, no deadline)
  - [ ] Workshop submission (NeurIPS, ICML)

---

## ⚠️ Risk Mitigation

### If Baselines Outperform JANUS-Minimal

**Scenario**: Simple DQN beats GAF-based approach

**Response**:
1. **Focus on visualization contribution**
   - GAF transformation as interpretable representation
   - UMAP manifold visualization
   - Architecture innovation (neuromorphic design)

2. **Adjust paper narrative**
   - Title: "Visualizing Neuromorphic Trading Systems: Design and Framework"
   - Contribution: Methodology, not performance
   - Future work: Full implementation in progress

3. **Publish as position paper**
   - Target workshop instead of main conference
   - Emphasize architecture and future vision

### If GPU Cluster Denied

**Scenario**: Cannot get 4× A100 reservation

**Response**:
1. **AWS Backup** (p4d.24xlarge)
   - Cost: $32/hr × 48 hours = $1,536
   - Budget approval required
   - Or use smaller instance (p3.8xlarge @ $12/hr)

2. **Extend timeline**
   - Use local GPUs (slower)
   - Run experiments sequentially
   - Accept 2-week delay

3. **Reduce scope**
   - Test on BTC only (not ETH/SOL)
   - Shorter time window (2023-2024 only)
   - Fewer baseline variations

---

## 📊 Success Criteria

### Week 3 Success
- [x] Data downloaded (BTC/ETH/SOL, 2022-2024)
- [x] GPU cluster reserved
- [x] Experiment tracking operational

### Week 4 Success
- [x] 4 baselines implemented and tested
- [x] Statistical analysis complete
- [x] Comparison table generated

### Week 5 Success
- [x] JANUS-Minimal backtest complete
- [x] Sharpe > 1.0 (beats market)
- [x] Visualization framework ready

### Week 6 Success
- [x] Paper draft complete (80%+)
- [x] 20 figures generated
- [x] Code repository public

### ICAIF Submission Success
- [x] Paper submitted on time
- [x] Supplementary materials included
- [x] No plagiarism/format violations

---

## 📞 Communication Plan

### Daily Standups (15 min)
**Time**: 10:00 AM  
**Attendees**: Research Lead, ML Engineer, Quant, Systems

**Format**:
1. Yesterday's progress (2 min each)
2. Today's goals (2 min each)
3. Blockers (5 min total)

### Weekly Reports (Fridays)
**Owner**: Research Lead  
**Distribution**: Stakeholders, Sponsors

**Format**:
1. Accomplishments this week
2. Next week's goals
3. Risks and mitigation
4. Budget status

### Slack Channels
- **#janus-research**: Daily updates, quick questions
- **#janus-results**: Share plots, experimental results
- **#janus-blockers**: Escalate urgent issues

---

## 🎯 Final Checklist (Before ICAIF Submission)

- [ ] All data acquired and validated
- [ ] All baselines tested (4 strategies × 3 pairs)
- [ ] JANUS-Minimal implemented and tested
- [ ] Statistical significance confirmed (p < 0.05 preferred, < 0.1 acceptable)
- [ ] 20 visualizations generated (300 DPI, publication-quality)
- [ ] EMPIRICAL_VALIDATION_TEMPLATE.md fully populated
- [ ] Paper draft complete (all sections)
- [ ] Honest implementation status disclosed
- [ ] Code repository public and documented
- [ ] Internal review complete
- [ ] Citations validated (52 references)
- [ ] Figures/tables numbered and captioned
- [ ] Abstract finalized (200 words max)
- [ ] Supplementary materials prepared
- [ ] PDF camera-ready (IEEE format)
- [ ] ArXiv preprint submitted (backup)
- [ ] ICAIF portal submission confirmed

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Status**: Ready for execution  
**Next Review**: End of Week 3 (after Decision 1 & 2)

---

**Related Documents**:
- [Gap Analysis](JANUS_IMPLEMENTATION_GAP_ANALYSIS.md)
- [Status Summary](IMPLEMENTATION_STATUS_SUMMARY.md)
- [Research Status](VISUALIZATION_RESEARCH_STATUS.md)
- [Roadmap](VISUALIZATION_MISSING_PIECES_ROADMAP.md)