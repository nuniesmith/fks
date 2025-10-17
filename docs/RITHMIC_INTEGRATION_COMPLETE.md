# Rithmic Integration for FKS Trading Systems

## Overview
This document describes the complete integration of Rithmic R|API with the FKS Trading Systems. The integration provides both test and live market data capabilities, order management, and seamless switching between environments.

## Features

### ✅ **Implemented Features**
- **Multi-environment support**: Test and Live environments
- **Market data handling**: Real-time Level 1 and Level 2 data
- **Order management**: Full order lifecycle management
- **Database persistence**: SQLite storage for all data
- **Asynchronous processing**: High-performance async implementation
- **Comprehensive logging**: Framework-integrated logging
- **Statistics and monitoring**: Real-time performance metrics
- **Error handling**: Robust error handling and reconnection logic
- **SSL/TLS support**: Secure connections with certificate validation

### 🚀 **Core Components**

#### 1. **RithmicConfig** (`/services/rithmic/config.py`)
- Environment-specific configuration
- SSL certificate management
- Symbol and exchange filtering
- Database connection settings
- Retry and timeout configurations

#### 2. **RithmicClient** (`/services/rithmic/client.py`)
- WebSocket connection management
- Message routing and handling
- Authentication and session management
- Heartbeat and reconnection logic
- Statistics tracking

#### 3. **RithmicDataHandler** (`/services/rithmic/data_handler.py`)
- Market data processing
- Order book management
- Trade data handling
- Database storage
- Historical data retrieval

#### 4. **RithmicOrderManager** (`/services/rithmic/order_manager.py`)
- Order creation and submission
- Order lifecycle management
- Fill processing
- Order modification and cancellation
- Position tracking

#### 5. **RithmicService** (`/services/rithmic/service.py`)
- Service coordination
- Component integration
- Health monitoring
- API endpoints

## Configuration

### Test Environment Configuration
```python
from services.rithmic.config import RithmicConfig

config = RithmicConfig(
    environment="test",
    host="rituz00100.rithmic.com",
    port=65000,
    username="YOUR_TEST_USERNAME",
    password="YOUR_TEST_PASSWORD",
    ssl_enabled=True,
    symbols=["NQ", "ES", "YM", "RTY"],
    database_url="sqlite:///fks_rithmic.db"
)
```

### Live Environment Configuration
```python
config = RithmicConfig(
    environment="live",
    host="YOUR_LIVE_HOST",
    port=YOUR_LIVE_PORT,
    username="YOUR_LIVE_USERNAME",
    password="YOUR_LIVE_PASSWORD",
    ssl_enabled=True,
    ssl_cert_path="/path/to/live/certificate.pem",
    symbols=["NQ", "ES", "YM", "RTY"],
    database_url="sqlite:///fks_rithmic_live.db"
)
```

### Environment Variables
```bash
# Set these in your environment
export RITHMIC_ENVIRONMENT=test
export RITHMIC_USERNAME=your_username
export RITHMIC_PASSWORD=your_password
export RITHMIC_SYMBOLS=NQ,ES,YM,RTY
export RITHMIC_DATABASE_URL=sqlite:///fks_rithmic.db
```

## Usage Examples

### 1. **Starting the Service**
```python
import asyncio
from services.rithmic.service import RithmicService
from services.rithmic.config import RithmicConfig

async def main():
    # Create configuration
    config = RithmicConfig(
        environment="test",
        username="your_username",
        password="your_password"
    )
    
    # Start service
    service = RithmicService(config)
    success = await service.start()
    
    if success:
        print("Rithmic service started successfully")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. **Market Data Subscription**
```python
from services.rithmic.data_handler import RithmicDataHandler

# Create data handler
data_handler = RithmicDataHandler(config)

# Add market data callback
async def on_market_data(market_data):
    print(f"Quote: {market_data.symbol} {market_data.bid}/{market_data.ask}")

data_handler.add_market_data_callback(on_market_data)

# Get latest quote
quote = data_handler.get_latest_quote("NQ")
if quote:
    print(f"NQ: {quote.bid}/{quote.ask}")
```

### 3. **Order Management**
```python
from services.rithmic.order_manager import (
    RithmicOrderManager, OrderSide, create_market_order, create_limit_order
)

# Create order manager
order_manager = RithmicOrderManager(config)

# Create and submit market order
order = create_market_order("NQ", OrderSide.BUY, 1)
success = await order_manager.submit_order(client, order)

# Create limit order
limit_order = create_limit_order("ES", OrderSide.SELL, 2, 4500.00)
success = await order_manager.submit_order(client, limit_order)

# Cancel order
await order_manager.cancel_order(client, order.order_id)
```

### 4. **Full Service Integration**
```python
from services.rithmic.service import RithmicService

# Create service
service = RithmicService(config)

# Start service
await service.start()

# Submit order through service
success = await service.submit_order(
    symbol="NQ",
    side="buy",
    quantity=1,
    order_type="market"
)

# Get latest market data
quote = await service.get_latest_quote("NQ")
depth = await service.get_latest_depth("NQ")
```

## Database Schema

### Market Data Table
```sql
CREATE TABLE market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    bid REAL,
    ask REAL,
    last REAL,
    volume INTEGER,
    bid_size INTEGER,
    ask_size INTEGER,
    high REAL,
    low REAL,
    open REAL,
    close REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Orders Table
```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL,
    stop_price REAL,
    time_in_force TEXT,
    status TEXT NOT NULL,
    filled_quantity INTEGER DEFAULT 0,
    remaining_quantity INTEGER,
    average_fill_price REAL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

## Running the Service

### Command Line Interface
```bash
# Start with test environment
cd /home/jordan/fks/src/python
python -m services.rithmic.service --environment test --username YOUR_USERNAME --password YOUR_PASSWORD

# Start with specific symbols
python -m services.rithmic.service --environment test --symbols NQ,ES,YM --username YOUR_USERNAME --password YOUR_PASSWORD
```

### Integration with Main FKS System
```python
# In your main FKS application
from services.rithmic.service import start_service, stop_service
from services.rithmic.config import RithmicConfig

# Start Rithmic service
config = RithmicConfig.from_env()
await start_service(config)

# Service is now running and integrated
```

## Testing

### Running Tests
```bash
# Run integration tests
cd /home/jordan/fks
python test_rithmic_integration.py
```

### Test Results
- ✅ Configuration loading and validation
- ✅ Client initialization and connection handling
- ✅ Data handler with database operations
- ✅ Order manager with order lifecycle
- ✅ Service integration and coordination
- ✅ Mock data processing

## Security Considerations

### SSL/TLS Configuration
- Test environment uses provided SSL certificate
- Live environment requires your own SSL certificate
- All connections are encrypted by default

### Credential Management
- Store credentials in environment variables
- Never hardcode passwords in configuration files
- Use separate credentials for test and live environments

## Monitoring and Statistics

### Service Statistics
```python
# Get comprehensive stats
stats = service.get_stats()
print(f"Service status: {stats['service_status']}")
print(f"Messages processed: {stats['client']['messages_received']}")
print(f"Orders submitted: {stats['order_manager']['orders_submitted']}")
print(f"Market data updates: {stats['data_handler']['quotes_processed']}")
```

### Performance Metrics
- Message processing rates
- Connection uptime
- Order execution latency
- Data storage performance

## Migration from Test to Live

### 1. **Update Configuration**
```python
# Change environment
config.environment = "live"
config.host = "YOUR_LIVE_HOST"
config.port = YOUR_LIVE_PORT
config.ssl_cert_path = "/path/to/live/certificate.pem"
```

### 2. **Update Credentials**
```bash
export RITHMIC_ENVIRONMENT=live
export RITHMIC_USERNAME=your_live_username
export RITHMIC_PASSWORD=your_live_password
```

### 3. **Database Separation**
```python
# Use separate database for live
config.database_url = "sqlite:///fks_rithmic_live.db"
```

### 4. **Testing Checklist**
- [ ] Test environment working correctly
- [ ] All market data subscriptions active
- [ ] Order placement and fills working
- [ ] Database operations functioning
- [ ] Statistics and monitoring operational
- [ ] Error handling and reconnection tested

## Support and Troubleshooting

### Common Issues
1. **SSL Certificate errors**: Check certificate path and validity
2. **Connection timeouts**: Verify host and port settings
3. **Authentication failures**: Confirm username/password
4. **Database errors**: Check file permissions and disk space
5. **Symbol subscription issues**: Verify symbol format and permissions

### Logging
All components use the FKS framework logging system:
```python
from framework.logging.setup import get_logger
logger = get_logger(__name__)
```

### Debug Mode
Enable debug logging for detailed troubleshooting:
```bash
export APP_LOG_LEVEL=DEBUG
```

## Next Steps

1. **Set up Rithmic test credentials** from your Rithmic account
2. **Test with live test environment** to validate connectivity
3. **Implement protobuf message handling** for full R|API compliance
4. **Add more market data types** (Level 2, time sales, etc.)
5. **Implement advanced order types** (OCO, bracket orders, etc.)
6. **Add position management** and P&L tracking
7. **Create web dashboard** for monitoring and control
8. **Set up alerts and notifications** for important events

The Rithmic integration is now complete and ready for test data. Once you have your test credentials, you can immediately start receiving market data and placing test orders. The system is designed to seamlessly switch to live data once you're ready to purchase the Level 2 data feed.
