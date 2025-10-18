#!/usr/bin/env python3
"""
Import detailed project plan as GitHub Issues.
This creates issues from your comprehensive 7-phase forward plan.
"""

import subprocess
import sys
from typing import List, Dict


class IssueImporter:
    """Import structured project plan into GitHub Issues."""
    
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        
    def create_issue(self, issue: Dict) -> bool:
        """Create a single GitHub issue."""
        cmd = [
            "gh", "issue", "create",
            "--title", issue["title"],
            "--body", issue["body"],
            "--repo", f"{self.owner}/{self.repo}",
        ]
        
        # Add labels
        for label in issue.get("labels", []):
            cmd.extend(["--label", label])
        
        # Add milestone if specified
        if "milestone" in issue:
            cmd.extend(["--milestone", issue["milestone"]])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✅ Created: {issue['title']}")
            return True
        else:
            print(f"  ❌ Failed: {issue['title']}")
            print(f"     {result.stderr}")
            return False
    
    def get_issues(self) -> List[Dict]:
        """Generate all issues from the forward plan."""
        return [
            # =====================================================================
            # PHASE 1: IMMEDIATE FIXES (2-4 Weeks)
            # =====================================================================
            {
                "title": "[PHASE 1] Immediate Fixes - Security, Tests, Cleanup",
                "body": """## 🎯 Phase Overview
**Duration**: 2-4 weeks  
**Priority**: 🔴 CRITICAL  
**Goal**: Stabilize core (security, tests, code) - unblocks everything

## 📋 Sub-Tasks
- [ ] #1.1: Security Hardening
- [ ] #1.2: Fix Import/Test Failures
- [ ] #1.3: Code Cleanup

## ✅ Success Criteria
- All 34 tests passing (100%)
- No security vulnerabilities in .env
- All legacy imports migrated
- Code lint-free (black/ruff)
- CI/CD pipeline operational

## 📊 Metrics to Track
- Test pass rate: 41% → 100%
- Security audit: Clean report
- Empty files: 25+ → <5
- Legacy imports: 20+ files → 0

## 🔗 Dependencies
None - This is the foundation for everything else.

## 📚 References
- PROJECT_STATUS.md section "Fix Plan: Import Errors"
- PROJECT_STATUS.md section "Fix Plan: Security"
- .github/copilot-instructions.md (test failures section)
""",
                "labels": ["🔴 critical", "effort:high", "phase:1-immediate"],
                "milestone": "Phase 1: Foundation"
            },
            
            # Phase 1.1: Security Hardening
            {
                "title": "[P1.1] Security Hardening - Production-Ready Secrets",
                "body": """## 🔒 Security Issue
`.env` contains placeholder passwords and insecure configuration.

## 🎯 Sub-Tasks
- [ ] **1.1.1**: Generate strong passwords (use `openssl rand -base64 32`) - 1 hr
- [ ] **1.1.2**: Add .env to .gitignore, create .env.example - 30 min
- [ ] **1.1.3**: Configure django-axes/ratelimit in settings.py - 2 hrs
- [ ] **1.1.4**: Enable DB SSL in docker-compose.yml - 1 hr
- [ ] **1.1.5**: Run `pip-audit`, update vulnerable libs - 2 hrs

## 🚨 Current Risks
- POSTGRES_PASSWORD: `CHANGE_THIS_SECURE_PASSWORD_123!`
- PGADMIN_PASSWORD: `CHANGE_THIS_ADMIN_PASSWORD_456!`
- REDIS_PASSWORD: Empty
- Exposed ports (5432, 6379) without restrictions
- API keys in plain text

## ✅ Success Criteria
- [ ] All passwords generated and secure
- [ ] .env not in git history
- [ ] Rate limiting active on API endpoints
- [ ] pip-audit returns no vulnerabilities
- [ ] Docker services use authentication

## 📊 Effort
**Total**: ~6.5 hours  
**Priority**: HIGH - Blocks deployment

## 🔗 Dependencies
None - Can start immediately

## 📚 References
- PROJECT_STATUS.md "Fix Plan: Security"
- docs/SECURITY_SETUP.md
""",
                "labels": ["🔴 critical", "🔒 security", "effort:medium", "phase:1-immediate"]
            },
            
            # Phase 1.2: Fix Import/Test Failures
            {
                "title": "[P1.2] Fix Import Errors - Unblock 20 Failing Tests",
                "body": """## 🐛 Problem
20 tests failing due to legacy microservices imports (`config`, `shared_python`).

## 🎯 Sub-Tasks
- [ ] **1.2.1**: Migrate legacy imports (config.py → framework/config/constants.py) - 4 hrs
  - Files: `src/core/database/models.py`, `src/trading/backtest/engine.py`, `src/trading/signals/generator.py`
- [ ] **1.2.2**: Remove shared_python refs in data/adapters/base.py - 2 hrs
- [ ] **1.2.3**: Run `pytest --cov`, fix failing tests, aim 50% coverage - 3 hrs
- [ ] **1.2.4**: Add GitHub Action for automated testing - 2 hrs

## 📝 Files to Modify
```python
# Create: src/framework/config/constants.py
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
MAINS = ['BTC', 'ETH']
ALTS = ['BNB', 'ADA', 'SOL']
FEE_RATE = 0.001
RISK_PER_TRADE = 0.02
```

## ✅ Success Criteria
- [ ] All 34 tests passing (pytest shows 34/34)
- [ ] No legacy imports in codebase
- [ ] GitHub Actions runs tests on every push
- [ ] Coverage report generated (aim 50%+)

## 📊 Effort
**Total**: ~11 hours  
**Priority**: CRITICAL - Blocks testing and deployment

## 🔗 Dependencies
- Requires #1.1 (secure env for tests)

## 📚 References
- .github/copilot-instructions.md (Known Test Failures section)
- PROJECT_STATUS.md "Fix Plan: Import Errors"
""",
                "labels": ["🔴 critical", "🐛 bug", "🧪 tests", "effort:high", "phase:1-immediate"]
            },
            
            # Phase 1.3: Code Cleanup
            {
                "title": "[P1.3] Code Cleanup - Remove Empty Files and Duplicates",
                "body": """## 🧹 Technical Debt
25+ empty/small files and 6+ legacy duplicates from migration.

## 🎯 Sub-Tasks
- [ ] **1.3.1**: Review 25+ empty files, flesh out or delete - 2 hrs
  - Files: api/admin.py, api/models.py, trading/execution/__init__.py
- [ ] **1.3.2**: Merge legacy duplicates - 1 hr
  - trading/backtest/engine.py + legacy_engine.py
  - trading/signals/generator.py + legacy_generator.py
- [ ] **1.3.3**: Run black/isort/ruff, fix all lint issues - 2 hrs

## 📋 Files to Review
- Empty: 25+ identified by analyze_project.py
- Duplicates: 6+ legacy_*.py files
- Lint issues: Run `ruff check src/` for full list

## ✅ Success Criteria
- [ ] <5 empty files remain (only necessary __init__.py)
- [ ] No legacy_*.py files
- [ ] `ruff check src/` passes with 0 errors
- [ ] Code formatted with black

## 📊 Effort
**Total**: ~5 hours  
**Priority**: MEDIUM - Reduces confusion

## 🔗 Dependencies
- Requires #1.2 (tests passing to verify no breakage)

## 📚 References
- analyze_project.py output (empty_files list)
- ruff.toml configuration
""",
                "labels": ["🧹 tech-debt", "🟢 medium", "effort:low", "phase:1-immediate"]
            },
            
            # =====================================================================
            # PHASE 2: CORE DEVELOPMENT (4-8 Weeks)
            # =====================================================================
            {
                "title": "[PHASE 2] Core Development - Migration + Features",
                "body": """## 🎯 Phase Overview
**Duration**: 4-8 weeks  
**Priority**: 🟡 HIGH  
**Goal**: Finish monolith migration, implement stubs, build RAG intelligence

## 📋 Sub-Tasks
- [ ] #2.1: Celery Task Implementation (16 tasks)
- [ ] #2.2: RAG System Completion
- [ ] #2.3: Web UI and API Polish
- [ ] #2.4: Data Sync and Backtesting

## ✅ Success Criteria
- All Celery tasks implemented and running
- RAG system generates trading recommendations
- Web UI fully functional
- Backtesting optimized with Optuna

## 📊 Metrics to Track
- Celery tasks: 0/16 → 16/16 implemented
- RAG queries: Functional with local LLM
- Web pages: All templates complete
- Backtest performance: Benchmarked

## 🔗 Dependencies
- Phase 1 complete (tests passing, secure)

## 📚 References
- src/trading/tasks.py (task stubs)
- src/rag/ directory
- src/web/templates/
""",
                "labels": ["🟡 high", "✨ feature", "effort:high", "phase:2-core"],
                "milestone": "Phase 2: Core Features"
            },
            
            # Phase 2.1: Celery Tasks
            {
                "title": "[P2.1] Implement All 16 Celery Tasks - Trading Automation",
                "body": """## ✨ Feature Implementation
Complete all 16 stub Celery tasks in `src/trading/tasks.py`.

## 🎯 Sub-Tasks (Priority Order)
1. **sync_market_data_task** - Fetch OHLCV from Binance (4 hrs) [FOUNDATION]
2. **generate_signals_task** - RSI, MACD, Bollinger Bands (4 hrs)
3. **run_backtest_task** - Execute strategy backtests (4 hrs)
4. **optimize_portfolio_task** - RAG-powered optimization (4 hrs)
5. **update_positions_task** - Sync positions from exchange (3 hrs)
6. **calculate_metrics_task** - Performance metrics (3 hrs)
7. **send_notifications_task** - Discord alerts (2 hrs)
8. **rebalance_portfolio_task** - Auto-rebalancing (4 hrs)
9. **analyze_risk_task** - Risk assessment (3 hrs)
10. **fetch_news_task** - Market news ingestion (3 hrs)
11. **update_indicators_task** - Technical indicators (3 hrs)
12. **check_stop_loss_task** - Stop loss monitoring (2 hrs)
13. **archive_old_data_task** - Data cleanup (2 hrs)
14. **generate_report_task** - Daily reports (3 hrs)
15. **sync_account_balance_task** - Balance updates (2 hrs)
16. **validate_strategies_task** - Strategy validation (3 hrs)

## ✅ Implementation Template
```python
@shared_task(bind=True, max_retries=3)
def task_name(self, param1, param2):
    \"\"\"Brief description.\"\"\"
    try:
        # 1. Validate inputs
        # 2. Perform logic
        # 3. Store results
        # 4. Return summary
        return {"status": "success", "data": {}}
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise self.retry(exc=e, countdown=60)
```

## ✅ Success Criteria
- [ ] All 16 tasks implemented with error handling
- [ ] Unit tests for each task
- [ ] Integration tests with Redis/Celery
- [ ] Beat schedule enabled in celery.py
- [ ] Flower dashboard shows active tasks

## 📊 Effort
**Total**: ~49 hours (phased implementation over 2-3 weeks)  
**Priority**: HIGH - Enables automated trading

## 🔗 Dependencies
- Phase 1.2 complete (tests passing)
- Redis running
- Binance API configured

## 📚 References
- src/trading/tasks.py
- src/web/django/celery.py
- Celery best practices: https://docs.celeryq.dev/
""",
                "labels": ["🟡 high", "✨ feature", "effort:high", "phase:2-core"]
            },
            
            # Phase 2.2: RAG System
            {
                "title": "[P2.2] Complete RAG System - AI-Powered Trading Intelligence",
                "body": """## ✨ Feature Implementation
Build complete RAG system for intelligent trading recommendations.

## 🎯 Sub-Tasks
- [ ] **2.2.1**: Implement document_processor.py - Chunk trading data (3 hrs)
- [ ] **2.2.2**: Setup embeddings with GPU fallback (2 hrs)
- [ ] **2.2.3**: Build retrieval service with pgvector (3 hrs)
- [ ] **2.2.4**: Orchestrate intelligence with Ollama LLM (4 hrs)
- [ ] **2.2.5**: Auto-ingest pipeline via Celery (2 hrs)

## 🤖 RAG Architecture
```
Trading Data → Document Processor → pgvector (embeddings)
                                          ↓
User Query → Retrieval Service → Context + LLM → Trading Insights
```

## 💡 Example Query
```python
from rag.services import IntelligenceOrchestrator

orchestrator = IntelligenceOrchestrator()
recommendation = orchestrator.get_trading_recommendation(
    symbol="BTCUSDT",
    account_balance=10000.00,
    context="current market conditions"
)
# Returns: Optimal position size, entry/exit points, risk assessment
```

## ✅ Success Criteria
- [ ] Documents automatically ingested from trades
- [ ] Semantic search working via pgvector
- [ ] Local LLM (Ollama) generates recommendations
- [ ] GPU acceleration functional
- [ ] Integration tests with mock data

## 📊 Effort
**Total**: ~14 hours  
**Priority**: HIGH - Core value proposition

## 🔗 Dependencies
- Phase 2.1 (Celery tasks for data ingestion)
- GPU stack running (docker-compose.gpu.yml)
- pgvector extension enabled

## 📚 References
- src/rag/ directory
- docker-compose.gpu.yml
- .github/copilot-instructions.md (RAG System section)
""",
                "labels": ["🟡 high", "✨ feature", "effort:high", "phase:2-core"]
            },
            
            # Phase 2.3: Web UI
            {
                "title": "[P2.3] Web UI and API Polish - User Interface",
                "body": """## ✨ Feature Implementation
Complete web interface with Bootstrap 5 templates and Django views.

## 🎯 Sub-Tasks
- [ ] **2.3.1**: Complete templates with Bootstrap forms (3 hrs)
  - Trading dashboard, signal viewer, backtest results
- [ ] **2.3.2**: Migrate FastAPI routes to Django views (4 hrs)
  - api/routes → web/views.py
- [ ] **2.3.3**: Implement health dashboard (2 hrs)
  - Show metrics, GPU status, service health

## 🎨 UI Components
- **Dashboard**: Portfolio overview, P&L charts
- **Signals**: Real-time trading signals table
- **Backtests**: Results visualization with Plotly
- **Settings**: Strategy configuration forms
- **Health**: System status indicators

## ✅ Success Criteria
- [ ] All templates render correctly
- [ ] Forms submit and validate
- [ ] API endpoints migrated to Django
- [ ] Health dashboard shows live metrics
- [ ] Responsive design (mobile-friendly)

## 📊 Effort
**Total**: ~9 hours  
**Priority**: MEDIUM - User-facing

## 🔗 Dependencies
- Phase 2.1 (Celery tasks provide data)

## 📚 References
- src/web/templates/
- src/web/static/css/
- src/web/views/
- Bootstrap 5 docs: https://getbootstrap.com/
""",
                "labels": ["🟢 medium", "✨ feature", "effort:medium", "phase:2-core"]
            },
            
            # Phase 2.4: Data Sync & Backtesting
            {
                "title": "[P2.4] Data Sync and Backtesting - Optimize Trading",
                "body": """## ✨ Feature Implementation
Enhance data synchronization and optimize backtesting engine.

## 🎯 Sub-Tasks
- [ ] **2.4.1**: Enhance Binance provider with rate limiting (2 hrs)
- [ ] **2.4.2**: Optimize backtest engine with Optuna (3 hrs)
- [ ] **2.4.3**: Add RAG to optimizer for param suggestions (2 hrs)

## 🔧 Enhancements
- **Rate Limiting**: Use circuit breaker for API calls
- **Optimization**: Hyperparameter tuning with Optuna
- **RAG Integration**: Query LLM for strategy parameters

## ✅ Success Criteria
- [ ] Data sync handles Binance rate limits gracefully
- [ ] Backtesting 3x faster with optimizations
- [ ] Optuna finds optimal strategy parameters
- [ ] RAG suggests parameters based on market conditions

## 📊 Effort
**Total**: ~7 hours  
**Priority**: HIGH - Core trading functionality

## 🔗 Dependencies
- Phase 2.2 (RAG system)

## 📚 References
- src/data/providers/binance.py
- src/trading/backtest/engine.py
- src/trading/optimizer/engine.py
- Optuna docs: https://optuna.org/
""",
                "labels": ["🟡 high", "✨ feature", "effort:medium", "phase:2-core"]
            },
            
            # =====================================================================
            # PHASE 3: TESTING & QA (Ongoing)
            # =====================================================================
            {
                "title": "[PHASE 3] Testing & QA - Achieve 80% Coverage",
                "body": """## 🎯 Phase Overview
**Duration**: 2-4 weeks (parallel with Phase 2)  
**Priority**: 🟡 HIGH  
**Goal**: Comprehensive test coverage and CI/CD automation

## 📋 Sub-Tasks
- [ ] #3.1: Expand Test Suite
- [ ] #3.2: CI/CD Setup

## ✅ Success Criteria
- 80%+ code coverage
- All tests passing
- CI runs on every push/PR
- Performance benchmarks established

## 📊 Metrics to Track
- Coverage: 50% → 80%+
- Test count: 34 → 100+
- CI/CD: Operational
- Benchmark: Baseline established

## 🔗 Dependencies
- Phases 1 & 2 (features to test)

## 📚 References
- pytest.ini configuration
- tests/ directory
- .github/workflows/
""",
                "labels": ["🟡 high", "🧪 tests", "effort:medium", "phase:3-testing"],
                "milestone": "Phase 3: Quality"
            },
            
            # Phase 3.1: Expand Tests
            {
                "title": "[P3.1] Expand Test Suite - Comprehensive Coverage",
                "body": """## 🧪 Testing Enhancement
Write comprehensive tests for all modules.

## 🎯 Sub-Tasks
- [ ] **3.1.1**: Unit tests for RAG system with mocks (3 hrs)
- [ ] **3.1.2**: Integration tests for Celery tasks (4 hrs)
- [ ] **3.1.3**: Performance tests with pytest-benchmark (2 hrs)

## 📝 Test Categories
- **Unit Tests**: Individual functions/classes (isolated)
- **Integration Tests**: Module interactions (Redis, DB)
- **Performance Tests**: Benchmark critical paths

## ✅ Success Criteria
- [ ] 80%+ coverage (run `pytest --cov`)
- [ ] All new features have tests
- [ ] Performance benchmarks documented
- [ ] Tests run in <5 minutes

## 📊 Effort
**Total**: ~9 hours  
**Priority**: HIGH - Quality assurance

## 🔗 Dependencies
- Phases 2.1-2.4 (features complete)

## 📚 References
- tests/unit/, tests/integration/
- pytest.ini
- pytest-benchmark docs
""",
                "labels": ["🟡 high", "🧪 tests", "effort:medium", "phase:3-testing"]
            },
            
            # Phase 3.2: CI/CD Setup
            {
                "title": "[P3.2] CI/CD Pipeline - Automated Quality Checks",
                "body": """## ⚙️ Automation Setup
Complete CI/CD pipeline with GitHub Actions.

## 🎯 Sub-Tasks
- [ ] **3.2.1**: GitHub Action for build, test, lint (2 hrs)
- [ ] **3.2.2**: Integrate analyze_project.py auto-commit (1 hr)

## 🔄 Pipeline Stages
1. **Build**: Docker image build
2. **Test**: pytest with coverage
3. **Lint**: ruff, black, mypy
4. **Security**: pip-audit
5. **Deploy**: (Future) Auto-deploy on main

## ✅ Success Criteria
- [ ] Actions run on every push/PR
- [ ] Test failures block merge
- [ ] Coverage reports posted to PR
- [ ] analyze_project.py runs weekly

## 📊 Effort
**Total**: ~3 hours  
**Priority**: MEDIUM - Automation

## 🔗 Dependencies
- Phase 1.2 (tests passing)

## 📚 References
- .github/workflows/project-health-check.yml
- .github/scripts/update_status.py
""",
                "labels": ["🟢 medium", "⚙️ automation", "effort:low", "phase:3-testing"]
            },
            
            # =====================================================================
            # PHASE 4: DOCUMENTATION (2 Weeks)
            # =====================================================================
            {
                "title": "[PHASE 4] Documentation - Consolidate & Update",
                "body": """## 🎯 Phase Overview
**Duration**: 2 weeks  
**Priority**: 🟢 MEDIUM  
**Goal**: Consolidate 111 docs → 15-20, update core docs

## 📋 Sub-Tasks
- [ ] #4.1: Update Core Documentation
- [ ] #4.2: Create Dynamic Documentation

## ✅ Success Criteria
- Core docs up-to-date and accurate
- Documentation consolidated (per CLEANUP_PLAN.md)
- API docs auto-generated
- Project health dashboard operational

## 🔗 Dependencies
- Phase 2 complete (features documented)

## 📚 References
- docs/CLEANUP_PLAN.md
- README.md, ARCHITECTURE.md
""",
                "labels": ["🟢 medium", "📚 documentation", "effort:low", "phase:4-docs"],
                "milestone": "Phase 4: Documentation"
            },
            
            # =====================================================================
            # PHASE 5: DEPLOYMENT (4-6 Weeks)
            # =====================================================================
            {
                "title": "[PHASE 5] Deployment & Monitoring - Production Ready",
                "body": """## 🎯 Phase Overview
**Duration**: 4-6 weeks  
**Priority**: 🟢 MEDIUM  
**Goal**: Prepare for production deployment

## 📋 Sub-Tasks
- [ ] #5.1: Local/Dev Enhancements
- [ ] #5.2: Production Readiness

## ✅ Success Criteria
- Local development optimized
- Production deployment plan complete
- Monitoring and alerts configured
- Backup and recovery tested

## 🔗 Dependencies
- Phase 3 complete (tests passing)

## 📚 References
- docker-compose.yml
- monitoring/prometheus/
- scripts/
""",
                "labels": ["🟢 medium", "🚀 deployment", "effort:high", "phase:5-deploy"],
                "milestone": "Phase 5: Production"
            },
            
            # =====================================================================
            # PHASE 6: OPTIMIZATION (Ongoing)
            # =====================================================================
            {
                "title": "[PHASE 6] Optimization & Maintenance - Performance",
                "body": """## 🎯 Phase Overview
**Duration**: Ongoing  
**Priority**: ⚪ LOW  
**Goal**: Optimize performance and maintain codebase

## 📋 Sub-Tasks
- [ ] #6.1: Performance Tuning
- [ ] #6.2: Analyzer Script Enhancements

## ✅ Success Criteria
- Query performance optimized
- Celery tasks profiled and optimized
- Analyzer script detects patterns
- Auto-prioritization functional

## 🔗 Dependencies
- Phase 5 complete (prod deployed)

## 📚 References
- scripts/analyze_project.py
- Monitoring dashboards
""",
                "labels": ["⚪ low", "⚡ performance", "effort:medium", "phase:6-optimize"],
                "milestone": "Phase 6: Optimization"
            },
            
            # =====================================================================
            # PHASE 7: FUTURE FEATURES (6+ Weeks)
            # =====================================================================
            {
                "title": "[PHASE 7] Future Features - Post-MVP Growth",
                "body": """## 🎯 Phase Overview
**Duration**: 6+ weeks  
**Priority**: ⚪ LOW  
**Goal**: Advanced features and integrations

## 📋 Sub-Tasks
- [ ] #7.1: Advanced Trading Features
- [ ] #7.2: Additional Integrations

## ✨ Future Features
- WebSocket real-time prices
- Interactive portfolio dashboard (Plotly)
- NinjaTrader integration
- Additional exchanges (Oanda, etc.)
- Advanced ML models

## ✅ Success Criteria
- User feedback incorporated
- Advanced features validated
- New integrations tested

## 🔗 Dependencies
- Phase 5 complete (prod operational)
- User feedback collected

## 📚 References
- README.md (Next Steps section)
- User feedback from production
""",
                "labels": ["⚪ low", "✨ feature", "effort:high", "phase:7-future"],
                "milestone": "Phase 7: Growth"
            },
        ]
    
    def run(self, dry_run: bool = False):
        """Import all issues."""
        issues = self.get_issues()
        
        print(f"\n🎯 Importing {len(issues)} issues to {self.owner}/{self.repo}")
        print(f"{'🔍 DRY RUN MODE - No issues will be created' if dry_run else '🚀 CREATING ISSUES'}\n")
        
        if dry_run:
            for i, issue in enumerate(issues, 1):
                print(f"{i}. {issue['title']}")
                print(f"   Labels: {', '.join(issue.get('labels', []))}")
                print(f"   Milestone: {issue.get('milestone', 'None')}")
                print()
            print(f"\nTotal: {len(issues)} issues ready to create")
            print("\nRun without --dry-run to create issues:")
            print(f"  python scripts/import_project_plan.py")
            return
        
        # Create issues
        created = 0
        failed = 0
        
        for issue in issues:
            if self.create_issue(issue):
                created += 1
            else:
                failed += 1
        
        print(f"\n✅ Summary:")
        print(f"   Created: {created}")
        print(f"   Failed: {failed}")
        print(f"\nView issues: https://github.com/{self.owner}/{self.repo}/issues")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import detailed project plan into GitHub Issues"
    )
    parser.add_argument("--owner", default="nuniesmith", help="GitHub owner")
    parser.add_argument("--repo", default="fks", help="Repository name")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    args = parser.parse_args()
    
    # Check gh CLI
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True)
        if result.returncode != 0:
            print("❌ GitHub CLI not authenticated. Run: gh auth login")
            sys.exit(1)
    except FileNotFoundError:
        print("❌ GitHub CLI (gh) not found. Install from: https://cli.github.com/")
        sys.exit(1)
    
    importer = IssueImporter(args.owner, args.repo)
    importer.run(dry_run=args.dry_run)
