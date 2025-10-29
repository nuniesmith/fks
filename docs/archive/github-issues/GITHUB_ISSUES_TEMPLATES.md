# FKS GitHub Issues - Task Templates

This document provides copy-paste templates for creating GitHub issues for each phase of development.

## How to Use

1. Copy the template for the task you want to create
2. Go to https://github.com/nuniesmith/fks/issues/new
3. Paste the template
4. Add appropriate labels (see label guide below)
5. Create the issue

## Label Guide

### Priority Labels
- `priority:P1` - Critical, blocks other work
- `priority:P2` - High, core features
- `priority:P3` - Medium, improvements
- `priority:P4` - Low, nice-to-have

### Impact Labels
- `impact:high` - Unblocks revenue/core features
- `impact:medium` - Improves efficiency
- `impact:low` - Nice-to-have

### Urgency Labels
- `urgency:high` - Blocks other tasks
- `urgency:medium` - Time-sensitive
- `urgency:low` - Can wait

### Effort Labels
- `effort:small` - <1 day
- `effort:medium` - 1-3 days
- `effort:large` - >3 days

### Type Labels
- `type:bug` - Something broken
- `type:feature` - New functionality
- `type:refactor` - Code improvement
- `type:security` - Security issue
- `type:test` - Testing-related

### Phase Labels
- `phase:1-immediate` - Phase 1: Immediate Fixes
- `phase:2-core` - Phase 2: Core Development
- `phase:3-testing` - Phase 3: Testing & QA
- `phase:4-accounts` - Phase 4: Account Integration
- `phase:5-viz` - Phase 5: Visualization
- `phase:6-advanced` - Phase 6: Advanced Features

---

## Phase 1: Immediate Fixes

### Issue #1: Security Hardening

```markdown
## Summary
Generate secure passwords and configure security features before any deployment.

## Priority
**Impact**: High | **Urgency**: High | **Effort**: 3 hours  
**Labels**: `priority:P1`, `impact:high`, `urgency:high`, `effort:small`, `type:security`, `phase:1-immediate`

## Description
Current `.env` file has placeholder passwords that pose security risks. Need to generate secure secrets and configure Django security features.

## Tasks
- [ ] **Hour 1**: Generate secure passwords
  - Use `openssl rand -base64 32` for POSTGRES_PASSWORD
  - Use `openssl rand -base64 32` for PGADMIN_PASSWORD
  - Use `openssl rand -base64 32` for REDIS_PASSWORD
  - Generate Django SECRET_KEY using `get_random_secret_key()`
  - Update `.env` file (DO NOT COMMIT)
  - Update `.env.example` with instructions

- [ ] **Hour 2**: Configure django-axes and django-ratelimit
  - Add `django-axes` and `django-ratelimit` to `INSTALLED_APPS`
  - Set `AXES_FAILURE_LIMIT=5` in settings
  - Configure rate limiting middleware
  - Test API endpoints for rate limiting

- [ ] **Hour 3**: Enable DB SSL and run security audit
  - Add `sslmode=require` to database connection string
  - Run `pip-audit` to check for CVE vulnerabilities
  - Update any vulnerable packages
  - Document security setup in `docs/SECURITY_SETUP.md`

## Dependencies
None - this is a blocker for all other work

## Acceptance Criteria
- [ ] All passwords are cryptographically secure (32+ characters)
- [ ] `.env` is in `.gitignore`
- [ ] `.env.example` has clear instructions for generating secrets
- [ ] Rate limiting is functional (test with multiple rapid requests)
- [ ] No high/critical CVEs in dependencies
- [ ] SSL is enabled for database connections

## References
- [Django Security Settings](https://docs.djangoproject.com/en/5.2/topics/security/)
- [django-axes Documentation](https://django-axes.readthedocs.io/)
- [Agent Instructions](../.github/copilot-instructions.md#security-hardening)
```

---

### Issue #2: Fix Import and Test Failures

```markdown
## Summary
Fix 20 failing tests caused by legacy microservices imports to reach 34/34 tests passing.

## Priority
**Impact**: High | **Urgency**: High | **Effort**: 11 hours  
**Labels**: `priority:P1`, `impact:high`, `urgency:high`, `effort:medium`, `type:refactor`, `phase:1-immediate`

## Description
Legacy imports from microservices architecture (`config`, `shared_python`) are causing 20 tests to fail. This blocks all testing and code validation.

## Affected Files
- `src/core/database/models.py` (line 10)
- `src/trading/backtest/engine.py` (line 16)
- `src/trading/signals/generator.py` (line 11)
- `src/trading/optimizer/engine.py` (via backtest import)
- `src/data/adapters/base.py` (lines 20, 24)

## Tasks

### Hours 1-2: Create Framework Constants
- [ ] Create `src/framework/config/constants.py`
- [ ] Add trading symbols:
  ```python
  SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
  MAINS = ['BTC', 'ETH']
  ALTS = ['BNB', 'ADA', 'SOL']
  FEE_RATE = 0.001
  RISK_PER_TRADE = 0.02
  ```
- [ ] Test imports work from multiple modules

### Hours 3-6: Update Import Statements
- [ ] Update `src/core/database/models.py`
  - Replace: `from config import SYMBOLS`
  - With: `from framework.config.constants import SYMBOLS`
- [ ] Update `src/trading/backtest/engine.py`
- [ ] Update `src/trading/signals/generator.py`
- [ ] Update `src/data/adapters/base.py`
  - Replace: `from shared_python.config import get_settings`
  - With: `from django.conf import settings`
- [ ] Update all test files with similar issues

### Hours 7-9: Fix and Verify Tests
- [ ] Run `pytest tests/unit/test_api/ -v` (should still pass - 14 tests)
- [ ] Run `pytest tests/unit/test_trading/ -v` (fix failures)
- [ ] Run `pytest tests/integration/ -v` (fix failures)
- [ ] Run full suite: `pytest tests/ -v`
- [ ] Target: 34/34 passing

### Hours 10-11: GitHub Action Setup
- [ ] Create `.github/workflows/test.yml`
- [ ] Configure to run on push and PR
- [ ] Run pytest with coverage report
- [ ] Run analyze script and commit summary
- [ ] Test workflow locally with `act` if possible

## Dependencies
- Depends on: Issue #1 (Security Hardening) for secure test environment

## Acceptance Criteria
- [ ] All 34 tests passing
- [ ] No imports from `config` or `shared_python` modules
- [ ] Framework constants properly defined and accessible
- [ ] GitHub Action runs successfully on push
- [ ] Coverage report generated in CI

## References
- [Known Test Failures](../.github/copilot-instructions.md#known-test-failures-to-fix)
- [Framework Config](../src/framework/config/README.md)
```

---

### Issue #3: Code Cleanup

```markdown
## Summary
Remove empty files, merge duplicates, and run code formatting for clean codebase.

## Priority
**Impact**: Medium | **Urgency**: Medium | **Effort**: 5 hours  
**Labels**: `priority:P2`, `impact:medium`, `urgency:medium`, `effort:small`, `type:refactor`, `phase:1-immediate`

## Description
Analyze script identified 25+ empty/stub files and 6+ legacy duplicates that need cleanup.

## Tasks

### Hour 1: Review Empty Files
- [ ] Run analyze script: `python scripts/analyze.py --type=python`
- [ ] Review output for empty `__init__.py` files
- [ ] Identify which are necessary package markers vs. true stubs
- [ ] Create list of files to delete vs. flesh out

### Hours 2-3: Cleanup Empty Files
- [ ] Delete obsolete empty files
- [ ] Flesh out stubs with basic implementations or docstrings
- [ ] For each kept file, add at minimum:
  ```python
  """
  Module description.
  
  This module is responsible for...
  """
  ```
- [ ] Test imports still work after changes

### Hour 4: Merge Legacy Duplicates
- [ ] Identify duplicate files:
  - `trading/backtest/engine.py` vs `legacy_engine.py`
  - `trading/signals/generator.py` vs `legacy_generator.py`
  - Others identified by analyze script
- [ ] Compare implementations
- [ ] Merge best features into single file
- [ ] Update imports referencing old files
- [ ] Delete legacy versions

### Hour 5: Code Formatting
- [ ] Run `black src/ tests/` to format all Python
- [ ] Run `isort src/ tests/` to organize imports
- [ ] Run `ruff check src/ tests/` and fix top issues
- [ ] Commit with message: "chore: code cleanup and formatting"

## Dependencies
- Depends on: Issue #2 (Import Fixes) to avoid conflicts

## Acceptance Criteria
- [ ] <5 empty files remaining (only necessary `__init__.py`)
- [ ] 0 duplicate legacy files
- [ ] All code passes `black --check`
- [ ] All code passes `isort --check`
- [ ] Ruff shows <10 warnings
- [ ] Analyze script shows improvement

## References
- [Code Style Guide](../.github/copilot-instructions.md#code-style--quality)
```

---

## Phase 2: Core Development

### Issue #4: Implement Market Data Sync Task

```markdown
## Summary
Implement the first Celery task to sync market data from Binance to TimescaleDB.

## Priority
**Impact**: High | **Urgency**: High | **Effort**: 4 hours  
**Labels**: `priority:P1`, `impact:high`, `urgency:high`, `effort:small`, `type:feature`, `phase:2-core`

## Description
Foundation task for all trading features. Fetches OHLCV data from Binance and stores in TimescaleDB hypertable.

## Tasks

### Hour 1: Core Implementation
- [ ] Open `src/trading/tasks.py`
- [ ] Implement `sync_market_data_task`:
  ```python
  @shared_task(bind=True, max_retries=3)
  def sync_market_data_task(self, symbol: str, interval: str = "1h"):
      """
      Sync market data from Binance for given symbol.
      
      Args:
          symbol: Trading pair (e.g., "BTCUSDT")
          interval: Timeframe (e.g., "1h", "1d")
          
      Returns:
          dict: Summary of synced data
      """
      # Implementation here
  ```
- [ ] Use `ccxt` library for Binance API
- [ ] Fetch last 100 candles for symbol

### Hour 2: Error Handling
- [ ] Add try/except for API errors
- [ ] Implement retry logic for rate limits
- [ ] Log errors with context
- [ ] Handle network timeouts
- [ ] Return proper error responses

### Hour 3: Database Storage
- [ ] Store data in TimescaleDB hypertable
- [ ] Use bulk insert for performance
- [ ] Handle duplicate records gracefully
- [ ] Add proper indexing

### Hour 4: Testing
- [ ] Write unit tests with mocked Binance API
- [ ] Test error scenarios
- [ ] Test database storage
- [ ] Manual test with real API (rate limits!)

## Dependencies
- Depends on: Issue #2 (tests passing)
- Requires: TimescaleDB running (`make up`)

## Acceptance Criteria
- [ ] Task successfully fetches 100 candles
- [ ] Data stored in database with correct schema
- [ ] Error handling covers API failures
- [ ] Tests pass with >80% coverage
- [ ] Can see task in Flower dashboard
- [ ] No API rate limit violations

## References
- [Celery Tasks Guide](../.github/copilot-instructions.md#celery-tasks)
- [CCXT Documentation](https://docs.ccxt.com/)
```

---

### Issue #5: Implement Signal Generation Task

```markdown
## Summary
Implement Celery task to generate trading signals using technical indicators.

## Priority
**Impact**: High | **Urgency**: Medium | **Effort**: 6 hours  
**Labels**: `priority:P2`, `impact:high`, `urgency:medium`, `effort:small`, `type:feature`, `phase:2-core`

## Description
Core trading feature that calculates RSI, MACD, Bollinger Bands and generates buy/sell signals.

## Tasks

### Hours 1-2: Technical Indicators
- [ ] Implement `calculate_indicators_task`
- [ ] Add RSI calculation (14-period default)
- [ ] Add MACD calculation (12, 26, 9)
- [ ] Add Bollinger Bands (20-period, 2 std dev)
- [ ] Add SMA (multiple periods)

### Hours 3-4: Signal Logic
- [ ] Implement `generate_signals_task`
- [ ] Define signal rules:
  - RSI < 30 = oversold (potential buy)
  - RSI > 70 = overbought (potential sell)
  - MACD crossover = trend change
  - Price touches Bollinger Band = potential reversal
- [ ] Combine multiple indicators
- [ ] Add confidence scores

### Hours 5-6: Testing and Validation
- [ ] Unit tests for each indicator
- [ ] Test signal generation logic
- [ ] Backtest on historical data
- [ ] Validate accuracy with known scenarios

## Dependencies
- Depends on: Issue #4 (market data available)

## Acceptance Criteria
- [ ] All indicators calculate correctly
- [ ] Signals generated with confidence scores
- [ ] Tests show >75% accuracy on historical data
- [ ] Signals stored in database
- [ ] Can view signals in admin panel

## References
- [Signal Generation](../src/trading/signals/generator.py)
- [Technical Indicators](https://technical-analysis-library-in-python.readthedocs.io/)
```

---

### Issue #6: Complete RAG Document Processor

```markdown
## Summary
Implement document chunking and processing for RAG system.

## Priority
**Impact**: High | **Urgency**: Medium | **Effort**: 3 hours  
**Labels**: `priority:P2`, `impact:high`, `urgency:medium`, `effort:small`, `type:feature`, `phase:2-core`

## Description
Core RAG component that chunks trading data for embeddings and semantic search.

## Tasks

### Hours 1-2: Chunking Logic
- [ ] Implement `DocumentProcessor` class in `src/web/rag/document_processor.py`
- [ ] Add chunking for OHLCV data (time-based windows)
- [ ] Add chunking for trade records (semantic grouping)
- [ ] Add metadata preservation (timestamp, symbol, etc.)
- [ ] Handle edge cases (incomplete data, missing fields)

### Hour 3: Testing
- [ ] Unit tests for chunking
- [ ] Test with sample trading data
- [ ] Verify metadata preservation
- [ ] Test performance with large datasets

## Dependencies
- None - foundational RAG component

## Acceptance Criteria
- [ ] Chunks created with appropriate size (512-1024 tokens)
- [ ] Metadata preserved for each chunk
- [ ] Performance <100ms per document
- [ ] Tests pass with >80% coverage

## References
- [RAG Architecture](../.github/copilot-instructions.md#rag-architecture)
```

---

## Creating Issues via GitHub CLI

If you have `gh` CLI installed:

```bash
# Phase 1
gh issue create --title "Security Hardening" --body-file templates/issue-1.md --label "priority:P1,impact:high,urgency:high,effort:small,type:security,phase:1-immediate"

gh issue create --title "Fix Import and Test Failures" --body-file templates/issue-2.md --label "priority:P1,impact:high,urgency:high,effort:medium,type:refactor,phase:1-immediate"

gh issue create --title "Code Cleanup" --body-file templates/issue-3.md --label "priority:P2,impact:medium,urgency:medium,effort:small,type:refactor,phase:1-immediate"

# Phase 2
gh issue create --title "Implement Market Data Sync Task" --body-file templates/issue-4.md --label "priority:P1,impact:high,urgency:high,effort:small,type:feature,phase:2-core"

gh issue create --title "Implement Signal Generation Task" --body-file templates/issue-5.md --label "priority:P2,impact:high,urgency:medium,effort:small,type:feature,phase:2-core"

gh issue create --title "Complete RAG Document Processor" --body-file templates/issue-6.md --label "priority:P2,impact:high,urgency:medium,effort:small,type:feature,phase:2-core"
```

---

## Bulk Issue Creation Script

Create `scripts/create_issues.sh`:

```bash
#!/bin/bash

# Create all Phase 1 issues
echo "Creating Phase 1 issues..."
# Add gh commands here

echo "✅ All issues created!"
echo "View at: https://github.com/nuniesmith/fks/issues"
```

Make executable: `chmod +x scripts/create_issues.sh`
