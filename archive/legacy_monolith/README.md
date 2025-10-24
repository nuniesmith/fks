# Legacy Monolith Code Archive

**Date Archived:** October 24, 2025  
**Reason:** Multi-repo microservices architecture migration

## What's Archived

This directory contains code from the original monolithic FKS application that has been superseded by the new microservices architecture.

### Archived Components

1. **app.py** - Legacy FastAPI monolith application
   - **Replaced by:** Individual services (fks_api, fks_app, fks_data, fks_execution)
   - **Status:** No longer used

2. **engine/** - Legacy trading engine
   - **Replaced by:** fks_app (business logic) + fks_execution (order execution)
   - **Status:** Logic migrated to appropriate services

3. **infrastructure/** - Legacy infrastructure code
   - **Replaced by:** Service-specific infrastructure in each microservice
   - **Status:** Distributed across services

4. **services/** - Legacy service layer
   - **Replaced by:** Individual microservices with clean separation
   - **Status:** No longer needed with microservices

5. **api/** - Legacy API routes (from main repo)
   - **Replaced by:** fks_api (API Gateway) + fks_app (business logic)
   - **Status:** Moved to appropriate services

6. **trading/** - Legacy trading logic (from main repo)
   - **Replaced by:** fks_app (core trading application)
   - **Status:** Migrated to fks_app service

7. **data/** - Legacy data handling (from main repo)
   - **Replaced by:** fks_data (dedicated data ingestion service)
   - **Status:** Migrated to fks_data service

## New Architecture

The FKS platform now uses a microservices architecture with clear separation of concerns:

### Active Services

1. **FKS Main** (`nuniesmith/fks`) - Orchestrator & Monitor
   - Service registry and health checks
   - Monitoring dashboard
   - Centralized configuration
   - **Does NOT contain business logic**

2. **fks_api** (`repo/api`) - API Gateway
   - Request routing and validation
   - Authentication & authorization
   - Rate limiting
   - Thin layer - no business logic

3. **fks_app** (`repo/app`) - Main Application Logic
   - Trading strategies and signals
   - Portfolio management
   - ML/AI models
   - Backtesting engine

4. **fks_data** (`repo/data`) - Data Ingestion & Storage
   - Always-on data collection
   - Multi-source aggregation
   - Local caching (TimescaleDB + Redis)
   - Data normalization

5. **fks_execution** (`repo/execution`) - Rust Execution Engine
   - High-performance order execution
   - Exchange/broker API integration
   - Position tracking
   - **Only** service that communicates with exchanges

6. **fks_ninja** (`repo/ninja`) - NinjaTrader 8 Bridge
   - C# bridge for NinjaTrader integration
   - Futures prop firm trading
   - Signal relay to NinjaTrader

7. **fks_web** (`repo/web`) - Django Web UI
   - User-facing web interface
   - Bootstrap 5 templates
   - Visualization dashboards

## Migration Guide

If you need to reference old code:

1. **Check git history** - Use `git log --follow <file>` to trace file movements
2. **Review SERVICE_CLEANUP_PLAN.md** - Comprehensive migration documentation
3. **Search by functionality** - Use this mapping:
   - Trading strategies → `repo/app/src/domain/trading/`
   - Data collection → `repo/data/src/collectors/`
   - Order execution → `repo/execution/src/orders/`
   - API routes → `repo/api/src/routes/`
   - Web UI → `repo/web/src/templates/`

## Recovery

To restore archived code (emergency fallback):

```bash
# From archive root
git log --all -- archive/legacy_monolith/

# Restore specific file
git checkout <commit-hash> -- <file-path>
```

## See Also

- [SERVICE_CLEANUP_PLAN.md](../../docs/SERVICE_CLEANUP_PLAN.md) - Complete migration plan
- [MULTI_REPO_ARCHITECTURE.md](../../docs/MULTI_REPO_ARCHITECTURE.md) - Architecture overview
- [QUICKREF_MULTI_REPO.md](../../docs/QUICKREF_MULTI_REPO.md) - Quick reference

---

**Note:** This code is preserved for historical reference only. Do not add new features to archived code.
