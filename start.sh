#!/bin/bash

# FKS Trading Tool - Start Script
# This script manages Docker containers, builds, and cleans temporary data

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to clear temporary data
clear_temp_data() {
    print_info "Clearing temporary data..."
    
    # Clear Redis cache
    if docker ps -q -f name=fks_redis > /dev/null 2>&1; then
        print_info "Flushing Redis cache..."
        docker exec fks_redis redis-cli FLUSHALL || print_warning "Could not flush Redis (container may not be running)"
    fi
    
    # Clear __pycache__ directories
    print_info "Removing __pycache__ directories..."
    find ./src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    
    print_success "Temporary data cleared"
}

# Function to stop containers
stop_containers() {
    print_info "Stopping containers..."
    docker compose -f docker-compose.yml down
    print_success "Containers stopped"
}

# Function to clean volumes
clean_volumes() {
    print_warning "This will remove all database and Redis data!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Removing volumes..."
        docker compose -f docker-compose.yml down -v
        print_success "Volumes removed"
    else
        print_info "Volume cleanup cancelled"
    fi
}

# Function to rebuild and start
rebuild_and_start() {
    print_info "Rebuilding containers..."
    clear_temp_data
    docker compose -f docker-compose.yml build --no-cache
    print_success "Build complete"
    
    print_info "Starting containers..."
    docker compose -f docker-compose.yml up -d
    print_success "Containers started"
    
    # Wait for services to be ready
    sleep 3
    
    print_info "Running Django migrations..."
    docker exec fks_app python manage.py migrate || print_warning "Migrations failed (check if Django is properly configured)"
    
    print_success "All services started!"
    echo
    print_info "Services available at:"
    echo "  - Django App: http://localhost:8000"
    echo "  - Admin Panel: http://localhost:8000/admin"
    echo "  - Flower (Celery): http://localhost:5555"
    echo "  - pgAdmin: http://localhost:5050"
    echo
    print_info "Showing logs (Ctrl+C to exit)..."
    docker compose -f docker-compose.yml logs -f
}

# Function to start without rebuild
start_containers() {
    print_info "Starting containers..."
    docker compose -f docker-compose.yml up -d
    print_success "Containers started"
    
    # Wait for services to be ready
    sleep 3
    
    print_info "Running Django migrations..."
    docker exec fks_app python manage.py migrate || print_warning "Migrations failed (check if Django is properly configured)"
    
    print_success "All services started!"
    echo
    print_info "Services available at:"
    echo "  - Django App: http://localhost:8000"
    echo "  - Admin Panel: http://localhost:8000/admin"
    echo "  - Flower (Celery): http://localhost:5555"
    echo "  - pgAdmin: http://localhost:5050"
    echo
    print_info "Showing logs (Ctrl+C to exit)..."
    docker compose -f docker-compose.yml logs -f
}

# Function to restart containers
restart_containers() {
    print_info "Restarting containers..."
    clear_temp_data
    docker compose -f docker-compose.yml restart
    print_success "Containers restarted"
    
    print_info "Showing logs (Ctrl+C to exit)..."
    docker compose -f docker-compose.yml logs -f
}

# Function to show status
show_status() {
    print_info "Container status:"
    docker compose -f docker-compose.yml ps
    echo
    print_info "Disk usage:"
    docker system df
}

# Function to view logs
view_logs() {
    docker compose -f docker-compose.yml logs -f
}

# Function to clean Docker system
clean_docker() {
    print_warning "This will remove unused Docker images and build cache!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleaning Docker system..."
        docker system prune -f
        print_success "Docker system cleaned"
    else
        print_info "Docker cleanup cancelled"
    fi
}

# Function to show help
show_help() {
    cat << EOF
${GREEN}FKS Trading Platform - Django with Celery${NC}

Usage: ./start.sh [COMMAND]

Commands:
  ${YELLOW}start${NC}       - Start all containers (Django, Celery, PostgreSQL, Redis)
  ${YELLOW}rebuild${NC}     - Force rebuild and start containers (clears cache)
  ${YELLOW}restart${NC}     - Restart containers and clear temp data
  ${YELLOW}stop${NC}        - Stop all containers
  ${YELLOW}logs${NC}        - View container logs
  ${YELLOW}status${NC}      - Show container and disk status
  ${YELLOW}clean${NC}       - Clear temporary data (cache, pycache)
  ${YELLOW}clean-volumes${NC} - Remove all volumes (database & Redis data)
  ${YELLOW}clean-docker${NC}  - Clean unused Docker images and build cache
  ${YELLOW}shell${NC}       - Open shell in Django container
  ${YELLOW}migrate${NC}     - Run Django migrations
  ${YELLOW}createsuperuser${NC} - Create Django admin superuser
  ${YELLOW}celery-status${NC}  - Check Celery worker and beat status
  ${YELLOW}help${NC}        - Show this help message

Services:
  ${BLUE}Django${NC}       - http://localhost:8000
  ${BLUE}Admin${NC}        - http://localhost:8000/admin
  ${BLUE}Flower${NC}       - http://localhost:5555 (Celery monitoring)
  ${BLUE}pgAdmin${NC}      - http://localhost:5050 (Database admin)

Examples:
  ./start.sh start          # Quick start all services
  ./start.sh rebuild        # After code changes
  ./start.sh migrate        # Run database migrations
  ./start.sh createsuperuser # Create admin user
  ./start.sh celery-status  # Check background tasks
  ./start.sh logs           # View all logs
  ./start.sh stop           # Stop everything

EOF
}

# Function to open shell in container
open_shell() {
    print_info "Opening shell in Django container..."
    docker exec -it fks_app /bin/bash
}

# Function to run Django migrations
run_migrations() {
    print_info "Running Django migrations..."
    docker exec -it fks_app python manage.py makemigrations
    docker exec -it fks_app python manage.py migrate
    print_success "Migrations complete"
}

# Function to create superuser
create_superuser() {
    print_info "Creating Django superuser..."
    docker exec -it fks_app python manage.py createsuperuser
}

# Function to check Celery status
check_celery_status() {
    print_info "Checking Celery status..."
    echo
    print_info "Celery Worker status:"
    docker compose -f docker-compose.yml ps celery_worker
    echo
    print_info "Celery Beat status:"
    docker compose -f docker-compose.yml ps celery_beat
    echo
    print_info "Flower UI status:"
    docker compose -f docker-compose.yml ps flower
    echo
    print_info "Active Celery tasks:"
    docker exec fks_app celery -A django inspect active || print_warning "Could not get active tasks"
    echo
    print_info "Registered tasks:"
    docker exec fks_app celery -A django inspect registered | head -20 || print_warning "Could not get registered tasks"
}

# Main script logic
case "${1:-start}" in
    start)
        clear_temp_data
        start_containers
        ;;
    rebuild)
        rebuild_and_start
        ;;
    restart)
        restart_containers
        ;;
    stop)
        stop_containers
        ;;
    logs)
        view_logs
        ;;
    status)
        show_status
        ;;
    clean)
        clear_temp_data
        ;;
    clean-volumes)
        clean_volumes
        ;;
    clean-docker)
        clean_docker
        ;;
    shell)
        open_shell
        ;;
    migrate)
        run_migrations
        ;;
    createsuperuser)
        create_superuser
        ;;
    celery-status)
        check_celery_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo
        show_help
        exit 1
        ;;
esac