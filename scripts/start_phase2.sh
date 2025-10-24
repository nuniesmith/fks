#!/bin/bash
# start_phase2.sh
# Quick start script for Phase 2 with WebSocket support

echo "╔════════════════════════════════════════════════════════╗"
echo "║   Phase 2: Real-Time Features & Persistent State      ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check if Phase 1 is complete
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please complete Phase 1 setup first:"
    echo "  ./quick_start.sh"
    exit 1
fi

echo "🔨 Step 1/4: Rebuilding Docker images with new dependencies..."
docker-compose build --no-cache web websocket

echo ""
echo "🚀 Step 2/4: Starting all services (including WebSocket)..."
docker-compose up -d

echo ""
echo "⏳ Step 3/4: Waiting for WebSocket to connect (10 seconds)..."
sleep 10

echo ""
echo "✅ Step 4/4: Checking WebSocket connection..."
docker-compose logs --tail=20 websocket

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║            Phase 2 Services Started! 🎉                ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Access Points:"
echo "   • Enhanced App: http://localhost:8501"
echo "   • pgAdmin:      http://localhost:5050"
echo "   • Database:     localhost:5432"
echo ""
echo "🔌 WebSocket Status:"
echo "   Check sidebar in web app for connection status"
echo "   Should show: ✅ Live Data Connected"
echo ""
echo "💡 Features:"
echo "   ✅ Live price updates every 5 seconds"
echo "   ✅ Session state persists across refreshes"
echo "   ✅ Multi-account support"
echo "   ✅ Real-time PnL tracking"
echo "   ✅ Live mini-charts"
echo ""
echo "📚 Commands:"
echo "   • View logs:          docker-compose logs -f [web|websocket]"
echo "   • Restart WebSocket:  docker-compose restart websocket"
echo "   • Stop all:           docker-compose down"
echo "   • Check WS status:    docker-compose exec redis redis-cli GET ws:connection_status"
echo ""
echo "📖 Full documentation: See PHASE2_SUMMARY.md"
echo ""
