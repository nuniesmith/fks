# FKS Trading Systems - Docker Images

## Recent Fixes (Latest Update)

### Fixed Docker Registry Issues
- **Problem**: Nginx build was trying to push to separate `fks-nginx` repository
- **Solution**: All images now use single `nuniesmith/fks` repository with descriptive tags
- **Result**: `fks:nginx-latest`, `fks:api-latest`, `fks:worker-latest`, `fks:web-latest`

### Fixed Linode CLI Configuration
- **Problem**: Interactive prompts causing workflow failures
- **Solution**: Non-interactive configuration with proper secrets integration
- **Result**: Automated server provisioning works correctly

### Fixed Docker Compose Configuration
- **Problem**: Conflict between inline nginx config and custom nginx image
- **Solution**: Use custom nginx image with templates, removed inline configuration
- **Result**: Cleaner setup using pre-built nginx configuration

## Available Docker Hub Images

All images are hosted on Docker Hub under `nuniesmith/fks` repository.

### Core Services

| Service | Docker Hub Image | Latest Tag | Purpose |
|---------|------------------|------------|---------|
| API | `nuniesmith/fks:api-latest` | `api` | REST API service |
| Data | `nuniesmith/fks:data-latest` | `data` | Data processing service |
| Worker | `nuniesmith/fks:worker-latest` | `worker` | Background worker service |
| App | `nuniesmith/fks:app-latest` | `app` | Main application service |
| Web | `nuniesmith/fks:web-latest` | `web` | React web interface |

### Ninja Trader Integration

| Service | Docker Hub Image | Latest Tag | Purpose |
|---------|------------------|------------|---------|
| Ninja Dev | `nuniesmith/fks:ninja-dev-latest` | `ninja-dev` | .NET development environment |
| Ninja Python | `nuniesmith/fks:ninja-python-latest` | `ninja-python` | Python trading interface |
| Ninja Build API | `nuniesmith/fks:ninja-build-api-latest` | `ninja-build-api` | Node.js build API |

## Deployment Commands

### Development (using override file)
```bash
# Uses docker-compose.override.yml automatically
docker compose up -d

# Or explicitly
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

### Production
```bash
# Production deployment with resource limits
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Pull Latest Images
```bash
# Pull all latest images
docker compose pull

# Pull specific service
docker compose pull api
```

## Image Tags Available

Each service has multiple tag formats:
- `service-name-latest` (e.g., `api-latest`)
- `service-name` (e.g., `api`)
- `main-service-name` (e.g., `main-api`)
- `service-name-{commit-hash}` (e.g., `api-e08271c`)

## Local Development

To build images locally instead of using Docker Hub:

1. Uncomment the `build` sections in `docker-compose.yml`
2. Comment out or change the `image` lines
3. Run: `docker compose build`

## Environment Variables

Use these environment variables to override default image tags:

```bash
# Core services
export API_IMAGE_TAG=nuniesmith/fks:api-latest
export DATA_IMAGE_TAG=nuniesmith/fks:data-latest
export WORKER_IMAGE_TAG=nuniesmith/fks:worker-latest
export APP_IMAGE_TAG=nuniesmith/fks:app-latest
export WEB_IMAGE_TAG=nuniesmith/fks:web-latest

# Ninja services
export NINJA_DEV_IMAGE_TAG=nuniesmith/fks:ninja-dev-latest
export NINJA_PYTHON_IMAGE_TAG=nuniesmith/fks:ninja-python-latest
export NINJA_BUILD_API_IMAGE_TAG=nuniesmith/fks:ninja-build-api-latest
```

## Benefits of Using Docker Hub Images

1. **Faster Deployments**: No build time, just pull and run
2. **Consistent Environments**: Same images across dev/staging/production
3. **Easier CI/CD**: Images are pre-built and tested
4. **Reduced Resource Usage**: No need to build locally
5. **Version Control**: Tagged images for rollbacks

## Updating Images

When new code is pushed, GitHub Actions automatically:
1. Builds new images
2. Pushes to Docker Hub with latest tags
3. Updates the stackscript deployment

To deploy updates:
```bash
docker compose pull && docker compose up -d
```
