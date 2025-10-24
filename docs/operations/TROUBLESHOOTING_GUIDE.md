# FKS Trading Systems - Troubleshooting Guide

## 🔍 **COMMON DEPLOYMENT ISSUES**

### **Docker Startup Failures**

#### **Problem**: Docker fails to start with overlay filesystem errors
```
Error: failed to mount overlay: no such device
```

**Solution for Arch Linux:**
```bash
# Configure Docker to use VFS storage driver
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json << EOF
{
  "storage-driver": "vfs",
  "iptables": false,
  "ip-masq": false
}
EOF

sudo systemctl restart docker
```

**Solution for Ubuntu/Debian:**
```bash
# Install overlay kernel module
sudo modprobe overlay
echo 'overlay' | sudo tee -a /etc/modules

# Restart Docker
sudo systemctl restart docker
```

#### **Problem**: Docker service won't start after reboot
```bash
# Check Docker status
sudo systemctl status docker

# Check Docker logs
journalctl -u docker.service -n 20

# Restart Docker with verbose logging
sudo dockerd --debug

# Quick fix - restart Docker
sudo systemctl restart docker
```

### **User Permission Issues**

#### **Problem**: "sudo: unknown user ninja" during setup
**Root Cause**: SSH setup attempted before user creation

**Solution 1 - Quick Fix Script:**
```bash
# Download and run the quick fix
curl -fsSL https://raw.githubusercontent.com/nuniesmith/ninja/main/scripts/stackscript-quickfix.sh -o quickfix.sh
chmod +x quickfix.sh

# Set your parameters
export NINJA_PASSWORD="your_secure_password"
export SSH_KEY="your_ssh_public_key_here"

# Run the fix
sudo ./quickfix.sh
```

**Solution 2 - Manual Fix:**
```bash
# Create the ninja user
sudo useradd -m -s /bin/bash ninja
echo "ninja:your_password" | sudo chpasswd

# Add to correct groups (Arch Linux uses 'wheel', others use 'sudo')
sudo usermod -aG sudo ninja    # Ubuntu/Debian
sudo usermod -aG wheel ninja   # Arch Linux
sudo usermod -aG docker ninja

# Set up SSH key
sudo -u ninja mkdir -p /home/ninja/.ssh
echo "your_ssh_public_key" | sudo -u ninja tee /home/ninja/.ssh/authorized_keys
sudo -u ninja chmod 600 /home/ninja/.ssh/authorized_keys
sudo -u ninja chmod 700 /home/ninja/.ssh
```

### **Network and Firewall Issues**

#### **Problem**: Cannot access web interfaces
**Symptoms**: Connection refused on ports 3000, 8002, 8081, 6080

**Check firewall status:**
```bash
# Ubuntu/Debian
sudo ufw status

# RHEL/CentOS
sudo firewall-cmd --list-all

# If blocked, allow the ports
sudo ufw allow 3000  # Trading interface
sudo ufw allow 8002  # Python API
sudo ufw allow 8081  # VS Code server
sudo ufw allow 6080  # VNC web
```

**Check services are running:**
```bash
# Check if services are listening
sudo netstat -tlnp | grep -E '(3000|8002|8081|6080|5900)'

# Check Docker containers
docker-compose ps

# Restart services if needed
docker-compose restart
```

### **SSH Connection Problems**

#### **Problem**: SSH connection refused or authentication failure

**Check SSH service:**
```bash
# Check if SSH is running
sudo systemctl status ssh     # Ubuntu/Debian
sudo systemctl status sshd    # RHEL/CentOS/Arch

# Restart SSH if needed
sudo systemctl restart ssh
```

**Check SSH configuration:**
```bash
# Verify SSH config
sudo sshd -T | grep -E "(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication)"

# Should show:
# PermitRootLogin no
# PasswordAuthentication no (if using keys)
# PubkeyAuthentication yes
```

**Test SSH key authentication:**
```bash
# Test from local machine
ssh -v ninja@YOUR_IP

# Check authorized_keys on server
ls -la /home/ninja/.ssh/
cat /home/ninja/.ssh/authorized_keys
```

---

## 🐛 **GITHUB ACTIONS ISSUES**

### **Tailscale Connection Failures**

#### **Problem**: GitHub Actions can't connect to Tailscale
```
Error: Failed to authenticate with Tailscale
```

**Check OAuth client configuration:**
1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin)
2. Navigate to **Settings** → **OAuth clients**
3. Verify client has correct scopes: `devices:write` and `all:read`
4. Verify tag: `tag:ci-cd`
5. Regenerate client secret if needed

**Check GitHub secrets:**
```bash
# Verify secrets are set in GitHub repository
# Settings → Secrets and variables → Actions → Repository secrets
TAILSCALE_OAUTH_CLIENT_ID
TAILSCALE_OAUTH_SECRET
NINJA_SSH_PRIVATE_KEY
```

### **SSH Authentication Failures**

#### **Problem**: GitHub Actions can't SSH to server
```
Error: Permission denied (publickey)
```

**Solution:**
```bash
# Generate new SSH key for CI/CD
ssh-keygen -t ed25519 -f ~/.ssh/ninja-ci-cd -N ""

# Copy public key to server
ssh-copy-id -i ~/.ssh/ninja-ci-cd.pub ninja@YOUR_SERVER_IP

# Update GitHub secret with private key content
cat ~/.ssh/ninja-ci-cd  # Copy this to NINJA_SSH_PRIVATE_KEY secret
```

### **Deployment Script Failures**

#### **Problem**: Deployment fails with "command not found"
**Check PATH and environment:**
```bash
# SSH into server and check
ssh ninja@YOUR_SERVER

# Check if tools are installed
which docker
which docker-compose
which git

# Check environment
echo $PATH
```

---

## ⚙️ **SYSTEM CONFIGURATION ISSUES**

### **Stage 2 Service Not Running**

#### **Problem**: Stage 2 deployment doesn't run after reboot
**Check systemd service:**
```bash
# Check if Stage 2 service exists
sudo systemctl status ninja-stage2

# Check logs
journalctl -u ninja-stage2 -n 50

# Manually run Stage 2 if needed
sudo /usr/local/bin/ninja-stage2.sh
```

### **Repository Cloning Issues**

#### **Problem**: Git clone fails with authentication error
```bash
# Check GitHub token has correct permissions
curl -H "Authorization: token YOUR_GITHUB_TOKEN" https://api.github.com/user

# Manual clone test
cd /home/ninja
git clone https://YOUR_TOKEN@github.com/nuniesmith/ninja.git

# Fix ownership if needed
sudo chown -R ninja:ninja /home/ninja/ninja
```

### **Environment Configuration Problems**

#### **Problem**: Services can't find configuration files
**Check configuration paths:**
```bash
# Verify configuration exists
ls -la /etc/ninja-trading/
cat /etc/ninja-trading/deployment-config.json

# Check environment file
cat /opt/ninja-trading/.env

# Verify permissions
sudo chown -R ninja:ninja /opt/ninja-trading/
```

---

## 🔧 **STRATEGY DEVELOPMENT ISSUES**

### **NinjaTrader Compilation Errors**

#### **Problem**: Strategy won't compile in NinjaTrader
**Common issues:**
```csharp
// Missing using statements
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Indicator;

// Incorrect namespace
namespace NinjaTrader.NinjaScript.Strategies
{
    public class FKS_Strategy_Clean : Strategy
    {
        // Strategy code
    }
}
```

**Check references:**
```xml
<!-- Ensure proper references in .csproj -->
<Reference Include="NinjaTrader.Core" />
<Reference Include="NinjaTrader.Custom" />
<Reference Include="NinjaTrader.Gui" />
```

### **Indicator Dependencies Missing**

#### **Problem**: Strategy can't find custom indicators
**Solution:**
```bash
# Copy all FKS AddOns to NinjaTrader
cp src/AddOns/*.cs "$env:USERPROFILE\Documents\NinjaTrader 8\bin\Custom\AddOns\"

# Compile AddOns first, then strategy
# In NinjaTrader: Tools → Edit NinjaScript → Compile
```

### **Signal Quality Issues**

#### **Problem**: Poor signal quality or too many/few signals
**Debug signal generation:**
```csharp
// Add debug output to strategy
Print($"Signal Quality: {signalQuality:F2}, " +
      $"EMA: {ema9[0]:F2}, " +
      $"VWAP: {vwap[0]:F2}, " +
      $"AO: {ao[0]:F2}");

// Check thresholds
if (signalQuality < SignalThreshold)
{
    Print($"Signal rejected: Quality {signalQuality:F2} < {SignalThreshold}");
}
```

---

## 🚨 **EMERGENCY PROCEDURES**

### **System Recovery**

#### **Complete system failure - can't access server**
```bash
# Use Linode console (Lish) to access system
# From Linode Cloud Manager → Select your Linode → Launch Lish Console

# Check system status
systemctl status
df -h
free -h

# Restart critical services
systemctl restart docker
systemctl restart nginx
systemctl restart ninja-trading
```

#### **Service rollback**
```bash
# Quick rollback to previous version
cd /home/ninja/ninja
git log --oneline -5  # Show recent commits
git reset --hard PREVIOUS_COMMIT_HASH
docker-compose restart
```

### **Data Recovery**

#### **Backup and restore configuration**
```bash
# Create backup
sudo tar -czf ninja-backup-$(date +%Y%m%d).tar.gz \
    /etc/ninja-trading/ \
    /home/ninja/ninja/ \
    /opt/ninja-trading/.env

# Restore from backup
sudo tar -xzf ninja-backup-YYYYMMDD.tar.gz -C /
sudo chown -R ninja:ninja /home/ninja/ninja/
```

### **Contact Information**

#### **When to escalate**
- System completely unreachable
- Data corruption or loss
- Security breach suspected
- Multiple service failures

#### **Information to gather before escalating**
```bash
# System information
uname -a
df -h
free -h
systemctl --failed

# Service status
docker-compose ps
journalctl --since "1 hour ago" | tail -50

# Network information
ip addr show
ss -tlnp
```

---

## 📋 **DIAGNOSTIC COMMANDS**

### **Quick Health Check**
```bash
#!/bin/bash
echo "=== System Health Check ==="
echo "Date: $(date)"
echo "Uptime: $(uptime)"
echo ""

echo "=== Disk Space ==="
df -h

echo ""
echo "=== Memory Usage ==="
free -h

echo ""
echo "=== Service Status ==="
systemctl is-active docker nginx ninja-trading

echo ""
echo "=== Container Status ==="
docker-compose ps

echo ""
echo "=== Port Status ==="
ss -tlnp | grep -E ':(3000|8002|8081|6080|5900)'
```

### **Log Collection Script**
```bash
#!/bin/bash
LOG_DIR="/tmp/ninja-logs-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

# System logs
journalctl --since "1 hour ago" > "$LOG_DIR/system.log"
journalctl -u docker.service -n 100 > "$LOG_DIR/docker.log"
journalctl -u ninja-trading -n 100 > "$LOG_DIR/ninja-trading.log"

# Application logs
cp /var/log/ninja-setup/* "$LOG_DIR/" 2>/dev/null
docker-compose logs > "$LOG_DIR/docker-compose.log" 2>/dev/null

# Configuration
cp /etc/ninja-trading/*.json "$LOG_DIR/" 2>/dev/null

echo "Logs collected in: $LOG_DIR"
tar -czf "${LOG_DIR}.tar.gz" -C /tmp "$(basename "$LOG_DIR")"
echo "Archive created: ${LOG_DIR}.tar.gz"
```

Run these scripts when troubleshooting to gather comprehensive diagnostic information.

## **SSH Connection Failures in CI/CD**

#### **Problem**: SSH connection fails with "Permission denied (publickey,password)"
```
***@***: Permission denied (publickey,password).
ERROR: SSH connection failed
```

**Common Causes & Solutions:**

1. **SSH Key Not Added to Server**
   ```bash
   # On your deployment server, add the public key to authorized_keys
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   
   # Add your public key to authorized_keys
   cat >> ~/.ssh/authorized_keys << 'EOF'
   ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC... your-public-key-here
   EOF
   
   chmod 600 ~/.ssh/authorized_keys
   ```

2. **Incorrect SSH Key Format in GitHub Secrets**
   - Ensure the private key includes proper headers:
     ```
     -----BEGIN OPENSSH PRIVATE KEY-----
     ...key content...
     -----END OPENSSH PRIVATE KEY-----
     ```
   - Or for RSA keys:
     ```
     -----BEGIN RSA PRIVATE KEY-----
     ...key content...
     -----END RSA PRIVATE KEY-----
     ```

3. **SSH Service Configuration Issues**
   ```bash
   # Check SSH service status
   sudo systemctl status ssh
   
   # Check SSH configuration
   sudo sshd -t
   
   # Common SSH config issues in /etc/ssh/sshd_config:
   PubkeyAuthentication yes
   PasswordAuthentication no  # For security
   AuthorizedKeysFile .ssh/authorized_keys
   ```

4. **Firewall Blocking SSH**
   ```bash
   # Check if SSH port is open
   sudo ufw status
   sudo ufw allow ssh
   
   # Or check with iptables
   sudo iptables -L INPUT -v -n | grep :22
   ```

5. **Wrong User or Host in GitHub Secrets**
   - Verify `DEV_SERVER_HOST` is correct (IP or hostname)
   - Verify `DEV_SERVER_USER` exists on the server
   - Test manually: `ssh user@host`

**Debugging Steps:**
```bash
# Test SSH connection manually
ssh -vvv user@hostname

# Generate SSH key pair if needed
ssh-keygen -t ed25519 -C "deployment@actions_user"

# Copy public key to server
ssh-copy-id user@hostname
```

#### **Problem**: Host key verification failures
```
Host key verification failed
```

**Solution:**
```bash
# Remove old host key
ssh-keygen -R hostname

# Accept new host key
ssh-keyscan -H hostname >> ~/.ssh/known_hosts
```
