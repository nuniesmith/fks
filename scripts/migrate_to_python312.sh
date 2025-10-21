#!/bin/bash
# Migrate from Python 3.13 to Python 3.12 for better package compatibility
# Usage: bash scripts/migrate_to_python312.sh

set -e

echo "🔄 Migrating from Python 3.13 to Python 3.12"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Why Python 3.12?"
echo "  - ✅ Full package compatibility (all wheels available)"
echo "  - ✅ Production-ready and stable"
echo "  - ✅ Used by Django, FastAPI, major projects"
echo "  - ✅ Python 3.13 is too new (released Oct 2024)"
echo ""
read -p "Continue with migration? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 1
fi

echo ""
echo "Step 1/5: Checking Python versions..."
if command -v python3.12 &> /dev/null; then
    PYTHON312_VERSION=$(python3.12 --version)
    echo "  ✅ $PYTHON312_VERSION found"
else
    echo "  ❌ Python 3.12 not installed"
    echo ""
    echo "Installing Python 3.12..."
    sudo apt update
    sudo apt install -y python3.12 python3.12-venv python3.12-dev
    echo "  ✅ Python 3.12 installed"
fi

echo ""
echo "Step 2/5: Backing up current venv..."
if [ -d ~/.venv/fks-trading ]; then
    mv ~/.venv/fks-trading ~/.venv/fks-trading-py313-backup
    echo "  ✅ Backed up to ~/.venv/fks-trading-py313-backup"
else
    echo "  ⚠️  No existing venv found"
fi

echo ""
echo "Step 3/5: Creating new Python 3.12 virtual environment..."
python3.12 -m venv ~/.venv/fks-trading
echo "  ✅ Created ~/.venv/fks-trading with Python 3.12"

echo ""
echo "Step 4/5: Activating and upgrading pip..."
source ~/.venv/fks-trading/bin/activate
pip install --upgrade pip setuptools wheel
echo "  ✅ pip $(pip --version | awk '{print $2}') ready"

echo ""
echo "Step 5/5: Installing packages..."
echo "  This will take 5-10 minutes..."
echo ""

# Install PyTorch with CUDA first
echo "  🔥 Installing PyTorch with CUDA 11.8..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Install base requirements
echo "  📦 Installing base requirements..."
pip install -r requirements.txt

# Install GPU requirements
echo "  ⚡ Installing GPU requirements..."
pip install -r requirements.gpu.txt

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Migration Complete!"
echo ""
echo "Python version:"
python --version
echo ""
echo "Virtual environment:"
echo "  Location: $VIRTUAL_ENV"
echo ""
echo "Next steps:"
echo "  1. Verify: bash scripts/verify_setup.sh"
echo "  2. Test: pytest tests/ -v"
echo "  3. Run: python src/manage.py runserver"
echo ""
echo "Note: Old Python 3.13 venv backed up to:"
echo "  ~/.venv/fks-trading-py313-backup"
echo "  (Delete when ready: rm -rf ~/.venv/fks-trading-py313-backup)"
