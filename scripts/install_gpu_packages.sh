#!/bin/bash
# Install GPU-enabled packages for FKS Trading Platform
# Requires: CUDA 11.8+ installed, Python 3.13, active venv
#
# Usage: source .venv-activate && bash scripts/install_gpu_packages.sh

set -e

echo "🎮 Installing GPU-enabled packages for FKS Trading Platform..."
echo ""

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Error: Virtual environment not activated"
    echo "Run: source ~/.venv/fks-trading/bin/activate"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "✅ Using Python $PYTHON_VERSION in venv: $VIRTUAL_ENV"
echo ""

# Step 1: Install base requirements (if not already installed)
echo "📦 Step 1/4: Installing base requirements..."
pip install -r requirements.txt
echo ""

# Step 2: Install PyTorch with CUDA 11.8 support
echo "🔥 Step 2/4: Installing PyTorch with CUDA 11.8..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
echo ""

# Step 3: Install GPU-accelerated ML libraries
echo "⚡ Step 3/4: Installing GPU-accelerated ML libraries..."
pip install -r requirements.gpu.txt
echo ""

# Step 4: Verify CUDA is available
echo "🔍 Step 4/4: Verifying CUDA availability..."
python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU device: {torch.cuda.get_device_name(0)}')
    print(f'GPU count: {torch.cuda.device_count()}')
else:
    print('⚠️  CUDA not available - GPU acceleration disabled')
    print('Check NVIDIA drivers and CUDA toolkit installation')
"
echo ""

echo "✅ GPU packages installation complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Test GPU: python -c 'import torch; print(torch.cuda.is_available())'"
echo "  2. Start services: make gpu-up"
echo "  3. Check RAG: http://localhost:8001"
