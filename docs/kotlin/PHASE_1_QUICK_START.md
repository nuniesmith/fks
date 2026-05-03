# Phase 1 Quick Start Guide

## 🚀 Getting Started in 5 Minutes

This guide will get you up and running with the new Portfolio and Orders features.

---

## Prerequisites

- JDK 21 installed
- Project cloned and dependencies synced
- Terminal access

---

## Quick Start

### 1. Run the Application

```bash
cd fks/src/clients
./gradlew :composeApp:run
```

The desktop app will launch showing the **Dashboard**.

### 2. Navigation

**Bottom Navigation Bar** (on mobile/compact screens):
- 📊 **Dashboard** - Portfolio overview
- 💼 **Portfolio** - View all positions
- 🛒 **Orders** - Manage orders
- 📈 **Signals** - Real-time trading signals

**Top App Bar**:
- ⚙️ **Settings** - Strategy configurations

---

## Feature Overview

### Dashboard Screen

**What you'll see:**
- Total P&L with color coding (green = profit, red = loss)
- Open/Closed position counts
- Win rate percentage
- Recent positions preview
- Quick action buttons
- Market status

**Actions:**
- Tap "Portfolio" → View all positions
- Tap "Orders" → View all orders
- Tap "Signals" → View real-time signals
- Tap "View All" → Navigate to detailed screens

---

### Portfolio Screen

**What you'll see:**
- Portfolio metrics summary card
  - Total P&L
  - Unrealized/Realized P&L
  - Win rate
  - Open/Closed counts
- List of positions with:
  - Symbol and side (BUY/SELL)
  - Entry and current price
  - Quantity
  - P&L and percentage
  - Stop-loss and take-profit levels

**Actions:**
- 🔍 **Filter** - Show open/closed only
- 🔃 **Refresh** - Reload from server
- 📊 **Sort** - By date, P&L, or symbol
- 👁️ **View Details** - Tap any position
- ❌ **Close Position** - Exit an open position
- 🗑️ **Delete** - Remove closed position

**Filters Available:**
- Open Only
- Closed Only
- Sort by: Newest, Oldest, P&L, Symbol

---

### Orders Screen

**What you'll see:**
- Order metrics summary card
  - Active orders count
  - Filled orders count
  - Fill rate percentage
  - Total volume
- List of orders with:
  - Symbol and side (BUY/SELL)
  - Order type (MARKET, LIMIT, STOP)
  - Status badge
  - Price and quantity
  - Fill progress (for partial fills)

**Actions:**
- ➕ **New Order** - Create new order (FAB button)
- 🔍 **Filter** - Show active only
- 🔃 **Refresh** - Reload from server
- 📊 **Sort** - By date, symbol, or quantity
- 👁️ **View Details** - Tap any order
- ❌ **Cancel** - Cancel active order
- 🗑️ **Delete** - Remove completed order

**Creating an Order:**
1. Tap the "New Order" floating action button
2. Fill in the form:
   - **Symbol**: e.g., "BTC/USD"
   - **Side**: BUY or SELL
   - **Type**: MARKET, LIMIT, or STOP
   - **Quantity**: Amount to trade
   - **Price**: Limit price (for LIMIT orders)
   - **Stop Price**: Trigger price (for STOP orders)
3. Tap "Create Order"

**Order Statuses:**
- 🟡 **PENDING** - Order submitted
- 🔵 **OPEN** - Order active in market
- 🟣 **PARTIAL** - Partially filled
- 🟢 **FILLED** - Fully executed
- ⚪ **CANCELLED** - User cancelled
- 🔴 **REJECTED** - Exchange rejected
- ⚪ **EXPIRED** - Time expired

---

## ViewModel Reference

### PortfolioViewModel

**Inject with Koin:**
```kotlin
val viewModel: PortfolioViewModel = koinInject()
```

**Main Functions:**
```kotlin
// Refresh from server
viewModel.refresh()

// Close a position
viewModel.closePosition(positionId)

// Delete a position
viewModel.deletePosition(positionId)

// Update filter
viewModel.updateFilter(PositionFilter(...))

// Toggle filters
viewModel.toggleShowOpenOnly()
viewModel.toggleShowClosedOnly()
viewModel.showAllPositions()

// Search
viewModel.setSearchQuery("BTC")

// Sort
viewModel.updateSortOption(SortOption.PNL_DESC)
```

**State Flows:**
```kotlin
val uiState: StateFlow<PortfolioUiState>
val filterState: StateFlow<PositionFilter>
val portfolioMetrics: StateFlow<PortfolioMetrics>
```

---

### OrdersViewModel

**Inject with Koin:**
```kotlin
val viewModel: OrdersViewModel = koinInject()
```

**Main Functions:**
```kotlin
// Create order
viewModel.createOrder(OrderRequest(...))

// Cancel order
viewModel.cancelOrder(orderId)

// Delete order
viewModel.deleteOrder(orderId)

// Refresh
viewModel.refresh()

// Filter & sort
viewModel.updateFilter(OrderFilter(...))
viewModel.toggleActiveOnly()
viewModel.updateSortOption(OrderSortOption.DATE_DESC)
```

**State Flows:**
```kotlin
val uiState: StateFlow<OrdersUiState>
val filterState: StateFlow<OrderFilter>
val orderMetrics: StateFlow<OrderMetrics>
val orderCreationState: StateFlow<OrderCreationState>
```

---

## Data Models Reference

### Position

```kotlin
data class Position(
    val positionId: String,
    val symbol: String,
    val side: OrderSide,           // BUY or SELL
    val quantity: Double,
    val entryPrice: Double,
    val currentPrice: Double,
    val stopLoss: Double?,
    val takeProfit: Double?,
    val status: PositionStatus,    // OPEN or CLOSED
    val unrealizedPnL: Double,
    val realizedPnL: Double,
    // ... more fields
)
```

**Useful Methods:**
```kotlin
position.isOpen()
position.isClosed()
position.isLong()
position.isShort()
position.getTotalPnL()
position.getPnLPercentage()
position.calculateUnrealizedPnL(currentPrice)
```

---

### Order

```kotlin
data class Order(
    val orderId: String,
    val symbol: String,
    val side: OrderSide,           // BUY or SELL
    val orderType: OrderType,      // MARKET, LIMIT, STOP, STOP_LIMIT
    val quantity: Double,
    val price: Double?,
    val stopPrice: Double?,
    val status: OrderStatus,
    val filledQuantity: Double,
    val averageFillPrice: Double?,
    // ... more fields
)
```

**Useful Methods:**
```kotlin
order.isActive()
order.isComplete()
order.isFilled()
order.getRemainingQuantity()
order.getFillPercentage()
order.getTotalValue()
```

---

## Common Tasks

### Task 1: Display Portfolio Summary

```kotlin
@Composable
fun MyPortfolioSummary() {
    val viewModel: PortfolioViewModel = koinInject()
    val metrics by viewModel.portfolioMetrics.collectAsState()
    
    Column {
        Text("Total P&L: ${metrics.totalPnL}")
        Text("Win Rate: ${metrics.winRate}%")
        Text("Open Positions: ${metrics.openPositions}")
    }
}
```

---

### Task 2: Create a Market Order

```kotlin
val orderRequest = OrderRequest(
    symbol = "BTC/USD",
    side = OrderSide.BUY,
    orderType = OrderType.MARKET,
    quantity = 1.0,
    timeInForce = TimeInForce.IOC
)

viewModel.createOrder(orderRequest)
```

---

### Task 3: Create a Limit Order

```kotlin
val orderRequest = OrderRequest(
    symbol = "ETH/USD",
    side = OrderSide.SELL,
    orderType = OrderType.LIMIT,
    quantity = 10.0,
    price = 3000.0,
    timeInForce = TimeInForce.GTC
)

viewModel.createOrder(orderRequest)
```

---

### Task 4: Filter Open Positions Only

```kotlin
viewModel.toggleShowOpenOnly()
// Or:
viewModel.updateFilter(
    PositionFilter(showOpenOnly = true)
)
```

---

### Task 5: Search for Positions by Symbol

```kotlin
viewModel.setSearchQuery("BTC")
```

---

### Task 6: Sort Positions by P&L

```kotlin
viewModel.updateSortOption(SortOption.PNL_DESC)
```

---

## Troubleshooting

### Build Fails

**Problem:** Compilation errors  
**Solution:** Clean and rebuild
```bash
./gradlew clean
./gradlew :composeApp:compileKotlinDesktop
```

---

### Data Not Showing

**Problem:** Empty screens  
**Solution:** 
1. Check backend API is running
2. Verify API base URL in `DatabaseModule.kt`
3. Check console for network errors
4. Tap "Refresh" button

---

### Navigation Not Working

**Problem:** Screen doesn't navigate  
**Solution:**
- Ensure Voyager `Navigator` is in scope
- Check screen is registered in navigation
- Verify bottom nav is showing

---

## Testing

### Manual Testing Checklist

```
Portfolio Screen:
[ ] Metrics card displays
[ ] Positions list shows
[ ] Filter works (open/closed)
[ ] Sort works
[ ] Position details dialog opens
[ ] Close position works
[ ] Refresh works

Orders Screen:
[ ] Metrics card displays
[ ] Orders list shows
[ ] New order button works
[ ] Order form validates
[ ] Order creation succeeds
[ ] Cancel order works
[ ] Filter works (active only)
[ ] Refresh works

Dashboard:
[ ] Portfolio summary displays
[ ] Recent positions show
[ ] Quick actions navigate
[ ] Win/loss stats display
```

---

## API Configuration

### Setting Base URL

Edit `fks/src/clients/shared/src/commonMain/kotlin/xyz/fkstrading/shared/di/DatabaseModule.kt`:

```kotlin
single {
    FksApiClient(
        baseUrl = "http://your-api-server:8000",
        httpClient = FksApiClient.createDefaultHttpClient(),
        authToken = "your-auth-token" // Optional
    )
}
```

### Expected Endpoints

**Positions:**
- `GET /api/positions` - List all
- `GET /api/positions/open` - Open only
- `GET /api/positions/closed` - Closed only
- `POST /api/positions` - Create/Update
- `POST /api/positions/{id}/close` - Close
- `DELETE /api/positions/{id}` - Delete

**Orders:**
- `GET /api/orders` - List all
- `GET /api/orders/active` - Active only
- `POST /api/orders` - Create
- `POST /api/orders/{id}/cancel` - Cancel
- `DELETE /api/orders/{id}` - Delete

---

## Performance Tips

1. **Use Filters** - Reduce data displayed for faster rendering
2. **Pagination** - Limit query results (default: 100)
3. **Caching** - Repositories cache locally with SQLDelight
4. **Refresh Wisely** - Don't over-refresh (rate limit)

---

## Keyboard Shortcuts (Desktop)

Currently not implemented. Planned for future versions.

---

## Color Coding Reference

- 🟢 **Green** - Profit, Long positions, Buy orders
- 🔴 **Red** - Loss, Short positions, Sell orders
- 🔵 **Blue** - Active/Open status
- ⚪ **Gray** - Cancelled/Expired status
- 🟣 **Purple** - Partial fills

---

## Next Steps

After familiarizing yourself with Phase 1:

1. **Explore Settings** - Configure strategy parameters
2. **Check Signals** - View real-time trading signals
3. **Test Order Flow** - Create and manage test orders
4. **Review Metrics** - Analyze portfolio performance

---

## Additional Resources

- **Full Documentation**: `docs/PHASE_1_IMPLEMENTATION.md`
- **API Docs**: `docs/API_INTEGRATION.md` (coming soon)
- **Testing Guide**: `docs/TESTING.md` (coming soon)
- **Deployment Guide**: `docs/DEPLOYMENT.md`

---

## Support

Having issues? Check:
1. Console logs for errors
2. Network tab for API calls
3. Database state (SQLDelight inspector)
4. Koin dependencies are injected

---

**Happy Trading! 🚀📈**

*Last Updated: 2025-01-20*