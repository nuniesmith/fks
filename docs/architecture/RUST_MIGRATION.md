# RFC: Phasing out Python (Ruby) into a burn-native Rust platform

> **Status:** Draft / proposed — 2026-06-07
> **Goal:** Retire the Python "Ruby" service and run the platform Rust-only,
> with native `burn` ML, by **growing janus into the platform** rather than
> building parallel services.
> **Owner:** @nuniesmith

This is the strategy doc for the "Rust-only" direction. It is deliberately
incremental: the system stays live and trades correctly at every step. Nothing
here is a big-bang rewrite.

> ⚠️ **Some specifics are in flux.** `docker-compose.yml` is being reworked
> (consolidated Ruby container, SvelteKit `webui`, port reshuffle). Pin exact
> ports / container names against the current compose file before acting on a
> phase — this RFC stays at the capability level on purpose.

---

## 0. Decisions locked

| Decision | Choice | Why |
|---|---|---|
| Where the Rust target lives | **Grow janus into it** | janus already does native data ingestion + has real `burn` ML + an axum API. Least new scaffolding. |
| How to reach burn-native ML | **Retrain natively in `burn`** | Reimplement the champion CNNs in `burn`, retrain, parity-test vs PyTorch. Truly burn-native end to end. |
| First deliverable | **This RFC** | Align the plan + parity strategy before writing migration code. |

**Out of scope as hard requirements (kept Python until Rust parity is _proven_):**
Rithmic connectivity, ad-hoc research/HPO. See §9.

---

## 1. Goal & non-goals

**Goal.** A Rust-only runtime where janus owns: market-data ingestion + serving
(the source of truth), feature engineering, the ML models (`burn`-native
training + inference), signal generation, the risk + execution-gate safety
layer, and the supporting APIs. The Python `src/ruby/` service is deleted.

**Non-goals.**
- "100% Rust" as a gate that blocks progress. Keep Python where it is still the
  pragmatic choice behind a clean service boundary (Rithmic) until Rust parity
  is demonstrated, not assumed.
- Rewriting the janus `neuromorphic` crate (~250K LOC, mostly `todo!()` skeleton,
  unused by the live path). Ignore it.
- Reproducing the breakout model's ImageNet-pretrained ResNet18 backbone
  literally (see §8.5 — redesign instead).

---

## 2. Current state — the migration is ~40% done already

The big realization: most of the Rust target already exists inside janus
(~50-crate, ~583K-LOC workspace). The work is **finishing + reconciling**, not
greenfield.

### Already in Rust (verified)

| Capability | Where | State |
|---|---|---|
| Live market-data ingestion | janus `services/data` + `exchange-apiws` 0.7 | ✅ native |
| Time-series writes | `janus-questdb-writer` (direct ILP) | ✅ native, fast |
| Postgres / Redis | janus `services/backward` (`sqlx`), shared state | ✅ native |
| TA / indicators | `indicators-ta` 0.1.5 | ✅ published, replaces Ruby's Python TA |
| Exchange REST/WS | `exchange-apiws` 0.7 | ✅ published |
| Risk sizing / circuit breakers | `rustrade-risk` 0.3 + janus risk manager | ✅ partial |
| Rule-based signals | janus `crates/strategies` (EMAFlip, MeanRev, Squeeze, VWAP, ORB) | ✅ live |
| `burn` ML (LSTM / MLP / DQN + autodiff training) | janus `crates/ml`, `crates/vision` | ✅ real, but **gated off** (`ENABLE_BRAIN_RUNTIME=false`) |
| REST + gRPC API | janus `lib/janus-api` (axum) | ✅ live |

### Still uniquely Ruby's (the actual migration surface)

| Capability | Difficulty | Notes |
|---|---|---|
| Data **factory** (gap-scan → backfill → reconcile, multi-provider) | Medium | The "source of truth" writer; janus has pieces |
| Champion **CNNs** (`PerAssetCNN`, `MasterCNN`, `HybridBreakoutCNN`, ~93.5% CME) | **Hard** | PyTorch `.pt`; different architectures than janus's LSTM/DiffGAF |
| **Execution gate** (9-check chain — the no-autonomous-execution invariant) | Medium-high | Safety-critical; port with exhaustive parity tests |
| Risk engine, correlation guard, journal | Medium | Partial overlap with `rustrade-risk` |
| News/sentiment, on-chain, multi-account routing, dashboards | Medium | Broad but mostly I/O + glue |
| **Rithmic** (CME prop: `async_rithmic`, proprietary mTLS+gRPC, vendored fork) | **Very hard** | No Rust equivalent — the true long-tail blocker |
| pandas/numpy analysis (140+ sites: ICT, CVD, HMM regime) | Hard | → `polars`/`ndarray`, needs golden-vector parity |

Key Ruby reference points: `src/ruby/src/ml/model.py` (CNNs),
`src/ruby/src/services/execution_gate.py` (the gate), the data factory
coordinator, and the 4-process supervisord layout (factory / data / engine / web).

---

## 3. Fix this first: the two-data-paths divergence

The docs say "Ruby is the single source of truth; never add a second data path."
The **code already has two**: janus ingests natively *and* still calls Ruby for
backfill + registry via `services/data/src/backfill/python_data_client.rs` and
`services/registry/`.

**Resolution:** make **janus the canonical source of truth**; the data factory
is the first Ruby subsystem retired. That turns `python_data_client.rs` from
architecture debt into the clean cut-over seam for Phase 1. Until then it is the
Python fallback during shadow-and-diff.

---

## 4. Strategy: strangler-fig + a parity harness

Never rewrite-and-swap. For each capability:

1. **Pin the contract** — snapshot the exact Ruby endpoints/outputs the rest of
   the system depends on (start with what janus + WebUI actually call:
   `/api/bars`, the asset registry, the signals webhook).
2. **Build the Rust side behind the same contract.**
3. **Shadow + diff** — run both; record Python output as golden vectors; assert
   Rust matches (bit-exact for data, tolerance-bounded for ML logits).
4. **Cut over** one consumer at a time; keep Python as fallback until the diff is
   clean for N days.
5. **Delete** the Python piece and its container wiring.

**The parity harness is the project.** Build it in Phase 0 and every later phase
becomes safe and measurable.

---

## 5. The parity harness (Phase 0 deliverable)

A small, reusable framework with three pieces:

- **Recorder** — wraps a running Ruby endpoint (or model) and captures
  `(input, output)` pairs to versioned golden files (`tests/parity/<domain>/*.jsonl`).
  For data: request → JSON body. For ML: feature tensor → logits/label.
- **Asserter** — a Rust test target that replays golden inputs through the Rust
  implementation and diffs:
  - **Exact** for data/serialization (bars, registry, journal rows).
  - **Tolerance-bounded** for floats/ML (`|Δlogit| < 1e-4`, argmax must match).
- **CI gate** — a job that fails the PR if any parity diff regresses. Lives in
  `.github/workflows/` alongside the existing per-workspace Rust checks.

Golden files are committed (small) so parity is reproducible without a live stack.

---

## 6. Phased plan

Each phase ships independently and leaves the system trading correctly.

### Phase 0 — Foundation (1–2 wks)
- Build the parity harness (§5).
- Decide + document the canonical data path (§3).
- Pin the contracts janus/WebUI actually depend on (record golden vectors).
- Pin the *exact* current CNN contract (feature count + class set are version-
  skewed across docs: 15/20/37 features, v8/v9/v10 — resolve to ground truth from
  `src/ruby/src/ml/` and the model `.json` sidecars).
- **Exit:** harness runs in CI; contracts + model metadata captured as goldens.

### Phase 1 — Data layer / source of truth
- Move gap-scan / backfill / reconcile into janus `services/data`; janus becomes
  the QuestDB/Postgres/Redis writer.
- Point Ruby's `/api/bars` consumers (and WebUI) at janus.
- Retire `python_data_client.rs` once the diff is clean.
- **Exit:** janus is the sole data writer; Ruby factory + data API removed from
  compose. *Highest leverage, lowest ML risk — do this first.*

### Phase 2 — burn-native ML inference
- Reimplement `PerAssetCNN` then `MasterCNN` in `janus-ml`; achieve inference
  parity vs the PyTorch champions (§8).
- Flip `ENABLE_BRAIN_RUNTIME=true` once parity holds.
- **Exit:** Rust serves CNN inference at parity; Python inference path removed.

### Phase 3 — Safety + signals
- Port the **execution gate** (all 9 gates) and the risk engine to Rust with
  exhaustive parity tests; preserve the human-confirmation invariant
  (`EXECUTION_MODE=paper_trading` default, never autonomous).
- Promote the Rust strategies to the live signal path.
- **Exit:** order flow gated entirely in Rust; Ruby engine process removed.

### Phase 4 — burn-native training
- Wire janus `services/backward` + Apalis into a real retraining loop (already
  scaffolded: `Trainer`, optimizers, schedulers, replay buffers exist).
- Replace `scripts/train.sh` (PyTorch) with a `burn` training pipeline +
  champion promotion + the `.json` sidecar contract.
- **Exit:** champions are trained in `burn`; the Python `trainer` container +
  PyTorch dependency are gone.

### Phase 5 — The long tail
- News/sentiment, on-chain, journal, dashboards → Rust (mostly I/O + glue).
- **Rithmic stays Python** behind a thin gRPC/HTTP shim — migrated last, or never.
- **Exit:** `src/ruby/` deleted except (optionally) a minimal Rithmic sidecar.

---

## 7. Target architecture (after the migration)

```
            exchange-apiws (WS/REST)        Rithmic sidecar (Python, optional)
                     │                                │ gRPC shim
                     ▼                                ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  janus  (the platform)                                       │
   │   services/data     — ingestion, factory, QuestDB writer     │
   │   crates/ml,vision  — burn-native models (train + inference) │
   │   crates/strategies — signal generation                      │
   │   risk + execution gate — safety layer (human confirm)       │
   │   lib/janus-api     — axum REST + gRPC (the public contract) │
   └───────────────┬─────────────────────────────┬───────────────┘
                   │ QuestDB / Postgres / Redis   │ REST/gRPC
                   ▼                              ▼
            (data stores, unchanged)         WebUI (SvelteKit)
```

Data stores (QuestDB / Postgres / Redis) stay; only the *compute + serving*
moves from Python to Rust.

---

## 8. The burn-native ML track (deep dive)

The headline goal. Approach, smallest-model-first:

### 8.1 Port architectures, not weights, first
`PerAssetCNN` (1-D conv + Squeeze-Excitation, ~47K params) maps cleanly to
`burn::nn` (`Conv1d`, `BatchNorm`, `Linear`, global avg pool). It's small → fast
to validate. Do it first as the reference implementation, then `MasterCNN`.

### 8.2 Golden-vector parity before anything else
Dump ~1,000 `(20×60 input → logits)` pairs from the Python model; assert the
`burn` model reproduces them within tolerance (argmax must match, `|Δlogit| < 1e-4`).
This test *is* "is the migration correct."

### 8.3 Check the existing weight converter
janus has `crates/ml/src/models/convert.rs`. Confirm whether it can lift
PyTorch/`safetensors` weights into `burn` tensors — if so, you can **transfer**
the champion weights for an immediate parity baseline, *then* retrain natively.
(Even though the decision is "retrain in burn," transferring first gives a known-
good oracle to retrain against.)

### 8.4 Port the feature pipeline with its own goldens
The 20-channel features (Hurst, RSI, ATR, book-imbalance, …) → `polars`/`ndarray`
+ `indicators-ta`. Same-input-same-output tests guarantee the model still behaves.
This is where pandas/numpy semantics bite — the harness is mandatory here.

### 8.5 Redesign the breakout model — do NOT literal-port it
`HybridBreakoutCNN` renders candles → 224×224 images → **ImageNet-pretrained
ResNet18** + 37 tabular features. Reproducing a pretrained vision backbone in
`burn` is the worst effort/value trade in the whole plan. Options, best first:
1. Collapse to a pure-tabular / 1-D model on the existing 37 features (drop the
   image path entirely).
2. Use janus's DiffGAF (`crates/vision`) for "time-series → image" if you want to
   keep that idea Rust-natively.
3. (Avoid) literal ResNet18 reimplementation.

### 8.6 Training loop in burn (Phase 4)
`burn-train` covers the needs: AdamW, focal loss, cosine warmup, early stopping,
temperature calibration. The labeler (forward-walk TP/SL) and dataset windowing
are straightforward Rust. janus's `services/backward` already has the scaffolding.

---

## 9. Risk register / blockers

| Risk | Severity | Mitigation |
|---|---|---|
| **Rithmic** proprietary mTLS+gRPC (`async_rithmic`) | 🔴 High | Keep as a thin Python sidecar behind a gRPC shim; migrate last or never |
| **CNN parity** (matching ~93.5%) | 🔴 High | Golden-vector harness + weight-transfer oracle (§8.2–8.3); don't flip the live path until parity holds |
| **pandas/numpy semantics** (140+ sites) | 🟡 Med | Per-feature golden vectors; `polars`/`ndarray`; port analysis incrementally |
| **Execution-gate behavior drift** | 🔴 High | Exhaustive parity tests on the 9-gate chain before cutover; the one bug that costs money |
| **Two data paths during transition** | 🟡 Med | Shadow-and-diff; keep Python fallback until N clean days; then delete |
| **Scope creep** (Ruby is 4 procs / ~30 routers) | 🟡 Med | Strangler-fig; never migrate more than one capability at a time |
| **janus already large** (~583K LOC) | 🟢 Low | Absorb as new crates; keep the neuromorphic skeleton out of the live path |

---

## 10. What stays Python (for now)

- **Rithmic connectivity** — until a Rust path is proven (or indefinitely).
- **Ad-hoc research / HPO (Optuna)** — offline, not in the live runtime.
- Anything where Rust parity is not yet demonstrated. The default is *keep Python
  behind a boundary*, not "rewrite blindly."

---

## 11. Open decisions (not yet locked)

- **Rithmic endgame** — permanent Python sidecar vs. eventual Rust port vs. drop
  CME from scope (crypto-only).
- **Model registry / versioning** — janus has no S3/registry today; champions are
  git-tracked `.pt` + `.json`. Define the `burn` champion-promotion + storage story
  in Phase 4.
- **Breakout model** — confirm the §8.5 redesign vs. keeping a Python sidecar for
  it specifically.
- **WebUI contract** — the SvelteKit `webui` currently consumes Ruby's API shape;
  confirm it can repoint to janus's axum API unchanged, or version the contract.

---

## 12. Immediate next steps

1. **Phase 0, item 1:** scaffold the parity harness (recorder + asserter + CI gate).
2. **Phase 0, item 2:** record goldens for `/api/bars` + the asset registry.
3. **Phase 2 spike (parallel):** reimplement `PerAssetCNN` in `janus-ml` with a
   golden-vector test — proves the burn-native ML path on the smallest model.

---

## 13. References

- `docs/architecture/REPO_TOPOLOGY.md` — the five-repo split + crates.io coordinates.
- `SPLIT_PLAN.md` — repo-split moves (precedent for this kind of staged plan).
- `src/ruby/CLAUDE.md` — the Python service's own map + invariants.
- janus: `crates/ml/` (burn models), `services/data/src/backfill/python_data_client.rs`
  (the cut-over seam), `services/backward/` (training scaffolding).
- `models/README.md` — current champion contract (`.pt` + `.json` sidecar).
