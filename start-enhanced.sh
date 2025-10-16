#!/bin/bash

# FKS Trading Platform - Enhanced Start Script
# Manages Docker containers with GPU support, logging, and health checks

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
        docker-compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" build
    else
        docker-compose -f "$COMPOSE_FILE" build
    fi
    
    print_success "Containers built successfully"
}

# Start services
start_services() {
    print_info "Starting services..."
    
    if [ "$USE_GPU" = true ]; then
        print_info "Starting with GPU support..."
        docker-compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" up -d
    else
        docker-compose -f "$COMPOSE_FILE" up -d
    fi
    
    print_success "Services started"
}

# Stop services
stop_services() {
    print_info "Stopping services..."
    
    if [ "$USE_GPU" = true ]; then
        docker-compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" down
    else
        docker-compose -f "$COMPOSE_FILE" down
    fi
    
    print_success "Services stopped"
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
    docker-compose ps
    
    echo ""
    print_info "Access URLs:"
    echo "  • Web App:       http://localhost:8000"
    echo "  • PgAdmin:       http://localhost:5050"
    echo "  • Flower:        http://localhost:5555"
    
    if [ "$USE_GPU" = true ]; then
        echo "  • RAG API:       http://localhost:8001"
        echo "  • Ollama API:    http://localhost:11434"
    fi
    
    echo ""
    print_info "Logs:"
    echo "  • View all:      docker-compose logs -f"
    echo "  • View web:      docker-compose logs -f web"
    echo "  • View celery:   docker-compose logs -f celery_worker"
    
    if [ "$USE_GPU" = true ]; then
        echo "  • View RAG:      docker-compose -f $COMPOSE_FILE -f $GPU_COMPOSE_FILE logs -f rag_service"
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  start         Start all services"
    echo "  stop          Stop all services"
    echo "  restart       Restart all services"
    echo "  build         Build containers"
    echo "  clean         Clean temporary data"
    echo "  logs          Show logs"
    echo "  status        Show service status"
    echo "  health        Run health checks"
    echo ""
    echo "Options:"
    echo "  --gpu         Enable GPU support for RAG/LLM"
    echo "  --no-cache    Build without cache"
    echo "  --help        Show this help message"
}

# Main script
main() {
    print_header
    
    # Parse arguments
    NO_CACHE=""
    COMMAND=""
    
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
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            start|stop|restart|build|clean|logs|status|health)
                COMMAND=$1
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Default command
    if [ -z "$COMMAND" ]; then
        COMMAND="start"
    fi
    
    # Execute command
    case $COMMAND in
        start)
            setup_logging
            build_containers
            start_services
            sleep 10
            health_check
            show_status
            ;;
        stop)
            stop_services
            ;;
        restart)
            stop_services
            clear_temp_data
            setup_logging
            start_services
            sleep 10
            health_check
            show_status
            ;;
        build)
            setup_logging
            build_containers
            ;;
        clean)
            clear_temp_data
            ;;
        logs)
            if [ "$USE_GPU" = true ]; then
                docker-compose -f "$COMPOSE_FILE" -f "$GPU_COMPOSE_FILE" logs -f
            else
                docker-compose -f "$COMPOSE_FILE" logs -f
            fi
            ;;
        status)
            show_status
            ;;
        health)
            health_check
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
