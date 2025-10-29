# Phase 3: Testing & QA - Comprehensive Test Plan

**Status:** 🚧 **IN PROGRESS**  
**Date:** October 23, 2025  
**Goal:** Achieve 80%+ test coverage with comprehensive integration and unit tests

## Current Test Status

### Existing Test Suite

**Total test files:** 56  
**Test directories:**
- `tests/unit/` - Unit tests for isolated components
- `tests/integration/` - Integration tests for component interactions
- `tests/performance/` - Performance benchmarks
- `tests/fixtures/` - Shared test fixtures

**Test coverage by category:**

| Category | Files | Status | Notes |
|----------|-------|--------|-------|
| Trading Tasks | ✅ tests/unit/test_trading/test_tasks.py | COMPLETE | All 17 tasks tested with mocks |
| Signal Generation | ✅ tests/unit/test_trading/test_signals.py | COMPLETE | RSI, MACD, BB, ATR, SMA, EMA |
| RAG System | ✅ tests/unit/test_rag/ | COMPLETE | Orchestrator, intelligence, embeddings |
| API Endpoints | ✅ tests/unit/test_api/ | COMPLETE | 14 tests passing |
| Backtest Engine | ⚠️ tests/integration/test_backtest/ | PARTIAL | 4 failures (config imports) |
| Data Adapters | ⚠️ tests/integration/test_data/ | PARTIAL | 11 failures (shared_python imports) |
| Core Database | ⚠️ tests/unit/test_core/ | PARTIAL | Import issues to fix |

### Test Markers (pytest.ini)

```ini
markers =
    unit: Unit tests for isolated components
    integration: Integration tests for component interactions
    slow: Tests that take a long time to run
    benchmark: Performance tests using pytest-benchmark
    data: Tests related to data adapters and repositories
    backtest: Tests related to backtesting engine
    trading: Tests related to trading strategies and execution
    api: Tests related to API endpoints
    web: Tests related to web interface
    rag: Tests related to RAG system components
```

## Phase 3 Objectives

### 3.1 Expand Test Coverage (9 hours estimated)

#### High Priority - Phases 1 & 2 (3 hours)

1. **Market Data Sync Tests** (1 hour)
   - [x] Basic sync test (exists in test_tasks.py)
   - [ ] Multi-symbol sync test
   - [ ] Circuit breaker failure handling
   - [ ] Rate limiting behavior
   - [ ] Duplicate prevention validation
   - [ ] SyncStatus tracking verification

2. **Signal Generation Tests** (1.5 hours)
   - [x] RAG-powered signal generation (exists in test_tasks.py)
   - [x] Legacy fallback mechanism (exists in test_tasks.py)
   - [ ] Position sizing calculations
   - [ ] Confidence boosting logic
   - [ ] Multi-symbol signal generation
   - [ ] Discord notification triggers
   - [ ] Technical indicator integration

3. **RAG Integration Tests** (0.5 hours)
   - [x] IntelligenceOrchestrator initialization (exists)
   - [x] Trading recommendation generation (exists)
   - [ ] Portfolio optimization
   - [ ] Daily signals generation
   - [ ] Context building from indicators
   - [ ] Document retrieval

#### Medium Priority - Integration (3 hours)

4. **End-to-End Workflow Tests** (2 hours)
   - [ ] Data sync → Indicator calculation → Signal generation
   - [ ] Signal generation → Position sizing → Risk analysis
   - [ ] RAG query → Recommendation → Notification
   - [ ] Backtest → Strategy validation → Report generation

5. **Celery Task Integration** (1 hour)
   - [ ] Test actual Celery task execution (Docker required)
   - [ ] Beat schedule verification
   - [ ] Task retry behavior
   - [ ] Error handling and logging
   - [ ] Task result persistence

#### Low Priority - Edge Cases (3 hours)

6. **Error Handling & Recovery** (1.5 hours)
   - [ ] Database connection failures
   - [ ] API rate limit exceeded
   - [ ] Circuit breaker open state
   - [ ] Invalid data handling
   - [ ] Concurrent task execution

7. **Performance & Load Tests** (1.5 hours)
   - [ ] Sync 11 symbols under 5 seconds
   - [ ] Signal generation under 15 seconds
   - [ ] RAG query response time < 1 second
   - [ ] Database query optimization
   - [ ] Memory usage under load

### 3.2 CI/CD Setup (3 hours)

1. **GitHub Actions Workflow** (2 hours)
   - [ ] Create `.github/workflows/ci.yml`
   - [ ] Run pytest on push/PR
   - [ ] Code coverage reporting
   - [ ] Docker build validation
   - [ ] Lint checks (ruff, mypy, black)

2. **Test Automation** (1 hour)
   - [ ] Automated test result reporting
   - [ ] Coverage badge generation
   - [ ] Slack/Discord notifications
   - [ ] Performance regression detection

## Test Execution Strategy

### Phase 1: Without Docker (Local Testing)

**Status:** ✅ Can run now

```bash
# Run all unit tests (no Docker required)
pytest tests/unit/ -v -m unit

# Run specific test categories
pytest tests/unit/test_trading/test_tasks.py -v
pytest tests/unit/test_trading/test_signals.py -v
pytest tests/unit/test_rag/ -v

# Run with coverage
pytest tests/unit/ -v --cov=src --cov-report=html
```

**Expected Results:**
- Unit tests: Should pass (mocked dependencies)
- No database required
- No external services required

### Phase 2: With Docker (Integration Testing)

**Status:** ⏳ Requires `make up`

```bash
# Start Docker services
make up

# Run integration tests
docker-compose exec web pytest tests/integration/ -v -m integration

# Run full test suite
docker-compose exec web pytest tests/ -v --cov=src --cov-report=html

# Run slow/benchmark tests
docker-compose exec web pytest tests/ -v -m "benchmark or slow"
```

**Expected Results:**
- All tests should pass
- Database integration works
- Celery tasks execute
- RAG system functional (if GPU stack running)

### Phase 3: CI/CD (Automated Testing)

**Triggers:**
- Every push to main/dev branches
- Every pull request
- Nightly builds (full test suite + benchmarks)

**Actions:**
- Run pytest with coverage
- Build Docker images
- Run lint checks
- Upload coverage reports
- Notify on failures

## Test Coverage Goals

### Current Coverage (Estimated)

Based on existing tests:
- **Trading tasks:** 80% (comprehensive mocking)
- **Signal generation:** 75% (technical indicators covered)
- **RAG system:** 70% (orchestrator + intelligence tests exist)
- **API endpoints:** 85% (14 tests passing)
- **Overall:** ~41% (based on previous run)

### Target Coverage

| Component | Current | Target | Priority |
|-----------|---------|--------|----------|
| Trading tasks | 80% | 90% | High |
| Signal generation | 75% | 85% | High |
| RAG system | 70% | 80% | Medium |
| Data adapters | 40% | 75% | Medium |
| Backtest engine | 50% | 80% | Medium |
| API endpoints | 85% | 90% | Low |
| Web views | 30% | 70% | Low |
| **Overall** | **41%** | **80%** | **High** |

## New Tests to Create

### 1. Market Data Sync Integration Test

**File:** `tests/integration/test_market_sync_integration.py`

```python
@pytest.mark.integration
@pytest.mark.trading
def test_full_market_sync_workflow():
    """Test complete market data sync workflow"""
    # 1. Sync data for all symbols
    result = sync_market_data_task()
    assert result['status'] == 'success'
    
    # 2. Verify data in database
    session = Session()
    for symbol in SYMBOLS:
        count = session.query(OHLCVData).filter_by(symbol=symbol).count()
        assert count > 0
    
    # 3. Check SyncStatus updates
    sync_status = session.query(SyncStatus).filter_by(symbol='BTCUSDT').first()
    assert sync_status.sync_status == 'completed'
    assert sync_status.total_candles > 0
```

### 2. RAG Signal Generation End-to-End Test

**File:** `tests/integration/test_rag_signal_e2e.py`

```python
@pytest.mark.integration
@pytest.mark.rag
@pytest.mark.slow
def test_rag_powered_signal_generation():
    """Test RAG-powered signal generation from data to recommendation"""
    # 1. Sync market data
    sync_market_data_task(symbol='BTCUSDT', limit=100)
    
    # 2. Update indicators
    update_indicators_task(symbol='BTCUSDT')
    
    # 3. Generate RAG signals
    result = generate_signals_task()
    
    assert result['status'] == 'success'
    assert result['method'] == 'rag'
    assert 'suggestions' in result
    assert len(result['suggestions']) > 0
```

### 3. Performance Benchmark Tests

**File:** `tests/performance/test_task_benchmarks.py`

```python
@pytest.mark.benchmark
def test_sync_market_data_performance(benchmark):
    """Benchmark market data sync performance"""
    result = benchmark(sync_market_data_task, symbol='BTCUSDT', limit=500)
    assert result['status'] == 'success'
    # Should complete under 5 seconds
    
@pytest.mark.benchmark  
def test_signal_generation_performance(benchmark):
    """Benchmark signal generation performance"""
    result = benchmark(generate_signals_task)
    assert result['status'] == 'success'
    # Should complete under 15 seconds
```

## GitHub Actions CI Workflow

**File:** `.github/workflows/ci.yml`

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main, dev ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest-cov pytest-benchmark
    
    - name: Run unit tests
      run: |
        pytest tests/unit/ -v --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Run lint checks
      run: |
        ruff check src/
        mypy src/ --ignore-missing-imports
        black --check src/
```

## Test Execution Checklist

### Pre-Testing (Phase 1.2 Fix Required)

- [ ] Fix import errors in tests (20 failing tests)
- [ ] Remove legacy `from config import` patterns
- [ ] Remove `from shared_python import` patterns
- [ ] Update test fixtures for Django patterns
- [ ] Verify all test dependencies installed

### Unit Tests (Can Run Now)

- [x] Trading tasks tests (test_tasks.py) - 17 tasks tested
- [x] Signal generation tests (test_signals.py) - All indicators
- [x] RAG orchestrator tests (test_orchestrator.py)
- [ ] Run full unit test suite: `pytest tests/unit/ -v`
- [ ] Generate coverage report: `pytest tests/unit/ --cov=src --cov-report=html`

### Integration Tests (Docker Required)

- [ ] Start Docker: `make up`
- [ ] Run database migrations: `make migrate`
- [ ] Run integration tests: `docker-compose exec web pytest tests/integration/ -v`
- [ ] Test Celery tasks: Verify tasks execute via Beat schedule
- [ ] Test RAG integration: Verify orchestrator queries work

### Performance Tests

- [ ] Run benchmarks: `pytest tests/performance/ -v -m benchmark`
- [ ] Verify sync performance: < 5 seconds for 11 symbols
- [ ] Verify signal generation: < 15 seconds
- [ ] Verify RAG queries: < 1 second per query

### CI/CD Setup

- [ ] Create `.github/workflows/ci.yml`
- [ ] Test workflow locally with `act` (GitHub Actions emulator)
- [ ] Push to GitHub and verify CI runs
- [ ] Add coverage badge to README
- [ ] Configure notifications (Discord/Slack)

## Success Criteria

### Phase 3 Complete When:

1. ✅ **Test Coverage ≥ 80%** - Measured by pytest-cov
2. ✅ **All Unit Tests Passing** - No failures in tests/unit/
3. ✅ **Integration Tests Passing** - With Docker running
4. ✅ **CI/CD Pipeline Active** - GitHub Actions running on push/PR
5. ✅ **Performance Benchmarks Met** - Tasks complete within targets
6. ✅ **Documentation Complete** - Test docs + CI/CD guide

## Current Blockers

### Phase 1.2 Import Fixes (PRIORITY)

**Status:** ⚠️ Blocking integration tests

**Issue:** 20 tests failing due to legacy imports
- `from config import SYMBOLS` → `from framework.config.constants import SYMBOLS`
- `from shared_python` → Remove entirely, use Django settings

**Fix Strategy:**
1. Update all test files with correct imports
2. Create test fixtures for mocked config
3. Re-run test suite to verify fixes
4. Document new import patterns for tests

### Docker Not Running

**Status:** ⚠️ Blocking integration tests

**Required for:**
- Integration tests
- Celery task execution tests
- Database-dependent tests
- RAG system tests (with GPU stack)

**Action:** Start Docker before Phase 3 integration testing

## Timeline

| Phase | Task | Duration | Status |
|-------|------|----------|--------|
| 3.1a | Fix import errors in tests | 1 hour | ⏳ Not started |
| 3.1b | Expand market sync tests | 1 hour | ⏳ Not started |
| 3.1c | Expand signal generation tests | 1.5 hours | ⏳ Not started |
| 3.1d | RAG integration tests | 0.5 hours | ⏳ Not started |
| 3.1e | End-to-end workflow tests | 2 hours | ⏳ Not started |
| 3.1f | Celery task integration tests | 1 hour | ⏳ Not started |
| 3.1g | Error handling tests | 1.5 hours | ⏳ Not started |
| 3.1h | Performance benchmarks | 1.5 hours | ⏳ Not started |
| 3.2a | GitHub Actions workflow | 2 hours | ⏳ Not started |
| 3.2b | Test automation setup | 1 hour | ⏳ Not started |
| **Total** | | **12 hours** | **0% complete** |

## Next Steps

### Immediate (Can Do Now)

1. **Run existing unit tests** to establish baseline
   ```bash
   pytest tests/unit/test_trading/test_tasks.py -v
   pytest tests/unit/test_trading/test_signals.py -v
   pytest tests/unit/test_rag/ -v
   ```

2. **Generate coverage report** to identify gaps
   ```bash
   pytest tests/unit/ -v --cov=src --cov-report=html
   open htmlcov/index.html  # View coverage
   ```

3. **Fix Phase 1.2 import errors** (blocking integration tests)
   - Update test files with correct imports
   - Remove legacy config/shared_python references

### After Docker Start

4. **Run integration tests**
   ```bash
   make up
   docker-compose exec web pytest tests/integration/ -v
   ```

5. **Test Celery tasks in Docker**
   ```bash
   docker-compose logs -f celery_worker
   # Watch for task executions
   ```

### Future (CI/CD)

6. **Create GitHub Actions workflow**
7. **Set up automated test reporting**
8. **Add performance monitoring**

---

*Phase 3 Test Plan Created: October 23, 2025*  
*Next Update: After running baseline tests*
