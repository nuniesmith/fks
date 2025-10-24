#!/bin/bash
# quick_start.sh
# One-command setup for the fks trading tool

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════╗"
echo "║   Advanced FKS Trading Tool - Quick Start Setup    ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your database password!"
    echo "   Default credentials are set, but please change them for security."
    echo ""
    read -p "Press Enter to continue with default credentials or Ctrl+C to exit and edit .env..."
fi

echo ""
echo "🐳 Step 1/4: Starting Docker services..."
docker-compose up -d db redis pgadmin

echo ""
echo "⏳ Step 2/4: Waiting for database to initialize (30 seconds)..."
sleep 30

echo ""
echo "✅ Step 3/4: Verifying database setup..."
docker-compose exec -T db psql -U fks_user -d fks_db -c "\dt" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "   ✓ Database initialized successfully"
else
    echo "   ✗ Database initialization failed"
    echo "   Check logs: docker-compose logs db"
    exit 1
fi

echo ""
echo "📊 Step 4/4: Syncing historical data (this may take 20-30 minutes)..."
echo "   Fetching 2 years of data for 5 symbols × 9 timeframes = 45 datasets"
echo ""
read -p "Start data sync now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose run --rm web python data_sync_service.py init
    
    echo ""
    echo "✅ Data sync completed! Checking status..."
    docker-compose run --rm web python data_sync_service.py status
else
    echo ""
    echo "⚠️  Skipping data sync. Run manually later:"
    echo "   docker-compose run --rm web python data_sync_service.py init"
fi

echo ""
echo "🚀 Starting web application..."
docker-compose up -d web

sleep 5

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║              Setup Complete! 🎉                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Access Points:"
echo "   • Web App:  http://localhost:8501"
echo "   • pgAdmin:  http://localhost:5050"
echo "   • Database: localhost:5432"
echo ""
echo "📚 Quick Commands:"
echo "   • View logs:        docker-compose logs -f web"
echo "   • Stop services:    docker-compose down"
echo "   • Restart:          docker-compose restart web"
echo "   • Sync data:        docker-compose run --rm web python data_sync_service.py update"
echo "   • Check DB status:  docker-compose run --rm web python data_sync_service.py status"
echo ""
echo "📖 Full documentation: See README.md"
echo ""
