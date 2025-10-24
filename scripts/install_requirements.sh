#!/bin/bash
# Install requirements for Python 3.13 with compatibility fixes
# Some packages don't have Python 3.13 wheels yet, so we install with fallbacks
#
# Usage: source .venv-activate && bash scripts/install_requirements.sh

set -e

echo "📦 Installing FKS Trading Platform Requirements for Python 3.13"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Error: Virtual environment not activated"
    echo "Run: source ~/.venv/fks-trading/bin/activate"
    exit 1
fi

PYTHON_VERSION=$(python --version | awk '{print $2}')
echo "✅ Using Python $PYTHON_VERSION"
echo ""

# Step 1: Upgrade pip, setuptools, wheel
echo "📦 Step 1/4: Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel
echo ""

# Step 2: Install PyTorch with CUDA 11.8 first (overrides CPU version)
echo "🔥 Step 2/4: Installing PyTorch with CUDA 11.8..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
echo ""

# Step 3: Install base requirements (skip packages without Python 3.13 support)
echo "📦 Step 3/4: Installing base requirements..."
# Try to install everything, but continue on errors
pip install -r requirements.txt --ignore-installed || {
    echo "⚠️  Some packages failed to install (expected for Python 3.13)"
    echo "   Continuing with individual package installation..."
}
echo ""

# Step 4: Install GPU-specific packages (excluding those already installed)
echo "⚡ Step 4/4: Installing GPU-accelerated packages..."
pip install xgboost>=3.0.5 lightgbm>=4.6.0 || echo "⚠️  xgboost/lightgbm failed"
pip install transformers>=4.57.1 accelerate>=1.10.1 || echo "⚠️  transformers/accelerate failed"
pip install sentence-transformers>=5.1.1 || echo "⚠️  sentence-transformers failed"
pip install bitsandbytes>=0.48.1 || echo "⚠️  bitsandbytes failed"

# llama-cpp-python requires compilation
echo ""
echo "🔧 Installing llama-cpp-python (may take a few minutes to compile)..."
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python>=0.3.16 || {
    echo "⚠️  llama-cpp-python with CUDA failed, trying CPU version..."
    pip install llama-cpp-python>=0.3.16
}

echo ""
echo "✅ Installation complete!"
echo ""

# Verify critical packages
echo "🔍 Verifying critical packages..."
python -c "
import sys
critical = ['django', 'celery', 'torch', 'pandas', 'numpy']
failed = []
for pkg in critical:
    try:
        __import__(pkg)
        print(f'  ✅ {pkg}')
    except ImportError:
        print(f'  ❌ {pkg} - NOT INSTALLED')
        failed.append(pkg)

if failed:
    print(f'\n❌ Failed packages: {failed}')
    print('Try reinstalling with: pip install ' + ' '.join(failed))
    sys.exit(1)
else:
    print('\n✅ All critical packages installed successfully!')
"

echo ""
echo "📊 Installation summary:"
pip list | grep -E "(Django|torch|celery|pandas|numpy|transformers)" || echo "Packages installed"
echo ""
echo "🚀 Next steps:"
echo "  1. Verify setup: bash scripts/verify_setup.sh"
echo "  2. Run tests: pytest tests/ -v"
echo "  3. Start development: python src/manage.py runserver"
