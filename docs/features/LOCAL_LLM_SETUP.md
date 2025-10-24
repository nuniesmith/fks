# FKS Intelligence - Local LLM Setup Guide with CUDA

## Overview

This guide covers setting up FKS Intelligence with local CUDA-accelerated models instead of OpenAI API. This provides:
- **Zero API costs** - No per-request fees
- **Privacy** - Your data stays local
- **Speed** - Fast inference with GPU acceleration
- **Offline capability** - Works without internet

## Prerequisites

### Hardware Requirements

**Minimum:**
- NVIDIA GPU with 6GB+ VRAM (GTX 1660, RTX 3060, etc.)
- CUDA 11.8 or higher
- 16GB system RAM

**Recommended:**
- NVIDIA GPU with 12GB+ VRAM (RTX 3080, RTX 4070, etc.)
- CUDA 12.0 or higher
- 32GB system RAM

### Software Requirements

- Docker with NVIDIA Container Toolkit (for GPU support)
- OR native Linux/WSL with CUDA drivers

## Setup Options

### Option 1: Ollama (Recommended - Easiest)

Ollama is the easiest way to run local LLMs with GPU acceleration.

#### 1.1 Install Ollama

**Linux/WSL:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from https://ollama.com/download

#### 1.2 Start Ollama Service

```bash
# Start service
ollama serve

# In another terminal, verify it's running
ollama list
```

#### 1.3 Pull Models

```bash
# Small, fast model (3B params, ~2GB VRAM)
ollama pull llama3.2:3b

# Tiny model (1B params, ~1GB VRAM)
ollama pull llama3.2:1b

# Better quality (7B params, ~4GB VRAM)
ollama pull mistral:7b

# Good balance (3.8B params, ~2.5GB VRAM)
ollama pull phi3:mini
```

#### 1.4 Test Ollama

```bash
# Test generation
ollama run llama3.2:3b "What is a good trading strategy?"
```

### Option 2: Docker with GPU Support

Add GPU support to your Docker Compose setup.

#### 2.1 Install NVIDIA Container Toolkit

**Ubuntu/Debian:**
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

#### 2.2 Update docker-compose.yml

Add to your `web` service:

```yaml
web:
  # ... existing config ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Option 3: Native Installation

Install dependencies directly on your system.

```bash
# Install PyTorch with CUDA
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install other dependencies
pip install sentence-transformers transformers accelerate bitsandbytes ollama
```

## Configuration

### Update Environment

Add to your `.env`:

```bash
# RAG Configuration
USE_LOCAL_LLM=true
LOCAL_LLM_MODEL=llama3.2:3b
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Optional: Fallback to OpenAI if local fails
OPENAI_API_KEY=your_key_here  # Optional
```

### Verify CUDA Setup

```python
python -c "
import torch
print(f'CUDA Available: {torch.cuda.is_available()}')
print(f'CUDA Version: {torch.version.cuda}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
"
```

Expected output:
```
CUDA Available: True
CUDA Version: 12.1
GPU: NVIDIA GeForce RTX 3080
VRAM: 10.0 GB
```

## Model Selection Guide

### Embedding Models (Sentence Transformers)

**Fast & Small (384d):**
- `all-MiniLM-L6-v2` - Best for speed, 384 dimensions
- `all-MiniLM-L12-v2` - Slightly better quality, 384 dimensions

**Better Quality (768d):**
- `all-mpnet-base-v2` - Good balance, 768 dimensions
- `all-roberta-large-v1` - Higher quality, 1024 dimensions

**Performance:**
- MiniLM-L6: ~1000 texts/sec on RTX 3080
- MPNet: ~500 texts/sec on RTX 3080

### Generation Models (Ollama)

**Recommended Models:**

| Model | Size | VRAM | Speed | Quality | Use Case |
|-------|------|------|-------|---------|----------|
| llama3.2:1b | 1B | 1GB | ⚡⚡⚡ | ⭐⭐ | Testing |
| llama3.2:3b | 3B | 2GB | ⚡⚡ | ⭐⭐⭐ | Production |
| phi3:mini | 3.8B | 2.5GB | ⚡⚡ | ⭐⭐⭐⭐ | Best balance |
| mistral:7b | 7B | 4GB | ⚡ | ⭐⭐⭐⭐⭐ | High quality |
| llama3:8b | 8B | 6GB | ⚡ | ⭐⭐⭐⭐⭐ | Best quality |

**Choosing a Model:**
- **6GB GPU**: Use llama3.2:3b or phi3:mini
- **8GB GPU**: Use mistral:7b
- **12GB+ GPU**: Use llama3:8b or mistral:7b-instruct

## Testing Local Setup

### 1. Test CUDA and Models

```bash
cd /path/to/fks
docker-compose exec web python src/rag/local_llm.py
```

Or directly:
```bash
python scripts/test_local_llm.py
```

### 2. Test RAG System

```python
from rag.intelligence import create_intelligence

# Create with local models
intelligence = create_intelligence(
    use_local=True,
    local_llm_model="llama3.2:3b",
    embedding_model="all-MiniLM-L6-v2"
)

# Test query
result = intelligence.query("What is a good strategy for Bitcoin?")
print(result['answer'])
```

### 3. Benchmark Performance

```python
from rag.local_llm import check_cuda_availability, create_local_embeddings
import time

# Check CUDA
print(check_cuda_availability())

# Benchmark embeddings
embeddings = create_local_embeddings()

texts = ["Sample text"] * 1000
start = time.time()
results = embeddings.generate_embeddings_batch(texts)
elapsed = time.time() - start

print(f"Embedded {len(texts)} texts in {elapsed:.2f}s")
print(f"Speed: {len(texts)/elapsed:.0f} texts/sec")
```

## Performance Optimization

### 1. Adjust Batch Sizes

```python
# For embeddings - larger batches = faster
embeddings = create_local_embeddings()
embeddings.generate_embeddings_batch(texts, batch_size=64)  # Increase for more VRAM
```

### 2. Use Quantization

Reduce memory usage with quantized models:

```bash
# Ollama automatically uses quantization
# Q4 models use ~50% less VRAM
ollama pull llama3.2:3b-q4_0  # 4-bit quantized
```

### 3. GPU Memory Management

```python
import torch

# Clear cache between operations
torch.cuda.empty_cache()

# Monitor memory usage
allocated = torch.cuda.memory_allocated() / 1e9
print(f"GPU memory: {allocated:.2f} GB")
```

## Troubleshooting

### Issue: CUDA Not Available

```bash
# Check NVIDIA driver
nvidia-smi

# Check CUDA installation
nvcc --version

# Reinstall PyTorch with CUDA
pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu118
```

### Issue: Out of Memory

Solutions:
1. Use smaller model (llama3.2:1b instead of mistral:7b)
2. Reduce batch size
3. Close other GPU applications
4. Enable quantization

### Issue: Ollama Not Responding

```bash
# Check if running
ps aux | grep ollama

# Restart service
pkill ollama
ollama serve

# Check logs
journalctl -u ollama -f
```

### Issue: Slow Performance

Checklist:
- [ ] Verify GPU is being used (`nvidia-smi` shows process)
- [ ] Use smaller model
- [ ] Increase batch size (if VRAM allows)
- [ ] Check system isn't thermal throttling

## Production Deployment

### 1. Create Ollama Service

**docker-compose.yml:**
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: fks_ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - fks-network

volumes:
  ollama_data:
```

### 2. Pre-pull Models

```bash
# Start Ollama
docker-compose up -d ollama

# Pull models
docker-compose exec ollama ollama pull llama3.2:3b
docker-compose exec ollama ollama pull all-minilm
```

### 3. Update Web Service

```yaml
web:
  environment:
    - OLLAMA_HOST=http://ollama:11434
    - USE_LOCAL_LLM=true
```

## Cost Comparison

### OpenAI API Costs

**Embeddings:**
- text-embedding-3-small: $0.02 per 1M tokens
- 10,000 documents: ~$0.20-$1.00

**Generation:**
- GPT-4o-mini input: $0.150 per 1M tokens
- GPT-4o-mini output: $0.600 per 1M tokens
- 1000 queries: ~$2-$10

**Monthly (moderate usage):**
- ~$50-200/month

### Local Setup Costs

**One-time:**
- GPU (if needed): $200-$1000
- Electricity: ~$5-15/month (24/7)

**Break-even:** 1-4 months for moderate usage

## Recommended Setup

### For Development (6-8GB GPU)

```bash
# Ollama
ollama pull llama3.2:3b

# Environment
USE_LOCAL_LLM=true
LOCAL_LLM_MODEL=llama3.2:3b
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### For Production (12GB+ GPU)

```bash
# Ollama
ollama pull mistral:7b
ollama pull phi3:mini

# Environment
USE_LOCAL_LLM=true
LOCAL_LLM_MODEL=mistral:7b
LOCAL_EMBEDDING_MODEL=all-mpnet-base-v2
```

## Next Steps

1. **Test the setup:**
   ```bash
   cd scripts
   chmod +x test_local_llm.sh
   ./test_local_llm.sh
   ```

2. **Ingest data:**
   ```bash
   docker-compose exec web python -c "
   from rag.ingestion import create_ingestion_pipeline
   pipeline = create_ingestion_pipeline()
   count = pipeline.batch_ingest_recent_trades(days=30)
   print(f'Ingested {count} trades')
   "
   ```

3. **Query the system:**
   ```bash
   docker-compose exec web python scripts/test_rag.py
   ```

4. **Monitor GPU usage:**
   ```bash
   watch -n 1 nvidia-smi
   ```

## Support

- Ollama docs: https://ollama.com/docs
- Sentence Transformers: https://www.sbert.net/
- PyTorch CUDA: https://pytorch.org/get-started/locally/

## Performance Metrics

Expected performance on RTX 3080:

| Operation | Speed | Notes |
|-----------|-------|-------|
| Embeddings (batch) | 1000/sec | MiniLM-L6 |
| Query (llama3.2:3b) | 50 tok/sec | ~2s response |
| Query (mistral:7b) | 30 tok/sec | ~3s response |
| Ingestion (1000 docs) | ~5 min | Including embeddings |
