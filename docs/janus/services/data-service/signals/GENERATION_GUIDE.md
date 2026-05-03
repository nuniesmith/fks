# Signal Generation Guide

**Date:** January 4, 2026  
**Status:** Quick Reference  
**Purpose:** How to generate and view trading signals in FKS

---

## Overview

The FKS Trading Platform automatically generates trading signals using Janus Brain (AI engine). This guide explains how signals are generated, stored, and displayed.

---

## Signal Flow

```
Janus Brain → Generate Signals → Save to Files → Web UI Displays
     ↓              ↓                   ↓              ↓
  AI Model      Task Queue        signals/*.json    Signal Cards
```

---

## How to Generate Signals

### Option 1: Automatic Generation (Recommended)

Signals are automatically generated on a schedule by Janus Brain:
- **Scalp signals**: Every 15 minutes
- **Swing signals**: Every 4 hours
- **Long-term signals**: Once daily

**Status:** Currently in development - auto-scheduling not yet active.

### Option 2: Manual Generation via API

Trigger signal generation manually:

```bash
# Generate swing signals for BTC
curl -X GET "https://fkstrading.xyz/api/signals/generate?category=swing"

# Generate signals for specific symbols
curl -X GET "https://fkstrading.xyz/api/signals/generate?category=scalp&symbols=BTC,ETH,SOL"

# Response:
{
  "task_id": "abc123",
  "status": "queued",
  "message": "Signal generation queued for BTCUSD",
  "category": "swing"
}
```

### Option 3: Manual Generation via Python

```python
from src.tasks.generate_signals import generate_signal_task

# Queue signal generation task
task = generate_signal_task.delay(
    symbol="BTCUSD",
    category="swing",
    strategy=None
)

print(f"Task ID: {task.id}")
```

---

## Signal Storage

### File Location
Signals are stored as JSON files:
```
data/signals/YYYYMMDD/
├── scalp_signals.json
├── swing_signals.json
└── long_term_signals.json
```

### File Format
```json
{
  "signals": [
    {
      "symbol": "BTCUSD",
      "direction": "LONG",
      "entry_price": 45000.00,
      "stop_loss": 44000.00,
      "take_profit_levels": [46000.00, 47000.00, 48000.00],
      "category": "swing",
      "confidence": 85,
      "timestamp": "2026-01-04T14:30:00Z",
      "indicators": {...},
      "metadata": {...}
    }
  ],
  "generated_at": "2026-01-04T14:30:00Z",
  "model_version": "1.0.0"
}
```

---

## Viewing Signals

### Web UI (Recommended)

1. Navigate to: `https://fkstrading.xyz/signals`
2. Select category filter (ALL/SWING/SCALP/DAY)
3. View signal cards with:
   - Symbol & Direction
   - Entry/Stop Loss/Take Profit
   - Confidence score
   - Timestamp

### API Endpoint

```bash
# Get all signals for today
curl "https://fkstrading.xyz/api/signals/from-files"

# Filter by category
curl "https://fkstrading.xyz/api/signals/from-files?category=swing"

# Filter by symbol
curl "https://fkstrading.xyz/api/signals/from-files?symbol=BTCUSD"

# Get specific date
curl "https://fkstrading.xyz/api/signals/from-files?date=20260104"
```

---

## Signal Categories

### Scalp Trading
- **Time Horizon**: 15 minutes - 4 hours
- **Frequency**: Multiple signals per day
- **Risk**: Lower per trade
- **Use Case**: Quick profits from small price movements

### Swing Trading
- **Time Horizon**: 1 day - 2 weeks
- **Frequency**: 1-3 signals per day
- **Risk**: Moderate
- **Use Case**: Capture medium-term trends

### Long-term Trading
- **Time Horizon**: 2 weeks - 3 months
- **Frequency**: 1-2 signals per week
- **Risk**: Higher per trade, lower frequency
- **Use Case**: Major trend following

---

## Manual Demo Trading Workflow

### Step 1: Wait for Signals
- Signals appear automatically when generated
- Check the Signals page regularly
- Set up notifications (future feature)

### Step 2: Evaluate Signal
- Check confidence score (>70% recommended)
- Verify price levels make sense
- Consider market conditions
- Review category time horizon

### Step 3: Execute Trade
1. Open your demo trading platform
2. Enter position at entry price
3. Set stop loss at specified level
4. Set take profit orders at target levels
5. Monitor position

### Step 4: Track Results
- Record entry/exit prices
- Note if stopped out or took profit
- Calculate P&L
- Report any issues or feedback

---

## Troubleshooting

### No Signals Showing

**Cause:** Signals haven't been generated yet.

**Solution:**
```bash
# Manually trigger signal generation
curl -X GET "https://fkstrading.xyz/api/signals/generate?category=swing"

# Wait 30-60 seconds for processing
# Refresh the Signals page
```

### 404 Error on API Call

**Cause:** Wrong endpoint URL.

**Fix:** Use `/api/signals/from-files` not `/api/v1/signals/history`

### Empty Response

**Cause:** No signals for selected date/category.

**Solution:**
- Try different category filter
- Generate signals manually
- Check if signal files exist in `data/signals/`

---

## Development Tips

### Adding Test Signals

Create a test signal file for development:

```bash
# Create signals directory
mkdir -p data/signals/$(date +%Y%m%d)

# Create test signal file
cat > data/signals/$(date +%Y%m%d)/swing_signals.json << 'EOF'
{
  "signals": [
    {
      "symbol": "BTCUSD",
      "direction": "LONG",
      "entry_price": 45000.00,
      "stop_loss": 44000.00,
      "take_profit_levels": [46000.00, 47000.00, 48000.00],
      "category": "swing",
      "confidence": 85,
      "timestamp": "2026-01-04T14:30:00Z"
    }
  ],
  "generated_at": "2026-01-04T14:30:00Z"
}
EOF

# Refresh the Signals page - signal should appear!
```

### Debugging Signal Generation

```bash
# Check signal generation logs
docker compose logs backward -f | grep -i signal

# Check gateway logs
docker compose logs gateway -f | grep -i signal

# Check task queue (if using Celery)
docker compose logs -f | grep celery
```

---

## API Reference

### GET /api/signals/from-files

Load signals from JSON files.

**Parameters:**
- `date` (optional): YYYYMMDD format (default: today)
- `category` (optional): Filter by category
- `symbol` (optional): Filter by symbol
- `include_lot_size` (optional): Include lot size calculations (default: true)

**Response:**
```json
{
  "date": "20260104",
  "signals": {
    "scalp": [...],
    "swing": [...],
    "long_term": [...]
  },
  "generated_at": "2026-01-04T15:00:00Z",
  "lot_size_enabled": true
}
```

### GET /api/signals/generate

Trigger signal generation (async task).

**Parameters:**
- `category` (optional): Trade category (default: "swing")
- `symbols` (optional): Comma-separated symbols
- `ai_enhanced` (optional): Use AI enhancement (default: false)

**Response:**
```json
{
  "task_id": "abc123",
  "status": "queued",
  "message": "Signal generation queued",
  "category": "swing"
}
```

### GET /api/signals/categories

Get available signal categories.

**Response:**
```json
{
  "categories": [
    {
      "category": "scalp",
      "description": "Short-term trades, minutes to hours",
      "time_horizon_min_hours": 0.25,
      "time_horizon_max_hours": 4
    },
    ...
  ]
}
```

---

## Next Steps

1. **Set up automatic signal generation** (cron job or Celery beat)
2. **Add real-time updates** (WebSocket for new signals)
3. **Implement signal validation** (backtesting before display)
4. **Add notifications** (email/SMS for high-confidence signals)
5. **Track performance** (win rate, average return per signal)

---

## Support

### Getting Help
- Check logs: `docker compose logs -f`
- Review API docs: `https://fkstrading.xyz/docs`
- Test endpoints: Use `curl` or Postman

### Common Issues
- **No signals**: Generate manually with API
- **404 errors**: Check endpoint URLs
- **Empty arrays**: Signals not generated for today

---

**Last Updated:** 2026-01-04  
**Status:** Active Development  
**Next Release:** Automatic signal generation scheduling