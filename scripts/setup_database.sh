#!/bin/bash
# setup_database.sh
# Script to initialize the database and sync historical data

echo "================================================"
echo "FKS Trading Tool - Database Setup"
echo "================================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

echo "Step 1: Starting Docker containers..."
docker-compose up -d db redis

echo ""
echo "Waiting for PostgreSQL to be ready..."
sleep 10

echo ""
echo "Step 2: Checking database initialization..."
docker-compose exec db psql -U ${DB_USER:-fks_user} -d ${DB_NAME:-fks_db} -c "\dt" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Database tables created successfully"
else
    echo "❌ Error: Database initialization failed"
    echo "Check docker logs: docker-compose logs db"
    exit 1
fi

echo ""
echo "Step 3: Starting pgAdmin..."
docker-compose up -d pgadmin

echo ""
echo "================================================"
echo "Database Setup Complete!"
echo "================================================"
echo ""
echo "📊 pgAdmin is available at: http://localhost:5050"
echo "   Email: ${PGADMIN_EMAIL:-admin@fks.local}"
echo "   Password: (check your .env file)"
echo ""
echo "🗄️  PostgreSQL connection details:"
echo "   Host: localhost (or 'db' from within Docker)"
echo "   Port: 5432"
echo "   Database: ${DB_NAME:-fks_db}"
echo "   User: ${DB_USER:-fks_user}"
echo ""
echo "Next steps:"
echo "1. Sync historical data:"
echo "   docker-compose run --rm web python data_sync_service.py init"
echo ""
echo "2. Start the web application:"
echo "   docker-compose up -d web"
echo ""
echo "3. Access the app at: http://localhost:8501"
echo ""
