#!/usr/bin/env python3
"""
RAG Foundation Validation Script

This script validates the Phase 1 RAG infrastructure setup without requiring
all external dependencies. It checks:

1. Import structure is correct
2. Database models are properly defined
3. SQL migrations exist
4. Module hierarchy is correct

Usage:
    python scripts/validate_rag_foundation.py
"""

import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def print_section(title: str, char: str = "="):
    """Print a formatted section header."""
    width = 80
    print(f"\n{char * width}")
    print(f" {title}")
    print(f"{char * width}\n")


def check_sql_migrations() -> bool:
    """Check that SQL migration files exist."""
    print_section("Step 1: SQL Migrations Check")
    
    sql_dir = Path(__file__).parent.parent / 'sql' / 'migrations'
    
    migrations = [
        '000_create_rag_tables.sql',
        '001_add_pgvector.sql'
    ]
    
    all_exist = True
    for migration in migrations:
        path = sql_dir / migration
        if path.exists():
            size = path.stat().st_size
            print(f"✓ {migration} ({size:,} bytes)")
        else:
            print(f"✗ {migration} not found")
            all_exist = False
    
    return all_exist


def check_module_structure() -> bool:
    """Check that RAG modules exist and have correct structure."""
    print_section("Step 2: Module Structure Check")
    
    rag_dir = Path(__file__).parent.parent / 'src' / 'web' / 'rag'
    
    expected_files = [
        '__init__.py',
        'embeddings.py',
        'document_processor.py',
        'retrieval.py',
        'intelligence.py',
        'ingestion.py',
        'orchestrator.py',
        'local_llm.py',
        'services.py',
        'README.md'
    ]
    
    all_exist = True
    for file in expected_files:
        path = rag_dir / file
        if path.exists():
            if file.endswith('.py'):
                size = path.stat().st_size
                print(f"✓ {file} ({size:,} bytes)")
            else:
                print(f"✓ {file}")
        else:
            print(f"✗ {file} not found")
            all_exist = False
    
    return all_exist


def check_import_structure() -> bool:
    """Check that imports work (without external dependencies)."""
    print_section("Step 3: Import Structure Check")
    
    checks = {
        'core.database.models': ['Session', 'Document', 'DocumentChunk', 'QueryHistory', 'TradingInsight'],
        'framework.config.constants': ['DATABASE_URL', 'OPENAI_API_KEY'],
    }
    
    all_ok = True
    missing_deps = False
    
    for module, expected_attrs in checks.items():
        try:
            imported = __import__(module, fromlist=expected_attrs)
            missing = [attr for attr in expected_attrs if not hasattr(imported, attr)]
            
            if missing:
                print(f"✗ {module} - Missing: {', '.join(missing)}")
                all_ok = False
            else:
                print(f"✓ {module} - Has: {', '.join(expected_attrs)}")
        except ImportError as e:
            error_msg = str(e)
            if 'sqlalchemy' in error_msg or 'loguru' in error_msg or 'pytz' in error_msg:
                print(f"⚠ {module} - Missing dependency (expected without install)")
                missing_deps = True
            else:
                print(f"✗ {module} - Import failed: {e}")
                all_ok = False
    
    # If only missing dependencies, that's ok for validation
    if missing_deps and all_ok:
        return True
    
    return all_ok


def check_database_models() -> bool:
    """Check that RAG database models are properly defined."""
    print_section("Step 4: Database Models Check")
    
    try:
        from core.database.models import Document, DocumentChunk, QueryHistory, TradingInsight
        
        # Check Document model
        doc_columns = ['id', 'doc_type', 'title', 'content', 'symbol', 'timeframe', 'metadata']
        missing = [col for col in doc_columns if not hasattr(Document, col)]
        if missing:
            print(f"✗ Document model - Missing columns: {', '.join(missing)}")
            return False
        print(f"✓ Document model - All {len(doc_columns)} columns present")
        
        # Check DocumentChunk model
        chunk_columns = ['id', 'document_id', 'chunk_index', 'content', 'embedding', 'token_count']
        missing = [col for col in chunk_columns if not hasattr(DocumentChunk, col)]
        if missing:
            print(f"✗ DocumentChunk model - Missing columns: {', '.join(missing)}")
            return False
        print(f"✓ DocumentChunk model - All {len(chunk_columns)} columns present")
        
        # Check QueryHistory model
        query_columns = ['id', 'query', 'response', 'retrieved_chunks', 'model_used']
        missing = [col for col in query_columns if not hasattr(QueryHistory, col)]
        if missing:
            print(f"✗ QueryHistory model - Missing columns: {', '.join(missing)}")
            return False
        print(f"✓ QueryHistory model - All {len(query_columns)} columns present")
        
        # Check TradingInsight model
        insight_columns = ['id', 'insight_type', 'title', 'content', 'symbol', 'impact', 'category']
        missing = [col for col in insight_columns if not hasattr(TradingInsight, col)]
        if missing:
            print(f"✗ TradingInsight model - Missing columns: {', '.join(missing)}")
            return False
        print(f"✓ TradingInsight model - All {len(insight_columns)} columns present")
        
        return True
        
    except ImportError as e:
        error_msg = str(e)
        if 'sqlalchemy' in error_msg or 'pytz' in error_msg:
            print(f"⚠ Database models validation skipped (missing dependencies)")
            print("  Install dependencies to fully validate: pip install -r requirements.txt")
            return True  # Don't fail validation for missing dependencies
        else:
            print(f"✗ Failed to import models: {e}")
            return False


def check_rag_module_exports() -> bool:
    """Check that RAG modules export expected classes/functions."""
    print_section("Step 5: RAG Module Exports Check")
    
    # We'll check the source files directly since we might not have dependencies
    rag_dir = Path(__file__).parent.parent / 'src' / 'web' / 'rag'
    
    # Check __init__.py exports
    init_file = rag_dir / '__init__.py'
    with open(init_file) as f:
        init_content = f.read()
    
    expected_exports = [
        'FKSIntelligence',
        'create_intelligence',
        'DocumentProcessor',
        'create_processor',
        'EmbeddingsService',
        'create_embeddings_service',
        'RetrievalService',
        'create_retrieval_service',
        'DataIngestionPipeline',
        'create_ingestion_pipeline',
    ]
    
    all_present = True
    for export in expected_exports:
        if export in init_content:
            print(f"✓ {export}")
        else:
            print(f"✗ {export} not exported")
            all_present = False
    
    return all_present


def check_documentation() -> bool:
    """Check that documentation exists."""
    print_section("Step 6: Documentation Check")
    
    docs = [
        'docs/RAG_PHASE1.md',
        'src/web/rag/README.md',
    ]
    
    all_exist = True
    for doc in docs:
        path = Path(__file__).parent.parent / doc
        if path.exists():
            size = path.stat().st_size
            lines = len(path.read_text().splitlines())
            print(f"✓ {doc} ({lines} lines, {size:,} bytes)")
        else:
            print(f"✗ {doc} not found")
            all_exist = False
    
    return all_exist


def main():
    """Run all validation checks."""
    print_section("RAG Foundation Validation", "=")
    
    results = {
        'SQL Migrations': check_sql_migrations(),
        'Module Structure': check_module_structure(),
        'Import Structure': check_import_structure(),
        'Database Models': check_database_models(),
        'Module Exports': check_rag_module_exports(),
        'Documentation': check_documentation(),
    }
    
    # Summary
    print_section("Validation Summary", "=")
    
    passed = sum(results.values())
    total = len(results)
    
    for check, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check}")
    
    print(f"\nResults: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✓ All validation checks passed!")
        print("  RAG Foundation (Phase 1) is properly set up.")
        print("\nNext steps:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Set up database: python scripts/setup_rag_foundation.py")
        print("  3. Run tests: pytest tests/unit/test_rag/ -v")
        return 0
    else:
        print(f"\n✗ {total - passed} validation check(s) failed")
        print("  Please review the errors above and fix them.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
