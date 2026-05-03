#!/bin/bash
# =============================================================================
# FKS Discord Webhook Test Script
# =============================================================================
#
# Tests the Discord webhook integration with AlertManager.
#
# Usage:
#   ./test-discord-webhook.sh <DISCORD_WEBHOOK_GENERAL>
#
# Or set the environment variable:
#   export DISCORD_WEBHOOK_GENERAL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN"
#   ./test-discord-webhook.sh
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}  FKS Discord Webhook Test${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# Get webhook URL from argument or environment
WEBHOOK_URL="${1:-$DISCORD_WEBHOOK_GENERAL}"

if [ -z "$WEBHOOK_URL" ]; then
    echo -e "${RED}Error: No Discord webhook URL provided!${NC}"
    echo ""
    echo "Usage:"
    echo "  $0 <DISCORD_WEBHOOK_GENERAL>"
    echo ""
    echo "Or set the environment variable:"
    echo "  export DISCORD_WEBHOOK_GENERAL=\"https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN\""
    echo "  $0"
    echo ""
    echo "To create a webhook:"
    echo "  1. Go to your Discord server settings"
    echo "  2. Navigate to Integrations > Webhooks"
    echo "  3. Create a new webhook"
    echo "  4. Copy the webhook URL"
    exit 1
fi

# Validate URL format
if [[ ! "$WEBHOOK_URL" =~ ^https://discord\.com/api/webhooks/ ]]; then
    echo -e "${YELLOW}Warning: URL doesn't look like a Discord webhook URL${NC}"
    echo "Expected format: https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN"
    echo ""
fi

echo -e "${BLUE}Testing webhook URL: ${NC}${WEBHOOK_URL:0:60}..."
echo ""

# Test 1: Direct Discord embed format
echo -e "${YELLOW}Test 1: Sending direct Discord embed...${NC}"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$WEBHOOK_URL" \
    -d '{
        "content": null,
        "embeds": [{
            "title": "🔔 FKS Test Alert",
            "description": "This is a test message from the FKS trading platform.\n\n**Status:** Test\n**Service:** AlertManager\n**Time:** '"$(date -u +"%Y-%m-%d %H:%M:%S UTC")"'",
            "color": 3066993,
            "footer": {
                "text": "FKS Trading Platform"
            },
            "timestamp": "'"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'"
        }]
    }')

if [ "$RESPONSE" = "204" ] || [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ Test 1 passed! (HTTP $RESPONSE)${NC}"
else
    echo -e "${RED}✗ Test 1 failed (HTTP $RESPONSE)${NC}"
fi

sleep 1

# Test 2: Slack-compatible format (used by AlertManager)
echo -e "${YELLOW}Test 2: Sending Slack-compatible format (AlertManager style)...${NC}"

# For Slack format, append /slack to the URL
SLACK_URL="${WEBHOOK_URL}/slack"

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$SLACK_URL" \
    -d '{
        "channel": "#fks-alerts",
        "username": "FKS AlertManager",
        "icon_emoji": ":chart_with_upwards_trend:",
        "attachments": [{
            "color": "warning",
            "title": "⚠️ FKS Test Alert (Slack Format)",
            "text": "*Status:* TEST\n*Summary:* This is a test alert using Slack-compatible format\n*Description:* If you see this message, AlertManager Discord integration is working correctly!\n*Service:* test-service\n*Instance:* test-instance",
            "footer": "FKS AlertManager Test",
            "ts": '"$(date +%s)"'
        }]
    }')

if [ "$RESPONSE" = "204" ] || [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ Test 2 passed! (HTTP $RESPONSE)${NC}"
else
    echo -e "${RED}✗ Test 2 failed (HTTP $RESPONSE)${NC}"
    echo -e "${YELLOW}Note: Slack format requires /slack appended to webhook URL${NC}"
fi

sleep 1

# Test 3: Simulate a critical alert
echo -e "${YELLOW}Test 3: Simulating critical alert...${NC}"

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$SLACK_URL" \
    -d '{
        "channel": "#fks-critical",
        "username": "FKS Critical Alerts",
        "icon_emoji": ":rotating_light:",
        "attachments": [{
            "color": "danger",
            "title": "🚨 CRITICAL: HighExecutionLatency (TEST)",
            "text": "*Summary:* Execution latency exceeded threshold\n*Description:* Order execution latency has exceeded 1000ms for the past 5 minutes\n*Severity:* critical\n*Instance:* execution:8081\n*Service:* execution\n\n<http://localhost:3000/d/fks-trading-main|View Dashboard> | <http://localhost:9093/#/silences/new|Silence Alert>",
            "footer": "FKS AlertManager Test - This is a test, not a real alert",
            "ts": '"$(date +%s)"'
        }]
    }')

if [ "$RESPONSE" = "204" ] || [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ Test 3 passed! (HTTP $RESPONSE)${NC}"
else
    echo -e "${RED}✗ Test 3 failed (HTTP $RESPONSE)${NC}"
fi

sleep 1

# Test 4: Simulate a resolved alert
echo -e "${YELLOW}Test 4: Simulating resolved alert...${NC}"

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$SLACK_URL" \
    -d '{
        "channel": "#fks-alerts",
        "username": "FKS AlertManager",
        "icon_emoji": ":white_check_mark:",
        "attachments": [{
            "color": "good",
            "title": "✅ RESOLVED: HighExecutionLatency (TEST)",
            "text": "*Status:* RESOLVED\n*Summary:* Execution latency back to normal\n*Description:* The alert condition is no longer firing\n*Service:* execution",
            "footer": "FKS AlertManager Test",
            "ts": '"$(date +%s)"'
        }]
    }')

if [ "$RESPONSE" = "204" ] || [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ Test 4 passed! (HTTP $RESPONSE)${NC}"
else
    echo -e "${RED}✗ Test 4 failed (HTTP $RESPONSE)${NC}"
fi

echo ""
echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""
echo "Check your Discord channel for the test messages!"
echo ""
echo -e "${YELLOW}To configure AlertManager with this webhook:${NC}"
echo ""
echo "1. Export the environment variable before starting docker-compose:"
echo -e "   ${GREEN}export DISCORD_WEBHOOK_GENERAL=\"$WEBHOOK_URL\"${NC}"
echo ""
echo "2. Or add it to your .env file:"
echo -e "   ${GREEN}DISCORD_WEBHOOK_GENERAL=$WEBHOOK_URL${NC}"
echo ""
echo "3. Restart AlertManager:"
echo -e "   ${GREEN}docker compose restart alertmanager${NC}"
echo ""
echo -e "${BLUE}=============================================${NC}"
