# JANUS Quick Start Guide

## 🚀 Quick Command Reference

### Build Commands

```bash
# Navigate to workspace
cd src/janus

# Check all packages compile
cargo check --workspace

# Build all packages (dev)
cargo build --workspace

# Build release binary
cargo build --package janus --release

# Build specific package
cargo build --package janus-core
cargo build --package janus-api
cargo build --package janus-dsp
cargo build --package janus-ltn
cargo build --package janus-data
```

### Run Commands

```bash
# Run unified JANUS service (all modules enabled)
cargo run --package janus

# Run in release mode
./target/release/janus

# Run with custom logging
RUST_LOG=debug cargo run --package janus

# Run with selective modules
JANUS_ENABLE_FORWARD=false \
JANUS_ENABLE_BACKWARD=false \
cargo run --package janus
```

### Test Commands

```bash
# Run all tests
cargo test --workspace

# Run tests for specific package
cargo test --package janus-core
cargo test --package janus-dsp
cargo test --package janus-ltn

# Run with output
cargo test --package janus-core -- --nocapture
```

### Cleanup Commands

```bash
# Fix warnings
cargo fix --workspace --allow-dirty

# Format code
cargo fmt --all

# Run clippy
cargo clippy --workspace

# Clean build artifacts
cargo clean
```

## 📊 Health Check Commands

```bash
# Check service health
curl http://localhost:8080/health

# Get detailed status
curl http://localhost:8080/status

# Check module health
curl http://localhost:8080/api/modules/health

# Get Prometheus metrics
curl http://localhost:9090/metrics

# Dashboard overview
curl http://localhost:8080/api/dashboard/overview
```

## 🔧 Configuration

### Minimal Configuration (All Defaults)

```bash
# Just run it
cargo run --package janus
```

### Custom Ports

```bash
export JANUS_HTTP_PORT=3000
export JANUS_METRICS_PORT=9091
cargo run --package janus
```

### Enable/Disable Modules

```bash
# Only API and Data modules
export JANUS_ENABLE_FORWARD=false
export JANUS_ENABLE_BACKWARD=false
export JANUS_ENABLE_CNS=false
export JANUS_ENABLE_API=true
export JANUS_ENABLE_DATA=true
cargo run --package janus
```

### External Services

```bash
export REDIS_URL=redis://localhost:6379/0
export DATABASE_URL=postgresql://user:pass@localhost:5432/janus
export QUESTDB_HOST=localhost:9009
cargo run --package janus
```

### Full Environment Example

```bash
# Create .env file
cat > .env << 'EOF'
# Ports
JANUS_HTTP_PORT=8080
JANUS_GRPC_PORT=50051
JANUS_WS_PORT=8081
JANUS_METRICS_PORT=9090

# Modules
JANUS_ENABLE_FORWARD=true
JANUS_ENABLE_BACKWARD=true
JANUS_ENABLE_CNS=true
JANUS_ENABLE_API=true
JANUS_ENABLE_DATA=true

# External Services
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/janus
QUESTDB_HOST=localhost:9009

# Logging
RUST_LOG=info,janus=debug

# Environment
JANUS_ENVIRONMENT=development
JANUS_SERVICE_NAME=janus
JANUS_CORS_ORIGINS=*
EOF

# Run with dotenv
cargo run --package janus
```

## 📦 Package Overview

| Package | Type | Description |
|---------|------|-------------|
| `janus` | Binary | Main unified service |
| `janus-core` | Library | Shared state and types |
| `janus-api` | Library | REST/HTTP API |
| `janus-dsp` | Library | Digital signal processing |
| `janus-ltn` | Library | Logic tensor networks |
| `janus-data` | Service | Market data ingestion |
| `janus-forward` | Service | Signal generation |
| `janus-backward` | Service | Analytics & persistence |
| `janus-cns` | Service | Health monitoring |

## 🐛 Troubleshooting

### Build Fails

```bash
# Clean and rebuild
cargo clean
cargo build --workspace

# Update dependencies
cargo update

# Check specific package
cargo check --package janus-core -vv
```

### Service Won't Start

```bash
# Check configuration
cargo run --package janus -- --help

# Verify ports available
lsof -i :8080
lsof -i :9090

# Check logs
RUST_LOG=debug cargo run --package janus
```

### Module Not Starting

```bash
# Check module is enabled
curl http://localhost:8080/api/modules/health

# View logs
RUST_LOG=debug,janus=trace cargo run --package janus
```

## 📈 Performance Testing

### Benchmark DSP

```bash
cd crates/dsp
cargo +nightly bench
```

### Load Test API

```bash
# Install wrk
sudo apt install wrk  # or brew install wrk

# Test health endpoint
wrk -t4 -c100 -d30s http://localhost:8080/health

# Test metrics endpoint
wrk -t4 -c100 -d30s http://localhost:9090/metrics
```

### Memory Profiling

```bash
# Install heaptrack
sudo apt install heaptrack

# Profile JANUS
heaptrack ./target/release/janus

# Analyze results
heaptrack_gui heaptrack.janus.*.gz
```

## 🔍 Useful Development Commands

### Watch for Changes

```bash
# Install cargo-watch
cargo install cargo-watch

# Auto-rebuild on changes
cargo watch -x 'check --workspace'

# Auto-run on changes
cargo watch -x 'run --package janus'
```

### Generate Documentation

```bash
# Generate and open docs
cargo doc --workspace --open

# Generate docs for specific package
cargo doc --package janus-core --open
```

### Dependency Tree

```bash
# Install cargo-tree
cargo install cargo-tree

# Show dependency tree
cargo tree --package janus

# Show workspace dependencies
cargo tree --workspace -d
```

### Code Coverage

```bash
# Install tarpaulin
cargo install cargo-tarpaulin

# Generate coverage report
cargo tarpaulin --workspace --out Html

# Open coverage report
open tarpaulin-report.html
```

## 🐳 Docker Commands (Coming Soon)

```bash
# Build Docker image
docker build -t janus:2.0.0 .

# Run container
docker run -p 8080:8080 -p 9090:9090 janus:2.0.0

# Run with environment
docker run --env-file .env janus:2.0.0

# Docker Compose
docker-compose up janus
```

## 🎯 Common Workflows

### Development Workflow

```bash
# 1. Make changes
vim src/janus/lib/janus-core/src/state.rs

# 2. Check compilation
cargo check --package janus-core

# 3. Run tests
cargo test --package janus-core

# 4. Format and lint
cargo fmt
cargo clippy

# 5. Run service
cargo run --package janus
```

### Testing Workflow

```bash
# 1. Unit tests
cargo test --workspace

# 2. Integration tests
cargo test --test integration

# 3. Health check
curl http://localhost:8080/health

# 4. Check metrics
curl http://localhost:9090/metrics
```

### Release Workflow

```bash
# 1. Update version
# Edit Cargo.toml [workspace.package] version

# 2. Build release
cargo build --release --package janus

# 3. Run tests
cargo test --release --workspace

# 4. Benchmark
cargo bench --workspace

# 5. Generate docs
cargo doc --workspace --no-deps

# 6. Tag release
git tag v2.0.0
git push --tags
```

## 📝 Notes

- All commands assume you're in the `src/janus` directory
- Default ports: HTTP=8080, Metrics=9090
- Logs go to stdout (capture with systemd/Docker)
- Configuration via environment variables (no config files)
- Health checks available at `/health` and `/api/modules/health`

## 🆘 Getting Help

```bash
# Show available commands
cargo --list

# Show package help
cargo run --package janus -- --help

# Check package info
cargo metadata --package janus | jq

# Show workspace info
cargo metadata --workspace | jq '.workspace_members'
```

---

**Quick Start Complete!** 🎉

For more details, see:
- `PHASE1_COMPLETE.md` - Phase 1 completion summary
- `INTEGRATION_SUMMARY.md` - Integration details
- `JANUS_CONSOLIDATION_PLAN.md` - Full consolidation plan