# Mock Data Mode - Testing Without Backend

## Overview

The FKS Trading Terminal includes a **Mock Data Mode** that allows you to test and develop the UI without needing a running backend server. This is perfect for:

- UI development and testing
- Demos and presentations
- Offline development
- Learning the application

---

## Quick Start

### Enable Mock Data Mode

Mock data mode is **enabled by default** in development. The app will use realistic sample data for positions and orders.

To explicitly control it, update the `AppConfig` in `DatabaseModule.kt`:

```kotlin
// Mock data enabled (default)
single {
    AppConfig.development(useMockData = true)
}

// Real API (requires backend running)
single {
    AppConfig.development(useMockData = false)
}
```

---

## Configuration Options

### AppConfig Presets

**1. Development with Mock Data (Default)**
```kotlin
AppConfig.development(useMockData = true)
```
- Uses localhost endpoints
- Mock data for positions and orders
- Full logging enabled
- Perfect for UI testing

**2. Development with Real API**
```kotlin
AppConfig.development(useMockData = false)
```
- Connects to `http://localhost:8000`
- Requires backend server running
- Real API calls

**3. Mock Only**
```kotlin
AppConfig.mockOnly()
```
- Forces mock data regardless of environment
- No network calls attempted
- Fastest startup

**4. Production**
```kotlin
AppConfig.production(authToken = "your-token")
```
- Connects to `https://api.fkstrading.xyz`
- No mock data
- Analytics enabled
- Requires authentication

**5. Staging**
```kotlin
AppConfig.staging(authToken = "your-token")
```
- Connects to staging environment
- Real API with test data
- Logging enabled

---

## Mock Data Included

### Positions (10 samples)

**Open Positions (6):**
- BTC/USD - Long, +$1,250 profit
- ETH/USD - Short, -$1,500 loss
- SOL/USD - Long, +$125 profit
- ADA/USD - Long, +$20 profit
- GOOGL - Short, +$40 profit
- XRP/USD - Long, +$40 profit

**Closed Positions (4):**
- AAPL - Big win: +$1,500
- TSLA - Small loss: -$250
- DOGE/USD - Win: +$100
- MSFT - Loss: -$150

**Portfolio Metrics:**
- Total P&L: Varies based on current prices
- Win Rate: ~60%
- Open Positions: 6
- Closed Positions: 4

### Orders (12 samples)

**Active Orders (5):**
- BTC/USD - Limit buy @ $46,000 (Open)
- ETH/USD - Limit sell @ $3,100 (Partially filled)
- SOL/USD - Stop buy @ $105 (Open)
- XRP/USD - Stop-limit sell (Open)
- MSFT - Limit sell @ $385 (Open)

**Completed Orders (7):**
- AAPL - Market buy (Filled)
- TSLA - Limit sell (Cancelled)
- ADA/USD - Limit buy (Pending)
- DOGE/USD - Market sell (Filled)
- GOOGL - Limit buy (Rejected)
- BTC/USD - Limit buy (Filled)
- ETH/USD - Market buy (Pending)

**Order Metrics:**
- Active Orders: 5
- Fill Rate: Varies
- Total Volume: Realistic amounts
- Completed: 7

---

## Mock Data Features

### 1. Realistic Data
- Actual crypto and stock symbols
- Realistic prices and quantities
- Proper P&L calculations
- Valid timestamps

### 2. Network Simulation
- Simulated network delays (50-200ms)
- Realistic response times
- Proper async behavior

### 3. Data Persistence
- Changes persist in memory during session
- Create new orders
- Close positions
- Delete items
- All CRUD operations supported

### 4. Dynamic Updates
Mock data sources include methods for simulating real-time updates:

```kotlin
// Simulate price changes
mockPositionDataSource.simulatePriceUpdate()

// Simulate order fills
mockOrderDataSource.simulateOrderUpdate()
```

---

## Testing Workflows

### Test Portfolio Management

1. Launch app (mock mode enabled by default)
2. Navigate to Portfolio screen
3. View 10 sample positions
4. Filter by open/closed
5. Sort by P&L, date, symbol
6. Tap position for details
7. Close an open position
8. Delete a closed position
9. Verify metrics update

### Test Order Management

1. Navigate to Orders screen
2. View 12 sample orders
3. Filter active only
4. Create new order:
   - Symbol: "BTC/USD"
   - Side: BUY
   - Type: LIMIT
   - Quantity: 1.0
   - Price: 50000
5. View order in list
6. Cancel an active order
7. Delete a completed order

### Test Dashboard

1. View portfolio summary
2. Check total P&L (should show realistic value)
3. See recent positions (top 3)
4. Verify quick actions work
5. Check market status indicator

---

## Customizing Mock Data

### Add Your Own Positions

Edit `MockPositionDataSource.kt`:

```kotlin
private fun generateSamplePositions(): List<Position> {
    val now = Clock.System.now()
    
    return listOf(
        // Your custom position
        Position(
            positionId = "POS-CUSTOM-001",
            symbol = "YOUR/SYMBOL",
            side = OrderSide.BUY,
            quantity = 100.0,
            entryPrice = 1000.0,
            currentPrice = 1050.0,
            status = PositionStatus.OPEN,
            openedAt = now.minus(1.days),
            unrealizedPnL = 5000.0
        ),
        // ... more positions
    )
}
```

### Add Your Own Orders

Edit `MockOrderDataSource.kt`:

```kotlin
private fun generateSampleOrders(): List<Order> {
    val now = Clock.System.now()
    
    return listOf(
        // Your custom order
        Order(
            orderId = "ORD-CUSTOM-001",
            symbol = "YOUR/SYMBOL",
            side = OrderSide.BUY,
            orderType = OrderType.LIMIT,
            quantity = 10.0,
            price = 100.0,
            status = OrderStatus.OPEN,
            timestamp = now.minus(1.hours)
        ),
        // ... more orders
    )
}
```

---

## Switching Modes

### At Compile Time

Update `DatabaseModule.kt`:

```kotlin
val databaseModule = module {
    single {
        // Change this line:
        AppConfig.development(useMockData = true)  // Mock mode
        // Or:
        AppConfig.development(useMockData = false) // Real API
    }
    // ...
}
```

### At Runtime (Future Enhancement)

Could add a settings toggle:

```kotlin
// In Settings UI
Switch(
    checked = useMockData,
    onCheckedChange = { 
        // Update config
        // Restart data sources
    }
)
```

---

## Mock vs Real API

| Feature | Mock Data | Real API |
|---------|-----------|----------|
| **Network Required** | No | Yes |
| **Backend Required** | No | Yes |
| **Data Persistence** | Session only | Database |
| **Real-time Updates** | Simulated | WebSocket |
| **Performance** | Instant | Network latency |
| **Data Volume** | 10-20 items | Unlimited |
| **Best For** | Development, demos | Production, testing |

---

## Troubleshooting

### Mock Data Not Showing

**Problem:** Empty screens despite mock mode enabled

**Solution:**
1. Check `DatabaseModule.kt` has `useMockData = true`
2. Verify `MockPositionDataSource` and `MockOrderDataSource` are being used
3. Check console for errors
4. Try clean rebuild: `./gradlew clean build`

### Data Doesn't Persist

**Problem:** Changes lost on app restart

**Solution:**
This is expected behavior in mock mode. Mock data resets on each app launch. For persistence:
1. Switch to real API mode
2. Connect to backend with database
3. Or implement local-only mode with SQLDelight only

### Network Errors in Mock Mode

**Problem:** Getting network errors with mock data

**Solution:**
1. Ensure `useMockData = true` in config
2. Check data sources are registered correctly in DI
3. Verify no API calls are being made (check logs)

---

## Best Practices

### 1. Use Mock Data For
- ✅ UI development
- ✅ Testing layouts and flows
- ✅ Demos and presentations
- ✅ Offline development
- ✅ Unit testing UI components

### 2. Use Real API For
- ✅ Integration testing
- ✅ Performance testing
- ✅ End-to-end testing
- ✅ Production deployment
- ✅ Staging verification

### 3. Development Workflow
1. Start with mock data for rapid UI iteration
2. Test with real API for integration
3. Deploy to staging for QA
4. Deploy to production with real data

---

## Feature Flags

Combine with feature flags for controlled rollouts:

```kotlin
val featureFlags = FeatureFlags(
    enableRealTimeUpdates = false,  // Disable in mock mode
    enableCharts = true,            // Test UI
    enableTradeHistory = true,
    enableRiskAnalytics = true
)
```

---

## Examples

### Example 1: Pure Mock Development

```kotlin
// DatabaseModule.kt
single { AppConfig.mockOnly() }

// Features:
// - No network calls
// - Instant startup
// - 100% offline
// - Perfect for UI work
```

### Example 2: Hybrid Mode

```kotlin
// DatabaseModule.kt
single {
    val useMock = System.getenv("USE_MOCK_DATA") == "true"
    AppConfig.development(useMockData = useMock)
}

// Run with mock: USE_MOCK_DATA=true ./gradlew run
// Run with API: ./gradlew run
```

### Example 3: Conditional by Platform

```kotlin
// Platform-specific module
val platformModule = module {
    single {
        when (getPlatform()) {
            Platform.IOS -> AppConfig.mockOnly()
            Platform.Android -> AppConfig.development(useMockData = false)
            Platform.Desktop -> AppConfig.development(useMockData = true)
            Platform.Web -> AppConfig.production()
        }
    }
}
```

---

## Next Steps

1. **Review Sample Data** - Check `MockPositionDataSource.kt` and `MockOrderDataSource.kt`
2. **Customize** - Add your own test scenarios
3. **Test Workflows** - Follow the testing workflows above
4. **Switch to Real API** - When ready, update config
5. **Deploy** - Use production config for deployment

---

## Resources

- **Config File**: `shared/src/.../config/AppConfig.kt`
- **Mock Sources**: `shared/src/.../data/mock/`
- **DI Setup**: `shared/src/.../di/DatabaseModule.kt`
- **Quick Start**: `docs/PHASE_1_QUICK_START.md`
- **Implementation Guide**: `docs/PHASE_1_IMPLEMENTATION.md`

---

**Mock Data Mode Status:** ✅ Fully Implemented  
**Sample Data:** 10 Positions + 12 Orders  
**Ready for Testing:** Yes  

*Last Updated: 2025-01-20*