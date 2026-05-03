# Kotlin Multiplatform (KMP) Architecture - FKS Trading Clients

**Status**: ✅ In Progress  
**Date**: 2025-12-28  
**Targets**: Android, iOS, Desktop (Linux/macOS/Windows), Web (WebAssembly)  
**Code Sharing**: 95%+ across all platforms

---

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Architecture Principles](#architecture-principles)
4. [Platform Targets](#platform-targets)
5. [Module Organization](#module-organization)
6. [Technology Stack](#technology-stack)
7. [Build & Run Instructions](#build--run-instructions)
8. [Feature Implementation Guide](#feature-implementation-guide)
9. [Performance Optimization](#performance-optimization)
10. [Deployment](#deployment)

---

## Overview

The FKS Trading Clients project uses **Kotlin Multiplatform (KMP)** with **Compose Multiplatform** to create a unified codebase that targets all major platforms. This architecture enables:

- **Single UI codebase** using Compose for all platforms including Web (via WebAssembly)
- **Shared business logic** for market data, signals, and trading algorithms
- **Platform-specific optimizations** where needed (Bluetooth on Android, tray icons on Desktop)
- **High-performance rendering** using Skiko graphics engine across all targets

### Why This Architecture?

Traditional approach: Separate codebases for Web (React/Vue), Mobile (Swift/Kotlin), Desktop (Electron)
- ❌ 4-5x code duplication
- ❌ Inconsistent UX across platforms
- ❌ Higher maintenance costs

**KMP Approach**: One codebase, all platforms
- ✅ 95%+ code sharing
- ✅ Consistent UX and features
- ✅ Native performance on all targets
- ✅ Type-safe API across platforms

---

## Project Structure

```
fks/src/clients/
├── composeApp/                    # 🎯 MAIN UNIFIED MODULE
│   ├── build.gradle.kts           # All platform targets configured here
│   └── src/
│       ├── commonMain/            # ⭐ SHARED CODE (95%+)
│       │   ├── kotlin/
│       │   │   ├── xyz/fkstrading/client/
│       │   │   │   ├── App.kt                    # Root Composable
│       │   │   │   ├── di/                       # Dependency Injection
│       │   │   │   │   ├── AppModule.kt          # Koin modules
│       │   │   │   │   └── PlatformModule.kt
│       │   │   │   ├── navigation/               # Navigation
│       │   │   │   │   ├── NavGraph.kt
│       │   │   │   │   └── Screen.kt
│       │   │   │   ├── theme/                    # Design System
│       │   │   │   │   ├── Theme.kt              # Material3 theme
│       │   │   │   │   ├── Typography.kt
│       │   │   │   │   └── Color.kt
│       │   │   │   ├── features/                 # Feature Modules
│       │   │   │   │   ├── dashboard/
│       │   │   │   │   │   ├── DashboardScreen.kt
│       │   │   │   │   │   ├── DashboardViewModel.kt
│       │   │   │   │   │   └── components/
│       │   │   │   │   ├── tradingwall/          # Trading Wall (Charts)
│       │   │   │   │   │   ├── TradingWallScreen.kt
│       │   │   │   │   │   ├── TradingWallViewModel.kt
│       │   │   │   │   │   └── charts/
│       │   │   │   │   │       ├── FinancialChart.kt  # Skiko-based
│       │   │   │   │   │       ├── CandlestickChart.kt
│       │   │   │   │   │       └── VolumeChart.kt
│       │   │   │   │   ├── signals/               # Signal Matrix
│       │   │   │   │   │   ├── SignalsScreen.kt
│       │   │   │   │   │   ├── SignalCard.kt
│       │   │   │   │   │   └── SignalViewModel.kt
│       │   │   │   │   └── settings/
│       │   │   │   ├── core/                     # Domain Layer
│       │   │   │   │   ├── domain/
│       │   │   │   │   │   ├── model/            # Data models
│       │   │   │   │   │   │   ├── Candle.kt
│       │   │   │   │   │   │   ├── Ticker.kt
│       │   │   │   │   │   │   ├── Signal.kt
│       │   │   │   │   │   │   └── OrderBook.kt
│       │   │   │   │   │   └── repository/       # Interfaces
│       │   │   │   │   ├── data/                 # Data Layer
│       │   │   │   │   │   ├── repository/       # Implementations
│       │   │   │   │   │   ├── local/            # Cache/DB
│       │   │   │   │   │   └── remote/           # API clients
│       │   │   │   │   └── network/              # Networking
│       │   │   │   │       ├── WebSocketClient.kt
│       │   │   │   │       ├── HttpClient.kt
│       │   │   │   │       └── dto/              # API DTOs
│       │   │   │   └── ui/                       # UI Components
│       │   │   │       ├── components/
│       │   │   │       │   ├── FksAppBar.kt
│       │   │   │       │   ├── FksBottomNav.kt
│       │   │   │       │   ├── LoadingIndicator.kt
│       │   │   │       │   └── ErrorView.kt
│       │   │   │       └── layouts/
│       │   │   │           ├── ResponsiveLayout.kt
│       │   │   │           └── AdaptiveScaffold.kt
│       │   └── resources/              # Shared Resources
│       │       ├── drawable/           # Images (SVG, PNG)
│       │       ├── font/               # Custom fonts
│       │       └── values/             # Strings (i18n)
│       │
│       ├── androidMain/               # Android-specific (5%)
│       │   ├── kotlin/
│       │   │   └── xyz/fkstrading/client/
│       │   │       ├── MainActivity.kt
│       │   │       ├── PlatformAndroid.kt
│       │   │       └── bluetooth/      # Android Bluetooth API
│       │   ├── AndroidManifest.xml
│       │   └── res/
│       │
│       ├── desktopMain/               # Desktop-specific (3%)
│       │   ├── kotlin/
│       │   │   └── xyz/fkstrading/client/
│       │   │       ├── Main.kt         # JVM entry point
│       │   │       ├── PlatformDesktop.kt
│       │   │       └── window/         # Window management
│       │   └── resources/
│       │       ├── icon.png
│       │       ├── icon.ico
│       │       └── icon.icns
│       │
│       ├── iosMain/                   # iOS-specific (2%)
│       │   └── kotlin/
│       │       └── xyz/fkstrading/client/
│       │           ├── MainViewController.kt
│       │           └── PlatformIOS.kt
│       │
│       └── wasmJsMain/                # Web-specific (2%)
│           └── kotlin/
│               └── xyz/fkstrading/client/
│                   ├── Main.kt         # Wasm entry point
│                   └── PlatformWeb.kt
│
├── iosApp/                            # Xcode iOS Entry Point
│   ├── iosApp.xcodeproj
│   └── iosApp/
│       ├── iOSApp.swift               # Swift entry calling Kotlin
│       └── Info.plist
│
├── build.gradle.kts                   # Root project config
├── settings.gradle.kts                # Module registration
├── gradle.properties                  # Build configuration
└── gradle/
    └── libs.versions.toml             # Version catalog
```

---

## Architecture Principles

### 1. **Feature-First Organization**

Organize code by feature, not by layer:

```
features/
├── dashboard/           # All dashboard code together
│   ├── DashboardScreen.kt
│   ├── DashboardViewModel.kt
│   ├── components/
│   └── model/
├── tradingwall/         # All trading wall code together
└── signals/
```

**Benefits**:
- Easy to find related code
- Clear module boundaries
- Can extract to separate modules later

### 2. **Platform Abstraction via `expect/actual`**

For platform-specific functionality, use Kotlin's `expect/actual` pattern:

```kotlin
// commonMain - Declaration
expect fun getPlatformName(): String
expect fun isCompactScreen(): Boolean
expect class PlatformStorage() {
    fun save(key: String, value: String)
    fun load(key: String): String?
}

// androidMain - Android implementation
actual fun getPlatformName() = "Android"
actual fun isCompactScreen() = 
    LocalConfiguration.current.screenWidthDp < 600

// desktopMain - Desktop implementation
actual fun getPlatformName() = "Desktop"
actual fun isCompactScreen() = false  // Always false on desktop

// wasmJsMain - Web implementation
actual fun getPlatformName() = "Web"
actual fun isCompactScreen() = 
    window.innerWidth < 600
```

### 3. **Responsive UI with Compose**

Use `BoxWithConstraints` for adaptive layouts:

```kotlin
@Composable
fun TradingWallScreen() {
    BoxWithConstraints {
        when {
            maxWidth >= 1200.dp -> {
                // Desktop: 3-column grid
                TradingWallDesktopLayout()
            }
            maxWidth >= 600.dp -> {
                // Tablet: 2-column grid
                TradingWallTabletLayout()
            }
            else -> {
                // Mobile: Single column, vertical scroll
                TradingWallMobileLayout()
            }
        }
    }
}
```

### 4. **Dependency Injection with Koin**

Shared DI configuration in `commonMain`:

```kotlin
val appModule = module {
    // ViewModels
    viewModel { DashboardViewModel(get(), get()) }
    viewModel { TradingWallViewModel(get()) }
    
    // Repositories
    single<MarketDataRepository> { MarketDataRepositoryImpl(get()) }
    
    // Network
    single { createHttpClient() }
    single { WebSocketClient(get()) }
}

// Platform-specific modules
expect fun platformModule(): Module

// androidMain
actual fun platformModule() = module {
    single { AndroidBluetoothManager() }
}
```

### 5. **State Management**

Use Kotlin Flow for reactive state:

```kotlin
class TradingWallViewModel(
    private val marketDataRepo: MarketDataRepository
) : ViewModel() {
    
    private val _candles = MutableStateFlow<List<Candle>>(emptyList())
    val candles: StateFlow<List<Candle>> = _candles.asStateFlow()
    
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()
    
    init {
        viewModelScope.launch {
            marketDataRepo.streamCandles("BTC/USD")
                .collect { newCandle ->
                    _candles.update { it + newCandle }
                }
        }
    }
}
```

---

## Platform Targets

### Android (Phone/Tablet)
- **Min SDK**: 24 (Android 7.0)
- **Target SDK**: 35 (Android 15)
- **Build Output**: APK / AAB
- **Special Features**: Bluetooth LE for hardware wallets

### iOS (iPhone/iPad)
- **Min Version**: iOS 14
- **Targets**: arm64, x64 (simulator), arm64 (simulator)
- **Build Output**: .framework → Xcode → .app / .ipa
- **Special Features**: Native iOS UI integration if needed

### Desktop (Linux, macOS, Windows)
- **JVM Target**: 21
- **Build Output**: 
  - Linux: .deb package
  - macOS: .dmg bundle
  - Windows: .msi installer
- **Special Features**: System tray, keyboard shortcuts, multi-window

### Web (Browser via WebAssembly)
- **Target**: wasmJs (Kotlin/Wasm)
- **Build Output**: .wasm + .js loader
- **Performance**: Near-native with Skiko rendering
- **Special Features**: Browser storage, full-screen mode

---

## Technology Stack

### UI Framework
- **Compose Multiplatform 1.9.3**: Declarative UI framework
- **Material3**: Modern design system
- **Skiko**: High-performance graphics rendering (used under the hood)

### Navigation
- **Voyager 1.0.0**: Type-safe navigation for Compose Multiplatform
  - Supports all platforms including Web
  - Tab navigation, transitions, bottom sheets

### Networking
- **Ktor Client 3.0.0**: Multiplatform HTTP/WebSocket client
  - OkHttp on Android
  - Darwin on iOS
  - CIO on Desktop
  - JS engine on Web

### Serialization
- **kotlinx.serialization 1.8.1**: JSON parsing
- Type-safe DTO definitions

### Dependency Injection
- **Koin 4.0.0**: Lightweight DI for Kotlin Multiplatform
- Compose integration for ViewModels

### Concurrency
- **kotlinx.coroutines 1.9.0**: Async/await pattern
- Flow for reactive streams

---

## Build & Run Instructions

### Prerequisites

```bash
# Install JDK 21
sdk install java 21.0.1-tem

# Install Kotlin 2.2.21 (via Gradle wrapper)
cd fks/src/clients
./gradlew --version

# For iOS: Install Xcode 15+
xcode-select --install

# For Web: Install Node.js 22+
node --version
```

### Development Commands

#### Web (Wasm)
```bash
# Development server (http://localhost:8080)
./gradlew :composeApp:wasmJsBrowserDevelopmentRun

# Production build
./gradlew :composeApp:wasmJsBrowserDistribution
# Output: composeApp/build/dist/wasmJs/productionExecutable/

# Deploy to static hosting
cd composeApp/build/dist/wasmJs/productionExecutable/
# Upload to Netlify/Vercel/S3
```

#### Desktop (Current OS)
```bash
# Run directly
./gradlew :composeApp:run

# Package for distribution
./gradlew :composeApp:packageDistributionForCurrentOS
# Linux: composeApp/build/compose/binaries/main/deb/
# macOS: composeApp/build/compose/binaries/main/dmg/
# Windows: composeApp/build/compose/binaries/main/msi/

# Package for all platforms (requires cross-compilation setup)
./gradlew :composeApp:packageReleaseDistribution
```

#### Android
```bash
# Debug build & install
./gradlew :composeApp:installDebug

# Run on connected device
adb install composeApp/build/outputs/apk/debug/composeApp-debug.apk

# Release build (signed)
./gradlew :composeApp:bundleRelease
# Output: composeApp/build/outputs/bundle/release/composeApp-release.aab
```

#### iOS
```bash
# Build framework
./gradlew :composeApp:linkDebugFrameworkIosSimulatorArm64

# Open Xcode project
open iosApp/iosApp.xcodeproj

# Run from Xcode or command line
xcodebuild -project iosApp/iosApp.xcodeproj \
  -scheme iosApp \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  run
```

---

## Feature Implementation Guide

### Adding a New Feature (Example: Order Entry Screen)

#### Step 1: Create Feature Module Structure

```
features/
└── orders/
    ├── OrderEntryScreen.kt       # UI
    ├── OrderViewModel.kt         # State management
    ├── components/
    │   ├── PriceInput.kt
    │   └── OrderButton.kt
    └── model/
        └── Order.kt
```

#### Step 2: Define Domain Model (commonMain)

```kotlin
// features/orders/model/Order.kt
@Serializable
data class Order(
    val id: String,
    val symbol: String,
    val side: OrderSide,
    val type: OrderType,
    val price: Double,
    val quantity: Double,
    val timestamp: Long
)

enum class OrderSide { BUY, SELL }
enum class OrderType { LIMIT, MARKET, STOP }
```

#### Step 3: Create Screen (commonMain)

```kotlin
// features/orders/OrderEntryScreen.kt
class OrderEntryScreen : Screen {
    @Composable
    override fun Content() {
        val viewModel = koinScreenModel<OrderViewModel>()
        val state by viewModel.state.collectAsState()
        
        OrderEntryContent(
            state = state,
            onPriceChange = viewModel::updatePrice,
            onQuantityChange = viewModel::updateQuantity,
            onSubmit = viewModel::submitOrder
        )
    }
}

@Composable
fun OrderEntryContent(
    state: OrderEntryState,
    onPriceChange: (Double) -> Unit,
    onQuantityChange: (Double) -> Unit,
    onSubmit: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        PriceInput(
            value = state.price,
            onValueChange = onPriceChange
        )
        
        QuantityInput(
            value = state.quantity,
            onValueChange = onQuantityChange
        )
        
        Button(
            onClick = onSubmit,
            enabled = state.isValid
        ) {
            Text("Submit Order")
        }
    }
}
```

#### Step 4: Create ViewModel (commonMain)

```kotlin
// features/orders/OrderViewModel.kt
class OrderViewModel(
    private val orderRepository: OrderRepository
) : ScreenModel {
    
    private val _state = MutableStateFlow(OrderEntryState())
    val state: StateFlow<OrderEntryState> = _state.asStateFlow()
    
    fun updatePrice(price: Double) {
        _state.update { it.copy(price = price) }
    }
    
    fun updateQuantity(quantity: Double) {
        _state.update { it.copy(quantity = quantity) }
    }
    
    fun submitOrder() {
        screenModelScope.launch {
            val order = Order(
                id = UUID.randomUUID().toString(),
                symbol = _state.value.symbol,
                side = _state.value.side,
                type = OrderType.LIMIT,
                price = _state.value.price,
                quantity = _state.value.quantity,
                timestamp = Clock.System.now().toEpochMilliseconds()
            )
            
            orderRepository.submitOrder(order)
        }
    }
}
```

#### Step 5: Register in DI (commonMain)

```kotlin
// di/AppModule.kt
val appModule = module {
    // ... existing
    
    screenModel { OrderViewModel(get()) }
    single<OrderRepository> { OrderRepositoryImpl(get()) }
}
```

#### Step 6: Add Navigation (commonMain)

```kotlin
// In App.kt or NavigationGraph.kt
Navigator(HomeScreen()) { navigator ->
    // ...
    FloatingActionButton(
        onClick = { navigator.push(OrderEntryScreen()) }
    ) {
        Icon(Icons.Default.Add, "New Order")
    }
}
```

---

## Performance Optimization

### 1. Chart Rendering (High-Frequency Updates)

Use Skiko Canvas for direct rendering:

```kotlin
@Composable
fun CandlestickChart(candles: List<Candle>) {
    Canvas(modifier = Modifier.fillMaxSize()) {
        val paint = Paint()
        
        candles.forEachIndexed { index, candle ->
            val x = index * barWidth
            val yHigh = candle.high.toCanvasY()
            val yLow = candle.low.toCanvasY()
            
            // Draw wick
            drawLine(
                color = Color.Gray,
                start = Offset(x, yHigh),
                end = Offset(x, yLow),
                strokeWidth = 1.dp.toPx()
            )
            
            // Draw body
            drawRect(
                color = if (candle.close > candle.open) 
                    TradingColors.bullGreen 
                    else TradingColors.bearRed,
                topLeft = Offset(x - barWidth/2, min(yOpen, yClose)),
                size = Size(barWidth, abs(yClose - yOpen))
            )
        }
    }
}
```

### 2. WebSocket Data Throttling

Prevent UI overload on high-frequency updates:

```kotlin
marketDataStream
    .sample(100) // Emit only every 100ms
    .collectLatest { tick ->
        _currentPrice.value = tick.price
    }
```

### 3. Lazy Loading

Use `LazyColumn` for large lists:

```kotlin
@Composable
fun SignalsList(signals: List<Signal>) {
    LazyColumn {
        items(
            items = signals,
            key = { it.id }
        ) { signal ->
            SignalCard(signal)
        }
    }
}
```

### 4. Image Optimization

Use compose resources for automatic platform optimization:

```kotlin
Image(
    painter = painterResource(Res.drawable.logo),
    contentDescription = "Logo"
)
```

---

## Deployment

### Web (Wasm) Deployment

1. **Build production bundle**:
   ```bash
   ./gradlew :composeApp:wasmJsBrowserDistribution
   ```

2. **Output files**:
   - `fks-trading-web.wasm` - WebAssembly binary
   - `fks-trading-web.js` - JavaScript loader
   - `index.html` - Entry page

3. **Deploy to static hosting**:
   ```bash
   # Netlify
   netlify deploy --prod --dir=composeApp/build/dist/wasmJs/productionExecutable/
   
   # Vercel
   vercel --prod composeApp/build/dist/wasmJs/productionExecutable/
   
   # AWS S3
   aws s3 sync composeApp/build/dist/wasmJs/productionExecutable/ s3://fks-trading-web/
   ```

### Desktop Deployment

1. **Build installers**:
   ```bash
   ./gradlew :composeApp:packageDistributionForCurrentOS
   ```

2. **Sign and notarize** (macOS):
   ```bash
   codesign --sign "Developer ID" FKS-Trading-Pro.dmg
   xcrun notarytool submit FKS-Trading-Pro.dmg
   ```

3. **Distribute**:
   - Upload to website
   - GitHub Releases
   - Microsoft Store (Windows)
   - Snap Store (Linux)

### Mobile Deployment

#### Android
1. Build release AAB:
   ```bash
   ./gradlew :composeApp:bundleRelease
   ```

2. Upload to Google Play Console

#### iOS
1. Archive in Xcode
2. Upload to App Store Connect
3. Submit for review

---

## Next Steps

### Immediate Tasks
1. ✅ Project structure created
2. ✅ Build configuration complete
3. 🔄 Implement core features:
   - Dashboard screen
   - Trading Wall with charts
   - Signal Matrix
4. 📋 Add WebSocket integration
5. 📋 Implement authentication
6. 📋 Add data persistence (local storage)

### Future Enhancements
- [ ] Multi-language support (i18n)
- [ ] Dark/Light theme toggle
- [ ] Offline mode with local caching
- [ ] Push notifications (mobile)
- [ ] Desktop system tray integration
- [ ] Export data to CSV/PDF
- [ ] Advanced charting (indicators, drawing tools)
- [ ] Real-time collaboration features

---

## References

- [Kotlin Multiplatform Docs](https://kotlinlang.org/docs/multiplatform.html)
- [Compose Multiplatform Docs](https://www.jetbrains.com/lp/compose-multiplatform/)
- [Voyager Navigation](https://voyager.adriel.cafe/)
- [Ktor Client](https://ktor.io/docs/client.html)
- [Koin DI](https://insert-koin.io/docs/reference/koin-mp/kmp)

---

**Architecture Version**: 1.0  
**Last Updated**: 2025-12-28  
**Maintainer**: FKS Trading Team