# Kotlin/KMP Tests - Quick Reference

## Running Tests Locally

### All Tests
```bash
cd src/clients
./gradlew :shared:allTests
```

### Desktop/JVM Tests (Fastest)
```bash
./gradlew :shared:desktopTest
```

### Android Tests
```bash
./gradlew :shared:testDebugUnitTest
```

### With Coverage
```bash
./gradlew :shared:desktopTest :shared:koverHtmlReport
# Open: shared/build/reports/kover/html/index.html
```

## Test Statistics

```
Total Tests:     148
Test Files:        6
Success Rate:   100%

Breakdown:
  HttpClientFactoryTest  →  19 tests
  ApiResponsesTest       →  19 tests
  OrderTest              →  37 tests
  PositionTest           →  47 tests
  SignalTest             →  21 tests
  ApiIntegrationTest     →   5 tests
```

## CI Integration

### CI Job Name
`kotlin-kmp-quality-and-tests`

### Execution Time
~2-3 minutes (with Gradle caching)

### What Gets Tested
1. Kotlin formatting (detekt - optional)
2. Build all KMP targets
3. Run commonTest suite
4. Run JVM/Desktop tests
5. Run Android unit tests (optional)
6. Generate JUnit reports
7. Upload test artifacts

### Failure Behavior
- **Critical**: Blocks pipeline if tests fail
- **Included in**: test-summary gate
- **Parallel with**: Rust & Python tests

## Adding New Tests

### 1. Create Test File
```kotlin
// Location: src/clients/shared/src/commonTest/kotlin/...
package xyz.fkstrading.shared.domain.models

import kotlin.test.Test
import kotlin.test.assertEquals

class MyFeatureTest {
    @Test
    fun `should do something`() {
        // Arrange
        val feature = MyFeature()
        
        // Act
        val result = feature.doSomething()
        
        // Assert
        assertEquals(expected, result)
    }
}
```

### 2. Run Tests
```bash
./gradlew :shared:desktopTest --tests "*MyFeatureTest"
```

### 3. Verify in CI
Push to branch → CI runs automatically → Check Actions tab

## Common Issues

### Tests Pass Locally, Fail in CI
```bash
# Clean and rebuild
./gradlew clean
./gradlew :shared:desktopTest
```

### Gradle Daemon Issues
```bash
./gradlew --stop
./gradlew :shared:desktopTest
```

### WASM Tests Fail
CI skips WASM tests (no headless browser). This is expected.

### Android SDK Missing
```bash
export ANDROID_HOME=~/android-sdk
# Or install Android SDK
```

## Test File Locations

```
src/clients/shared/src/
├── commonMain/kotlin/
│   └── xyz/fkstrading/shared/
│       ├── data/
│       │   ├── api/
│       │   │   ├── ApiClient.kt
│       │   │   ├── ApiClientImpl.kt
│       │   │   └── HttpClientFactory.kt
│       │   └── models/
│       │       └── ApiResponses.kt
│       └── domain/models/
│           ├── Order.kt
│           ├── Position.kt
│           └── Signal.kt
└── commonTest/kotlin/
    └── xyz/fkstrading/shared/
        ├── data/
        │   ├── api/
        │   │   └── HttpClientFactoryTest.kt      ← NEW
        │   └── models/
        │       └── ApiResponsesTest.kt           ← NEW
        ├── domain/models/
        │   ├── OrderTest.kt
        │   ├── PositionTest.kt
        │   └── SignalTest.kt
        └── integration/
            └── ApiIntegrationTest.kt
```

## Test Coverage Areas

### ✅ Covered
- Domain models (Order, Position, Signal)
- API response DTOs
- HTTP client factory
- DTO → Domain conversions
- Validation logic
- Calculations (P&L, risk/reward)

### 🔲 TODO
- API client implementation (mocked)
- Dependency injection modules
- WebSocket client
- Repository implementations
- Use case/business logic

## CI Workflow File

**Location**: `.github/workflows/ci.yml`

**Job Section**:
```yaml
kotlin-kmp-quality-and-tests:
  name: 🎯 Kotlin/KMP Quality & Tests
  runs-on: ubuntu-latest
  timeout-minutes: 30
  # ... steps ...
```

## Documentation

- **Full Summary**: `docs/CI_KOTLIN_TESTS_SUMMARY.md`
- **This Quick Ref**: `docs/KOTLIN_TESTS_QUICK_REF.md`
- **CI Workflow**: `.github/workflows/ci.yml`

## Useful Commands

```bash
# Validate CI YAML
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

# Check test count
find src/clients/shared/src/commonTest -name "*.kt" | wc -l

# View test results
open src/clients/shared/build/reports/tests/desktopTest/index.html

# Run with info logging
./gradlew :shared:desktopTest --info

# Run specific test class
./gradlew :shared:desktopTest --tests "*OrderTest"

# Run specific test method
./gradlew :shared:desktopTest --tests "*OrderTest.should do something*"

# Continuous test execution (watch mode)
./gradlew -t :shared:desktopTest
```

## Next Steps

1. Add code coverage reporting (Kover)
2. Add detekt configuration for linting
3. Expand test coverage to ApiClientImpl
4. Add mutation testing
5. Add contract tests (Pact)

---

**Last Updated**: January 2, 2026  
**Contact**: Development Team  
**Related**: CI_KOTLIN_TESTS_SUMMARY.md