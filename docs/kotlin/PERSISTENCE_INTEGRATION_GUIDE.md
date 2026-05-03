# Persistence Layer Integration Guide

## Quick Start

This guide shows how to integrate the Week 3 persistence layer into your application.

## 1. Initialize Koin with Platform Module

### Android

```kotlin
// In your Application class
class FksApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        
        initKoin {
            androidContext(this@FksApplication)
            modules(
                allModules + androidPlatformModule(this@FksApplication)
            )
        }
    }
}
```

### iOS

```kotlin
// In your main iOS file
fun initializeKoin() {
    initKoin {
        modules(allModules + iosPlatformModule)
    }
}
```

### Desktop

```kotlin
// In your main desktop function
fun main() = application {
    initKoin {
        modules(allModules + desktopPlatformModule)
    }
    
    // ... your compose UI
}
```

## 2. Inject Repositories in ViewModels

```kotlin
class SignalsViewModel(
    private val signalRepository: SignalRepository,
    private val syncEngine: SyncEngine
) : ViewModel() {
    
    // Observe all signals - updates automatically
    val signals: StateFlow<List<Signal>> = signalRepository
        .observeAllSignals()
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = emptyList()
        )
    
    // Observe sync state
    val syncState: StateFlow<SyncState> = syncEngine.syncState
    
    init {
        // Start periodic sync
        syncEngine.start()
    }
    
    // Save a signal (works offline)
    fun saveSignal(signal: Signal) {
        viewModelScope.launch {
            try {
                signalRepository.saveSignal(signal)
                // Saved locally, will sync in background
            } catch (e: Exception) {
                // Handle error
            }
        }
    }
    
    // Manual sync trigger
    fun syncNow() {
        viewModelScope.launch {
            val success = syncEngine.sync()
            if (success) {
                // Sync completed
            } else {
                // Sync failed
            }
        }
    }
    
    override fun onCleared() {
        super.onCleared()
        syncEngine.stop()
    }
}
```

## 3. Use in Compose UI

```kotlin
@Composable
fun SignalsScreen(
    viewModel: SignalsViewModel = koinViewModel()
) {
    val signals by viewModel.signals.collectAsState()
    val syncState by viewModel.syncState.collectAsState()
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Signals") },
                actions = {
                    // Sync indicator
                    when (syncState) {
                        is SyncState.Syncing -> {
                            CircularProgressIndicator(
                                modifier = Modifier.size(24.dp)
                            )
                        }
                        is SyncState.Error -> {
                            Icon(
                                imageVector = Icons.Default.CloudOff,
                                contentDescription = "Offline"
                            )
                        }
                        else -> {}
                    }
                    
                    // Manual sync button
                    IconButton(onClick = { viewModel.syncNow() }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Sync"
                        )
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding)
        ) {
            items(signals, key = { it.signalId }) { signal ->
                SignalCard(signal = signal)
            }
        }
    }
}
```

## 4. Integrate WebSocket with Persistence

Update your WebSocket subscription to save data to local database:

```kotlin
class RealTimeSignalsViewModel(
    private val webSocketClient: WebSocketClient,
    private val dataStream: WebSocketDataStream,
    private val signalRepository: SignalRepository // Add repository
) : ViewModel() {
    
    init {
        viewModelScope.launch {
            // Subscribe to WebSocket signals
            dataStream.signalsFlow.collect { signal ->
                // Save to local database automatically
                signalRepository.saveSignal(signal)
                // Repository handles sync in background
            }
        }
    }
}
```

## 5. Koin Module Definition

Add ViewModels to your Koin module:

```kotlin
val viewModelModule = module {
    viewModel { SignalsViewModel(get(), get()) }
    viewModel { OrdersViewModel(get(), get()) }
    viewModel { PositionsViewModel(get(), get()) }
    viewModel { 
        RealTimeSignalsViewModel(
            webSocketClient = get(),
            dataStream = get(),
            signalRepository = get()
        )
    }
}

// Update allModules
val allModules = listOf(
    networkModule,
    webSocketModule,
    databaseModule,
    viewModelModule,
    appModule,
    useCaseModule
)
```

## 6. Repository Operations Reference

### SignalRepository

```kotlin
// Observe signals (reactive)
signalRepository.observeAllSignals(): Flow<List<Signal>>
signalRepository.observeSignalsBySymbol(symbol): Flow<List<Signal>>
signalRepository.observeRecentSignals(limit): Flow<List<Signal>>

// Get signals (one-time)
signalRepository.getSignalById(id): Signal?
signalRepository.getAllSignals(): List<Signal>

// Save signals (offline-capable)
signalRepository.saveSignal(signal)
signalRepository.saveSignals(signals)

// Delete signals
signalRepository.deleteSignal(id)
signalRepository.deleteOldSignals(olderThanMillis)

// Sync operations
signalRepository.sync(): Boolean
signalRepository.refresh()
```

### OrderRepository

```kotlin
// Observe orders (reactive)
orderRepository.observeAllOrders(): Flow<List<Order>>
orderRepository.observeActiveOrders(): Flow<List<Order>>
orderRepository.observeOrdersBySymbol(symbol): Flow<List<Order>>
orderRepository.observeOrdersBySignalId(signalId): Flow<List<Order>>

// Get orders (one-time)
orderRepository.getOrderById(id): Order?
orderRepository.getActiveOrders(): List<Order>

// Save orders (offline-capable)
orderRepository.saveOrder(order)
orderRepository.saveOrders(orders)

// Update order status
orderRepository.updateOrderStatus(id, status)

// Sync operations
orderRepository.sync(): Boolean
orderRepository.refresh()
```

### PositionRepository

```kotlin
// Observe positions (reactive)
positionRepository.observeAllPositions(): Flow<List<Position>>
positionRepository.observeOpenPositions(): Flow<List<Position>>
positionRepository.observeClosedPositions(): Flow<List<Position>>
positionRepository.observePositionsBySymbol(symbol): Flow<List<Position>>

// Get positions (one-time)
positionRepository.getPositionById(id): Position?
positionRepository.getOpenPositions(): List<Position>

// Save positions (offline-capable)
positionRepository.savePosition(position)
positionRepository.savePositions(positions)

// Update position
positionRepository.updatePositionPrice(id, price, pnl)
positionRepository.closePosition(id, realizedPnL)

// Sync operations
positionRepository.sync(): Boolean
positionRepository.refresh()
```

## 7. Sync Engine Usage

```kotlin
class MainViewModel(
    private val syncEngine: SyncEngine
) : ViewModel() {
    
    val syncState = syncEngine.syncState
    val lastSyncTime = syncEngine.lastSyncTime
    
    init {
        // Start automatic periodic sync
        syncEngine.start()
    }
    
    fun manualSync() {
        viewModelScope.launch {
            val success = syncEngine.sync()
            // Handle result
        }
    }
    
    fun forceRefresh() {
        viewModelScope.launch {
            val success = syncEngine.refresh()
            // Handle result
        }
    }
    
    fun enableSync(enabled: Boolean) {
        syncEngine.setEnabled(enabled)
    }
    
    override fun onCleared() {
        super.onCleared()
        syncEngine.stop()
    }
}
```

## 8. Testing with Repositories

```kotlin
class SignalsViewModelTest {
    
    private lateinit var signalRepository: SignalRepository
    private lateinit var syncEngine: SyncEngine
    private lateinit var viewModel: SignalsViewModel
    
    @Before
    fun setup() {
        // Create in-memory database for testing
        val driver = DesktopDatabaseDriverFactory.createInMemoryDriver()
        val database = DatabaseWrapper(object : DatabaseDriverFactory {
            override fun createDriver() = driver
        })
        
        // Create repository without remote data source
        signalRepository = SignalRepositoryImpl(
            database = database,
            remoteDataSource = null
        )
        
        // Create sync engine
        syncEngine = SyncEngine(
            signalRepository = signalRepository,
            orderRepository = mockOrderRepository,
            positionRepository = mockPositionRepository
        )
        
        // Create ViewModel
        viewModel = SignalsViewModel(signalRepository, syncEngine)
    }
    
    @Test
    fun testSaveSignal() = runTest {
        val signal = Signal.sample()
        viewModel.saveSignal(signal)
        
        val signals = viewModel.signals.first()
        assertTrue(signals.contains(signal))
    }
}
```

## 9. Error Handling

```kotlin
class SignalsViewModel(
    private val signalRepository: SignalRepository
) : ViewModel() {
    
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    
    fun saveSignal(signal: Signal) {
        viewModelScope.launch {
            try {
                signalRepository.saveSignal(signal)
                _error.value = null
            } catch (e: Exception) {
                _error.value = "Failed to save signal: ${e.message}"
                // Log error
                println("Save signal error: ${e.message}")
            }
        }
    }
}
```

## 10. Best Practices

### Do's ✅

1. **Always use repositories in ViewModels**
   - Never access database directly from UI layer
   - Repositories handle offline logic

2. **Use Flow for reactive data**
   - UI updates automatically
   - No manual refresh needed

3. **Start sync engine early**
   - Start in Application onCreate (Android) or main (Desktop)
   - Let it run in background

4. **Handle errors gracefully**
   - Show user-friendly messages
   - Log errors for debugging

5. **Test with in-memory database**
   - Fast and isolated tests
   - No cleanup needed

### Don'ts ❌

1. **Don't block UI thread**
   - All repository operations are suspend functions
   - Always use coroutines

2. **Don't forget to stop sync engine**
   - Stop in onCleared() or app shutdown
   - Prevents memory leaks

3. **Don't assume network is available**
   - App should work offline
   - Sync will catch up later

4. **Don't hold references to database**
   - Let Koin manage lifecycle
   - Use repositories instead

5. **Don't ignore sync errors**
   - Monitor sync state
   - Show user feedback

## 11. Common Patterns

### Pattern 1: Load + Auto-refresh

```kotlin
val signals = signalRepository
    .observeRecentSignals(limit = 50)
    .stateIn(scope, SharingStarted.WhileSubscribed(), emptyList())
```

### Pattern 2: Pull-to-refresh

```kotlin
fun refresh() {
    viewModelScope.launch {
        _isRefreshing.value = true
        try {
            signalRepository.refresh()
        } finally {
            _isRefreshing.value = false
        }
    }
}
```

### Pattern 3: Offline indicator

```kotlin
@Composable
fun OfflineIndicator() {
    val syncState by syncEngine.syncState.collectAsState()
    
    if (syncState is SyncState.Error) {
        Snackbar {
            Text("Working offline - will sync when connected")
        }
    }
}
```

## 12. Migration from Direct WebSocket

**Before (Week 2):**
```kotlin
class SignalsViewModel(
    private val dataStream: WebSocketDataStream
) : ViewModel() {
    val signals = dataStream.signalsFlow
        .stateIn(scope, SharingStarted.Lazily, emptyList())
}
```

**After (Week 3):**
```kotlin
class SignalsViewModel(
    private val signalRepository: SignalRepository,
    private val dataStream: WebSocketDataStream
) : ViewModel() {
    
    // Read from repository (includes cached data)
    val signals = signalRepository.observeAllSignals()
        .stateIn(scope, SharingStarted.Lazily, emptyList())
    
    init {
        // Save WebSocket updates to repository
        viewModelScope.launch {
            dataStream.signalsFlow.collect { signal ->
                signalRepository.saveSignal(signal)
            }
        }
    }
}
```

## Summary

The persistence layer provides:
- ✅ Offline-first data access
- ✅ Automatic background sync
- ✅ Reactive UI updates
- ✅ Type-safe operations
- ✅ Cross-platform support

All data operations are now cached locally and synchronized with the server automatically!