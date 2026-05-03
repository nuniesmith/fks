# JANUS CNS Deployment & Operations Guide

This guide covers deploying, operating, and maintaining the JANUS Central Nervous System in various environments.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Deployment](#local-development-deployment)
- [Docker Deployment](#docker-deployment)
- [Docker Compose Deployment](#docker-compose-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Production Considerations](#production-considerations)
- [Operations](#operations)
- [Monitoring & Alerting](#monitoring--alerting)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

---

## Prerequisites

### Software Requirements

- **Rust**: 1.70 or later
- **Docker**: 20.10 or later (for containerized deployment)
- **Docker Compose**: v2.0 or later
- **Kubernetes**: 1.24 or later (for K8s deployment)
- **curl**: For health checks
- **jq**: For JSON parsing

### Infrastructure Requirements

| Component | Development | Production |
|-----------|-------------|------------|
| CPU | 2 cores | 4+ cores |
| Memory | 4GB | 8GB+ |
| Storage | 10GB | 50GB+ |
| Network | 100Mbps | 1Gbps+ |

### Port Requirements

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| CNS | 9090 | HTTP | Metrics & Health |
| Forward | 8081 | HTTP/gRPC | Trading Service |
| Backward | 8082 | HTTP/gRPC | Training Service |
| Gateway | 8080 | HTTP | API Gateway |
| Redis | 6379 | TCP | Job Queue |
| Qdrant | 6333 | HTTP | Vector DB |
| Prometheus | 9091 | HTTP | Metrics |
| Grafana | 3000 | HTTP | Dashboards |

---

## Local Development Deployment

### Step 1: Clone and Build

```bash
# Clone repository
git clone https://github.com/your-org/janus.git
cd janus/src/janus

# Build all services
cargo build --release

# Or use Makefile
make build
```

### Step 2: Start Dependencies

```bash
# Start Redis
docker run -d --name janus-redis -p 6379:6379 redis:7-alpine

# Start Qdrant
docker run -d --name janus-qdrant -p 6333:6333 qdrant/qdrant:latest

# Verify
redis-cli ping  # Should return PONG
curl http://localhost:6333/healthz  # Should return OK
```

### Step 3: Configure CNS

```bash
# Copy example config
cp config/cns.toml.example config/cns.toml

# Edit configuration
vim config/cns.toml
```

Update endpoints if needed:
```toml
[endpoints]
forward_service = "http://localhost:8081"
backward_service = "http://localhost:8082"
gateway_service = "http://localhost:8080"
redis = "redis://localhost:6379"
qdrant = "http://localhost:6333"
```

### Step 4: Start CNS

```bash
# Start CNS service
RUST_LOG=info cargo run --release --bin janus-cns

# Or use Makefile
make run-cns
```

### Step 5: Verify

```bash
# Check health
curl http://localhost:9090/health | jq '.'

# Check metrics
curl http://localhost:9090/metrics | head -20

# Use control script
./scripts/cns-ctl.sh status
```

---

## Docker Deployment

### Build Docker Image

```bash
# Build CNS image
docker build -t janus/cns:latest -f services/cns/Dockerfile .

# Verify image
docker images | grep janus/cns
```

### Run Container

```bash
# Run CNS container
docker run -d \
  --name janus-cns \
  --network host \
  -v $(pwd)/config/cns.toml:/app/config/cns.toml:ro \
  -v /dev/shm:/dev/shm \
  -e RUST_LOG=info \
  -p 9090:9090 \
  janus/cns:latest

# Check logs
docker logs -f janus-cns

# Check health
docker exec janus-cns curl http://localhost:9090/health
```

### Docker Network Setup

```bash
# Create custom network
docker network create janus-network

# Run services on network
docker run -d --name janus-redis --network janus-network redis:7-alpine
docker run -d --name janus-qdrant --network janus-network qdrant/qdrant:latest

# Run CNS with network references
docker run -d \
  --name janus-cns \
  --network janus-network \
  -v $(pwd)/config/cns.toml:/app/config/cns.toml:ro \
  -e RUST_LOG=info \
  -p 9090:9090 \
  janus/cns:latest
```

---

## Docker Compose Deployment

### Basic Stack

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f janus-cns

# Stop all services
docker-compose down
```

### Production Stack with Monitoring

```bash
# Start full stack including Prometheus & Grafana
docker-compose --profile monitoring-full up -d

# Verify all services
docker-compose ps

# Access UIs
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9091
# - CNS: http://localhost:9090/health
```

### Scaling Services

```bash
# Scale Forward service replicas
docker-compose up -d --scale janus-forward=3

# Scale Backward service
docker-compose up -d --scale janus-backward=2
```

### Update Services

```bash
# Rebuild specific service
docker-compose build janus-cns

# Recreate with new image
docker-compose up -d --force-recreate janus-cns

# Rolling update (no downtime)
docker-compose up -d --no-deps --build janus-cns
```

---

## Kubernetes Deployment

### Namespace Setup

```bash
# Create namespace
kubectl create namespace janus

# Set default namespace
kubectl config set-context --current --namespace=janus
```

### Deploy CNS

```yaml
# k8s/cns-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: janus-cns-config
  namespace: janus
data:
  cns.toml: |
    [brain]
    health_check_interval_secs = 10
    enable_reflexes = true
    
    [endpoints]
    forward_service = "http://janus-forward:8081"
    backward_service = "http://janus-backward:8082"
    gateway_service = "http://janus-gateway:8080"
    redis = "redis://janus-redis:6379"
    qdrant = "http://janus-qdrant:6333"
```

Apply deployment:
```bash
# Apply all manifests
kubectl apply -f k8s/cns-configmap.yaml
kubectl apply -f k8s/cns-deployment.yaml
kubectl apply -f k8s/cns-service.yaml

# Verify deployment
kubectl get pods -l app=janus-cns
kubectl get svc janus-cns

# Check logs
kubectl logs -l app=janus-cns -f
```

### Ingress Configuration

```yaml
# k8s/cns-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: janus-cns-ingress
  namespace: janus
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - cns.janus.example.com
      secretName: janus-cns-tls
  rules:
    - host: cns.janus.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: janus-cns
                port:
                  number: 9090
```

### Helm Chart (Recommended)

```bash
# Install using Helm
helm repo add janus https://charts.janus.io
helm repo update

# Install CNS
helm install janus-cns janus/cns \
  --namespace janus \
  --create-namespace \
  --values values-prod.yaml

# Upgrade
helm upgrade janus-cns janus/cns \
  --namespace janus \
  --values values-prod.yaml

# Rollback
helm rollback janus-cns 1 --namespace janus
```

### StatefulSet for Prometheus

```yaml
# k8s/prometheus-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: prometheus
  namespace: janus
spec:
  serviceName: prometheus
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus'
          - '--storage.tsdb.retention.time=30d'
        ports:
        - containerPort: 9090
          name: http
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        - name: storage
          mountPath: /prometheus
      volumes:
      - name: config
        configMap:
          name: prometheus-config
  volumeClaimTemplates:
  - metadata:
      name: storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 50Gi
```

---

## Production Considerations

### High Availability

**Multiple CNS Replicas:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: janus-cns
spec:
  replicas: 3  # Run 3 instances
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
```

**Load Balancing:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: janus-cns
spec:
  type: LoadBalancer
  selector:
    app: janus-cns
  ports:
  - port: 9090
    targetPort: 9090
```

### Resource Limits

```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "200m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

### Auto-scaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: janus-cns-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: janus-cns
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Data Persistence

**Prometheus:**
```yaml
volumeMounts:
  - name: prometheus-storage
    mountPath: /prometheus
volumes:
  - name: prometheus-storage
    persistentVolumeClaim:
      claimName: prometheus-pvc
```

**Grafana:**
```yaml
volumeMounts:
  - name: grafana-storage
    mountPath: /var/lib/grafana
volumes:
  - name: grafana-storage
    persistentVolumeClaim:
      claimName: grafana-pvc
```

---

## Operations

### Using the Control Script

```bash
# Make script executable
chmod +x scripts/cns-ctl.sh

# Check status
./scripts/cns-ctl.sh status

# Watch health in real-time
./scripts/cns-ctl.sh watch 5

# View components
./scripts/cns-ctl.sh components

# Check circuit breakers
./scripts/cns-ctl.sh circuit-breakers

# View active alerts
./scripts/cns-ctl.sh alerts

# Export metrics
./scripts/cns-ctl.sh export-metrics

# Open dashboards
./scripts/cns-ctl.sh dashboard
```

### Health Checks

```bash
# Basic health check
curl http://localhost:9090/health

# Detailed health check
curl http://localhost:9090/health/detailed

# Specific component
curl -s http://localhost:9090/health | jq '.components[] | select(.component_type == "redis")'
```

### Metrics Collection

```bash
# View all metrics
curl http://localhost:9090/metrics

# Specific metric
curl -s http://localhost:9090/metrics | grep janus_cns_system_health_score

# Export to file with timestamp
curl -s http://localhost:9090/metrics > metrics_$(date +%Y%m%d_%H%M%S).txt
```

### Log Management

**Docker:**
```bash
# Follow logs
docker logs -f janus-cns

# Last 100 lines
docker logs --tail 100 janus-cns

# Since timestamp
docker logs --since 2025-01-15T10:00:00 janus-cns
```

**Kubernetes:**
```bash
# Follow logs
kubectl logs -l app=janus-cns -f

# Previous container
kubectl logs -l app=janus-cns --previous

# All replicas
kubectl logs -l app=janus-cns --all-containers
```

**Systemd:**
```bash
# Follow logs
journalctl -u janus-cns -f

# Last hour
journalctl -u janus-cns --since "1 hour ago"

# Export to file
journalctl -u janus-cns > cns_logs.txt
```

---

## Monitoring & Alerting

### Prometheus Setup

**Retention Policy:**
```yaml
command:
  - '--storage.tsdb.retention.time=30d'
  - '--storage.tsdb.retention.size=50GB'
```

**Scrape Configuration:**
```yaml
scrape_configs:
  - job_name: 'janus-cns'
    scrape_interval: 10s
    scrape_timeout: 5s
    static_configs:
      - targets: ['janus-cns:9090']
```

### Grafana Dashboards

**Import Dashboard:**
1. Login to Grafana (http://localhost:3000)
2. Navigate to Dashboards → Import
3. Upload `config/grafana/janus_cns_dashboard.json`
4. Select Prometheus data source
5. Click Import

**Dashboard Annotations:**
```json
{
  "datasource": "Prometheus",
  "enable": true,
  "expr": "ALERTS{alertstate=\"firing\"}",
  "iconColor": "red",
  "name": "Alerts",
  "step": "60s",
  "tagKeys": "alertname,severity",
  "textFormat": "{{alertname}}: {{annotations.summary}}",
  "titleFormat": "Alert"
}
```

### Alert Configuration

**Slack Integration:**
```yaml
# config/alertmanager.yml
receivers:
  - name: 'slack-critical'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#janus-alerts'
        title: 'JANUS Alert: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

route:
  receiver: 'slack-critical'
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  routes:
    - match:
        severity: critical
      receiver: 'slack-critical'
```

**PagerDuty Integration:**
```yaml
receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
        description: '{{ .GroupLabels.alertname }}'
```

---

## Backup & Recovery

### Configuration Backup

```bash
# Backup all configs
tar -czf janus-config-backup-$(date +%Y%m%d).tar.gz config/

# Restore
tar -xzf janus-config-backup-20240115.tar.gz
```

### Prometheus Data Backup

```bash
# Snapshot Prometheus data
curl -XPOST http://localhost:9091/api/v1/admin/tsdb/snapshot

# Copy snapshot
docker cp prometheus:/prometheus/snapshots/20240115T120000Z-abc123 ./backups/

# Restore
docker cp ./backups/20240115T120000Z-abc123 prometheus:/prometheus/
```

### Grafana Backup

```bash
# Backup Grafana database
docker exec janus-grafana grafana-cli admin reset-admin-password admin
docker cp janus-grafana:/var/lib/grafana ./grafana-backup/

# Restore
docker cp ./grafana-backup/grafana janus-grafana:/var/lib/
docker restart janus-grafana
```

### Disaster Recovery Plan

1. **Regular Backups**: Daily automated backups of configs and data
2. **Documentation**: Keep runbooks up-to-date
3. **Testing**: Test recovery procedures quarterly
4. **Redundancy**: Multi-region deployment for critical systems
5. **Monitoring**: Alert on backup failures

---

## Troubleshooting

### CNS Service Won't Start

**Issue**: Port already in use
```bash
# Find process using port 9090
lsof -i :9090

# Kill process
kill -9 <PID>

# Or use different port
CNS_PORT=9095 cargo run --bin janus-cns
```

**Issue**: Cannot connect to Redis
```bash
# Verify Redis is running
redis-cli ping

# Check connectivity
telnet localhost 6379

# Check CNS config
grep redis config/cns.toml
```

### High Memory Usage

```bash
# Check memory usage
docker stats janus-cns

# Kubernetes
kubectl top pod -l app=janus-cns

# Increase memory limit
# In docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 1G
```

### Metrics Not Appearing

```bash
# Verify CNS metrics endpoint
curl http://localhost:9090/metrics | head

# Check Prometheus targets
curl http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job == "janus-cns")'

# Verify Prometheus config
docker exec janus-prometheus cat /etc/prometheus/prometheus.yml
```

### Health Checks Failing

```bash
# Check service endpoints
curl http://localhost:8081/health  # Forward
curl http://localhost:8082/health  # Backward
curl http://localhost:8080/health  # Gateway

# Increase timeout
# In config/cns.toml:
[health]
timeout_secs = 10
```

---

## Security

### Authentication

**Basic Auth for Metrics:**
```bash
# Generate password
htpasswd -c auth janus-admin

# Add to Nginx config
location /metrics {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/auth;
    proxy_pass http://janus-cns:9090/metrics;
}
```

### TLS/SSL

**Generate Certificates:**
```bash
# Self-signed for testing
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout cns-key.pem -out cns-cert.pem

# Let's Encrypt for production
certbot certonly --standalone -d cns.janus.example.com
```

**Configure Ingress:**
```yaml
tls:
  - hosts:
      - cns.janus.example.com
    secretName: janus-cns-tls
```

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: janus-cns-netpol
spec:
  podSelector:
    matchLabels:
      app: janus-cns
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: prometheus
    ports:
    - protocol: TCP
      port: 9090
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
```

### Secrets Management

**Docker Compose:**
```yaml
secrets:
  redis_password:
    file: ./secrets/redis_password.txt

services:
  janus-cns:
    secrets:
      - redis_password
    environment:
      - REDIS_PASSWORD_FILE=/run/secrets/redis_password
```

**Kubernetes:**
```bash
# Create secret
kubectl create secret generic janus-cns-secrets \
  --from-literal=redis-password='your-password' \
  --namespace janus

# Use in deployment
env:
  - name: REDIS_PASSWORD
    valueFrom:
      secretKeyRef:
        name: janus-cns-secrets
        key: redis-password
```

---

## Performance Tuning

### CNS Configuration

```toml
[brain]
# Reduce check frequency for less load
health_check_interval_secs = 30

[advanced]
# Limit concurrent probes
max_concurrent_probes = 5

# Increase startup grace period
startup_grace_period_secs = 60
```

### Prometheus Optimization

```yaml
# Reduce scrape frequency for less critical jobs
scrape_configs:
  - job_name: 'janus-backward'
    scrape_interval: 30s  # Less frequent for batch jobs
```

### Resource Optimization

```yaml
# Reduce Grafana memory
environment:
  - GF_DATABASE_CACHE_SIZE=32
  - GF_DATABASE_MAX_OPEN_CONN=25
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Check dashboard for anomalies
- Review active alerts
- Verify backup completion

**Weekly:**
- Review log aggregations
- Check disk usage
- Update dashboards

**Monthly:**
- Review and update alert rules
- Performance tuning
- Security updates
- Backup testing

### Upgrades

```bash
# Backup current state
./scripts/backup.sh

# Pull latest images
docker-compose pull

# Recreate services
docker-compose up -d

# Verify health
./scripts/cns-ctl.sh health

# Rollback if needed
docker-compose down
docker-compose up -d --force-recreate
```

---

## Conclusion

This deployment guide covers the essential aspects of deploying and operating the JANUS CNS. For additional support:

- Review [Architecture Documentation](./CNS_ARCHITECTURE.md)
- Check [Quick Start Guide](./CNS_QUICKSTART.md)
- Consult [Main README](../README.md)

For production deployments, always test in staging first and maintain comprehensive monitoring and backup procedures.