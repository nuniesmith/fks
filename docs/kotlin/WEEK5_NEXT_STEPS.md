# Week 5: Next Steps - Immediate Action Items

**Status:** 🔴 Compilation errors blocking progress  
**Priority:** Fix errors before proceeding  
**Estimated Time:** 30-45 minutes  

---

## 🔴 CRITICAL: Fix Compilation Errors

**Problem:** Signal model uses different field names than our code expects.

### Quick Fix Guide

#### 1. Remove Duplicate TimeInForce Enum (5 min)

**File:** `shared/src/commonMain/kotlin/xyz/fkstrading/shared/domain/strategy/models/ExecutionConfig.kt`

**Change:**
```kotlin
// DELETE this enum from ExecutionConfig.kt (lines 365-389):
enum class TimeInForce {
    GTC,
    IOC,
    FOK,
    DAY
}

// UPDATE import at top of file:
import xyz.fkstrading.shared.domain.models.TimeInForce
```

#### 2. Create Direction to OrderSide Converter (5 min)

**File:** `shared/src/commonMain/kotlin/xyz/fkstrading/shared/domain/strategy/OrderBuilder.kt`

**Add after imports:**
```kotlin
// Converter function
private fun Direction.toOrderSide(): OrderSide = when (this) {
    Direction.LONG -> OrderSide.BUY
    Direction.SHORT -> OrderSide.SELL
}
```

#### 3. Fix Signal Field References in OrderBuilder.kt (10 min)

**File:** `shared/src/commonMain/kotlin/xyz/fkstrading/shared/domain/strategy/OrderBuilder.kt`

**Changes:**
```kotlin
// Line 56: Change signal side conversion
val orderSide = signal.direction.toOrderSide()

// Line 128-130: Fix stop-loss calculation
when (signal.direction) {
    Direction.LONG -> currentPrice - stopDistance
    Direction.SHORT -> currentPrice + stopDistance
}

// Line 144-146: Fix ATR stop-loss
when (signal.direction) {
    Direction.LONG -> currentPrice - stopDistance
    Direction.SHORT -> currentPrice + stopDistance
}

// Line 171-173: Fix take-profit percentage
when (signal.direction) {
    Direction.LONG -> currentPrice + profitDistance
    Direction.SHORT -> currentPrice - profitDistance
}

// Line 188-190: Fix take-profit ATR
when (signal.direction) {
    Direction.LONG -> currentPrice + profitDistance
    Direction.SHORT -> currentPrice - profitDistance
}

// Line 205-207: Fix take-profit risk-reward
when (signal.direction) {
    Direction.LONG -> currentPrice + profitDistance
    Direction.SHORT -> currentPrice - profitDistance
}

// Line 384: Remove signal.reasoning (doesn't exist)
// DELETE this line or make it optional
```

#### 4. Fix Signal Field References in ExecutionValidator.kt (5 min)

**File:** `shared/src/commonMain/kotlin/xyz/fkstrading/shared/domain/strategy/ExecutionValidator.kt`

**Changes:**
```kotlin
// Line 121: Remove targetPrice check (use entryPrice instead)
if (signal.entryPrice <= 0) {
    errors.add("Signal entry price must be positive")
}

// Line 298, 303: Fix side references
val sameSignalOrders = existingOrders.filter {
    it.signalId == signal.signalId && it.isActive()
}

val recentSameSymbolOrders = existingOrders.filter { order ->
    order.symbol == signal.symbol &&
    order.side.name == signal.direction.toOrderSide().name &&
    order.isActive()
}

// Line 379-381: Fix stop-loss direction validation
val isValid = when (signal.direction) {
    Direction.LONG -> stopDistance > 0  // SL below entry
    Direction.SHORT -> stopDistance < 0 // SL above entry
}

// Line 386: Fix error message
"Stop-loss on wrong side: ${signal.direction.name} at..."
```

#### 5. Fix Signal Field References in StrategyExecutor.kt (5 min)

**File:** `shared/src/commonMain/kotlin/xyz/fkstrading/shared/domain/strategy/StrategyExecutor.kt`

**Changes:**
```kotlin
// Line 395: Fix confirmExecution price fallback
currentPrice = signal.entryPrice

// Also update any other targetPrice references to entryPrice
```

#### 6. Fix ExecutionResult.kt (5 min)

**File:** `shared/src/commonMain/kotlin/xyz/fkstrading/shared/domain/strategy/models/ExecutionResult.kt`

**Changes:**
```kotlin
// Line 140-142: Fix summary() string building
ExecutionStatus.SUCCESS -> "Successfully executed ${signal.symbol} ${signal.direction.toOrderSide()} order for ${positionSize} units"
ExecutionStatus.DRY_RUN_SUCCESS -> "Dry-run: Would execute ${signal.symbol} ${signal.direction.toOrderSide()} order for ${positionSize} units"
ExecutionStatus.PENDING_CONFIRMATION -> "Awaiting confirmation for ${signal.symbol} ${signal.direction.toOrderSide()} order"
```

#### 7. Fix PositionSizerTest.kt (5 min)

**File:** `shared/src/commonTest/kotlin/xyz/fkstrading/shared/domain/strategy/PositionSizerTest.kt`

**Changes:**
```kotlin
// Line 408-420: Fix test helper function
private fun createTestSignal(
    symbol: String = "BTC/USD",
    direction: Direction = Direction.LONG,
    confidence: Double = 0.8
): Signal {
    return Signal(
        signalId = "TEST-SIGNAL-001",
        signalType = SignalType.ENTRY,
        symbol = symbol,
        timeframe = Timeframe.H1,
        direction = direction,
        entryPrice = 100.0,
        stopLoss = if (direction == Direction.LONG) 98.0 else 102.0,
        takeProfit = if (direction == Direction.LONG) 105.0 else 95.0,
        confidence = confidence,
        timestamp = Clock.System.now(),
        strategyName = "TestStrategy"
    )
}

// Also update test cases that use SignalSide:
// Change: side = SignalSide.BUY
// To:     direction = Direction.LONG
```

---

## ✅ Verification Steps

After making all changes above:

```bash
cd src/clients
./gradlew :shared:desktopTest --tests "xyz.fkstrading.shared.domain.strategy.PositionSizerTest"
```

**Expected Output:**
- All 17 tests pass
- No compilation errors
- Build succeeds in < 10 seconds

---

## 📋 Post-Fix Checklist

Once errors are fixed and tests pass:

### Immediate Tasks (Day 1 completion)
- [ ] Verify all PositionSizerTest tests pass
- [ ] Commit working code: "feat: implement strategy execution engine core"
- [ ] Update WEEK5_PROGRESS.md status to "Phase 1: 70% → 80%"

### Next Session (Day 2)
- [ ] Write OrderBuilder unit tests (15 tests, ~2 hours)
- [ ] Write ExecutionValidator unit tests (20 tests, ~2 hours)
- [ ] Write StrategyExecutor unit tests (15 tests, ~2 hours)
- [ ] Create integration test for full flow (1 hour)
- [ ] Begin Phase 2: Risk Management System

---

## 🎯 Success Criteria

**Day 1 Complete When:**
1. ✅ No compilation errors
2. ✅ All 17 PositionSizer tests pass
3. ✅ Code committed to version control
4. ✅ Documentation updated

**Phase 1 Complete When (Day 2):**
1. ✅ All unit tests written and passing (67+ tests total)
2. ✅ Integration test passing
3. ✅ Test coverage > 90%
4. ✅ Strategy configuration persistence implemented
5. ✅ Ready to begin Phase 2 (Risk Management)

---

## 📞 Questions?

- Review `WEEK5_SESSION1_SUMMARY.md` for detailed component documentation
- Check `WEEK5_PROGRESS.md` for current status
- See `WEEK5_PLAN.md` for overall sprint plan

---

**Estimated Total Fix Time:** 30-45 minutes  
**Difficulty:** Low (straightforward field name replacements)  
**Risk:** Low (mechanical changes, no logic changes needed)

Let's fix these errors and get the tests passing! 🚀