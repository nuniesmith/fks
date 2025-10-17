#!/bin/bash

# FKS Trading Platform - Enhanced Start Script
# Manages Docker containers with GPU support, logging, health checks, and additional management features

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
LOG_DIR="./logs"
COMPOSE_FILE="docker-compose.yml"
GPU_COMPOSE_FILE="docker-compose.gpu.yml"
USE_GPU=false

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

print_header() {
    echo -e "${PURPLE}╔════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║     FKS Trading Platform Manager      ║${NC}"
    echo -e "${PURPLE}╚════════════════════════════════════════╝${NC}"
}

# Check if GPU is available
check_gpu() {
    print_info "Checking for NVIDIA GPU..."
    
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null; then
            print_success "NVIDIA GPU detected!"
            nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
            return 0
        fi
    fi
    
    print_warning "No NVIDIA GPU detected or nvidia-smi not available"
    return 1
}

# Check if nvidia-docker is available
check_nvidia_docker() {
    print_info "Checking for NVIDIA Docker runtime..."
    
    if docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        print_success "NVIDIA Docker runtime is available"
        return 0
    else
        print_warning "NVIDIA Docker runtime not available"
        print_info "Install with: distribution=$(. /etc/os-release;echo \$ID\$VERSION_ID) && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - && curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list"
        return 1
    fi
}

# Setup log directories
setup_logging() {
    print_info "Setting up log directories..."
    
    mkdir -p "$LOG_DIR"/{nginx,gunicorn,postgres,redis,celery,rag}
    chmod -R 755 "$LOG_DIR"
    
    print_success "Log directories created"
}

# Clear temporary data
clear_temp_data() {
    print_info "Clearing temporary data..."
    
    # Clear Redis cache
    if docker ps -q -f name=fks_redis > /dev/null 2>&1; then
        print_info "Flushing Redis cache..."
        docker exec fks_redis redis-cli FLUSHALL 2>/dev/null || print_warning "Could not flush Redis"
    fi
    
    # Clear Python cache
    print_info "Removing Python cache..."
    find ./src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find ./src -type f -name "*.pyc" -delete 2>/dev/null || true
    find ./src -type f -name "*.pyo" -delete 2>/dev/null || true
    find ./src -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    
    print_success "Temporary data cleared"
}

# Build containers
build_containers() {
    print_info "Building Docker containers..."
    
    if [ "$USE_GPU" = true ]; then
        docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" build $NO_CACHE
    else
        docker compose -f "$COMPOSE_FILE" build $NO_CACHE
    fi
    
    print_success "Containers built successfully"
}

# Start services
start_services() {
    print_info "Starting services..."
    
    if [ "$USE_GPU" = true ]; then
        print_info "Starting with GPU support..."
        docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" up -d
    else
        docker compose -f "$COMPOSE_FILE" up -d
    fi
    
    print_success "Services started"
    
    # Wait for services to be ready
    sleep 3
    
    print_info "Running Django migrations..."
    docker exec fks_app python manage.py migrate || print_warning "Migrations failed (check if Django is properly configured)"
}

# Stop services
stop_services() {
    print_info "Stopping services..."
    
    if [ "$USE_GPU" = true ]; then
        docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" down
    else
        docker compose -f "$COMPOSE_FILE" down
    fi
    
    print_success "Services stopped"
}

# Clean volumes
clean_volumes() {
    print_warning "This will remove all database and Redis data!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Removing volumes..."
        if [ "$USE_GPU" = true ]; then
            docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" down -v
        else
            docker compose -f "$COMPOSE_FILE" down -v
        fi
        print_success "Volumes removed"
    else
        print_info "Volume cleanup cancelled"
    fi
}

# Clean Docker system
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

# Health check
health_check() {
    print_info "Performing health checks..."
    
    sleep 5  # Wait for services to start
    
    # Check web service
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Web service: healthy"
    else
        print_warning "Web service: not responding (may still be starting)"
    fi
    
    # Check database
    if docker exec fks_db pg_isready -U postgres > /dev/null 2>&1; then
        print_success "Database: healthy"
    else
        print_warning "Database: not ready"
    fi
    
    # Check Redis
    if docker exec fks_redis redis-cli ping > /dev/null 2>&1; then
        print_success "Redis: healthy"
    else
        print_warning "Redis: not ready"
    fi
    
    # Check RAG service (if GPU enabled)
    if [ "$USE_GPU" = true ]; then
        if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
            print_success "RAG service: healthy"
        else
            print_warning "RAG service: not responding (may still be loading models)"
        fi
    fi
}

# Show service status
show_status() {
    print_info "Service Status:"
    if [ "$USE_GPU" = true ]; then
        docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" ps
    else
        docker compose -f "$COMPOSE_FILE" ps
    fi
    
    echo ""
    print_info "Disk usage:"
    docker system df
    
    echo ""
    print_info "Access URLs:"
    echo "  • Django App:    http://localhost:8000"
    echo "  • Admin Panel:   http://localhost:8000/admin"
    echo "  • Flower:        http://localhost:5555"
    echo "  • pgAdmin:       http://localhost:5050"
    
    if [ "$USE_GPU" = true ]; then
        echo "  • RAG API:       http://localhost:8001"
        echo "  • Ollama API:    http://localhost:11434"
    fi
    
    echo ""
    print_info "Logs:"
    echo "  • View all:      ./start.sh logs"
    echo "  • View web:      docker compose logs -f web"
    echo "  • View celery:   docker compose logs -f celery_worker"
    
    if [ "$USE_GPU" = true ]; then
        echo "  • View RAG:      docker compose -f $COMPOSE_FILE -f $GPU_COMPOSE_FILE logs -f rag_service"
    fi
}

# View logs
view_logs() {
    if [ "$USE_GPU" = true ]; then
        docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" logs -f
    else
        docker compose -f "$COMPOSE_FILE" logs -f
    fi
}

# Open shell in container
open_shell() {
    print_info "Opening shell in Django container..."
    docker exec -it fks_app /bin/bash
}

# Run Django migrations
run_migrations() {
    print_info "Running Django migrations..."
    docker exec -it fks_app python manage.py makemigrations
    docker exec -it fks_app python manage.py migrate
    print_success "Migrations complete"
}

# Create superuser
create_superuser() {
    print_info "Creating Django superuser..."
    docker exec -it fks_app python manage.py createsuperuser
}

# Check Celery status
check_celery_status() {
    print_info "Checking Celery status..."
    echo
    print_info "Celery Worker status:"
    if [ "$USE_GPU" = true ]; then
        docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" ps celery_worker
    else
        docker compose -f "$COMPOSE_FILE" ps celery_worker
    fi
    echo
    print_info "Celery Beat status:"
    if [ "$USE_GPU" = true ]; then
        docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" ps celery_beat
    else
        docker compose -f "$COMPOSE_FILE" ps celery_beat
    fi
    echo
    print_info "Flower UI status:"
    if [ "$USE_GPU" = true ]; then
        docker compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" ps flower
    else
        docker compose -f "$COMPOSE_FILE" ps flower
    fi
    echo
    print_info "Active Celery tasks:"
    docker exec fks_app celery -A web.django inspect active || print_warning "Could not get active tasks"
    echo
    print_info "Registered tasks:"
    docker exec fks_app celery -A web.django inspect registered | head -20 || print_warning "Could not get registered tasks"
}

# Check GPU status in container
check_gpu_status() {
    if [ "$USE_GPU" != true ]; then
        print_warning "GPU support not enabled. Use --gpu flag to enable."
        return 1
    fi
    
    print_info "Checking GPU status in RAG service container..."
    if docker ps -q -f name=fks_rag_gpu > /dev/null 2>&1; then
        docker exec fks_rag_gpu nvidia-smi
        echo ""
        print_info "GPU memory usage:"
        docker stats --no-stream fks_rag_gpu
    else
        print_warning "RAG GPU service is not running"
        return 1
    fi
}

# Show usage
show_usage() {
    print_header
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start            Start all services (clears temp data)"
    echo "  rebuild          Force rebuild and start services (no-cache)"
    echo "  restart          Restart services (stops, clears temp, starts)"
    echo "  build            Build containers"
    echo "  stop             Stop all services"
    echo "  logs             Show logs"
    echo "  status           Show service and disk status"
    echo "  health           Run health checks"
    echo "  clean            Clear temporary data (cache, pycache)"
    echo "  clean-volumes    Remove all volumes (database & Redis data)"
    echo "  clean-docker     Clean unused Docker images and build cache"
    echo "  shell            Open shell in Django container"
    echo "  migrate          Run Django migrations"
    echo "  createsuperuser  Create Django admin superuser"
    echo "  celery-status    Check Celery worker and beat status"
    echo "  gpu-status       Check GPU status and usage (requires --gpu)"
    echo "  help             Show this help message"
    echo ""
    echo "Options:"
    echo "  --gpu            Enable GPU support for RAG/LLM"
    echo "  --no-cache       Build without cache (for build/rebuild)"
    echo ""
    echo "Examples:"
    echo "  ./start.sh start                # Quick start all services"
    echo "  ./start.sh --gpu start          # Start with GPU support"
    echo "  ./start.sh --gpu rebuild        # Rebuild with GPU support"
    echo "  ./start.sh --gpu --no-cache rebuild  # Force rebuild with GPU (no cache)"
    echo "  ./start.sh migrate              # Run database migrations"
    echo "  ./start.sh createsuperuser      # Create admin user"
    echo "  ./start.sh celery-status        # Check background tasks"
    echo "  ./start.sh --gpu gpu-status     # Check GPU usage"
    echo "  ./start.sh logs                 # View all logs"
    echo "  ./start.sh stop                 # Stop everything"
}

# Main script
main() {
    print_header
    
    # Parse arguments
    NO_CACHE=""
    COMMAND=""
    
    # First pass: parse all flags
    while [[ $# -gt 0 ]]; do
        case $1 in
            --gpu)
                if check_gpu && check_nvidia_docker; then
                    USE_GPU=true
                    print_success "GPU support enabled"
                else
                    print_error "GPU support requested but not available"
                    exit 1
                fi
                shift
                ;;
            --no-cache)
                NO_CACHE="--no-cache"
                print_info "Build will not use cache"
                shift
                ;;
            --help|help|-h)
                COMMAND="help"
                shift
                ;;
            start|rebuild|restart|build|stop|logs|status|health|clean|clean-volumes|clean-docker|shell|migrate|createsuperuser|celery-status|gpu-status)
                if [ -z "$COMMAND" ]; then
                    COMMAND=$1
                fi
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Default command if none provided
    if [ -z "$COMMAND" ]; then
        COMMAND="start"
    fi
    
    # Execute command
    case $COMMAND in
        start)
            setup_logging
            clear_temp_data
            start_services
            health_check
            show_status
            ;;
        rebuild)
            NO_CACHE="--no-cache"
            setup_logging
            clear_temp_data
            build_containers
            start_services
            health_check
            show_status
            ;;
        restart)
            stop_services
            clear_temp_data
            setup_logging
            start_services
            health_check
            show_status
            ;;
        build)
            setup_logging
            build_containers
            ;;
        stop)
            stop_services
            ;;
        logs)
            view_logs
            ;;
        status)
            show_status
            ;;
        health)
            health_check
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
        gpu-status)
            check_gpu_status
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

# Run main
main "$@"