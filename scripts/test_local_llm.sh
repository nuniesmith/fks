#!/bin/bash
# Test local LLM setup with CUDA

set -e

echo "=================================="
echo "Testing Local LLM Setup"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check NVIDIA drivers
echo -e "${YELLOW}Step 1: Checking NVIDIA drivers...${NC}"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo -e "${GREEN}✓ NVIDIA drivers installed${NC}"
else
    echo -e "${RED}✗ NVIDIA drivers not found${NC}"
    echo "Install NVIDIA drivers first"
    exit 1
fi
echo ""

# Step 2: Check CUDA
echo -e "${YELLOW}Step 2: Checking CUDA availability...${NC}"
python3 << 'PYTHON'
import torch

cuda_available = torch.cuda.is_available()
print(f"CUDA Available: {cuda_available}")

if cuda_available:
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"PyTorch Version: {torch.__version__}")
    print(f"GPU Count: {torch.cuda.device_count()}")
    
    for i in range(torch.cuda.device_count()):
        print(f"\nGPU {i}:")
        print(f"  Name: {torch.cuda.get_device_name(i)}")
        props = torch.cuda.get_device_properties(i)
        print(f"  Memory: {props.total_memory / 1e9:.1f} GB")
        print(f"  Compute: {props.major}.{props.minor}")
else:
    print("ERROR: CUDA not available")
    exit(1)
PYTHON

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ CUDA working${NC}"
else
    echo -e "${RED}✗ CUDA not available${NC}"
    exit 1
fi
echo ""

# Step 3: Check Ollama
echo -e "${YELLOW}Step 3: Checking Ollama...${NC}"
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓ Ollama installed${NC}"
    
    # Check if service is running
    if curl -s http://localhost:11434 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Ollama service running${NC}"
        
        # List models
        echo ""
        echo "Available models:"
        ollama list
    else
        echo -e "${YELLOW}⚠ Ollama not running${NC}"
        echo "Start with: ollama serve"
    fi
else
    echo -e "${YELLOW}⚠ Ollama not installed${NC}"
    echo "Install from: https://ollama.com"
fi
echo ""

# Step 4: Test local embeddings
echo -e "${YELLOW}Step 4: Testing local embeddings...${NC}"
python3 << 'PYTHON'
import sys
sys.path.insert(0, 'src')

try:
    from rag.local_llm import create_local_embeddings
    import time
    
    print("Loading embedding model...")
    embeddings = create_local_embeddings(model_name="all-MiniLM-L6-v2")
    
    # Test single embedding
    test_text = "Bitcoin trading strategy"
    start = time.time()
    result = embeddings.generate_embedding(test_text)
    elapsed = time.time() - start
    
    print(f"✓ Generated embedding in {elapsed*1000:.1f}ms")
    print(f"  Dimension: {len(result)}")
    
    # Test batch
    batch_texts = ["Test"] * 100
    start = time.time()
    results = embeddings.generate_embeddings_batch(batch_texts)
    elapsed = time.time() - start
    
    speed = len(batch_texts) / elapsed
    print(f"✓ Batch performance: {speed:.0f} texts/sec")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Local embeddings working${NC}"
else
    echo -e "${RED}✗ Embeddings test failed${NC}"
    exit 1
fi
echo ""

# Step 5: Test Ollama LLM
echo -e "${YELLOW}Step 5: Testing Ollama LLM...${NC}"
if curl -s http://localhost:11434 > /dev/null 2>&1; then
    python3 << 'PYTHON'
import sys
sys.path.insert(0, 'src')

try:
    from rag.local_llm import create_local_llm
    import time
    
    print("Loading LLM (llama3.2:3b)...")
    llm = create_local_llm(model_name="llama3.2:3b", backend="ollama")
    
    print("Generating response...")
    start = time.time()
    response = llm.generate(
        prompt="What is 2+2?",
        max_tokens=50
    )
    elapsed = time.time() - start
    
    print(f"✓ Response generated in {elapsed:.1f}s")
    print(f"  Output: {response[:100]}...")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Ollama LLM working${NC}"
    else
        echo -e "${YELLOW}⚠ LLM test failed (model may not be pulled)${NC}"
        echo "  Pull model with: ollama pull llama3.2:3b"
    fi
else
    echo -e "${YELLOW}⚠ Ollama service not running, skipping LLM test${NC}"
fi
echo ""

# Summary
echo "=================================="
echo -e "${GREEN}Setup Test Complete${NC}"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. If Ollama is not installed:"
echo "     curl -fsSL https://ollama.com/install.sh | sh"
echo ""
echo "  2. Start Ollama service:"
echo "     ollama serve"
echo ""
echo "  3. Pull a model:"
echo "     ollama pull llama3.2:3b"
echo ""
echo "  4. Test RAG system:"
echo "     python scripts/test_rag.py"
echo ""
echo "  5. See full guide:"
echo "     cat docs/LOCAL_LLM_SETUP.md"
echo ""
