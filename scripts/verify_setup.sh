#!/bin/bash
# Verify Python 3.13 Virtual Environment Setup
# Usage: source .venv-activate && bash scripts/verify_setup.sh

set -e

echo "🔍 Verifying FKS Python 3.13 Virtual Environment Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Virtual environment not activated!"
    echo "   Run: source ~/.venv/fks-trading/bin/activate"
    exit 1
fi

echo "✅ Virtual Environment: $VIRTUAL_ENV"
echo ""

# Python version
PYTHON_VERSION=$(python --version)
echo "📦 $PYTHON_VERSION"

# Pip version
PIP_VERSION=$(pip --version | awk '{print $2}')
echo "📦 pip $PIP_VERSION"
echo ""

# Key package checks
echo "🔧 Checking Core Packages..."
python -c "
import sys

packages = {
    'Django': 'django',
    'Celery': 'celery',
    'pandas': 'pandas',
    'numpy': 'numpy',
    'scikit-learn': 'sklearn',
    'PyTorch': 'torch',
    'transformers': 'transformers',
    'langchain': 'langchain',
    'chromadb': 'chromadb',
    'sqlalchemy': 'sqlalchemy',
    'redis': 'redis',
    'pytest': 'pytest',
}

for name, module in packages.items():
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'unknown')
        print(f'  ✅ {name}: {version}')
    except ImportError:
        print(f'  ❌ {name}: NOT INSTALLED')
        sys.exit(1)
"

echo ""
echo "🎮 Checking GPU Support..."
python -c "
import torch

print(f'  PyTorch version: {torch.__version__}')
print(f'  CUDA available: {torch.cuda.is_available()}')

if torch.cuda.is_available():
    print(f'  CUDA version: {torch.version.cuda}')
    print(f'  cuDNN version: {torch.backends.cudnn.version()}')
    print(f'  GPU count: {torch.cuda.device_count()}')
    for i in range(torch.cuda.device_count()):
        print(f'  GPU {i}: {torch.cuda.get_device_name(i)}')
else:
    print('  ⚠️  CUDA not available - CPU mode only')
    print('  Note: Install NVIDIA drivers for GPU acceleration')
"

echo ""
echo "📊 Package Statistics..."
PACKAGE_COUNT=$(pip list | wc -l)
echo "  Total packages installed: $((PACKAGE_COUNT - 2))"

echo ""
echo "✅ Setup verification complete!"
echo ""
echo "🚀 Next steps:"
echo "  1. Fix import errors: gh issue develop 48 --checkout"
echo "  2. Run tests: pytest tests/ -v"
echo "  3. Start development: python src/manage.py runserver"
echo ""
