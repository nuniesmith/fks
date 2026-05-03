# Settings UI Integration Checklist

**Target:** Integrate Strategy Settings UI into FKS Application  
**Estimated Time:** 3-6 hours  
**Status:** Ready for Integration

---

## ✅ Pre-Integration Verification

- [x] ViewModel created: `StrategyConfigViewModel.kt`
- [x] Main screen created: `SettingsScreen.kt`
- [x] Preset dialog created: `PresetSelectionDialog.kt`
- [x] Config editor created: `CreateConfigDialog.kt`
- [x] Documentation complete
- [x] All files in correct location

---

## 📋 Integration Steps

### 1. Dependency Injection Setup

**File:** `composeApp/src/commonMain/kotlin/xyz/fkstrading/client/di/AppModule.kt`

```kotlin
// Add to existing modules or create new settingsModule
val settingsModule = module {
    viewModel { StrategyConfigViewModel(get()) }
}

// In startKoin block
startKoin {
    modules(
        databaseModule,        // Already exists
        settingsModule,        // NEW
        // ... other modules
    )
}
```

**Verification:**
- [ ] settingsModule created
- [ ] Module added to startKoin
- [ ] App builds without errors
- [ ] ViewModel can be resolved

---

### 2. Navigation Setup

**File:** `composeApp/src/commonMain/kotlin/xyz/fkstrading/client/navigation/NavGraph.kt` (or equivalent)

```kotlin
NavHost(navController, startDestination = "home") {
    // Existing routes...
    
    // NEW: Settings route
    composable("settings") {
        val viewModel: StrategyConfigViewModel = koinViewModel()
        SettingsScreen(
            viewModel = viewModel,
            onNavigateBack = { navController.navigateUp() }
        )
    }
}
```

**Verification:**
- [ ] Route "settings" added to NavHost
- [ ] ViewModel injection working
- [ ] Navigation compiles
- [ ] Can navigate to settings (test with button)

---

### 3. Main Menu Integration

**Option A: App Bar Action**

**File:** `composeApp/.../ui/components/FksAppBar.kt`

```kotlin
IconButton(
    onClick = { navController.navigate("settings") }
) {
    Icon(Icons.Default.Settings, "Settings")
}
```

**Option B: Navigation Drawer**

```kotlin
NavigationDrawerItem(
    label = { Text("Settings") },
    selected = false,
    onClick = {
        navController.navigate("settings")
        scope.launch { drawerState.close() }
    },
    icon = { Icon(Icons.Default.Settings, "Settings") }
)
```

**Option C: Bottom Navigation**

```kotlin
BottomNavigationItem(
    icon = { Icon(Icons.Default.Settings, "Settings") },
    label = { Text("Settings") },
    selected = currentRoute == "settings",
    onClick = { navController.navigate("settings") }
)
```

**Verification:**
- [ ] Settings menu item added
- [ ] Icon displayed correctly
- [ ] Click navigates to settings
- [ ] Back navigation works

---

### 4. Platform-Specific Testing

#### Desktop (JVM)
```bash
cd src/clients
./gradlew :composeApp:runDesktop
```

**Test:**
- [ ] App launches
- [ ] Navigate to Settings
- [ ] Create preset configuration
- [ ] Edit configuration
- [ ] Set as default
- [ ] Toggle active/inactive
- [ ] Delete configuration
- [ ] Back navigation

#### Android
```bash
./gradlew :android:installDebug
```

**Test:**
- [ ] Same tests as desktop
- [ ] Responsive layout on phone
- [ ] Responsive layout on tablet
- [ ] Material 3 theme correct

#### iOS (if applicable)
```bash
./gradlew :ios:runDebug
```

**Test:**
- [ ] Same tests as above
- [ ] Native navigation feel

---

### 5. Unit Testing

**Create:** `composeApp/.../settings/StrategyConfigViewModelTest.kt`

```kotlin
class StrategyConfigViewModelTest {
    private lateinit var repository: StrategyConfigRepository
    private lateinit var viewModel: StrategyConfigViewModel

    @BeforeTest
    fun setup() {
        // Use TestDatabaseDriverFactory
        val database = DatabaseWrapper(
            TestDatabaseDriverFactory.createInMemoryDriverFactory()
        )
        repository = StrategyConfigRepositoryImpl(database)
        viewModel = StrategyConfigViewModel(repository)
    }

    @Test
    fun `test createConfig emits success state`() = runTest {
        // Given
        val config = ExecutionConfig()
        
        // When
        viewModel.createConfig("Test Config", config)
        
        // Then
        val state = viewModel.uiState.value
        assertTrue(state is SettingsUiState.Success)
    }
    
    // Add more tests...
}
```

**Test Coverage Checklist:**
- [ ] Create configuration test
- [ ] Update configuration test
- [ ] Delete configuration test
- [ ] Set default test
- [ ] Toggle active test
- [ ] Create preset test
- [ ] Duplicate config test
- [ ] UI state transitions test

**Run Tests:**
```bash
./gradlew :composeApp:testDebugUnitTest
```

---

### 6. Integration Testing

**Test Scenarios:**

**Scenario 1: First-Time User**
- [ ] Open app (no configs exist)
- [ ] Navigate to Settings
- [ ] See empty state
- [ ] Click "Create Preset"
- [ ] Select Conservative
- [ ] Verify config created
- [ ] Verify set as default automatically

**Scenario 2: Creating Custom Config**
- [ ] Click "Create Custom"
- [ ] Enter name "My Strategy"
- [ ] Adjust risk to 3%
- [ ] Set stop loss to 5%
- [ ] Set max positions to 5
- [ ] Save
- [ ] Verify appears in list

**Scenario 3: Managing Configs**
- [ ] Create 3 different configs
- [ ] Set one as default (verify badge)
- [ ] Toggle one inactive (verify switch)
- [ ] Duplicate one (verify copy created)
- [ ] Delete one (verify confirmation dialog)
- [ ] Confirm deletion (verify removed)

**Scenario 4: Real Execution**
- [ ] Set conservative config as default
- [ ] Navigate to signal execution screen
- [ ] Execute signal with default config
- [ ] Verify correct config used
- [ ] Change default to aggressive
- [ ] Execute another signal
- [ ] Verify new config used

---

### 7. Performance Testing

**Metrics to Check:**
- [ ] Settings screen loads in < 500ms
- [ ] Config list scrolls smoothly (60 FPS)
- [ ] Dialogs open without lag
- [ ] State updates are instant
- [ ] No memory leaks (check profiler)

**Load Testing:**
- [ ] Create 50 configurations
- [ ] Verify list performance
- [ ] Verify search/filter (if implemented)
- [ ] Delete all (batch operation)

---

### 8. Accessibility Testing

**Checks:**
- [ ] All buttons have content descriptions
- [ ] Screen reader announces state changes
- [ ] Keyboard navigation works
- [ ] Tab order is logical
- [ ] High contrast mode works
- [ ] Text scaling supported

---

### 9. Documentation Updates

**Update Files:**
- [ ] Add Settings to user manual
- [ ] Update navigation documentation
- [ ] Add screenshots to docs
- [ ] Update CHANGELOG.md
- [ ] Create video tutorial (optional)

---

### 10. Code Review Checklist

**Review Points:**
- [ ] No hardcoded strings (use resources)
- [ ] Error handling comprehensive
- [ ] Loading states handled
- [ ] Edge cases covered
- [ ] Code follows project style guide
- [ ] No TODO comments left
- [ ] All public APIs documented
- [ ] No lint warnings

---

## 🚀 Deployment Checklist

### Pre-Deployment
- [ ] All tests passing (unit + integration)
- [ ] No compiler warnings
- [ ] Documentation complete
- [ ] Code reviewed and approved
- [ ] Performance benchmarks met
- [ ] Accessibility verified

### Deployment
- [ ] Merge to main branch
- [ ] Tag release version
- [ ] Update release notes
- [ ] Deploy to staging
- [ ] Verify on staging
- [ ] Deploy to production

### Post-Deployment
- [ ] Monitor error logs
- [ ] Check analytics for usage
- [ ] Gather user feedback
- [ ] Create issues for bugs/enhancements
- [ ] Plan next iteration

---

## 🐛 Troubleshooting

### Common Issues

**Issue:** ViewModel not found
**Solution:** Verify Koin module is loaded in startKoin

**Issue:** Navigation crashes
**Solution:** Check NavHost includes "settings" route

**Issue:** UI not updating
**Solution:** Verify StateFlow collection with collectAsState()

**Issue:** Database errors
**Solution:** Check DatabaseWrapper initialization in DI

**Issue:** Compilation errors
**Solution:** Verify all imports, check Kotlin version compatibility

---

## 📊 Success Criteria

### Minimum Viable Product (MVP)
- [x] Settings screen accessible
- [x] Can create configurations
- [x] Can set default
- [x] Can activate/deactivate
- [x] Can delete configurations
- [x] Presets available
- [x] Data persists across restarts

### Nice to Have
- [ ] Search and filter
- [ ] Import/Export
- [ ] Analytics integration
- [ ] Remote sync

### Future Enhancements
- [ ] Performance analytics per config
- [ ] A/B testing support
- [ ] Configuration marketplace
- [ ] AI optimization suggestions

---

## ✨ Final Verification

Before marking as complete:

- [ ] All checklist items above completed
- [ ] User acceptance testing passed
- [ ] No critical bugs remaining
- [ ] Documentation updated
- [ ] Team trained on new feature
- [ ] Support team briefed
- [ ] Release notes published

---

## 📝 Notes

**Started:** [DATE]  
**Completed:** [DATE]  
**Integrated By:** [NAME]  
**Reviewed By:** [NAME]  
**Issues Found:** [LINK TO ISSUES]

---

**Status:** ✅ Ready for Integration  
**Risk Level:** Low  
**Impact:** High (Major UX improvement)

Good luck with the integration! 🚀
