# KMP Quick Reference Card

## 🚀 Commands

### Run
```bash
# Web (localhost:8080)
./gradlew :composeApp:wasmJsBrowserDevelopmentRun

# Desktop
./gradlew :composeApp:run

# Android
./gradlew :composeApp:installDebug

# iOS
open iosApp/iosApp.xcodeproj
```

### Build
```bash
# Web production
./gradlew :composeApp:wasmJsBrowserDistribution

# Desktop package
./gradlew :composeApp:packageDistributionForCurrentOS

# Android release
./gradlew :composeApp:bundleRelease
```

## 📁 Structure

```
composeApp/src/
├── commonMain/          # 95% shared
│   ├── features/        # Screens & ViewModels
│   ├── core/            # Domain & Data
│   ├── ui/components/   # Reusable UI
│   └── theme/           # Design system
├── androidMain/         # 2% Android
├── iosMain/             # 2% iOS
├── desktopMain/         # 1% Desktop
└── wasmJsMain/          # 1% Web
```

## 🎨 Theme

```kotlin
TradingColors.bullGreen      // #00E676
TradingColors.bearRed        // #FF5252
MonospaceStyles.priceText    // 16sp
```

## 🔧 Common Tasks

### Add Feature
1. Create `features/yourFeature/YourScreen.kt`
2. Write Compose UI (works on ALL platforms)
3. Register in `di/AppModule.kt`
4. Navigate: `navigator.push(YourScreen())`

### Platform Code
```kotlin
// commonMain
expect fun getPlatform(): String

// androidMain
actual fun getPlatform() = "Android"
```

### Responsive Layout
```kotlin
BoxWithConstraints {
    when {
        maxWidth >= 1200.dp -> DesktopLayout()
        maxWidth >= 600.dp -> TabletLayout()
        else -> MobileLayout()
    }
}
```

## 📚 Docs
- `KMP_ARCHITECTURE.md` - Full architecture (768 lines)
- `README.md` - Getting started (435 lines)
- `KMP_IMPLEMENTATION_SUMMARY.md` - Status report (764 lines)
