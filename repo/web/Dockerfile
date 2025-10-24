# FKS Web - Django/Vite Web UI Dockerfile
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js for Vite
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    wget \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Django
RUN pip install --no-cache-dir django>=5.2.7

# Copy application code
COPY src/ ./src/

# Copy static files and templates
COPY static/ ./static/ 2>/dev/null || true
COPY templates/ ./templates/ 2>/dev/null || true

# Install Node.js dependencies for Vite (if package.json exists)
COPY package.json package-lock.json* ./ 2>/dev/null || true
RUN if [ -f package.json ]; then npm install; fi

# Collect static files
RUN if [ -f src/manage.py ]; then python src/manage.py collectstatic --noinput; fi || true

# Expose port
EXPOSE 3001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
  CMD curl -f http://localhost:3001/ || exit 1

# Run Django development server
CMD ["python", "src/manage.py", "runserver", "0.0.0.0:3001"]
