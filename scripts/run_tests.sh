#!/bin/bash

# Test runner script for fks trading bot

echo "=================================="
echo "Running Test Suite"
echo "=================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install test dependencies if needed
echo "Checking test dependencies..."
pip install -q pytest pytest-cov pytest-asyncio pytest-mock faker

echo ""
echo "=================================="
echo "Running All Tests"
echo "=================================="
echo ""

# Run tests with coverage
pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

TEST_EXIT_CODE=$?

echo ""
echo "=================================="
echo "Test Results Summary"
echo "=================================="
echo ""

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
    echo ""
    echo "Coverage report generated in htmlcov/index.html"
else
    echo "❌ Some tests failed!"
    echo ""
    echo "Please review the test output above for details."
fi

echo ""
echo "=================================="
echo "Test Categories"
echo "=================================="
echo ""
echo "Run specific test categories:"
echo "  pytest tests/ -v -m unit           # Unit tests only"
echo "  pytest tests/ -v -m integration    # Integration tests only"
echo "  pytest tests/ -v -m \"not slow\"     # Skip slow tests"
echo ""
echo "Run specific test files:"
echo "  pytest tests/test_backtest.py -v      # Backtest tests"
echo "  pytest tests/test_database.py -v      # Database tests"
echo "  pytest tests/test_signals.py -v       # Signal tests"
echo "  pytest tests/test_data.py -v          # Data fetching tests"
echo "  pytest tests/test_ml_models.py -v     # ML model tests"
echo "  pytest tests/test_daily_trading_engine.py -v  # Trading engine tests"
echo ""

exit $TEST_EXIT_CODE
