#!/usr/bin/env python3
"""
RAG Foundation Setup Script

This script sets up the basic RAG infrastructure:
1. Verifies database connectivity
2. Creates RAG tables if they don't exist
3. Enables pgvector extension
4. Creates necessary indexes
5. Tests basic functionality

Usage:
    python scripts/setup_rag_foundation.py
    
    # With specific database URL
    python scripts/setup_rag_foundation.py --db-url postgresql://user:pass@host:5432/dbname
    
    # Skip test phase
    python scripts/setup_rag_foundation.py --no-test
"""

import sys
import argparse
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from framework.config.constants import DATABASE_URL


def print_section(title: str, char: str = "="):
    """Print a formatted section header."""
    width = 80
    print(f"\n{char * width}")
    print(f" {title}")
    print(f"{char * width}\n")


def check_database_connection(db_url: str) -> bool:
    """
    Check if we can connect to the database.
    
    Args:
        db_url: Database URL
        
    Returns:
        True if connection successful, False otherwise
    """
    print_section("Step 1: Database Connection Check")
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✓ Connected to PostgreSQL")
            print(f"  Version: {version.split(',')[0]}")
            return True
    except OperationalError as e:
        print(f"✗ Database connection failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def enable_pgvector(db_url: str) -> bool:
    """
    Enable pgvector extension.
    
    Args:
        db_url: Database URL
        
    Returns:
        True if successful, False otherwise
    """
    print_section("Step 2: Enable pgvector Extension")
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Check if pgvector is available
            result = conn.execute(text(
                "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
            ))
            
            if not result.fetchone():
                print("✗ pgvector extension not available in this PostgreSQL installation")
                print("  Please install pgvector: https://github.com/pgvector/pgvector")
                return False
            
            # Enable the extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            
            # Verify it's enabled
            result = conn.execute(text(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            ))
            
            if result.fetchone():
                print("✓ pgvector extension enabled")
                return True
            else:
                print("✗ Failed to enable pgvector extension")
                return False
                
    except ProgrammingError as e:
        if "permission denied" in str(e).lower():
            print("✗ Permission denied. Need superuser or database owner privileges.")
            print("  Try running: psql -U postgres -d your_db -c 'CREATE EXTENSION vector;'")
        else:
            print(f"✗ Error enabling pgvector: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def create_rag_tables(db_url: str) -> bool:
    """
    Create RAG tables if they don't exist.
    
    Args:
        db_url: Database URL
        
    Returns:
        True if successful, False otherwise
    """
    print_section("Step 3: Create RAG Tables")
    
    try:
        # Read the SQL migration file
        sql_file = Path(__file__).parent.parent / 'sql' / 'migrations' / '000_create_rag_tables.sql'
        
        if not sql_file.exists():
            print(f"✗ Migration file not found: {sql_file}")
            return False
        
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Execute the SQL
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in sql_content.split(';') if s.strip()]
            
            for statement in statements:
                if statement and not statement.startswith('--'):
                    try:
                        conn.execute(text(statement))
                    except Exception as e:
                        # Some statements might fail if tables already exist - that's ok
                        if "already exists" not in str(e).lower():
                            print(f"  Warning: {e}")
            
            conn.commit()
        
        # Verify tables were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['documents', 'document_chunks', 'query_history', 'trading_insights']
        missing_tables = [t for t in expected_tables if t not in tables]
        
        if missing_tables:
            print(f"✗ Missing tables: {', '.join(missing_tables)}")
            return False
        
        print("✓ RAG tables created successfully:")
        for table in expected_tables:
            print(f"  - {table}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        return False


def create_vector_indexes(db_url: str) -> bool:
    """
    Create pgvector indexes for semantic search.
    
    Args:
        db_url: Database URL
        
    Returns:
        True if successful, False otherwise
    """
    print_section("Step 4: Create Vector Indexes")
    
    try:
        # Read the pgvector migration file
        sql_file = Path(__file__).parent.parent / 'sql' / 'migrations' / '001_add_pgvector.sql'
        
        if not sql_file.exists():
            print(f"✗ Migration file not found: {sql_file}")
            return False
        
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Execute the SQL
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Execute the full migration
            try:
                conn.execute(text(sql_content))
                conn.commit()
                print("✓ Vector indexes created successfully")
                return True
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("✓ Vector indexes already exist")
                    return True
                else:
                    print(f"✗ Error creating indexes: {e}")
                    return False
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_basic_functionality(db_url: str) -> bool:
    """
    Test basic RAG functionality.
    
    Args:
        db_url: Database URL
        
    Returns:
        True if tests pass, False otherwise
    """
    print_section("Step 5: Test Basic Functionality")
    
    try:
        from core.database.models import Session, Document, DocumentChunk
        
        session = Session()
        
        # Test 1: Create a document
        print("Test 1: Creating a test document...")
        doc = Document(
            doc_type='strategy',
            title='Test Strategy',
            content='This is a test strategy for RAG system verification.',
            symbol='BTCUSDT',
            metadata={'test': True}
        )
        session.add(doc)
        session.commit()
        print(f"  ✓ Document created with ID: {doc.id}")
        
        # Test 2: Create a document chunk
        print("\nTest 2: Creating a test chunk...")
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            content='Test chunk content',
            token_count=3
        )
        session.add(chunk)
        session.commit()
        print(f"  ✓ Chunk created with ID: {chunk.id}")
        
        # Test 3: Query documents
        print("\nTest 3: Querying documents...")
        docs = session.query(Document).filter(Document.doc_type == 'strategy').all()
        print(f"  ✓ Found {len(docs)} strategy document(s)")
        
        # Cleanup test data
        print("\nCleaning up test data...")
        session.delete(chunk)
        session.delete(doc)
        session.commit()
        session.close()
        print("  ✓ Test data cleaned up")
        
        print("\n✓ All basic functionality tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description='Setup RAG Foundation Infrastructure')
    parser.add_argument('--db-url', help='Database URL (default: from environment)')
    parser.add_argument('--no-test', action='store_true', help='Skip functionality tests')
    
    args = parser.parse_args()
    
    db_url = args.db_url or DATABASE_URL
    
    print_section("RAG Foundation Setup", "=")
    print(f"Database URL: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    
    # Step 1: Check database connection
    if not check_database_connection(db_url):
        print("\n❌ Setup failed: Cannot connect to database")
        return 1
    
    # Step 2: Enable pgvector
    if not enable_pgvector(db_url):
        print("\n⚠️  Warning: pgvector not enabled, but continuing...")
        print("   Vector search will not work until pgvector is installed")
    
    # Step 3: Create RAG tables
    if not create_rag_tables(db_url):
        print("\n❌ Setup failed: Could not create RAG tables")
        return 1
    
    # Step 4: Create vector indexes
    if not create_vector_indexes(db_url):
        print("\n⚠️  Warning: Vector indexes not created")
        print("   Semantic search may be slow without proper indexes")
    
    # Step 5: Test functionality (if not skipped)
    if not args.no_test:
        if not test_basic_functionality(db_url):
            print("\n⚠️  Warning: Some tests failed")
            print("   RAG tables are created but functionality may be limited")
    else:
        print_section("Step 5: Skipped (--no-test)", "-")
    
    # Final summary
    print_section("Setup Complete", "=")
    print("✓ RAG Foundation is ready!")
    print("\nNext steps:")
    print("  1. Start using the RAG system:")
    print("     from web.rag.services import IntelligenceOrchestrator")
    print("     orchestrator = IntelligenceOrchestrator()")
    print()
    print("  2. Run example script:")
    print("     python scripts/rag_example.py")
    print()
    print("  3. Ingest your trading data:")
    print("     python scripts/test_rag_system.py")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
