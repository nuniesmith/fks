# Stage 1: Builder
FROM python:3.13-slim AS builder

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    wget \
    build-essential \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Set work directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt .

# Install uv and use it to install dependencies (much faster than pip)
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim

# Set environment variables for runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy TA-Lib libraries from builder
COPY --from=builder /usr/lib/libta_lib.so* /usr/lib/

# Copy Python site-packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy Python executables (celery, gunicorn, etc.) from builder
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Set work directory
WORKDIR /app

# Copy application code
COPY src/ .

EXPOSE 8000

CMD ["gunicorn", "django.wsgi:application", "--bind", "0.0.0.0:8000"]