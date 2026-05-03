# StrategyExecutor & StrategyConfig Integration Guide

**Version:** 1.0  
**Last Updated:** 2024-01-XX  
**Status:** Implementation Guide

---

## Overview

This guide explains how to integrate the `StrategyExecutor` with the `StrategyConfigRepository` to enable:
- Persistent storage of execution configurations
- Dynamic configuration updates (reactive)
- User-managed strategy presets
- Default configuration management

---

## Architecture

### Current State

**StrategyExecutor** (Week 5 - Completed)
```kotlin
class StrategyExecutor(
    private val positionSizer: PositionSizer,
    private val orderBuilder: OrderBuilder,
    private val validator: ExecutionValidator
) {
    suspend fun execute(
        signal: Signal,
        config: ExecutionConfig,  // ← Passed explicitly
        accountBalance: Double,
        // ... other params
    ): ExecutionResult
}
```

**StrategyConfigRepository** (Week 5 - Completed)
```kotlin
interface StrategyConfigRepository {
    suspend fun getDefaultConfig(): StrategyConfig?
    fun observeDefaultConfig(): Flow<StrategyConfig?>
    suspend fun getConfigById(configId: String): StrategyConfig?
    // ... 20+ more methods
}
```

### Target State

**Enhanced StrategyExecutor** with config integration:
```kotlin
class StrategyExecutor(
    private val configRepository: StrategyConfigRepository?,  // Optional dependency
    private val positionSizer: PositionSizer,
    private val orderBuilder: OrderBuilder,
    private val validator: ExecutionValidator
) {
    // Execute with explicit config (existing behavior)
    suspend fun execute(signal: Signal, config: ExecutionConfig, ...): ExecutionResult
    
    // NEW: Execute using persisted config
    suspend fun executeWithConfig(signal: Signal, configId: String, ...): ExecutionResult
    
    // NEW: Execute using default config
    suspend fun executeWithDefaultConfig(signal: Signal, ...): ExecutionResult
}
```

---

## Integration Options

### Option 1: Dependency Injection (Recommended)

**Advantages:**
- Clean separation of concerns
- Easy to test (mock repository)
- Supports optional config persistence
- Works with existing code (backward compatible)

**Implementation:**

```kotlin
class StrategyExecutor(
    private val configRepository: StrategyConfigRepository? = null,
    private val positionSizer: PositionSizer = PositionSizer(),
    private val orderBuilder: OrderBuilder = OrderBuilder(),
    private val validator: ExecutionValidator = ExecutionValidator()
) {
    /**
     * Executes using default configuration from repository.
     * Falls back to ExecutionConfig.default() if repository is not available.
     */
    suspend fun executeWithDefaultConfig(
        signal: Signal,
        accountBalance: Double,
        currentPrice: Double,
        existingPositions: List<Position> = emptyList(),
        existingOrders: List<Order> = emptyList(),
        atr: Double? = null,
        winRate: Double? = null,
        profitFactor: Double? = null,
        strategyId: String? = null
    ): ExecutionResult {
        val config = configRepository?.getDefaultConfig()?.executionConfig
            ?: ExecutionConfig.default()
        
        return execute(
            signal = signal,
            config = config,
            accountBalance = accountBalance,
            currentPrice = currentPrice,
            existingPositions = existingPositions,
            existingOrders = existingOrders,
            atr = atr,
            winRate = winRate,
            profitFactor = profitFactor,
            strategyId = strategyId
        )
    }
    
    /**
     * Executes using a specific persisted configuration.
     */
    suspend fun executeWithConfig(
        signal: Signal,
        configId: String,
        accountBalance: Double,
        currentPrice: Double,
        existingPositions: List<Position> = emptyList(),
        existingOrders: List<Order> = emptyList(),
        atr: Double? = null,
        winRate: Double? = null,
        profitFactor: Double? = null
    ): ExecutionResult {
        val strategyConfig = configRepository?.getConfigById(configId)
            ?: return ExecutionResult.failed(
                signalId = signal.signalId,
                reason = "Configuration '$configId' not found"
            )
        
        if (!strategyConfig.isActive) {
            return ExecutionResult.failed(
                signalId = signal.signalId,
                reason = "Configuration '$configId' is not active"
            )
        }
        
        return execute(
            signal = signal,
            config = strategyConfig.executionConfig,
            accountBalance = accountBalance,
            currentPrice = currentPrice,
            existingPositions = existingPositions,
            existingOrders = existingOrders,
            atr = atr,
            winRate = winRate,
            profitFactor = profitFactor,
            strategyId = configId  // Use config ID as strategy ID
        )
    }
}
```

**Koin Module Setup:**

```kotlin
// shared/src/commonMain/kotlin/xyz/fkstrading/shared/di/StrategyModule.kt

val strategyModule = module {
    
    // Repository (from existing databaseModule)
    single<StrategyConfigRepository> {
        StrategyConfigRepositoryImpl(get())
    }
    
    // StrategyExecutor with config repository
    factory {
        StrategyExecutor(
            configRepository = get(),
            positionSizer = PositionSizer(),
            orderBuilder = OrderBuilder(),
            validator = ExecutionValidator()
        )
    }
}
```

---

### Option 2: Config Manager Wrapper

**Advantages:**
- StrategyExecutor remains unchanged
- Centralized config management logic
- Easy to add caching/optimization

**Implementation:**

```kotlin
class StrategyConfigManager(
    private val repository: StrategyConfigRepository,
    private val executor: StrategyExecutor
) {
    private var cachedDefaultConfig: ExecutionConfig? = null
    
    /**
     * Observes the default config and updates cache.
     */
    fun observeDefaultConfig(): Flow<StrategyConfig?> {
        return repository.observeDefaultConfig()
            .onEach { config ->
                cachedDefaultConfig = config?.executionConfig
            }
    }
    
    /**
     * Executes signal with default config.
     */
    suspend fun executeWithDefault(
        signal: Signal,
        accountBalance: Double,
        currentPrice: Double,
        // ... other params
    ): ExecutionResult {
        val config = cachedDefaultConfig 
            ?: repository.getDefaultConfig()?.executionConfig
            ?: ExecutionConfig.default()
        
        return executor.execute(
            signal = signal,
            config = config,
            accountBalance = accountBalance,
            currentPrice = currentPrice
        )
    }
    
    /**
     * Executes signal with specific config.
     */
    suspend fun executeWithConfig(
        signal: Signal,
        configId: String,
        accountBalance: Double,
        currentPrice: Double,
        // ... other params
    ): ExecutionResult {
        val strategyConfig = repository.getConfigById(configId)
            ?: return ExecutionResult.failed(
                signalId = signal.signalId,
                reason = "Config not found: $configId"
            )
        
        return executor.execute(
            signal = signal,
            config = strategyConfig.executionConfig,
            accountBalance = accountBalance,
            currentPrice = currentPrice
        )
    }
}
```

---

## Reactive Configuration Updates

### Use Case: Real-time Config Changes

Enable the executor to react to configuration changes without restart:

```kotlin
class ReactiveStrategyExecutor(
    private val configRepository: StrategyConfigRepository,
    private val executor: StrategyExecutor,
    private val scope: CoroutineScope
) {
    private val currentConfig = MutableStateFlow<ExecutionConfig?>(null)
    
    init {
        // Observe default config changes
        scope.launch {
            configRepository.observeDefaultConfig()
                .mapNotNull { it?.executionConfig }
                .collect { config ->
                    currentConfig.value = config
                    println("Config updated: ${config.mode}, sizing: ${config.positionSizingMethod}")
                }
        }
    }
    
    /**
     * Executes with latest default config.
     */
    suspend fun execute(
        signal: Signal,
        accountBalance: Double,
        currentPrice: Double,
        // ... other params
    ): ExecutionResult {
        val config = currentConfig.value ?: ExecutionConfig.default()
        
        return executor.execute(
            signal = signal,
            config = config,
            accountBalance = accountBalance,
            currentPrice = currentPrice
        )
    }
}
```

---

## UI Integration Examples

### Settings Screen

```kotlin
// ViewModel for Settings UI
class StrategyConfigViewModel(
    private val repository: StrategyConfigRepository
) : ViewModel() {
    
    // Observe all configs
    val configs: StateFlow<List<StrategyConfig>> = repository
        .observeAllConfigs()
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())
    
    // Current default config
    val defaultConfig: StateFlow<StrategyConfig?> = repository
        .observeDefaultConfig()
        .stateIn(viewModelScope, SharingStarted.Eagerly, null)
    
    // Set a config as default
    fun setDefault(configId: String) {
        viewModelScope.launch {
            repository.setAsDefault(configId)
                .onSuccess { println("Default config updated") }
                .onFailure { error -> println("Failed: ${error.message}") }
        }
    }
    
    // Toggle active status
    fun toggleActive(configId: String, isActive: Boolean) {
        viewModelScope.launch {
            repository.updateActiveStatus(configId, isActive)
        }
    }
    
    // Create new config
    fun createConfig(name: String, config: ExecutionConfig) {
        viewModelScope.launch {
            val strategyConfig = StrategyConfig(
                configId = "config-${System.currentTimeMillis()}",
                name = name,
                executionConfig = config,
                createdAt = Clock.System.now(),
                updatedAt = Clock.System.now()
            )
            repository.saveConfig(strategyConfig)
        }
    }
}
```

### Execution UI

```kotlin
// ViewModel for Signal Execution
class SignalExecutionViewModel(
    private val configRepository: StrategyConfigRepository,
    private val executor: StrategyExecutor
) : ViewModel() {
    
    // Get active configs for dropdown
    val activeConfigs: StateFlow<List<StrategyConfig>> = configRepository
        .observeActiveConfigs()
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())
    
    // Selected config
    private val selectedConfigId = MutableStateFlow<String?>(null)
    
    // Execute signal with selected config
    fun executeSignal(signal: Signal, accountBalance: Double, currentPrice: Double) {
        viewModelScope.launch {
            val configId = selectedConfigId.value
            
            val result = if (configId != null) {
                // Execute with specific config
                executor.executeWithConfig(
                    signal = signal,
                    configId = configId,
                    accountBalance = accountBalance,
                    currentPrice = currentPrice
                )
            } else {
                // Execute with default config
                executor.executeWithDefaultConfig(
                    signal = signal,
                    accountBalance = accountBalance,
                    currentPrice = currentPrice
                )
            }
            
            handleResult(result)
        }
    }
}
```

---

## Migration Path

### Phase 1: Add Optional Repository (Week 6)
1. ✅ Create `StrategyConfigRepository` and implementation
2. ✅ Add comprehensive tests (22 tests)
3. [ ] Add repository as optional dependency to `StrategyExecutor`
4. [ ] Implement `executeWithDefaultConfig()` and `executeWithConfig()`
5. [ ] Add tests for new methods

### Phase 2: UI Integration (Week 6-7)
1. [ ] Create Settings screen for config management
2. [ ] Add config selection to execution flow
3. [ ] Implement config presets (Conservative, Balanced, Aggressive)
4. [ ] Add import/export functionality

### Phase 3: Remote Sync (Week 7-8)
1. [ ] Implement REST endpoints for config sync
2. [ ] Add conflict resolution strategy
3. [ ] Implement background sync service
4. [ ] Add sync status indicators to UI

---

## Testing Strategy

### Unit Tests for Integration

```kotlin
class StrategyExecutorConfigIntegrationTest {
    
    private lateinit var repository: StrategyConfigRepository
    private lateinit var executor: StrategyExecutor
    
    @BeforeTest
    fun setup() {
        val database = DatabaseWrapper(TestDatabaseDriverFactory.createInMemoryDriverFactory())
        repository = StrategyConfigRepositoryImpl(database)
        executor = StrategyExecutor(configRepository = repository)
    }
    
    @Test
    fun `test execute with default config`() = runTest {
        // Given: A default config exists
        val config = StrategyConfig.conservative("default-1", Clock.System.now())
        repository.saveConfig(config)
        repository.setAsDefault("default-1")
        
        // When: Execute with default config
        val result = executor.executeWithDefaultConfig(
            signal = Signal.sample(signalId = "SIG-001"),
            accountBalance = 10000.0,
            currentPrice = 50000.0
        )
        
        // Then: Execution uses the persisted config
        assertTrue(result is ExecutionResult.Success || result is ExecutionResult.PendingConfirmation)
    }
    
    @Test
    fun `test execute with specific config`() = runTest {
        // Given: Multiple configs
        repository.saveConfig(StrategyConfig.default("config-1", Clock.System.now()))
        repository.saveConfig(StrategyConfig.aggressive("config-2", Clock.System.now()))
        
        // When: Execute with specific config
        val result = executor.executeWithConfig(
            signal = Signal.sample(signalId = "SIG-001"),
            configId = "config-2",
            accountBalance = 10000.0,
            currentPrice = 50000.0
        )
        
        // Then: Execution succeeds
        assertNotNull(result)
    }
    
    @Test
    fun `test execute fails with inactive config`() = runTest {
        // Given: An inactive config
        val config = StrategyConfig.default("inactive", Clock.System.now())
            .copy(isActive = false)
        repository.saveConfig(config)
        
        // When: Try to execute
        val result = executor.executeWithConfig(
            signal = Signal.sample(signalId = "SIG-001"),
            configId = "inactive",
            accountBalance = 10000.0,
            currentPrice = 50000.0
        )
        
        // Then: Execution fails
        assertTrue(result is ExecutionResult.Failed)
        assertTrue(result.reason.contains("not active"))
    }
}
```

---

## Best Practices

### 1. Always Provide Fallback Config
```kotlin
val config = repository.getDefaultConfig()?.executionConfig
    ?: ExecutionConfig.default()  // Fallback to safe defaults
```

### 2. Validate Config Before Execution
```kotlin
if (!strategyConfig.isActive) {
    return ExecutionResult.failed(reason = "Config is inactive")
}
```

### 3. Use Reactive Flows for UI
```kotlin
// Good: Reactive updates
repository.observeDefaultConfig()
    .collect { config -> updateUI(config) }

// Avoid: Polling
while (true) {
    val config = repository.getDefaultConfig()
    updateUI(config)
    delay(1000)
}
```

### 4. Handle Repository Failures Gracefully
```kotlin
val config = try {
    repository.getDefaultConfig()?.executionConfig
} catch (e: Exception) {
    logger.error("Config fetch failed", e)
    ExecutionConfig.default()
}
```

### 5. Ensure Default Config Exists on App Start
```kotlin
class AppInitializer(private val repository: StrategyConfigRepository) {
    suspend fun initialize() {
        // Ensure at least one config exists
        if (repository.getConfigCount() == 0L) {
            val defaultConfig = StrategyConfig.default(
                configId = "default",
                timestamp = Clock.System.now()
            )
            repository.saveConfig(defaultConfig)
            repository.setAsDefault("default")
        }
    }
}
```

---

## Conclusion

The integration of `StrategyExecutor` with `StrategyConfigRepository` provides:

✅ **Persistence:** Save and manage execution configurations  
✅ **Flexibility:** Use default, specific, or dynamic configs  
✅ **User Control:** UI-driven config management  
✅ **Backward Compatibility:** Existing `execute()` method unchanged  
✅ **Testability:** Easy to mock repository in tests  

**Recommended Approach:** Option 1 (Dependency Injection) for maximum flexibility and testability.

**Next Steps:**
1. Implement enhanced `StrategyExecutor` with new methods
2. Add comprehensive tests
3. Create Settings UI for config management
4. Document API for mobile app teams