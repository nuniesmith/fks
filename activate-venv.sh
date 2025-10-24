#!/bin/bash
# FKS Trading Platform - Virtual Environment Activation Script
# Usage: source activate-venv.sh

echo "🐍 Activating FKS Trading Platform virtual environment..."

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Creating it now..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
fi

# Activate the virtual environment
source .venv/bin/activate

# Verify activation
echo "✅ Virtual environment activated!"
echo "📍 Python: $(which python3)"
echo "📦 Pip: $(python3 -m pip --version)"
echo ""
echo "💡 To install dependencies, run:"
echo "   python3 -m pip install -r requirements.txt"
echo ""
echo "💡 To deactivate, run:"
echo "   deactivate"
