#!/bin/bash
# FKS Intelligence RAG System Setup Script

set -e

echo "=================================="
echo "FKS Intelligence Setup"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running in docker
if [ -f /.dockerenv ]; then
    IN_DOCKER=true
else
    IN_DOCKER=false
fi

# Step 1: Check environment
echo -e "${YELLOW}Step 1: Checking environment...${NC}"

if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Creating from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}Please edit .env and add your OPENAI_API_KEY${NC}"
    exit 1
fi

# Check for OpenAI key
if ! grep -q "OPENAI_API_KEY=sk-" .env; then
    echo -e "${RED}Warning: OPENAI_API_KEY not set in .env${NC}"
    echo "Please add your OpenAI API key to .env:"
    echo "  OPENAI_API_KEY=sk-your-key-here"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}✓ Environment check passed${NC}"
echo ""

# Step 2: Start services
echo -e "${YELLOW}Step 2: Starting Docker services...${NC}"

if [ "$IN_DOCKER" = false ]; then
    docker-compose up -d db redis
    echo "Waiting for database to be ready..."
    sleep 10
    echo -e "${GREEN}✓ Services started${NC}"
else
    echo -e "${GREEN}✓ Already in Docker${NC}"
fi

echo ""

# Step 3: Enable pgvector
echo -e "${YELLOW}Step 3: Enabling pgvector extension...${NC}"

if [ "$IN_DOCKER" = false ]; then
    docker-compose exec -T db psql -U postgres -d trading_db -c "CREATE EXTENSION IF NOT EXISTS vector;" || true
else
    psql -U postgres -d trading_db -c "CREATE EXTENSION IF NOT EXISTS vector;" || true
fi

# Verify
if [ "$IN_DOCKER" = false ]; then
    VECTOR_ENABLED=$(docker-compose exec -T db psql -U postgres -d trading_db -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname='vector';")
else
    VECTOR_ENABLED=$(psql -U postgres -d trading_db -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname='vector';")
fi

if [ "$VECTOR_ENABLED" -ge 1 ]; then
    echo -e "${GREEN}✓ pgvector enabled${NC}"
else
    echo -e "${RED}✗ Failed to enable pgvector${NC}"
    exit 1
fi

echo ""

# Step 4: Create tables
echo -e "${YELLOW}Step 4: Creating database tables...${NC}"

if [ "$IN_DOCKER" = false ]; then
    docker-compose exec -T web python << 'PYTHON'
import sys
sys.path.insert(0, '/app')
from database import init_db
init_db()
print("Tables created successfully")
PYTHON
else
    python << 'PYTHON'
import sys
from database import init_db
init_db()
print("Tables created successfully")
PYTHON
fi

echo -e "${GREEN}✓ Database tables created${NC}"
echo ""

# Step 5: Run migrations
echo -e "${YELLOW}Step 5: Running RAG migrations...${NC}"

if [ "$IN_DOCKER" = false ]; then
    if [ -f sql/migrations/001_add_pgvector.sql ]; then
        docker-compose exec -T db psql -U postgres -d trading_db < sql/migrations/001_add_pgvector.sql || true
        echo -e "${GREEN}✓ Migrations applied${NC}"
    else
        echo -e "${YELLOW}⚠ Migration file not found, skipping${NC}"
    fi
else
    if [ -f /docker-entrypoint-initdb.d/migrations/001_add_pgvector.sql ]; then
        psql -U postgres -d trading_db -f /docker-entrypoint-initdb.d/migrations/001_add_pgvector.sql || true
        echo -e "${GREEN}✓ Migrations applied${NC}"
    fi
fi

echo ""

# Step 6: Test RAG system
echo -e "${YELLOW}Step 6: Testing RAG system...${NC}"

if [ "$IN_DOCKER" = false ]; then
    docker-compose exec -T web python << 'PYTHON'
import sys
sys.path.insert(0, '/app')

try:
    from rag.intelligence import create_intelligence
    
    print("Testing FKS Intelligence...")
    intelligence = create_intelligence()
    
    # Test document ingestion
    from database import Session
    session = Session()
    
    doc_id = intelligence.ingest_document(
        content="Bitcoin shows strong support at 40k level. RSI indicates oversold conditions. Consider long position.",
        doc_type="market_report",
        title="BTC Market Analysis - Test",
        symbol="BTCUSDT",
        timeframe="1h",
        metadata={"test": True},
        session=session
    )
    
    session.close()
    
    print(f"✓ Document ingested successfully (ID: {doc_id})")
    print("✓ RAG system is working!")
    
except Exception as e:
    print(f"✗ Error testing RAG: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON
else
    python << 'PYTHON'
import sys

try:
    from rag.intelligence import create_intelligence
    
    print("Testing FKS Intelligence...")
    intelligence = create_intelligence()
    
    from database import Session
    session = Session()
    
    doc_id = intelligence.ingest_document(
        content="Bitcoin shows strong support at 40k level. RSI indicates oversold conditions. Consider long position.",
        doc_type="market_report",
        title="BTC Market Analysis - Test",
        symbol="BTCUSDT",
        timeframe="1h",
        metadata={"test": True},
        session=session
    )
    
    session.close()
    
    print(f"✓ Document ingested successfully (ID: {doc_id})")
    print("✓ RAG system is working!")
    
except Exception as e:
    print(f"✗ Error testing RAG: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON
fi

echo -e "${GREEN}✓ RAG system test passed${NC}"
echo ""

# Summary
echo "=================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Ingest historical data:"
echo "     docker-compose exec web python -c '"
echo "from rag.ingestion import create_ingestion_pipeline"
echo "pipeline = create_ingestion_pipeline()"
echo "count = pipeline.batch_ingest_recent_trades(days=30)"
echo "print(f\"Ingested {count} trades\")"
echo "'"
echo ""
echo "  2. Query the knowledge base:"
echo "     docker-compose exec web python -c '"
echo "from rag.intelligence import create_intelligence"
echo "intelligence = create_intelligence()"
echo "result = intelligence.query(\"What strategy works best for BTCUSDT?\")"
echo "print(result[\"answer\"])"
echo "'"
echo ""
echo "  3. View documentation:"
echo "     cat docs/RAG_SETUP_GUIDE.md"
echo ""
echo "  4. Check project plan:"
echo "     cat docs/PROJECT_IMPROVEMENT_PLAN.md"
echo ""
echo "For issues, check logs in logs/ directory"
echo ""
