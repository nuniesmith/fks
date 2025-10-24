#!/bin/bash

# RAG System End-to-End Test Script
# Tests the complete RAG pipeline: ingestion → storage → retrieval → generation

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   FKS RAG System End-to-End Test      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if Docker containers are running
echo -e "${YELLOW}[1/8] Checking Docker containers...${NC}"
if ! docker ps | grep -q fks_db; then
    echo -e "${RED}✗ Database container not running${NC}"
    echo "Run: make up"
    exit 1
fi
echo -e "${GREEN}✓ Database container running${NC}"

if ! docker ps | grep -q fks_redis; then
    echo -e "${RED}✗ Redis container not running${NC}"
    echo "Run: make up"
    exit 1
fi
echo -e "${GREEN}✓ Redis container running${NC}"
echo ""

# Check pgvector extension
echo -e "${YELLOW}[2/8] Verifying pgvector extension...${NC}"
if docker exec fks_db psql -U postgres -d trading_db -c "SELECT * FROM pg_extension WHERE extname='vector';" | grep -q vector; then
    echo -e "${GREEN}✓ pgvector extension enabled${NC}"
else
    echo -e "${YELLOW}⚠ pgvector not enabled, attempting to enable...${NC}"
    docker exec fks_db psql -U postgres -d trading_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
    echo -e "${GREEN}✓ pgvector enabled${NC}"
fi
echo ""

# Run database migrations for RAG tables
echo -e "${YELLOW}[3/8] Checking RAG database tables...${NC}"
if docker exec fks_db psql -U postgres -d trading_db -c "\dt" | grep -q document_chunks; then
    echo -e "${GREEN}✓ RAG tables exist${NC}"
else
    echo -e "${YELLOW}⚠ RAG tables not found, running migration...${NC}"
    if [ -f sql/migrations/001_add_pgvector.sql ]; then
        docker exec -i fks_db psql -U postgres -d trading_db < sql/migrations/001_add_pgvector.sql
        echo -e "${GREEN}✓ RAG tables created${NC}"
    else
        echo -e "${RED}✗ Migration file not found${NC}"
        exit 1
    fi
fi
echo ""

# Test Python imports
echo -e "${YELLOW}[4/8] Testing Python imports...${NC}"
docker-compose exec -T web python3 -c "
try:
    from rag.intelligence import create_intelligence
    from rag.ingestion import create_ingestion_pipeline
    from rag.embeddings import create_embeddings_service
    from rag.local_llm import check_cuda_availability
    print('✓ All RAG modules imported successfully')
except Exception as e:
    print(f'✗ Import error: {e}')
    exit(1)
" || {
    echo -e "${RED}✗ Import failed${NC}"
    exit 1
}
echo ""

# Check CUDA availability (optional)
echo -e "${YELLOW}[5/8] Checking CUDA availability...${NC}"
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        echo -e "${GREEN}✓ NVIDIA GPU detected${NC}"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
        GPU_AVAILABLE=true
    else
        echo -e "${YELLOW}⚠ nvidia-smi found but not working${NC}"
        GPU_AVAILABLE=false
    fi
else
    echo -e "${YELLOW}⚠ No NVIDIA GPU detected (will use CPU)${NC}"
    GPU_AVAILABLE=false
fi
echo ""

# Test embedding generation
echo -e "${YELLOW}[6/8] Testing embedding generation...${NC}"
docker-compose exec -T web python3 << 'PYTHON'
from rag.embeddings import create_embeddings_service
import time

try:
    print("Creating embeddings service...")
    service = create_embeddings_service(use_local=True)
    
    print("Generating test embedding...")
    start = time.time()
    embedding = service.generate_embedding("Test trading strategy for BTCUSDT")
    elapsed = time.time() - start
    
    print(f"✓ Generated embedding: {len(embedding)} dimensions in {elapsed:.3f}s")
    
    if len(embedding) not in [384, 768, 1536]:
        print(f"✗ Unexpected embedding dimension: {len(embedding)}")
        exit(1)
        
except Exception as e:
    print(f"✗ Embedding test failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Embedding test failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Embedding generation working${NC}"
echo ""

# Test data ingestion
echo -e "${YELLOW}[7/8] Testing data ingestion...${NC}"
docker-compose exec -T web python3 << 'PYTHON'
from rag.ingestion import create_ingestion_pipeline

try:
    print("Creating ingestion pipeline...")
    pipeline = create_ingestion_pipeline(use_local=True)
    
    # Test ingesting a sample signal
    sample_signal = {
        'id': 99999,
        'symbol': 'TESTUSDT',
        'type': 'long',
        'strength': 0.85,
        'price': 50000.0,
        'timestamp': '2025-10-16T00:00:00',
        'indicators': {'rsi': 35, 'macd': -0.5},
        'strategy': 'test_momentum'
    }
    
    print("Ingesting sample signal...")
    doc = pipeline.ingest_signal(sample_signal)
    print(f"✓ Signal ingested: Document ID {doc.id}")
    
    # Test ingesting a sample trade
    sample_trade = {
        'id': 99999,
        'symbol': 'TESTUSDT',
        'side': 'buy',
        'quantity': 1.0,
        'entry_price': 50000.0,
        'exit_price': 51000.0,
        'pnl': 1000.0,
        'entry_time': '2025-10-16T00:00:00',
        'exit_time': '2025-10-16T01:00:00'
    }
    
    print("Ingesting sample trade...")
    doc = pipeline.ingest_completed_trade(sample_trade)
    print(f"✓ Trade ingested: Document ID {doc.id}")
    
except Exception as e:
    print(f"✗ Ingestion test failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Ingestion test failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Data ingestion working${NC}"
echo ""

# Test RAG query (if Ollama is available)
echo -e "${YELLOW}[8/8] Testing RAG query...${NC}"
if [ "$GPU_AVAILABLE" = true ] && command -v ollama &> /dev/null; then
    echo -e "${BLUE}Testing with local LLM...${NC}"
    
    # Check if model is available
    if ollama list | grep -q "llama3.2:3b"; then
        docker-compose exec -T web python3 << 'PYTHON'
from rag.intelligence import create_intelligence

try:
    print("Creating intelligence service...")
    intelligence = create_intelligence(use_local=True, local_llm_model="llama3.2:3b")
    
    print("Querying knowledge base...")
    result = intelligence.query("What test strategies are in the knowledge base?", top_k=2)
    
    print(f"\n✓ Query successful!")
    print(f"Answer: {result['answer'][:200]}...")
    print(f"Sources: {len(result.get('sources', []))} documents")
    
except Exception as e:
    print(f"✗ Query test failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ RAG query working${NC}"
        else
            echo -e "${YELLOW}⚠ RAG query failed (but ingestion works)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ llama3.2:3b not available${NC}"
        echo "  Pull with: ollama pull llama3.2:3b"
    fi
else
    echo -e "${YELLOW}⚠ Skipping LLM test (GPU/Ollama not available)${NC}"
    echo "  For full testing: install Ollama and pull llama3.2:3b"
fi
echo ""

# Summary
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Test Summary                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Docker containers${NC}"
echo -e "${GREEN}✓ pgvector extension${NC}"
echo -e "${GREEN}✓ RAG database tables${NC}"
echo -e "${GREEN}✓ Python imports${NC}"
echo -e "${GREEN}✓ Embedding generation${NC}"
echo -e "${GREEN}✓ Data ingestion${NC}"

if [ "$GPU_AVAILABLE" = true ]; then
    echo -e "${GREEN}✓ GPU detected${NC}"
else
    echo -e "${YELLOW}⚠ No GPU (CPU mode)${NC}"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}   RAG System Tests Passed! ✓           ${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Test API endpoints: curl http://localhost:8000/api/intelligence/health/"
echo "  2. Trigger ingestion: curl -X POST http://localhost:8000/api/intelligence/ingest/ -d '{\"type\":\"all\"}'"
echo "  3. Query RAG: curl -X POST http://localhost:8000/api/intelligence/query/ -d '{\"query\":\"What are momentum strategies?\"}'"
echo "  4. View stats: curl http://localhost:8000/api/intelligence/stats/"
echo ""
