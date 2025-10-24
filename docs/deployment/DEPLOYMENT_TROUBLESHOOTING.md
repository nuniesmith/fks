# Deployment Troubleshooting Guide

## Server IP Resolution Issues

### Problem: "Could not resolve hostname" during deployment

**Error Message:**
```
ssh: Could not resolve hostname : Name or service not known
Error: Process completed with exit code 255.
```

**Root Cause:**
The deployment workflow cannot determine the target server IP address. This happens when:
1. Infrastructure provisioning is skipped (`run_infra != 'true'`)
2. No fallback server IP is configured

### Solutions (in order of preference):

#### Option 1: Set FKS_SERVER_IP Secret (Recommended)
Add a GitHub secret with your existing FKS server IP:

1. Go to your repository's Settings → Secrets and variables → Actions
2. Add a new repository secret:
   - **Name**: `FKS_SERVER_IP`
   - **Value**: Your server's IP address (e.g., `192.168.1.100`)

#### Option 2: Enable Infrastructure Provisioning
If you want to provision a new server each time:
- Set the `run_infra` environment variable to `'true'` in your workflow dispatch

#### Option 3: Use Domain Resolution
The workflow will automatically try to resolve your domain name to an IP address if `DOMAIN_NAME` secret is set.

### Verification Steps

After setting the FKS_SERVER_IP secret, you can verify deployment readiness:

1. **SSH Access Test:**
   ```bash
   ssh actions_user@YOUR_SERVER_IP
   ```

2. **Required Server Setup:**
   - User `actions_user` must exist with sudo privileges
   - User `fks_user` must exist for application deployment
   - Docker must be installed and running
   - Required directories must exist: `/home/fks_user/fks`

3. **Network Requirements:**
   - Server must be accessible on standard SSH port (22)
   - Required ports must be open: 80, 443, 8000, 3000, 9001

### Server Preparation Commands

Run these commands on your target server to prepare for deployment:

```bash
# Create required users
sudo useradd -m -s /bin/bash actions_user
sudo useradd -m -s /bin/bash fks_user

# Set up sudo access for actions_user
sudo usermod -aG sudo actions_user
sudo usermod -aG docker actions_user
sudo usermod -aG docker fks_user

# Create application directory
sudo mkdir -p /home/fks_user/fks
sudo chown fks_user:fks_user /home/fks_user/fks

# Set password for actions_user (use the same password as ACTIONS_USER_PASSWORD secret)
sudo passwd actions_user

# Enable password authentication (if using passwords instead of SSH keys)
sudo sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### Alternative: Using SSH Keys

For better security, you can use SSH keys instead of passwords:

1. Generate SSH keys for GitHub Actions
2. Add the public key to `actions_user`'s authorized_keys
3. Store the private key as a GitHub secret
4. Modify the workflow to use SSH keys instead of sshpass

## Common Deployment Issues

### Issue: Docker not accessible
**Solution:** Add users to docker group and restart docker service

### Issue: Permission denied on /home/fks_user/fks
**Solution:** Ensure proper ownership: `sudo chown -R fks_user:fks_user /home/fks_user/fks`

### Issue: Services fail to start
**Solution:** Check Docker logs: `docker compose logs` in the deployment directory

## Manual Deployment Fallback

If automated deployment fails, you can deploy manually:

1. SSH into your server:
   ```bash
   ssh actions_user@YOUR_SERVER_IP
   ```

2. Switch to fks_user:
   ```bash
   sudo su - fks_user
   cd /home/fks_user/fks
   ```

3. Clone or update the repository:
   ```bash
   git clone https://github.com/nuniesmith/fks.git .
   # or for updates:
   git pull origin main
   ```

4. Run the deployment:
   ```bash
   docker compose down
   docker compose pull
   docker compose up -d
   ```

5. Check service status:
   ```bash
   docker compose ps
   docker compose logs
   ```
