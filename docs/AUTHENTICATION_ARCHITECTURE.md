# Authentication Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Browser │  │  Mobile  │  │   API    │  │  Trading │       │
│  │    UI    │  │   App    │  │  Client  │  │   Bot    │       │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘       │
│        │             │              │              │             │
│        └─────────────┴──────────────┴──────────────┘             │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      NGINX LAYER (Port 80/443)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • SSL Termination                                        │  │
│  │  • Rate Limiting (IP-based)                               │  │
│  │  • Basic Auth (Optional for /admin, /flower, /pgadmin)   │  │
│  │  • Load Balancing                                         │  │
│  │  • Static File Serving                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DJANGO APPLICATION LAYER                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              AUTHENTICATION MIDDLEWARE STACK              │  │
│  │  1. SessionMiddleware     - Load session from Redis       │  │
│  │  2. AuthenticationMiddleware - Identify user              │  │
│  │  3. APIKeyAuthMiddleware  - Validate API keys             │  │
│  │  4. SessionTrackingMiddleware - Track activity            │  │
│  │  5. RateLimitMiddleware   - Per-user rate limits          │  │
│  │  6. UserStateMiddleware   - Attach user state             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    AUTHENTICATION APP                     │  │
│  │  • User Management (CRUD)                                 │  │
│  │  • Session Management                                     │  │
│  │  • API Key Management                                     │  │
│  │  • Permission Checking                                    │  │
│  │  • Rate Limit Enforcement                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
    ┌───────────────────────┐  ┌──────────────────┐
    │   POSTGRESQL DB       │  │   REDIS CACHE    │
    │  ┌─────────────────┐  │  │  ┌────────────┐ │
    │  │ Users           │  │  │  │ Sessions   │ │
    │  │ UserProfiles    │  │  │  │ States     │ │
    │  │ APIKeys         │  │  │  │ Rate Limits│ │
    │  │ UserSessions    │  │  │  │ API Usage  │ │
    │  └─────────────────┘  │  │  └────────────┘ │
    └───────────────────────┘  └──────────────────┘
```

## Authentication Flow

### 1. User Login (Session-based)

```
┌─────────┐                  ┌─────────┐                  ┌──────────┐
│ Client  │                  │ Django  │                  │  Redis   │
└────┬────┘                  └────┬────┘                  └────┬─────┘
     │                            │                            │
     │ POST /auth/login/          │                            │
     │ {username, password}       │                            │
     ├───────────────────────────►│                            │
     │                            │                            │
     │                            │ Validate credentials       │
     │                            │ (PostgreSQL)               │
     │                            │                            │
     │                            │ Create session             │
     │                            ├───────────────────────────►│
     │                            │                            │
     │                            │ Store session data         │
     │                            │◄───────────────────────────┤
     │                            │                            │
     │                            │ Track session metadata     │
     │                            │ (UserSession model)        │
     │                            │                            │
     │◄───────────────────────────┤                            │
     │ Set-Cookie: sessionid      │                            │
     │ {user_data}                │                            │
     │                            │                            │
     
     ┌─── Subsequent Requests ────────────────────────────────┐
     │                            │                            │
     │ GET /auth/me/              │                            │
     │ Cookie: sessionid          │                            │
     ├───────────────────────────►│                            │
     │                            │                            │
     │                            │ Load session from Redis    │
     │                            ├───────────────────────────►│
     │                            │◄───────────────────────────┤
     │                            │                            │
     │                            │ Attach user to request     │
     │                            │                            │
     │◄───────────────────────────┤                            │
     │ {user_data}                │                            │
     │                            │                            │
```

### 2. API Key Authentication

```
┌─────────┐                  ┌─────────┐                  ┌──────────┐
│ Bot/API │                  │ Django  │                  │  Redis   │
└────┬────┘                  └────┬────┘                  └────┬─────┘
     │                            │                            │
     │ GET /api/v1/data           │                            │
     │ X-API-Key: abc123...       │                            │
     ├───────────────────────────►│                            │
     │                            │                            │
     │                            │ APIKeyAuthMiddleware       │
     │                            │                            │
     │                            │ Validate API key           │
     │                            │ (PostgreSQL)               │
     │                            │                            │
     │                            │ Check rate limit           │
     │                            ├───────────────────────────►│
     │                            │◄───────────────────────────┤
     │                            │                            │
     │                            │ Increment usage            │
     │                            ├───────────────────────────►│
     │                            │                            │
     │                            │ Attach user to request     │
     │                            │                            │
     │◄───────────────────────────┤                            │
     │ X-RateLimit-Remaining: 99  │                            │
     │ {response_data}            │                            │
     │                            │                            │
```

### 3. Rate Limiting Flow

```
Request arrives
      │
      ▼
┌──────────────────────────┐
│ Extract Identifier       │
│ - User ID (auth)         │
│ - IP Address (anon)      │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Check Redis              │
│ Key: rate_limit:{id}     │
│ Counter: current_count   │
└──────────┬───────────────┘
           │
           ▼
      ┌────────┐
      │ Count  │
  ┌───┤ < Limit├───┐
  │   └────────┘   │
  │                │
  ▼ Yes            ▼ No
┌──────────┐   ┌─────────────────┐
│ Increment│   │ Return 429      │
│ Counter  │   │ Too Many Reqs   │
└────┬─────┘   │ Retry-After: 60 │
     │         └─────────────────┘
     ▼
┌──────────────────────────┐
│ Allow Request            │
│ Add Rate Limit Headers:  │
│ X-RateLimit-Limit: 300   │
│ X-RateLimit-Remaining: X │
└──────────────────────────┘
```

### 4. User State Management

```
┌─────────┐                  ┌─────────┐                  ┌──────────┐
│  User   │                  │ Django  │                  │  Redis   │
└────┬────┘                  └────┬────┘                  └────┬─────┘
     │                            │                            │
     │ POST /auth/state/          │                            │
     │ {theme: "dark", ...}       │                            │
     ├───────────────────────────►│                            │
     │                            │                            │
     │                            │ user.set_user_state()      │
     │                            │                            │
     │                            │ SET user:{id}:state        │
     │                            ├───────────────────────────►│
     │                            │                            │
     │◄───────────────────────────┤                            │
     │ {success}                  │                            │
     │                            │                            │
     
     ┌─── Retrieve State ──────────────────────────────────────┐
     │                            │                            │
     │ GET /auth/me/              │                            │
     ├───────────────────────────►│                            │
     │                            │                            │
     │                            │ user.get_user_state()      │
     │                            │                            │
     │                            │ GET user:{id}:state        │
     │                            ├───────────────────────────►│
     │                            │◄───────────────────────────┤
     │                            │                            │
     │◄───────────────────────────┤                            │
     │ {user_data, state}         │                            │
     │                            │                            │
```

## Permission Hierarchy

```
┌──────────────────────────────────────────────────────┐
│                      ADMIN                           │
│  • All Features                                      │
│  • User Management                                   │
│  • System Configuration                              │
│  • No Rate Limits                                    │
└──────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐           ┌──────────────────┐
│     TRADER       │           │     ANALYST      │
│  • Trading       │           │  • Analytics     │
│  • Backtest      │           │  • Backtest      │
│  • Analytics     │           │  • Reports       │
│  • API Access    │           │  • Read-only     │
│  • 300 req/min   │           │  • 300 req/min   │
└──────────────────┘           └──────────────────┘
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
                ┌──────────────────┐
                │     VIEWER       │
                │  • Dashboard     │
                │  • Reports       │
                │  • 300 req/min   │
                └──────────────────┘
```

## Session Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                      SESSION CREATION                        │
│  1. User logs in                                             │
│  2. Django creates session in Redis                          │
│  3. UserSession record created in PostgreSQL                 │
│  4. Session added to user's session list (Redis)             │
│  5. Session cookie sent to client                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   ACTIVE SESSION PERIOD                      │
│  • Each request updates last_activity                        │
│  • User state can be updated                                 │
│  • Rate limits tracked per user                              │
│  • Concurrent session check on new logins                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   SESSION TERMINATION                        │
│  Triggers:                                                   │
│  • User logout                                               │
│  • Session expiration (7 days default)                       │
│  • Manual termination (admin)                                │
│  • Concurrent session limit exceeded                         │
│  • User suspension                                           │
│                                                              │
│  Actions:                                                    │
│  • UserSession.is_active = False                             │
│  • Remove from user's session list (Redis)                   │
│  • Clear session data from Redis                             │
└─────────────────────────────────────────────────────────────┘
```

## Multi-User Testing Scenarios

```
Scenario 1: Concurrent Sessions
┌──────────────────────────────────────────────────────────┐
│  User: test_trader (max_concurrent_sessions: 5)          │
│                                                           │
│  Login from:                                              │
│  1. Desktop (Chrome)    ✓ Active                          │
│  2. Mobile (Safari)     ✓ Active                          │
│  3. Laptop (Firefox)    ✓ Active                          │
│  4. Tablet (Edge)       ✓ Active                          │
│  5. Work PC (Chrome)    ✓ Active                          │
│  6. Home PC (Firefox)   ✓ Active (oldest session dropped) │
└──────────────────────────────────────────────────────────┘

Scenario 2: User States
┌──────────────────────────────────────────────────────────┐
│  User: test_analyst                                       │
│                                                           │
│  State stored in Redis:                                   │
│  {                                                        │
│    "theme": "dark",                                       │
│    "chart_timeframe": "1h",                               │
│    "selected_indicators": ["RSI", "MACD"],                │
│    "watchlist": ["BTC/USDT", "ETH/USDT"],                 │
│    "last_viewed": "BTC/USDT-4h",                          │
│    "notifications": {                                     │
│      "email": true,                                       │
│      "discord": false                                     │
│    }                                                      │
│  }                                                        │
│                                                           │
│  • Persists across sessions                               │
│  • Independent of session data                            │
│  • Fast access from Redis                                 │
└──────────────────────────────────────────────────────────┘

Scenario 3: API Key Usage
┌──────────────────────────────────────────────────────────┐
│  User: test_trader                                        │
│  API Key: Trading Bot v1                                  │
│  Rate Limit: 200 req/min                                  │
│                                                           │
│  Requests:                                                │
│  00:00 - Request 1-50     ✓ Allowed (remaining: 150)     │
│  00:00 - Request 51-100   ✓ Allowed (remaining: 100)     │
│  00:00 - Request 101-200  ✓ Allowed (remaining: 0)       │
│  00:00 - Request 201      ✗ 429 Too Many Requests        │
│  00:01 - Counter reset    ✓ Ready for new requests       │
└──────────────────────────────────────────────────────────┘
```

## Redis Key Structure

```
Redis Database 1 (Sessions & State)
├── user:1:state            → JSON: {theme, preferences, ...}
├── user:1:sessions         → JSON: [{session_id, device, ...}]
├── user:2:state
├── user:2:sessions
├── session_token:abc123    → JSON: {user_id, username, ...}
├── rate_limit:user:1       → Counter (TTL: 60s)
├── rate_limit:ip:1.2.3.4   → Counter (TTL: 60s)
├── api_key:xyz789:usage    → Counter (TTL: 60s)
└── django.contrib.sessions.*  → Session data

Key Patterns:
- user:{id}:state           → User state (TTL: 24h)
- user:{id}:sessions        → Active sessions (TTL: 7d)
- session_token:{token}     → Token auth (TTL: 24h)
- rate_limit:{type}:{id}    → Rate counters (TTL: 60s)
- api_key:{key}:usage       → API usage (TTL: 60s)
```

## Complete Request Flow

```
1. Request arrives at Nginx
   └─► SSL termination
   └─► Rate limit check (nginx level)
   └─► Optional basic auth (/admin, /flower)
   └─► Forward to Django

2. Django receives request
   └─► SessionMiddleware loads session from Redis
   └─► AuthenticationMiddleware identifies user
   └─► APIKeyAuthMiddleware (if API key present)
   └─► SessionTrackingMiddleware updates activity
   └─► RateLimitMiddleware checks user/IP limits
   └─► UserStateMiddleware attaches user state

3. View processes request
   └─► Check user.can_access_feature()
   └─► Check user.is_premium
   └─► Access user.get_user_state()
   └─► Process business logic

4. Response generated
   └─► Add rate limit headers
   └─► Update session if needed
   └─► Log activity
   └─► Return to client
```

This architecture provides:
- ✅ Scalable session management (Redis)
- ✅ Multiple authentication methods (Session + API Key)
- ✅ Fine-grained permissions (User types + Feature flags)
- ✅ Rate limiting at multiple levels (Nginx + Django + User)
- ✅ User state persistence (Redis)
- ✅ Session tracking and monitoring
- ✅ Ready for horizontal scaling
