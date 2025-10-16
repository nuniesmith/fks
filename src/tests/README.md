# Test Suite Documentation

This directory contains comprehensive tests for the fks trading bot.

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and configuration
├── test_backtest.py                 # Backtesting engine tests
├── test_database.py                 # Database models and operations tests
├── test_signals.py                  # Trading signals tests
├── test_data.py                     # Data fetching and validation tests
├── test_ml_models.py                # ML models (HMM, LSTM) tests
└── test_daily_trading_engine.py     # Daily trading engine tests
```

## Running Tests

### Run All Tests
```bash
# With coverage report
pytest tests/ -v --cov=src --cov-report=term-missing

# Or use the test runner script
./run_tests.sh
```

### Run Specific Test Files
```bash
# Backtest tests
pytest tests/test_backtest.py -v

# Database tests
pytest tests/test_database.py -v

# Signal tests
pytest tests/test_signals.py -v

# Data tests
pytest tests/test_data.py -v

# ML model tests
pytest tests/test_ml_models.py -v

# Trading engine tests
pytest tests/test_daily_trading_engine.py -v
```

### Run by Category
```bash
# Unit tests only
pytest tests/ -v -m unit

# Integration tests only
pytest tests/ -v -m integration

# Skip slow tests
pytest tests/ -v -m "not slow"
```

### Run Specific Test Functions
```bash
# Run a single test
pytest tests/test_backtest.py::TestBacktest::test_run_backtest_basic -v

# Run tests matching a pattern
pytest tests/ -v -k "test_hmm"
```

## Test Coverage

The test suite covers:

### 1. Backtesting (`test_backtest.py`)
- Basic backtest execution
- Metrics calculation (Sharpe, drawdown, win rate)
- Parameter variations
- Edge cases (empty data, single trade)
- Equity curve length consistency

### 2. Database (`test_database.py`)
- All model CRUD operations
- Foreign key relationships
- Metadata field handling
- Cascade behavior
- Data integrity constraints

### 3. Signals (`test_signals.py`)
- RSI calculation
- MACD calculation
- Signal generation
- No lookahead bias verification
- Trend detection

### 4. Data Fetching (`test_data.py`)
- OHLCV data fetching
- Multiple symbol handling
- Error handling and retries
- Data validation
- Price consistency checks

### 5. ML Models (`test_ml_models.py`)
- HMM regime detection
- LSTM price prediction
- Model training and validation
- Feature preparation
- Model persistence (save/load)
- Trading signal generation

### 6. Daily Trading Engine (`test_daily_trading_engine.py`)
- Position analysis
- Opportunity scanning
- Daily plan generation
- Position sizing
- Stop loss calculation
- Take profit calculation
- Risk management

## Test Fixtures

Common fixtures available in `conftest.py`:

- `test_db_engine`: In-memory SQLite database
- `db_session`: Database session for tests
- `sample_ohlcv_data`: Sample price data (100 days)
- `sample_trades`: Sample trade history
- `sample_account`: Test account in database
- `sample_positions`: Test positions in database
- `sample_strategy`: Strategy configuration
- `mock_exchange`: Mock exchange API
- `sample_market_data`: Multi-symbol market data

## Requirements

Install test dependencies:

```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock faker
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Writing New Tests

### Test Structure
```python
import pytest

class TestYourFeature:
    """Test your feature description"""
    
    @pytest.fixture
    def your_fixture(self):
        """Setup test data"""
        return some_data
    
    def test_basic_functionality(self, your_fixture):
        """Test basic behavior"""
        result = function_under_test(your_fixture)
        assert result == expected_value
    
    def test_edge_cases(self):
        """Test edge cases"""
        with pytest.raises(ValueError):
            function_under_test(invalid_input)
```

### Marking Tests
```python
@pytest.mark.slow
def test_long_running():
    """This test takes a while"""
    pass

@pytest.mark.integration
def test_full_pipeline():
    """This is an integration test"""
    pass

@pytest.mark.unit
def test_single_function():
    """This is a unit test"""
    pass
```

## Continuous Integration

Tests should be run:
- Before committing code
- After fixing bugs
- Before deploying to production
- On every pull request

## Troubleshooting

### Import Errors
If you get import errors, make sure the `src` directory is in your Python path:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
```

### Database Errors
If database tests fail, ensure:
- SQLAlchemy is installed
- Foreign key constraints are correct
- Metadata fields are renamed (not using reserved 'metadata' name)

### ML Test Failures
If ML tests fail:
- Check PyTorch is installed with CUDA support
- Verify hmmlearn and scikit-learn versions
- Some tests are marked as slow and can be skipped

### Missing Dependencies
Install all dependencies:
```bash
pip install -r requirements.txt
```

## Code Coverage

Target coverage: >80%

Generate coverage report:
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

## Known Issues

1. **CUDA Tests**: ML model tests require CUDA. They will be skipped if CUDA is not available.
2. **Long Tests**: Some ML training tests are marked as `@pytest.mark.slow` and can be skipped.
3. **Mock Data**: Tests use mock data, so results may differ from production.

## Future Improvements

- [ ] Add performance benchmarks
- [ ] Add load testing
- [ ] Add end-to-end integration tests
- [ ] Add test for live trading scenarios
- [ ] Add tests for error recovery
- [ ] Add tests for concurrent operations
