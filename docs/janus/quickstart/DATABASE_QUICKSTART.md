# JANUS Database Quick Start Guide

## Overview

This guide will help you set up and configure the PostgreSQL database for the JANUS signal generation service.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Docker Setup](#docker-setup)
- [Configuration](#configuration)
- [Running Migrations](#running-migrations)
- [Verification](#verification)
- [Common Issues](#common-issues)

---

## Prerequisites

- PostgreSQL 14 or later
- Rust 1.70+
- Docker (optional, for containerized setup)

---

## Local Development Setup

### 1. Install PostgreSQL

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### macOS (Homebrew)
```bash
brew install postgresql@14
brew services start postgresql@14
```

#### Windows
Download and install from: https://www.postgresql.org/download/windows/

### 2. Create Database and User

```bash
# Connect to PostgreSQL as postgres user
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE janus;
CREATE USER janus WITH PASSWORD 'janus_dev_password';
GRANT ALL PRIVILEGES ON DATABASE janus TO janus;

# For PostgreSQL 15+, also grant schema privileges:
\c janus
GRANT ALL ON SCHEMA public TO janus;

# Exit
\q
```

### 3. Set Environment Variables

```bash
# Add to ~/.bashrc, ~/.zshrc, or .env file
export DATABASE_URL="postgresql://janus:janus_dev_password@localhost:5432/janus"
export DB_MAX_CONNECTIONS=10
export DB_MIN_CONNECTIONS=2
export DB_ENABLE_LOGGING=false
```

### 4. Test Connection

```bash
# Using psql
psql -U janus -d janus -h localhost

# Or using connection string
psql $DATABASE_URL
```

---

## Docker Setup

### 1. Using Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:14-alpine
    container_name: janus-postgres
    environment:
      JANUS_DB: janus
      POSTGRES_USER: janus
      POSTGRES_PASSWORD: janus_dev_password
      POSTGRES_INITDB_ARGS: "-E UTF8"
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U janus"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
    driver: local
```

### 2. Start PostgreSQL

```bash
# Start the database
docker-compose up -d postgres

# Check logs
docker-compose logs -f postgres

# Verify it's running
docker-compose ps
```

### 3. Connect to Database

```bash
# Using docker exec
docker exec -it janus-postgres psql -U janus -d janus

# Or using psql from host
psql -h localhost -U janus -d janus
```

---

## Configuration

### Environment Variables

```bash
# Required
DATABASE_URL="postgresql://user:password@host:port/database"

# Optional (with defaults)
DB_MAX_CONNECTIONS=10          # Maximum pool size
DB_MIN_CONNECTIONS=2           # Minimum pool size
DB_CONNECT_TIMEOUT=30          # Connection timeout (seconds)
DB_IDLE_TIMEOUT=600           # Idle connection timeout (seconds)
DB_MAX_LIFETIME=1800          # Max connection lifetime (seconds)
DB_ENABLE_LOGGING=false       # Enable SQL query logging
```

### Using .env File

Create `.env` file in project root:

```env
# Database Configuration
DATABASE_URL=postgresql://janus:janus_dev_password@localhost:5432/janus
DB_MAX_CONNECTIONS=10
DB_MIN_CONNECTIONS=2
DB_ENABLE_LOGGING=false

# JANUS Service Configuration
JANUS_REST_PORT=8080
JANUS_GRPC_PORT=50051
JANUS_METRICS_PORT=9090
RUST_LOG=info,janus=debug
```

Load in your application:

```rust
use dotenv::dotenv;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Load .env file
    dotenv().ok();
    
    // Load database config from environment
    let config = DatabaseConfig::from_env()?;
    
    Ok(())
}
```

---

## Running Migrations

### Method 1: Embedded Migrations (Recommended)

Migrations are embedded in the application and run automatically:

```rust
use janus::persistence::{Database, DatabaseConfig};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config = DatabaseConfig::from_env()?;
    let db = Database::connect(config).await?;
    
    // Run all migrations
    db.run_migrations().await?;
    
    Ok(())
}
```

### Method 2: Manual SQL Execution

```bash
# Navigate to migrations directory
cd services/janus/migrations

# Run each migration in order
psql $DATABASE_URL -f 001_create_signals_table.sql
psql $DATABASE_URL -f 002_create_portfolio_tables.sql
psql $DATABASE_URL -f 003_create_metrics_tables.sql
```

### Method 3: Using sqlx-cli (Optional)

```bash
# Install sqlx-cli
cargo install sqlx-cli --no-default-features --features postgres

# Run migrations
sqlx migrate run --database-url $DATABASE_URL
```

---

## Verification

### 1. Check Database Connection

```rust
use janus::persistence::{Database, DatabaseConfig};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config = DatabaseConfig::from_env()?;
    let db = Database::connect(config).await?;
    
    // Health check
    db.health_check().await?;
    println!("✅ Database connection successful!");
    
    Ok(())
}
```

### 2. Verify Tables

```bash
# Connect to database
psql $DATABASE_URL

# List all tables
\dt

# Expected tables:
# - signals
# - portfolios
# - positions
# - position_updates
# - portfolio_snapshots
# - trade_metrics
# - performance_stats
# - risk_metrics
# - signal_performance
# - strategy_performance
```

### 3. Check Indexes

```sql
-- List all indexes
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- Should show 40+ indexes
```

### 4. Test Basic Operations

```rust
use janus::persistence::models::NewSignal;
use uuid::Uuid;
use chrono::Utc;

// Create signal repository
let signal_repo = db.signal_repository();

// Insert a test signal
let signal = NewSignal {
    signal_id: Uuid::new_v4(),
    symbol: "TEST/USD".to_string(),
    signal_type: "Buy".to_string(),
    timeframe: "1h".to_string(),
    confidence: 0.85,
    strength: 0.75,
    timestamp: Utc::now(),
    source_type: "test".to_string(),
    filtered: false,
    is_backtest: true,
    // ... other fields
};

let saved = signal_repo.create(signal).await?;
println!("✅ Signal saved: {}", saved.signal_id);

// Query the signal
let found = signal_repo.find_by_id(saved.signal_id).await?;
println!("✅ Signal retrieved: {}", found.symbol);
```

---

## Common Issues

### Issue 1: Connection Refused

```
Error: Connection refused (os error 111)
```

**Solution**:
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start if not running
sudo systemctl start postgresql

# Check if listening on correct port
sudo netstat -tulpn | grep 5432
```

### Issue 2: Authentication Failed

```
Error: password authentication failed for user "janus"
```

**Solution**:
```bash
# Reset password
sudo -u postgres psql
ALTER USER janus WITH PASSWORD 'new_password';

# Update DATABASE_URL with new password
export DATABASE_URL="postgresql://janus:new_password@localhost:5432/janus"
```

### Issue 3: Database Does Not Exist

```
Error: database "janus" does not exist
```

**Solution**:
```bash
# Create database
sudo -u postgres psql
CREATE DATABASE janus;
GRANT ALL PRIVILEGES ON DATABASE janus TO janus;
```

### Issue 4: Permission Denied

```
Error: permission denied for schema public
```

**Solution** (PostgreSQL 15+):
```bash
sudo -u postgres psql janus
GRANT ALL ON SCHEMA public TO janus;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO janus;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO janus;
```

### Issue 5: Too Many Connections

```
Error: sorry, too many clients already
```

**Solution**:
```bash
# Check current connections
sudo -u postgres psql
SELECT count(*) FROM pg_stat_activity;

# Increase max_connections in postgresql.conf
sudo nano /etc/postgresql/14/main/postgresql.conf
# Set: max_connections = 100

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Issue 6: Slow Queries

**Solution**:
```sql
-- Enable query logging
ALTER DATABASE janus SET log_min_duration_statement = 1000;

-- Analyze tables
ANALYZE signals;
ANALYZE portfolios;
ANALYZE positions;

-- Check for missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY tablename, attname;
```

---

## Performance Tuning

### PostgreSQL Configuration

Edit `/etc/postgresql/14/main/postgresql.conf`:

```ini
# Memory Settings
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 16MB

# Checkpoint Settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Query Planner
random_page_cost = 1.1  # For SSD
effective_io_concurrency = 200

# Logging
log_min_duration_statement = 1000  # Log slow queries (>1s)
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

Restart after changes:
```bash
sudo systemctl restart postgresql
```

### Maintenance

```sql
-- Regular maintenance (run weekly)
VACUUM ANALYZE;

-- Reindex if needed
REINDEX DATABASE janus;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Backup and Restore

### Backup

```bash
# Full database backup
pg_dump -U janus -h localhost janus > janus_backup_$(date +%Y%m%d).sql

# Compressed backup
pg_dump -U janus -h localhost janus | gzip > janus_backup_$(date +%Y%m%d).sql.gz

# Schema only
pg_dump -U janus -h localhost --schema-only janus > janus_schema.sql

# Data only
pg_dump -U janus -h localhost --data-only janus > janus_data.sql
```

### Restore

```bash
# From SQL file
psql -U janus -h localhost janus < janus_backup.sql

# From compressed file
gunzip -c janus_backup.sql.gz | psql -U janus -h localhost janus

# Drop and recreate database first
dropdb -U postgres janus
createdb -U postgres janus
psql -U janus -h localhost janus < janus_backup.sql
```

---

## Docker Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  postgres:
    image: postgres:14-alpine
    container_name: janus-postgres-prod
    restart: always
    environment:
      JANUS_DB: ${JANUS_DB:-janus}
      POSTGRES_USER: ${POSTGRES_USER:-janus}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}
    ports:
      - "127.0.0.1:5432:5432"  # Only localhost
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    command: >
      postgres
      -c shared_buffers=256MB
      -c max_connections=100
      -c work_mem=16MB
      -c maintenance_work_mem=64MB
      -c effective_cache_size=1GB
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

  janus:
    build: .
    restart: always
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${JANUS_DB}
      DB_MAX_CONNECTIONS: 20
      RUST_LOG: info
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  postgres_data:
    driver: local
```

---

## Next Steps

1. **Test Connection**: Verify database connectivity
2. **Run Migrations**: Execute all schema migrations
3. **Insert Test Data**: Create test signals and portfolios
4. **Query Data**: Test repository operations
5. **Monitor Performance**: Check query execution times
6. **Set Up Backups**: Configure automated backups

---

## Resources

- **PostgreSQL Documentation**: https://www.postgresql.org/docs/14/
- **SQLx Documentation**: https://docs.rs/sqlx/latest/sqlx/
- **JANUS API Documentation**: See `WEEK6_REST_API.md`
- **Database Schema**: See migration files in `migrations/`

---

**Last Updated**: Week 7  
**Version**: 1.0