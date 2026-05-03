> ⚠️ **ARCHIVED:** Authelia has been removed from FKS. The project now uses Tailscale for authentication. This document is kept for historical reference only.

# Authelia Configuration

## Quick Setup

### 1. Generate Secrets (Automatic)

Run the initialization script to automatically generate all required secrets:

```bash
./scripts/setup/init-authelia.sh
```

This generates four secrets in your `.env` file:
- `AUTHELIA_SESSION_SECRET` — Session encryption (64+ chars)
- `AUTHELIA_STORAGE_ENCRYPTION_KEY` — Storage encryption (64+ chars)
- `AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET` — Password reset JWT (64+ chars)
- `AUTHELIA_POSTGRES_PASSWORD` — Dedicated Authelia PostgreSQL password (40 chars)

To regenerate all secrets (even if they already exist):

```bash
./scripts/setup/init-authelia.sh --force
```

### 2. First-Run Setup

On first launch, the web UI (`/setup`) will prompt you to create an admin account. After creating the initial admin account, you can use the web UI to manage additional accounts.

### 3. Start Authelia

```bash
docker compose -f docker-compose.yml -f infrastructure/compose/docker-compose.prod.yml up -d authelia
```

## Manual Setup

If you prefer to generate secrets manually:

```bash
# Generate individual secrets (64+ chars each)
openssl rand -base64 96 | tr -d '/+\n=' | head -c 64

# Generate the PostgreSQL password (40 chars)
openssl rand -base64 48 | tr -d '/+\n=' | head -c 40
```

Add the output to your `.env` file with the correct variable names.

## Configuration Files

| File | Description |
|------|-------------|
| `infrastructure/config/authelia/configuration.yml` | Main Authelia configuration |
| `infrastructure/config/authelia/users_database.yml` | User accounts and passwords (template) |
| `.env` | Secret keys (auto-generated, **never** commit to git) |

## Default Credentials

⚠️ **IMPORTANT**: The default admin account uses password `ChangeMe123!` — change it immediately!

- **Username:** `admin`
- **Password:** `ChangeMe123!`

To change the password:
1. Generate a new hash:
   ```bash
   ./scripts/setup/generate-user-password.sh 'YourNewPassword!'
   ```
2. Update `infrastructure/config/authelia/users_database.yml` with the new hash
3. Restart Authelia:
   ```bash
   docker compose restart authelia
   ```

## Required Environment Variables

| Variable | Min Length | Description |
|----------|-----------|-------------|
| `AUTHELIA_SESSION_SECRET` | 64 | Encrypts session cookies |
| `AUTHELIA_STORAGE_ENCRYPTION_KEY` | 64 | Encrypts Authelia's PostgreSQL storage |
| `AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET` | 64 | Signs password-reset JWTs |
| `AUTHELIA_POSTGRES_PASSWORD` | — | Password for the dedicated `postgres_auth` database |
| `REDIS_PASSWORD` | — | Shared Redis password (used for session storage) |

## Access Control

| Resource | Required Groups | Auth Level |
|----------|-----------------|------------|
| Setup (`/setup`) | — (bypass) | None |
| Health (`/health`) | — (bypass) | None |
| Auth portal (`auth.fkstrading.xyz`) | — (bypass) | None |
| Web App (`/`) | users, admins | Single Factor |
| API (`/api/*`) | users, admins | Single Factor |
| Grafana (`/grafana/*`) | users, admins | Single Factor |
| Prometheus (`/prometheus/*`) | admins | Two Factor |
| QuestDB (`/questdb/*`) | admins | Two Factor |
| Jaeger (`/jaeger/*`) | admins | Two Factor |
| Admin (`/admin/*`) | admins | Two Factor |
| Execution (`/execution/*`) | traders, admins | Two Factor |
| Dev subdomain (`dev.fkstrading.xyz`) | dev, admins | Two Factor |

## Troubleshooting

### Secrets not working?
- Ensure `.env` file exists and contains all four Authelia secrets
- Check that secrets don't contain `CHANGE_ME` placeholder text
- Verify the three main secrets are at least 64 characters long
- Validate environment variables: `docker compose config | grep AUTHELIA`

### Can't login?
- Verify password hash in `users_database.yml` is correct
- Check Authelia logs: `docker compose logs authelia`
- Ensure Authelia is healthy: `docker compose ps authelia`

### Permission errors?

```bash
./scripts/setup/fix-authelia-permissions.sh
```

This fixes file ownership when Docker creates files as root.

### Reset User Password

```bash
./scripts/setup/generate-user-password.sh 'NewPassword123!'
# Paste the hash into infrastructure/config/authelia/users_database.yml
docker compose restart authelia
```

### Health Check

```bash
docker compose exec authelia wget -q -O - http://localhost:9091/api/health
```
