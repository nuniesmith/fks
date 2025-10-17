#!/bin/bash

# Setup script for ML Phase 3 - GPU Acceleration
# This script helps configure CUDA and train ML models

set -e

echo "================================================"
echo "ML INTELLIGENCE SETUP - PHASE 3"
echo "================================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if CUDA is available
print_info "Checking for CUDA..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
    CUDA_AVAILABLE=1
    print_info "✅ CUDA is available!"
else
    print_warn "⚠️  CUDA not detected. ML will run on CPU (slower)."
    CUDA_AVAILABLE=0
fi

# Check Python version
print_info "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_info "Python version: $PYTHON_VERSION"

# Install ML dependencies
print_info "Installing ML dependencies..."

if [ $CUDA_AVAILABLE -eq 1 ]; then
    print_info "Installing PyTorch with CUDA support..."
    
    # Detect CUDA version
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}' | cut -d. -f1,2)
    print_info "Detected CUDA version: $CUDA_VERSION"
    
    if [[ "$CUDA_VERSION" == "11.8" ]]; then
        pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
    elif [[ "$CUDA_VERSION" == "12."* ]]; then
        pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
    else
        print_warn "Unknown CUDA version, installing default PyTorch"
        pip install torch torchvision
    fi
else
    print_info "Installing PyTorch (CPU version)..."
    pip install torch torchvision
fi

# Install other ML dependencies
print_info "Installing other ML packages..."
pip install hmmlearn scikit-learn joblib scipy xgboost lightgbm

# Verify installations
print_info "Verifying installations..."

python3 << EOF
import sys

print("\n" + "="*60)
print("VERIFICATION RESULTS")
print("="*60)

# Check PyTorch
try:
    import torch
    print(f"✅ PyTorch: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA version: {torch.version.cuda}")
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print(f"   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
except ImportError:
    print("❌ PyTorch not installed")
    sys.exit(1)

# Check HMM
try:
    from hmmlearn import hmm
    print(f"✅ hmmlearn: Available")
except ImportError:
    print("❌ hmmlearn not installed")
    sys.exit(1)

# Check scikit-learn
try:
    import sklearn
    print(f"✅ scikit-learn: {sklearn.__version__}")
except ImportError:
    print("❌ scikit-learn not installed")
    sys.exit(1)

# Check other packages
try:
    import scipy
    print(f"✅ scipy: {scipy.__version__}")
except ImportError:
    print("⚠️  scipy not installed (optional)")

try:
    import xgboost
    print(f"✅ xgboost: {xgboost.__version__}")
except ImportError:
    print("⚠️  xgboost not installed (optional)")

print("="*60 + "\n")
EOF

print_info "✅ All required packages installed!"

# Create directories
print_info "Creating required directories..."
mkdir -p ./models
mkdir -p ./logs

# Check if database is ready
print_info "Checking database connection..."
python3 << EOF
from database import Session

try:
    session = Session()
    print("✅ Database connection successful")
    session.close()
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    print("   Make sure PostgreSQL is running (docker-compose up -d)")
    exit(1)
EOF

# Offer to train models
print_info ""
read -p "Do you want to train ML models now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Starting ML model training..."
    print_info "This may take 10-30 minutes depending on your hardware..."
    
    python3 src/ml_training_pipeline.py
    
    if [ $? -eq 0 ]; then
        print_info "✅ Model training successful!"
    else
        print_error "❌ Model training failed. Check logs above."
    fi
fi

# Final instructions
print_info ""
print_info "================================================"
print_info "SETUP COMPLETE!"
print_info "================================================"
print_info ""
print_info "Next steps:"
print_info "1. Start the ML-enhanced app:"
print_info "   streamlit run src/app_ml.py"
print_info ""
print_info "2. Generate daily recommendations:"
print_info "   python src/daily_trading_engine.py"
print_info ""
print_info "3. View market regimes in the web interface"
print_info ""
print_info "For more information, see PHASE3_ML_INTELLIGENCE.md"
print_info ""
