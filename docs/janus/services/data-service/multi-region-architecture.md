# Multi-Region Architecture Design

**Version:** 1.0  
**Date:** Week 10  
**Status:** Design Approved  
**Owner:** Infrastructure & SRE Teams

---

## Executive Summary

This document outlines the multi-region architecture for the Data Service, enabling global deployment with high availability, disaster recovery, and optimized latency for users worldwide.

**Key Objectives:**
- **Global Availability:** 99.99% uptime across all regions
- **Low Latency:** <50ms response time for regional users
- **Disaster Recovery:** RPO 5 minutes, RTO 15 minutes
- **Scalability:** Support 10x growth across multiple regions
- **Cost Efficiency:** Optimize infrastructure spend while maintaining quality

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Region Selection](#region-selection)
3. [Component Architecture](#component-architecture)
4. [Data Replication Strategy](#data-replication-strategy)
5. [Traffic Management](#traffic-management)
6. [Disaster Recovery](#disaster-recovery)
7. [Monitoring & Observability](#monitoring--observability)
8. [Cost Analysis](#cost-analysis)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Operational Procedures](#operational-procedures)

---

## Architecture Overview

### Current State (Single Region)

```
                    [Internet]
                        |
                  [Load Balancer]
                        |
                  [Data Service] (us-east-1)
                   /          \
            [QuestDB]      [Redis]
                |              |
          [Exchange APIs]  [Dedup/Locks]
```

**Limitations:**
- Single point of failure (regional outage = full outage)
- High latency for non-US users (200-300ms)
- No disaster recovery (RPO/RTO undefined)
- Scalability limited to single region capacity

### Target State (Multi-Region)

```
                         [Route53 GSLB]
                    (Latency-Based Routing)
                              |
        +---------------------+---------------------+
        |                     |                     |
   [us-east-1]           [eu-west-1]         [ap-southeast-1]
    (Primary)            (Secondary)            (Secondary)
        |                     |                     |
    [ALB/NLB]             [ALB/NLB]              [ALB/NLB]
        |                     |                     |
  [Data Service]        [Data Service]         [Data Service]
   (3-15 pods)           (3-15 pods)            (3-15 pods)
    /      \              /      \               /      \
[QuestDB] [Redis]    [QuestDB] [Redis]      [QuestDB] [Redis]
   |         |          |         |             |         |
[Cluster] [Cluster] [Cluster] [Cluster]    [Cluster] [Cluster]
        |                     |                     |
        +---------------------+---------------------+
              [Cross-Region Replication]
                  (Async, Bi-directional)
```

**Benefits:**
- 99.99% availability (multi-region redundancy)
- <50ms latency for 95% of global users
- Automated disaster recovery (RPO: 5min, RTO: 15min)
- Horizontal scalability across regions
- Exchange co-location (lower API latency)

---

## Region Selection

### Selected Regions

| Region | Code | Purpose | Users | Exchange Proximity |
|--------|------|---------|-------|-------------------|
| **US East (N. Virginia)** | us-east-1 | Primary | Americas | Coinbase, Kraken |
| **EU (Ireland)** | eu-west-1 | Secondary | Europe, Middle East, Africa | European exchanges |
| **Asia Pacific (Singapore)** | ap-southeast-1 | Secondary | Asia Pacific | Binance, OKX, Bybit |

### Selection Criteria

**1. Geographic Coverage**
- us-east-1: Americas (North & South)
- eu-west-1: Europe, Middle East, Africa
- ap-southeast-1: Asia Pacific

**Coverage:** 95% of global crypto trading volume within 50ms

**2. Exchange Proximity**
- Binance (primary): Singapore (~1ms from ap-southeast-1)
- Kraken: US East (~5ms from us-east-1)
- Coinbase: US East/West (~10ms from us-east-1)
- European exchanges: Ireland (~2ms from eu-west-1)

**3. AWS Service Availability**
- EKS: Available in all selected regions ✅
- RDS/Aurora: Available ✅
- ElastiCache: Available ✅
- Global Accelerator: Supported ✅

**4. Compliance & Data Residency**
- GDPR: EU data can remain in eu-west-1
- US regulations: Data in us-east-1
- APAC: Data in ap-southeast-1

**5. Cost Efficiency**
- us-east-1: Lowest AWS pricing (baseline)
- eu-west-1: ~10% premium
- ap-southeast-1: ~15% premium

### Future Expansion Regions

**Phase 2 (12-18 months):**
- ap-northeast-1 (Tokyo): Japan market
- us-west-2 (Oregon): Disaster recovery for US
- sa-east-1 (São Paulo): Latin America

**Phase 3 (24+ months):**
- Edge locations via CloudFront + Lambda@Edge
- Local market-specific deployments

---

## Component Architecture

### Data Service (Kubernetes)

**Per-Region Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: data-service
  namespace: production
spec:
  replicas: 3  # Min replicas per region
  selector:
    matchLabels:
      app: data-service
      region: us-east-1  # Region label
  template:
    metadata:
      labels:
        app: data-service
        region: us-east-1
        version: v1.0.0
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchLabels:
                app: data-service
            topologyKey: topology.kubernetes.io/zone
      containers:
      - name: data-service
        image: data-service:v1.0.0
        env:
        - name: REGION
          value: "us-east-1"
        - name: QUESTDB_ENDPOINT
          value: "questdb-local.production:9000"
        - name: REDIS_ENDPOINT
          value: "redis-local.production:6379"
        - name: CROSS_REGION_REPLICATION
          value: "true"
        resources:
          requests:
            cpu: 1500m
            memory: 3Gi
          limits:
            cpu: 3000m
            memory: 6Gi
```

**HPA Configuration (Per Region):**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: data-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: data-service
  minReplicas: 3
  maxReplicas: 15
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
        averageUtilization: 75
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

### QuestDB (Time-Series Database)

**Architecture:** Clustered deployment with cross-region replication

**Per-Region Cluster:**
- 3-node QuestDB cluster for high availability
- Local writes (low latency)
- Async replication to other regions

**Replication Strategy:**
```
Region 1 (us-east-1)          Region 2 (eu-west-1)
     [QuestDB-1]                   [QuestDB-1]
     [QuestDB-2]  <--- Async --->  [QuestDB-2]
     [QuestDB-3]    Replication     [QuestDB-3]
         |                              |
    [Local Writes]                [Local Writes]
```

**Configuration:**
```yaml
# QuestDB StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: questdb
spec:
  serviceName: questdb
  replicas: 3
  selector:
    matchLabels:
      app: questdb
  template:
    spec:
      containers:
      - name: questdb
        image: questdb/questdb:7.3.3
        env:
        - name: QDB_CAIRO_COMMIT_LAG
          value: "10000"
        - name: QDB_PG_ENABLED
          value: "true"
        - name: QDB_HTTP_ENABLED
          value: "true"
        - name: QDB_LINE_TCP_ENABLED
          value: "true"
        - name: REGION
          value: "us-east-1"
        - name: REPLICATION_ENABLED
          value: "true"
        - name: REPLICATION_TARGETS
          value: "eu-west-1.questdb.global,ap-southeast-1.questdb.global"
        volumeMounts:
        - name: data
          mountPath: /var/lib/questdb
        resources:
          requests:
            cpu: 2000m
            memory: 8Gi
          limits:
            cpu: 4000m
            memory: 16Gi
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 30Ti  # 20Ti data + headroom
      storageClassName: gp3
```

**Replication Mechanism:**
- Change Data Capture (CDC) from WAL
- Async replication with eventual consistency
- Conflict resolution: Last-write-wins (timestamp-based)
- Monitoring: Replication lag alerts

### Redis (Caching & Coordination)

**Architecture:** Redis Enterprise with Active-Active replication

**Deployment Model:**
```
Region 1                Region 2                Region 3
[Redis Cluster]  <-->  [Redis Cluster]  <-->  [Redis Cluster]
  6 nodes                 6 nodes                 6 nodes
  (3 master +             (3 master +            (3 master +
   3 replica)              3 replica)             3 replica)
```

**Configuration:**
```yaml
# Redis Cluster (per region)
apiVersion: redis.redis.opstreelabs.in/v1beta1
kind: RedisCluster
metadata:
  name: redis-cluster
spec:
  clusterSize: 6
  clusterVersion: "7.0"
  redisExporter:
    enabled: true
  kubernetesConfig:
    image: redis:7.0-alpine
    resources:
      requests:
        cpu: 500m
        memory: 2Gi
      limits:
        cpu: 1000m
        memory: 4Gi
  storage:
    volumeClaimTemplate:
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 100Gi
        storageClassName: gp3
  # Active-Active replication
  redisConfig:
    repl-diskless-sync: "yes"
    repl-diskless-sync-delay: "5"
    min-replicas-to-write: "1"
    # Cross-region endpoints
    replica-announce-ip: "redis.us-east-1.global"
```

**Active-Active Replication:**
- Conflict-free Replicated Data Types (CRDTs)
- Bi-directional replication between regions
- Automatic conflict resolution
- Target replication lag: <100ms

**Data Partitioning:**
- Locks: Majority-write (2 of 3 regions)
- Cache: Regional with TTL-based invalidation
- Deduplication: Global with CRDT counters

---

## Data Replication Strategy

### Replication Model: Active-Active

**Characteristics:**
- All regions accept writes
- Asynchronous replication
- Eventual consistency
- Automatic conflict resolution

**Trade-offs:**
- ✅ Low latency (local writes)
- ✅ High availability (no single primary)
- ✅ Better resource utilization
- ⚠️ Eventual consistency (acceptable for market data)
- ⚠️ Conflict resolution complexity

### Data Consistency Requirements

**Market Data (Trades):**
- Consistency: Eventual (5-minute window acceptable)
- Write pattern: Insert-only (no updates)
- Conflict resolution: Timestamp + exchange ID (deterministic)
- Replication lag target: <60 seconds (P95)

**Locks (Redis):**
- Consistency: Strong (majority quorum)
- Write pattern: Create/Delete
- Conflict resolution: First-writer-wins
- Replication lag target: <100ms

**Cache (Redis):**
- Consistency: Eventual (TTL-based)
- Write pattern: Set/Delete
- Conflict resolution: Last-write-wins
- Replication lag target: <500ms

### Replication Topology

```
           us-east-1 (Primary)
                |
        +-------+-------+
        |               |
    eu-west-1      ap-southeast-1
        |               |
        +-------+-------+
                |
        Bi-directional Mesh
```

**Replication Paths:**
- us-east-1 → eu-west-1 (Direct)
- us-east-1 → ap-southeast-1 (Direct)
- eu-west-1 → ap-southeast-1 (Direct)
- Reverse paths for Active-Active

**Bandwidth Requirements:**
- Average: 500 Mbps per path
- Peak: 2 Gbps per path
- Total cross-region: ~3 Gbps average, 12 Gbps peak

### Conflict Resolution

**Trade Data Conflicts:**
```rust
// Deterministic conflict resolution
fn resolve_trade_conflict(trade1: &Trade, trade2: &Trade) -> &Trade {
    // Compare by timestamp first
    match trade1.timestamp.cmp(&trade2.timestamp) {
        Ordering::Less => trade2,
        Ordering::Greater => trade1,
        Ordering::Equal => {
            // If timestamps equal, use exchange + trade_id
            if (trade1.exchange.as_str(), &trade1.trade_id) >
               (trade2.exchange.as_str(), &trade2.trade_id) {
                trade1
            } else {
                trade2
            }
        }
    }
}
```

**Lock Conflicts:**
- Use distributed consensus (Raft/Paxos)
- Require majority quorum (2 of 3 regions)
- Timeout-based release (5 minutes)

---

## Traffic Management

### Global Load Balancing

**AWS Route53 Configuration:**
```json
{
  "Type": "A",
  "Name": "api.dataservice.global",
  "SetIdentifier": "us-east-1",
  "GeoLocation": {
    "ContinentCode": "NA"
  },
  "TTL": 60,
  "ResourceRecords": [
    {
      "Value": "52.1.2.3"
    }
  ],
  "HealthCheckId": "abc123"
}
```

**Routing Policies:**

1. **Primary: Latency-Based Routing**
   - Routes to region with lowest latency
   - Measured via Route53 health checks
   - Updates every 60 seconds

2. **Failover: Health-Based**
   - Primary: us-east-1
   - Secondary: eu-west-1, ap-southeast-1
   - Automatic failover on health check failure

3. **Geo-Location Override**
   - GDPR-sensitive: Always route EU to eu-west-1
   - Compliance requirements: Route to specific regions

**Health Checks:**
```yaml
HealthCheck:
  Type: HTTPS
  ResourcePath: /health
  FullyQualifiedDomainName: api.us-east-1.dataservice.global
  Port: 443
  RequestInterval: 30
  FailureThreshold: 3
  MeasureLatency: true
```

### Traffic Distribution (Expected)

| Region | Traffic % | Peak RPS | Avg RPS |
|--------|-----------|----------|---------|
| us-east-1 | 40% | 6,320 | 4,096 |
| eu-west-1 | 35% | 5,530 | 3,584 |
| ap-southeast-1 | 25% | 3,950 | 2,560 |
| **Total** | **100%** | **15,800** | **10,240** |

### Regional Load Balancing

**Per-Region ALB Configuration:**
```yaml
# Application Load Balancer
Type: application
Scheme: internet-facing
IpAddressType: ipv4

Listeners:
  - Protocol: HTTPS
    Port: 443
    DefaultActions:
      - Type: forward
        TargetGroupArn: !Ref DataServiceTargetGroup
    Certificates:
      - CertificateArn: !Ref SSLCertificate
    
TargetGroup:
  Protocol: HTTP
  Port: 8080
  VpcId: !Ref VPC
  HealthCheckEnabled: true
  HealthCheckPath: /health
  HealthCheckIntervalSeconds: 30
  HealthyThresholdCount: 2
  UnhealthyThresholdCount: 3
  TargetType: ip
  Deregistration Delay: 30
```

---

## Disaster Recovery

### RPO & RTO Targets

| Scenario | RPO | RTO | Strategy |
|----------|-----|-----|----------|
| Regional Outage | 5 minutes | 15 minutes | Automatic failover |
| AZ Outage | 0 (no data loss) | 2 minutes | Multi-AZ deployment |
| Database Failure | 5 minutes | 10 minutes | Automated recovery |
| Application Failure | 0 | 5 minutes | Auto-restart + HPA |
| Complete Disaster | 15 minutes | 1 hour | Manual intervention |

### Automated Failover

**Trigger Conditions:**
1. Health check failures (3 consecutive)
2. Error rate >5% for 5 minutes
3. Latency P95 >2000ms for 5 minutes
4. Manual failover trigger

**Failover Process:**
```
1. Detect Failure
   └─> Route53 health check fails
   
2. Validate Failure
   └─> Multiple vantage points confirm
   
3. Initiate Failover
   └─> Route53 updates DNS (60s TTL)
   
4. Traffic Reroutes
   └─> Clients connect to healthy region
   
5. Monitor Recovery
   └─> Primary region health restoration
   
6. Automatic Failback (Optional)
   └─> Return to primary after 15 min stability
```

**Failover Script:**
```bash
#!/bin/bash
# Regional failover automation

FAILED_REGION="$1"
TARGET_REGION="$2"

echo "Initiating failover from $FAILED_REGION to $TARGET_REGION"

# 1. Update Route53 health check
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch file://failover-config.json

# 2. Scale up target region
kubectl --context=$TARGET_REGION scale deployment/data-service \
  --replicas=15 -n production

# 3. Verify target region capacity
kubectl --context=$TARGET_REGION wait \
  --for=condition=ready pod \
  -l app=data-service \
  --timeout=300s \
  -n production

# 4. Monitor metrics
echo "Failover complete. Monitoring..."
# Send alerts to PagerDuty/Slack
```

### Backup & Recovery

**QuestDB Backups:**
- Frequency: Every 6 hours
- Retention: 7 days (local), 30 days (S3)
- Cross-region replication: S3 to all regions
- Restore time: <10 minutes (local), <30 minutes (S3)

**Redis Backups:**
- RDB snapshots: Every hour
- AOF: Enabled (every second)
- Retention: 24 hours (local), 7 days (S3)
- Restore time: <5 minutes

**Configuration Backups:**
- GitOps: All Kubernetes manifests in Git
- Secrets: Vault with automated backups
- Infrastructure: Terraform state in S3

---

## Monitoring & Observability

### Multi-Region Metrics

**Cross-Region Latency:**
```promql
# Replication lag between regions
histogram_quantile(0.95,
  rate(questdb_replication_lag_seconds_bucket{
    source_region="us-east-1",
    target_region="eu-west-1"
  }[5m])
)
```

**Regional Health Score:**
```promql
# Composite health (0-1)
min(
  (up{job="data-service",region="us-east-1"} == 1) *
  (rate(http_requests_total{region="us-east-1",code=~"5.."}[5m]) < 0.01) *
  (histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{region="us-east-1"}[5m])) < 0.5)
)
```

**Traffic Distribution:**
```promql
# Requests per second by region
sum(rate(http_requests_total[1m])) by (region)
```

### Dashboards

**Global Overview Dashboard:**
- World map with regional health status
- Traffic distribution (pie chart)
- Cross-region latency heatmap
- Replication lag trends
- Failover history

**Per-Region Dashboard:**
- Regional request rate
- Latency percentiles (P50, P95, P99)
- Error rates
- Resource utilization
- Database performance

### Alerts

```yaml
# Critical: Regional outage
- alert: RegionalOutage
  expr: up{job="data-service"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Region {{ $labels.region }} is down"
    action: "Automatic failover initiated"

# Warning: High replication lag
- alert: HighReplicationLag
  expr: questdb_replication_lag_seconds > 300
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Replication lag {{ $labels.source_region }} → {{ $labels.target_region }} exceeds 5 minutes"

# Warning: Unbalanced traffic
- alert: TrafficImbalance
  expr: |
    abs(
      sum(rate(http_requests_total[5m])) by (region) /
      sum(rate(http_requests_total[5m])) - 0.33
    ) > 0.15
  for: 15m
  annotations:
    summary: "Traffic distribution imbalanced across regions"
```

---

## Cost Analysis

### Infrastructure Costs (Per Region)

| Component | us-east-1 | eu-west-1 | ap-southeast-1 | Total |
|-----------|-----------|-----------|----------------|-------|
| EKS Control Plane | $73 | $73 | $73 | $219 |
| EC2 Worker Nodes | $1,314 | $1,445 | $1,511 | $4,270 |
| QuestDB Storage (30TB) | $3,000 | $3,300 | $3,450 | $9,750 |
| Redis Cluster | $584 | $642 | $672 | $1,898 |
| Load Balancers | $438 | $482 | $504 | $1,424 |
| Data Transfer (intra) | $120 | $132 | $138 | $390 |
| Monitoring | $250 | $100 | $100 | $450 |
| **Regional Total** | **$5,779** | **$6,174** | **$6,448** | **$18,401** |

### Cross-Region Costs

| Item | Monthly Cost |
|------|--------------|
| Data Transfer (cross-region) | $1,200 |
| Route53 (GSLB) | $50 |
| VPC Peering | $0 (same account) |
| Backup Storage (S3 cross-region) | $150 |
| **Total Cross-Region** | **$1,400** |

### Total Multi-Region Cost

| Item | Monthly |
|------|---------|
| Regional Infrastructure | $18,401 |
| Cross-Region | $1,400 |
| **Total** | **$19,801** |

**vs. Single Region:** $3,538 (Week 9 optimized)  
**Increase:** $16,263/month (459% increase)

### Cost Optimization Strategies

1. **Reserved Instances:** -30% on compute = -$1,281/month
2. **Spot Instances:** -60% on 30% of fleet = -$770/month
3. **Storage Optimization:** Compress + retention = -$1,950/month
4. **Data Transfer Optimization:** Compression = -$240/month

**Optimized Multi-Region Cost:** $15,560/month  
**Cost per million trades:** $0.058 (vs $0.134 single region)

### ROI Analysis

**Costs:**
- Infrastructure: $15,560/month
- Implementation: $50,000 (one-time)
- Ongoing operations: $5,000/month

**Benefits:**
- **Revenue:** New markets accessible (Asia, Europe)
- **SLA Credits Avoided:** 99.99% vs 99.9% = $10k-50k/year
- **Competitive Advantage:** 50ms latency vs competitors' 200ms
- **Risk Mitigation:** Disaster recovery (unquantifiable)

**Break-even:** 6-12 months (with new market revenue)

---

## Implementation Roadmap

### Phase 1: Foundation (Week 10-11)

**Week 10:**
- ✅ Architecture design and approval
- ✅ Network topology setup (VPC, Transit Gateway)
- ✅ QuestDB clustering design
- ✅ Redis Active-Active planning

**Week 11:**
- Deploy secondary region (eu-west-1)
- Set up cross-region replication
- Implement Route53 GSLB
- Testing and validation

### Phase 2: Production Rollout (Week 12-13)

**Week 12:**
- Production deployment to eu-west-1
- Traffic migration (10% → 30% → 50%)
- Performance validation
- Failover testing

**Week 13:**
- Deploy third region (ap-southeast-1)
- Complete traffic migration
- Full disaster recovery drill
- Documentation and training

### Phase 3: Optimization (Week 14-16)

**Week 14-16:**
- Performance tuning
- Cost optimization
- Advanced monitoring
- Operational maturity

---

## Operational Procedures

### Daily Operations

**Health Monitoring:**
1. Check regional health dashboard (Grafana)
2. Verify replication lag <60s across all regions
3. Review overnight alerts and incidents
4. Validate traffic distribution

**Capacity Management:**
1. Monitor HPA behavior in each region
2. Check resource utilization trends
3. Review cost metrics
4. Plan capacity adjustments

### Failover Procedures

**Automatic Failover:**
- Triggered by Route53 health checks
- No manual intervention required
- Post-failover validation checklist

**Manual Failover:**
```bash
# Execute manual failover
./scripts/failover-region.sh --from us-east-1 --to eu-west-1

# Checklist:
# 1. Verify target region capacity
# 2. Update Route53 manually if needed
# 3. Monitor traffic shift
# 4. Validate SLOs in target region
# 5. Document in incident log
```

### Runbooks

1. **Regional Deployment** - Deploy new region
2. **Failover Execution** - Manual failover steps
3. **Failback Procedure** - Return to primary region
4. **Replication Issues** - Debug replication lag
5. **Traffic Rebalancing** - Adjust regional traffic
6. **Disaster Recovery** - Complete DR drill

---

## Security & Compliance

### Data Residency

- EU data stays in eu-west-1 (GDPR)
- US data in us-east-1
- Cross-region replication with encryption

### Network Security

- VPC peering with security groups
- TLS 1.3 for cross-region traffic
- Private subnets for databases
- WAF at regional load balancers

### Access Control

- Regional IAM roles
- Separate Kubernetes contexts
- Vault per region (federated)
- Audit logging to central SIEM

---

## Appendix

### A. Network Diagram

```
[Route53 GSLB: api.dataservice.global]
            |
    --------+--------+--------
    |               |        |
[us-east-1]   [eu-west-1] [ap-southeast-1]
    |               |        |
[VPC 10.0.0.0/16] [VPC 10.1.0.0/16] [VPC 10.2.0.0/16]
    |               |        |
    +-------[Transit Gateway]-------+
            |
    [VPC Peering / Direct Connect]
```

### B. Capacity Planning

| Region | Current | 2x Growth | 5x Growth |
|--------|---------|-----------|-----------|
| us-east-1 | 4k RPS | 8k RPS | 20k RPS |
| eu-west-1 | 3.5k RPS | 7k RPS | 17.5k RPS |
| ap-southeast-1 | 2.5k RPS | 5k RPS | 12.5k RPS |

### C. Contact Information

- **Architecture Team:** architecture@company.com
- **SRE Team:** sre@company.com
- **On-Call:** PagerDuty rotation
- **Escalation:** VP Engineering

---

**Document Status:** Approved for Implementation  
**Next Review:** End of Phase 1 (Week 11)  
**Version History:**
- v1.0: Initial design (Week 10)