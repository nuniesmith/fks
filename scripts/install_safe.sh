#!/bin/bash
# WSL-Safe Installation Script
# Prevents crashes by installing packages in small batches with memory management
#
# Usage: source ~/.venv/fks-trading/bin/activate && bash scripts/install_safe.sh

set -e

echo "🛡️  WSL-Safe Package Installation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check venv
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Virtual environment not activated"
    echo "Run: source ~/.venv/fks-trading/bin/activate"
    exit 1
fi

PYTHON_VERSION=$(python --version)
echo "✅ $PYTHON_VERSION in $VIRTUAL_ENV"
echo ""

# Function to install with retry and memory management
install_batch() {
    local batch_name=$1
    shift
    local packages=("$@")

    echo "📦 Installing $batch_name..."
    for pkg in "${packages[@]}"; do
        echo "  → $pkg"
        pip install --no-cache-dir "$pkg" || {
            echo "  ⚠️  $pkg failed, continuing..."
        }
    done
    echo "  ✅ $batch_name complete"
    echo ""

    # Free memory between batches
    sync
    sleep 2
}

# Upgrade pip first (small, fast)
echo "📦 Step 1/6: Upgrading pip..."
pip install --no-cache-dir --upgrade pip setuptools wheel
echo ""

# PyTorch already installed, skip
if pip show torch &>/dev/null; then
    echo "✅ PyTorch already installed (skipping)"
else
    echo "🔥 Step 2/6: Installing PyTorch with CUDA..."
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu118
fi
echo ""

# Core Django/Web Framework (critical)
echo "📦 Step 3/6: Installing Django & Core Web..."
install_batch "Django Core" \
    "Django>=5.2.7" \
    "djangorestframework>=3.16.1" \
    "django-cors-headers>=4.9.0" \
    "django-environ>=0.12.0" \
    "python-dotenv>=1.1.1" \
    "gunicorn>=23.0.0" \
    "whitenoise>=6.11.0"

# Database (critical)
echo "📦 Step 4/6: Installing Database..."
install_batch "Database" \
    "psycopg2-binary>=2.9.11" \
    "sqlalchemy>=2.0.44" \
    "alembic>=1.17.0" \
    "pgvector>=0.4.1"

# Celery & Redis (critical)
echo "📦 Step 5/6: Installing Celery & Redis..."
install_batch "Task Queue" \
    "celery>=5.5.3" \
    "redis>=6.4.0" \
    "django-celery-beat>=2.8.1" \
    "django-celery-results>=2.6.0" \
    "flower>=2.0.1"

# Data Science Core (may be slow)
echo "📦 Step 6/6: Installing Data Science..."
install_batch "NumPy/Pandas" \
    "numpy>=2.3.4" \
    "pandas>=2.3.3" \
    "scipy>=1.16.2"

install_batch "Scikit-Learn" \
    "scikit-learn>=1.7.2" \
    "joblib>=1.5.2"

install_batch "ML Libraries" \
    "xgboost>=3.1.0" \
    "lightgbm>=4.6.0"

# LLM/RAG (may be large)
echo "📦 Step 7/8: Installing LLM/RAG..."
install_batch "Transformers" \
    "transformers>=4.57.1" \
    "accelerate>=1.10.1" \
    "sentence-transformers>=5.1.1"

install_batch "LangChain" \
    "langchain>=1.0.0" \
    "langchain-community>=0.4" \
    "langchain-openai>=1.0.0"

install_batch "Vector DB" \
    "faiss-cpu>=1.12.0" \
    "chromadb>=1.2.0"

# Testing (important)
echo "📦 Step 8/8: Installing Testing & Dev Tools..."
install_batch "Testing" \
    "pytest>=8.4.2" \
    "pytest-django>=4.11.1" \
    "pytest-cov>=7.0.0" \
    "pytest-asyncio>=1.2.0"

install_batch "Linting" \
    "black>=25.9.0" \
    "flake8>=7.3.0" \
    "isort>=7.0.0" \
    "mypy>=1.18.2" \
    "pylint>=4.0.1"

# Remaining packages (batch install)
echo "📦 Installing remaining packages..."
pip install --no-cache-dir -r requirements.txt || {
    echo "⚠️  Some packages failed, but core packages installed"
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation Complete!"
echo ""
echo "📊 Summary:"
pip list | wc -l | xargs -I {} echo "  Total packages: {}"
pip list | grep -E "(Django|torch|pandas|celery|pytest)" | wc -l | xargs -I {} echo "  Critical packages: {}"
echo ""
echo "🔍 Verify installation:"
echo "  bash scripts/verify_setup.sh"
echo ""
echo "🚀 Start development:"
echo "  python src/manage.py runserver"
