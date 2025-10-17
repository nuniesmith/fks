# FKS Trading Systems - run.sh Command Reference

## Overview
The `run.sh` script is a comprehensive orchestrator for the FKS Trading Systems with 40+ commands organized into logical categories. This script serves as both an interactive system manager and a command-line interface perfect for automation workflows.

## Architecture

### Script Structure
- **Main Entry Point**: `/home/${USER}/fks/run.sh`
- **Integration Scripts**: 
  - Main Script: `/home/${USER}/fks/scripts/main.sh`
  - Docker Script: `/home/${USER}/fks/scripts/build/docker.sh`
  - Requirements Script: `/home/${USER}/fks/scripts/build/requirements.sh`
- **Interactive Mode**: Full menu-driven interface
- **Direct Command Mode**: CLI for automation

### Key Features
- ✅ **Error Handling**: Comprehensive error trapping and logging
- ✅ **Service Management**: Built-in Docker Compose orchestration
- ✅ **Docker Hub Integration**: Complete CI/CD pipeline support
- ✅ **Interactive Menus**: User-friendly interface
- ✅ **Workflow Ready**: All commands support automation
- ✅ **Debug Mode**: Toggle-able debug output
- ✅ **Health Checks**: Service monitoring and validation

## Command Categories

### 🔧 System Management Commands
| Command | Description | Workflow Usage |
|---------|-------------|----------------|
| `init` / `initialize` | First-time system setup | CI/CD initialization |
| `status` | Comprehensive system status | Health monitoring |
| `health` | Run health checks | Automated monitoring |
| `setup` | Setup directories and scripts | Environment preparation |
| `update` | Update requirements and rebuild | Maintenance workflows |
| `version` | Show version and component status | Version reporting |

### 🚀 Service Management Commands
| Command | Description | Workflow Usage |
|---------|-------------|----------------|
| `start [services...]` | Start specific services or all | Deployment workflows |
| `stop [services...]` | Stop specific services or all | Maintenance/shutdown |
| `restart [services...]` | Restart specific services | Rolling updates |
| `logs [services...]` | Show service logs | Debugging/monitoring |
| `list-services` | List all available services | Service discovery |

### 🏗️ Build Commands
| Command | Description | Workflow Usage |
|---------|-------------|----------------|
| `build [services...]` | Build services via docker-compose | Development builds |
| `build-images [services...]` | Build Docker images directly | Image creation |
| `generate-dockerfiles` | Generate service Dockerfiles | Template generation |

### 📦 Requirements Management Commands
| Command | Description | Workflow Usage |
|---------|-------------|----------------|
| `generate-requirements` | Generate service requirements | Dependency management |
| `requirements-status` | Show requirements status | Dependency auditing |
| `validate-requirements` | Validate requirements system | Quality assurance |
| `clean-requirements` | Clean requirements files | Cleanup workflows |

### 🐳 Docker Hub Commands (CI/CD Ready)
| Command | Description | Workflow Usage |
|---------|-------------|----------------|
| `docker-hub-status` | Show Docker Hub config/status | Pre-build validation |
| `build-push-all [tag]` | Build and push all services | Release workflows |
| `build-push [--tag <tag>] <services...>` | Build/push specific services | Selective deployments |
| `pull-images [tag] [services...]` | Pull prebuilt images | Environment setup |

### 🚀 Deployment Commands
| Command | Description | Workflow Usage |
|---------|-------------|----------------|
| `deploy [environment] [services...]` | Deploy to environment | Automated deployments |
| `update-env --services <list> --tag <tag> --repo <repo>` | Update .env file | Configuration management |

### 🐋 Docker Management Commands
| Command | Description | Workflow Usage |
|---------|-------------|----------------|
| `docker-status` | Show Docker system status | System monitoring |
| `docker-cleanup [level]` | Clean Docker system | Maintenance workflows |
| `docker-logs [service]` | Show Docker container logs | Debugging |

### 🧹 Cleanup Commands
| Command | Description | Workflow Usage |
|---------|-------------|----------------|
| `clean [basic\|docker\|requirements\|all]` | System cleanup | Maintenance workflows |

## Custom Service Architecture

### Buildable Services (FKS Custom)
The script intelligently identifies and builds only custom FKS services:

1. **nginx** - Web server/reverse proxy
2. **web** - React frontend (fks-web)
3. **api** - FKS API server
4. **worker** - Background task processor
5. **data** - Data service
6. **training** - ML training service (when available)
7. **transformer** - ML transformer service (when available)

### External Services (Not Built)
These services use existing Docker Hub images:
- `postgres`, `redis`
- `authelia-*` (SSO services)
- `adminer`, `redis-commander` (admin tools)
- `netdata` (monitoring)
- `vscode` (development)

## Workflow Integration Examples

### CI/CD Pipeline Usage

#### Basic Build and Deploy Workflow
```bash
# Initialize system
./run.sh init

# Health check
./run.sh health

# Build and push all services with version tag
./run.sh build-push-all v1.2.3

# Deploy to staging
./run.sh deploy staging

# Deploy to production
./run.sh deploy production
```

#### Selective Service Deployment
```bash
# Build and push only API changes
./run.sh build-push --tag hotfix-v1.2.4 api

# Update environment file
./run.sh update-env --services api --tag hotfix-v1.2.4 --repo nuniesmith/fks

# Restart API service only
./run.sh restart api
```

#### Maintenance Workflow
```bash
# System status check
./run.sh status

# Clean system
./run.sh clean docker

# Generate fresh requirements
./run.sh generate-requirements

# Validate everything
./run.sh validate-requirements
```

### GitHub Actions Integration

#### Environment Variables Required
```bash
DOCKER_HUB_USERNAME=nuniesmith
DOCKER_HUB_REPO=fks
FKS_MODE=production
DEBUG=false
```

#### Sample Workflow Steps
```yaml
- name: Build and Push Services
  run: |
    export DOCKER_HUB_USERNAME=${{ secrets.DOCKER_HUB_USERNAME }}
    ./run.sh build-push-all ${{ github.ref_name }}

- name: Deploy to Production
  run: |
    ./run.sh deploy production

- name: Health Check
  run: |
    ./run.sh health
```

## Interactive Mode Features

### Menu Structure (28 Options)
1. **System Management** (1-4): Status, health, setup, update
2. **Service Management** (5-8): Start, stop, restart, logs
3. **Build & Deploy** (9-12): Build services, images, generate files
4. **Requirements** (13-16): Status, list, validate, clean
5. **Docker Management** (17-20): Status, cleanup, logs, shell
6. **Cleanup Options** (21-24): Various cleanup levels
7. **Docker Hub** (25-28): Status, build/push, pull images
8. **Utilities**: Help, debug toggle, version, quit

### Smart Service Selection
- Service discovery from docker-compose.yml
- Multi-service selection with comma separation
- "All services" option
- Back navigation

## Configuration

### Key Paths (Hardcoded)
```bash
PROJECT_ROOT="/home/${USER}/fks"
SCRIPTS_DIR="/home/${USER}/fks/scripts"
CONFIG_DIR="/home/${USER}/fks/config"
COMPOSE_FILE="/home/${USER}/fks/docker-compose.yml"
```

### Docker Hub Configuration
```bash
DOCKER_HUB_USERNAME="${DOCKER_HUB_USERNAME:-nuniesmith}"
DOCKER_HUB_REPO="${DOCKER_HUB_REPO:-fks}"
DOCKER_BUILD_CONTEXT="${DOCKER_BUILD_CONTEXT:-$PROJECT_ROOT}"
```

## Error Handling & Logging

### Logging Levels
- `log_info()` - Informational messages
- `log_warn()` - Warning messages  
- `log_error()` - Error messages (stderr)
- `log_success()` - Success messages with ✅
- `log_debug()` - Debug messages (when DEBUG=true)

### Error Handling
- Global error trap with `handle_error()`
- Graceful failure with cleanup
- Exit code propagation
- User-friendly error messages

## Security & Safety Features

### Validation Checks
- Docker Hub authentication validation
- Script existence verification
- Directory structure validation
- Service availability checks

### Safety Mechanisms
- Interactive confirmation for destructive operations
- Backup creation for .env files
- Emergency reset with confirmation
- Cleanup level selection

## Extensibility

### Adding New Commands
1. Add case in `execute_command()` function
2. Implement command function
3. Add to help system
4. Add interactive menu option (optional)

### Adding New Services
1. Add to docker-compose.yml
2. Services automatically detected by `get_buildable_services()`
3. Add to custom_services array if buildable

## Best Practices for Workflow Usage

### 1. Environment Setup
```bash
# Always start with initialization
./run.sh init

# Verify system status
./run.sh status
```

### 2. Development Workflow
```bash
# Start services for development
./run.sh start api worker data

# Build and test locally
./run.sh build api

# Check logs
./run.sh logs api
```

### 3. Production Deployment
```bash
# Validate Docker Hub config
./run.sh docker-hub-status

# Build and push with version tag
./run.sh build-push-all v1.0.0

# Deploy to production
./run.sh deploy production

# Health check
./run.sh health
```

### 4. Maintenance
```bash
# Regular cleanup
./run.sh clean docker

# Requirements update
./run.sh generate-requirements

# System validation
./run.sh validate-requirements
```

## Conclusion

The `run.sh` script is a production-ready orchestrator that provides:
- **40+ commands** for comprehensive system management
- **Interactive mode** for user-friendly operation
- **CLI mode** perfect for automation and workflows
- **Docker Hub integration** for complete CI/CD pipelines
- **Intelligent service detection** that only builds custom services
- **Robust error handling** and logging
- **Extensible architecture** for future enhancements

This script can serve as the foundation for all FKS system automation, from development workflows to production deployments.
