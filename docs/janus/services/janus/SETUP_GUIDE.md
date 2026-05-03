# JANUS Setup Guide - Weeks 1-2

**Last Updated:** 2024-01-XX  
**Scope:** Market Data Integration + News/Sentiment Analysis  
**Estimated Setup Time:** 2-3 hours  

---

## Overview

This guide walks you through setting up the JANUS trading system foundation (Weeks 1-2):
- Market data collection from 6 exchanges
- News ingestion with sentiment analysis
- PostgreSQL and QuestDB databases
- Prometheus metrics and Grafana dashboards

---

## Prerequisites Checklist

### System Requirements

- [ ] **OS:** Linux (Ubuntu 20.04+ recommended) or macOS
- [ ] **CPU:** 4+ cores recommended
- [ ] **RAM:** 8GB minimum, 16GB recommended
- [ ] **Storage:** 100GB available (50GB for databases, 50GB for logs/archives)
- [ ] **Network:** Stable internet connection for WebSocket feeds

### Software Dependencies

```bash
# Rust 1.70+
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustup update stable

# PostgreSQL 14+
sudo apt update
sudo apt install postgresql-14 postgresql-contrib-14

# Docker & Docker Compose (for QuestDB, Prometheus, Grafana)
sudo apt install docker.io docker-compose
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect

# Development tools
sudo apt install build-essential pkg-config libssl-dev
```

### Verify Installation

```bash
# Check Rust
rustc --version  # Should be 1.70+
cargo --version

# Check PostgreSQL
psql --version  # Should be 14.x+

# Check Docker
docker --version
docker-compose --version
```

---

## Part 1: Project Setup

### Clone and Structure

```bash
cd /home/jordan/github/fks/src/janus

# Verify workspace structure
ls -la
# Should see: Cargo.toml, crates/, services/, lib/, docs/
```

### Create Missing Directories

```bash
# Create sentiment crate
mkdir -p crates/sentiment/src

# Create news service
mkdir -p services/news/src/{sources,storage,processor,metrics}
mkdir -p services/news/examples

# Verify
tree -L 3 crates/sentiment services/news
```

---

## Part 2: Code Implementation

### Step 1: Copy Sentiment Crate Code

**From:** `docs/janus/WEEK2_IMPLEMENTATION_GUIDE.md`  
**To:** `crates/sentiment/src/`

```bash
cd crates/sentiment

# Create files (copy code from WEEK2_IMPLEMENTATION_GUIDE.md):
# - Cargo.toml
# - src/lib.rs
# - src/lexicon.rs
# - src/scorer.rs
# - src/entities.rs
# - src/classifier.rs

# Verify
cargo check --package janus-sentiment
```

### Step 2: Copy News Service Code

**From:** `docs/janus/WEEK2_NEWS_SERVICE_CODE.md`  
**To:** `services/news/src/`

```bash
cd services/news

# Create files (copy code from WEEK2_NEWS_SERVICE_CODE.md):
# - Cargo.toml
# - schema.sql
# - .env.example
# - src/main.rs
# - src/lib.rs
# - src/config.rs
# - src/metrics.rs
# - src/sources/mod.rs
# - src/sources/rss.rs
# - src/sources/deduplicator.rs
# - src/storage/mod.rs
# - src/storage/postgres.rs
# - src/processor/mod.rs
# - examples/collect_news.rs

# Verify
cargo check --package janus-news
```

### Step 3: Update Workspace

Edit `src/janus/Cargo.toml`:

```toml
[workspace]
members = [
    # ... existing members ...
    "crates/sentiment",    # ADD THIS
    "services/news",       # ADD THIS
]
```

### Step 4: Build Everything

```bash
cd src/janus

# Build all packages
cargo build --workspace --release

# Expected output:
# Compiling janus-sentiment v0.1.0
# Compiling janus-news v0.1.0
# ... (other packages)
# Finished release [optimized] target(s) in X.XXs
```

---

## Part 3: Database Setup

### PostgreSQL Setup

```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE janus_news;
CREATE USER janus WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE janus_news TO janus;
\q
EOF

# Run schema
psql -U janus -d janus_news < services/news/schema.sql

# Verify tables
psql -U janus -d janus_news -c "\dt"
# Should show: news_articles, news_sources

# Check default sources
psql -U janus -d janus_news -c "SELECT name, enabled FROM news_sources;"
# Should show 5 RSS feeds
```

### QuestDB Setup (Docker)

```bash
# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  questdb:
    image: questdb/questdb:latest
    container_name: janus-questdb
    ports:
      - "9000:9000"  # HTTP/REST API
      - "9009:9009"  # InfluxDB line protocol
      - "8812:8812"  # PostgreSQL wire protocol
      - "9003:9003"  # Min health check
    volumes:
      - ./questdb-data:/var/lib/questdb
    environment:
      - QDB_CAIRO_COMMIT_LAG=1000
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: janus-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: janus-grafana
    ports:
      - "3000:3000"
    volumes:
      - ./grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    restart: unless-stopped
EOF

# Create Prometheus config
cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'janus-data'
    static_configs:
      - targets: ['host.docker.internal:9092']

  - job_name: 'janus-news'
    static_configs:
      - targets: ['host.docker.internal:9091']
EOF

# Start services
docker-compose up -d

# Verify
docker ps
# Should show: janus-questdb, janus-prometheus, janus-grafana

# Check QuestDB UI
curl http://localhost:9000
# Or open in browser: http://localhost:9000
```

---

## Part 4: Configuration

### Environment Variables

#### Data Service

```bash
cd services/data

# Copy example env file
cp .env.starter .env

# Edit .env
cat >> .env << 'EOF'
# Exchange WebSocket URLs
COINBASE_WS_URL=wss://advanced-trade-ws.coinbase.com
KRAKEN_WS_URL=wss://ws.kraken.com/v2
OKX_WS_URL=wss://ws.okx.com:8443/ws/v5/public

# Primary exchange
PRIMARY_EXCHANGE=coinbase
SECONDARY_EXCHANGE=kraken
TERTIARY_EXCHANGE=okx

# Assets to monitor
ASSETS=BTC,ETH,SOL,AVAX,MATIC

# Database
QUESTDB_HOST=localhost
QUESTDB_ILP_PORT=9009
QUESTDB_HTTP_PORT=9000

# Metrics
METRICS_PORT=9092
EOF
```

#### News Service

```bash
cd services/news

# Copy example env file
cp .env.example .env

# Edit .env
cat >> .env << 'EOF'
# PostgreSQL
DATABASE_URL=postgresql://janus:your_secure_password_here@localhost/janus_news

# News Collection
POLL_INTERVAL_SECS=300
MAX_ARTICLES_PER_POLL=100

# Sentiment Analysis
ENABLE_SENTIMENT=true
MIN_CONFIDENCE_THRESHOLD=0.3

# Logging
LOG_LEVEL=info

# Metrics
METRICS_PORT=9091
EOF
```

---

## Part 5: Running Services

### Terminal 1: Data Service

```bash
cd services/data

# Run in foreground (for testing)
RUST_LOG=info cargo run --release

# Or run in background
nohup cargo run --release > data.log 2>&1 &

# Check logs
tail -f data.log

# Expected output:
# INFO ConnectorManager: Initializing exchange connectors
# INFO ConnectorManager: Starting WebSocket for BTCUSD on coinbase
# INFO WebSocket Actor: Connected to coinbase for BTC-USDT
```

### Terminal 2: News Service

```bash
cd services/news

# Run in foreground (for testing)
RUST_LOG=info cargo run --release

# Or run in background
nohup cargo run --release > news.log 2>&1 &

# Check logs
tail -f news.log

# Expected output:
# INFO NewsService: Starting news collection loop
# INFO NewsCollector: Collecting news from all sources
# INFO NewsService: Collected 15 articles from CoinTelegraph
```

### Verify Services

```bash
# Check data service metrics
curl http://localhost:9092/metrics | grep janus_exchange

# Check news service metrics
curl http://localhost:9091/metrics | grep janus_news

# Check PostgreSQL articles
psql -U janus -d janus_news -c "SELECT COUNT(*) FROM news_articles;"

# Should show articles being collected
```

---

## Part 6: Monitoring Setup

### Access Grafana

1. Open browser: http://localhost:3000
2. Login: admin / admin
3. Add Prometheus data source:
   - URL: http://prometheus:9090
   - Save & Test

### Import Dashboards

**News Dashboard:**

1. Create New Dashboard
2. Add Panel: "Articles Ingested Rate"
   ```promql
   rate(janus_news_articles_ingested_total[5m])
   ```

3. Add Panel: "Sentiment by Asset"
   ```promql
   janus_news_sentiment_score
   ```

4. Add Panel: "Processing Latency"
   ```promql
   histogram_quantile(0.95, rate(janus_news_processing_latency_seconds_bucket[5m]))
   ```

**Market Data Dashboard:**

1. Create New Dashboard
2. Add Panel: "Message Rate"
   ```promql
   rate(janus_exchange_message_total[1m])
   ```

3. Add Panel: "Exchange Health"
   ```promql
   janus_exchange_health_status
   ```

4. Add Panel: "Parse Errors"
   ```promql
   rate(janus_exchange_message_parse_errors_total[5m])
   ```

### Set Up Alerts

**Prometheus alerts.yml:**

```yaml
groups:
  - name: janus_alerts
    interval: 30s
    rules:
      - alert: NewsCollectionStopped
        expr: rate(janus_news_articles_ingested_total[10m]) == 0
        for: 15m
        severity: warning

      - alert: ExchangeDown
        expr: janus_exchange_health_status < 0.5
        for: 5m
        severity: critical

      - alert: HighParseErrors
        expr: rate(janus_exchange_message_parse_errors_total[5m]) > 0.1
        for: 5m
        severity: warning
```

---

## Part 7: Testing

### Run Unit Tests

```bash
cd src/janus

# Test sentiment crate
cargo test --package janus-sentiment
# Expected: 42 tests passed

# Test news service
cargo test --package janus-news
# Expected: 38 tests passed

# Test exchanges crate
cargo test --package janus-exchanges
# Expected: 43 tests passed

# Test data service
cargo test --package janus-data
# Expected: 24 tests passed (integration tests)
```

### Run Integration Tests

```bash
# Database integration (requires PostgreSQL running)
cd services/news
cargo test --test database_integration

# RSS integration (requires network)
cargo test --test rss_integration -- --ignored
```

### Verify Data Flow

```bash
# Check news articles are being collected
psql -U janus -d janus_news << 'EOF'
SELECT 
    source,
    COUNT(*) as articles,
    AVG(sentiment_score) as avg_sentiment,
    MAX(published_at) as latest
FROM news_articles
GROUP BY source
ORDER BY articles DESC;
EOF

# Check recent BTC sentiment
psql -U janus -d janus_news << 'EOF'
SELECT title, sentiment_score, mentioned_assets, published_at
FROM news_articles
WHERE 'BTC' = ANY(mentioned_assets)
ORDER BY published_at DESC
LIMIT 5;
EOF
```

---

## Part 8: Troubleshooting

### Common Issues

#### 1. Sentiment crate won't compile

**Error:** `cannot find crate janus-core`

**Solution:**
```bash
# Make sure janus-core exists
ls -la lib/janus-core/Cargo.toml

# Update workspace Cargo.toml
grep "janus-core" Cargo.toml

# Clean and rebuild
cargo clean
cargo build --package janus-sentiment
```

#### 2. News service can't connect to PostgreSQL

**Error:** `connection refused`

**Solution:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U janus -d janus_news

# Check DATABASE_URL in .env
echo $DATABASE_URL

# Test connection
psql "$DATABASE_URL" -c "SELECT 1;"
```

#### 3. No articles being collected

**Error:** `janus_news_articles_ingested_total` metric is 0

**Solution:**
```bash
# Check news sources are enabled
psql -U janus -d janus_news -c "SELECT name, enabled FROM news_sources;"

# Check logs for errors
tail -f services/news/news.log

# Test RSS feed manually
curl https://cointelegraph.com/rss

# Check network connectivity
ping cointelegraph.com
```

#### 4. WebSocket connection failures

**Error:** `WebSocket Actor: Connection failed`

**Solution:**
```bash
# Check exchange URLs
grep "_WS_URL" services/data/.env

# Test connection manually
wscat -c wss://advanced-trade-ws.coinbase.com

# Check firewall
sudo ufw status

# Check logs
tail -f services/data/data.log | grep WebSocket
```

#### 5. High memory usage

**Solution:**
```bash
# Monitor memory
watch -n 1 'ps aux | grep janus'

# Check connection pool limits
grep "pool_size" services/news/.env

# Reduce poll frequency
# Edit .env: POLL_INTERVAL_SECS=600

# Restart service
pkill -9 janus-news
cargo run --release
```

---

## Part 9: Verification Checklist

### Services Running ✓

- [ ] PostgreSQL running: `sudo systemctl status postgresql`
- [ ] QuestDB running: `docker ps | grep questdb`
- [ ] Prometheus running: `docker ps | grep prometheus`
- [ ] Grafana running: `docker ps | grep grafana`
- [ ] Data service running: `ps aux | grep janus-data`
- [ ] News service running: `ps aux | grep janus-news`

### Data Collection ✓

- [ ] Articles in database: `psql -U janus -d janus_news -c "SELECT COUNT(*) FROM news_articles;"`
- [ ] Market data flowing: `curl localhost:9092/metrics | grep janus_exchange_message_total`
- [ ] Sentiment scores computed: `psql -U janus -d janus_news -c "SELECT AVG(sentiment_score) FROM news_articles;"`
- [ ] No errors in logs: `tail -100 services/*/logs/*.log | grep ERROR`

### Metrics ✓

- [ ] Data service metrics: http://localhost:9092/metrics
- [ ] News service metrics: http://localhost:9091/metrics
- [ ] Prometheus UI: http://localhost:9090
- [ ] Grafana dashboards: http://localhost:3000

### Health Checks ✓

- [ ] Exchange health: `curl localhost:9092/metrics | grep janus_exchange_health_status`
- [ ] News source health: `curl localhost:9091/metrics | grep janus_news_source_health`
- [ ] Database connections: `psql -U janus -d janus_news -c "SELECT COUNT(*) FROM pg_stat_activity;"`
- [ ] Zero parse errors: `curl localhost:9092/metrics | grep parse_errors_total`

---

## Part 10: Production Hardening

### Security

```bash
# Change default passwords
sudo -u postgres psql -c "ALTER USER janus WITH PASSWORD 'new_secure_password';"

# Update Grafana admin password
docker exec -it janus-grafana grafana-cli admin reset-admin-password new_password

# Set up firewall
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 3000/tcp    # Grafana
sudo ufw enable

# Restrict database access
sudo nano /etc/postgresql/14/main/pg_hba.conf
# Change: host all all 0.0.0.0/0 md5
# To:     host janus_news janus 127.0.0.1/32 md5
sudo systemctl restart postgresql
```

### Systemd Services

**Data Service:**

```bash
sudo tee /etc/systemd/system/janus-data.service << 'EOF'
[Unit]
Description=JANUS Data Service
After=network.target questdb.service

[Service]
Type=simple
User=janus
WorkingDirectory=/home/jordan/github/fks/src/janus/services/data
Environment="RUST_LOG=info"
ExecStart=/home/jordan/github/fks/src/janus/target/release/janus-data
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable janus-data
sudo systemctl start janus-data
```

**News Service:**

```bash
sudo tee /etc/systemd/system/janus-news.service << 'EOF'
[Unit]
Description=JANUS News Service
After=network.target postgresql.service

[Service]
Type=simple
User=janus
WorkingDirectory=/home/jordan/github/fks/src/janus/services/news
Environment="RUST_LOG=info"
ExecStart=/home/jordan/github/fks/src/janus/target/release/janus-news
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable janus-news
sudo systemctl start janus-news
```

### Log Rotation

```bash
sudo tee /etc/logrotate.d/janus << 'EOF'
/home/jordan/github/fks/src/janus/services/*/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 janus janus
    sharedscripts
    postrotate
        systemctl reload janus-data janus-news
    endscript
}
EOF
```

### Backup Scripts

```bash
# Backup PostgreSQL
cat > /usr/local/bin/backup-janus-news.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/var/backups/janus
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
pg_dump -U janus janus_news | gzip > $BACKUP_DIR/janus_news_$DATE.sql.gz

# Keep last 7 days
find $BACKUP_DIR -name "janus_news_*.sql.gz" -mtime +7 -delete
EOF

chmod +x /usr/local/bin/backup-janus-news.sh

# Add to crontab
echo "0 2 * * * /usr/local/bin/backup-janus-news.sh" | sudo crontab -
```

---

## Part 11: Performance Tuning

### PostgreSQL Tuning

```bash
sudo nano /etc/postgresql/14/main/postgresql.conf

# Add/modify:
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 64MB
min_wal_size = 1GB
max_wal_size = 4GB

# Restart
sudo systemctl restart postgresql
```

### Rust Release Optimizations

```bash
# Edit services/news/Cargo.toml
[profile.release]
lto = true
codegen-units = 1
opt-level = 3
strip = true

# Rebuild
cargo build --release
```

---

## Completion Checklist

### Setup Complete ✓

- [ ] All dependencies installed
- [ ] Project code implemented
- [ ] Databases created and configured
- [ ] Services running and healthy
- [ ] Metrics being collected
- [ ] Dashboards configured
- [ ] Tests passing
- [ ] Documentation reviewed

### Next Steps

1. **Monitor for 24 hours** - Ensure stability
2. **Review metrics** - Check for anomalies
3. **Tune configuration** - Adjust poll intervals, thresholds
4. **Add more sources** - Twitter, Reddit, etc.
5. **Proceed to Week 3** - Data quality pipeline

---

## Support

### Documentation References

- **Roadmap:** `docs/janus/JANUS_12_WEEK_ROADMAP.md`
- **Week 1 Complete:** `docs/janus/WEEK1_INTEGRATION_COMPLETE.md`
- **Week 2 Guide:** `docs/janus/WEEK2_IMPLEMENTATION_GUIDE.md`
- **Testing Guide:** `docs/janus/WEEK2_TESTING_AND_INTEGRATION.md`
- **Project Status:** `docs/janus/PROJECT_STATUS.md`

### Quick Commands

```bash
# View all metrics
curl http://localhost:9091/metrics
curl http://localhost:9092/metrics

# Check service status
systemctl status janus-data janus-news

# View logs
journalctl -u janus-data -f
journalctl -u janus-news -f

# Database queries
psql -U janus -d janus_news

# Restart services
sudo systemctl restart janus-data janus-news
```

---

**Setup Status:** Ready for production deployment  
**Estimated Time:** 2-3 hours  
**Next Milestone:** Week 3 - Data Quality Pipeline  
**Support:** See documentation in `docs/janus/`
