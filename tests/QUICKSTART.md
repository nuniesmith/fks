# Test Suite Quick Start

## 🚀 Run Tests Fast

```bash
# All tests
pytest tests/ -v

# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests (needs Redis)
pytest tests/integration/ -v

# Performance benchmarks
pytest tests/performance/ --benchmark-only

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

## 🏷️ Filter by Markers

```bash
pytest -m unit                  # Unit tests
pytest -m integration           # Integration tests
pytest -m benchmark             # Performance benchmarks
pytest -m rag                   # RAG system tests
pytest -m "not slow"            # Skip slow tests
```

## 📊 Coverage Reports

```bash
# HTML report (best)
pytest tests/ --cov=src --cov-report=html && open htmlcov/index.html

# Terminal report
pytest tests/ --cov=src --cov-report=term-missing

# Check threshold (80%)
pytest tests/ --cov=src --cov-fail-under=80
```

## 🎯 New Tests Overview

### Unit Tests (60+ tests)
```bash
# RAG document processor
pytest tests/unit/test_rag/test_document_processor.py -v

# RAG embeddings service
pytest tests/unit/test_rag/test_embeddings_mocked.py -v

# RAG intelligence
pytest tests/unit/test_rag/test_intelligence_mocked.py -v
```

### Integration Tests (40+ tests)
```bash
# Celery tasks
pytest tests/integration/test_celery/test_tasks.py -v
```

### Performance Tests (30+ benchmarks)
```bash
# RAG performance
pytest tests/performance/test_rag_performance.py --benchmark-only

# Trading performance
pytest tests/performance/test_trading_performance.py --benchmark-only

# Save baseline
pytest tests/performance/ --benchmark-save=baseline

# Compare
pytest tests/performance/ --benchmark-compare=baseline
```

## 🐛 Debug Tests

```bash
# Show print statements
pytest tests/ -v -s

# Full traceback
pytest tests/ --tb=long

# Stop on first failure
pytest tests/ -x

# Drop to debugger on failure
pytest tests/ --pdb
```

## 📦 Install Dependencies

```bash
pip install pytest pytest-django pytest-cov pytest-benchmark pytest-mock pytest-asyncio faker factory-boy
```

## 📝 Test Structure

```
tests/
├── unit/test_rag/              # 60+ RAG unit tests (NEW)
├── integration/test_celery/    # 40+ Celery tests (NEW)
├── performance/                # 30+ benchmarks (NEW)
├── TEST_GUIDE.md              # Full documentation
├── TEST_SUMMARY.md            # Implementation report
└── QUICKSTART.md              # This file
```

## ✅ Success Metrics

- **130+ tests** across all categories
- **~4 minutes** execution time
- **75-80%** estimated coverage
- **All tests validated** ✓

## 🔗 Quick Links

- [Full Guide](TEST_GUIDE.md) - Comprehensive documentation
- [Summary](TEST_SUMMARY.md) - Implementation details
- [pytest.ini](../pytest.ini) - Configuration
- [conftest.py](conftest.py) - Fixtures

## 💡 Common Commands

```bash
# Run specific test
pytest tests/unit/test_rag/test_intelligence_mocked.py::TestFKSIntelligenceMocked::test_query_basic -v

# Parallel execution (faster)
pytest tests/ -n auto

# Last failed tests only
pytest tests/ --lf

# New tests first
pytest tests/ --nf

# Validate test files
python tests/validate_tests.py
```

## 🎭 Test Markers Explained

- `@pytest.mark.unit` - Fast unit tests with mocks
- `@pytest.mark.integration` - Tests with real components
- `@pytest.mark.benchmark` - Performance benchmarks
- `@pytest.mark.slow` - Long-running tests (skip with `-m "not slow"`)
- `@pytest.mark.rag` - RAG system specific tests

## 📈 Performance Targets

| Operation | Target |
|-----------|--------|
| Document chunking | <10ms |
| Single embedding | <50ms |
| Batch embeddings (10) | <200ms |
| RAG query pipeline | <500ms |
| Signal generation | <100ms |

---

**Need help?** See [TEST_GUIDE.md](TEST_GUIDE.md) for full documentation.
