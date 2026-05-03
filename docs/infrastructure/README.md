---
title: "Infrastructure"
category: "infrastructure"
tags: ["docker", "nginx", "tailscale", "compose"]
---

# Infrastructure Documentation

This directory contains documentation for infrastructure components, including containerization, orchestration, networking, and supporting services.

## Contents

### Container Infrastructure

#### [Docker](docker/)
Complete Docker-related documentation for the FKS platform.

**Key Documents:**
- [Docker Architecture](docker/ARCHITECTURE.md) - Container architecture overview
- [Dockerfile Guide](docker/DOCKERFILE_GUIDE.md) - Best practices for Dockerfiles
- [Docker Quick Start](docker/QUICKSTART.md) - Getting started with Docker
- [Docker Quick Reference](docker/QUICK_REFERENCE.md) - Common Docker commands
- [Compose Checklist](docker/COMPOSE_CHECKLIST.md) - Docker Compose validation
- [Migration Summary](docker/MIGRATION_SUMMARY.md) - Docker migration history

### Configuration Services

#### [Authelia](authelia.md)
Authentication and authorization proxy configuration.

**Features:**
- Single sign-on (SSO)
- Two-factor authentication (2FA)
- Access control policies
- Session management

#### [NGINX](nginx.md)
Reverse proxy and load balancer configuration.

**Features:**
- Request routing
- SSL/TLS termination
- Rate limiting
- Static content serving

#### [Monitoring Configuration](monitoring-config.md)
Prometheus and Grafana monitoring stack configuration.

**Features:**
- Metrics collection
- Dashboard provisioning
- Alert rules
- Service discovery

## Infrastructure Components

### Core Services

```
┌─────────────────────────────────────────────────┐
│              Load Balancer (NGINX)              │
│         SSL Termination & Routing               │
└─────────────────┬───────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
┌────────▼─────┐  ┌────────▼─────────┐
│   Authelia   │  │   Application    │
│     (SSO)    │  │    Services      │
└──────────────┘  └──────────────────┘
                           │
                  ┌────────┴────────┐
                  │                 │
         ┌────────▼─────┐  ┌────────▼─────┐
         │   QuestDB    │  │    Redis     │
         │ (Time-Series)│  │  (Cache/Lock)│
         └──────────────┘  └──────────────┘
```

### Monitoring Stack

```
┌─────────────────────────────────────────────────┐
│                   Grafana                       │
│          Dashboards & Visualization             │
└─────────────────┬───────────────────────────────┘
                  │
         ┌────────▼────────┐
         │   Prometheus    │
         │ Metrics Storage │
         └────────┬────────┘
                  │
         ┌────────┴────────┐
         │                 │
┌────────▼─────┐  ┌────────▼──────────┐
│   Exporters  │  │  Service Metrics  │
│ (Node, etc)  │  │   (/metrics)      │
└──────────────┘  └───────────────────┘
```

## Deployment Environments

### Local Development
- Docker Compose for all services
- Hot-reload enabled where applicable
- Local volume mounts for development
- Simplified authentication

### Home Production
- Docker Compose production stack
- Persistent volumes for data
- Backup automation
- Full monitoring stack
- See: [Home Production Setup](../guides/HOME_PRODUCTION_SETUP.md)

### Cloud Production (Linode/LKE)
- Kubernetes manifests
- StatefulSets for databases
- Horizontal pod autoscaling
- Multi-region capabilities
- See: [Production Deployment](../operations/deployment/PRODUCTION_DEPLOYMENT.md)

## Infrastructure as Code

### Docker Compose Files
Located in project root:
- `docker-compose.yml` - Development stack
- `docker-compose.prod.yml` - Home production stack
- `docker-compose.staging.yml` - Staging environment

### Kubernetes Manifests
Located in service directories:
- `deployment/kubernetes/` - Kubernetes resources
- StatefulSets for stateful services
- ConfigMaps and Secrets
- Service definitions
- Ingress rules

## Networking

### Service Communication
- Internal Docker network for container communication
- Service discovery via Docker DNS
- Port mapping for external access
- NGINX as reverse proxy for HTTP(S) services

### Security
- Private networks for service-to-service communication
- SSL/TLS for external endpoints
- Authelia for authentication
- Network policies (Kubernetes)

### Port Allocation

**Development:**
- 8080: API Gateway
- 8081: Data Service
- 9009: QuestDB ILP
- 9000: QuestDB HTTP
- 6379: Redis
- 9090: Prometheus
- 3000: Grafana

**Production:**
- 443: HTTPS (NGINX)
- 80: HTTP → HTTPS redirect
- Internal services on Docker network only

## Data Persistence

### Volumes

**Development:**
```yaml
questdb_data: ./data/questdb
redis_data: ./data/redis
prometheus_data: ./data/prometheus
grafana_data: ./data/grafana
```

**Production:**
```yaml
questdb_data: /var/lib/fks/questdb
redis_data: /var/lib/fks/redis
prometheus_data: /var/lib/fks/prometheus
grafana_data: /var/lib/fks/grafana
backups: /var/backups/fks
```

### Backup Strategy
- Daily automated backups
- Retention policy (30 days local)
- Offsite backup to Backblaze B2 (optional)
- Database snapshots
- Configuration backups

## Resource Requirements

### Minimum (Development)
- 4GB RAM
- 2 CPU cores
- 20GB disk space

### Recommended (Home Production)
- 8GB RAM
- 4 CPU cores
- 100GB SSD storage
- 1TB for long-term data retention

### Production (Cloud)
- Horizontal scaling based on load
- See: [Capacity Planning Model](../services/data-service/capacity-planning-model.md)

## Configuration Management

### Environment Variables
- `.env.development` - Local development
- `.env.staging` - Staging environment
- `.env.production` - Production (excluded from git)

### Secrets Management
- **Development:** Plain environment variables
- **Staging:** Vault or encrypted secrets
- **Production:** HashiCorp Vault with agent sidecar pattern

### Configuration Files
- Located in `config/` directory
- Environment-specific overrides
- Templating support where needed

## Monitoring & Observability

### Metrics Collection
- Prometheus scrapes `/metrics` endpoints
- Node exporter for host metrics
- Custom exporters (QuestDB)
- Service-specific metrics

### Dashboards
- Grafana dashboards in `config/monitor/grafana/dashboards/`
- Auto-provisioning in production
- Service-level and infrastructure-level views

### Logging
- Structured JSON logging
- Docker log drivers
- Log aggregation (planned)

### Alerting
- Prometheus Alertmanager
- Alert rules in `config/monitor/prometheus/alerts/`
- CNS integration for notifications

## Troubleshooting

### Common Issues
See [Docker Troubleshooting](../operations/infrastructure/DOCKER_TROUBLESHOOTING.md)

### Health Checks
All services expose `/health` endpoints:
- Data Service: `http://localhost:8081/health`
- QuestDB: `http://localhost:9000/`
- Redis: `redis-cli ping`
- Prometheus: `http://localhost:9090/-/healthy`

### Debug Mode
Enable with environment variables:
```bash
RUST_LOG=debug
LOG_LEVEL=debug
```

## Migration Guides

### Docker to Kubernetes
1. Review [Kubernetes manifests](../../deployment/kubernetes/)
2. Adapt ConfigMaps and Secrets
3. Update service discovery endpoints
4. Test in staging environment
5. Follow [Production Deployment Guide](../operations/deployment/PRODUCTION_DEPLOYMENT.md)

### Home to Cloud
See: [Home Production Setup - Migration Section](../guides/HOME_PRODUCTION_SETUP.md#migration-to-cloud)

## Best Practices

### Container Images
- Use multi-stage builds
- Minimal base images (alpine, distroless)
- Layer caching optimization
- Security scanning
- Version tagging (not `latest`)

### Configuration
- Use environment variables for configuration
- Never commit secrets
- Validate configuration on startup
- Document all configuration options

### Networking
- Use internal networks for service communication
- Expose only necessary ports
- Implement rate limiting
- Use TLS for external communication

### Resource Management
- Set resource limits and requests
- Monitor resource usage
- Implement health checks
- Use readiness and liveness probes

## Related Documentation

- [Operations Documentation](../operations/README.md)
- [Deployment Guides](../operations/deployment/)
- [Service Documentation](../services/README.md)
- [Runbooks](../runbooks/README.md)
- [Architecture Overview](../architecture/README.md)

## Quick Links

- [Main Documentation Index](../README.md)
- [Quick Start Guide](../guides/QUICKSTART.md)
- [Home Production Setup](../guides/HOME_PRODUCTION_SETUP.md)
- [Docker Quick Reference](docker/QUICK_REFERENCE.md)