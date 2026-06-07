# RFC: Phasing out Python (Ruby) into a burn-native Rust platform

> **Status:** Active — 2026-06-07. **`src/ruby/` has been removed from
> `fks-full`** (see §0.1); the remaining work is finishing the burn-native
> capabilities inside janus.
> **Goal:** Retire the Python "Ruby" service and run the platform Rust-only,
> with native `burn` ML, by **growing janus into the platform** rather than
> building parallel services.
> **Owner:** @nuniesmith

This is the strategy doc for the "Rust-only" direction. It is deliberately
incremental: the system stays live and trades correctly at every step. Nothing
here is a big-bang rewrite.

> ⚠️ **Some specifics are in flux.** Pin exact ports / container names against
> the current compose file before acting on a phase — this RFC stays at the
> capability level on purpose.

---

## 0.1 What changed (2026-06-07): Ruby removed from fks-full

`fks-full` no longer carries the Python trading system. **janus is good enough
for the demo**, so rather than keep the Python service limping behind a service
boundary until the very end (the original Phase 5 ordering), we cut it now and
let the repo become the lean janus-centric orchestrator it's heading toward
(`SPLIT_PLAN.md` Phase 4/5).

**Removed:** `src/ruby/` (the whole Python tree), the `ruby` + `trainer` +
`base` + `venv` compose services (dev + prod), their Dockerfiles, the
ruby/trainer Prometheus jobs + alerts + Grafana dashboards, the `python.yml` CI
workflow, the root `pyproject.toml`, and all the run.sh / `.env.example` wiring.

**Preserved (critical):** the Bot Spawner's `ruby_db` schema —
`bot_configs` / `bot_runs` — was relocated out of `src/ruby/sql/` into
[`src/sql/spawner/`](../../src/sql/spawner/) and the postgres init image now
bakes it from there. The database keeps the `ruby_db` name (env `RUBY_DB`) for
backward compatibility; the spawner is untouched.

**Consequences (now tracked as follow-ups, see §12):** janus ingests market
data natively, so dropping `PYTHON_DATA_SERVICE_URL` is fine; but the WebUI's
data API and the nginx dashboard routes still assume Ruby's contract and need a
janus-native repoint. Those are infrastructure follow-ups, not blockers for the
janus demo.

> **2026-06-07 (later) — dead-artifact sweep.** A follow-up cleanup removed the
> orphaned bits the removal left behind: the Ruby-era training orchestrators
> (`scripts/training/`), the empty `fks.ruby.v1` proto (`proto/fks/ruby/`), the
> dead trainer Grafana dashboard + Jaeger sampler entries (`ruby` + `trainer`) +
> `TRAINER_API_KEY` in `run.sh`, and the dead WebUI `/trainer` iframe route. The
> remaining `fks_ruby` references are the **repoints** in §12-C (nginx ×74,
> `vite.config.ts` ×9, WebUI `ruby_signal` ×10), which are gated on janus serving
> the data contract — see the janus `TODO.md` Track D. `ruby_db` (spawner schema)
> is intentionally kept.

### The burn-native ML track is already substantially built

Since this RFC was first written, the smallest-model-first plan in §8 has largely
landed in **janus `crates/ml`** (behind the gate; nothing live flips without
parity):

| Piece | Where (janus) | State |
|---|---|---|
| `PerAssetCnn` (burn) + raw-f32 reference oracle | `crates/ml/src/models/per_asset_cnn.rs` | ✅ built |
| `MasterCnn` (cross-asset MHA) + risk reference | `crates/ml/src/models/master_cnn.rs` | ✅ built |
| 20-channel feature pipeline (pandas-faithful) | `crates/ml/src/features/per_asset_cnn.rs` | ✅ built |
| Breakout labeler (consolidation→ATR walk-forward) | `crates/ml/src/labeler.rs` | ✅ built |
| Windowed dataset + class weights | `crates/ml/src/per_asset_dataset.rs` | ✅ built |
| Trainable CNN (im2col conv) + `CnnTrainer` (AdamW+CE) | `crates/ml/src/models/trainable_per_asset_cnn.rs` | ✅ built |
| End-to-end `train_champion` (features→labels→train→inference) | `crates/ml/src/train_per_asset.rs` | ✅ built |
| Gated CNN vote at the consensus seam | `services/forward/src/cnn_inference.rs` (`ENABLE_CNN_INFERENCE`, default off) | ✅ wired |

What's **not** yet done on the ML track: the PyTorch→burn **champion goldens**
(needs the user's Python env + the `.pt` weights — the one true parity blocker),
and training polish (cosine schedule / val-split / temperature calibration /
champion save+load + promotion). See §12.

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
- **Status (2026-06-07):** the deletion happened *early* — `src/ruby/` is gone
  from `fks-full` now (§0.1) since janus is good enough for the demo. The
  long-tail features were simply **not carried over**; rebuild the ones you
  actually need as janus crates (or a Rithmic sidecar) rather than porting the
  whole Python surface. This is the strangler-fig's final cut, pulled forward.

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

## 12. Immediate next steps (post-removal follow-ups)

With `src/ruby/` gone (§0.1) and the burn-native ML scaffolding built, the
remaining work splits into **ML parity/polish** (inside janus) and
**infrastructure repoint** (here in fks-full). None of it blocks the janus demo.

### A. ML — finish the burn-native champion (janus `crates/ml`)
1. **Champion goldens (the one real blocker).** In your Python env, dump
   ~1,000 `(20×60 input → logits)` pairs + the champion `.pt` weights; drop them
   into `crates/ml/tests/golden/`. The skip-if-absent parity tests + recorders
   (`janus/tools/parity/`) are already in place and will light up.
2. **Weight transfer oracle** (§8.3) — lift the `.pt` weights into the burn
   `PerAssetCnn` for an immediate known-good baseline, then retrain natively.
3. **Training polish** — cosine LR schedule, train/val split + best-val
   checkpoint, temperature calibration, and champion **save/load + promotion**
   (the `.json` sidecar contract) in `train_per_asset.rs`.
4. **Flip the gate** — only once parity holds, enable `ENABLE_CNN_INFERENCE`
   (then `ENABLE_BRAIN_RUNTIME`) on a shadow basis.

### B. Data layer — make janus the sole source of truth (§3, §6 Phase 1)
5. Move gap-scan / backfill / reconcile into janus `services/data`; retire
   `python_data_client.rs` once janus is the only QuestDB/Postgres/Redis writer.

### C. Infrastructure repoint (fks-full — left dangling by the removal)
6. **WebUI → janus data contract.** The SvelteKit app's `PUBLIC_API_URL` now
   points at janus (`:7000`) but janus doesn't serve Ruby's API shape yet.
   Either version janus's axum API to cover what the dashboard calls, or trim the
   dashboard to janus-native endpoints.
7. **nginx janus-centric rewrite.** `infrastructure/config/nginx/conf.d/*.conf`
   still route `/`, `/api/*`, `/factory/*`, `/trading*`, etc. at `fks_ruby`.
   nginx starts fine (lazy variable upstreams → 502 on those routes), but the
   config needs a rewrite to a janus + spawner + monitoring topology.
8. **Test harness scripts.** `scripts/testing/{monitor-test,run-integration-tests,
   test-signal-pipeline}.sh` still probe `fks_ruby`; update or retire them.
9. **(Optional) rename `ruby_db` → `spawner_db`.** Cosmetic; the spawner is the
   only consumer now. Kept as `ruby_db` for backward compatibility.

### D. Execution-gate + safety (§6 Phase 3)
10. **Port the 9-check execution gate to Rust** with exhaustive parity tests
    before promoting the Rust strategies to the live signal path. Preserve the
    no-autonomous-execution invariant (`EXECUTION_MODE=paper_trading` default).
    - ✅ **Core ported (2026-06-07):** the 9-gate chain + consecutive-loss breaker
      + correlation guard + adaptive threshold now live in janus
      `crates/execution-gate` — a faithful, pure/synchronous port with 36 unit
      tests + doctest, clippy-clean.
    - ⏳ **Remaining:** wire it into `services/forward`'s live loop (advisory →
      enforce behind `JANUS_GATE_ENFORCE`), feed it the producer inputs +
      closed-trade outcomes, add the Redis persistence adapter. Tracked in the
      janus `TODO.md` (Track C).

---

## 13. References

- `docs/architecture/REPO_TOPOLOGY.md` — the five-repo split + crates.io coordinates.
- `SPLIT_PLAN.md` — repo-split moves (precedent for this kind of staged plan).
- The old Python service's map + invariants — now in git history (the commit that
  removed `src/ruby/`) or the `nuniesmith/ruby` repo if it's extracted there.
- janus: `crates/ml/` (burn models — see §0.1 for the built pieces),
  `services/data/src/backfill/python_data_client.rs` (the cut-over seam),
  `services/backward/` (training scaffolding).
- `models/README.md` — current champion contract (`.pt` + `.json` sidecar).
