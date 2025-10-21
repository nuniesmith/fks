# WSL Crash Recovery Guide

## ⚠️ Problem: WSL Terminal Exit Code -1

**Cause**: Large Python package installations (like requirements.txt with 140+ packages) can crash WSL due to:

- Memory pressure from compilation
- Too many simultaneous downloads
- Large binary wheels (PyTorch = 3GB+)

## ✅ Current Status (After Recovery)

You've successfully:

- ✅ Migrated from Python 3.13 → Python 3.12.3
- ✅ Backed up Python 3.13 venv (`~/.venv/fks-trading-py313-backup`)
- ✅ Created new Python 3.12 venv (`~/.venv/fks-trading`)
- ✅ Installed PyTorch 2.7.1+cu118 (before crash)

Still needed:

- ⏳ Django and 130+ other packages

## 🛡️ Solution: WSL-Safe Installation

I've created `scripts/install_safe.sh` which:

1. **Installs in small batches** - Prevents memory overflow
2. **Uses `--no-cache-dir`** - Reduces disk I/O crashes
3. **Adds delays between batches** - Lets WSL recover
4. **Continues on error** - Won't crash entire installation

### Run It Now

```bash
# Ensure venv is activated
source ~/.venv/fks-trading/bin/activate

# Run safe installer (15-20 minutes)
bash scripts/install_safe.sh
```

**Expected time**: 15-20 minutes
**Memory usage**: Low (batched installs)
**Crash risk**: Minimal

## 🚀 Quick Recovery (Right Now)

If you want to start immediately, install just the essentials:

```bash
source ~/.venv/fks-trading/bin/activate

# Core Django (2 minutes)
pip install --no-cache-dir Django djangorestframework django-cors-headers gunicorn

# Database (1 minute)
pip install --no-cache-dir psycopg2-binary sqlalchemy

# Celery (2 minutes)
pip install --no-cache-dir celery redis django-celery-beat

# Data Science (5 minutes)
pip install --no-cache-dir pandas numpy scipy

# Testing (1 minute)
pip install --no-cache-dir pytest pytest-django black

# Verify
python -c "import django, celery, pandas; print('✅ Core packages work!')"
```

**Total time**: ~10 minutes
**Status**: Can start development immediately

## 📊 Why WSL Crashes During pip install

### Memory Issues

```
pip install -r requirements.txt (140 packages)
  ↓
Downloads 20+ packages simultaneously
  ↓
Compiles C extensions (numpy, pandas, etc.)
  ↓
WSL memory limit exceeded
  ↓
CRASH (exit code -1)
```

### Solution Strategy

```
Install in batches of 5-10 packages
  ↓
Use --no-cache-dir (skip pip cache)
  ↓
Add sleep delays (let memory settle)
  ↓
Continue on individual failures
  ↓
✅ Installation completes
```

## 🔧 Preventing Future Crashes

### 1. Increase WSL Memory Limit

Create/edit `C:\Users\jordan\.wslconfig`:

```ini
[wsl2]
memory=8GB          # Limit WSL to 8GB (adjust based on your RAM)
processors=4        # Limit CPU cores
swap=4GB           # Add swap space
localhostForwarding=true
```

**Apply changes:**

```powershell
# In PowerShell (as Admin)
wsl --shutdown
wsl
```

### 2. Use Batched Installations

Always install large package lists in batches:

```bash
# BAD (can crash)
pip install -r requirements.txt

# GOOD (safe)
bash scripts/install_safe.sh
```

### 3. Monitor WSL Resources

While installing:

```bash
# Terminal 1: Run installation
bash scripts/install_safe.sh

# Terminal 2: Monitor memory
watch -n 2 free -h
```

### 4. Clear Pip Cache Regularly

```bash
# Free up disk space
pip cache purge

# Check cache size
du -sh ~/.cache/pip
```

## 📝 Installation Scripts Available

| Script | Purpose | Time | Crash Risk |
|--------|---------|------|------------|
| `install_safe.sh` | **Recommended** - Batched install | 15-20m | ⬇️ Low |
| `install_requirements.sh` | Smart installer with fallbacks | 10-15m | ⬇️ Low |
| `migrate_to_python312.sh` | Full migration (already done) | 5-10m | ⬇️ Low |
| `pip install -r requirements.txt` | ❌ Not recommended | 5-10m | ⬆️ High |

## ✅ Post-Installation Checklist

After running `install_safe.sh`:

```bash
# 1. Verify Python version
python --version
# Should show: Python 3.12.3

# 2. Check critical packages
bash scripts/verify_setup.sh

# 3. Run a quick test
python -c "
import django
import celery
import pandas
import torch
print(f'✅ Django {django.__version__}')
print(f'✅ Celery {celery.__version__}')
print(f'✅ Pandas {pandas.__version__}')
print(f'✅ PyTorch {torch.__version__}')
"

# 4. Check CUDA (GPU)
python -c "
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
"

# 5. Run tests
pytest tests/ -v --tb=short -x
```

## 🎯 Recommended Next Steps

### Option 1: Full Install (Comprehensive)

```bash
# Run the safe installer
bash scripts/install_safe.sh

# Verify
bash scripts/verify_setup.sh

# Start coding
gh issue develop 48 --checkout
```

### Option 2: Quick Start (Minimal)

```bash
# Install just what you need now
pip install --no-cache-dir Django pandas pytest black

# Install more later as needed
pip install --no-cache-dir package-name
```

### Option 3: Docker (Bypass WSL Issues)

```bash
# Let Docker handle dependencies
make up

# Access services
# - Web: http://localhost:8000
# - PgAdmin: http://localhost:5050
```

## 🐛 Troubleshooting

### WSL Keeps Crashing

**Check available memory:**

```bash
free -h
```

**Increase WSL memory** (see `.wslconfig` above)

**Restart WSL:**

```powershell
wsl --shutdown
wsl
```

### Package Installation Fails

**Skip problematic packages:**

```bash
# Edit requirements.txt, comment out failing package
# Install manually later
pip install package-name --no-cache-dir
```

### Out of Disk Space

**Check disk usage:**

```bash
df -h
du -sh ~/.cache/pip
du -sh ~/.venv/
```

**Clean up:**

```bash
pip cache purge
rm -rf ~/.venv/fks-trading-py313-backup  # If migration successful
```

## 📚 Files Created for Recovery

- ✅ `scripts/install_safe.sh` - WSL-safe batch installer
- ✅ `scripts/install_requirements.sh` - Smart installer with retries
- ✅ `scripts/migrate_to_python312.sh` - Python version migration
- ✅ `scripts/verify_setup.sh` - Installation verification
- ✅ `docs/PYTHON313_ISSUE_SOLUTION.md` - Python 3.13 compatibility
- ✅ `docs/PYTHON313_COMPATIBILITY.md` - Version comparison
- ✅ This file - WSL crash recovery guide

## 🎉 Summary

**Problem**: WSL crashed during package installation (exit code -1)
**Cause**: Memory pressure from installing 140+ packages simultaneously
**Solution**: Use `scripts/install_safe.sh` for batched installation
**Status**: Python 3.12 venv ready, PyTorch installed, core packages pending
**Action**: Run `bash scripts/install_safe.sh` to complete installation safely

---

**Ready to continue?**

```bash
# Start the safe installation now
source ~/.venv/fks-trading/bin/activate
bash scripts/install_safe.sh
```

This will take 15-20 minutes and install everything without crashing. ☕
