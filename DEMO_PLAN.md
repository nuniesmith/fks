# FKS Trading Platform - Working Demo Plan

**Goal**: Functional local demo that generates real trading signals, displays them in UI, and provides basic RAG intelligence.

**Timeline**: 4 weeks @ 10-20 hrs/week = 40-80 total hours  
**Current Reality**: 69 passing tests (41%), Docker runs, but core features stubbed  
**Demo Definition**: 
- ✅ Generate signals from Yahoo Finance (BTC, ETH via `yfin.py`)
- ✅ Display signals in Bootstrap UI (`signals.html`)
- ✅ RAG provides simple risk assessment
- ✅ Celery tasks actually execute (not stubs)
- ✅ 80%+ test coverage, all tests passing

---

## Phase 1: Stabilization & Security (Weeks 1-2; 16-20 hrs)
**Milestone**: Clean local environment, no import errors, secure credentials

### Week 1: Security & Dependencies (8-10 hrs)

#### Task 1.1: Security Hardening (4 hrs; CRITICAL)
**Files**: `.env.example`, `docker-compose.yml`, `src/web/django/settings.py`

**Steps**:
1. Generate secure passwords (2 hrs)
   ```bash
   # Create .env.example with placeholders
   cp .env .env.backup
   
   # Generate strong passwords
   python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))" >> .env.new
   python3 -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_urlsafe(32))" >> .env.new
   python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))" >> .env.new
   python3 -c "import secrets; print('PGADMIN_PASSWORD=' + secrets.token_urlsafe(32))" >> .env.new
   
   # Move to .env
   mv .env.new .env
   ```

2. Configure django-axes (1 hr)
   ```python
   # src/web/django/settings.py
   INSTALLED_APPS += ['axes']
   MIDDLEWARE += ['axes.middleware.AxesMiddleware']
   AUTHENTICATION_BACKENDS = [
       'axes.backends.AxesStandaloneBackend',
       'django.contrib.auth.backends.ModelBackend',
   ]
   AXES_FAILURE_LIMIT = 5
   AXES_COOLOFF_TIME = 1  # 1 hour
   ```

3. Enable rate limiting (1 hr)
   ```python
   # src/api/middleware/rate_limiter/middleware.py
   # Apply to trading routes
   # Test with curl
   ```

4. Security audit (30 min)
   ```bash
   pip-audit --requirement requirements.txt > security-audit.txt
   # Fix vulnerabilities
   ```

**Validation**: 
- `docker-compose up` with new passwords
- `curl` API endpoints → rate limited
- No pip-audit critical issues

**Output**: 
- `.env` with strong passwords (gitignored)
- `.env.example` with placeholders (committed)
- `security-audit.txt` report

---

#### Task 1.2: Import Cleanup (4-6 hrs; HIGH PRIORITY)
**Files**: 50+ files with legacy imports

**Steps**:
1. Map all legacy imports (1 hr)
   ```bash
   grep -r "from config import" src/ > legacy-imports.txt
   grep -r "from shared_python" src/ >> legacy-imports.txt
   ```

2. Create migration script (2 hrs)
   ```python
   # scripts/fix_imports.py
   import os
   import re
   
   REPLACEMENTS = {
       'from config import': 'from framework.config.constants import',
       'from shared_python': 'from framework',
       # Add all mappings
   }
   
   # Bulk replace with validation
   ```

3. Run migration + tests (2 hrs)
   ```bash
   python scripts/fix_imports.py
   docker-compose exec web pytest tests/unit/ -v
   # Fix any new errors
   ```

4. Remove empty files (30 min)
   ```bash
   find src/ -type f -size 0 -delete
   find src/ -name "*.py" -size -100c  # Review small files
   ```

**Validation**:
- All 100+ unit tests passing
- No import errors in logs
- `python manage.py check` passes

**Output**:
- Fixed imports across codebase
- Deleted 25+ empty placeholder files
- Test pass rate → 100%

---

### Week 2: Environment & Foundation (8-10 hrs)

#### Task 1.3: Database Migrations (2 hrs)
**Files**: `src/*/migrations/`

**Steps**:
1. Review existing migrations
2. Create missing migrations for all models
   ```bash
   docker-compose exec web python manage.py makemigrations
   docker-compose exec web python manage.py migrate
   ```
3. Add fixtures for test data
   ```python
   # tests/fixtures/test_data.json
   # Sample signals, strategies, etc.
   ```

**Validation**: 
- `python manage.py showmigrations` all applied
- Test database loads fixtures

---

#### Task 1.4: Dependency Resolution (2 hrs)
**Files**: `requirements.txt`, `requirements.dev.txt`

**Steps**:
1. Pin all versions (avoid conflicts)
   ```bash
   pip freeze > requirements.lock
   # Review torch/langchain compatibility
   ```
2. Separate concerns
   ```
   requirements.txt     # Production (no dev tools)
   requirements.dev.txt # Local dev (existing, no GPU)
   requirements.gpu.txt # GPU/RAG (existing)
   requirements.test.txt # Testing (pytest, coverage)
   ```

**Validation**: 
- Fresh venv installs without errors
- CI uses correct requirements

---

## Phase 2: Core Trading Logic (Weeks 3-4; 24-30 hrs)
**Milestone**: Generate real signals, display in UI, basic RAG

### Week 3: Signal Generation (12-15 hrs)

#### Task 2.1: Implement Yahoo Finance Adapter (4 hrs)
**Files**: `src/data/adapters/yfin.py`, `src/trading/tasks.py`

**Steps**:
1. Complete `yfin.py` (2 hrs)
   ```python
   # src/data/adapters/yfin.py
   import yfinance as yf
   
   class YFinanceAdapter:
       def fetch_candles(self, symbol, interval='1d', period='30d'):
           ticker = yf.Ticker(symbol)
           df = ticker.history(period=period, interval=interval)
           return self._normalize(df)
   ```

2. Write tests (1 hr)
   ```python
   # tests/unit/test_data/test_yfin.py
   def test_fetch_btc_candles():
       adapter = YFinanceAdapter()
       candles = adapter.fetch_candles('BTC-USD')
       assert len(candles) > 0
   ```

3. Implement Celery task (1 hr)
   ```python
   # src/trading/tasks.py
   @shared_task
   def sync_market_data(symbol='BTC-USD'):
       adapter = YFinanceAdapter()
       candles = adapter.fetch_candles(symbol)
       # Save to database
   ```

**Validation**:
- `pytest tests/unit/test_data/test_yfin.py` passes
- Celery task runs: `docker-compose exec web celery -A web.django call trading.tasks.sync_market_data`

---

#### Task 2.2: Signal Generator Implementation (5 hrs)
**Files**: `src/trading/signals/generator.py`, `src/trading/tasks.py`

**Steps**:
1. Implement RSI/MACD calculators (2 hrs)
   ```python
   # src/trading/indicators/calculations.py
   def calculate_rsi(prices, period=14):
       # Actual implementation (not stub)
   ```

2. Complete signal generator (2 hrs)
   ```python
   # src/trading/signals/generator.py
   class SignalGenerator:
       def generate(self, candles):
           rsi = calculate_rsi(candles['close'])
           macd = calculate_macd(candles['close'])
           # Generate buy/sell signals
   ```

3. Celery task for signal generation (1 hr)
   ```python
   @shared_task
   def generate_signals(symbol='BTC-USD'):
       candles = fetch_latest_candles(symbol)
       signals = SignalGenerator().generate(candles)
       # Save to database
   ```

**Validation**:
- Unit tests for indicators
- Integration test: fetch data → generate signal
- Signal appears in database

---

#### Task 2.3: Beat Schedule (1 hr)
**Files**: `src/web/django/celery.py`

**Steps**:
```python
# Uncomment beat schedule
beat_schedule = {
    'sync-btc-data': {
        'task': 'trading.tasks.sync_market_data',
        'schedule': crontab(minute='*/15'),  # Every 15 min
        'args': ('BTC-USD',)
    },
    'generate-signals': {
        'task': 'trading.tasks.generate_signals',
        'schedule': crontab(minute='*/30'),
        'args': ('BTC-USD',)
    },
}
```

**Validation**:
- `docker-compose up -d celery_beat`
- Signals generated automatically
- Check Flower UI: http://localhost:5555

---

### Week 4: UI & RAG (12-15 hrs)

#### Task 2.4: Signals Dashboard (4 hrs)
**Files**: `src/web/templates/signals.html`, `src/web/views.py`

**Steps**:
1. Create view (1 hr)
   ```python
   # src/web/views.py
   def signals_dashboard(request):
       signals = Signal.objects.filter(
           created_at__gte=timezone.now() - timedelta(days=7)
       ).order_by('-created_at')
       return render(request, 'signals.html', {'signals': signals})
   ```

2. Update template (2 hrs)
   ```html
   <!-- src/web/templates/signals.html -->
   <table class="table">
     {% for signal in signals %}
     <tr class="{{ signal.action }}">
       <td>{{ signal.symbol }}</td>
       <td>{{ signal.action }}</td>
       <td>{{ signal.confidence }}</td>
     </tr>
     {% endfor %}
   </table>
   ```

3. Add charts (1 hr)
   - Chart.js for price + signals visualization

**Validation**:
- Visit http://localhost:8000/signals
- See real BTC signals from last 7 days

---

#### Task 2.5: Basic RAG Implementation (6 hrs)
**Files**: `src/web/rag/intelligence.py`, `src/web/rag/ingestion.py`

**Steps**:
1. Complete document processor (2 hrs)
   ```python
   # src/web/rag/ingestion.py
   def ingest_signal(signal):
       chunks = chunk_signal_data(signal)
       embeddings = embed_chunks(chunks)
       store_in_pgvector(embeddings)
   ```

2. Implement retrieval (2 hrs)
   ```python
   # src/web/rag/retrieval.py
   def query_similar_signals(symbol, limit=5):
       query_embedding = embed_query(f"Recent {symbol} signals")
       similar = pgvector_search(query_embedding, limit)
       return similar
   ```

3. Intelligence orchestrator (2 hrs)
   ```python
   # src/web/rag/intelligence.py
   def assess_risk(signal):
       similar = query_similar_signals(signal.symbol)
       # Simple risk score based on historical accuracy
       return {'risk': 'low', 'confidence': 0.75}
   ```

**Validation**:
- Generate signal → auto-ingested to RAG
- Query RAG for risk assessment
- Display in UI

---

#### Task 2.6: Integration Testing (2 hrs)
**Files**: `tests/integration/test_demo_flow.py`

**Steps**:
```python
def test_full_demo_flow():
    # 1. Sync data
    sync_market_data('BTC-USD')
    
    # 2. Generate signal
    signal = generate_signals('BTC-USD')
    assert signal.action in ['buy', 'sell', 'hold']
    
    # 3. RAG assessment
    risk = assess_risk(signal)
    assert 'risk' in risk
    
    # 4. UI displays
    response = client.get('/signals')
    assert signal.symbol in response.content.decode()
```

**Validation**: Full test passes end-to-end

---

## Weekly Checkpoints

**Every Monday** (30 min):
1. Run `scripts/analyze_codebase.sh`
2. Update `PROJECT_STATUS.md` with metrics
3. Review Kanban board (move completed tasks)
4. Pick 3-5 tasks for the week

**Metrics to Track**:
- Test coverage % (target: 80%+)
- Import errors (target: 0)
- Empty files (target: 0)
- Security issues (target: 0 critical)
- Demo functionality (% complete)

---

## Definition of Done (Demo Complete)

✅ **Security**: 
- Strong passwords in `.env` (gitignored)
- Rate limiting active
- No critical pip-audit issues

✅ **Data Pipeline**:
- Yahoo Finance fetches BTC/ETH data every 15 min
- Stored in TimescaleDB hypertables

✅ **Signal Generation**:
- RSI/MACD indicators working
- Signals generated every 30 min
- Visible in Celery Flower

✅ **UI**:
- Dashboard shows last 7 days of signals
- Chart.js visualization of price + signals
- Responsive Bootstrap design

✅ **RAG**:
- Signals auto-ingested to pgvector
- Risk assessment query returns results
- Displayed in UI alongside signals

✅ **Testing**:
- 100 unit tests passing
- 10 integration tests passing
- 80%+ coverage overall

✅ **Documentation**:
- `README.md` updated with demo instructions
- `PROJECT_STATUS.md` reflects actual state
- No "TODO" comments in core files

---

## Anti-Patterns to Avoid

❌ **Don't**: Document aspirational features as complete  
✅ **Do**: Mark stubs clearly, track in issues

❌ **Don't**: Assume migrations "should have been done"  
✅ **Do**: Run `makemigrations` and verify

❌ **Don't**: Leave empty files "for later"  
✅ **Do**: Delete now, recreate when needed

❌ **Don't**: Use default/weak passwords  
✅ **Do**: Generate strong ones upfront

❌ **Don't**: Build all features at once  
✅ **Do**: One working vertical slice (BTC → signal → UI)

---

## Success Criteria

**Week 2 End**: `docker-compose up` runs clean, all tests pass  
**Week 4 End**: Visit `http://localhost:8000/signals` → see live BTC signals with RAG risk scores

**Demo Script** (5 min):
1. Start services: `make up`
2. Open dashboard: `http://localhost:8000/signals`
3. Show live BTC signals (auto-updating)
4. Click signal → see RAG risk assessment
5. Open Flower: `http://localhost:5555` → Celery tasks running
6. Run tests: `make test` → 100% passing

That's the working demo! 🎉
