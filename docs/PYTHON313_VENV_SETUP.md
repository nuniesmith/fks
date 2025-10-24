# Python 3.13 Virtual Environment Setup - Complete ✅

**Date**: October 18, 2025  
**Python Version**: 3.13.8  
**Virtual Environment**: `~/.venv/fks-trading`

---

## ✅ What Was Installed

### 1. Python 3.13.8
```bash
$ python --version
Python 3.13.8
```

### 2. Virtual Environment Location
```
~/.venv/fks-trading  # In Ubuntu home directory (NOT in project)
```

### 3. Installed Packages

#### Core Packages (requirements.txt)
- ✅ **Django 5.2.7** - Web framework
- ✅ **PostgreSQL/SQLAlchemy** - Database
- ✅ **Celery 5.5.3** - Task queue
- ✅ **Redis** - Cache and message broker
- ✅ **pandas, numpy, scipy** - Data science
- ✅ **scikit-learn, xgboost, lightgbm** - Machine learning
- ✅ **langchain, chromadb** - RAG/LLM
- ✅ **streamlit, plotly** - Visualization
- ✅ **pytest, black, mypy** - Testing and linting

#### GPU Packages (requirements.gpu.txt)
- ✅ **PyTorch 2.7.1+cu118** - Deep learning with CUDA 11.8
- ✅ **torchvision 0.22.1+cu118** - Computer vision
- ✅ **CUDA 11.8 libraries** - GPU acceleration
  - nvidia-cuda-nvrtc-cu11
  - nvidia-cuda-runtime-cu11
  - nvidia-cudnn-cu11
  - nvidia-cublas-cu11
  - nvidia-cufft-cu11
  - nvidia-nccl-cu11
- ✅ **transformers** - Hugging Face models
- ✅ **accelerate** - GPU memory optimization
- ✅ **sentence-transformers** - Embeddings (GPU-enabled)
- ✅ **llama-cpp-python** - Local LLM inference
- ✅ **bitsandbytes** - CUDA quantization

**Note**: `faiss-gpu` was skipped (no Python 3.13 support yet) - using `faiss-cpu` from base requirements instead.

---

## 📂 Files Created

### 1. `.venv-activate` (Project Root)
Quick activation helper:
```bash
source .venv-activate
```

### 2. `scripts/install_python313.sh`
Automated Python 3.13 installation script for Ubuntu 24.04

### 3. `scripts/install_gpu_packages.sh`
Automated GPU packages installation script

### 4. `docs/INSTALL_PYTHON_313.md`
Comprehensive Python 3.13 installation guide

---

## 🚀 How to Use

### Activate Virtual Environment
```bash
# Option 1: Use helper script
source .venv-activate

# Option 2: Direct activation
source ~/.venv/fks-trading/bin/activate

# Verify activation
which python
# Should show: /home/jordan/.venv/fks-trading/bin/python
```

### Deactivate Virtual Environment
```bash
deactivate
```

### Verify GPU Support
```bash
source ~/.venv/fks-trading/bin/activate
python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU device: {torch.cuda.get_device_name(0)}')
    print(f'GPU count: {torch.cuda.device_count()}')
"
```

### Run Django Project
```bash
source .venv-activate
cd /mnt/c/Users/jordan/nextcloud/code/repos/fks
python src/manage.py runserver
```

### Run Docker with GPU
```bash
# Start GPU-enabled stack
make gpu-up

# Check logs
make logs

# Access services
# - Web: http://localhost:8000
# - RAG API: http://localhost:8001
# - Grafana: http://localhost:3000
```

---

## 📦 Package Management

### Install New Packages
```bash
source .venv-activate
pip install package-name

# Add to requirements
pip freeze | grep package-name >> requirements.txt
```

### Update Packages
```bash
pip install --upgrade package-name

# Update requirements.txt
pip freeze > requirements-new.txt
# Review and merge into requirements.txt
```

### Rebuild Virtual Environment
```bash
# Delete old venv
rm -rf ~/.venv/fks-trading

# Create new one
python3.13 -m venv ~/.venv/fks-trading

# Activate and install
source ~/.venv/fks-trading/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.gpu.txt
```

---

## ⚠️ Known Issues

### 1. faiss-gpu Not Available for Python 3.13
**Issue**: `faiss-gpu>=1.7.2` doesn't have Python 3.13 wheels yet  
**Solution**: Using `faiss-cpu` from base requirements (still fast for most use cases)  
**Alternative**: Build faiss-gpu from source or wait for official Python 3.13 support

### 2. distutils Deprecated
**Issue**: Python 3.13 removed `distutils` module  
**Solution**: Modern packages use `setuptools` instead (already installed)

### 3. CUDA Availability
**Status**: PyTorch installed with CUDA 11.8 support  
**Check**: Run verification script above to confirm GPU is detected  
**Note**: Requires NVIDIA GPU with CUDA 11.8+ drivers installed on Windows/WSL

---

## 🎯 Next Steps

### 1. Verify Installation
```bash
source .venv-activate
cd /mnt/c/Users/jordan/nextcloud/code/repos/fks

# Run tests
pytest tests/ -v

# Check for import errors
python -c "
from django.conf import settings
import torch
import pandas as pd
import celery
print('✅ All core imports successful')
"
```

### 2. Fix Import Errors (Issue #48)
```bash
# Start fixing legacy imports
gh issue develop 48 --checkout

# Create framework/config/constants.py
# Update imports in affected files
# Run tests after each fix
pytest tests/unit/test_trading/ -v
```

### 3. Start Development
```bash
# Activate venv
source .venv-activate

# Run Django migrations
python src/manage.py migrate

# Start dev server
python src/manage.py runserver

# Or use Docker
make up
```

---

## 📊 Installation Summary

| Component | Version | Status | Notes |
|-----------|---------|--------|-------|
| Python | 3.13.8 | ✅ Installed | Latest stable |
| Venv Location | ~/.venv/fks-trading | ✅ Created | Outside project |
| Base Packages | 140+ | ✅ Installed | All requirements.txt |
| PyTorch | 2.7.1+cu118 | ✅ Installed | CUDA 11.8 support |
| CUDA Libraries | 11.8.x | ✅ Installed | GPU acceleration |
| GPU Packages | 10+ | ✅ Installed | Most from requirements.gpu.txt |
| faiss-gpu | N/A | ⚠️ Skipped | No Python 3.13 support |

---

## 🔧 Troubleshooting

### Virtual Environment Not Activating
```bash
# Check if venv exists
ls -la ~/.venv/fks-trading/

# Recreate if needed
python3.13 -m venv ~/.venv/fks-trading
```

### Import Errors After Installation
```bash
# Ensure venv is activated
source ~/.venv/fks-trading/bin/activate

# Check Python path
which python
# Should be: /home/jordan/.venv/fks-trading/bin/python

# Reinstall package
pip install --force-reinstall package-name
```

### CUDA Not Detected
```bash
# Check NVIDIA drivers
nvidia-smi

# Verify PyTorch CUDA build
python -c "import torch; print(torch.version.cuda)"

# If issues, reinstall PyTorch
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

---

## 📝 VS Code Configuration

Add to `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "/home/jordan/.venv/fks-trading/bin/python",
  "python.terminal.activateEnvironment": true,
  "python.terminal.activateEnvInCurrentTerminal": true
}
```

---

**Status**: ✅ Complete - Ready for development  
**Next**: Fix Issue #48 (import errors) then implement Issue #49 (RAG tasks)

🚀 **Virtual environment is ready! Start coding!**
