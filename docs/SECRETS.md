# FKS GitHub Secrets Configuration

This document maps the GitHub secrets to their usage in the FKS deployment system.

## Required Secrets

### Core Deployment Secrets
| Secret Name | Purpose | Used In |
|-------------|---------|---------|
| `LINODE_CLI_TOKEN` | Linode API access token | Stage 0 (server creation) |
| `FKS_DEV_ROOT_PASSWORD` | Root password for new Linode servers | Stage 0, Stage 1 |
| `JORDAN_PASSWORD` | Password for jordan user | Stage 1 |
| `FKS_USER_PASSWORD` | Password for fks_user | Stage 1 |
| `TAILSCALE_AUTH_KEY` | Tailscale VPN authentication key | Stage 1, Stage 2 |

### Optional Service Secrets
| Secret Name | Purpose | Used In |
|-------------|---------|---------|
| `DOCKER_USERNAME` | Docker Hub username | Stage 1 (Docker authentication) |
| `DOCKER_TOKEN` | Docker Hub access token | Stage 1, GitHub Actions |
| `NETDATA_CLAIM_TOKEN` | Netdata Cloud claim token | Stage 1 |
| `NETDATA_CLAIM_ROOM` | Netdata Cloud room ID | Stage 1 |

### SSH Public Keys
| Secret Name | Purpose | User Account |
|-------------|---------|-------------|
| `ACTIONS_ACTIONS_JORDAN_SSH_PUB` | Jordan's SSH public key | jordan |
| `ACTIONS_FKS_SSH_PUB` | FKS User SSH public key | fks_user |
| `ACTIONS_ROOT_SSH_PUB` | Root SSH public key | root |
| `ACTIONS_USER_SSH_PUB` | GitHub Actions SSH public key | actions_user |

### Private Key (for GitHub repository access)

| Secret Name | Purpose | Notes |
|-------------|---------|-------|
| `ACTIONS_ROOT_PRIVATE_KEY` | SSH private key for cloning private GitHub repositories | Used by GitHub Actions to authenticate git clone operations on the remote server |

### Notification Webhooks
| Secret Name | Purpose | Used In |
|-------------|---------|---------|
| `DISCORD_WEBHOOK_SERVERS` | Discord webhook for server notifications | GitHub Actions |
| `DISCORD_WEBHOOK_SIGNALS` | Discord webhook for signals | Application (if needed) |

## Secret Configuration Examples

### SSH Key Generation
To generate the SSH keys that correspond to your secrets:

```bash
# Generate keys for each user
ssh-keygen -t ed25519 -f jordan_id_ed25519 -N "" -C "jordan@fks"
ssh-keygen -t ed25519 -f github_actions_id_ed25519 -N "" -C "github_actions_user@fks"
ssh-keygen -t ed25519 -f root_id_ed25519 -N "" -C "root@fks"
ssh-keygen -t ed25519 -f fks_user_id_ed25519 -N "" -C "fks_user@fks"

# Set GitHub secrets with the public keys:
# ACTIONS_ACTIONS_JORDAN_SSH_PUB = contents of jordan_id_ed25519.pub
# ACTIONS_FKS_SSH_PUB = contents of github_actions_id_ed25519.pub
# ACTIONS_ROOT_SSH_PUB = contents of root_id_ed25519.pub
# ACTIONS_USER_SSH_PUB = contents of fks_user_id_ed25519.pub

# Set private key for GitHub Actions access:
# ACTIONS_ROOT_PRIVATE_KEY = contents of github_actions_id_ed25519 (private key)
```

### Tailscale Auth Key
1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/machines)
2. Generate a new auth key
3. Set `TAILSCALE_AUTH_KEY` secret with the generated key

### Docker Hub Token
1. Go to [Docker Hub Account Settings](https://hub.docker.com/settings/security)
2. Create a new access token
3. Set `DOCKER_USERNAME` and `DOCKER_TOKEN` secrets

### Linode API Token
1. Go to [Linode Cloud Manager API Tokens](https://cloud.linode.com/profile/tokens)
2. Create a new personal access token with Linodes read/write permissions
3. Set `LINODE_CLI_TOKEN` secret

### Netdata Cloud (Optional)
1. Go to [Netdata Cloud](https://app.netdata.cloud/)
2. Create a space and get claim token
3. Set `NETDATA_CLAIM_TOKEN` and `NETDATA_CLAIM_ROOM` secrets

### Discord Webhooks (Optional)
1. Create a Discord webhook in your server
2. Set `DISCORD_WEBHOOK_SERVERS` secret with the webhook URL

## Deployment Environment Mapping

The GitHub Actions workflow maps these secrets to environment variables:

```bash
# Core secrets
LINODE_CLI_TOKEN=${{ secrets.LINODE_CLI_TOKEN }}
FKS_DEV_ROOT_PASSWORD=${{ secrets.FKS_DEV_ROOT_PASSWORD }}
JORDAN_PASSWORD=${{ secrets.JORDAN_PASSWORD }}
FKS_USER_PASSWORD=${{ secrets.FKS_USER_PASSWORD }}
TAILSCALE_AUTH_KEY=${{ secrets.TAILSCALE_AUTH_KEY }}

# Service secrets
DOCKER_USERNAME=${{ secrets.DOCKER_USERNAME }}
DOCKER_TOKEN=${{ secrets.DOCKER_TOKEN }}
NETDATA_CLAIM_TOKEN=${{ secrets.NETDATA_CLAIM_TOKEN }}
NETDATA_CLAIM_ROOM=${{ secrets.NETDATA_CLAIM_ROOM }}

# SSH keys
ACTIONS_JORDAN_SSH_PUB=${{ secrets.ACTIONS_ACTIONS_JORDAN_SSH_PUB }}
ACTIONS_USER_SSH_PUB=${{ secrets.ACTIONS_FKS_SSH_PUB }}
ACTIONS_ROOT_SSH_PUB=${{ secrets.ACTIONS_ROOT_SSH_PUB }}
ACTIONS_FKS_SSH_PUB=${{ secrets.ACTIONS_USER_SSH_PUB }}
```

## Security Notes

1. **Private Key Security**: The `ACTIONS_ROOT_PRIVATE_KEY` should be the private key corresponding to one of the public keys (typically `ACTIONS_FKS_SSH_PUB`)

2. **Password Security**: Use strong, unique passwords for `JORDAN_PASSWORD` and `FKS_USER_PASSWORD`

3. **Tailscale Security**: The deployment configures Tailscale with "shields up" mode for enhanced security

4. **Key Rotation**: Regularly rotate SSH keys and API tokens for security

5. **Least Privilege**: Each service only gets access to the secrets it needs

## Validation

You can validate your secret configuration by running the GitHub Actions workflow. It will check for missing required secrets and fail early if any are missing.
