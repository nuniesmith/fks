#!/bin/bash

# FKS Log Fetcher
# Fetches logs from all FKS services running on remote oryx server
# Usage: ./scripts/fetch_logs.sh [ssh_user@host] [--tail N] [--since DURATION]
#
# Examples:
#   ./scripts/fetch_logs.sh                    # Uses default: jordan@oryx
#   ./scripts/fetch_logs.sh user@myserver      # Custom SSH target
#   ./scripts/fetch_logs.sh --tail 100         # Last 100 lines per service
#   ./scripts/fetch_logs.sh --since 10m        # Last 10 minutes of logs

set -e

# Default values
SSH_TARGET="jordan@oryx"
TAIL_LINES=200
SINCE_DURATION=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tail)
            TAIL_LINES="$2"
            shift 2
            ;;
        --since)
            SINCE_DURATION="$2"
            shift 2
            ;;
        *)
            # If it looks like SSH target (contains @), use it
            if [[ "$1" == *"@"* ]]; then
                SSH_TARGET="$1"
            fi
            shift
            ;;
    esac
done

# FKS service container names
SERVICES=(
    "fks_janus"
    "fks_janus_worker"
    "fks_janus_beat"
    "fks_muscle"
    "fks_monitor"
    "fks_web"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  FKS Service Logs Fetcher${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}SSH Target:${NC} ${SSH_TARGET}"
echo -e "${BLUE}Tail Lines:${NC} ${TAIL_LINES}"
if [[ -n "$SINCE_DURATION" ]]; then
    echo -e "${BLUE}Since:${NC} ${SINCE_DURATION}"
fi
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Build docker logs command arguments
DOCKER_ARGS="--tail ${TAIL_LINES}"
if [[ -n "$SINCE_DURATION" ]]; then
    DOCKER_ARGS="${DOCKER_ARGS} --since ${SINCE_DURATION}"
fi

# Fetch logs for each service
for service in "${SERVICES[@]}"; do
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ${service}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Check if container exists and is running
    if ssh -o ConnectTimeout=5 "$SSH_TARGET" "docker ps --format '{{.Names}}' | grep -q '^${service}$'" 2>/dev/null; then
        # Fetch logs
        ssh "$SSH_TARGET" "docker logs ${DOCKER_ARGS} ${service} 2>&1" || {
            echo -e "${YELLOW}⚠️  Failed to fetch logs for ${service}${NC}"
        }
    else
        echo -e "${YELLOW}⚠️  Container ${service} is not running or does not exist${NC}"
    fi
    
    echo ""
done

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  Log fetch complete${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Optional: Also fetch a summary of container statuses
echo ""
echo -e "${BLUE}Container Status Summary:${NC}"
ssh "$SSH_TARGET" "docker ps --filter 'name=fks_' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'" || true

