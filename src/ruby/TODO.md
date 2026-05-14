# ruby — TODO

> **Repo (future):** `github.com/nuniesmith/ruby`
> **Today's path:** `fks-full/src/ruby/`
> **Last synced:** 2026-05-14

---

## P0 — Codebase Health

- [ ] `pyproject.toml` — Consider removing `psycopg2-binary` if fully migrated to psycopg3
- [ ] Audit `data/api/` for any remaining endpoints without JSON variants (SVK-17 remaining items)

---

## P1 — Asset Registry

- [ ] Store registry config in Redis (`fks:asset_registry`) with file-based fallback in `infrastructure/config/` — currently in-memory only
- [ ] Make registry editable via WebUI settings page (REG-A remaining)

---

## P1 — Data Factory

### FACTORY-A: Continuous Health & Verification
- [ ] Add Redis pub/sub notifications when gaps are detected or backfills complete
- [ ] Ensure BackfillManager respects API rate limits for all providers
- [ ] Add alerting (via Alertmanager) when data gaps exceed threshold (>1 hour missing)

### FACTORY-C: Crypto Data Expansion
- [ ] Add Kraken OHLC (1m/5m/15m/1h) to factory provider config: BTC, ETH, SOL
- [ ] Run backfill: `python backfill_kraken_crypto.py --days 730 --symbols BTC,ETH,SOL,...` (requires live stack)
- [ ] Add Binance public API as secondary crypto source
- [ ] Add crypto session windows to training config
- [ ] Verify data quality: compare Kraken vs Binance prices

---

## P1 — Module Registry (MOD-A through MOD-E)

> This is the foundational work that enables the modular framework. Zero refactor of existing logic — thin wrappers only.

- [ ] **MOD-A:** Create `src/core/module_registry.py` — `ModuleCategory`, `ModuleManifest`, `FKSModule` ABC, `ModuleRegistry` singleton, `ModuleLoader` (auto-discovers `__fks_module__` sentinel)
- [ ] **MOD-A:** Create `src/core/module_runner.py` — `ModuleRunner` lifecycle, per-instance state, Redis pub/sub output, health tracking
- [ ] **MOD-B:** Wrap 5 indicators (pilot): `indicators.ema`, `indicators.rsi`, `indicators.vwap`, `indicators.atr`, `indicators.bbands`
- [ ] **MOD-B:** Wrap 5 analyzers (pilot): `analysis.ict`, `analysis.cvd`, `analysis.volatility`, `analysis.confluence`, `analysis.signal_quality`
- [ ] **MOD-B:** Add `__fks_module__ = XxxModule` sentinel to each wrapped file
- [ ] **MOD-B:** Unit tests: `tests/test_module_registry.py` — loader discovers all 10 pilots, manifests valid, `run_once()` returns expected keys
- [ ] **MOD-C:** HTTP API routes: `GET /api/modules`, `GET /api/modules/{id}`, `GET /api/modules/{id}/config-schema`, `POST /api/modules/{id}/run`, `GET /api/modules/health`, `GET /api/modules/categories`
- [ ] **MOD-C:** Wire `ModuleLoader.discover_all()` into Ruby app lifespan startup
- [ ] **MOD-C:** Publish registry snapshot to Redis `fks:module:registry` on startup
- [ ] **MOD-D (after pilot):** Wrap remaining indicators, analyzers, strategies, data providers, models, risk modules
- [ ] **MOD-E:** `ModulePipeline` class — ordered execution, per-module config, Redis storage, `BotSupervisor` wiring

---

## P1 — FUTURES-MERGE: Strip HTMX from futures container

- [ ] **FMERGE-A:** Create `src/futures/src/api/` — JSON-only FastAPI app; remove all `TemplateResponse`, Jinja2, HTMLResponse; copy business logic from `web/app.py`
- [ ] **FMERGE-A:** Create route files: `workers.py`, `signals.py`, `trades.py`, `pnl.py`, `cnn.py`, `reports.py`, `tasks.py`, `health.py`
- [ ] **FMERGE-A:** Update `supervisor.py` to start `api.main` instead of `web.app`
- [ ] **FMERGE-A:** Delete `src/futures/src/web/` (all templates, static, Jinja2 code)
- [ ] **FMERGE-C:** Add `/api/futures/*` proxy endpoints to Ruby data service API using `httpx.AsyncClient`
- [ ] **FMERGE-C:** Add `FUTURES_API_URL=http://fks_ruby:8080` to ruby service env
- [ ] **FMERGE-C:** Write tests: `tests/test_futures_proxy.py`

---

## P1 — Multi-Account & Routing

- [ ] **ACCT-B:** Create `src/services/data/api/accounts.py` — exchange account CRUD: `GET/POST /api/accounts`, `GET/PATCH/DELETE /api/accounts/{id}`, `POST /api/accounts/{id}/test`, `GET /api/accounts/{id}/balance`
- [ ] **ACCT-B:** Credential storage: `credentials_ref` = env var name, not value. Write key to `.env` as `ACCT_{UUID}_API_KEY`, store ref.
- [ ] **ACCT-C:** Add routing endpoints: `GET/PUT /api/routing`, `GET /api/routing/{symbol}`, `POST /api/routing/preview`
- [ ] **ACCT-C:** Update `AlertmanagerSignalMonitor` / `ExecutionGate` to read routing from Postgres instead of hardcoded `account_type`
- [ ] **ACCT-D:** Create `src/services/profit_sweep.py` — `ProfitSweepService`, `check_and_sweep()` (scheduler), `execute_sweep()`
- [ ] **ACCT-D:** Add sweep endpoints: `POST/GET /api/accounts/sweep-config`, `POST /api/accounts/sweep/run`
- [ ] **ACCT-D:** Wire into scheduler (`src/services/scheduler.py`)
- [ ] **ACCT-D:** Tests: `tests/test_profit_sweep.py`

---

## P1 — Training

### TRAIN-C: Initial Crypto Model Training
- [ ] Run training: `POST /train` with `{"symbols": ["BTC","ETH","SOL"], "train_mode": "per_group"}` (requires live stack + backfilled data)
- [ ] Compare accuracy against 93.5% CME baseline — expect ≥80% for crypto-majors
- [ ] Run bracket sweep for crypto-specific optimal brackets

### TRAIN-D: Live Sim Validation
- [ ] Create `JanusAIBot` sim sessions for BTC, ETH, SOL
- [ ] Run 7-14 days with real Kraken data
- [ ] Track every signal/fill/outcome in `janus_memories`
- [ ] Compare sim results vs backtest expectations

---

## P1 — Janus Integration (Ruby side)

### JFLOW-A (remaining)
- [ ] Test in paper trading before any live capital

### JFLOW-B
- [ ] Janus startup config overlay from Redis: Janus reads `fks:janus:config` at startup — requires `janus-core/config.rs` change (deferred to fks-janus)

### JFLOW-C
- [ ] Ruby displays Janus guidance in the Trading workspace: take-profit / stop-adjust suggestions from amygdala
- [ ] All feedback stored as execution memories for learning

### JFLOW-D
- [ ] Full Postgres bootstrap path in Rust: query `janus_memories` directly at startup (deferred to fks-janus)

---

## P1 — Kraken Spot Portfolio

- [ ] Live test with real Kraken credentials — run dry-run first (`KRAKEN_API_KEY` + `KRAKEN_API_SECRET` must be set)

---

## P1 — Janus AI Session (remaining)

- [ ] Session metrics: wire from signal pipeline (JFLOW-A) to call `POST .../metrics` endpoint — deferred until live signal pipeline test

---

## P2 — Nice-to-Have

- [ ] `pyproject.toml` — Track `apalis` 1.0 stable (Janus side) to remove vendored fork
- [ ] DOM / Positions / Paper Trading: native Svelte rebuild (replace iframes) — deferred to fks-web
- [ ] OSS-B: OpenViking RAG context DB — evaluate vs current brute-force vector search in RC
- [ ] OSS-E: MiroFish sentiment simulation — stand up offline stack, create FastAPI bridge

---

## P3 — Future

- [ ] Tax Reporting (Canada) — capital gains ACB, CSV export
- [ ] multi-exchange: crypto.com API integration
- [ ] multi-exchange: Netcoins (Canadian) balance + on/off ramp
- [ ] BOT-C: crypto.com futures bot integration
