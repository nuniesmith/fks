# Settings UI Testing Checklist

**Test Date:** _________________  
**Tester:** _________________  
**Platform:** ☐ Desktop ☐ Android ☐ iOS  
**Build Version:** _________________

---

## Pre-Test Setup

- [ ] Build completes without errors
- [ ] All dependencies installed (Kotlin, Gradle, JDK 21)
- [ ] Database schema migrated successfully
- [ ] Koin DI modules registered correctly

---

## Navigation Tests

### From App Bar (All Platforms)
- [ ] Settings icon (⚙️) visible in top-right of app bar
- [ ] Clicking Settings icon navigates to Settings screen
- [ ] Back arrow in Settings screen returns to previous screen
- [ ] Navigation animation is smooth

### From Bottom Navigation (Mobile Only)
- [ ] Settings tab visible in bottom navigation on compact screens
- [ ] Settings tab NOT visible on tablet/desktop (>600dp width)
- [ ] Tapping Settings tab navigates to Settings screen
- [ ] Correct tab highlighted when on Settings screen

---

## Settings Screen UI

### Initial State (No Configurations)
- [ ] Empty state displays correctly
- [ ] "No Strategy Configurations" message shown
- [ ] Settings icon (large) displayed
- [ ] "Create Preset" button visible and clickable
- [ ] Help text explains what to do next

### Configuration List View
- [ ] All saved configurations displayed
- [ ] Configuration cards have correct layout
- [ ] Configuration name is bold and prominent
- [ ] Default badge shows on default configuration
- [ ] Active/inactive toggle switch visible on each card
- [ ] Cards are tappable to expand/collapse

### Expanded Configuration Card
- [ ] Card expands smoothly when tapped
- [ ] All parameters displayed:
  - [ ] Execution Mode
  - [ ] Position Sizing Method
  - [ ] Risk Per Trade (%)
  - [ ] Stop Loss (%)
  - [ ] Take Profit (%)
  - [ ] Max Positions
  - [ ] Min Confidence (%)
- [ ] Action buttons visible:
  - [ ] "Set Default" (if not already default)
  - [ ] "Duplicate"
  - [ ] "Edit"
  - [ ] Delete icon (trash)

---

## Create Configuration Tests

### Preset Creation
- [ ] "Add Preset" icon in app bar clickable
- [ ] Preset selection dialog appears
- [ ] Three presets listed:
  - [ ] Conservative
  - [ ] Balanced
  - [ ] Aggressive
- [ ] Each preset has icon and description
- [ ] Selecting preset creates configuration
- [ ] New configuration appears in list
- [ ] Success state/message displayed
- [ ] Dialog closes after creation

### Custom Configuration
- [ ] "Create Custom" button/icon clickable
- [ ] Create configuration dialog appears
- [ ] All input fields present:
  - [ ] Name (text input)
  - [ ] Description (optional text input)
  - [ ] Execution Mode (dropdown/selector)
  - [ ] Position Sizing (dropdown/selector)
  - [ ] Risk per trade (slider/input)
  - [ ] Stop loss % (slider/input)
  - [ ] Take profit % (slider/input)
  - [ ] Max positions (number input)
  - [ ] Min confidence (slider/input)
- [ ] Input validation works:
  - [ ] Name cannot be blank
  - [ ] Risk percentages are positive
  - [ ] Max positions > 0
  - [ ] Confidence between 0-100%
- [ ] "Cancel" button dismisses dialog
- [ ] "Create" button saves configuration
- [ ] Invalid inputs show error messages
- [ ] Created config appears in list immediately

---

## Edit Configuration Tests

- [ ] "Edit" button opens edit dialog
- [ ] Dialog pre-filled with current values
- [ ] All fields editable
- [ ] Changes save correctly
- [ ] Updated timestamp reflects change
- [ ] Cancel discards changes
- [ ] Configuration list updates reactively

---

## Configuration Actions

### Set as Default
- [ ] "Set Default" button visible on non-default configs
- [ ] Clicking sets config as default
- [ ] Default badge appears on selected config
- [ ] Previous default loses default badge
- [ ] Only one default at a time

### Toggle Active/Inactive
- [ ] Toggle switch changes state smoothly
- [ ] Active configs have switch ON (blue/green)
- [ ] Inactive configs have switch OFF (gray)
- [ ] Toggle persists across app restarts
- [ ] State change is immediate (no delay)

### Duplicate Configuration
- [ ] "Duplicate" button creates copy
- [ ] Copy has "(Copy)" appended to name
- [ ] Copy has new unique ID
- [ ] Copy is not default
- [ ] Copy appears in list immediately
- [ ] All parameters copied correctly

### Delete Configuration
- [ ] Delete icon clickable
- [ ] Confirmation dialog appears
- [ ] Dialog shows config name
- [ ] "Cancel" dismisses dialog without deleting
- [ ] "Delete" removes configuration
- [ ] Configuration disappears from list
- [ ] Cannot delete if only one config exists
- [ ] Cannot delete while executor is using it (future)

---

## Data Persistence

### Save & Reload
- [ ] Create configuration
- [ ] Close app completely
- [ ] Reopen app
- [ ] Navigate to Settings
- [ ] Configuration still exists with correct values
- [ ] Default status persisted
- [ ] Active status persisted

### Multiple Configurations
- [ ] Create 3+ configurations
- [ ] Set different ones as default
- [ ] Toggle different ones active/inactive
- [ ] Close and reopen app
- [ ] All configurations present
- [ ] Correct states maintained

---

## Error Handling

### Invalid Input
- [ ] Empty name shows error
- [ ] Negative risk % shows error
- [ ] Risk > 100% shows error
- [ ] Zero max positions shows error
- [ ] Error messages are clear and helpful

### Database Errors (Simulated)
- [ ] Handle database unavailable gracefully
- [ ] Show error message to user
- [ ] Don't crash app
- [ ] Allow retry

### Network Errors (Future - Remote Sync)
- [ ] Offline mode works (local-only)
- [ ] Sync error shows message
- [ ] Data preserved locally

---

## Performance Tests

### List Rendering
- [ ] List scrolls smoothly with 10+ configs
- [ ] Expand/collapse is instant
- [ ] No lag when toggling switches
- [ ] No memory leaks during navigation

### Database Operations
- [ ] Create operation < 100ms
- [ ] Update operation < 100ms
- [ ] Delete operation < 100ms
- [ ] List load < 200ms

---

## Platform-Specific Tests

### Desktop
- [ ] Window resize doesn't break layout
- [ ] Keyboard shortcuts work (if implemented)
- [ ] Click interactions precise
- [ ] Dialogs centered on screen

### Android
- [ ] Rotation preserves state
- [ ] Back button works correctly
- [ ] Touch targets ≥ 48dp
- [ ] Dialogs fit on small screens
- [ ] Bottom nav shows on phones, hides on tablets
- [ ] Keyboard doesn't cover inputs

### iOS
- [ ] Safe area insets respected
- [ ] Swipe back gesture works
- [ ] Platform-native feel (if custom styled)
- [ ] Keyboard "Done" button works
- [ ] Dialog styling matches platform

---

## Accessibility (Future)

- [ ] All buttons have content descriptions
- [ ] Screen reader can navigate settings
- [ ] Focus order is logical
- [ ] Color contrast meets WCAG AA
- [ ] Text scalable to 200%

---

## Integration with Strategy Executor

### Using Default Config
- [ ] Set a config as default
- [ ] Execute strategy without specifying config
- [ ] Executor uses default config
- [ ] Verify correct parameters applied

### Using Specific Config
- [ ] Execute strategy with config ID
- [ ] Executor uses specified config
- [ ] Verify correct parameters applied

### Fallback Behavior
- [ ] Delete all configs
- [ ] Executor creates default conservative config
- [ ] No crash occurs
- [ ] Warning logged

---

## Regression Tests

After each change, verify:
- [ ] All existing configs still load
- [ ] Default config still marked correctly
- [ ] No duplicate configs created
- [ ] Navigation still works
- [ ] No new compilation warnings/errors

---

## Edge Cases

### Boundary Conditions
- [ ] 0 configurations (handled)
- [ ] 1 configuration (cannot delete)
- [ ] 100+ configurations (performance OK)
- [ ] Very long config name (truncates gracefully)
- [ ] Special characters in name (handled)

### Concurrent Actions
- [ ] Rapid clicking doesn't duplicate actions
- [ ] Switching configs while editing cancels correctly
- [ ] Multiple deletions queued handled correctly

---

## User Experience

### Visual Polish
- [ ] Icons are clear and recognizable
- [ ] Colors follow app theme
- [ ] Spacing is consistent
- [ ] Animations are smooth (not jarring)
- [ ] Loading states shown when appropriate

### Usability
- [ ] Common actions require few taps
- [ ] Destructive actions require confirmation
- [ ] Feedback provided for all actions
- [ ] Error messages are actionable
- [ ] Empty states guide user to action

---

## Final Sign-Off

### Blocker Issues (Must Fix)
Count: ______  
List:
1. _________________________________
2. _________________________________
3. _________________________________

### Minor Issues (Nice to Fix)
Count: ______  
List:
1. _________________________________
2. _________________________________
3. _________________________________

### Overall Assessment
☐ **Pass** - Ready for production  
☐ **Pass with Minor Issues** - OK to ship, fix in next release  
☐ **Fail** - Blocker issues must be resolved

---

**Tester Signature:** _____________________  
**Date:** _____________________  
**Notes:**

_____________________________________________________________
_____________________________________________________________
_____________________________________________________________
_____________________________________________________________
_____________________________________________________________

---

## Automation Candidates

Tests suitable for automation:
- [ ] Configuration CRUD operations
- [ ] Validation rules
- [ ] Data persistence
- [ ] Default/active state management
- [ ] Duplicate functionality

See `StrategyConfigViewModelTest.kt` for automated test suite.