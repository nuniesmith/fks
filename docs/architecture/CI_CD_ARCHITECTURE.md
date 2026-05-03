# CI/CD Architecture - FKS Trading Platform

## Overview

The FKS Trading Platform uses GitHub Actions for automated continuous integration and deployment. This document describes the complete CI/CD pipeline architecture, focusing on the deployment flow to production servers using custom SSH ports.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           GITHUB REPOSITORY                              │
│                                                                          │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐                │
│  │   Push to  │      │  Pull      │      │  Manual    │                │
│  │    main    │──┐   │  Request   │──┐   │  Trigger   │──┐             │
│  └────────────┘  │   └────────────┘  │   └────────────┘  │             │
│                  │                    │                   │             │
│                  └────────────────────┴───────────────────┘             │
│                                      │                                  │
│                                      ▼                                  │
│                          ┌─────────────────────┐                        │
│                          │  GitHub Actions     │                        │
│                          │  Workflow Triggered │                        │
│                          └─────────────────────┘                        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        CI/CD PIPELINE (ci.yml)                           │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 1: Code Quality & Testing                                │    │
│  │                                                                 │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │
│  │  │ Rust Quality │  │ Rust Tests   │  │ Python Tests │         │    │
│  │  │              │  │              │  │              │         │    │
│  │  │ • rustfmt    │  │ • Unit tests │  │ • pytest     │         │    │
│  │  │ • clippy     │  │ • Integration│  │ • Ruff       │         │    │
│  │  │ • build      │  │ • Redis      │  │ • Mypy       │         │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                   │                                     │
│                                   ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 2: Docker Build & Push                                   │    │
│  │                                                                 │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │    │
│  │  │ janus-      │  │ janus-      │  │ janus-      │ ┌────────┐│    │
│  │  │ forward     │  │ backward    │  │ gateway     │ │monitor ││    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ └────────┘│    │
│  │         │                 │                 │           │      │    │
│  │         └─────────────────┴─────────────────┴───────────┘      │    │
│  │                           │                                    │    │
│  │                           ▼                                    │    │
│  │                  ┌─────────────────┐                          │    │
│  │                  │   Docker Hub    │                          │    │
│  │                  │ nuniesmith/fks  │                          │    │
│  │                  └─────────────────┘                          │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                   │                                     │
│                                   ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ STAGE 3: Production Deployment                                 │    │
│  │                                                                 │    │
│  │  ┌──────────────────────────────────────────────────────────┐ │    │
│  │  │ SSH Connection Setup                                     │ │    │
│  │  │                                                          │ │    │
│  │  │  • Server: actions@PROD_IP                              │ │    │
│  │  │  • Port: PROD_PORT (custom, e.g., 2222)                 │ │    │
│  │  │  • Auth: SSH Key (primary) or Password (fallback)       │ │    │
│  │  │  • Key scan: ssh-keyscan -p PROD_PORT                   │ │    │
│  │  └──────────────────────────────────────────────────────────┘ │    │
│  │                           │                                    │    │
│  │                           ▼                                    │    │
│  │  ┌──────────────────────────────────────────────────────────┐ │    │
│  │  │ Deploy Script Upload                                     │ │    │
│  │  │                                                          │ │    │
│  │  │  • scp -P PROD_PORT deploy.sh → /tmp/deploy.sh          │ │    │
│  │  └──────────────────────────────────────────────────────────┘ │    │
│  │                           │                                    │    │
│  │                           ▼                                    │    │
│  │  ┌──────────────────────────────────────────────────────────┐ │    │
│  │  │ Execute Deployment                                       │ │    │
│  │  │                                                          │ │    │
│  │  │  • ssh -p PROD_PORT 'bash /tmp/deploy.sh'               │ │    │
│  │  │  • Pull Docker images from Docker Hub                   │ │    │
│  │  │  • Run docker compose up -d                             │ │    │
│  │  │  • Retrieve Tailscale IP                                │ │    │
│  │  └──────────────────────────────────────────────────────────┘ │    │
│  │                           │                                    │    │
│  │                           ▼                                    │    │
│  │  ┌──────────────────────────────────────────────────────────┐ │    │
│  │  │ Cloudflare DNS Update                                    │ │    │
│  │  │                                                          │ │    │
│  │  │  • Update A record: DNS_NAME → Tailscale IP            │ │    │
│  │  │  • TTL: 120 seconds                                     │ │    │
│  │  │  • Proxied: false                                       │ │    │
│  │  └──────────────────────────────────────────────────────────┘ │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       PRODUCTION SERVER                                  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ SSH Server                                                      │    │
│  │  • Port: PROD_PORT (custom, e.g., 2222)                        │    │
│  │  • User: actions (docker group member)                         │    │
│  │  • Auth: SSH key + password fallback                           │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                   │                                     │
│                                   ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ Docker Services (docker-compose.yml)                           │    │
│  │                                                                 │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │
│  │  │ janus-forward│  │ janus-backward│  │ janus-gateway│         │    │
│  │  │   :50051     │  │   :50052      │  │   :8001      │         │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │    │
│  │                                                                 │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │
│  │  │   monitor    │  │     nginx    │  │     web      │         │    │
│  │  │   :8009      │  │  :80 :443    │  │   :8080      │         │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │    │
│  │                                                                 │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │
│  │  │     redis    │  │ timescaledb  │  │    qdrant    │         │    │
│  │  │   :6379      │  │   :5432      │  │   :6333      │         │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                   │                                     │
│                                   ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ Tailscale Network                                               │    │
│  │  • Provides secure internal IP                                  │    │
│  │  • Used for production access                                   │    │
│  │  • Mapped to DNS via Cloudflare                                 │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## SSH Connection Flow

```
GitHub Actions                Production Server
     │                              │
     │  1. Setup SSH Key            │
     │─────────────────────────────>│
     │                              │
     │  2. ssh-keyscan -p PROD_PORT │
     │─────────────────────────────>│
     │                              │
     │  3. Test Connection          │
     │  ssh -p PROD_PORT            │
     │─────────────────────────────>│
     │                              │
     │  4. Upload deploy.sh         │
     │  scp -P PROD_PORT            │
     │─────────────────────────────>│
     │                              │
     │  5. Execute Deployment       │
     │  ssh -p PROD_PORT            │
     │─────────────────────────────>│
     │                              │
     │                              │ 6. Pull Docker Images
     │                              │    from Docker Hub
     │                              │
     │                              │ 7. Start Services
     │                              │    docker compose up
     │                              │
     │  8. Get Tailscale IP         │
     │<─────────────────────────────│
     │                              │
     │  9. Update Cloudflare DNS    │
     │  (Tailscale IP → DNS Name)   │
     │                              │
```

## Required GitHub Secrets

| Secret Name              | Description                          | Example                    |
|-------------------------|--------------------------------------|----------------------------|
| `PROD_IP`               | Production server IP address         | `203.0.113.42`            |
| `PROD_PORT`             | Custom SSH port                      | `2222`                    |
| `PROD_SSH_KEY`          | Private SSH key for actions user     | `-----BEGIN OPENSSH...`   |
| `PROD_PASSWORD`         | Password (fallback authentication)   | `SecurePassword123!`      |
| `DOCKER_TOKEN`          | Docker Hub access token              | `dckr_pat_...`            |
| `CLOUDFLARE_ZONE_ID`    | Cloudflare zone identifier           | `a1b2c3d4e5f6g7h8...`     |
| `CLOUDFLARE_API_TOKEN`  | Cloudflare API token                 | `Bearer token...`         |
| `CLOUDFLARE_DNS_NAME`   | DNS record to manage                 | `fks.example.com`         |
| `CODECOV_TOKEN`         | Code coverage upload token (optional)| `abc123...`               |

## Deployment Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  SSH Authentication                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Step 1: Try SSH Key Authentication                   │   │
│  │                                                       │   │
│  │  ssh -p PROD_PORT -i ~/.ssh/id_rsa actions@PROD_IP  │   │
│  │                                                       │   │
│  │  Success? ──Yes──> USE_PASSWORD=false                │   │
│  │     │                                                 │   │
│  │     No                                                │   │
│  │     │                                                 │   │
│  │     ▼                                                 │   │
│  │  Set USE_PASSWORD=true                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Step 2: Execute Commands Based on Auth Method        │   │
│  │                                                       │   │
│  │  if USE_PASSWORD=false:                              │   │
│  │      ssh -p PROD_PORT -i ~/.ssh/id_rsa ...           │   │
│  │      scp -P PROD_PORT -i ~/.ssh/id_rsa ...           │   │
│  │  else:                                                │   │
│  │      sshpass -p PASSWORD ssh -p PROD_PORT ...        │   │
│  │      sshpass -p PASSWORD scp -P PROD_PORT ...        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Network Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Internet                                     │
│                                                                  │
│  ┌────────────────┐                      ┌──────────────────┐   │
│  │  GitHub Actions│                      │  Cloudflare DNS  │   │
│  │  Runner        │                      │                  │   │
│  │                │                      │  fks.example.com │   │
│  └────────┬───────┘                      │  → Tailscale IP  │   │
│           │                              └──────────────────┘   │
│           │ SSH (PROD_PORT)                                     │
│           │                                                     │
└───────────┼─────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Production Server (Public IP)                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Firewall                                                  │   │
│  │  • Allow: PROD_PORT/tcp (SSH from anywhere)              │   │
│  │  • Allow: Tailscale VPN                                  │   │
│  │  • Block: All other inbound                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ SSH Server (Port: PROD_PORT)                             │   │
│  │  • Only accessible via custom port                       │   │
│  │  • Used by CI/CD for deployment                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Tailscale Network Interface                              │   │
│  │  • Provides secure internal IP (100.x.x.x)               │   │
│  │  • All production traffic uses this                      │   │
│  │  • Encrypted mesh network                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Docker Services                                           │   │
│  │  • Bound to Tailscale IP only                            │   │
│  │  • Not exposed on public interface                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Tailscale VPN
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                   Authorized Clients                             │
│                                                                  │
│  • Connect via Tailscale network                                │
│  • Access services via fks.example.com (resolves to Tailscale)  │
│  • End-to-end encrypted                                         │
└─────────────────────────────────────────────────────────────────┘
```

## Security Layers

1. **Custom SSH Port (PROD_PORT)**
   - Reduces automated attack surface
   - Not security through obscurity, but reduces noise
   - Requires explicit firewall rule configuration

2. **SSH Key Authentication**
   - Primary authentication method
   - More secure than passwords
   - Stored as GitHub secret (PROD_SSH_KEY)
   - Falls back to password if key fails

3. **Tailscale VPN**
   - All production services behind Tailscale
   - Zero-trust network architecture
   - Services not exposed on public IP
   - End-to-end encryption

4. **Cloudflare DNS**
   - DNS points to Tailscale IP (internal)
   - Only accessible from Tailscale network
   - Provides friendly domain names
   - Low TTL (120s) for quick updates

5. **Docker Network Isolation**
   - Services communicate via internal Docker network
   - Only necessary ports exposed
   - Resource limits and health checks

## CI/CD Workflow Triggers

| Trigger          | Tests | Docker Build | Deploy |
|-----------------|-------|--------------|--------|
| Pull Request    | ✅    | ❌           | ❌     |
| Push to main    | ✅    | ✅           | ✅     |
| Tag push (v*)   | ✅    | ✅           | ✅     |
| Manual dispatch | ⚙️    | ⚙️           | ⚙️     |

*⚙️ = Configurable via workflow inputs*

## Deployment Process Details

### 1. Pre-Deployment Checks
- Verify all tests pass
- Ensure Docker images built successfully
- Validate GitHub secrets are available

### 2. SSH Connection Establishment
```bash
# Add host key to known_hosts
ssh-keyscan -p $PROD_PORT -H $PROD_IP >> ~/.ssh/known_hosts

# Test connection with key
ssh -p $PROD_PORT -i ~/.ssh/id_rsa actions@$PROD_IP 'exit'

# If key fails, fall back to password
sshpass -p "$PROD_PASSWORD" ssh -p $PROD_PORT actions@$PROD_IP
```

### 3. Deployment Script Upload
```bash
# Upload deploy.sh to server
scp -P $PROD_PORT -i ~/.ssh/id_rsa .github/deploy.sh actions@$PROD_IP:/tmp/
```

### 4. Remote Execution
```bash
# Execute deployment on server
ssh -p $PROD_PORT -i ~/.ssh/id_rsa actions@$PROD_IP 'bash /tmp/deploy.sh'

# deploy.sh performs:
# - cd ~/fks
# - git pull (optional)
# - docker compose pull
# - docker compose up -d
# - Extract Tailscale IP
```

### 5. DNS Update
```bash
# Retrieve Tailscale IP from server
TAILSCALE_IP=$(ssh -p $PROD_PORT ... "cat /tmp/deployment_info.txt")

# Update Cloudflare A record
curl -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
  -H "Authorization: Bearer $API_TOKEN" \
  --data '{"content": "$TAILSCALE_IP", "name": "$DNS_NAME"}'
```

### 6. Verification
- Check all services are healthy
- Verify DNS resolution
- Confirm Tailscale connectivity
- Generate deployment summary in GitHub Actions

## Monitoring & Logging

- **Service Logs**: Available via `docker compose logs`
- **Deployment Logs**: GitHub Actions workflow runs
- **Health Checks**: Automatic via Docker healthcheck
- **Metrics**: Prometheus + Grafana (monitor service)

## Rollback Procedure

```bash
# SSH into production server
ssh -p $PROD_PORT actions@$PROD_IP

# Rollback to previous version
cd ~/fks
docker compose down
docker compose pull nuniesmith/fks:janus-forward-PREVIOUS_TAG
docker compose up -d
```

Or trigger re-deployment from a previous commit/tag via GitHub Actions.

## Best Practices

1. ✅ Always use custom SSH port (not 22)
2. ✅ Prefer SSH keys over passwords
3. ✅ Keep secrets in GitHub repository settings
4. ✅ Use Tailscale for production access
5. ✅ Monitor deployment logs
6. ✅ Test deployments in staging first
7. ✅ Use tagged releases for production
8. ✅ Maintain low DNS TTL for quick updates
9. ✅ Enable Docker healthchecks
10. ✅ Regular security updates

## Related Documentation

- [GitHub Secrets Configuration](./GITHUB_SECRETS.md)
- [Production Deployment Checklist](./PRODUCTION_DEPLOYMENT_CHECKLIST.md)
- [Rust Installation Guide](./RUST_INSTALLATION.md)
- [CI/CD Workflow](.github/workflows/ci.yml)
- [Deployment Script](.github/deploy.sh)

---

**Version**: 1.0  
**Last Updated**: 2025-12-24  
**Maintainer**: FKS Platform Team