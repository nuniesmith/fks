# Environment Configuration Guide

This guide explains how to configure and use the environment variables for the FKS Trading Systems's dynamic Docker setup.

## Overview

The system uses a comprehensive set of environment variables to configure:
- Build settings for the dynamic Dockerfile
- Service configurations for Docker Compose
- Runtime parameters for all services
- Resource limits and constraints

## Environment Files

### Main Environment File (`.env`)
The primary configuration file containing all available variables with default values. This file serves as both documentation and default configuration.

### Environment-Specific Files
- `.env.development` - Development environment settings
- `.env.production` - Production environment settings  
- `.env.staging` - Staging environment settings
- `.env.testing` - Testing environment settings

### Local Overrides (`.env.local`)
Create this file for local development overrides (git ignored).

## Key Variable Categories

### 1. Build Configuration
Controls how Docker images are built:

```bash
# Build context and versions
BUILD_CONTEXT=.
DOCKERFILE_PATH=./deployment/docker/Dockerfile
PYTHON_VERSION=3.11
RUST_VERSION=1.86.0

# Build flags - enable/disable components
BUILD_PYTHON=true
BUILD_RUST_NETWORK=false
BUILD_RUST_EXECUTION=false
BUILD_CONNECTOR=false
BUILD_DOTNET=false
BUILD_NODE=false

# Build types
BUILD_TYPE_CPU=cpu
BUILD_TYPE_GPU=gpu
SERVICE_RUNTIME=python
```

### 2. Service Configuration
Defines service behavior and networking:

```bash
# Service ports and hosts
API_SERVICE_PORT=8000
API_SERVICE_HOST=0.0.0.0
DATA_SERVICE_PORT=8001
WORKER_SERVICE_PORT=8002

# Service types and modules
API_SERVICE_TYPE=api
API_PYTHON_MODULE=main
```

### 3. Container Configuration
Controls container behavior:

```bash
# Container names
API_CONTAINER_NAME=fks_api
DATA_CONTAINER_NAME=fks_data

# Image tags
API_IMAGE_TAG=nuniesmith/fks:api
DATA_IMAGE_TAG=nuniesmith/fks:data

# Restart policies
API_RESTART_POLICY=unless-stopped
```

### 4. Resource Limits
Sets resource constraints:

```bash
# CPU and memory limits
API_CPU_LIMIT=2
API_MEMORY_LIMIT=2048M
DATA_CPU_LIMIT=2
DATA_MEMORY_LIMIT=2048M
```

### 5. Requirements Files
Specifies Python requirements for different environments:

```bash
# Development
API_REQUIREMENTS_FILE=requirements_dev.txt

# Production
API_REQUIREMENTS_FILE=requirements_prod_docker.txt

# Testing
API_REQUIREMENTS_FILE=requirements_test.txt
```

## Usage Examples

### Development Environment
```bash
# Use default development settings
docker-compose up -d

# Or explicitly specify development environment
docker-compose --env-file .env.development up -d
```

### Production Environment
```bash
# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d
```

### Staging Environment
```bash
# Staging deployment
docker-compose --env-file .env.staging up -d
```

### Testing Environment
```bash
# Testing with minimal resources
docker-compose --env-file .env.testing up -d
```

### Custom Build Configuration

#### Enable Rust Components
```bash
# In your .env.local or environment-specific file
BUILD_RUST_NETWORK=true
BUILD_RUST_EXECUTION=true
BUILD_CONNECTOR=true
```

#### GPU Support
```bash
# Enable GPU builds
BUILD_TYPE_CPU=gpu
BUILD_TYPE_GPU=gpu
GPU_COUNT=1
```

#### Different Python Version
```bash
# Use Python 3.11
PYTHON_VERSION=3.11-slim
```

### Service-Specific Overrides

#### API Service Customization
```bash
API_SERVICE_PORT=9000
API_SERVICE_HOST=127.0.0.1
API_PYTHON_MODULE=api_main
API_REQUIREMENTS_FILE=requirements_api.txt
```

#### Database Configuration
```bash
POSTGRES_MAX_CONNECTIONS=150
POSTGRES_SHARED_BUFFERS=384MB
REDIS_MAXMEMORY=768mb
```

## Advanced Configuration

### External Secrets
For production, use Docker secrets:

```bash
# Enable external secrets
USE_EXTERNAL_SECRETS=true

# Specify secret file paths
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
REDIS_PASSWORD_FILE=/run/secrets/redis_password
SECRET_KEY_FILE=/run/secrets/secret_key
```

### Custom Requirements Files
Create environment-specific requirements:

```bash
# Development with debug tools
API_REQUIREMENTS_FILE=requirements_dev_api.txt
APP_REQUIREMENTS_FILE=requirements_dev_app.txt

# Production optimized
API_REQUIREMENTS_FILE=requirements_prod_optimized.txt
```

### Resource Optimization

#### Memory Constrained Environment
```bash
API_MEMORY_LIMIT=512M
DATA_MEMORY_LIMIT=512M
WORKER_MEMORY_LIMIT=512M
POSTGRES_SHARED_BUFFERS=64MB
REDIS_MAXMEMORY=128mb
```

#### High Performance Environment
```bash
API_CPU_LIMIT=8
API_MEMORY_LIMIT=8192M
DATA_CPU_LIMIT=8
DATA_MEMORY_LIMIT=8192M
POSTGRES_MAX_CONNECTIONS=500
POSTGRES_SHARED_BUFFERS=2GB
REDIS_MAXMEMORY=4gb
```

## Validation

Validate your configuration:

```bash
# Check environment variables
docker-compose config

# Validate specific service
docker-compose config api

# Check environment file loading
docker-compose --env-file .env.production config
```

## Troubleshooting

### Common Issues

1. **Missing environment variables**: Check that all required variables are set in your environment file.

2. **Build failures**: Ensure build flags match your source code structure:
   ```bash
   BUILD_PYTHON=true  # if you have Python code
   BUILD_RUST_NETWORK=true  # if you have Rust network code
   ```

3. **Resource limits**: Adjust based on available system resources:
   ```bash
   # For low-memory systems
   API_MEMORY_LIMIT=512M
   POSTGRES_SHARED_BUFFERS=64MB
   ```

4. **Port conflicts**: Change service ports if defaults are in use:
   ```bash
   API_SERVICE_PORT=9000
   DATA_SERVICE_PORT=9001
   ```

### Debug Commands

```bash
# Show resolved configuration
docker-compose config

# Show environment variables for a service
docker-compose exec api env | grep -E "APP_|SERVICE_|BUILD_"

# Check build arguments
docker-compose config api | grep -A 20 "build:"
```

## Best Practices

1. **Use environment-specific files**: Don't modify the main `.env` file for deployment-specific settings.

2. **Override in layers**: Use the base `.env` + environment-specific file + local overrides pattern.

3. **Validate before deployment**: Always run `docker-compose config` before deploying.

4. **Secure secrets**: Use Docker secrets or external secret management for production.

5. **Resource monitoring**: Start with conservative resource limits and adjust based on monitoring.

6. **Version pinning**: Pin specific versions for production deployments.

## Security Considerations

- Never commit actual secrets to version control
- Use strong passwords for production databases
- Enable SSL/TLS for production deployments
- Regularly rotate secrets and passwords
- Monitor resource usage to prevent DoS
