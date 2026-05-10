#!/bin/bash

# Distributed Web Crawler Deployment Script
# This script deploys the complete distributed crawler system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
    fi
    
    # Check available memory
    TOTAL_MEMORY=$(free -m | awk 'NR==2{printf "%.0f", $2}')
    if [ "$TOTAL_MEMORY" -lt 16000 ]; then
        warning "System has less than 16GB RAM. Performance may be affected."
    fi
    
    # Check available disk space
    AVAILABLE_SPACE=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [ "$AVAILABLE_SPACE" -lt 100 ]; then
        error "Less than 100GB disk space available. Please free up space."
    fi
    
    log "Prerequisites check completed."
}

# Setup environment
setup_environment() {
    log "Setting up environment..."
    
    # Create necessary directories
    mkdir -p data logs httpcache monitoring/sql monitoring/grafana
    
    # Copy environment file if not exists
    if [ ! -f .env ]; then
        cp .env.example .env
        warning "Created .env from template. Please review and update configuration."
    fi
    
    # Set permissions
    chmod 755 scripts/*.sh
    
    log "Environment setup completed."
}

# Build Docker images
build_images() {
    log "Building Docker images..."
    
    docker-compose build --no-cache
    
    log "Docker images built successfully."
}

# Start services
start_services() {
    log "Starting services..."
    
    # Start core services first
    docker-compose up -d redis postgres
    
    # Wait for services to be ready
    log "Waiting for Redis to be ready..."
    while ! docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
        sleep 2
    done
    
    log "Waiting for PostgreSQL to be ready..."
    while ! docker-compose exec -T postgres pg_isready -U crawler > /dev/null 2>&1; do
        sleep 2
    done
    
    # Start monitoring services
    docker-compose up -d prometheus grafana
    
    # Start crawler workers
    docker-compose up -d scrapy-worker-1 scrapy-worker-2 scrapy-worker-3 scrapy-worker-4
    
    log "All services started successfully."
}

# Initialize crawler
initialize_crawler() {
    log "Initializing crawler..."
    
    # Load seed URLs into Redis
    python scripts/load_seed_urls.py
    
    # Verify Redis queue
    QUEUE_SIZE=$(docker-compose exec -T redis redis-cli llen nigerian_news:start_urls)
    log "Loaded $QUEUE_SIZE seed URLs into Redis queue."
    
    log "Crawler initialization completed."
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Check all services are running
    SERVICES=("redis" "postgres" "prometheus" "grafana" "scrapy-worker-1" "scrapy-worker-2" "scrapy-worker-3" "scrapy-worker-4")
    
    for service in "${SERVICES[@]}"; do
        if docker-compose ps | grep -q "$service.*Up"; then
            log "✓ $service is running"
        else
            error "✗ $service is not running"
        fi
    done
    
    # Check Prometheus metrics
    if curl -s http://localhost:9090/api/v1/query?query=up > /dev/null; then
        log "✓ Prometheus metrics endpoint is accessible"
    else
        warning "Prometheus metrics endpoint is not accessible"
    fi
    
    # Check Grafana dashboard
    if curl -s http://localhost:3000/api/health > /dev/null; then
        log "✓ Grafana dashboard is accessible"
    else
        warning "Grafana dashboard is not accessible"
    fi
    
    log "Deployment verification completed."
}

# Show status
show_status() {
    log "System Status:"
    echo ""
    
    # Docker Compose status
    docker-compose ps
    echo ""
    
    # Redis queue status
    QUEUE_SIZE=$(docker-compose exec -T redis redis-cli llen nigerian_news:requests)
    echo "Redis queue size: $QUEUE_SIZE URLs"
    
    # Crawler statistics
    ITEMS_SCRAPED=$(docker-compose exec -T redis redis-cli get nigerian_news:stats:items_scraped || echo "0")
    echo "Items scraped: $ITEMS_SCRAPED"
    
    # Resource usage
    echo ""
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
}

# Monitoring URLs
show_monitoring_info() {
    log "Monitoring URLs:"
    echo ""
    echo "📊 Grafana Dashboard: http://localhost:3000 (admin/admin)"
    echo "📈 Prometheus: http://localhost:9090"
    echo "🔍 Redis Commander: http://localhost:8081"
    echo "🗄️  pgAdmin: http://localhost:5050 (admin@university.edu/admin)"
    echo ""
    echo "📋 Crawler Logs: docker-compose logs -f scrapy-worker-1"
    echo "🔧 System Logs: docker-compose logs -f"
}

# Main deployment function
deploy() {
    log "Starting distributed web crawler deployment..."
    
    check_prerequisites
    setup_environment
    build_images
    start_services
    initialize_crawler
    verify_deployment
    show_status
    show_monitoring_info
    
    log "Deployment completed successfully!"
    echo ""
    echo "🎯 The distributed crawler is now running and collecting Nigerian news articles."
    echo "📊 Monitor progress at: http://localhost:3000"
    echo "📈 Check metrics at: http://localhost:9090"
}

# Cleanup function
cleanup() {
    log "Cleaning up..."
    
    # Stop all services
    docker-compose down
    
    # Remove unused images
    docker image prune -f
    
    # Clean up old logs (keep last 7 days)
    find logs/ -name "*.log" -mtime +7 -delete 2>/dev/null || true
    
    log "Cleanup completed."
}

# Scale workers
scale_workers() {
    local scale_count=$1
    
    if [ -z "$scale_count" ]; then
        error "Please provide the number of workers to scale to."
    fi
    
    log "Scaling workers to $scale_count instances..."
    
    docker-compose up -d --scale scrapy-worker=$scale_count
    
    log "Workers scaled to $scale_count instances."
}

# Backup data
backup_data() {
    local backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    
    log "Creating backup in $backup_dir..."
    
    mkdir -p "$backup_dir"
    
    # Backup SQLite databases
    cp data/*.db "$backup_dir/" 2>/dev/null || true
    
    # Backup PostgreSQL
    docker-compose exec -T postgres pg_dump -U crawler crawler_db > "$backup_dir/postgres_backup.sql"
    
    # Backup configuration
    cp .env "$backup_dir/"
    cp -r monitoring "$backup_dir/"
    
    # Create backup info
    cat > "$backup_dir/backup_info.txt" << EOF
Backup created: $(date)
Total items scraped: $(docker-compose exec -T redis redis-cli get nigerian_news:stats:items_scraped || echo "0")
Queue size: $(docker-compose exec -T redis redis-cli llen nigerian_news:requests)
EOF
    
    log "Backup completed: $backup_dir"
}

# Show help
show_help() {
    echo "Distributed Web Crawler Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy      - Deploy the complete crawler system"
    echo "  start       - Start all services"
    echo "  stop        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  status      - Show system status"
    echo "  scale N     - Scale workers to N instances"
    echo "  backup      - Create data backup"
    echo "  cleanup     - Stop services and clean up"
    echo "  logs        - Show crawler logs"
    echo "  help        - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy           # Full deployment"
    echo "  $0 scale 8          # Scale to 8 workers"
    echo "  $0 backup           # Create backup"
    echo "  $0 logs             # Show logs"
}

# Main script logic
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    start)
        log "Starting services..."
        docker-compose up -d
        ;;
    stop)
        log "Stopping services..."
        docker-compose down
        ;;
    restart)
        log "Restarting services..."
        docker-compose restart
        ;;
    status)
        show_status
        ;;
    scale)
        scale_workers "$2"
        ;;
    backup)
        backup_data
        ;;
    cleanup)
        cleanup
        ;;
    logs)
        docker-compose logs -f scrapy-worker-1 scrapy-worker-2 scrapy-worker-3 scrapy-worker-4
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        error "Unknown command: $1. Use 'help' for available commands."
        ;;
esac
