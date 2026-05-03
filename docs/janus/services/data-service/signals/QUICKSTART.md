# Signals API Quick Start Guide

Get up and running with the FKS Signals API in 5 minutes.

---

## Prerequisites

- Docker & Docker Compose installed
- FKS repository cloned
- Port 8080 available

---

## 1. Start the Services

```bash
cd fks
docker-compose up -d data-service questdb redis
```

Wait for services to initialize (~30 seconds):

```bash
docker-compose logs -f data-service
```

Look for:
```
✅ Signal actor started (EMA cross, RSI zones, MACD cross, confluence)
✅ API server started on port 8080
```

---

## 2. Warm Up Indicators

The SignalActor needs historical indicator data to detect crossovers. Run a deep warmup:

```bash
curl -X POST http://localhost:8080/api/v1/indicators/warmup/deep \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTCUSD", "ETHUSDT"],
    "timeframes": ["1m"],
    "limit": 250
  }'
```

This fetches 250 historical candles from Binance and processes them through the indicator pipeline.

**Wait 30-60 seconds** for signal detection to complete.

---

## 3. Query Signals

### Get Signal Statistics

```bash
curl http://localhost:8080/api/v1/signals/stats | jq
```

**Expected Output**:
```json
{
  "total_signals": 42,
  "signals_by_type": {
    "ema_golden_cross": 8,
    "ema_death_cross": 7,
    "rsi_overbought": 5,
    "rsi_oversold": 6,
    "macd_bullish_cross": 9,
    "macd_bearish_cross": 7
  },
  "signals_by_symbol": {
    "BTCUSD": 23,
    "ETHUSDT": 19
  },
  "signals_by_timeframe": {
    "1m": 42
  },
  "last_signal_timestamp": "2025-01-20 15:45:32"
}
```

### List Recent Signals

```bash
curl "http://localhost:8080/api/v1/signals?limit=10" | jq
```

**Expected Output**:
```json
{
  "signals": [
    {
      "symbol": "BTCUSD",
      "timeframe": "1m",
      "signal_type": "ema_golden_cross",
      "direction": "bullish",
      "timestamp": "2025-01-20 15:30:00",
      "price": 42350.50,
      "ema_8": 42300.25,
      "ema_21": 42280.75,
      "rsi": 55.3,
      "macd": 12.5,
      "macd_signal": 10.2,
      "metadata": "{}"
    }
  ],
  "count": 10,
  "limit": 10
}
```

### Get Signals for Specific Symbol

```bash
curl "http://localhost:8080/api/v1/signals/BTCUSD/1m?limit=20" | jq
```

### Filter by Signal Type

```bash
# Get only golden cross signals
curl "http://localhost:8080/api/v1/signals?signal_type=ema_golden_cross&limit=50" | jq
```

### Filter by Time Range

```bash
# Get signals from the last hour
START_TIME=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)
curl "http://localhost:8080/api/v1/signals?start_time=$START_TIME&limit=100" | jq
```

---

## 4. Monitor Signal Generation

### Check Prometheus Metrics

```bash
curl http://localhost:8080/metrics | grep signals_generated_total
```

**Sample Output**:
```
signals_generated_total{symbol="BTCUSD",timeframe="1m",signal_type="ema_golden_cross",direction="bullish"} 8
signals_generated_total{symbol="BTCUSD",timeframe="1m",signal_type="ema_death_cross",direction="bearish"} 7
signals_generated_total{symbol="BTCUSD",timeframe="1m",signal_type="rsi_oversold",direction="bullish"} 6
```

### View Grafana Dashboard

1. Open Grafana: http://localhost:3000
2. Login: `admin` / `admin`
3. Navigate to: **Dashboards** → **Technical Indicators**
4. View signal generation rates and distribution

---

## 5. Real-Time Signal Monitoring

### Tail Service Logs

```bash
docker-compose logs -f data-service | grep "Generated.*signal"
```

**Sample Output**:
```
SignalActor: Generated ema_golden_cross signal for BTCUSD:1m @ 42350.50
SignalActor: Generated rsi_oversold signal for ETHUSDT:1m @ 2234.75
```

### Query QuestDB Directly

```bash
curl "http://localhost:9000/exec?query=SELECT+*+FROM+signals_crypto+ORDER+BY+timestamp+DESC+LIMIT+10" | jq
```

---

## Common Use Cases

### 1. Build a Trading Bot

```python
import requests
import time

def check_for_bullish_signals():
    response = requests.get(
        "http://localhost:8080/api/v1/signals",
        params={
            "direction": "bullish",
            "limit": 5
        }
    )
    
    signals = response.json()["signals"]
    
    for signal in signals:
        if signal["signal_type"] == "bullish_confluence":
            print(f"🚀 HIGH CONFIDENCE: {signal['symbol']} @ {signal['price']}")
            # Place order here
        elif signal["signal_type"] == "ema_golden_cross":
            print(f"📈 Golden Cross: {signal['symbol']} @ {signal['price']}")

# Run every minute
while True:
    check_for_bullish_signals()
    time.sleep(60)
```

### 2. Backtest a Strategy

```python
import requests
from datetime import datetime, timedelta

# Fetch signals from the last 24 hours
start_time = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"

response = requests.get(
    "http://localhost:8080/api/v1/signals/BTCUSD/1m",
    params={
        "start_time": start_time,
        "limit": 1000
    }
)

signals = response.json()["signals"]

# Analyze signal performance
for signal in signals:
    entry_price = signal["price"]
    # Fetch price 1 hour later and calculate P&L
    # ...
```

### 3. Signal Alerts Dashboard

```javascript
// React component
import { useEffect, useState } from 'react';

function SignalDashboard() {
  const [signals, setSignals] = useState([]);

  useEffect(() => {
    const fetchSignals = async () => {
      const res = await fetch('http://localhost:8080/api/v1/signals?limit=50');
      const data = await res.json();
      setSignals(data.signals);
    };

    // Fetch every 10 seconds
    const interval = setInterval(fetchSignals, 10000);
    fetchSignals();

    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <h1>Recent Signals</h1>
      {signals.map(signal => (
        <div key={`${signal.symbol}-${signal.timestamp}`}>
          {signal.signal_type} - {signal.symbol} @ {signal.price}
        </div>
      ))}
    </div>
  );
}
```

---

## Troubleshooting

### Problem: No Signals Generated

**Check 1**: Are indicators warmed up?
```bash
curl http://localhost:8080/api/v1/indicators/BTCUSD/1m/status
```

**Expected**: `"all_indicators_ready": true`

**Solution**: Run deep warmup (see Step 2)

---

**Check 2**: Are WebSockets connected?
```bash
docker-compose logs data-service | grep "WebSocket connected"
```

**Expected**: 
```
✅ WebSocket connected to Binance (BTCUSD)
```

**Solution**: Check network connectivity, restart service

---

**Check 3**: Is QuestDB running?
```bash
curl http://localhost:9000/exec?query=SELECT+1
```

**Expected**: HTTP 200 with JSON response

**Solution**: `docker-compose up -d questdb`

---

### Problem: Old Signals Only

**Cause**: Live WebSocket feed not active

**Solution**:
```bash
# Restart data-service to reconnect WebSockets
docker-compose restart data-service

# Wait 30 seconds, check logs
docker-compose logs -f data-service | grep "candle"
```

---

### Problem: API Returns 500 Error

**Check**: QuestDB HTTP API connectivity
```bash
curl http://localhost:9000
```

**Solution**: Ensure `QUESTDB_HOST=questdb` in docker-compose environment

---

## Next Steps

- **Read Full API Docs**: [`docs/signals-api.md`](./signals-api.md)
- **Configure Alert Rules**: [`config/prometheus/alerts/technical-indicators.yml`](../config/prometheus/alerts/technical-indicators.yml)
- **Build Strategies**: Use confluence signals for higher accuracy
- **Multi-Timeframe**: Add 5m, 15m, 1h signals for confirmation

---

## Quick Reference

### All Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/signals` | List all signals |
| `GET /api/v1/signals/{symbol}` | Signals for symbol |
| `GET /api/v1/signals/{symbol}/{timeframe}` | Signals for symbol + timeframe |
| `GET /api/v1/signals/stats` | Aggregated statistics |

### Signal Types

- `ema_golden_cross` / `ema_death_cross` - EMA crossovers
- `rsi_overbought` / `rsi_oversold` - RSI zones
- `rsi_exit_overbought` / `rsi_exit_oversold` - RSI exits
- `macd_bullish_cross` / `macd_bearish_cross` - MACD crossovers
- `bullish_confluence` / `bearish_confluence` - Multi-indicator alignment

### Environment Variables

```bash
QUESTDB_HOST=questdb          # QuestDB hostname
QUESTDB_HTTP_PORT=9000        # QuestDB HTTP API port
RUST_LOG=info,fks_data=debug  # Logging level
```

---

**Questions?** Check the [full documentation](./signals-api.md) or open an issue on GitHub.