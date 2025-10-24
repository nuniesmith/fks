# Python 3.13 Compatibility Issues

## Problem

Python 3.13 was just released and **many packages don't have wheels yet**:

- ❌ Some numpy/scipy versions
- ❌ Some ML library versions
- ❌ faiss-gpu (no Python 3.13 support)

This causes installation failures.

## Solutions

### Option 1: Use Python 3.12 (Recommended) ✅

Python 3.12 is the current stable production version with full package support.

```bash
# 1. Remove Python 3.13 venv
rm -rf ~/.venv/fks-trading

# 2. Install Python 3.12
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# 3. Create new venv with Python 3.12
python3.12 -m venv ~/.venv/fks-trading

# 4. Activate and install
source ~/.venv/fks-trading/bin/activate
pip install --upgrade pip setuptools wheel

# 5. Install PyTorch with CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# 6. Install all requirements (should work without errors)
pip install -r requirements.txt
pip install -r requirements.gpu.txt
```

### Option 2: Stay with Python 3.13 (Partial Install) ⚠️

Install what's available, skip incompatible packages:

```bash
source ~/.venv/fks-trading/bin/activate

# Use the smart installation script
chmod +x scripts/install_requirements.sh
bash scripts/install_requirements.sh
```

This will:

- Install PyTorch with CUDA first
- Install base requirements (skip failures)
- Install GPU packages individually
- Report what succeeded/failed

### Option 3: Wait for Package Updates 🕐

Python 3.13 support will improve over the next few months as package maintainers release new versions.

Check package compatibility:

- NumPy: https://numpy.org/install/
- SciPy: https://scipy.org/install/
- PyTorch: https://pytorch.org/get-started/locally/

## Recommendation

**Use Python 3.12** for production work right now:

| Version | Status | Recommendation |
|---------|--------|----------------|
| Python 3.13 | ⚠️ Bleeding edge | Wait 3-6 months |
| Python 3.12 | ✅ Production ready | **Use this** |
| Python 3.11 | ✅ Stable | Also good |
| Python 3.10 | ✅ LTS | Conservative choice |

## Quick Fix: Switch to Python 3.12

```bash
# Full script
rm -rf ~/.venv/fks-trading
sudo apt install -y python3.12 python3.12-venv python3.12-dev
python3.12 -m venv ~/.venv/fks-trading
source ~/.venv/fks-trading/bin/activate
pip install --upgrade pip setuptools wheel
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

**Result**: All packages will install without errors. 🎉

## What's Different in Python 3.13?

Major changes causing compatibility issues:

1. **Removed `distutils`** (deprecated in 3.10, removed in 3.13)
2. **New C-API changes** - requires package recompilation
3. **PEP 684** - Per-interpreter GIL (impacts C extensions)
4. **Changed bytecode format** - affects compiled packages

Most ML/data science packages need updates for these changes.

## Current Project Status

- ✅ PyTorch 2.7.1+cu118 installed (Python 3.13 compatible)
- ✅ NumPy 2.3.3 installed (Python 3.13 compatible)
- ❌ Some requirements.txt packages missing wheels
- ❌ faiss-gpu not available for Python 3.13

**Estimated time for full Python 3.13 support**: 3-6 months

## Decision Matrix

| If you need... | Use Python... |
|---------------|---------------|
| Work NOW with no issues | 3.12 |
| Latest features, can debug | 3.13 |
| Production deployment | 3.12 |
| Maximum stability | 3.11 |

**For FKS Trading Platform**: Recommend Python 3.12 until package ecosystem catches up.
