#!/bin/bash
# test_installation.sh
# Quick test to verify everything is working correctly

echo "🧪 Testing FKS Trading Tool Installation"
echo "=============================================="
echo ""

# Test 1: Check Docker
echo "Test 1: Docker is running..."
if docker info > /dev/null 2>&1; then
    echo "   ✅ Docker is running"
else
    echo "   ❌ Docker is not running"
    echo "   Please start Docker first"
    exit 1
fi

# Test 2: Check containers
echo ""
echo "Test 2: Checking containers..."
RUNNING=$(docker-compose ps --services --filter "status=running" 2>/dev/null | wc -l)
echo "   Running containers: $RUNNING"

if [ "$RUNNING" -ge 3 ]; then
    echo "   ✅ Core services are running"
else
    echo "   ⚠️  Some services may not be running"
    echo "   Run: docker-compose up -d"
fi

# Test 3: Database connection
echo ""
echo "Test 3: Testing database connection..."
docker-compose exec -T db psql -U fks_user -d fks_db -c "SELECT version();" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "   ✅ Database connection successful"
else
    echo "   ❌ Cannot connect to database"
    exit 1
fi

# Test 4: Check tables
echo ""
echo "Test 4: Checking database tables..."
TABLE_COUNT=$(docker-compose exec -T db psql -U fks_user -d fks_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')

if [ "$TABLE_COUNT" -ge 8 ]; then
    echo "   ✅ Found $TABLE_COUNT tables"
else
    echo "   ⚠️  Only found $TABLE_COUNT tables (expected 8+)"
fi

# Test 5: Check hypertables
echo ""
echo "Test 5: Checking TimescaleDB hypertables..."
HYPERTABLE_COUNT=$(docker-compose exec -T db psql -U fks_user -d fks_db -t -c "SELECT COUNT(*) FROM timescaledb_information.hypertables;" 2>/dev/null | tr -d ' ')

if [ "$HYPERTABLE_COUNT" -ge 3 ]; then
    echo "   ✅ Found $HYPERTABLE_COUNT hypertables"
else
    echo "   ⚠️  Only found $HYPERTABLE_COUNT hypertables (expected 4)"
fi

# Test 6: Check Redis
echo ""
echo "Test 6: Testing Redis connection..."
docker-compose exec -T redis redis-cli ping > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "   ✅ Redis connection successful"
else
    echo "   ❌ Cannot connect to Redis"
fi

# Test 7: Check data sync status
echo ""
echo "Test 7: Checking data sync status..."
SYNCED=$(docker-compose exec -T db psql -U fks_user -d fks_db -t -c "SELECT COUNT(*) FROM sync_status WHERE sync_status='completed';" 2>/dev/null | tr -d ' ')
TOTAL=$(docker-compose exec -T db psql -U fks_user -d fks_db -t -c "SELECT COUNT(*) FROM sync_status;" 2>/dev/null | tr -d ' ')

echo "   Synced: $SYNCED / $TOTAL datasets"

if [ "$SYNCED" -gt 0 ]; then
    echo "   ✅ Some data has been synced"
else
    echo "   ⚠️  No data synced yet"
    echo "   Run: docker-compose run --rm web python data_sync_service.py init"
fi

# Test 8: Check OHLCV data
echo ""
echo "Test 8: Checking OHLCV data..."
OHLCV_COUNT=$(docker-compose exec -T db psql -U fks_user -d fks_db -t -c "SELECT COUNT(*) FROM ohlcv_data;" 2>/dev/null | tr -d ' ')

if [ "$OHLCV_COUNT" -gt 0 ]; then
    echo "   ✅ Found $OHLCV_COUNT OHLCV records"
else
    echo "   ⚠️  No OHLCV data found"
    echo "   This is normal if you haven't run data sync yet"
fi

# Test 9: Check web app
echo ""
echo "Test 9: Checking web application..."
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo "   ✅ Web app is accessible at http://localhost:8501"
else
    echo "   ⚠️  Web app not accessible"
    echo "   Run: docker-compose up -d web"
fi

# Test 10: Check pgAdmin
echo ""
echo "Test 10: Checking pgAdmin..."
if curl -s http://localhost:5050 > /dev/null 2>&1; then
    echo "   ✅ pgAdmin is accessible at http://localhost:5050"
else
    echo "   ⚠️  pgAdmin not accessible"
    echo "   Run: docker-compose up -d pgadmin"
fi

# Summary
echo ""
echo "=============================================="
echo "📊 Test Summary"
echo "=============================================="
echo ""
echo "Services Status:"
docker-compose ps
echo ""
echo "📍 Access Points:"
echo "   • Web App:  http://localhost:8501"
echo "   • pgAdmin:  http://localhost:5050"
echo "   • Database: localhost:5432"
echo ""
echo "💡 Quick Commands:"
echo "   • View logs:     docker-compose logs -f web"
echo "   • Sync data:     docker-compose run --rm web python data_sync_service.py init"
echo "   • Check status:  docker-compose run --rm web python data_sync_service.py status"
echo "   • Restart:       docker-compose restart"
echo "   • Stop:          docker-compose down"
echo ""
