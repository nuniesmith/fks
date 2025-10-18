# FKS Trading Platform - Test Suite Guide

## 📋 Overview

Comprehensive test suite for the FKS Trading Platform covering unit tests, integration tests, and performance benchmarks.

## 🎯 Test Coverage Goals

- **Target**: 80%+ code coverage
- **Execution Time**: &lt;5 minutes for full suite
- **Categories**: Unit, Integration, Performance

## 📂 Test Structure

```
tests/
├── unit/                      # Unit tests with mocks
│   ├── test_api/             # API endpoint tests
│   ├── test_core/            # Core models and database tests
│   ├── test_rag/             # RAG system unit tests (NEW)
│   │   ├── test_document_processor.py
│   │   ├── test_embeddings_mocked.py
│   │   └── test_intelligence_mocked.py
│   └── test_trading/         # Trading logic tests
│
├── integration/               # Integration tests
│   ├── test_backtest/        # Backtesting integration
│   ├── test_celery/          # Celery tasks integration (NEW)
│   │   └── test_tasks.py
│   └── test_data/            # Data adapter integration
│
├── performance/               # Performance benchmarks (NEW)
│   ├── test_rag_performance.py
│   └── test_trading_performance.py
│
├── fixtures/                  # Shared test fixtures
└── conftest.py               # Global pytest configuration
```

## 🧪 Test Categories

### Unit Tests (`@pytest.mark.unit`)
Tests individual functions/classes in isolation with mocked dependencies.

**Examples:**
- Document processor chunking logic
- Embeddings service with mocked models
- RAG intelligence orchestration
- Signal evaluation algorithms

**Run:**
```bash
pytest tests/unit/ -v
pytest tests/unit/ -m unit
```

### Integration Tests (`@pytest.mark.integration`)
Tests interaction between components with real or minimal mocking.

**Examples:**
- Celery task execution and scheduling
- Task retry and failure handling
- Redis integration
- Database operations

**Run:**
```bash
pytest tests/integration/ -v
pytest tests/integration/ -m integration
```

### Performance Tests (`@pytest.mark.benchmark`)
Benchmarks critical paths using pytest-benchmark.

**Examples:**
- RAG query processing time
- Embedding generation speed
- Signal processing throughput
- Backtesting performance

**Run:**
```bash
pytest tests/performance/ -v --benchmark-only
pytest -m benchmark --benchmark-only
```

## 🚀 Running Tests

### Quick Start
```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Fast tests only (skip slow)
pytest tests/ -m "not slow"

# Specific category
pytest tests/unit/test_rag/ -v
pytest -m rag -v
```

### Common Commands

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Performance benchmarks
pytest tests/performance/ --benchmark-only

# Coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Parallel execution (faster)
pytest tests/ -n auto

# Stop on first failure
pytest tests/ -x

# Verbose with full output
pytest tests/ -vv --tb=long

# Specific test file
pytest tests/unit/test_rag/test_intelligence_mocked.py -v

# Specific test function
pytest tests/unit/test_rag/test_intelligence_mocked.py::TestFKSIntelligenceMocked::test_query_basic -v
```

## 📊 Coverage Reports

### Generate HTML Coverage Report
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html  # View in browser
```

### Terminal Coverage Report
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### Check Coverage Threshold
```bash
pytest tests/ --cov=src --cov-fail-under=80
```

## 🎭 Test Markers

Use markers to organize and filter tests:

```python
@pytest.mark.unit
def test_something():
    """Unit test"""
    pass

@pytest.mark.integration
def test_integration():
    """Integration test"""
    pass

@pytest.mark.benchmark
def test_performance(benchmark):
    """Performance benchmark"""
    result = benchmark(my_function, args)
```

Available markers:
- `unit` - Unit tests (isolated, mocked)
- `integration` - Integration tests (real components)
- `benchmark` - Performance tests
- `slow` - Long-running tests
- `rag` - RAG system tests
- `trading` - Trading logic tests
- `api` - API endpoint tests
- `web` - Web interface tests

### Filter by Markers
```bash
# Only unit tests
pytest -m unit

# Only integration tests
pytest -m integration

# Only benchmarks
pytest -m benchmark --benchmark-only

# Exclude slow tests
pytest -m "not slow"

# Multiple markers (unit OR integration)
pytest -m "unit or integration"

# Multiple markers (integration AND NOT slow)
pytest -m "integration and not slow"
```

## 🔧 Fixtures

### Global Fixtures (conftest.py)
- `sample_trading_data` - Sample trading data
- `mock_api_response` - Mock API response
- `django_db_setup` - Django database setup

### RAG Test Fixtures
- `processor` - Document processor instance
- `mock_local_embeddings` - Mocked embeddings model
- `service_with_mocks` - Embeddings service with mocks
- `intelligence_with_mocks` - RAG intelligence with mocks

### Trading Test Fixtures
- `mock_market_data` - Market data samples
- `mock_indicators` - Technical indicators
- `mock_positions` - Portfolio positions

## 📈 Performance Benchmarking

### Basic Benchmark
```python
def test_my_function_performance(benchmark):
    result = benchmark(my_function, arg1, arg2)
    assert result is not None
```

### Benchmark with Setup
```python
def test_with_setup(benchmark):
    def setup():
        return expensive_setup()
    
    result = benchmark.pedantic(
        my_function,
        setup=setup,
        rounds=100
    )
```

### View Benchmark Results
```bash
# Run benchmarks and save results
pytest tests/performance/ --benchmark-only --benchmark-save=baseline

# Compare with previous results
pytest tests/performance/ --benchmark-only --benchmark-compare=baseline

# Generate histogram
pytest tests/performance/ --benchmark-only --benchmark-histogram
```

### Performance Targets

| Operation | Target | Current |
|-----------|--------|---------|
| Document chunking | &lt;10ms | TBD |
| Single embedding | &lt;50ms | TBD |
| Batch embeddings (10) | &lt;200ms | TBD |
| RAG query pipeline | &lt;500ms | TBD |
| Signal generation | &lt;100ms | TBD |
| Portfolio valuation | &lt;50ms | TBD |

## 🐛 Debugging Tests

### Run with Debug Output
```bash
# Show print statements
pytest tests/ -v -s

# Show full traceback
pytest tests/ --tb=long

# Drop into debugger on failure
pytest tests/ --pdb

# Show local variables on failure
pytest tests/ -l
```

### Run Single Test with Debug
```bash
pytest tests/unit/test_rag/test_intelligence_mocked.py::TestFKSIntelligenceMocked::test_query_basic -vv -s
```

## 🔄 Continuous Integration

Tests run automatically on:
- Every push to repository
- Every pull request
- Scheduled nightly builds

CI Configuration: `.github/workflows/ci-cd.yml`

### CI Test Commands
```bash
# Lint
make lint

# Test with coverage
pytest tests/ --cov=src --cov-report=xml

# Generate coverage badge
coverage-badge -o coverage.svg
```

## 📝 Writing New Tests

### Unit Test Template
```python
"""
Unit tests for [component] with mocks.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from module.to.test import ComponentToTest


class TestComponentToTest:
    """Test ComponentToTest in isolation."""

    @pytest.fixture
    def component(self):
        """Create component instance."""
        return ComponentToTest()

    def test_basic_functionality(self, component):
        """Test basic functionality."""
        result = component.method()
        
        assert result is not None
        assert result.property == expected_value
    
    def test_with_mock(self, component):
        """Test with mocked dependency."""
        with patch('module.to.test.Dependency') as mock_dep:
            mock_dep.return_value.method.return_value = 'mocked'
            
            result = component.method_using_dependency()
            
            assert result == 'expected'
            mock_dep.assert_called_once()
```

### Integration Test Template
```python
"""
Integration tests for [component] with real dependencies.
"""
import pytest


@pytest.mark.integration
class TestComponentIntegration:
    """Test component integration."""

    def test_real_interaction(self):
        """Test with real components."""
        # Use real dependencies, minimal mocking
        result = real_component.interact()
        
        assert result is not None
```

### Benchmark Template
```python
"""
Performance tests for [component].
"""
import pytest


@pytest.mark.benchmark
class TestComponentPerformance:
    """Benchmark component operations."""

    def test_operation_performance(self, benchmark):
        """Benchmark operation."""
        result = benchmark(component.operation, args)
        
        assert result is not None
        stats = benchmark.stats.stats
        print(f"Mean: {stats.mean:.6f}s")
```

## 📊 Test Metrics

### Current Status
- ✅ Unit tests: 60+ tests
- ✅ Integration tests: 40+ tests
- ✅ Performance tests: 30+ benchmarks
- 🎯 Coverage: Target 80%+
- ⚡ Execution time: Target &lt;5 minutes

### Test Distribution
- Unit Tests: ~60%
- Integration Tests: ~30%
- Performance Tests: ~10%

## 🔍 Troubleshooting

### Common Issues

**Issue**: Tests fail with `ImportError`
```bash
# Solution: Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
pytest tests/
```

**Issue**: Celery tests skip
```bash
# Solution: Tests skip if broker not available (expected in CI)
# To run locally, start Redis:
docker-compose up -d redis
pytest tests/integration/test_celery/
```

**Issue**: Django configuration errors
```bash
# Solution: Set Django settings
export DJANGO_SETTINGS_MODULE=web.django.settings
pytest tests/
```

**Issue**: Slow test execution
```bash
# Solution: Run in parallel
pip install pytest-xdist
pytest tests/ -n auto
```

## 📚 Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-benchmark Documentation](https://pytest-benchmark.readthedocs.io/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Python Mock Documentation](https://docs.python.org/3/library/unittest.mock.html)

## 🎯 Next Steps

1. **Expand Coverage**: Add tests for remaining modules
2. **Improve Performance**: Optimize slow tests
3. **Add Fixtures**: Create reusable test data
4. **Document Edge Cases**: Add more edge case tests
5. **CI Integration**: Enhance CI/CD pipeline

---

**Last Updated**: October 2025  
**Test Suite Version**: 1.0  
**Coverage Target**: 80%+
