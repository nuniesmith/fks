#!/usr/bin/env bash
# ============================================================================
# FKS Docker Helper Script
# ============================================================================
# Convenience script for common Docker operations
#
# Usage:
#   ./docker-helper.sh [command] [options]
#
# Commands:
#   build         Build all or specific services
#   start         Start services (dev or prod)
#   stop          Stop all services
#   restart       Restart services
#   logs          View service logs
#   status        Show service status
#   clean         Clean up containers, images, volumes
#   health        Check service health
#   backup        Backup databases
#   restore       Restore databases
#   shell         Open shell in service container
#   help          Show this help message
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
COMPOSE_PROD_FILE="docker-compose.prod.yml"
BACKUP_DIR="./backups"

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi

    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
}

# ============================================================================
# Command Functions
# ============================================================================

cmd_build() {
    print_header "Building Docker Images"

    local service="${1:-}"
    local no_cache="${2:-}"

    if [ -n "$no_cache" ] && [ "$no_cache" == "--no-cache" ]; then
        print_info "Building with --no-cache flag"
        if [ -n "$service" ]; then
            docker compose build --no-cache "$service"
        else
            docker compose build --no-cache
        fi
    else
        if [ -n "$service" ]; then
            print_info "Building service: $service"
            docker compose build "$service"
        else
            print_info "Building all services"
            docker compose build
        fi
    fi

    print_success "Build completed"
}

cmd_start() {
    local mode="${1:-dev}"

    if [ "$mode" == "prod" ] || [ "$mode" == "production" ]; then
        print_header "Starting Services (Production Mode)"
        docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_PROD_FILE" up -d
    else
        print_header "Starting Services (Development Mode)"
        docker compose up -d
    fi

    print_success "Services started"
    echo ""
    cmd_status
}

cmd_stop() {
    print_header "Stopping All Services"
    docker compose down
    print_success "All services stopped"
}

cmd_restart() {
    local service="${1:-}"

    if [ -n "$service" ]; then
        print_header "Restarting Service: $service"
        docker compose restart "$service"
        print_success "Service $service restarted"
    else
        print_header "Restarting All Services"
        docker compose restart
        print_success "All services restarted"
    fi
}

cmd_logs() {
    local service="${1:-}"
    local follow="${2:--f}"

    if [ -n "$service" ]; then
        print_header "Viewing Logs: $service"
        docker compose logs "$follow" "$service"
    else
        print_header "Viewing All Logs"
        docker compose logs "$follow"
    fi
}

cmd_status() {
    print_header "Service Status"
    docker compose ps
    echo ""

    print_info "Service Health:"
    docker compose ps --format json | jq -r '.[] | "\(.Service): \(.State) - \(.Health)"' 2>/dev/null || \
        docker compose ps
}

cmd_health() {
    print_header "Health Check"

    local services=("gateway" "forward" "audit" "monitor" "questdb" "redis")
    local ports=("8001" "50051" "8080" "8009" "9000" "6379")

    for i in "${!services[@]}"; do
        local service="${services[$i]}"
        local port="${ports[$i]}"

        if [ "$service" == "forward" ]; then
            # gRPC service - just check if port is open
            if nc -z localhost "$port" 2>/dev/null; then
                print_success "$service (port $port): Healthy"
            else
                print_error "$service (port $port): Unhealthy"
            fi
        elif [ "$service" == "redis" ]; then
            if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
                print_success "$service: Healthy"
            else
                print_error "$service: Unhealthy"
            fi
        else
            local health_url=""
            case "$service" in
                gateway) health_url="http://localhost:$port/health/" ;;
                audit) health_url="http://localhost:$port/health" ;;
                monitor) health_url="http://localhost:$port/health" ;;
                questdb) health_url="http://localhost:$port/ping" ;;
            esac

            if [ -n "$health_url" ]; then
                if curl -sf "$health_url" > /dev/null 2>&1; then
                    print_success "$service ($health_url): Healthy"
                else
                    print_error "$service ($health_url): Unhealthy"
                fi
            fi
        fi
    done
}

cmd_clean() {
    print_header "Cleaning Docker Resources"

    read -p "This will remove stopped containers, unused images, and volumes. Continue? (y/N) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Stopping all services..."
        docker compose down

        print_info "Removing unused containers..."
        docker container prune -f

        print_info "Removing unused images..."
        docker image prune -a -f

        print_info "Removing unused volumes..."
        docker volume prune -f

        print_info "Removing unused networks..."
        docker network prune -f

        print_success "Cleanup completed"
        docker system df
    else
        print_warning "Cleanup cancelled"
    fi
}

cmd_backup() {
    print_header "Backing Up Databases"

    mkdir -p "$BACKUP_DIR"
    local timestamp=$(date +%Y%m%d_%H%M%S)

    # Backup QuestDB
    print_info "Backing up QuestDB..."
    if docker compose exec -T questdb tar czf /tmp/questdb_backup.tar.gz -C /var/lib/questdb db 2>/dev/null; then
        docker cp fks_questdb:/tmp/questdb_backup.tar.gz "$BACKUP_DIR/questdb_${timestamp}.tar.gz"
        print_success "QuestDB backup saved to $BACKUP_DIR/questdb_${timestamp}.tar.gz"
    else
        print_error "QuestDB backup failed"
    fi

    # Backup Redis
    print_info "Backing up Redis..."
    if docker compose exec -T redis redis-cli BGSAVE >/dev/null 2>&1; then
        sleep 2
        docker cp fks_redis:/data/dump.rdb "$BACKUP_DIR/redis_${timestamp}.rdb"
        print_success "Redis backup saved to $BACKUP_DIR/redis_${timestamp}.rdb"
    else
        print_error "Redis backup failed"
    fi

    print_success "Backup completed"
}

cmd_restore() {
    local backup_file="${1:-}"

    if [ -z "$backup_file" ]; then
        print_error "Usage: $0 restore <backup_file>"
        print_info "Available backups:"
        ls -lh "$BACKUP_DIR" 2>/dev/null || print_warning "No backups found"
        exit 1
    fi

    print_header "Restoring Database"

    if [[ "$backup_file" == *"questdb"* ]]; then
        print_info "Restoring QuestDB from $backup_file..."
        docker cp "$backup_file" fks_questdb:/tmp/restore.tar.gz
        docker compose exec -T questdb tar xzf /tmp/restore.tar.gz -C /var/lib/questdb
        docker compose restart questdb
        print_success "QuestDB restored"
    elif [[ "$backup_file" == *"redis"* ]]; then
        print_info "Restoring Redis from $backup_file..."
        docker compose stop redis
        docker cp "$backup_file" fks_redis:/data/dump.rdb
        docker compose start redis
        print_success "Redis restored"
    else
        print_error "Unknown backup type"
        exit 1
    fi
}

cmd_shell() {
    local service="${1:-gateway}"

    print_header "Opening Shell in $service"

    case "$service" in
        forward|audit|monitor)
            docker compose exec "$service" /bin/bash || docker compose exec "$service" /bin/sh
            ;;
        gateway)
            docker compose exec "$service" /bin/bash
            ;;
        redis)
            docker compose exec "$service" redis-cli
            ;;
        questdb|prometheus|grafana)
            docker compose exec "$service" /bin/sh
            ;;
        *)
            print_error "Unknown service: $service"
            print_info "Available services: forward, gateway, audit, monitor, redis, questdb, prometheus, grafana"
            exit 1
            ;;
    esac
}

cmd_help() {
    cat << EOF
FKS Docker Helper Script

Usage:
    $0 [command] [options]

Commands:
    build [service] [--no-cache]  Build all or specific service images
    start [dev|prod]              Start services in dev or production mode
    stop                          Stop all services
    restart [service]             Restart all services or specific service
    logs [service] [-f|--tail=N]  View logs for all or specific service
    status                        Show status of all services
    health                        Check health of all services
    clean                         Remove stopped containers, unused images, and volumes
    backup                        Backup QuestDB and Redis databases
    restore <file>                Restore database from backup file
    shell <service>               Open shell in service container
    help                          Show this help message

Examples:
    $0 build                      # Build all services
    $0 build forward --no-cache   # Clean build of forward service
    $0 start                      # Start in development mode
    $0 start prod                 # Start in production mode
    $0 logs forward -f            # Follow forward service logs
    $0 logs --tail=100            # Show last 100 log lines
    $0 restart gateway            # Restart gateway service
    $0 shell gateway              # Open bash shell in gateway
    $0 shell redis                # Open redis-cli in redis
    $0 backup                     # Backup all databases
    $0 restore backups/questdb_20240101_120000.tar.gz

Services:
    - forward    : Rust execution engine
    - gateway    : Python API and orchestration
    - audit      : Code analysis service
    - monitor    : Infrastructure monitoring
    - redis      : Pub/Sub and caching
    - questdb    : Time-series database
    - prometheus : Metrics collection
    - grafana    : Visualization dashboards

Environment:
    Set these in .env file:
    - TRADING_MODE (paper|live)
    - BYBIT_API_KEY
    - BYBIT_API_SECRET
    - XAI_API_KEY
    - GRAFANA_PASSWORD

For more information, see:
    - ./docker/README.docker.md
    - ./README.md
EOF
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    check_docker

    local command="${1:-help}"
    shift || true

    case "$command" in
        build)
            cmd_build "$@"
            ;;
        start|up)
            cmd_start "$@"
            ;;
        stop|down)
            cmd_stop "$@"
            ;;
        restart)
            cmd_restart "$@"
            ;;
        logs)
            cmd_logs "$@"
            ;;
        status|ps)
            cmd_status "$@"
            ;;
        health)
            cmd_health "$@"
            ;;
        clean)
            cmd_clean "$@"
            ;;
        backup)
            cmd_backup "$@"
            ;;
        restore)
            cmd_restore "$@"
            ;;
        shell|exec)
            cmd_shell "$@"
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
