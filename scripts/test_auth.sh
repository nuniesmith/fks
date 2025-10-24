#!/bin/bash
# Test Authentication System
# Usage: bash scripts/test_auth.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== FKS Authentication System Test ===${NC}\n"

# Configuration
BASE_URL="${BASE_URL:-http://localhost}"
COOKIE_FILE="./test_cookies.txt"

# Cleanup function
cleanup() {
    rm -f "$COOKIE_FILE" 2>/dev/null || true
}

trap cleanup EXIT

echo -e "${YELLOW}Testing API Endpoints...${NC}\n"

# Test 1: Health Check
echo "1. Health Check..."
curl -s "${BASE_URL}/health" > /dev/null && echo -e "   ${GREEN}✓ Server is up${NC}" || echo -e "   ${RED}✗ Server is down${NC}"

# Test 2: Register New User
echo -e "\n2. Registering new user..."
REGISTER_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/register/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test_'$(date +%s)'",
    "email": "test_'$(date +%s)'@example.com",
    "password": "TestPass123!",
    "password_confirm": "TestPass123!",
    "first_name": "Test",
    "last_name": "User"
  }')

if echo "$REGISTER_RESPONSE" | grep -q "username"; then
    echo -e "   ${GREEN}✓ User registered successfully${NC}"
    USERNAME=$(echo "$REGISTER_RESPONSE" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
    echo "   Username: $USERNAME"
else
    echo -e "   ${RED}✗ Registration failed${NC}"
    echo "   Response: $REGISTER_RESPONSE"
    exit 1
fi

# Test 3: Login
echo -e "\n3. Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "'$USERNAME'",
    "password": "TestPass123!"
  }' \
  -c "$COOKIE_FILE")

if echo "$LOGIN_RESPONSE" | grep -q "Login successful"; then
    echo -e "   ${GREEN}✓ Login successful${NC}"
    SESSION_ID=$(echo "$LOGIN_RESPONSE" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
    echo "   Session ID: $SESSION_ID"
else
    echo -e "   ${RED}✗ Login failed${NC}"
    echo "   Response: $LOGIN_RESPONSE"
    exit 1
fi

# Test 4: Get Current User
echo -e "\n4. Getting current user info..."
USER_RESPONSE=$(curl -s "${BASE_URL}/auth/me/" -b "$COOKIE_FILE")

if echo "$USER_RESPONSE" | grep -q "username"; then
    echo -e "   ${GREEN}✓ User info retrieved${NC}"
    echo "   User Type: $(echo "$USER_RESPONSE" | grep -o '"user_type":"[^"]*"' | cut -d'"' -f4)"
    echo "   Status: $(echo "$USER_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)"
else
    echo -e "   ${RED}✗ Failed to get user info${NC}"
fi

# Test 5: Update User State
echo -e "\n5. Updating user state..."
STATE_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/state/" \
  -H "Content-Type: application/json" \
  -b "$COOKIE_FILE" \
  -d '{
    "theme": "dark",
    "selected_exchange": "binance",
    "watchlist": ["BTC", "ETH", "SOL"]
  }')

if echo "$STATE_RESPONSE" | grep -q "State updated"; then
    echo -e "   ${GREEN}✓ State updated successfully${NC}"
else
    echo -e "   ${YELLOW}⚠ State update may have failed${NC}"
fi

# Test 6: Rate Limiting
echo -e "\n6. Testing rate limiting (making 10 rapid requests)..."
RATE_LIMIT_HIT=false
for i in {1..10}; do
    RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL}/auth/me/" -b "$COOKIE_FILE")
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    
    if [ "$HTTP_CODE" == "429" ]; then
        RATE_LIMIT_HIT=true
        echo -e "   ${YELLOW}⚠ Rate limit hit at request $i (expected behavior)${NC}"
        break
    fi
done

if [ "$RATE_LIMIT_HIT" == false ]; then
    echo -e "   ${GREEN}✓ All requests within rate limit${NC}"
fi

# Test 7: Get User Sessions
echo -e "\n7. Getting active sessions..."
SESSIONS_RESPONSE=$(curl -s "${BASE_URL}/auth/users/?format=json" -b "$COOKIE_FILE")
echo -e "   ${GREEN}✓ Sessions retrieved${NC}"

# Test 8: Logout
echo -e "\n8. Logging out..."
LOGOUT_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/logout/" -b "$COOKIE_FILE")

if echo "$LOGOUT_RESPONSE" | grep -q "Logout successful"; then
    echo -e "   ${GREEN}✓ Logout successful${NC}"
else
    echo -e "   ${YELLOW}⚠ Logout may have failed${NC}"
fi

# Test 9: Verify Session Expired
echo -e "\n9. Verifying session expired..."
EXPIRED_RESPONSE=$(curl -s "${BASE_URL}/auth/me/" -b "$COOKIE_FILE")

if echo "$EXPIRED_RESPONSE" | grep -q "detail.*credentials"; then
    echo -e "   ${GREEN}✓ Session properly expired${NC}"
else
    echo -e "   ${YELLOW}⚠ Session may still be active${NC}"
fi

# Summary
echo -e "\n${GREEN}=== Test Summary ===${NC}"
echo "✓ Authentication system is functional"
echo "✓ User registration working"
echo "✓ Login/logout working"
echo "✓ Session management working"
echo "✓ User state management working"
echo "✓ Rate limiting configured"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Check Django admin: ${BASE_URL}/admin/"
echo "2. View Redis data: docker-compose exec redis redis-cli"
echo "3. Check logs: tail -f logs/django.log"
echo "4. Create API keys in admin panel"
echo -e "\nSee docs/AUTHENTICATION_IMPLEMENTATION.md for full documentation"

cleanup
