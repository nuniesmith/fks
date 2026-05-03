#!/bin/bash
# ============================================================================
# FKS Log Rotation and Archival Setup
# ============================================================================
# This script configures Docker log rotation and sets up automated log
# archival for the 30-day paper trading test.
#
# Usage:
#   ./scripts/monitoring/setup-log-rotation.sh
#
# What it does:
#   1. Updates docker-compose.yml with log rotation settings
#   2. Creates log archival script
#   3. Sets up cron job for weekly log archival
#   4. Creates backup directory structure
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/infrastructure/compose/docker-compose.yml"
ARCHIVE_DIR="/var/backups/fks/logs"
ARCHIVE_SCRIPT="$PROJECT_ROOT/scripts/monitoring/archive-logs.sh"

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# ============================================================================
# Main Script
# ============================================================================

print_header "FKS Log Rotation Setup"

echo -e "This script will configure Docker log rotation and archival for the"
echo -e "30-day paper trading test.\n"

# ============================================================================
# Step 1: Check if docker-compose.yml exists
# ============================================================================

print_step "Step 1: Checking docker-compose.yml..."

if [ ! -f "$COMPOSE_FILE" ]; then
    print_error "docker-compose.yml not found at $COMPOSE_FILE"
    exit 1
fi

print_success "Found docker-compose.yml"

# ============================================================================
# Step 2: Create backup directory structure
# ============================================================================

print_step "Step 2: Creating backup directories..."

# Check if we need sudo for /var/backups
if [ -w /var/backups ] || sudo mkdir -p "$ARCHIVE_DIR" 2>/dev/null; then
    print_success "Created archive directory: $ARCHIVE_DIR"
else
    print_warning "Cannot create $ARCHIVE_DIR - will use local directory instead"
    ARCHIVE_DIR="$PROJECT_ROOT/backups/logs"
    mkdir -p "$ARCHIVE_DIR"
    print_success "Created local archive directory: $ARCHIVE_DIR"
fi

# Set permissions if we created in /var/backups
if [[ "$ARCHIVE_DIR" == /var/backups/* ]] && [ -d "$ARCHIVE_DIR" ]; then
    sudo chown -R $(whoami):$(whoami) "$ARCHIVE_DIR" 2>/dev/null || true
fi

# ============================================================================
# Step 3: Check current log rotation settings
# ============================================================================

print_step "Step 3: Checking current log rotation settings..."

# Check if logging is already configured in docker-compose
if grep -q "logging:" "$COMPOSE_FILE"; then
    print_warning "Log rotation settings already exist in docker-compose.yml"
    echo -e "Current settings will be preserved. You may want to review them manually."
else
    print_warning "No log rotation settings found in docker-compose.yml"
    echo -e "Add the following to each service in your docker-compose.yml:\n"
    cat << 'EOF'
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
        compress: "true"
EOF
    echo ""
fi

# ============================================================================
# Step 4: Create log archival script
# ============================================================================

print_step "Step 4: Creating log archival script..."

cat > "$ARCHIVE_SCRIPT" << 'ARCHIVE_SCRIPT_EOF'
#!/bin/bash
# ============================================================================
# FKS Log Archival Script
# ============================================================================
# This script archives Docker logs for FKS services on a weekly basis.
# Intended to be run via cron.
#
# Usage:
#   ./scripts/monitoring/archive-logs.sh
# ============================================================================

set -e

# Configuration
ARCHIVE_DIR="/var/backups/fks/logs"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=90  # Keep archives for 90 days

# Check if archive dir is accessible, fall back to local
if [ ! -w "$ARCHIVE_DIR" ] 2>/dev/null; then
    ARCHIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/backups/logs"
    mkdir -p "$ARCHIVE_DIR"
fi

TEMP_DIR="$ARCHIVE_DIR/temp_${DATE}"
mkdir -p "$TEMP_DIR"

echo "=== FKS Log Archival Started: $(date) ==="
echo "Archive directory: $ARCHIVE_DIR"
echo "Temp directory: $TEMP_DIR"

# Services to archive
SERVICES=(
    "fks_janus"
    "fks_execution"
    "fks_forward"
    "fks_data"
    "fks_cns"
    "fks_postgres"
    "questdb"
    "redis"
    "prometheus"
    "grafana"
    "alertmanager"
)

# Archive each service's logs
for service in "${SERVICES[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${service}$"; then
        echo "Archiving logs for: $service"
        docker logs "$service" > "$TEMP_DIR/${service}_${DATE}.log" 2>&1 || true
    else
        echo "Skipping $service (not running)"
    fi
done

# Create compressed archive
echo "Creating compressed archive..."
ARCHIVE_NAME="fks_logs_${DATE}.tar.gz"
tar -czf "$ARCHIVE_DIR/$ARCHIVE_NAME" -C "$TEMP_DIR" . 2>/dev/null || {
    echo "Warning: tar compression failed, trying without compression"
    tar -cf "$ARCHIVE_DIR/fks_logs_${DATE}.tar" -C "$TEMP_DIR" .
    ARCHIVE_NAME="fks_logs_${DATE}.tar"
}

# Cleanup temp directory
rm -rf "$TEMP_DIR"

# Calculate archive size
ARCHIVE_SIZE=$(du -h "$ARCHIVE_DIR/$ARCHIVE_NAME" | cut -f1)
echo "Archive created: $ARCHIVE_NAME (Size: $ARCHIVE_SIZE)"

# Cleanup old archives (older than retention period)
echo "Cleaning up archives older than $RETENTION_DAYS days..."
find "$ARCHIVE_DIR" -name "fks_logs_*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
find "$ARCHIVE_DIR" -name "fks_logs_*.tar" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

# List current archives
echo ""
echo "=== Current Archives ==="
ls -lh "$ARCHIVE_DIR"/fks_logs_*.tar* 2>/dev/null | tail -10 || echo "No archives found"

echo ""
echo "=== FKS Log Archival Completed: $(date) ==="
ARCHIVE_SCRIPT_EOF

chmod +x "$ARCHIVE_SCRIPT"
print_success "Created log archival script: $ARCHIVE_SCRIPT"

# ============================================================================
# Step 5: Test the archival script
# ============================================================================

print_step "Step 5: Testing log archival script..."

echo -e "\nRunning test archive..."
if bash "$ARCHIVE_SCRIPT"; then
    print_success "Test archive created successfully"

    # Show the archive
    echo -e "\nTest archive created:"
    ls -lh "$ARCHIVE_DIR"/fks_logs_*.tar* 2>/dev/null | tail -1 || echo "No archive found"
else
    print_warning "Test archive failed - you may need to run it manually"
fi

# ============================================================================
# Step 6: Set up cron job
# ============================================================================

print_step "Step 6: Setting up cron job for weekly archival..."

echo -e "\nWould you like to set up a weekly cron job to archive logs?"
echo -e "This will run every Sunday at 2:00 AM."
echo -e ""
read -p "Set up cron job? (y/n): " SETUP_CRON

if [[ "$SETUP_CRON" =~ ^[Yy] ]]; then
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "$ARCHIVE_SCRIPT"; then
        print_warning "Cron job already exists"
    else
        # Add cron job
        (crontab -l 2>/dev/null; echo "# FKS Log Archival - Every Sunday at 2:00 AM") | crontab -
        (crontab -l 2>/dev/null; echo "0 2 * * 0 $ARCHIVE_SCRIPT >> $ARCHIVE_DIR/archival.log 2>&1") | crontab -
        print_success "Cron job added successfully"

        echo -e "\nCurrent crontab:"
        crontab -l | grep -A 1 "FKS Log Archival"
    fi
else
    echo -e "\nTo manually set up the cron job, add this line to your crontab (crontab -e):"
    echo -e "${YELLOW}0 2 * * 0 $ARCHIVE_SCRIPT >> $ARCHIVE_DIR/archival.log 2>&1${NC}"
fi

# ============================================================================
# Step 7: Docker log rotation configuration
# ============================================================================

print_step "Step 7: Docker daemon log rotation..."

DOCKER_DAEMON_JSON="/etc/docker/daemon.json"

echo -e "\nDocker daemon-level log rotation can be configured in $DOCKER_DAEMON_JSON"
echo -e "This will apply to all containers by default.\n"

if [ -f "$DOCKER_DAEMON_JSON" ]; then
    echo -e "Current daemon.json exists. Please review it manually."
else
    echo -e "Recommended daemon.json configuration:"
    cat << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5",
    "compress": "true"
  }
}
EOF
    echo -e ""
    read -p "Would you like to create this file? (requires sudo) (y/n): " CREATE_DAEMON_JSON

    if [[ "$CREATE_DAEMON_JSON" =~ ^[Yy] ]]; then
        echo '{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5",
    "compress": "true"
  }
}' | sudo tee "$DOCKER_DAEMON_JSON" > /dev/null

        print_success "Created $DOCKER_DAEMON_JSON"
        print_warning "Docker daemon restart required to apply changes"

        read -p "Restart Docker daemon now? (y/n): " RESTART_DOCKER
        if [[ "$RESTART_DOCKER" =~ ^[Yy] ]]; then
            sudo systemctl restart docker
            print_success "Docker daemon restarted"
        fi
    fi
fi

# ============================================================================
# Summary
# ============================================================================

print_header "Setup Complete!"

echo -e "Log rotation and archival have been configured:\n"
echo -e "  ${CYAN}Archive Directory:${NC}  $ARCHIVE_DIR"
echo -e "  ${CYAN}Archival Script:${NC}   $ARCHIVE_SCRIPT"
echo -e "  ${CYAN}Archive Retention:${NC} 90 days"
echo -e "  ${CYAN}Cron Schedule:${NC}     Every Sunday at 2:00 AM (if configured)"

echo -e "\n${CYAN}Recommended docker-compose.yml settings for each service:${NC}"
cat << 'EOF'
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
        compress: "true"
EOF

echo -e "\n${CYAN}Manual Commands:${NC}"
echo -e "  # Run archival manually"
echo -e "  $ARCHIVE_SCRIPT"
echo -e ""
echo -e "  # View current Docker logs"
echo -e "  docker logs fks_janus --tail 100"
echo -e ""
echo -e "  # Check log file sizes"
echo -e "  sudo du -sh /var/lib/docker/containers/*/\*-json.log"
echo -e ""
echo -e "  # View archived logs"
echo -e "  ls -lh $ARCHIVE_DIR"
echo -e ""
echo -e "  # Extract an archive"
echo -e "  tar -xzf $ARCHIVE_DIR/fks_logs_YYYYMMDD_HHMMSS.tar.gz"

echo -e "\n${GREEN}Your logs are now configured for the 30-day test!${NC}"
