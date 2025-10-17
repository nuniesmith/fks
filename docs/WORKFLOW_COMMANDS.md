# FKS run.sh - Workflow Command Summary

## Command Categories for Automation

### System Commands
- `init` - Initialize system
- `status` - System status
- `health` - Health check
- `setup` - Setup directories
- `update` - Update system

### Service Management
- `start [services...]` - Start services
- `stop [services...]` - Stop services  
- `restart [services...]` - Restart services
- `logs [services...]` - View logs
- `list-services` - List available services

### Build Operations
- `build [services...]` - Build via compose
- `build-images [services...]` - Build Docker images
- `generate-dockerfiles` - Generate Dockerfiles

### Requirements Management
- `generate-requirements` - Generate requirements
- `requirements-status` - Show status
- `validate-requirements` - Validate system
- `clean-requirements` - Clean files

### Docker Hub Operations (CI/CD)
- `docker-hub-status` - Show config/status
- `build-push-all [tag]` - Build/push all services
- `build-push [--tag <tag>] <services...>` - Build/push specific
- `pull-images [tag] [services...]` - Pull images

### Deployment
- `deploy [environment] [services...]` - Deploy to env
- `update-env --services <list> --tag <tag> --repo <repo>` - Update env

### Docker Management
- `docker-status` - Docker system status
- `docker-cleanup [level]` - Docker cleanup
- `docker-logs [service]` - Container logs

### Cleanup
- `clean [basic|docker|requirements|all]` - System cleanup

## FKS Custom Services

Only these services are built as Docker images:
1. **nginx** - Web server
2. **web** - React frontend  
3. **api** - API server
4. **worker** - Background processor
5. **data** - Data service
6. **training** - ML training (future)
7. **transformer** - ML transformer (future)

External services (not built): postgres, redis, authelia-*, adminer, redis-commander, netdata, vscode

## Key Workflow Examples

### CI/CD Pipeline
```bash
./run.sh init
./run.sh build-push-all v1.0.0
./run.sh deploy production
./run.sh health
```

### Development
```bash
./run.sh start api worker data
./run.sh build api
./run.sh logs api
```

### Maintenance
```bash
./run.sh clean docker
./run.sh generate-requirements
./run.sh validate-requirements
```

## Environment Variables

Required for Docker Hub operations:
- `DOCKER_HUB_USERNAME=nuniesmith`
- `DOCKER_HUB_REPO=fks`
- `FKS_MODE=production`
- `DEBUG=false`

## Usage Modes

1. **Interactive**: `./run.sh` (menu-driven)
2. **Direct Commands**: `./run.sh <command> [args]`
3. **Help**: `./run.sh help`
4. **Debug**: `./run.sh --debug <command>`
