# Forward → Execution Integration Guide

This guide covers the integration between the JANUS Forward service (signal generation) and the FKS Execution service (order execution), including setup, implementation, and testing procedures.

## Overview

The Forward → Execution integration enables automated trading signal execution:

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────┐
│  JANUS Forward  │  gRPC   │  FKS Execution   │  REST   │   Exchange   │
│  (Signals)      │ ──────> │  (Orders)        │ ──────> │  (Bybit)     │
└─────────────────┘         └──────────────────┘         └──────────────┘
     Signal Gen                Order Execution              Live/Paper
     Risk Check                Risk Management              Trading
     Position Size             Position Tracking
```

## Implementation Status

### ✅ Completed

1. **Execution Service Added to Docker Compose**
   - Service definition in `docker-compose.yml`
   - Dockerfile build target for execution service
   - Health checks and resource limits configured
   - Environment variables for simulated/paper/live modes

2. **Execution gRPC Client Created**
   - `src/janus/services/forward/src/execution/client.rs`
   - Protobuf definitions copied and build script updated
   - Signal-to-order conversion logic
   - Retry logic with exponential backoff
   - Health check integration

3. **Discord Notifications**
   - Discord webhook notifier in execution service
   - UI for webhook management (KMP frontend)
   - Environment variable configuration

### ⏳ Next Steps

1. **Wire Execution Client in Forward Service** (2-3 hours)
2. **Add Configuration & Environment Variables** (1 hour)
3. **Run 48-Hour Simulated Integration Test** (2+ days)
4. **Paper Trading Test on Bybit Testnet** (1-2 weeks)

---

## Part 1: Wire Execution Client in Forward Service

### 1.1 Update Signal Generator to Submit Signals

The signal generator needs to be enhanced to automatically submit generated signals to the execution service.

**File: `src/janus/services/forward/src/signal/mod.rs`**

Add execution client integration:

```rust
use crate::execution::{ExecutionClient, ExecutionClientConfig};

pub struct SignalGenerator {
    // ... existing fields ...
    execution_client: Option<Arc<tokio::sync::Mutex<ExecutionClient>>>,
}

impl SignalGenerator {
    pub async fn new_with_execution(
        config: SignalGeneratorConfig,
        execution_config: Option<ExecutionClientConfig>,
    ) -> Result<Self> {
        // ... existing initialization ...
        
        let execution_client = if let Some(exec_cfg) = execution_config {
            match ExecutionClient::new(exec_cfg).await {
                Ok(client) => {
                    info!("✅ Execution client connected");
                    Some(Arc::new(tokio::sync::Mutex::new(client)))
                }
                Err(e) => {
                    warn!("Failed to connect execution client: {}", e);
                    None
                }
            }
        } else {
            None
        };

        Ok(Self {
            // ... existing fields ...
            execution_client,
        })
    }

    /// Submit signal to execution service if client is available
    async fn submit_to_execution(&self, signal: &TradingSignal) -> Result<()> {
        if let Some(client) = &self.execution_client {
            let mut client = client.lock().await;
            match client.submit_signal(signal).await {
                Ok(response) => {
                    info!(
                        "✅ Signal {} submitted to execution (order: {})",
                        signal.signal_id,
                        response.order_id.as_deref().unwrap_or("N/A")
                    );
                    Ok(())
                }
                Err(e) => {
                    error!("❌ Failed to submit signal to execution: {}", e);
                    Err(e)
                }
            }
        } else {
            debug!("Execution client not configured, signal not submitted");
            Ok(())
        }
    }
}
```

### 1.2 Integrate into Signal Generation Flow

Modify the `generate_from_analysis` method to submit signals:

```rust
pub async fn generate_from_analysis(
    &self,
    symbol: String,
    timeframe: Timeframe,
    analysis: &IndicatorAnalysis,
    current_price: f64,
) -> Result<Option<TradingSignal>> {
    // ... existing signal generation logic ...
    
    if let Some(signal) = &signal {
        // Submit to execution service
        if let Err(e) = self.submit_to_execution(signal).await {
            warn!("Signal generated but execution submission failed: {}", e);
            // Continue - signal is still valid even if submission failed
        }
    }
    
    Ok(signal)
}
```

### 1.3 Update Forward Service Configuration

**File: `src/janus/services/forward/src/lib.rs`**

Add execution client config to `ForwardServiceConfig`:

```rust
pub struct ForwardServiceConfig {
    // ... existing fields ...
    
    /// Execution client configuration (None = signals generated but not executed)
    pub execution_config: Option<ExecutionClientConfig>,
}

impl ForwardService {
    pub async fn new(config: ForwardServiceConfig) -> Result<Self> {
        // ... existing code ...
        
        let signal_generator = if config.execution_config.is_some() {
            Arc::new(SignalGenerator::new_with_execution(
                config.signal_config.clone(),
                config.execution_config.clone(),
            ).await?)
        } else {
            Arc::new(SignalGenerator::new(config.signal_config.clone()))
        };
        
        // ... rest of initialization ...
    }
}
```

### 1.4 Update Main Entry Point

**File: `src/janus/services/forward/src/main.rs`**

Add environment variable parsing for execution client:

```rust
#[tokio::main]
async fn main() -> Result<()> {
    // ... existing initialization ...
    
    // Configure execution client (optional)
    let execution_config = if std::env::var("ENABLE_EXECUTION")
        .unwrap_or_else(|_| "false".to_string())
        .parse::<bool>()
        .unwrap_or(false)
    {
        Some(ExecutionClientConfig {
            endpoint: std::env::var("EXECUTION_ENDPOINT")
                .unwrap_or_else(|_| "http://execution:50052".to_string()),
            connect_timeout_secs: std::env::var("EXECUTION_CONNECT_TIMEOUT")
                .unwrap_or_else(|_| "10".to_string())
                .parse()
                .unwrap_or(10),
            request_timeout_secs: std::env::var("EXECUTION_REQUEST_TIMEOUT")
                .unwrap_or_else(|_| "30".to_string())
                .parse()
                .unwrap_or(30),
            enable_tls: std::env::var("EXECUTION_ENABLE_TLS")
                .unwrap_or_else(|_| "false".to_string())
                .parse()
                .unwrap_or(false),
            max_retries: std::env::var("EXECUTION_MAX_RETRIES")
                .unwrap_or_else(|_| "3".to_string())
                .parse()
                .unwrap_or(3),
            retry_backoff_ms: std::env::var("EXECUTION_RETRY_BACKOFF_MS")
                .unwrap_or_else(|_| "100".to_string())
                .parse()
                .unwrap_or(100),
        })
    } else {
        info!("Execution client disabled - signals will be generated but not executed");
        None
    };
    
    let config = ForwardServiceConfig {
        // ... existing config ...
        execution_config,
    };
    
    let mut service = ForwardService::new(config).await?;
    service.start().await?;
    
    Ok(())
}
```

---

## Part 2: Configuration & Environment Variables

### 2.1 Update Docker Compose for Forward Service

Add execution integration environment variables to `docker-compose.yml`:

```yaml
forward:
    environment:
        # ... existing environment variables ...
        
        # Execution Integration
        - ENABLE_EXECUTION=${ENABLE_EXECUTION:-true}
        - EXECUTION_ENDPOINT=http://execution:50052
        - EXECUTION_CONNECT_TIMEOUT=10
        - EXECUTION_REQUEST_TIMEOUT=30
        - EXECUTION_ENABLE_TLS=false
        - EXECUTION_MAX_RETRIES=3
        - EXECUTION_RETRY_BACKOFF_MS=100
    
    depends_on:
        redis:
            condition: service_healthy
        questdb:
            condition: service_healthy
        execution:
            condition: service_healthy  # Add execution dependency
```

### 2.2 Environment Variables Reference

**Forward Service:**

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_EXECUTION` | Enable automatic signal submission | `false` |
| `EXECUTION_ENDPOINT` | Execution service gRPC endpoint | `http://execution:50052` |
| `EXECUTION_CONNECT_TIMEOUT` | Connection timeout (seconds) | `10` |
| `EXECUTION_REQUEST_TIMEOUT` | Request timeout (seconds) | `30` |
| `EXECUTION_MAX_RETRIES` | Max retry attempts | `3` |
| `EXECUTION_RETRY_BACKOFF_MS` | Retry backoff (milliseconds) | `100` |

**Execution Service:**

| Variable | Description | Default |
|----------|-------------|---------|
| `EXECUTION_MODE` | Mode: `simulated`, `paper`, `live` | `simulated` |
| `SIMULATION_INITIAL_BALANCE` | Starting balance (simulated) | `100000` |
| `SIMULATION_SLIPPAGE_BPS` | Slippage in basis points | `5` |
| `SIMULATION_FEE_BPS` | Trading fee in basis points | `10` |
| `MAX_POSITION_SIZE_USD` | Max position size (USD) | `10000` |
| `MAX_PORTFOLIO_EXPOSURE_USD` | Max portfolio exposure (USD) | `50000` |
| `MAX_OPEN_POSITIONS` | Max concurrent positions | `10` |
| `DISCORD_WEBHOOK_GENERAL` | Discord webhook for notifications | (empty) |
| `DISCORD_NOTIFICATIONS_ENABLED` | Enable Discord notifications | `false` |

### 2.3 Create `.env` File for Local Testing

Create a `.env` file in the `fks/` directory:

```bash
# Forward → Execution Integration
ENABLE_EXECUTION=true
EXECUTION_ENDPOINT=http://execution:50052

# Execution Mode
EXECUTION_MODE=simulated

# Simulation Settings
SIMULATION_INITIAL_BALANCE=100000
SIMULATION_SLIPPAGE_BPS=5
SIMULATION_FEE_BPS=10
SIMULATION_FILL_DELAY_MS=100
SIMULATION_ENABLE_SLIPPAGE=true

# Risk Limits
MAX_POSITION_SIZE_USD=10000
MAX_PORTFOLIO_EXPOSURE_USD=50000
MAX_OPEN_POSITIONS=10
MAX_DAILY_LOSS_USD=1000
ENABLE_RISK_CHECKS=true

# Discord Notifications (get webhook URL from Discord: Server Settings → Integrations → Webhooks)
DISCORD_WEBHOOK_GENERAL=
DISCORD_NOTIFICATIONS_ENABLED=false

# Bybit (for paper/live trading - not needed for simulated)
BYBIT_API_KEY=
BYBIT_API_SECRET=
BYBIT_TESTNET=true
```

---

## Part 3: Build & Deploy

### 3.1 Build the Services

```bash
cd fks

# Build all services
docker compose build

# Or build specific services
docker compose build forward
docker compose build execution
```

### 3.2 Start the Stack

```bash
# Start all services
docker compose up -d

# Check logs
docker compose logs -f forward
docker compose logs -f execution

# Check service health
docker compose ps
```

### 3.3 Verify Integration

```bash
# Check forward service health
curl http://localhost:8080/api/v1/health

# Check execution service health
curl http://localhost:8081/health

# Check execution metrics
curl http://localhost:8081/metrics

# Generate a test signal (REST API)
curl -X POST http://localhost:8080/api/v1/signals/generate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "timeframe": "15m",
    "analysis": {
      "rsi": 65.0,
      "macd": 150.0,
      "macd_signal": 100.0,
      "bb_upper": 51000.0,
      "bb_lower": 49000.0
    },
    "current_price": 50000.0
  }'
```

---

## Part 4: 48-Hour Simulated Integration Test

### 4.1 Test Objectives

1. **Signal Generation → Execution Flow**
   - Verify signals are generated from market data
   - Confirm signals are submitted to execution service
   - Check orders are created and tracked

2. **Order Execution & Fills**
   - Verify simulated fills with slippage
   - Check fee calculation
   - Confirm position updates

3. **Risk Management**
   - Test position size limits
   - Verify portfolio exposure limits
   - Confirm daily loss limits

4. **Notifications**
   - Verify Discord notifications for orders
   - Check notification content and formatting

5. **Stability & Performance**
   - Monitor service uptime
   - Check memory and CPU usage
   - Verify no memory leaks

### 4.2 Test Setup

1. **Enable Discord Notifications**

   ```bash
   # Create a Discord webhook:
   # 1. Go to Discord Server Settings → Integrations → Webhooks
   # 2. Click "New Webhook"
   # 3. Name it "FKS Trading System"
   # 4. Copy webhook URL
   
   # Update .env file
   echo "DISCORD_WEBHOOK_GENERAL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN" >> .env
   echo "DISCORD_NOTIFICATIONS_ENABLED=true" >> .env
   
   # Restart execution service
   docker compose restart execution
   ```

2. **Configure Monitoring**

   Access Grafana: http://localhost:3000
   - Default login: `admin` / `admin`
   - Import FKS dashboards
   - Monitor:
     - Signal generation rate
     - Order execution rate
     - Fill rate
     - Position P&L
     - Service health

3. **Set Up Log Monitoring**

   ```bash
   # Follow all relevant logs
   docker compose logs -f forward execution data
   
   # Or use Loki/Promtail (if configured)
   # Access Grafana Explore → Loki
   ```

### 4.3 Test Execution

```bash
# Start the test
docker compose up -d

# Monitor logs in separate terminals
docker compose logs -f forward
docker compose logs -f execution

# Check QuestDB for data
# Access: http://localhost:9000
# Queries:
# - SELECT * FROM signals ORDER BY timestamp DESC LIMIT 100;
# - SELECT * FROM orders ORDER BY timestamp DESC LIMIT 100;
# - SELECT * FROM fills ORDER BY timestamp DESC LIMIT 100;
# - SELECT * FROM positions ORDER BY timestamp DESC;
```

### 4.4 Test Validation Checklist

After 48 hours, verify the following:

- [ ] **Signal Generation**
  - [ ] Signals generated for BTC, ETH, SOL
  - [ ] Signal quality metrics look reasonable
  - [ ] No excessive filtering (check filter rate)

- [ ] **Order Execution**
  - [ ] Orders created for valid signals
  - [ ] Orders filled in simulated mode
  - [ ] Fill prices include slippage
  - [ ] Fees calculated correctly

- [ ] **Position Tracking**
  - [ ] Positions opened and closed correctly
  - [ ] P&L calculated accurately
  - [ ] Position sizes within limits

- [ ] **Risk Management**
  - [ ] No position exceeds max size
  - [ ] Total exposure within limits
  - [ ] Daily loss limits enforced (if triggered)

- [ ] **Notifications**
  - [ ] Discord messages received for orders
  - [ ] Messages include all relevant info
  - [ ] No notification spam or errors

- [ ] **System Stability**
  - [ ] All services running without crashes
  - [ ] Memory usage stable (no leaks)
  - [ ] CPU usage reasonable (<50% on average)
  - [ ] No database connection errors

- [ ] **Data Quality**
  - [ ] Market data flowing consistently
  - [ ] All data persisted to QuestDB
  - [ ] No gaps in time series

### 4.5 Performance Metrics to Track

Query QuestDB to get these metrics:

```sql
-- Signal generation stats
SELECT 
    COUNT(*) as total_signals,
    COUNT_IF(executed = true) as executed_signals,
    AVG(confidence) as avg_confidence,
    AVG(strength) as avg_strength
FROM signals
WHERE timestamp > dateadd('h', -48, now());

-- Order execution stats
SELECT 
    COUNT(*) as total_orders,
    COUNT_IF(status = 'FILLED') as filled_orders,
    AVG(fill_time_ms) as avg_fill_time_ms,
    SUM(fee_paid) as total_fees
FROM orders
WHERE created_at > dateadd('h', -48, now());

-- Position P&L
SELECT 
    symbol,
    COUNT(*) as trades,
    SUM(realized_pnl) as total_pnl,
    AVG(realized_pnl) as avg_pnl_per_trade,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades
FROM positions
WHERE closed_at > dateadd('h', -48, now())
GROUP BY symbol;

-- Risk metrics
SELECT 
    timestamp,
    total_exposure_usd,
    open_positions_count,
    daily_pnl
FROM portfolio_state
WHERE timestamp > dateadd('h', -48, now())
ORDER BY timestamp DESC;
```

---

## Part 5: Paper Trading Test (After Simulated Success)

### 5.1 Prerequisites

1. **Successful 48-hour simulated test** (all checklist items ✅)
2. **Bybit testnet account** with API keys
3. **Small test balance** on testnet (e.g., 1000 USDT)

### 5.2 Configuration for Paper Trading

Update `.env`:

```bash
# Switch to paper mode
EXECUTION_MODE=paper

# Bybit Testnet API (get from: https://testnet.bybit.com/app/user/api-management)
BYBIT_API_KEY=your_testnet_api_key
BYBIT_API_SECRET=your_testnet_api_secret
BYBIT_TESTNET=true

# Conservative limits for testing
MAX_POSITION_SIZE_USD=100
MAX_PORTFOLIO_EXPOSURE_USD=500
MAX_OPEN_POSITIONS=3
MAX_DAILY_LOSS_USD=50

# Enable notifications
DISCORD_NOTIFICATIONS_ENABLED=true
```

### 5.3 Paper Trading Test Duration

Recommended: **1-2 weeks**

Monitor:
- Order submission to real exchange (testnet)
- Order fills from exchange WebSocket
- Position synchronization
- Real market slippage vs. simulated
- API rate limiting
- Exchange error handling

---

## Part 6: Troubleshooting

### Common Issues

**1. Execution client connection failed**

```
Error: Failed to connect to execution service
```

**Solution:**
- Check execution service is running: `docker compose ps execution`
- Check execution service logs: `docker compose logs execution`
- Verify endpoint in config: should be `http://execution:50052` (service name in Docker)
- Check network connectivity: `docker compose exec forward ping execution`

**2. Signal not submitted to execution**

```
Execution client not configured, signal not submitted
```

**Solution:**
- Verify `ENABLE_EXECUTION=true` in environment
- Check forward service logs for execution client initialization
- Restart forward service: `docker compose restart forward`

**3. Orders rejected by execution service**

```
Execution service rejected signal: Risk violation
```

**Solution:**
- Check risk limits in execution service config
- Verify position size calculation in forward service
- Review risk metrics: `curl http://localhost:8081/metrics`

**4. Protobuf compilation errors**

```
error: failed to compile `proto/execution.proto`
```

**Solution:**
- Ensure protobuf compiler is installed: `apt install -y protobuf-compiler`
- Check proto file syntax
- Clean build: `cargo clean && cargo build`

**5. Discord notifications not working**

```
Failed to send Discord notification
```

**Solution:**
- Verify webhook URL is correct and not expired
- Check `DISCORD_NOTIFICATIONS_ENABLED=true`
- Test webhook manually: `curl -X POST <webhook_url> -H "Content-Type: application/json" -d '{"content":"test"}'`
- Check execution service logs for webhook errors

---

## Part 7: Next Steps After Successful Testing

### 7.1 After Simulated Test Success

1. **Analyze Performance**
   - Review all metrics and P&L
   - Identify areas for improvement
   - Adjust signal generation parameters if needed

2. **Tune Risk Parameters**
   - Adjust position sizing
   - Optimize stop loss / take profit levels
   - Refine risk limits

3. **Move to Paper Trading**
   - Follow Part 5 instructions
   - Start with conservative limits
   - Monitor closely for first week

### 7.2 After Paper Trading Success

1. **Evaluate Strategy Performance**
   - Compare simulated vs. paper results
   - Analyze slippage and fees impact
   - Calculate Sharpe ratio and other metrics

2. **Prepare for Live Trading** (if results are positive)
   - Set up live exchange account
   - Configure production environment
   - Implement additional safety measures
   - Start with minimal capital

3. **Production Deployment**
   - Use `docker-compose.prod.yml`
   - Enable TLS for all services
   - Set up proper secrets management
   - Configure monitoring and alerts
   - Implement circuit breakers
   - Set up automated backups

---

## Appendices

### A. Service Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                         FKS Trading System                         │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                  │
│  │   Data   │────▶│ Forward  │────▶│Execution │────┐             │
│  │ Service  │     │ Service  │ gRPC│ Service  │    │             │
│  └──────────┘     └──────────┘     └──────────┘    │             │
│       │                  │               │          │             │
│       │                  │               │          ▼             │
│       ▼                  ▼               ▼     ┌─────────┐        │
│  ┌─────────┐        ┌────────┐     ┌────────┐│ Discord │        │
│  │QuestDB  │        │ Redis  │     │ Bybit  ││Webhook  │        │
│  │(Storage)│        │(PubSub)│     │Exchange││Notifier │        │
│  └─────────┘        └────────┘     └────────┘└─────────┘        │
│                                                                    │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                  │
│  │Prometheus│────▶│ Grafana  │     │  Jaeger  │                  │
│  │(Metrics) │     │(Dashboar)│     │(Tracing) │                  │
│  └──────────┘     └──────────┘     └──────────┘                  │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### B. Signal Flow Diagram

```
Market Data → Data Service → QuestDB
                    │
                    ▼
              Forward Service
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    Signal Gen          Risk Analysis
         │                     │
         └──────────┬──────────┘
                    ▼
            Valid Signal?
                    │
         ┌──────────┴──────────┐
         │                     │
        Yes                   No
         │                     │
         ▼                     ▼
    Execution gRPC      Discard Signal
      Submit                  │
         │                    ▼
         ▼               Log & Metrics
   Execution Service
         │
    ┌────┴────┐
    ▼         ▼
  Order    Discord
  Place    Notify
    │
    ▼
 Position
  Update
```

### C. Useful Commands

```bash
# View all service statuses
docker compose ps

# Restart specific service
docker compose restart forward
docker compose restart execution

# View logs with timestamps
docker compose logs -f --timestamps forward execution

# Execute SQL in QuestDB
curl -G \
  --data-urlencode "query=SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10" \
  http://localhost:9000/exec

# Check Redis keys
docker compose exec redis redis-cli KEYS "*"

# Monitor resource usage
docker stats fks_forward fks_execution

# Backup QuestDB data
docker compose exec questdb tar czf /tmp/backup.tar.gz /var/lib/questdb
docker compose cp questdb:/tmp/backup.tar.gz ./questdb-backup.tar.gz

# Clean up and restart
docker compose down
docker compose up -d
```

---

## Summary

This integration connects the JANUS Forward service (signal generation) with the FKS Execution service (order execution), enabling end-to-end automated trading.

**Key Points:**
1. Start with **simulated mode** for 48 hours minimum
2. Verify all components work correctly before advancing
3. Use **paper trading** (testnet) for 1-2 weeks before considering live
4. Monitor Discord notifications for all trading activity
5. Review metrics and logs regularly
6. Never skip testing phases

**Estimated Timeline:**
- Implementation: 3-4 hours
- Simulated testing: 48 hours (2 days)
- Paper trading: 1-2 weeks
- Total to production-ready: ~3 weeks minimum

Good luck! 🚀