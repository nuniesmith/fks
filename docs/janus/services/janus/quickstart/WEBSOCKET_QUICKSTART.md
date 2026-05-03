# WebSocket Integration Quickstart Guide

## Overview

This guide shows you how to integrate and use the JANUS WebSocket real-time streaming system for signals, risk alerts, portfolio updates, and market data.

---

## Table of Contents

1. [Server Setup](#server-setup)
2. [Client Connection](#client-connection)
3. [Message Types](#message-types)
4. [Subscription Management](#subscription-management)
5. [Data Service Integration](#data-service-integration)
6. [Client Examples](#client-examples)
7. [Troubleshooting](#troubleshooting)

---

## Server Setup

### Basic Configuration

```rust
use janus::websocket::{
    WebSocketServer, WebSocketConfig, ClientManager, SignalBroadcaster,
    HeartbeatManager, HeartbeatConfig, DataServiceClient, DataServiceConfig
};
use std::sync::Arc;
use std::time::Duration;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Create client manager
    let client_manager = Arc::new(ClientManager::new());
    
    // Create metrics
    let metrics = Arc::new(JanusMetrics::new());
    
    // Create broadcaster
    let broadcaster = Arc::new(SignalBroadcaster::new(
        client_manager.clone(),
        metrics.clone()
    ));
    
    // Configure and start heartbeat monitoring
    let heartbeat_config = HeartbeatConfig {
        check_interval: Duration::from_secs(30),
        client_timeout: Duration::from_secs(90),
        send_pings: true,
        ping_interval: Duration::from_secs(30),
    };
    let heartbeat = Arc::new(HeartbeatManager::new(
        client_manager.clone(),
        heartbeat_config
    ));
    heartbeat.start().await?;
    
    // Configure WebSocket server
    let ws_config = WebSocketConfig {
        bind_address: "0.0.0.0:8081".to_string(),
        max_connections: 10000,
        heartbeat_interval: Duration::from_secs(30),
        client_timeout: Duration::from_secs(90),
        max_message_size: 1048576, // 1MB
        enable_compression: true,
    };
    
    // Create and start WebSocket server
    let server = WebSocketServer::new(
        ws_config,
        client_manager,
        broadcaster.clone(),
        heartbeat,
    );
    
    server.start().await?;
    
    Ok(())
}
```

### Environment Variables

```bash
# .env file
DATA_SERVICE_WS_URL=ws://localhost:8080/stream
DATA_SERVICE_HTTP_URL=http://localhost:8080
DATA_SERVICE_API_KEY=your-api-key-here

WS_BIND_ADDRESS=0.0.0.0:8081
WS_MAX_CONNECTIONS=10000
WS_HEARTBEAT_INTERVAL=30
WS_CLIENT_TIMEOUT=90
WS_MAX_MESSAGE_SIZE=1048576
WS_ENABLE_COMPRESSION=true
```

---

## Client Connection

### WebSocket URL

```
ws://localhost:8081/ws
```

### Connection Flow

1. **Connect** - Upgrade HTTP to WebSocket
2. **Receive Welcome** - Server sends welcome message
3. **Subscribe** - Send subscription preferences
4. **Stream** - Receive filtered updates
5. **Heartbeat** - Respond to ping messages
6. **Disconnect** - Clean shutdown or timeout

### Welcome Message

Upon connection, server sends:

```json
{
  "type": "welcome",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "server_version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "capabilities": ["signals", "portfolio", "risk_alerts", "market_data"]
}
```

---

## Message Types

### 1. Signal Update

Real-time trading signals:

```json
{
  "type": "signal_update",
  "signal_id": "123e4567-e89b-12d3-a456-426614174000",
  "symbol": "BTCUSD",
  "timestamp": "2024-01-15T10:30:00Z",
  "signal_type": "Entry",
  "action": "Buy",
  "confidence": 0.85,
  "entry_price": 43250.0,
  "stop_loss": 42000.0,
  "take_profit": [44000.0, 45000.0],
  "position_size": 0.5,
  "risk_reward_ratio": 2.5,
  "strategy": "momentum",
  "timeframe": "1h",
  "metadata": {}
}
```

### 2. Portfolio Update

Portfolio state changes:

```json
{
  "type": "portfolio_update",
  "timestamp": "2024-01-15T10:30:00Z",
  "portfolio_id": "portfolio-uuid",
  "total_value": 10500.0,
  "cash": 5000.0,
  "positions": [
    {
      "symbol": "BTCUSD",
      "quantity": 0.5,
      "entry_price": 42000.0,
      "current_price": 43250.0,
      "unrealized_pnl": 625.0,
      "realized_pnl": 0.0,
      "position_value": 21625.0,
      "weight": 0.45,
      "opened_at": "2024-01-15T08:00:00Z"
    }
  ],
  "unrealized_pnl": 625.0,
  "realized_pnl": 1000.0,
  "daily_pnl": 250.0,
  "daily_return": 0.025,
  "total_return": 0.05,
  "exposures": {
    "crypto": 0.45,
    "cash": 0.55
  }
}
```

### 3. Risk Alert

Risk management warnings:

```json
{
  "type": "risk_alert",
  "alert_id": "alert-uuid",
  "timestamp": "2024-01-15T10:30:00Z",
  "severity": "High",
  "alert_type": "DailyLossLimitApproaching",
  "message": "Daily loss approaching limit: -450.00 / -500.00",
  "affected_symbols": ["BTCUSD"],
  "current_value": -450.0,
  "threshold": -500.0,
  "recommended_action": "Consider reducing position sizes"
}
```

### 4. Market Data

Real-time market data:

```json
{
  "type": "market_data",
  "symbol": "BTCUSD",
  "timestamp": "2024-01-15T10:30:00Z",
  "data_type": "Candle",
  "data": {
    "interval": "1m",
    "open": 43200.0,
    "high": 43300.0,
    "low": 43150.0,
    "close": 43250.0,
    "volume": 123.45
  }
}
```

### 5. Performance Update

Performance metrics:

```json
{
  "type": "performance_update",
  "timestamp": "2024-01-15T10:30:00Z",
  "portfolio_id": "portfolio-uuid",
  "period": "daily",
  "total_return": 0.05,
  "sharpe_ratio": 1.8,
  "max_drawdown": -0.12,
  "win_rate": 0.65,
  "profit_factor": 2.1,
  "total_trades": 100,
  "winning_trades": 65,
  "losing_trades": 35,
  "average_win": 150.0,
  "average_loss": -70.0
}
```

---

## Subscription Management

### Subscribe to Signals

```json
{
  "type": "subscribe",
  "symbols": ["BTCUSD", "ETHUSDT"],
  "min_confidence": 0.7,
  "signal_types": ["Entry", "Exit"],
  "portfolio_updates": true,
  "risk_alerts": true
}
```

### Subscribe to All Symbols

```json
{
  "type": "subscribe",
  "symbols": null,
  "min_confidence": 0.8,
  "signal_types": null,
  "portfolio_updates": true,
  "risk_alerts": true
}
```

### Unsubscribe

```json
{
  "type": "unsubscribe",
  "symbols": ["ETHUSDT"]
}
```

---

## Data Service Integration

### Configure Data Service Client

```rust
use janus::websocket::{DataServiceClient, DataServiceConfig, MessageHandler};

// Create configuration
let config = DataServiceConfig {
    ws_url: "ws://data-service:8080/stream".to_string(),
    http_url: "http://data-service:8080".to_string(),
    api_key: Some("your-api-key".to_string()),
    reconnect_policy: ReconnectPolicy {
        max_retries: Some(10),
        initial_delay: Duration::from_secs(1),
        max_delay: Duration::from_secs(60),
        backoff_multiplier: 2.0,
    },
    connection_timeout: Duration::from_secs(10),
    heartbeat_interval: Duration::from_secs(30),
};

// Create message handler
struct MyHandler {
    broadcaster: Arc<SignalBroadcaster>,
}

#[async_trait::async_trait]
impl MessageHandler for MyHandler {
    async fn on_candle(&self, candle: CandleData) {
        // Process candle and broadcast to clients
        let market_data = MarketDataUpdate {
            symbol: candle.symbol.clone(),
            timestamp: candle.timestamp,
            data_type: MarketDataType::Candle,
            data: serde_json::to_value(&candle).unwrap(),
        };
        
        self.broadcaster.broadcast_market_data(market_data).await.ok();
    }
    
    async fn on_tick(&self, tick: TickData) {
        // Handle tick data
    }
    
    // ... implement other handlers
}

// Create and start client
let handler = Arc::new(MyHandler { broadcaster });
let client = Arc::new(DataServiceClient::new(config, handler));
client.connect().await?;
client.start().await?;

// Subscribe to symbols
client.subscribe_symbols(vec![
    "BTCUSD".to_string(),
    "ETHUSDT".to_string(),
]).await?;
```

### Fetch Historical Data

```rust
use chrono::Utc;

let candles = data_client.get_historical_candles(
    "BTCUSD",
    Utc::now() - chrono::Duration::hours(24),
    Utc::now(),
    "1m"
).await?;

for candle in candles {
    println!("Candle: {:?}", candle);
}
```

---

## Client Examples

### JavaScript/TypeScript

```javascript
const ws = new WebSocket('ws://localhost:8081/ws');

ws.onopen = () => {
    console.log('Connected to JANUS');
    
    // Subscribe to signals
    ws.send(JSON.stringify({
        type: 'subscribe',
        symbols: ['BTCUSD', 'ETHUSDT'],
        min_confidence: 0.7,
        signal_types: ['Entry'],
        portfolio_updates: true,
        risk_alerts: true
    }));
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    switch (message.type) {
        case 'welcome':
            console.log('Session ID:', message.session_id);
            break;
            
        case 'signal_update':
            console.log('Signal:', message.symbol, message.action);
            handleSignal(message);
            break;
            
        case 'risk_alert':
            console.warn('Risk Alert:', message.severity, message.message);
            break;
            
        case 'ping':
            ws.send(JSON.stringify({ type: 'pong' }));
            break;
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Disconnected from JANUS');
    // Implement reconnection logic
};

function handleSignal(signal) {
    // Process signal
    if (signal.action === 'Buy' && signal.confidence > 0.8) {
        console.log(`Strong buy signal for ${signal.symbol}`);
        // Execute trade
    }
}
```

### Python

```python
import asyncio
import json
import websockets

async def connect_janus():
    uri = "ws://localhost:8081/ws"
    
    async with websockets.connect(uri) as ws:
        # Receive welcome message
        welcome = await ws.recv()
        print(f"Welcome: {welcome}")
        
        # Subscribe
        subscribe_msg = {
            "type": "subscribe",
            "symbols": ["BTCUSD", "ETHUSDT"],
            "min_confidence": 0.7,
            "signal_types": ["Entry", "Exit"],
            "portfolio_updates": True,
            "risk_alerts": True
        }
        await ws.send(json.dumps(subscribe_msg))
        
        # Listen for messages
        while True:
            message = await ws.recv()
            data = json.loads(message)
            
            if data["type"] == "signal_update":
                handle_signal(data)
            elif data["type"] == "risk_alert":
                handle_alert(data)
            elif data["type"] == "ping":
                await ws.send(json.dumps({"type": "pong"}))

def handle_signal(signal):
    print(f"Signal: {signal['symbol']} - {signal['action']} @ {signal['confidence']}")

def handle_alert(alert):
    print(f"Risk Alert: {alert['severity']} - {alert['message']}")

if __name__ == "__main__":
    asyncio.run(connect_janus())
```

### Rust Client

```rust
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::{SinkExt, StreamExt};
use serde_json::json;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let (ws_stream, _) = connect_async("ws://localhost:8081/ws").await?;
    let (mut write, mut read) = ws_stream.split();
    
    // Subscribe
    let subscribe = json!({
        "type": "subscribe",
        "symbols": ["BTCUSD", "ETHUSDT"],
        "min_confidence": 0.7,
        "signal_types": ["Entry"],
        "portfolio_updates": true,
        "risk_alerts": true
    });
    
    write.send(Message::Text(subscribe.to_string())).await?;
    
    // Listen for messages
    while let Some(msg) = read.next().await {
        match msg? {
            Message::Text(text) => {
                let data: serde_json::Value = serde_json::from_str(&text)?;
                
                match data["type"].as_str() {
                    Some("signal_update") => {
                        println!("Signal: {}", data["symbol"]);
                    }
                    Some("ping") => {
                        let pong = json!({"type": "pong"});
                        write.send(Message::Text(pong.to_string())).await?;
                    }
                    _ => {}
                }
            }
            Message::Close(_) => break,
            _ => {}
        }
    }
    
    Ok(())
}
```

---

## Broadcasting from Server

### Broadcast Signal

```rust
use janus::websocket::{SignalUpdate, SignalType, Action};

let signal = SignalUpdate {
    signal_id: Uuid::new_v4(),
    symbol: "BTCUSD".to_string(),
    timestamp: Utc::now(),
    signal_type: SignalType::Entry,
    action: Action::Buy,
    confidence: 0.85,
    entry_price: 43250.0,
    stop_loss: Some(42000.0),
    take_profit: vec![44000.0, 45000.0],
    position_size: Some(0.5),
    risk_reward_ratio: Some(2.5),
    strategy: "momentum".to_string(),
    timeframe: "1h".to_string(),
    metadata: HashMap::new(),
};

broadcaster.broadcast_signal(signal).await?;
```

### Broadcast Risk Alert

```rust
use janus::websocket::{RiskAlert, AlertSeverity, RiskAlertType};

let alert = RiskAlert {
    alert_id: Uuid::new_v4(),
    timestamp: Utc::now(),
    severity: AlertSeverity::High,
    alert_type: RiskAlertType::DailyLossLimitApproaching,
    message: "Daily loss approaching limit".to_string(),
    affected_symbols: vec!["BTCUSD".to_string()],
    current_value: -450.0,
    threshold: -500.0,
    recommended_action: Some("Reduce position sizes".to_string()),
};

broadcaster.broadcast_risk_alert(alert).await?;
```

---

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to WebSocket
**Solution**:
- Verify server is running: `netstat -an | grep 8081`
- Check firewall settings
- Ensure correct URL format: `ws://` not `wss://` for non-TLS

### No Messages Received

**Problem**: Connected but not receiving messages
**Solution**:
- Verify subscription was sent and acknowledged
- Check subscription filters (min_confidence, symbols)
- Monitor server logs for errors
- Ensure broadcaster is initialized

### Connection Timeout

**Problem**: Connection drops after 90 seconds
**Solution**:
- Implement ping/pong handling in client
- Respond to server ping messages
- Adjust `client_timeout` in server config

### High Latency

**Problem**: Messages arrive with significant delay
**Solution**:
- Check network latency: `ping server-host`
- Reduce message size (use compression)
- Optimize subscription filters
- Scale horizontally if needed

### Memory Issues

**Problem**: Server memory growing over time
**Solution**:
- Check for stale connections: `client_manager.client_count()`
- Verify heartbeat manager is running
- Reduce `max_connections` if needed
- Monitor metrics: `ws_connections_active`

---

## Monitoring

### Key Metrics

```rust
// Connection metrics
ws_connections_total
ws_connections_active
ws_messages_sent_total
ws_errors_total

// Performance metrics
ws_message_latency
ws_broadcast_duration

// Data service metrics
data_service_connection_status
data_service_reconnections_total
```

### Health Check

```bash
curl http://localhost:8081/health
```

### Metrics Endpoint

```bash
curl http://localhost:8081/metrics
```

---

## Best Practices

1. **Always handle ping/pong** - Respond to server pings to maintain connection
2. **Implement reconnection logic** - Handle disconnections gracefully
3. **Use subscription filters** - Reduce bandwidth by filtering at source
4. **Monitor connection count** - Track active connections in production
5. **Enable compression** - Reduce bandwidth usage for large message volumes
6. **Validate messages** - Always validate incoming message structure
7. **Rate limiting** - Implement client-side rate limiting to avoid overwhelming server
8. **Error handling** - Handle all message types including errors
9. **Graceful shutdown** - Close connections properly before exiting

---

## Security Notes

- **TLS/SSL**: Use `wss://` in production with valid certificates
- **Authentication**: JWT tokens will be added in Week 10
- **API Keys**: Store securely, never commit to version control
- **Rate Limiting**: Will be implemented in Week 10
- **Input Validation**: All client messages are validated server-side

---

## Performance Tips

1. **Batch updates**: Group related updates when possible
2. **Use binary protocol**: Consider switching to binary for high-frequency data
3. **Compression**: Enable for text-heavy messages
4. **Connection pooling**: Reuse connections when possible
5. **Selective subscriptions**: Only subscribe to needed symbols

---

## Support

For issues or questions:
- Check server logs: `journalctl -u janus -f`
- Review metrics dashboard
- Enable debug logging: `RUST_LOG=debug`
- Consult Week 9 documentation

---

**Version**: 1.0.0 (Week 9)
**Last Updated**: 2024
**Status**: Production Ready (pending server.rs implementation)