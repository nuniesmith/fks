# FKS Trading Platform - Task Workflow Guide

## Task Execution Flow

This document illustrates how the 16 Celery tasks work together in the automated trading system.

---

## Minute-by-Minute Schedule

### Every 5 Minutes (Critical Path)
```
┌─────────────────────────────────────────────────────────────┐
│  🔄 sync_market_data_task                                   │
│     ↓                                                       │
│  📊 update_positions_task                                   │
│     ↓                                                       │
│  🛑 check_stop_loss_task                                    │
└─────────────────────────────────────────────────────────────┘
```

**Flow:**
1. Fetch latest OHLCV data from Binance
2. Update position prices and unrealized PnL
3. Check if any stop losses triggered
4. Send alerts if needed

---

### Every 15 Minutes (Signal Generation)
```
┌─────────────────────────────────────────────────────────────┐
│  🔄 sync_market_data_task (new data)                        │
│     ↓                                                       │
│  📈 generate_signals_task                                   │
│     ↓                                                       │
│  💰 sync_account_balance_task                               │
└─────────────────────────────────────────────────────────────┘
```

**Flow:**
1. Ensure fresh market data
2. Generate BUY/HOLD signals
3. Update account balance and equity
4. Send Discord alert if BUY signal

---

### Every 30 Minutes (Analysis & Indicators)
```
┌─────────────────────────────────────────────────────────────┐
│  🔄 sync_market_data_task (new data)                        │
│     ↓                                                       │
│  📊 update_indicators_task                                  │
│     ↓                                                       │
│  ⚠️  analyze_risk_task                                      │
└─────────────────────────────────────────────────────────────┘
```

**Flow:**
1. Fetch fresh data
2. Calculate RSI, MACD, BB, ATR, SMA, EMA
3. Cache indicators for signal generation
4. Assess portfolio risk
5. Send HIGH risk alerts if needed

---

### Every Hour (News & Data)
```
┌─────────────────────────────────────────────────────────────┐
│  📰 fetch_news_task                                         │
└─────────────────────────────────────────────────────────────┘
```

**Flow:**
1. Fetch market news
2. Store for sentiment analysis
3. (Future: Feed into signal generation)

---

## Daily Schedule

### Midnight (00:00) - Backtesting
```
┌─────────────────────────────────────────────────────────────┐
│  🧪 run_backtest_task                                       │
│     ↓                                                       │
│  📊 Calculate performance metrics                           │
│     ↓                                                       │
│  💾 Store strategy parameters                               │
└─────────────────────────────────────────────────────────────┘
```

**Purpose:** Test strategy on previous day's data

---

### 1 AM - Strategy Validation
```
┌─────────────────────────────────────────────────────────────┐
│  ✅ validate_strategies_task                                │
│     ↓                                                       │
│  📊 Run backtest with each strategy                         │
│     ↓                                                       │
│  ⚠️  Check: Sharpe > 1.0, Return > 0, DD < 30%            │
│     ↓                                                       │
│  🚫 Auto-disable failing strategies                         │
└─────────────────────────────────────────────────────────────┘
```

**Purpose:** Ensure only profitable strategies remain active

---

### 3 AM - Data Management
```
┌─────────────────────────────────────────────────────────────┐
│  🗄️  archive_old_data_task                                  │
│     ↓                                                       │
│  📦 Identify data older than retention period               │
│     ↓                                                       │
│  ♻️  Archive or delete (maintain performance)               │
└─────────────────────────────────────────────────────────────┘
```

**Purpose:** Keep database lean and fast

---

### 6 AM - Portfolio Optimization
```
┌─────────────────────────────────────────────────────────────┐
│  💼 optimize_portfolio_task                                 │
│     ↓                                                       │
│  📊 Analyze current allocation                              │
│     ↓                                                       │
│  🎯 Compare to target (50% mains, 50% alts)                │
│     ↓                                                       │
│  📋 Generate rebalancing recommendations                    │
└─────────────────────────────────────────────────────────────┘
```

**Purpose:** Daily portfolio health check and rebalancing suggestions

---

### 11 PM - Metrics & Reports
```
┌─────────────────────────────────────────────────────────────┐
│  📊 calculate_metrics_task                                  │
│     ↓                                                       │
│  Calculate: Sharpe, Drawdown, Win Rate, Returns            │
│     ↓                                                       │
│  📈 generate_report_task (11:30 PM)                         │
│     ↓                                                       │
│  📧 Send daily report via Discord                           │
└─────────────────────────────────────────────────────────────┘
```

**Purpose:** Daily performance summary

---

## Weekly Schedule

### Monday 8 AM - Weekly Report
```
┌─────────────────────────────────────────────────────────────┐
│  📊 calculate_metrics_task (7 days)                         │
│     ↓                                                       │
│  📈 generate_report_task (report_type='weekly')             │
│     ↓                                                       │
│  📧 Send weekly report via Discord                          │
└─────────────────────────────────────────────────────────────┘
```

**Purpose:** Weekly performance review

---

## On-Demand Tasks (Not Scheduled)

### Manual Rebalancing
```
┌─────────────────────────────────────────────────────────────┐
│  User/Admin triggers:                                       │
│  💼 rebalance_portfolio_task(account_id, execute=False)     │
│     ↓                                                       │
│  📋 Review dry-run recommendations                          │
│     ↓                                                       │
│  User approves:                                             │
│  💼 rebalance_portfolio_task(account_id, execute=True)      │
│     ↓                                                       │
│  💱 Execute trades                                          │
│     ↓                                                       │
│  📧 Send confirmation via Discord                           │
└─────────────────────────────────────────────────────────────┘
```

**Purpose:** Safe, manual portfolio rebalancing

---

### Custom Notifications
```
┌─────────────────────────────────────────────────────────────┐
│  Any task can call:                                         │
│  📧 send_notifications_task(type, message, urgent)          │
│     ↓                                                       │
│  📱 Discord webhook                                         │
│  📧 Email (future)                                          │
│  📲 SMS (future)                                            │
└─────────────────────────────────────────────────────────────┘
```

**Purpose:** Flexible notification system

---

## Complete Trading Workflow

### Normal Market Conditions
```
┌─────────────────────────────────────────────────────────────┐
│  Every 5 minutes:                                           │
│  🔄 Sync data → 📊 Update positions → 🛑 Check stops       │
│                                                             │
│  Every 15 minutes:                                          │
│  📈 Generate signals → 💰 Sync balance                      │
│                                                             │
│  Every 30 minutes:                                          │
│  📊 Update indicators → ⚠️  Analyze risk                    │
│                                                             │
│  Daily:                                                     │
│  🧪 Backtest → ✅ Validate → 💼 Optimize → 📈 Report       │
└─────────────────────────────────────────────────────────────┘
```

---

### BUY Signal Detected
```
┌─────────────────────────────────────────────────────────────┐
│  📈 generate_signals_task                                   │
│     ↓                                                       │
│  🎯 Signal = BUY                                            │
│     ↓                                                       │
│  📧 send_notifications_task("🚀 BUY Signal!")               │
│     ↓                                                       │
│  👤 Trader reviews suggestions                              │
│     ↓                                                       │
│  💱 Manual trade execution (or future: auto-execute)        │
│     ↓                                                       │
│  📊 update_positions_task (next cycle)                      │
└─────────────────────────────────────────────────────────────┘
```

---

### Stop Loss Triggered
```
┌─────────────────────────────────────────────────────────────┐
│  🛑 check_stop_loss_task                                    │
│     ↓                                                       │
│  ⚠️  Position price <= Stop Loss                            │
│     ↓                                                       │
│  📧 send_notifications_task("🛑 STOP LOSS TRIGGERED!")      │
│     ↓                                                       │
│  👤 Trader executes exit                                    │
│     ↓                                                       │
│  📊 update_positions_task (position closed)                 │
│     ↓                                                       │
│  💰 sync_account_balance_task (realize loss)                │
└─────────────────────────────────────────────────────────────┘
```

---

### HIGH Risk Detected
```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️  analyze_risk_task                                      │
│     ↓                                                       │
│  🔴 Risk Level = HIGH                                       │
│     ↓                                                       │
│  📧 send_notifications_task("⚠️ HIGH RISK ALERT!")          │
│     ↓                                                       │
│  👤 Trader reviews:                                         │
│     • Exposure > 80%?                                       │
│     • Unrealized loss > 10%?                                │
│     • Position concentration > 20%?                         │
│     ↓                                                       │
│  💼 Consider: rebalance_portfolio_task                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Task Dependencies

### Data Flow
```
sync_market_data_task
    ├──> update_indicators_task (needs OHLCV)
    ├──> generate_signals_task (needs OHLCV + indicators)
    ├──> run_backtest_task (needs historical OHLCV)
    └──> update_positions_task (needs current prices)

update_positions_task
    ├──> sync_account_balance_task (needs position PnL)
    ├──> check_stop_loss_task (needs current prices)
    └──> analyze_risk_task (needs position values)

generate_signals_task
    └──> send_notifications_task (on BUY signal)

calculate_metrics_task
    └──> generate_report_task (needs metrics)

optimize_portfolio_task
    └──> rebalance_portfolio_task (provides recommendations)
```

---

## Monitoring Points

### Flower Dashboard (http://localhost:5555)
- Task success/failure rates
- Execution times
- Queue depths
- Worker status

### Discord Notifications
- 🚀 BUY signals
- ⚠️ HIGH risk alerts
- 🛑 Stop loss triggers
- 💼 Rebalancing actions
- 📊 Daily/weekly reports
- ⚠️ Strategy validation failures

### Database Monitoring
- SyncStatus table (data freshness)
- BalanceHistory (equity tracking)
- Trade table (execution log)
- StrategyParameters (active strategies)

---

## Troubleshooting Flow

### Task Not Running
```
1. Check Celery worker: celery -A web.django inspect active
2. Check Beat schedule: celery -A web.django inspect scheduled
3. Check Redis: redis-cli ping
4. Review logs: tail -f celery.log
```

### Task Failing
```
1. Get task result: AsyncResult('task-id').traceback
2. Check database connection
3. Verify external APIs (Binance, Discord)
4. Review error logs
5. Manual retry if transient error
```

### Missing Data
```
1. Check sync_market_data_task status
2. Verify Binance API connectivity
3. Check SyncStatus table
4. Run manual sync: sync_market_data_task.delay()
```

---

## Performance Optimization

### Task Execution Times
- **Fast (< 5s):** sync_market_data, update_positions, check_stop_loss
- **Medium (5-15s):** generate_signals, update_indicators, calculate_metrics
- **Slow (> 15s):** run_backtest, generate_report

### Database Optimization
- Indexes on (time, symbol, timeframe)
- TimescaleDB compression for old data
- Regular VACUUM operations
- Connection pooling

### Redis Optimization
- Monitor queue sizes: `celery -A web.django inspect active_queues`
- Set result expiration: `result_expires = 3600`
- Clear old results periodically

---

## Best Practices

### Task Design
✓ Keep tasks idempotent (safe to retry)  
✓ Use short timeouts for external APIs  
✓ Log all important actions  
✓ Return standardized dictionaries  
✓ Handle all exceptions gracefully  

### Scheduling
✓ Critical tasks every 5 minutes  
✓ Analysis tasks every 30 minutes  
✓ Heavy tasks during low-traffic hours  
✓ Stagger related tasks (e.g., metrics at 11 PM, report at 11:30 PM)  

### Monitoring
✓ Watch task failure rates in Flower  
✓ Set up Discord alerts for critical failures  
✓ Monitor database growth  
✓ Track task execution times  
✓ Review logs daily  

---

**Last Updated:** October 18, 2025  
**Version:** 1.0.0
