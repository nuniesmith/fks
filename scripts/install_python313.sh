#!/bin/bash
# Install Python 3.13 on Ubuntu 24.04
# Run with: bash install_python313.sh

set -e  # Exit on error

echo "🐍 Installing Python 3.13 on Ubuntu 24.04..."
echo ""

# Update package lists
echo "📦 Updating package lists..."
sudo apt update

# Add deadsnakes PPA (provides newer Python versions)
echo "➕ Adding deadsnakes PPA..."
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Install Python 3.13 and related packages
echo "⬇️  Installing Python 3.13..."
sudo apt install -y \
    python3.13 \
    python3.13-venv \
    python3.13-dev

# Verify installation
echo ""
echo "✅ Verifying installation..."
python3.13 --version

# Optional: Set Python 3.13 as alternative (doesn't change default)
echo ""
echo "🔧 Configuring update-alternatives..."
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 2

echo ""
echo "✨ Python 3.13 installed successfully!"
echo ""
echo "To use Python 3.13:"
echo "  - Run: python3.13"
echo "  - Create venv: python3.13 -m venv ~/.venv/fks-trading-py313"
echo ""
echo "To switch default python3 version:"
echo "  sudo update-alternatives --config python3"
echo ""
