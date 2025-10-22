#!/bin/bash
# Script to import FKS development tasks as GitHub issues
# Usage: ./scripts/import_github_issues.sh

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== FKS GitHub Issues Import ===${NC}"
echo "This will create 19 issues across 7 phases"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed${NC}"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub CLI${NC}"
    echo "Run: gh auth login"
    exit 1
fi

echo -e "${GREEN}✓ GitHub CLI ready${NC}"
echo ""

# Create milestones for each phase
echo -e "${BLUE}Creating milestones...${NC}"

gh api repos/:owner/:repo/milestones -X POST -f title="Phase 1: Immediate Fixes" -f description="Weeks 1-4; 20-30 hours total" -f state="open" 2>/dev/null || echo "Phase 1 milestone may already exist"
gh api repos/:owner/:repo/milestones -X POST -f title="Phase 2: Core Development" -f description="Weeks 5-10; 60-80 hours total" -f state="open" 2>/dev/null || echo "Phase 2 milestone may already exist"
gh api repos/:owner/:repo/milestones -X POST -f title="Phase 3: Testing & QA" -f description="Weeks 7-12; 12-15 hours total (Parallel with Phase 2)" -f state="open" 2>/dev/null || echo "Phase 3 milestone may already exist"
gh api repos/:owner/:repo/milestones -X POST -f title="Phase 4: Documentation" -f description="Weeks 11-12; 7 hours total" -f state="open" 2>/dev/null || echo "Phase 4 milestone may already exist"
gh api repos/:owner/:repo/milestones -X POST -f title="Phase 5: Deployment & Monitoring" -f description="Weeks 13-18; 13 hours total" -f state="open" 2>/dev/null || echo "Phase 5 milestone may already exist"
gh api repos/:owner/:repo/milestones -X POST -f title="Phase 6: Optimization & Maintenance" -f description="Ongoing; 15 hours total" -f state="open" 2>/dev/null || echo "Phase 6 milestone may already exist"
gh api repos/:owner/:repo/milestones -X POST -f title="Phase 7: Future Features" -f description="Weeks 19+; 28 hours total" -f state="open" 2>/dev/null || echo "Phase 7 milestone may already exist"

echo -e "${GREEN}✓ Milestones created${NC}"
echo ""

# Function to create issue
create_issue() {
    local title="$1"
    local body="$2"
    local labels="$3"
    local milestone="$4"
    
    echo -e "${BLUE}Creating: ${title}${NC}"
    gh issue create \
        --title "$title" \
        --body "$body" \
        --label "$labels" \
        --milestone "$milestone" || echo -e "${RED}Failed to create issue: ${title}${NC}"
}

# PHASE 1 ISSUES

echo -e "${BLUE}=== Phase 1: Immediate Fixes ===${NC}"

# Issue 1: Security Hardening
create_issue \
    "Security Hardening" \
    "## Overview
**Phase**: 1 - Immediate Fixes
**Impact**: High
**Urgency**: High
**Effort**: Medium (~3 hours)
**Dependencies**: None

## Description
Implement comprehensive security hardening including secure password generation, port exposure removal, rate limiting, and vulnerability patching.

## Hour-by-Hour Breakdown

### Hour 1: Secure Passwords & Database
- Generate secure passwords using pwgen or similar tool
- Update .env file with new values:
  - POSTGRES_PASSWORD
  - PGADMIN_PASSWORD
  - REDIS_PASSWORD
- Test local database connections
- Verify no connection errors

### Hour 2: Port Security & SSL
- Modify docker-compose.yml to remove external port exposures
- Set ports to internal only (no host binding)
- Add sslmode=require to DB environment variables
- Restart services: \`make down && make up\`
- Verify no external access possible

### Hour 3: Rate Limiting & Vulnerability Audit
- Install django-axes and django-ratelimit
- Configure in settings.py:
  - AXES_FAILURE_LIMIT=5
  - Add rate limiting middleware
- Run pip-audit to check for vulnerabilities
- Update 1-2 vulnerable libraries if found
- Re-test application functionality

## Verification
- [ ] All passwords updated and documented securely
- [ ] No external port access (test with nmap or netstat)
- [ ] Rate limiting active (test login failures)
- [ ] pip-audit shows no critical vulnerabilities
- [ ] Run analyze script shows clean security status

## Notes
- Run analyze script at end of task
- Prioritize immediate updates if vulnerabilities found
- Document new passwords in secure password manager" \
    "impact:high,urgency:high,effort:medium,phase:1" \
    "Phase 1: Immediate Fixes"

# Issue 2: Fix Import/Test Failures
create_issue \
    "Fix Import/Test Failures" \
    "## Overview
**Phase**: 1 - Immediate Fixes
**Impact**: High
**Urgency**: High
**Effort**: High (~11 hours)
**Dependencies**: Issue #1 (Security Hardening)

## Description
Resolve all legacy import errors from microservices migration and fix failing tests. Target 80%+ test pass rate with 50%+ code coverage.

## Hour-by-Hour Breakdown

### Hours 1-2: Legacy Import Migration
- Scan codebase for legacy imports:
  - \`grep -r \"from config\" src/\`
  - \`grep -r \"shared_python\" src/\`
- Replace 5-10 instances with framework equivalents:
  - \`from config\` → \`from framework.config\`
  - \`shared_python\` → \`from django.conf import settings\`
- Update affected files in src/trading/, src/core/, src/data/

### Hours 3-4: Fix Initial Test Batch
- Run \`pytest tests/ -v\` to identify failures
- Fix 5 failing tests (focus on import-related errors)
- Priority files:
  - tests/unit/test_core/test_database.py
  - tests/unit/test_trading/test_assets.py
- Verify fixes with \`pytest tests/ -v\`

### Hours 5-6: Fix Remaining Tests
- Fix another 5-10 failing tests
- Target files:
  - tests/integration/test_backtest/*
  - tests/integration/test_data/*
- Aim for 20+ passing tests
- Document any remaining blockers

### Hour 7: Coverage Analysis
- Run \`pytest --cov=src --cov-report=html\`
- Identify low-coverage areas (<30%)
- Add 2-3 basic unit tests for critical paths
- Focus on src/trading/tasks.py and src/core/

### Hours 8-9: Expand Test Coverage
- Continue adding tests to hit 50% coverage
- Write tests for:
  - Signal generation functions
  - Database model methods
  - Utility functions
- Debug any new test failures

### Hours 10-11: CI/CD Integration
- Create .github/workflows/test.yml
- Configure pytest + coverage reporting
- Add analyze script to workflow
- Test locally with act or push to branch
- Verify workflow runs successfully

## Verification
- [ ] No legacy import errors remain
- [ ] 80%+ tests passing (aim for 30+/34)
- [ ] 50%+ code coverage
- [ ] CI/CD workflow running
- [ ] All import errors documented and resolved

## Notes
- If stuck on imports, search for patterns with grep
- Re-run pytest after each batch of fixes
- Refer to docs/IMPORT_GUIDE.md for migration patterns" \
    "impact:high,urgency:high,effort:high,phase:1" \
    "Phase 1: Immediate Fixes"

# Issue 3: Code Cleanup
create_issue \
    "Code Cleanup" \
    "## Overview
**Phase**: 1 - Immediate Fixes
**Impact**: Medium
**Urgency**: Medium
**Effort**: Medium (~5 hours)
**Dependencies**: Issue #2 (Fix Import/Test Failures)

## Description
Clean up codebase by removing obsolete files, fleshing out stubs, merging duplicates, and applying consistent formatting.

## Hour-by-Hour Breakdown

### Hour 1: Remove Obsolete Files
- Run analyze script to list empty/small files
- Review output for deletion candidates
- Delete 10+ obsolete files:
  - Empty __init__.py files (if not needed)
  - Unused legacy modules
  - Duplicate test files
- Commit changes with descriptive message

### Hour 2: Flesh Out Stub Files
- Identify 5-10 remaining small files (<10 lines)
- Add basic implementations:
  - Docstrings
  - Type hints
  - Basic logic (not full implementation)
- Focus on files in src/trading/ and src/core/

### Hour 3: Merge Duplicate Files
- Identify duplicates (e.g., multiple engine.py files)
- Compare implementations:
  - src/trading/backtest/engine.py
  - Any other engine.py variants
- Merge into single canonical version
- Keep best implementation, remove others

### Hour 4: Update Import References
- Find all imports referencing merged files
- Update to point to canonical location
- Test affected modules:
  - \`pytest tests/unit/test_trading/\`
  - \`pytest tests/integration/test_backtest/\`
- Verify no import errors

### Hour 5: Apply Code Formatting
- Run \`make format\` (black + isort)
- Run \`make lint\` (ruff + mypy)
- Fix top 10 linting issues
- Re-run to verify clean output
- Commit formatting changes

## Verification
- [ ] 10+ obsolete files removed
- [ ] All stub files have basic implementation
- [ ] Duplicate files merged (verify with analyze script)
- [ ] All imports updated and tested
- [ ] Linting passes with no critical errors
- [ ] Code coverage maintained or improved

## Notes
- Re-run analyze script post-merge to confirm reductions
- Keep git history clean with logical commits
- Update docs if file structure changes significantly" \
    "impact:medium,urgency:medium,effort:medium,phase:1" \
    "Phase 1: Immediate Fixes"

echo -e "${GREEN}✓ Phase 1 issues created${NC}"
echo ""

# PHASE 2 ISSUES

echo -e "${BLUE}=== Phase 2: Core Development ===${NC}"

# Issue 4: Celery Task Implementation
create_issue \
    "Celery Task Implementation" \
    "## Overview
**Phase**: 2 - Core Development
**Impact**: High
**Urgency**: High
**Effort**: High (~25-30 hours)
**Dependencies**: Issues #1-3 (Phase 1 complete)

## Description
Implement all Celery tasks for market data sync, signal generation, backtesting, and RAG integration. Configure beat schedule for automation.

## Hour-by-Hour Breakdown

### Hours 1-4: Market Data & Basic Indicators (First 4 Tasks)
- Implement \`sync_market_data_task\`:
  - Fetch OHLCV data from Binance
  - Store in TimescaleDB hypertable
  - Add error handling and retries
- Implement \`calculate_rsi_task\`:
  - Compute RSI indicator
  - Update database with results
- Implement \`calculate_macd_task\`
- Implement \`calculate_bollinger_bands_task\`
- Test each individually: \`celery -A web.django call trading.tasks.<task_name>\`

### Hours 5-8: Signal Generation (Next 4 Tasks)
- Implement \`generate_trading_signals_task\`:
  - Combine indicators for signals
  - Apply strategy rules
- Implement \`evaluate_signal_strength_task\`:
  - Score signals (0-100)
  - Filter by threshold
- Implement \`apply_risk_management_task\`:
  - Calculate position sizes
  - Apply stop-loss/take-profit
- Implement \`send_signal_notifications_task\`:
  - Discord webhook integration
- Test signal chain end-to-end

### Hours 9-12: Backtesting (Next 4 Tasks)
- Implement \`run_backtest_task\`:
  - Execute strategy on historical data
  - Calculate metrics (Sharpe, drawdown)
- Implement \`optimize_strategy_parameters_task\`:
  - Integrate Optuna for hyperparam tuning
  - Run grid/random search
- Implement \`validate_backtest_results_task\`:
  - Statistical significance tests
  - Walk-forward validation
- Implement \`store_backtest_results_task\`:
  - Save to database
  - Generate reports
- Verify outputs and metrics

### Hours 13-16: RAG & Intelligence (Final 4 Tasks)
- Implement \`analyze_with_rag_task\`:
  - Query RAG system for context
  - Enhance signals with AI insights
- Implement \`update_strategy_from_rag_task\`:
  - Auto-adjust parameters based on RAG
  - Track changes
- Implement \`ingest_trading_data_to_rag_task\`:
  - Index signals, backtests, trades
  - Update pgvector embeddings
- Implement \`optimize_portfolio_task\`:
  - Rebalance based on RAG recommendations
  - Account for available cash
- Test RAG integration

### Hours 17-18: Beat Schedule Configuration
- Configure celery beat in src/web/django/celery.py
- Set intervals:
  - Market data sync: every 1 hour
  - Signal generation: every 4 hours
  - Backtesting: daily
  - RAG ingestion: every 6 hours
- Test with Flower (http://localhost:5555)
- Verify scheduled execution

### Hours 19-21: RAG Ingestion Hooks
- Add auto-ingestion after signal generation
- Hook backtesting results to RAG
- Index sample historical data
- Verify pgvector storage
- Test retrieval quality

### Hours 22-25: End-to-End Testing
- Run complete task chain:
  - Data sync → Signals → Backtest → RAG → Notify
- Debug dependencies and error handling
- Add retries for failed tasks (max_retries=3)
- Load test with Celery workers
- Monitor with Flower

## Verification
- [ ] All 16 tasks implemented with tests
- [ ] Beat schedule configured and running
- [ ] RAG ingestion working (check pgvector)
- [ ] End-to-end chain executes successfully
- [ ] Flower shows healthy task execution
- [ ] Error handling and retries functional
- [ ] No memory leaks or performance issues

## Notes
- Run partial tests after every 4 tasks
- Adjust GPU settings if RAG needed early
- Monitor Redis memory usage
- Check Celery logs in logs/celery/" \
    "impact:high,urgency:high,effort:high,phase:2" \
    "Phase 2: Core Development"

# Issue 5: RAG System Completion
create_issue \
    "RAG System Completion" \
    "## Overview
**Phase**: 2 - Core Development
**Impact**: High
**Urgency**: High
**Effort**: High (~14 hours)
**Dependencies**: Issue #4 (Celery tasks for integration)

## Description
Complete RAG system with document processing, embeddings, retrieval, and orchestration. Enable auto-ingestion and knowledge base management.

## Hour-by-Hour Breakdown

### Hours 1-3: Document Processor
- Implement document_processor.py:
  - Chunking logic for OHLCV data
  - Text extraction from trade records
  - Metadata handling (timestamps, symbols)
- Test with sample data:
  - 100 trades
  - 10 backtest results
  - Signal history
- Verify chunk quality and overlap

### Hours 4-5: Embeddings Setup
- Configure sentence-transformers:
  - Model selection (all-MiniLM-L6-v2 or similar)
  - GPU/CPU fallback detection
- Implement embedding generation:
  - Batch processing
  - Caching for efficiency
- Test embedding quality with similarity search

### Hours 6-8: Retrieval Service
- Build retrieval.py:
  - pgvector search implementation
  - Scoring and ranking logic
  - Query expansion
- Add filters:
  - Date range
  - Symbol
  - Signal type
- Test retrieval accuracy:
  - Precision/recall metrics
  - Latency benchmarks

### Hours 9-12: Intelligence Orchestration
- Implement intelligence.py:
  - Ollama API integration
  - Prompt engineering for trading
  - Context combination (retrieval + LLM)
- Add features:
  - Query optimization recommendations
  - Strategy parameter suggestions
  - Risk assessment
- Test with sample queries:
  - \"Best signals for BTCUSDT today\"
  - \"Optimize strategy for current market\"
  - \"Risk analysis for new position\"

### Hours 13-14: Auto-Ingestion & Scheduling
- Hook ingestion to Celery tasks:
  - After signal generation
  - After backtest completion
  - After trade execution
- Schedule re-indexing:
  - Full re-index weekly
  - Incremental updates hourly
- Test knowledge base:
  - Query historical data
  - Verify up-to-date information
  - Check vector storage size

## Verification
- [ ] Document processor handles all data types
- [ ] Embeddings generate successfully (GPU/CPU)
- [ ] Retrieval returns relevant results (<500ms)
- [ ] Ollama integration working
- [ ] Auto-ingestion hooks functional
- [ ] Knowledge base queryable via API
- [ ] pgvector contains expected vectors

## Notes
- Measure performance after Hour 8
- Integrate with Phase 2.1 Celery tasks
- Monitor GPU usage if applicable
- Refer to docs/RAG_IMPLEMENTATION_SUMMARY.md" \
    "impact:high,urgency:high,effort:high,phase:2" \
    "Phase 2: Core Development"

# Issue 6: Web UI/API Migration
create_issue \
    "Web UI/API Migration" \
    "## Overview
**Phase**: 2 - Core Development
**Impact**: Medium
**Urgency**: Medium
**Effort**: Medium (~9 hours)
**Dependencies**: Issues #2 (tests passing), #4 (tasks for data)

## Description
Complete Django web UI with Bootstrap templates and migrate remaining FastAPI routes to Django views.

## Hour-by-Hour Breakdown

### Hours 1-3: Bootstrap Templates
- Complete dashboard.html:
  - Trading signals view
  - Portfolio summary
  - Recent trades table
- Add forms in src/web/forms.py:
  - Strategy configuration
  - Backtest parameters
  - Signal filters
- Test responsiveness:
  - Desktop (1920x1080)
  - Tablet (768x1024)
  - Mobile (375x667)
- Add CSS in src/web/static/css/

### Hours 4-7: API Migration
- Audit remaining FastAPI routes in src/api/
- Migrate 5-10 routes to Django views:
  - /api/signals → src/web/views/signals.py
  - /api/backtest → src/web/views/backtest.py
  - /api/portfolio → src/web/views/portfolio.py
- Add authentication checks (django-axes)
- Test endpoints with curl/Postman:
  - GET requests
  - POST with CSRF tokens
  - Error handling

### Hours 8-9: Health Dashboard
- Implement /health/dashboard/ view:
  - Integrate analyze script outputs
  - Show service status (DB, Redis, Celery)
  - Display recent errors
  - List next steps
- Add navigation to main menu
- Browser test all features
- Verify real-time updates

## Verification
- [ ] Dashboard renders correctly on all devices
- [ ] Forms submit and validate properly
- [ ] All API routes migrated and tested
- [ ] Authentication working on new views
- [ ] Health dashboard shows accurate status
- [ ] No FastAPI dependencies remain
- [ ] CSS/JS assets loading correctly

## Notes
- Verify with local server: \`make up\`
- Test at http://localhost:8000
- Check browser console for JS errors
- Refer to docs/WEB_UI_IMPLEMENTATION.md" \
    "impact:medium,urgency:medium,effort:medium,phase:2" \
    "Phase 2: Core Development"

# Issue 7: Data Sync/Backtesting Enhancements
create_issue \
    "Data Sync/Backtesting Enhancements" \
    "## Overview
**Phase**: 2 - Core Development
**Impact**: Medium
**Urgency**: Medium
**Effort**: Medium (~7 hours)
**Dependencies**: Issue #4 (Celery tasks), #5 (RAG system)

## Description
Enhance Binance data adapter with robust error handling and integrate Optuna for hyperparameter optimization with RAG-powered suggestions.

## Hour-by-Hour Breakdown

### Hours 1-2: Binance Adapter Enhancement
- Enhance src/data/adapters/binance.py:
  - Add rate limiting (10 requests/second)
  - Implement exponential backoff
  - Add circuit breaker for API failures
- Handle edge cases:
  - Network timeouts
  - Invalid symbols
  - Data gaps
- Test API calls:
  - 100 consecutive requests
  - Failure scenarios
  - Rate limit handling

### Hours 3-5: Optuna Integration
- Integrate Optuna in src/trading/optimizer/engine.py:
  - Define parameter space (RSI periods, thresholds)
  - Setup objective function (Sharpe ratio)
  - Configure sampler (TPE or NSGA-II)
- Run sample optimization:
  - 50-100 trials
  - 3-month backtest window
- Compare results:
  - Before vs after optimization
  - Parameter convergence
- Save study results to database

### Hours 6-7: RAG-Powered Optimization
- Add RAG hooks to optimizer:
  - Query for historical parameter performance
  - Get suggestions based on market regime
  - Incorporate risk preferences
- Implement feedback loop:
  - Store optimization results in RAG
  - Learn from successful strategies
- Measure improvements:
  - Strategy performance metrics
  - Parameter stability
  - Adaptation to market changes

## Verification
- [ ] Binance adapter handles 1000+ requests without failures
- [ ] Rate limiting prevents API bans
- [ ] Optuna finds better parameters (>10% Sharpe improvement)
- [ ] RAG provides relevant optimization suggestions
- [ ] Optimization results stored and queryable
- [ ] No data sync errors in logs

## Notes
- Benchmark before/after Optuna
- Monitor API rate limits in production
- Track optimization metrics in Grafana
- Refer to examples/optimize_strategy.py" \
    "impact:medium,urgency:medium,effort:medium,phase:2" \
    "Phase 2: Core Development"

echo -e "${GREEN}✓ Phase 2 issues created${NC}"
echo ""

# PHASE 3 ISSUES

echo -e "${BLUE}=== Phase 3: Testing & QA ===${NC}"

# Issue 8: Expand Tests
create_issue \
    "Expand Test Coverage" \
    "## Overview
**Phase**: 3 - Testing & QA (Parallel with Phase 2)
**Impact**: High
**Urgency**: Medium
**Effort**: Medium (~9 hours)
**Dependencies**: Phase 2 features implemented

## Description
Expand test coverage for RAG system, Celery tasks, and performance benchmarks. Target 80%+ coverage.

## Hour-by-Hour Breakdown

### Hours 1-3: RAG Unit Tests
- Write tests in tests/unit/test_core/test_rag_system.py:
  - Mock embeddings generation
  - Mock retrieval service
  - Test document chunking
  - Cover 5-10 RAG functions
- Add integration tests:
  - End-to-end RAG query
  - pgvector storage/retrieval
- Run: \`pytest tests/unit/test_core/test_rag_system.py -v\`

### Hours 4-7: Celery Integration Tests
- Create tests/integration/test_celery/:
  - Mock Celery queues
  - Test task scheduling
  - Test task chaining
  - Test retry logic
  - Test error handling
- Cover all 16 tasks from Issue #4
- Run: \`pytest tests/integration/test_celery/ -v\`

### Hours 8-9: Performance Benchmarks
- Implement benchmarks in tests/benchmarks/:
  - Backtesting speed (10K candles)
  - Signal generation latency
  - RAG query response time
  - Database query performance
- Set baselines:
  - Backtest: <30s for 1-year data
  - Signals: <1s per symbol
  - RAG: <500ms per query
- Run: \`pytest tests/benchmarks/ -v\`

## Verification
- [ ] 80%+ code coverage achieved
- [ ] All RAG functions tested
- [ ] All Celery tasks have integration tests
- [ ] Benchmarks passing with acceptable times
- [ ] No flaky tests
- [ ] Coverage report generated (HTML)

## Notes
- Run after Phase 2 features complete
- Aim for incremental coverage improvements
- Focus on critical paths first
- Use pytest markers: -m unit, -m integration" \
    "impact:high,urgency:medium,effort:medium,phase:3" \
    "Phase 3: Testing & QA"

# Issue 9: CI/CD Setup
create_issue \
    "CI/CD Pipeline Setup" \
    "## Overview
**Phase**: 3 - Testing & QA
**Impact**: Medium
**Urgency**: Medium
**Effort**: Low (~3 hours)
**Dependencies**: Issue #8 (tests expanded)

## Description
Setup GitHub Actions for automated testing, linting, and code analysis on every push/PR.

## Hour-by-Hour Breakdown

### Hours 1-2: GitHub Action YAML
- Create .github/workflows/ci.yml:
  - Build Docker images
  - Run pytest with coverage
  - Run make lint (ruff, mypy, black)
  - Upload coverage to codecov
- Add matrix testing:
  - Python 3.12, 3.13
  - PostgreSQL 15, 16
- Configure caching:
  - pip dependencies
  - Docker layers
- Test workflow locally with act

### Hour 3: Integrate Analyze Script
- Add analyze script to workflow:
  - Auto-run on PR
  - Comment results on PR
  - Fail if critical issues found
- Setup automatic commits:
  - Format code with black
  - Update metrics.json
- Configure notifications:
  - Discord webhook on failure
  - Email on success

## Verification
- [ ] Workflow runs on push to main
- [ ] Workflow runs on all PRs
- [ ] Tests pass in CI environment
- [ ] Coverage report uploads successfully
- [ ] Analyze script comments on PRs
- [ ] No secrets exposed in logs
- [ ] Notifications working

## Notes
- Trigger on PRs for immediate feedback
- Use GitHub secrets for sensitive data
- Monitor workflow execution time (<10 min)
- Refer to .github/workflows/ examples" \
    "impact:medium,urgency:medium,effort:low,phase:3" \
    "Phase 3: Testing & QA"

echo -e "${GREEN}✓ Phase 3 issues created${NC}"
echo ""

# PHASE 4 ISSUES

echo -e "${BLUE}=== Phase 4: Documentation ===${NC}"

# Issue 10: Update Core Docs
create_issue \
    "Update Core Documentation" \
    "## Overview
**Phase**: 4 - Documentation & Knowledge Management
**Impact**: Low
**Urgency**: Low
**Effort**: Low (~4 hours)
**Dependencies**: Phases 1-3 complete

## Description
Refresh README, ARCHITECTURE, and copilot-instructions with latest changes and status.

## Hour-by-Hour Breakdown

### Hour 1: README Update
- Update README.md:
  - Mark Phase 1-3 tasks as complete
  - Update setup instructions
  - Add new features section
  - Update screenshots/examples
- Verify all links work
- Test commands in fresh environment

### Hours 2-3: Architecture Documentation
- Expand ARCHITECTURE.md:
  - Add Mermaid diagrams for RAG flow
  - Document Celery task dependencies
  - Update database schema
  - Add deployment architecture
- Create diagrams with draw.io:
  - System overview
  - Data flow
  - Integration points
- Embed in docs/

### Hour 4: Copilot Instructions
- Update .github/copilot-instructions.md:
  - Mark completed tasks
  - Add new conventions
  - Update known issues section
  - Document RAG usage patterns
- Add status indicators (✅ complete, 🔄 in progress)
- Verify accuracy of all sections

## Verification
- [ ] README accurate and up-to-date
- [ ] All links functional
- [ ] Diagrams clear and informative
- [ ] Copilot instructions reflect current state
- [ ] No outdated information
- [ ] New features documented

## Notes
- Verify links after each update
- Get feedback on diagrams
- Keep copilot-instructions concise
- Update version numbers" \
    "impact:low,urgency:low,effort:low,phase:4" \
    "Phase 4: Documentation"

# Issue 11: Create Dynamic Docs
create_issue \
    "Create Dynamic Documentation" \
    "## Overview
**Phase**: 4 - Documentation & Knowledge Management
**Impact**: Low
**Urgency**: Low
**Effort**: Low (~3 hours)
**Dependencies**: Issue #6 (Web UI complete)

## Description
Build health dashboard with live metrics and generate interactive API documentation.

## Hour-by-Hour Breakdown

### Hour 1: Health Dashboard Markdown
- Create docs/HEALTH_DASHBOARD.md:
  - Embed analyze script outputs
  - Show current metrics
  - List active issues
  - Display next steps
- Auto-generate on each run:
  - Via GitHub Actions
  - Via pre-commit hook
- Add to main menu

### Hours 2-3: API Documentation
- Install drf-spectacular:
  - Add to requirements.txt
  - Configure in settings.py
- Generate Swagger/OpenAPI docs:
  - Document all endpoints
  - Add request/response examples
  - Include authentication details
- Deploy at /api/docs/:
  - Interactive testing
  - Schema download
  - Authentication playground
- Test all documented endpoints

## Verification
- [ ] Health dashboard auto-updates
- [ ] Dashboard shows accurate metrics
- [ ] Swagger UI accessible at /api/docs/
- [ ] All endpoints documented
- [ ] Interactive testing works
- [ ] Schema validates correctly

## Notes
- Test interactive Swagger page
- Ensure authentication works in docs
- Keep dashboard updated automatically
- Monitor dashboard load time" \
    "impact:low,urgency:low,effort:low,phase:4" \
    "Phase 4: Documentation"

echo -e "${GREEN}✓ Phase 4 issues created${NC}"
echo ""

# PHASE 5 ISSUES

echo -e "${BLUE}=== Phase 5: Deployment & Monitoring ===${NC}"

# Issue 12: Local/Dev Enhancements
create_issue \
    "Local/Dev Environment Enhancements" \
    "## Overview
**Phase**: 5 - Deployment & Monitoring
**Impact**: Medium
**Urgency**: Low
**Effort**: Medium (~4 hours)
**Dependencies**: Phase 2 complete (core features working)

## Description
Fix GPU detection in start.sh and optimize Docker configuration for local development.

## Hour-by-Hour Breakdown

### Hours 1-2: GPU Detection Fix
- Fix scripts/start.sh:
  - Add AMD GPU detection (rocm-smi)
  - Add Intel GPU detection (intel_gpu_top)
  - Add fallback to CPU mode
- Test on different hardware:
  - NVIDIA GPU system
  - AMD GPU system
  - CPU-only system
- Document supported configurations

### Hours 3-4: Docker Optimizations
- Optimize docker-compose.yml:
  - Add Redis memory limits
  - Configure PostgreSQL shared buffers
  - Tune Celery worker concurrency
- Create backup script:
  - Automated database backups
  - Backup rotation (keep 7 days)
  - Test restore process
- Add health checks:
  - Database reachability
  - Redis connectivity
  - Celery worker status

## Verification
- [ ] GPU detection works on all hardware
- [ ] Fallback to CPU mode successful
- [ ] Docker optimizations applied
- [ ] Backup script creates valid backups
- [ ] Restore process tested and working
- [ ] Health checks passing
- [ ] Services restart automatically on failure

## Notes
- Test fallback modes thoroughly
- Document hardware requirements
- Schedule backups via cron
- Monitor resource usage with htop" \
    "impact:medium,urgency:low,effort:medium,phase:5" \
    "Phase 5: Deployment & Monitoring"

# Issue 13: Production Readiness
create_issue \
    "Production Readiness" \
    "## Overview
**Phase**: 5 - Deployment & Monitoring
**Impact**: High
**Urgency**: Low
**Effort**: High (~9 hours)
**Dependencies**: All Phase 1-4 tasks complete

## Description
Configure Tailscale VPN, setup Prometheus alerts, and deploy to production VPS with full security.

## Hour-by-Hour Breakdown

### Hours 1-2: Tailscale Configuration
- Install/configure Tailscale:
  - Add TAILSCALE_AUTH_KEY to .env
  - Configure DNS records
  - Setup MagicDNS
- Test connectivity:
  - Access from external network
  - Verify encryption
  - Test DNS resolution
- Document access procedures

### Hours 3-5: Prometheus Alerts
- Configure monitoring/prometheus/prometheus.yml:
  - CPU usage alerts (>80%)
  - Memory alerts (>85%)
  - Disk space alerts (<10% free)
  - Service down alerts
- Integrate Discord notifications:
  - Alertmanager config
  - Webhook setup
  - Test alert firing
- Setup alert rules:
  - Database connection failures
  - Celery task failures
  - High error rates

### Hours 6-9: VPS Deployment
- Provision VPS:
  - Ubuntu 22.04 LTS
  - Docker + docker-compose installed
  - Firewall configured (ufw)
- Deploy application:
  - Clone repository
  - Configure .env
  - Run docker-compose up -d
  - Setup SSL with Let's Encrypt
- Security hardening:
  - Disable password auth (SSH keys only)
  - Configure fail2ban
  - Setup automatic updates
- Thorough testing:
  - All services running
  - SSL certificates valid
  - Monitoring active
  - Backups working

## Verification
- [ ] Tailscale VPN working
- [ ] External access secure
- [ ] Prometheus alerts configured
- [ ] Discord notifications working
- [ ] VPS deployed successfully
- [ ] SSL certificates valid
- [ ] No exposed ports (except 80/443)
- [ ] Firewall configured correctly
- [ ] Backups automated and tested

## Notes
- No exposed database/Redis ports
- Validate security with nmap scan
- Test failover scenarios
- Document production access" \
    "impact:high,urgency:low,effort:high,phase:5" \
    "Phase 5: Deployment & Monitoring"

echo -e "${GREEN}✓ Phase 5 issues created${NC}"
echo ""

# PHASE 6 ISSUES

echo -e "${BLUE}=== Phase 6: Optimization & Maintenance ===${NC}"

# Issue 14: Performance Tuning
create_issue \
    "Performance Tuning" \
    "## Overview
**Phase**: 6 - Optimization & Maintenance (Ongoing)
**Impact**: Medium
**Urgency**: Low
**Effort**: Medium (~7 hours)
**Dependencies**: Phase 5 complete (production running)

## Description
Optimize database performance with TimescaleDB compression and query profiling.

## Hour-by-Hour Breakdown

### Hours 1-4: Database Optimization
- Configure TimescaleDB compression:
  - Enable on OHLCV hypertable
  - Set compression policy (7 days)
  - Monitor compression ratio
- Add indexes:
  - Symbol + timestamp (composite)
  - Signal type + created_at
  - Account + trade_date
- Test query performance:
  - Before/after benchmarks
  - Measure size reduction
- Expected: 50-70% size reduction

### Hours 5-7: Query Profiling
- Profile slow queries:
  - Enable pg_stat_statements
  - Identify top 10 slow queries
  - Analyze with EXPLAIN ANALYZE
- Optimize Celery operations:
  - Add connection pooling
  - Implement Redis caching
  - Batch database writes
- Load testing:
  - 1000+ concurrent tasks
  - Monitor resource usage
- Measure improvements:
  - Query latency reduction
  - Memory usage
  - Throughput increase

## Verification
- [ ] Compression enabled and working
- [ ] Database size reduced by 50%+
- [ ] Slow queries optimized (<100ms)
- [ ] Connection pooling implemented
- [ ] Redis cache hit rate >80%
- [ ] Load tests passing
- [ ] No performance regressions

## Notes
- Measure before/after metrics
- Monitor with Grafana dashboards
- Document optimization changes
- Test during low-traffic periods" \
    "impact:medium,urgency:low,effort:medium,phase:6" \
    "Phase 6: Optimization & Maintenance"

# Issue 15: Maintenance Automation
create_issue \
    "Maintenance Automation" \
    "## Overview
**Phase**: 6 - Optimization & Maintenance (Ongoing)
**Impact**: Low
**Urgency**: Low
**Effort**: Low (~3 hours)
**Dependencies**: Phase 3 complete (CI/CD working)

## Description
Enhance analyze scripts and automate weekly maintenance tasks.

## Hour-by-Hour Breakdown

### Hours 1-2: Enhance Analyze Scripts
- Update scripts/analyze_*.sh:
  - Add performance metrics collection
  - Detect code patterns/anti-patterns
  - Measure technical debt
- Output enhancements:
  - JSON format for automation
  - Trend analysis (week-over-week)
  - Action recommendations
- Integration:
  - Add to GitHub Actions
  - Weekly scheduled runs
  - Auto-comment on PRs

### Hour 3: Weekly Update Automation
- Create scripts/weekly_update.sh:
  - Check for dependency updates
  - Run security audit (pip-audit)
  - Generate health report
  - Create GitHub issue if problems found
- Schedule via cron:
  - Run every Sunday at 2 AM
  - Send report to Discord
  - Log to monitoring/logs/
- Test reliability:
  - Dry run multiple times
  - Verify notifications
  - Check error handling

## Verification
- [ ] Analyze scripts enhanced
- [ ] Performance metrics collected
- [ ] Weekly update script created
- [ ] Cron job scheduled
- [ ] Notifications working
- [ ] Reports generated correctly
- [ ] No false positives

## Notes
- Test automation reliability
- Monitor resource usage during runs
- Keep reports concise and actionable
- Archive old reports after 30 days" \
    "impact:low,urgency:low,effort:low,phase:6" \
    "Phase 6: Optimization & Maintenance"

# Issue 16: Code Quality Improvements
create_issue \
    "Code Quality Improvements" \
    "## Overview
**Phase**: 6 - Optimization & Maintenance (Ongoing)
**Impact**: Medium
**Urgency**: Low
**Effort**: Medium (~5 hours)
**Dependencies**: Phase 2 complete (core features working)

## Description
Fix remaining code quality issues and enhance monitoring with custom metrics.

## Hour-by-Hour Breakdown

### Hours 1-3: Fix Remaining Issues
- Address legacy imports:
  - Final migration from old patterns
  - Remove all config module references
  - Clean up shared_python imports
- Resolve duplications:
  - Merge similar functions
  - Extract common logic
  - Create utility modules
- Improve error handling:
  - Use specific exceptions
  - Add proper logging
  - Implement graceful degradation
- Run full linting suite

### Hours 4-5: Monitoring Enhancements
- Add custom Prometheus metrics:
  - Trading signal accuracy
  - Backtest performance metrics
  - RAG query latency
  - Task execution counts
- Create Grafana dashboards:
  - Trading performance overview
  - System health summary
  - Resource utilization
- Setup custom alerts:
  - Trading anomalies
  - RAG degradation
  - Task queue buildup

## Verification
- [ ] No legacy imports remain
- [ ] Code duplication <5%
- [ ] Error handling comprehensive
- [ ] Custom metrics collecting
- [ ] Grafana dashboards created
- [ ] Alerts triggering correctly
- [ ] All linting passes

## Notes
- Update docs post-fixes
- Test monitoring in staging
- Get feedback on dashboards
- Document custom metrics" \
    "impact:medium,urgency:low,effort:medium,phase:6" \
    "Phase 6: Optimization & Maintenance"

echo -e "${GREEN}✓ Phase 6 issues created${NC}"
echo ""

# PHASE 7 ISSUES

echo -e "${BLUE}=== Phase 7: Future Features ===${NC}"

# Issue 17: Real-time Features
create_issue \
    "Real-time Features (WebSocket)" \
    "## Overview
**Phase**: 7 - Future Features (Weeks 19+)
**Impact**: High
**Urgency**: Low
**Effort**: High (~10 hours)
**Dependencies**: Phase 5 complete (production deployed)

## Description
Implement WebSocket feeds for real-time trading updates, portfolio tracking, and live charts.

## Hour-by-Hour Breakdown

### Hours 1-6: WebSocket Infrastructure
- Setup Django Channels:
  - Install channels + redis backend
  - Configure ASGI application
  - Create WebSocket consumers
- Implement feeds:
  - Live price updates (Binance)
  - Signal notifications (real-time)
  - Trade execution alerts
  - Portfolio value updates
- Add authentication:
  - Token-based WebSocket auth
  - Rate limiting per connection
- Test performance:
  - 100+ concurrent connections
  - Message latency <50ms
  - No dropped messages

### Hours 7-10: Live Updates & Charts
- Build real-time dashboard:
  - Live candlestick charts (TradingView)
  - Portfolio value graph
  - Recent trades feed
  - Active signals list
- Add notifications:
  - Browser notifications
  - Discord webhooks
  - Email alerts (optional)
- Implement tracking:
  - Position monitoring
  - P&L updates (real-time)
  - Risk metrics
- Reliability testing:
  - Reconnection logic
  - State synchronization
  - Error recovery

## Verification
- [ ] WebSocket connections stable
- [ ] Real-time updates <1s delay
- [ ] Charts render smoothly
- [ ] Notifications delivering
- [ ] 100+ concurrent users supported
- [ ] No memory leaks
- [ ] Graceful reconnection working

## Notes
- Focus on reliability over features
- Monitor WebSocket resource usage
- Test on mobile devices
- Implement backoff for reconnects" \
    "impact:high,urgency:low,effort:high,phase:7" \
    "Phase 7: Future Features"

# Issue 18: Exchange Integration
create_issue \
    "Additional Exchange Integration" \
    "## Overview
**Phase**: 7 - Future Features (Weeks 19+)
**Impact**: High
**Urgency**: Low
**Effort**: High (~8 hours)
**Dependencies**: Phase 2 complete (Binance working)

## Description
Integrate Coinbase and Kraken exchanges with unified adapter interface.

## Hour-by-Hour Breakdown

### Hours 1-4: Coinbase Integration
- Create src/data/adapters/coinbase.py:
  - Implement base adapter interface
  - Add authentication (API keys)
  - Fetch OHLCV data
  - Get account info
- Add features:
  - Order placement
  - Position tracking
  - Fee calculation
- Testing:
  - API connectivity
  - Data consistency
  - Error handling
  - Rate limiting

### Hours 5-8: Kraken Integration
- Create src/data/adapters/kraken.py:
  - Implement base adapter interface
  - Add authentication
  - Fetch market data
  - Handle Kraken-specific quirks
- Unified interface:
  - Abstract common operations
  - Normalize data formats
  - Handle exchange differences
- Thorough testing:
  - All CRUD operations
  - Error scenarios
  - Multi-exchange strategies
  - Data synchronization

## Verification
- [ ] Coinbase adapter fully functional
- [ ] Kraken adapter fully functional
- [ ] Unified interface working
- [ ] Data formats normalized
- [ ] Multi-exchange strategies possible
- [ ] All tests passing
- [ ] Compliance requirements met

## Notes
- Check compliance/legal requirements
- Test with small amounts first
- Document API rate limits
- Monitor for API changes" \
    "impact:high,urgency:low,effort:high,phase:7" \
    "Phase 7: Future Features"

# Issue 19: Advanced Analytics & UX
create_issue \
    "Advanced Analytics & UX Improvements" \
    "## Overview
**Phase**: 7 - Future Features (Weeks 19+)
**Impact**: Medium
**Urgency**: Low
**Effort**: Medium (~10 hours)
**Dependencies**: Phase 2-6 complete

## Description
Implement portfolio optimization, risk management, mobile optimization, and API enhancements.

## Hour-by-Hour Breakdown

### Hours 1-3: Portfolio Analytics
- Implement portfolio metrics:
  - Sharpe ratio calculation
  - Maximum drawdown
  - Win rate / profit factor
  - Risk-adjusted returns
- Add optimization:
  - Modern Portfolio Theory (MPT)
  - Mean-variance optimization
  - Rebalancing recommendations
  - Risk parity allocation
- Create dashboards:
  - Performance attribution
  - Correlation matrix
  - Risk decomposition

### Hours 4-6: Risk Management
- Build risk calculations:
  - Value at Risk (VaR)
  - Expected Shortfall (CVaR)
  - Position sizing (Kelly Criterion)
  - Correlation analysis
- Add alerts:
  - Drawdown thresholds
  - Concentration limits
  - Volatility spikes
  - Portfolio imbalance
- Integration with RAG:
  - Risk-adjusted recommendations
  - Market regime detection

### Hours 7-8: Mobile Optimization
- Optimize for mobile:
  - Responsive design (Bootstrap)
  - Touch-friendly charts
  - Simplified navigation
  - Reduced data usage
- Test on devices:
  - iOS Safari
  - Android Chrome
  - Various screen sizes
- Progressive Web App (PWA):
  - Offline support
  - Add to homescreen
  - Push notifications

### Hours 9-10: API Enhancements
- Enhance API:
  - Add pagination
  - Improve error messages
  - Add rate limiting headers
  - Versioning (v1, v2)
- Better documentation:
  - Code examples
  - SDKs (Python, JS)
  - Postman collection
  - Interactive tutorials
- Performance:
  - Response caching
  - Compression (gzip)
  - Query optimization

## Verification
- [ ] Portfolio metrics accurate
- [ ] Risk calculations validated
- [ ] Mobile experience smooth
- [ ] API documentation complete
- [ ] All features tested on mobile
- [ ] Performance benchmarks met
- [ ] User feedback positive

## Notes
- Test on real devices
- Validate financial calculations
- Get user feedback early
- Monitor API usage patterns" \
    "impact:medium,urgency:low,effort:medium,phase:7" \
    "Phase 7: Future Features"

echo -e "${GREEN}✓ Phase 7 issues created${NC}"
echo ""

# Summary
echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}✅ GitHub Issues Import Complete!${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo "Summary:"
echo "  • Phase 1: 3 issues (Immediate Fixes)"
echo "  • Phase 2: 4 issues (Core Development)"
echo "  • Phase 3: 2 issues (Testing & QA)"
echo "  • Phase 4: 2 issues (Documentation)"
echo "  • Phase 5: 2 issues (Deployment & Monitoring)"
echo "  • Phase 6: 3 issues (Optimization & Maintenance)"
echo "  • Phase 7: 3 issues (Future Features)"
echo ""
echo "Total: 19 issues created"
echo ""
echo "Next steps:"
echo "  1. View issues: gh issue list"
echo "  2. Assign to project: gh issue edit <number> --add-project 'FKS Development'"
echo "  3. Start work: gh issue develop <number> --checkout"
echo ""
echo -e "${BLUE}Happy coding! 🚀${NC}"
