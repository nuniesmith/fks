#!/bin/bash
# Fetch market data using Docker container with all dependencies
# Usage: ./scripts/fetch_market_data_docker.sh BTC/USDT 1m 2000

set -e

SYMBOL="${1:-BTC/USDT}"
INTERVAL="${2:-1m}"
LIMIT="${3:-2000}"
SOURCE="${4:-ccxt}"

echo "🚀 Fetching market data via Docker..."
echo "Symbol: $SYMBOL | Interval: $INTERVAL | Limit: $LIMIT | Source: $SOURCE"

# Copy script into container
docker cp scripts/fetch_market_data.py fks_app:/tmp/fetch_market_data.py

# Install dependencies if needed
docker-compose exec fks_app pip install ccxt yfinance 2>&1 | grep -v "Requirement already satisfied" || true

# Run script
docker-compose exec fks_app python /tmp/fetch_market_data.py \
    --symbol "$SYMBOL" \
    --interval "$INTERVAL" \
    --limit "$LIMIT" \
    --source "$SOURCE" \
    --output "/app/data/market_data/latest.json"

# Copy results back
mkdir -p data/market_data
docker cp fks_app:/app/data/market_data/. data/market_data/

echo "✅ Data saved to data/market_data/"
ls -lh data/market_data/
